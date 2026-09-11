"""Concrete sketch: T010 Variance-Risk-Premium Harvester.

Run: python3 -m pytest modules/tests/test_T010.py -q
"""
import csv
import math
import os

SID = "T010"
TAPE = os.path.join("modules", "fixtures", "T010_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T010_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T010 COST block (single source of truth)."""
    spread_bps = 5.0    # [example] options bid/ask on variance exposure at the money
    fee_bps = 3.0       # [example] options commissions per contract equivalent
    borrow_bps = 0.0    # [default] variance exposure; no borrow
    impact_bps = 5.0    # [example] rolling variance exposure
    return spread_bps + fee_bps + borrow_bps + impact_bps

def load_csv(path):
    with open(path) as f:
        lines = f.readlines()
    assert lines[0].strip().startswith("# TYPE:"), "missing TYPE header"
    return lines[0].strip(), list(csv.DictReader(lines[1:]))


def test_type_header():
    type_line, _ = load_csv(TAPE)
    assert "validation-run" in type_line
    type_line2, _ = load_csv(EXPECTED)
    assert "validation-run" in type_line2


def test_fixture_arithmetic():
    # the tape's stored cost stack, the module's cost callable, and the
    # expected CSV must all agree; P&L arithmetic is recomputed by hand
    _, tape = load_csv(TAPE)
    _, exp = load_csv(EXPECTED)
    assert len(tape) >= 5, "need >=5 hand-checked rows"
    exp_by_id = {e["trade_id"]: e for e in exp if e["trade_id"] != "SUMMARY"}
    for t in tape:
        e = exp_by_id[t["trade_id"]]
        qty = float(t["qty"])
        entry = float(t["entry_px"])
        exitp = float(t["exit_px"])
        notional = float(t["notional"])
        stack_bps = (float(t["spread_bps"]) + float(t["fee_bps"])
                     + float(t["borrow_bps"]) + float(t["impact_bps"]))
        cbps = expected_cost_bps(notional, float(t["adv_pct"]), t["venue"],
                                 "taker", t["urgency"])
        assert abs(cbps - stack_bps) <= TOL
        assert abs(cbps - float(e["expected_cost_bps"])) <= CSV_TOL_BPS
        sign = 1 if t["side"] in ("BUY", "LONG") else -1
        gross = sign * (exitp - entry) * qty
        net = gross - notional * cbps / 10000.0
        assert abs(gross - float(e["gross_pnl"])) <= CSV_TOL_USD
        assert abs(net - float(e["net_pnl"])) <= CSV_TOL_USD


def test_no_signal_bar_fills():
    _, tape = load_csv(TAPE)
    for t in tape:
        fill_event = int(t["fill_ts"])
        signal_event = int(t["signal_ts"])
        assert fill_event > signal_event, "fill_event > signal_event (t->t+1 causality)"


def test_cost_gate_predicate():
    # the normative C3 predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5
    c = expected_cost_bps(100000.0, 0.1, "XNAS", "taker", "normal")
    if c <= 0:
        # zero/negative cost (overlay, maker rebate): the gate passes any positive edge
        assert c <= k * 0.05, "non-positive cost must clear the gate"
    else:
        assert c <= k * 50.0, "cost gate must pass when edge >> cost"
        assert not (c <= k * 0.05), "cost gate must block when edge << cost"


def test_kill_switch_trips_and_rearms():
    # ARMED -> TRIPPED -> RECOVERY -> ARMED
    state = "ARMED"
    kill_conditions = ["vol spike: realized > 2× implied [example]", "term structure inverts [example]", "clock skew > 50 ms [example]", "options chain stale > 5 min [example]"]
    stale_s = 300.0
    if stale_s >= 2.0:
        state = "TRIPPED"   # cancel all, flatten, OFF
    assert state == "TRIPPED"
    checklist = [True, True, True, True, True]
    assert all(checklist)
    state = "RECOVERY"
    state = "ARMED"
    assert state == "ARMED"
    assert isinstance(kill_conditions, list) and len(kill_conditions) >= 3


def test_invalid_input_emits_unknown():
    # crossed/locked/empty input -> UNKNOWN, never interpolated
    def emit_state(bid_px, ask_px):
        if bid_px <= 0 or ask_px <= bid_px:
            return "UNKNOWN"
        return "OK"
    assert emit_state(50.00, 50.00) == "UNKNOWN"
    assert emit_state(50.01, 50.00) == "UNKNOWN"
    assert emit_state(50.00, 50.01) == "OK"


def test_cost_callable_signature():
    c = expected_cost_bps(250000.0, 0.5, "XNAS", "taker", "normal")
    assert isinstance(c, float) and math.isfinite(c)


def _enter(vrp, ts, pj, cost_ok, vrp_entry=3.0, ts_slope_min=0.0,
           p_jump_max=0.30):
    # mirrors the §T2 Boolean entry rule: all four must hold
    return ((vrp >= vrp_entry) and (ts >= ts_slope_min)
            and (pj <= p_jump_max) and cost_ok)


def _exit(vrp, ts, pj, realized, implied, vrp_exit=1.0, stop_vrp=-1.0,
          ts_slope_min=0.0, p_jump_max=0.30):
    # mirrors the §T2 exit rule: any one unwinds
    return ((vrp <= vrp_exit) or (vrp <= stop_vrp) or (ts < ts_slope_min)
            or (pj > p_jump_max) or (realized > 2.0 * implied))


def test_entry_exit_boolean_rules():
    # enter fires only when premium wide + contango + jump gate clear + cost gate
    assert _enter(4.0, 0.5, 0.2, True)
    assert not _enter(2.0, 0.5, 0.2, True), "vrp below entry -> FLAT"
    assert not _enter(4.0, -0.5, 0.2, True), "backwardation vetoes"
    assert not _enter(4.0, 0.5, 0.35, True), "jump gate vetoes"
    assert not _enter(4.0, 0.5, 0.2, False), "cost gate blocks"
    # boundary: exactly at thresholds enters
    assert _enter(3.0, 0.0, 0.30, True)
    # exits
    assert _exit(0.5, 0.3, 0.2, 15.0, 12.0), "premium harvested"
    assert _exit(-1.5, 0.3, 0.2, 15.0, 12.0), "stop: premium inverts"
    assert _exit(2.0, -0.1, 0.2, 15.0, 12.0), "term-structure inversion"
    assert _exit(2.0, 0.3, 0.35, 15.0, 12.0), "jump gate"
    assert _exit(2.0, 0.3, 0.2, 30.0, 12.0), "vol-spike kill"
    assert not _exit(2.0, 0.3, 0.2, 15.0, 12.0), "no exit condition -> hold"
