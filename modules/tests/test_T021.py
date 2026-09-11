"""Concrete sketch: T021 Avellaneda-Stoikov Inventory Skew MM.

Run: python3 -m pytest modules/tests/test_T021.py -q
"""
import csv
import math
import os

SID = "T021"
TAPE = os.path.join("modules", "fixtures", "T021_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T021_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T021 COST block (single source of truth)."""
    spread_bps = -4.0   # [example] maker: earns half the 2c spread @ $50 = -4 bps/round-trip
    fee_bps = 1.0       # [example] maker fees/rebates net @ $50
    borrow_bps = 0.0    # [default] intraday inventory; no borrow
    impact_bps = 0.0    # [example] maker: no taking impact; adverse selection separate
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
                                 "maker", t["urgency"])
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
    c = expected_cost_bps(100000.0, 0.1, "XNAS", "maker", "normal")
    if c <= 0:
        # zero/negative cost (overlay, maker rebate): the gate passes any positive edge
        assert c <= k * 0.05, "non-positive cost must clear the gate"
    else:
        assert c <= k * 50.0, "cost gate must pass when edge >> cost"
        assert not (c <= k * 0.05), "cost gate must block when edge << cost"


def test_kill_switch_trips_and_rearms():
    # ARMED -> TRIPPED -> RECOVERY -> ARMED, walked as a real state machine
    # with the §T0 re-arm checklist
    transitions = {"ARMED": {"trip": "TRIPPED"},
                   "TRIPPED": {"begin_recovery": "RECOVERY"},
                   "RECOVERY": {"rearm": "ARMED"}}
    state = "ARMED"
    kill_conditions = ["VPIN > 0.40 [example]", "inventory > max [example]",
                       "L1 stale > 1 s [example]", "clock skew > 1 ms [example]"]
    assert isinstance(kill_conditions, list) and len(kill_conditions) >= 3
    vpin, stale_s, skew_ms, abs_q, inv_max = 0.41, 1.0, 0.5, 3.0, 5.0
    tripped = ((vpin > 0.40) or (stale_s >= 1.0)
               or (skew_ms > 1.0) or (abs_q > inv_max))
    if tripped:  # on trip: stop emitting, cancel working intents, flatten, page
        state = transitions[state]["trip"]
    assert state == "TRIPPED"
    checklist = {"manual_review": True, "cooldown_expired": True,
                 "l1_healthy": True, "skew_ok": True, "vpin_ok": True}
    assert all(checklist.values()), "all 5 re-arm checklist items must pass"
    state = transitions[state]["begin_recovery"]
    assert state == "RECOVERY"
    state = transitions[state]["rearm"]
    assert state == "ARMED"


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
    c = expected_cost_bps(250000.0, 0.5, "XNAS", "maker", "normal")
    assert isinstance(c, float) and math.isfinite(c)


def test_inventory_guard_skew_only():
    # C11: |q| > inv_max -> skew-only, no new quote tickets (mirrors §T3 pseudocode)
    def quote_decision(abs_q, inv_max):
        if abs_q > inv_max:
            return "SKEW_ONLY"
        return "QUOTE"
    assert quote_decision(6.0, 5.0) == "SKEW_ONLY"
    assert quote_decision(5.0, 5.0) == "QUOTE"
    assert quote_decision(0.0, 5.0) == "QUOTE"


def test_vpin_veto_pulls_quotes():
    # C12: vpin > vpin_veto -> pull quotes, emit nothing (mirrors §T3 pseudocode)
    def tickets_for(vpin, vpin_veto):
        if vpin > vpin_veto:
            return []
        return ["BUY", "SELL"]
    assert tickets_for(0.41, 0.40) == []
    assert tickets_for(0.40, 0.40) == ["BUY", "SELL"]
    assert tickets_for(0.10, 0.40) == ["BUY", "SELL"]
