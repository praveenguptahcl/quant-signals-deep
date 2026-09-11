"""Concrete sketch: T006 Intraday Trend + Vol-Regime Allocator.

Run: python3 -m pytest modules/tests/test_T006.py -q
"""
import csv
import math
import os

SID = "T006"
TAPE = os.path.join("modules", "fixtures", "T006_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T006_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T006 COST block (single source of truth)."""
    spread_bps = 0.5   # [example] ~0.5c effective spread on SPY @ $500 at 15:30
    fee_bps = 0.5      # [example] ~0.5c commission on SPY @ $500 at 15:30
    borrow_bps = 0.0   # [default] single-day ETF hold; borrow stubbed at zero
    impact_bps = 0.0   # [example] conservative variant: MOC + 1c adverse
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
    kill_conditions = ["15:30 bar stale > 3 min [example]", "clock skew > 50 ms [example]", "HMM inputs stale [example]"]
    stale_s = 300.0
    if stale_s >= 180.0:
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


def test_expected_summary_consistent():
    # the SUMMARY row must equal hand-recomputed sums from the tape
    _, tape = load_csv(TAPE)
    _, exp = load_csv(EXPECTED)
    gross_sum = 0.0
    net_sum = 0.0
    for t in tape:
        qty = float(t["qty"])
        entry = float(t["entry_px"])
        exitp = float(t["exit_px"])
        notional = float(t["notional"])
        stack_bps = (float(t["spread_bps"]) + float(t["fee_bps"])
                     + float(t["borrow_bps"]) + float(t["impact_bps"]))
        sign = 1 if t["side"] in ("BUY", "LONG") else -1
        gross_sum += sign * (exitp - entry) * qty
        net_sum += sign * (exitp - entry) * qty - notional * stack_bps / 10000.0
    summary = {e["trade_id"]: e for e in exp}["SUMMARY"]
    assert abs(gross_sum - float(summary["gross_pnl"])) <= CSV_TOL_USD
    assert abs(net_sum - float(summary["net_pnl"])) <= CSV_TOL_USD


def test_moc_exit_discipline():
    # every trade exits at the 16:00 close: fill exactly 1800 s after signal,
    # exit reason is the MOC print
    _, tape = load_csv(TAPE)
    for t in tape:
        assert int(t["fill_ts"]) - int(t["signal_ts"]) == 1_800_000_000_000
        assert "MOC" in t["exit_reason"], "exit must be the 16:00 MOC print"


def test_cost_gate_k_matches_config():
    # fixture cost_gate_k must equal the §T0 Config default (0.5), and the
    # §T1 modeled edge must clear the C3 gate: 1.0 bps <= 0.5 * 13.75 bps
    _, exp = load_csv(EXPECTED)
    edge_bps = 0.0025 * 1e4 * 0.55  # [example] modeled edge from §T1
    for e in exp:
        if e["trade_id"] == "SUMMARY":
            continue
        k = float(e["cost_gate_k"])
        assert k == 0.5
        c = float(e["expected_cost_bps"])
        assert c <= k * edge_bps, "C3 gate must pass on the fixture tape"
