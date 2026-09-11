"""Acceptance tests for T026 - Kyle-Lambda Participation Throttle.

Template v1.0.0. Reference implementation of the module's normative emit()
contract:
    emit(state, signals, cfg) -> list[OrderTicket]
at one-bar granularity via process_bar(). Strategies emit ORDER INTENTS
ONLY (Appendix C v1.0.0); execution/broker layers create orders.

Entry = z-trigger AND lambda_ok AND illiq_ok AND no-spike AND spacing_ok
AND cost-gate AND child_qty >= min_child. Sizing spends an all-in slice
budget R: predicted temporary impact $ + expected cost $ <= R.

Run: python3 -m pytest modules/tests/test_T026.py -q   (from repo root)
"""
import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T026_tape.csv"
EXPECTED = FIX / "T026_expected.csv"

TOL = 1e-9  # tolerance on float comparisons


@dataclass(frozen=True)
class OrderTicket:
    symbol: str
    side: str            # BUY | SELL | SHORT - intent, not a wire order
    qty: int             # shares, integer, > 0
    limit: float | None  # limit price; None = marketable intent
    tif: str             # DAY | IOC | FOK | GTC | OPG | CLS
    ticket_id: str       # module-generated idempotency key
    parent_signal: str   # "S<nnn>@<computed_at_ns>" - full provenance
    intent_ts: int       # int64 ns UTC - when the intent was emitted
    state: str           # NEW | WORKING | ... (intent-side mirror only)


@dataclass
class Config:
    sid: str = "T026"
    primary_signal: str = "S010"
    z_entry: float = 2.5
    z_exit: float = 1.0
    cost_gate_k: float = 0.5
    risk_R_usd: float = 250.0
    stop_bps: float = 25.0
    participation_cap: float = 0.10
    min_child: int = 100
    lambda_max: float = 1e-3
    lambda_spike_mult: float = 3.0
    lambda_spike_lookback: int = 5
    illiq_cap_bps: float = 5.0
    half_life_spacing_mult: float = 3.0
    vol_regime_mult: float = 3.0
    vol_median: float = 0.02
    parent_total: int = 5000
    slice_ref_notional: float = 100000.0
    spread_full_bps: float = 2.0
    taker_fee_bps: float = 0.3
    impact_k: float = 30.0
    daily_loss_stop_pct: float = 1.0
    venue: str = "primary"
    side_exec: str = "taker"        # taker | maker
    urgency_mult: float = 1.5


class KillSwitch:
    """Kill-switch state machine: ARMED -> TRIPPED -> RECOVERY -> ARMED."""

    def __init__(self):
        self.state = "ARMED"
        self.trips = []

    def trip(self, ts, reason):
        if self.state == "ARMED":
            self.state = "TRIPPED"
            self.trips.append((int(ts), str(reason)))

    def begin_recovery(self):
        if self.state == "TRIPPED":
            self.state = "RECOVERY"

    def rearm(self, checklist_ok):
        """Re-arm only from RECOVERY with every checklist item True."""
        if self.state == "RECOVERY" and all(checklist_ok):
            self.state = "ARMED"
            return True
        return False


def expected_cost_bps(notional, adv_pct, venue, side, urgency, cfg):
    """4-component cost stack (COST-block callable). Buy-leg reference;
    sell-leg regulatory fees (~0.21 bps) are added by the harness, not here."""
    spread_bps = cfg.spread_full_bps / 2.0
    fee_bps = cfg.taker_fee_bps if side == "taker" else 0.0
    borrow_bps = 0.0  # long-only sleeve: no borrow
    impact_bps = cfg.impact_k * math.sqrt(max(adv_pct, 0.0) / 100.0)
    if urgency == "high":
        impact_bps *= cfg.urgency_mult
    return spread_bps + fee_bps + borrow_bps + impact_bps


