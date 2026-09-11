"""Acceptance tests for T040 - PCA Eigenportfolio Residual Reversal.

Template v1.0.0. Concrete sketch: loads the fixture tape, runs the module's
reference emit() (normative pseudocode via process_bar), and asserts the
TYPE header, fixture-vs-expected agreement, causality (no-signal-bar fills),
the cost-gate predicate, kill-switch trip/re-arm, and invalid-input handling.

Run: python3 -m pytest modules/tests/test_T040.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T040_tape.csv"
EXPECTED = FIX / "T040_expected.csv"

TOL = 1e-9  # tolerance on float comparisons



"""Reference implementation for T-module acceptance tests (shared sketch).

Implements the module's normative emit() contract:
    emit(state, signals, cfg) -> list[OrderTicket]
at one-bar granularity via process_bar(). Strategies emit ORDER INTENTS
ONLY (Appendix C v1.0.0); execution/broker layers create orders.
"""
import math
from dataclasses import dataclass


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
    sid: str = "T040"
    primary_signal: str = "S080"
    z_entry: float = 1.25
    z_exit: float = 0.5
    cost_gate_k: float = 0.5
    risk_R_usd: float = 250.0
    stop_bps: float = 25.0
    adv_cap_pct: float = 1.0
    spread_full_bps: float = 3.0
    taker_fee_bps: float = 0.30
    maker_rebate_bps: float = -0.20
    borrow_bps_per_day: float = 0.06   # GC easy-to-borrow, documented
    expected_hold_days: float = 5.0    # residual half-life scale, example
    short_leg_fraction: float = 0.5    # dollar-neutral residual book, example
    impact_k: float = 15.0
    side_exec: str = "taker"           # taker | maker
    daily_loss_stop_pct: float = 1.5
    venue: str = "primary"
    cooldown_sessions: int = 1         # post-exit cooldown, C10
    crowding_mult: float = 2.0         # crowding breaker multiple


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
    """4-component cost stack (COST-block callable).

    side = taker|maker|mixed is the EXECUTION side. Borrow is the book-average
    for the dollar-neutral residual book: borrow_bps_per_day x
    expected_hold_days x short_leg_fraction.
    """
    spread_bps = cfg.spread_full_bps / 2.0
    fee_bps = cfg.maker_rebate_bps if side == "maker" else cfg.taker_fee_bps
    borrow_bps = (cfg.borrow_bps_per_day * cfg.expected_hold_days
                  * cfg.short_leg_fraction)
    impact_bps = cfg.impact_k * math.sqrt(max(adv_pct, 0.0) / 100.0)
    if urgency == "high":
        impact_bps *= 1.5
    return spread_bps + fee_bps + borrow_bps + impact_bps


def shares(risk_budget_R, stop_distance_bps, vol_estimate_bps, ADV_cap_shares,
           cost_bps, px):
    """Fenced sizing: shares = f(risk_budget_R, stop_distance, vol_estimate,
    ADV_cap, cost). cost_bps is gate-consumed upstream (cost <= k*edge_bps);
    shares are risk-capped, not cost-derated [default]."""
    stop_bps = max(stop_distance_bps, vol_estimate_bps)  # wider of fixed/vol stop
    raw = risk_budget_R / max(stop_bps / 1e4 * px, 1e-9)
    return max(1, min(int(raw), int(ADV_cap_shares)))


def process_bar(state, bar, cfg):
    """One bar through the strategy. Returns (ticket|None, module_state, note).

    Mirrors the module's normative pseudocode: validate (F1/F2) -> kill
    switch -> size -> normative cost-gate predicate -> entry/exit rules.
    Earliest fill for a bar-t intent is bar t+1's open (t -> t+1).
    """
    ks = state["kill"]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if (bar["close"] <= 0 or bar["market_state"] != "CONTINUOUS_TRADING"
            or bar["asof_ts"] < bar["event_ts"]):
        state["position"] = 0
        return None, "UNKNOWN", "invalid-input"
    # Kill switch: TRIPPED blocks everything; breach trips it
    if ks.state != "ARMED":
        return None, "OFF", "kill-" + ks.state.lower()
    if bar["daily_pnl_pct"] <= -cfg.daily_loss_stop_pct:
        ks.trip(bar["event_ts"], "daily-loss-stop")
        state["position"] = 0
        return None, "OFF", "kill-trip"
    # Position sizing: shares(risk_budget_R, stop_distance, vol_estimate,
    # ADV_cap, cost, px). In this fixture stop_bps doubles as the
    # vol-calibrated stop (vol_estimate_bps = stop_bps) [example].
    cost = expected_cost_bps(bar["notional"], bar["adv_pct"], cfg.venue,
                             cfg.side_exec, bar["urgency"], cfg)
    cap_qty = int(cfg.adv_cap_pct / 100.0 * bar["adv_shares"])
    qty = shares(cfg.risk_R_usd, bar["stop_bps"], bar["stop_bps"],
                 cap_qty, cost, bar["close"])
    # Normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
    gate = cost <= cfg.cost_gate_k * bar["edge_bps"]
    z = bar["signal_z"]
    pos = state.get("position", 0)
    if pos == 0:
        if abs(z) >= cfg.z_entry:
            # C10 post-exit cooldown: suppress re-entry until it elapses
            if bar["event_ts"] < state.get("cooldown_until", 0):
                return None, "OK", "cooldown"
            if gate:
                side = "SHORT" if z > 0 else "BUY"  # fade the residual
                ticket = OrderTicket(
                    symbol=bar["symbol"], side=side, qty=qty,
                    limit=(round(bar["close"], 2) if cfg.side_exec == "maker" else None),
                    tif="DAY", ticket_id="%s-%04d" % (cfg.sid, int(bar["bar"])),
                    parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
                    intent_ts=bar["event_ts"], state="NEW")
                state["position"] = -1 if side == "SHORT" else 1
                return ticket, "OK", "entry"
            return None, "OK", "gate-block"
        return None, "OK", "flat"
    # Position open: exit on z through the exit band (exits never cost-gated)
    if abs(z) <= cfg.z_exit:
        exit_side = "SELL" if pos > 0 else "BUY"
        ticket = OrderTicket(
            symbol=bar["symbol"], side=exit_side, qty=qty,
            limit=(round(bar["close"], 2) if cfg.side_exec == "maker" else None),
            tif="DAY", ticket_id="%s-%04dx" % (cfg.sid, int(bar["bar"])),
            parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
            intent_ts=bar["event_ts"], state="NEW")
        state["position"] = 0
        # C10: arm the post-exit cooldown
        state["cooldown_until"] = (bar["event_ts"]
                                   + cfg.cooldown_sessions * 86_400_000_000_000)
        return ticket, "OK", "exit"
    return None, "OK", "hold"


CFG = Config(
    sid="T040", primary_signal="S080",
    z_entry=1.25, z_exit=0.5, cost_gate_k=0.5,
    risk_R_usd=250, stop_bps=25, adv_cap_pct=1.0,
    spread_full_bps=3.0, taker_fee_bps=0.3,
    maker_rebate_bps=-0.2, side_exec="taker",
    borrow_bps_per_day=0.06, expected_hold_days=5,
    short_leg_fraction=0.5, impact_k=15.0,
    daily_loss_stop_pct=1.5, venue="primary",
    cooldown_sessions=1, crowding_mult=2.0)


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
        })
    return rows


def expected():
    return load_csv(EXPECTED)


def fresh_state():
    return {"position": 0, "kill": KillSwitch()}


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
    assert {"event_ts", "asof_ts", "close", "signal_z", "market_state"} <= tcols
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
        if t is not None:
            assert t.qty > 0
            assert t.side in ("BUY", "SELL", "SHORT", "LONG")
            assert t.intent_ts == b["event_ts"]
            assert t.ticket_id.startswith(CFG.sid)
            assert t.parent_signal == "%s@%d" % (CFG.primary_signal, b["event_ts"])


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
    edge_bps = entry["edge_bps"]
    assert cost_bps <= CFG.cost_gate_k * edge_bps  # entry edge clears the gate
    if cost_bps > 0:
        blocked = bars[7]
        cost7 = expected_cost_bps(blocked["notional"], blocked["adv_pct"], CFG.venue,
                                  CFG.side_exec, blocked["urgency"], CFG)
        assert not (cost7 <= CFG.cost_gate_k * blocked["edge_bps"])  # tiny edge blocks
    else:
        # zero-cost overlay/filter/normalizer: the predicate holds vacuously
        assert cost_bps == 0.0


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


def test_post_exit_cooldown():
    """C10: after an exit, re-entry is suppressed for cooldown_sessions."""
    st = fresh_state()
    base = tape()[3]
    day_ns = 86_400_000_000_000

    def synth(ts, z, edge):
        b = dict(base)
        b["event_ts"] = ts
        b["asof_ts"] = ts + 25_000_000
        b["signal_z"] = z
        b["edge_bps"] = edge
        b["daily_pnl_pct"] = 0.05
        b["market_state"] = "CONTINUOUS_TRADING"
        return b

    t0 = base["event_ts"]
    # entry (big edge clears the gate)
    t, ms, note = process_bar(st, synth(t0, 1.5, 50.0), CFG)
    assert t is not None and note == "entry"
    # exit (|z| through the exit band)
    t, ms, note = process_bar(st, synth(t0 + day_ns, 0.2, 50.0), CFG)
    assert t is not None and note == "exit"
    # 12h later: |z| >= entry with a huge edge -> cooldown veto, not gate
    t, ms, note = process_bar(st, synth(t0 + day_ns + day_ns // 2, 1.6, 500.0), CFG)
    assert t is None and ms == "OK" and note == "cooldown"
    # 24h after the exit: cooldown elapsed -> entry allowed again
    t, ms, note = process_bar(st, synth(t0 + 2 * day_ns, 1.6, 500.0), CFG)
    assert t is not None and note == "entry"
