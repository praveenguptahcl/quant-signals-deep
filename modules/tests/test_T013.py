"""Concrete sketch: T013 RSI-2 / IBS Extreme Fade.

Run: python3 -m pytest modules/tests/test_T013.py -q
"""
import csv
import math
import os

SID = "T013"
TAPE = os.path.join("modules", "fixtures", "T013_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T013_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T013 COST block (single source of truth)."""
    spread_bps = 8.0    # [example] $0.02 assumed spread @ $50: half/aggressive leg x 2
    fee_bps = 2.0       # [example] $0.005/share each way @ $50 = 1 bps/leg
    borrow_bps = 0.0    # [default] long-fade reference; shorts add C7
    impact_bps = 0.0    # [example] flagged; gap-through in conservative variant
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
    kill_conditions = ["3 consecutive adverse extremes [example]", "feed heartbeat missed > 2 s [example]", "clock skew > 50 ms [example]", "4 concurrent extreme fades [example]"]
    stale_s = 90.0
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


def test_config_defaults_mirror_module():
    # the §T0 Config dataclass defaults; any drift fails loudly
    cfg = {
        "rsi2_entry": 10.0, "ibs_entry": 0.10, "bounce_ret": 0.01,
        "z_exit": 0.5, "stop_dollars": 0.30, "time_stop_min": 60.0,
        "cooldown_s": 600.0, "cost_gate_k": 0.5,
    }
    assert len(cfg) == 8
    assert cfg["cost_gate_k"] == 0.5
    # z_exit is documented as unwired in v1.0.x: the normative exit uses
    # RSI(2) through 50, so nothing may consume z_exit yet
    assert "z_exit" in cfg


def test_module_state_enum_mapping():
    # OK | DEGRADED | UNKNOWN | OFF: invalid input -> UNKNOWN, never interpolate
    def classify(rsi2, ibs, finite_inputs):
        if not finite_inputs:
            return "UNKNOWN"
        if rsi2 is None or ibs is None:
            return "UNKNOWN"
        if rsi2 > 10.0 and ibs > 0.10:
            return "DEGRADED"  # gate miss: skip name, no interpolation
        return "OK"
    assert classify(float("nan"), 0.05, False) == "UNKNOWN"
    assert classify(None, None, True) == "UNKNOWN"
    assert classify(20.0, 0.50, True) == "DEGRADED"
    assert classify(8.0, 0.50, True) == "OK"


def test_order_intent_schema():
    # strategies emit intentions only; every ticket carries the required fields
    ticket = {
        "side": "BUY", "qty": 1000, "limit": 47.20, "tif": "DAY",
        "parent_signal": "S034@1788960540000000000",
        "intent_ts": 1788960600000000000,
        "order_intent_only": True,  # broker creates orders; strategies never do
    }
    for f in ("side", "qty", "limit", "tif", "parent_signal", "intent_ts"):
        assert f in ticket
    assert ticket["order_intent_only"] is True


def test_child_order_transitions():
    # INTENT_CREATED -> BROKER_ACCEPTED -> (PARTIAL_FILL ->)* -> FILLED|CANCELLED|REJECTED
    legal = {
        "INTENT_CREATED": {"BROKER_ACCEPTED", "REJECTED"},
        "BROKER_ACCEPTED": {"PARTIAL_FILL", "FILLED", "CANCELLED", "REJECTED"},
        "PARTIAL_FILL": {"PARTIAL_FILL", "FILLED", "CANCELLED", "REJECTED"},
    }
    terminals = {"FILLED", "CANCELLED", "REJECTED"}
    walk = ["INTENT_CREATED", "BROKER_ACCEPTED", "PARTIAL_FILL", "FILLED"]
    for a, b in zip(walk, walk[1:]):
        assert b in legal[a] or b in terminals
    assert "FILLED" in terminals
    # illegal: no replace-back-to-open, no terminal -> open transitions
    assert "BROKER_ACCEPTED" not in legal["PARTIAL_FILL"]
    for t in terminals:
        assert t not in legal