def size_child(bar, cost_bps, cfg, state):
    """Fenced sizing: shares = f(risk_budget_R, stop_distance, vol_estimate,
    ADV_cap, cost). All-in slice budget: predicted impact $ + expected cost $
    <= R. Returns integer shares >= 0."""
    cost_usd = cost_bps / 1e4 * cfg.slice_ref_notional
    budget_net = max(cfg.risk_R_usd - cost_usd, 0.0)
    px = bar["close"]
    lam = bar["lambda_hat"]
    impact_leg = budget_net / max(lam * px, 1e-12)          # Kyle budget leg
    stop_leg = budget_net / max(bar["stop_bps"] / 1e4 * px, 1e-12)  # stop leg
    # R001-style vol regime: halve the participation cap when realized vol
    # exceeds vol_regime_mult * vol_median
    cap_mult = 0.5 if bar["vol_est"] > cfg.vol_regime_mult * cfg.vol_median else 1.0
    adv_leg = cap_mult * cfg.participation_cap * bar["adv_shares"]
    parent_leg = cfg.parent_total - state["filled"]
    return int(max(min(impact_leg, stop_leg, adv_leg, parent_leg), 0))


def process_bar(state, bar, cfg):
    """One bar through the strategy. Returns (ticket|None, module_state, note).

    Mirrors the module's normative pseudocode: validate (F1/F2) -> kill
    switch -> lambda-validity streak -> spike abort (F3) -> gates ->
    normative cost-gate predicate -> entry/exit rules.
    Earliest fill for a bar-t intent is bar t+1's open (t -> t+1).
    """
    ks = state["kill"]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if (bar["close"] <= 0 or bar["market_state"] != "CONTINUOUS_TRADING"
            or bar["asof_ts"] < bar["event_ts"]):
        state["position"] = 0
        state["qty"] = 0
        return None, "UNKNOWN", "invalid-input"
    # Kill switch: TRIPPED blocks everything; breaches trip it
    if ks.state != "ARMED":
        return None, "OFF", "kill-" + ks.state.lower()
    # lambda validity streak: NaN/non-positive lambda_hat 3 slices running
    lam = bar["lambda_hat"]
    if not (lam > 0.0) or (isinstance(lam, float) and math.isnan(lam)):
        state["lambda_bad_streak"] += 1
    else:
        state["lambda_bad_streak"] = 0
    if state["lambda_bad_streak"] >= 3:
        ks.trip(bar["event_ts"], "lambda-invalid-3x")
        state["position"] = 0
        state["qty"] = 0
        state["filled"] = 0
        return None, "OFF", "kill-trip"
    if bar["daily_pnl_pct"] <= -cfg.daily_loss_stop_pct:
        ks.trip(bar["event_ts"], "daily-loss-stop")
        state["position"] = 0
        state["qty"] = 0
        state["filled"] = 0
        return None, "OFF", "kill-trip"
    # F3/C12: lambda spike abort uses the PRIOR-bar median only (causality:
    # the current bar must not inflate its own benchmark)
    hist = state["lambda_hist"]
    if len(hist) >= cfg.lambda_spike_lookback:
        med = statistics.median(hist[-cfg.lambda_spike_lookback:])
        if lam > cfg.lambda_spike_mult * med:
            hist.append(lam)
            return None, "UNKNOWN", "lambda-spike-abort"  # ABORT slice; resume next clean slice
    hist.append(lam)
    # Gates
    z = bar["signal_z"]
    lambda_ok = 0.0 < lam < cfg.lambda_max
    illiq_ok = bar["illiq_bps"] <= cfg.illiq_cap_bps
    cost = expected_cost_bps(bar["notional"], bar["adv_pct"], cfg.venue,
                             cfg.side_exec, bar["urgency"], cfg)
    gate = cost <= cfg.cost_gate_k * bar["edge_bps"]
    pos = state["position"]
    if pos == 0:
        if abs(z) >= cfg.z_entry and lambda_ok and illiq_ok and gate:
            # Resiliency spacing: child spacing >= m * half-life
            last = state["last_child_ts"]
            min_gap_ns = int(cfg.half_life_spacing_mult * bar["half_life_s"] * 1e9)
            if last is not None and bar["event_ts"] - last < min_gap_ns:
                return None, "OK", "spacing-hold"
            qty = size_child(bar, cost, cfg, state)
            if qty >= cfg.min_child:
                ticket = OrderTicket(
                    symbol=bar["symbol"], side="BUY", qty=qty, limit=None,
                    tif="DAY", ticket_id="%s-%04d" % (cfg.sid, int(bar["bar"])),
                    parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
                    intent_ts=bar["event_ts"], state="NEW")
                state["position"] = 1
                state["qty"] = qty
                state["filled"] += qty
                state["last_child_ts"] = bar["event_ts"]
                return ticket, "OK", "entry"
            return None, "OK", "child-too-small"
        if abs(z) >= cfg.z_entry:
            return None, "OK", "gate-block"  # trigger fired; a gate vetoed
        return None, "OK", "flat"
    # Position open: exit on z through the exit band (exits never cost-gated)
    if abs(z) <= cfg.z_exit:
        ticket = OrderTicket(
            symbol=bar["symbol"], side="SELL", qty=state["qty"], limit=None,
            tif="DAY", ticket_id="%s-%04dx" % (cfg.sid, int(bar["bar"])),
            parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
            intent_ts=bar["event_ts"], state="NEW")
        state["position"] = 0
        state["qty"] = 0
        return ticket, "OK", "exit"
    return None, "OK", "hold"


