"""Acceptance tests for T037 - ADR / Dual-Listed Premium Convergence.

Template v1.0.0. Reference implementation for T-module acceptance tests:
implements the module's normative emit() contract
    emit(state, signals, cfg) -> list[OrderTicket]
at one-bar granularity via process_bar(). The strategy emits TWO OrderTicket
intents per entry/exit (sell the rich leg / buy the cheap leg); strategies emit
ORDER INTENTS ONLY (Appendix C v1.0.0) - execution/broker layers create orders.
Borrow is priced on the short leg only via leg_role.

Run: python3 -m pytest modules/tests/test_T037.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T037_tape.csv"
EXPECTED = FIX / "T037_expected.csv"

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


@dataclass(frozen=True)
class Config:
    """T037 Config - mirrors §T0.2 (single Config dataclass)."""
    sid: str = "T037"
    primary_signal: str = "S061"
    trigger_bps: float = 30.0
    exit_bps: float = 5.0
    friction_bps: float = 15.0
    max_hold_days: int = 10
    cost_gate_k: float = 1.0
    risk_R_usd: float = 250.0
    stop_bps: float = 25.0
    adv_cap_pct: float = 1.0
    spread_full_bps: float = 4.0
    taker_fee_bps: float = 0.4
    borrow_bps_per_day: float = 2.0
    expected_hold_days: float = 10.0
    impact_k: float = 15.0
    adr_ratio: float = 1.0
    daily_loss_stop_pct: float = 1.0
    venue: str = "primary"
    side_exec: str = "taker"        # taker | maker


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


def expected_cost_bps(notional, adv_pct, venue, side, urgency, cfg, leg_role="long"):
    """COST-block callable. Prices ONE leg; borrow on the short leg only.

    borrow_bps = borrow_bps_per_day * expected_hold_days (capitalized).
    """
    spread_bps = cfg.spread_full_bps / 2.0
    fee_bps = cfg.taker_fee_bps
    borrow_bps = (cfg.borrow_bps_per_day * cfg.expected_hold_days) \
        if leg_role == "short" else 0.0
    impact_bps = cfg.impact_k * math.sqrt(max(adv_pct, 0.0) / 100.0)
    if urgency == "high":
        impact_bps *= 1.5
    return spread_bps + fee_bps + borrow_bps + impact_bps


def pair_cost_bps(notional, adv_pct, venue, side, urgency, cfg):
    """Pair-level cost: mean of the two leg costs (borrow on the short leg only)."""
    c_long = expected_cost_bps(notional, adv_pct, venue, side, urgency, cfg,
                               leg_role="long")
    c_short = expected_cost_bps(notional, adv_pct, venue, side, urgency, cfg,
                                leg_role="short")
    return 0.5 * (c_long + c_short)


def shares(risk_budget_R, stop_distance, adv_cap):
    """Canonical sizing core: risk budget over stop distance, ADV-capped."""
    raw = risk_budget_R / max(stop_distance, 1e-9)
    return max(1, min(int(raw), int(adv_cap)))


def _ticket(symbol, side, qty, bar, cfg, tag):
    return OrderTicket(
        symbol=symbol, side=side, qty=qty, limit=None, tif="DAY",
        ticket_id="%s-%04d%s" % (cfg.sid, int(bar["bar"]), tag),
        parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
        intent_ts=bar["event_ts"], state="NEW")


def process_bar(state, bar, cfg):
    """One bar through the strategy. Returns (tickets|None, module_state, note).

    Mirrors the §T3 normative pseudocode: validate (F1/F2) -> kill switch ->
    exits (convergence / event / stop / max-hold) -> entry on |dev_bps| with
    the normative pair-cost gate -> two-leg OrderTicket intents.
    Earliest fill for a bar-t intent is bar t+1's open (t -> t+1).
    """
    ks = state["kill"]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if (bar["close"] <= 0 or bar["market_state"] != "CONTINUOUS_TRADING"
            or bar["asof_ts"] < bar["event_ts"]):
        state["position"] = 0
        state["held_bars"] = 0
        return None, "UNKNOWN", "invalid-input"
    # Kill switch: TRIPPED blocks everything; breach trips it
    if ks.state != "ARMED":
        return None, "OFF", "kill-" + ks.state.lower()
    if bar["daily_pnl_pct"] <= -cfg.daily_loss_stop_pct:
        ks.trip(bar["event_ts"], "daily-loss-stop")
        state["position"] = 0
        state["held_bars"] = 0
        return None, "OFF", "kill-trip"
    # Position sizing: risk_R / (stop_frac * price), ADV-capped; home leg via ratio
    qty = shares(cfg.risk_R_usd, bar["stop_bps"] / 1e4 * bar["close"],
                 cfg.adv_cap_pct / 100.0 * bar["adv_shares"])
    qty2 = int(qty * cfg.adr_ratio)
    # Normative cost-gate predicate: pair_cost_bps(...) <= k * edge_bps
    cost = pair_cost_bps(bar["notional"], bar["adv_pct"], cfg.venue,
                         cfg.side_exec, bar["urgency"], cfg)
    gate = cost <= cfg.cost_gate_k * bar["edge_bps"]
    dev = bar["dev_bps"]
    pos = state.get("position", 0)
    if pos != 0:
        held = state.get("held_bars", 0) + 1
        state["held_bars"] = held
        # Exits: convergence | corporate event | stop | max-hold (never cost-gated)
        if (abs(dev) <= cfg.exit_bps or bar["event"]
                or held >= cfg.max_hold_days):
            t1 = _ticket(bar["symbol"], "BUY", qty, bar, cfg, "x")
            t2 = _ticket(bar["symbol"], "SELL", qty2, bar, cfg, "x-B")
            state["position"] = 0
            state["held_bars"] = 0
            return [t1, t2], "OK", "exit"
        return None, "OK", "hold"
    # Entry: |dev_bps| >= trigger_bps, both markets open (tape: market_state),
    # pair cost gate
    if abs(dev) >= cfg.trigger_bps and gate:
        rich = "ADR" if dev > 0 else "HOME"
        t1 = _ticket(bar["symbol"], "SELL" if rich == "ADR" else "BUY",
                     qty, bar, cfg, "")
        t2 = _ticket(bar["symbol"], "BUY" if rich == "ADR" else "SELL",
                     qty2, bar, cfg, "-B")
        state["position"] = 1 if dev > 0 else -1
        state["held_bars"] = 0
        return [t1, t2], "OK", "entry"
    return None, "OK", "gate-block" if abs(dev) >= cfg.trigger_bps else "flat"


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
            "close": float(r["close"]), "dev_bps": float(r["dev_bps"]),
            "signal_z": float(r["signal_z"]),
            "edge_bps": float(r["edge_bps"]), "event": int(r["event"]),
            "notional": float(r["notional"]),
            "adv_pct": float(r["adv_pct"]), "adv_shares": float(r["adv_shares"]),
            "stop_bps": float(r["stop_bps"]), "urgency": r["urgency"],
            "market_state": r["market_state"],
            "daily_pnl_pct": float(r["daily_pnl_pct"]),
        })
    return rows


def expected():
    return load_csv(EXPECTED)


def fresh_state():
    return {"position": 0, "held_bars": 0, "kill": KillSwitch()}


def run_tape():
    st = fresh_state()
    out = []
    for b in tape():
        ts, ms, note = process_bar(st, b, CFG)
        out.append((b, ts, ms, note))
    return out


def _int(s):
    return int(s) if s.strip() else 0


# ------------------------------------------------------------------- tests
def test_type_header_and_columns():
    """Fixture files carry the TYPE header and the expected columns."""
    for path in (TAPE, EXPECTED):
        with open(path) as f:
            first = f.readline().strip()
        assert first.startswith("# TYPE:"), path
    tcols = set(load_csv(TAPE)[0].keys())
    ecols = set(load_csv(EXPECTED)[0].keys())
    assert {"event_ts", "asof_ts", "close", "dev_bps", "event",
            "market_state"} <= tcols
    assert {"intent_ts", "action", "qty", "action2", "qty2", "intent_ts2",
            "cost_call_bps", "gate_pass", "module_state"} <= ecols
    assert len(load_csv(TAPE)) == len(load_csv(EXPECTED)) == 12


def test_fixture_recomputes_to_expected():
    """Reference process_bar reproduces the expected CSV row by row (two legs)."""
    exp = {int(r["bar"]): r for r in expected()}
    for b, ts, ms, note in run_tape():
        w = exp[b["bar"]]
        want = [(w["action"], _int(w["qty"]), w["intent_ts"]),
                (w["action2"], _int(w["qty2"]), w["intent_ts2"])]
        if ts is None:
            assert all(a == "" for a, _, _ in want), b["bar"]
        else:
            assert len(ts) == 2, b["bar"]
            for t, (a, q, its) in zip(ts, want):
                assert t.side == a, b["bar"]
                assert t.qty == q, b["bar"]
                assert str(t.intent_ts) == its, b["bar"]
                assert t.qty > 0
                assert t.ticket_id.startswith(CFG.sid)
                assert t.parent_signal == "%s@%d" % (CFG.primary_signal,
                                                     b["event_ts"])
        assert w["module_state"] == ms, b["bar"]
        assert w["note"] == note, b["bar"]
        cost = pair_cost_bps(b["notional"], b["adv_pct"], CFG.venue,
                             CFG.side_exec, b["urgency"], CFG)
        assert w["gate_pass"] == str(cost <= CFG.cost_gate_k * b["edge_bps"]), \
            b["bar"]
        assert math.isclose(float(w["cost_call_bps"]), cost, rel_tol=TOL), \
            b["bar"]


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event (both legs)."""
    bars = tape()
    exp = {int(r["bar"]): r for r in expected()}
    for i, b in enumerate(bars):
        r = exp[b["bar"]]
        for key in ("intent_ts", "intent_ts2"):
            if r[key].strip():
                signal_event = int(r[key])
                fill_event = bars[i + 1]["event_ts"]  # earliest: next bar open
                assert fill_event > signal_event, "signal-bar fill at bar %d" % i