CFG = Config()


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({
            "bar": int(r["bar"]), "event_ts": int(r["event_ts"]),
            "asof_ts": int(r["asof_ts"]), "symbol": r["symbol"],
            "close": float(r["close"]), "signal_z": float(r["signal_z"]),
            "edge_bps": float(r["edge_bps"]), "notional": float(r["notional"]),
            "adv_pct": float(r["adv_pct"]), "adv_shares": float(r["adv_shares"]),
            "stop_bps": float(r["stop_bps"]), "urgency": r["urgency"],
            "market_state": r["market_state"],
            "daily_pnl_pct": float(r["daily_pnl_pct"]),
            "lambda_hat": float(r["lambda_hat"]),
            "illiq_bps": float(r["illiq_bps"]),
            "half_life_s": float(r["half_life_s"]),
            "vol_est": float(r["vol_est"]),
        })
    return rows


def expected():
    return load_csv(EXPECTED)


def fresh_state():
    return {"position": 0, "qty": 0, "filled": 0, "lambda_hist": [],
            "last_child_ts": None, "lambda_bad_streak": 0, "kill": KillSwitch()}


def run_tape():
    st = fresh_state()
    out = []
    for b in tape():
        t, ms, note = process_bar(st, b, CFG)
        out.append((b, t, ms, note))
    return out


# ------------------------------------------------------------------- tests
def test_type_header_and_columns():
    """Fixture files carry the TYPE header and the expected columns."""
    for path in (TAPE, EXPECTED):
        with open(path) as f:
            first = f.readline().strip()
        assert first.startswith("# TYPE:"), path
    tcols = set(load_csv(TAPE)[0].keys())
    ecols = set(load_csv(EXPECTED)[0].keys())
    assert {"event_ts", "asof_ts", "close", "signal_z", "market_state",
            "lambda_hat", "illiq_bps", "half_life_s", "vol_est"} <= tcols
    assert {"intent_ts", "action", "qty", "cost_call_bps",
            "gate_pass", "module_state"} <= ecols
    assert len(load_csv(TAPE)) == len(load_csv(EXPECTED)) == 12


def test_fixture_recomputes_to_expected():
    """Reference process_bar reproduces the expected CSV row by row."""
    exp = {int(r["bar"]): r for r in expected()}
    for b, t, ms, note in run_tape():
        w = exp[b["bar"]]
        want_action = t.side if t else "HOLD"
        assert w["action"] == want_action, b["bar"]
        assert int(w["qty"]) == (t.qty if t else 0), b["bar"]
        assert w["module_state"] == ms, b["bar"]
        assert w["note"] == note, b["bar"]
        assert w["gate_pass"] == str(
            float(w["cost_call_bps"]) <= CFG.cost_gate_k * b["edge_bps"]), b["bar"]
        assert math.isclose(float(w["cost_call_bps"]),
                            expected_cost_bps(b["notional"], b["adv_pct"], CFG.venue,
                                              CFG.side_exec, b["urgency"], CFG),
                            rel_tol=TOL), b["bar"]
        assert math.isclose(float(w["lambda_hat"]), b["lambda_hat"],
                            rel_tol=TOL), b["bar"]
        if t is not None:
            assert t.qty > 0
            assert t.side in ("BUY", "SELL", "SHORT")
            assert t.intent_ts == b["event_ts"]
            assert t.ticket_id.startswith(CFG.sid)
            assert t.parent_signal == "%s@%d" % (CFG.primary_signal, b["event_ts"])
    # bar 3 entry quantity is the all-in-budget sizing, not a re-sized stop leg
    e3 = exp[3]
    assert int(e3["qty"]) == 861


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    bars = tape()
    exp = {int(r["bar"]): r for r in expected()}
    for i, b in enumerate(bars):
        r = exp[b["bar"]]
        if r["intent_ts"]:
            signal_event = int(r["intent_ts"])
            fill_event = bars[i + 1]["event_ts"]  # earliest fill: next bar's open
            assert fill_event > signal_event, "signal-bar fill at bar %d" % i


def test_cost_gate_predicate():
    """Normative predicate: expected_cost_bps(...) <= k * edge_bps."""
    bars = tape()
    entry = bars[3]
    cost_bps = expected_cost_bps(entry["notional"], entry["adv_pct"], CFG.venue,
                                 CFG.side_exec, entry["urgency"], CFG)
    assert cost_bps <= CFG.cost_gate_k * entry["edge_bps"]  # entry edge clears
    blocked = bars[7]
    cost7 = expected_cost_bps(blocked["notional"], blocked["adv_pct"], CFG.venue,
                              CFG.side_exec, blocked["urgency"], CFG)
    assert not (cost7 <= CFG.cost_gate_k * blocked["edge_bps"])  # tiny edge blocks


def test_kill_switch_trip_and_rearm():
    """ARMED -> TRIPPED blocks intents; checklist re-arm restores ARMED."""
    st = fresh_state()
    bars = tape()
    for b in bars[:9]:
        t, ms, note = process_bar(st, b, CFG)
    assert st["kill"].state == "ARMED", "kill must not trip before bar 9"
    b9 = bars[9]
    t9, ms9, note9 = process_bar(st, b9, CFG)
    assert t9 is None and ms9 == "OFF" and note9 == "kill-trip"
    assert st["kill"].state == "TRIPPED"
    # still tripped on the next bar: no intents while TRIPPED
    t10, ms10, note10 = process_bar(st, bars[10], CFG)
    assert t10 is None and ms10 == "OFF" and note10 == "kill-tripped"
    # re-arm checklist: RECOVERY + all-true checklist -> ARMED
    st["kill"].begin_recovery()
    assert st["kill"].state == "RECOVERY"
    assert st["kill"].rearm([True, True, True, True, True]) is True
    assert st["kill"].state == "ARMED"
    # and a partial checklist must NOT re-arm
    st["kill"].trip(b9["event_ts"], "retest")
    st["kill"].begin_recovery()
    assert st["kill"].rearm([True, True, False, True, True]) is False
    assert st["kill"].state == "RECOVERY"


def test_invalid_input_unknown():
    """F1/F2: halted or invalid bars -> UNKNOWN, never interpolate."""
    st = fresh_state()
    bars = tape()
    t8, ms8, note8 = process_bar(st, bars[8], CFG)  # HALTED bar
    assert t8 is None and ms8 == "UNKNOWN" and note8 == "invalid-input"
    bad = dict(bars[3])
    bad["close"] = -1.0  # invalid price
    t, ms, _ = process_bar(fresh_state(), bad, CFG)
    assert t is None and ms == "UNKNOWN"


def test_lambda_spike_aborts_slice():
    """F3/C12: lambda_hat > 3x prior-bar median -> ABORT slice, UNKNOWN,
    position retained for the next clean slice."""
    st = fresh_state()
    bars = tape()
    for b in bars[:5]:
        t, ms, note = process_bar(st, b, CFG)
    assert st["position"] == 1 and st["qty"] == 861  # entered at bar 3
    t5, ms5, note5 = process_bar(st, bars[5], CFG)   # lambda 8e-5 vs 3x median 7.5e-5
    assert t5 is None and ms5 == "UNKNOWN" and note5 == "lambda-spike-abort"
    assert st["position"] == 1 and st["qty"] == 861  # slice aborted, not flattened
    # next clean bar resumes: bar 6 z through the exit band -> exit
    t6, ms6, note6 = process_bar(st, bars[6], CFG)
    assert t6 is not None and t6.side == "SELL" and t6.qty == 861
    assert ms6 == "OK" and note6 == "exit"