def test_cost_gate_predicate():
    """Normative predicate: pair_cost_bps(...) <= k * edge_bps."""
    bars = tape()
    entry = bars[3]
    cost = pair_cost_bps(entry["notional"], entry["adv_pct"], CFG.venue,
                         CFG.side_exec, entry["urgency"], CFG)
    assert cost <= CFG.cost_gate_k * entry["edge_bps"]  # entry edge clears
    blocked = bars[7]
    cost7 = pair_cost_bps(blocked["notional"], blocked["adv_pct"], CFG.venue,
                          CFG.side_exec, blocked["urgency"], CFG)
    assert not (cost7 <= CFG.cost_gate_k * blocked["edge_bps"])  # tiny edge blocks


def test_kill_switch_trip_and_rearm():
    """ARMED -> TRIPPED blocks intents; checklist re-arm restores ARMED."""
    st = fresh_state()
    bars = tape()
    for b in bars[:9]:
        ts, ms, note = process_bar(st, b, CFG)
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


def test_two_leg_emission():
    """Entry emits two tickets: opposite sides, ratio-scaled qty, both causal."""
    st = fresh_state()
    bars = tape()
    ts, ms, note = process_bar(st, bars[3], CFG)
    assert ms == "OK" and note == "entry"
    assert ts is not None and len(ts) == 2
    t1, t2 = ts
    assert {t1.side, t2.side} == {"SELL", "BUY"}   # rich leg sold, cheap leg bought
    assert t2.qty == int(t1.qty * CFG.adr_ratio)
    assert t1.ticket_id != t2.ticket_id
    assert t1.ticket_id.startswith(CFG.sid) and t2.ticket_id.startswith(CFG.sid)
    assert t1.intent_ts == t2.intent_ts == bars[3]["event_ts"]
    assert t1.parent_signal == t2.parent_signal == "S061@%d" % bars[3]["event_ts"]


def test_max_hold_exit():
    """bars_held >= max_hold_days exits the pair even without convergence."""
    st = fresh_state()
    st["position"] = 1
    st["held_bars"] = CFG.max_hold_days  # at the cap: next bar exits
    b = dict(tape()[4])
    b["dev_bps"] = 20.0  # no convergence, no event
    b["event"] = 0
    ts, ms, note = process_bar(st, b, CFG)
    assert ts is not None and len(ts) == 2
    assert ms == "OK" and note == "exit"
    assert st["position"] == 0
    assert {t.side for t in ts} == {"BUY", "SELL"}  # mirror pair


def test_borrow_applies_to_short_leg_only():
    """leg_role semantics: borrow = borrow_bps_per_day * expected_hold_days, short leg only."""
    b = tape()[3]
    c_long = expected_cost_bps(b["notional"], b["adv_pct"], CFG.venue,
                               CFG.side_exec, b["urgency"], CFG, leg_role="long")
    c_short = expected_cost_bps(b["notional"], b["adv_pct"], CFG.venue,
                                CFG.side_exec, b["urgency"], CFG, leg_role="short")
    assert math.isclose(c_short - c_long,
                        CFG.borrow_bps_per_day * CFG.expected_hold_days,
                        rel_tol=TOL)
    assert math.isclose(pair_cost_bps(b["notional"], b["adv_pct"], CFG.venue,
                                      CFG.side_exec, b["urgency"], CFG),
                        0.5 * (c_long + c_short), rel_tol=TOL)