def test_illiq_gate_vetoes_entry():
    """S011 screen: illiq_bps above the cap vetoes entry even on trigger."""
    st = fresh_state()
    bars = tape()
    bad = dict(bars[3])
    bad["illiq_bps"] = 12.0  # above the 5 bps cap
    t, ms, note = process_bar(st, bad, CFG)
    assert t is None and ms == "OK" and note == "gate-block"
    assert st["position"] == 0


def test_resiliency_spacing_suppresses_early_child():
    """Child spacing >= m * half-life: a trigger 120 s after the last child
    (required 270 s) is held, not emitted."""
    st = fresh_state()
    bars = tape()
    t3, ms3, note3 = process_bar(st, bars[3], CFG)
    assert t3 is not None and note3 == "entry"
    early = dict(bars[3])
    early["bar"] = 99
    early["event_ts"] = bars[3]["event_ts"] + 120_000_000_000  # +120 s < 270 s
    early["asof_ts"] = early["event_ts"] + 250_000
    st["position"] = 0  # pretend flat so the trigger is evaluated
    t, ms, note = process_bar(st, early, CFG)
    assert t is None and ms == "OK" and note == "spacing-hold"


def test_sizing_legs():
    """size_child = min(Kyle impact leg, stop leg, ADV-cap leg, parent leg),
    with the cost haircut and the R001 vol-halve."""
    bars = tape()
    b3 = bars[3]
    st = fresh_state()
    cost = expected_cost_bps(b3["notional"], b3["adv_pct"], CFG.venue,
                             CFG.side_exec, b3["urgency"], CFG)
    # tape bar 3: stop leg binds (861) under the impact leg (86134)
    assert size_child(b3, cost, CFG, st) == 861
    # impact leg binds when lambda_hat is large relative to the stop
    big_lam = dict(b3)
    big_lam["lambda_hat"] = 0.0009
    big_lam["stop_bps"] = 5.0
    assert size_child(big_lam, cost, CFG, st) == 2392
    # ADV-cap leg binds on tiny ADV
    tiny_adv = dict(b3)
    tiny_adv["adv_shares"] = 1000.0
    assert size_child(tiny_adv, cost, CFG, st) == 100
    # parent-remaining leg binds near parent completion
    st2 = fresh_state()
    st2["filled"] = 4950
    assert size_child(b3, cost, CFG, st2) == 50
    # cost haircut: zero cost leaves the full R for impact -> larger child
    assert size_child(b3, 0.0, CFG, st) == 997
    assert size_child(b3, cost, CFG, st) < size_child(b3, 0.0, CFG, st)
    # R001 vol-halve: high vol_est halves the ADV-cap leg
    calm = dict(b3)
    calm["adv_shares"] = 4000.0
    calm["vol_est"] = 0.02
    stressed = dict(calm)
    stressed["vol_est"] = 0.10  # > 3 * 0.02 -> halve
    assert size_child(stressed, cost, CFG, st) == 200
    assert size_child(calm, cost, CFG, st) == 400


def test_lambda_invalid_streak_trips_kill():
    """Three consecutive invalid lambda_hat readings trip the kill switch."""
    st = fresh_state()
    bars = tape()
    bad = dict(bars[3])
    bad["lambda_hat"] = -0.001
    for i in range(2):
        b = dict(bad)
        b["event_ts"] = bars[3]["event_ts"] + i * 300_000_000_000
        b["asof_ts"] = b["event_ts"] + 250_000
        t, ms, note = process_bar(st, b, CFG)
        assert st["kill"].state == "ARMED"
        assert ms == "OK"  # vetoed entry, not yet tripped
    b = dict(bad)
    b["event_ts"] = bars[3]["event_ts"] + 2 * 300_000_000_000
    b["asof_ts"] = b["event_ts"] + 250_000
    t, ms, note = process_bar(st, b, CFG)
    assert t is None and ms == "OFF" and note == "kill-trip"
    assert st["kill"].state == "TRIPPED"
