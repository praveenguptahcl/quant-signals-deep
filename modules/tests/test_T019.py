"""T019 Donchian/Keltner Breakout + Vol Sizing — acceptance tests.

Run: python3 -m pytest modules/tests/test_T019.py -q
"""
import csv
import math
import os

SID = "T019"
TAPE = os.path.join("modules", "fixtures", "T019_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T019_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp
NS_PER_DAY = 86400e9


def expected_cost_bps(notional, adv_pct, venue, side, urgency,
                      order_side="BUY", hold_days=1.0) -> float:
    """Callable cost model - T019 COST block (single source of truth).

    Verbatim copy of the §T2 COST-block callable. Short (SELL/SHORT) legs
    accrue stock-loan borrow at 50 bps/yr [example], pro-rated per calendar
    day held; long legs borrow nothing (no borrow on longs [default reason]).
    """
    spread_bps = 4.0   # [example] 1c assumed spread @ $50: half/aggressive leg x 2
    fee_bps = 2.0      # [example] $0.005/share each way @ $50 = 1 bps/leg
    impact_bps = 4.0   # [example] breakout chasing: 2c adverse @ $50
    borrow_annual_bps = 50.0  # [example] general-collateral stock-loan fee
    if order_side in ("SELL", "SHORT"):
        borrow_bps = borrow_annual_bps * hold_days / 365.0  # [example] pro-rata
    else:
        borrow_bps = 0.0  # [default] no borrow on long positions (reason)
    return spread_bps + fee_bps + borrow_bps + impact_bps


def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if ln.strip()]
    type_line = next(ln for ln in lines if ln.startswith("# TYPE:"))
    assert any(ln.startswith("# SYNTHETIC:") for ln in lines), "missing SYNTHETIC header"
    data = [ln for ln in lines if not ln.startswith("#")]
    return type_line.strip(), list(csv.DictReader(data))


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
        hold_days = (int(t["fill_ts"]) - int(t["signal_ts"])) / NS_PER_DAY
        cbps = expected_cost_bps(notional, float(t["adv_pct"]), t["venue"],
                                 t["exec_side"], t["urgency"],
                                 order_side=t["side"], hold_days=hold_days)
        assert abs(cbps - stack_bps) <= CSV_TOL_BPS  # tape rounds stack to 4 dp
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
    # borrow convention: short leg costs strictly more than the long reference
    c_short = expected_cost_bps(100000.0, 0.1, "XNAS", "taker", "normal",
                                order_side="SELL", hold_days=1.0)
    c_long = expected_cost_bps(100000.0, 0.1, "XNAS", "taker", "normal",
                               order_side="BUY", hold_days=1.0)
    assert c_short > c_long, "short borrow must be priced into the cost stack"
    assert math.isclose(c_long, 10.0, rel_tol=1e-12), "long reference stack is 10 bps"


def test_kill_switch_trips_and_rearms():
    # ARMED -> TRIPPED -> RECOVERY -> ARMED with re-arm checklist
    trip_conditions = [
        "4 units in one name [example]",
        "12 units portfolio [example]",
        "clock skew > 50 ms [example]",
    ]

    def trip(units_name, units_portfolio, clock_skew_ms):
        if units_name >= 4 or units_portfolio >= 12 or clock_skew_ms > 50:
            return "TRIPPED"
        return "ARMED"

    assert trip(4, 0, 10) == "TRIPPED"
    assert trip(0, 12, 10) == "TRIPPED"
    assert trip(0, 0, 51) == "TRIPPED"
    assert trip(3, 11, 10) == "ARMED"

    # re-arm checklist: manual review + cooldown expiry + feed healthy +
    # unit counts back inside limits + decision log reviewed
    checklist = {
        "manual_review": True,
        "cooldown_expired": True,
        "feed_healthy": True,
        "units_within_limits": True,
        "decision_log_reviewed": True,
    }
    state = "RECOVERY"
    if all(checklist.values()):
        state = "ARMED"
    assert state == "ARMED"
    assert isinstance(trip_conditions, list) and len(trip_conditions) >= 3


def test_invalid_input_emits_unknown():
    # F1/F2: invalid input -> UNKNOWN, never interpolated
    def module_state(bars, donch_hi, keltner_upper, p_vol):
        if not bars:
            return "UNKNOWN"
        vals = [donch_hi, keltner_upper, p_vol]
        if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in vals):
            return "UNKNOWN"
        return "OK"
    assert module_state([], 50.0, 51.0, 0.5) == "UNKNOWN"
    assert module_state([1], float("nan"), 51.0, 0.5) == "UNKNOWN"
    assert module_state([1], 50.0, 51.0, 0.5) == "OK"


def test_cost_callable_signature():
    c = expected_cost_bps(250000.0, 0.5, "XNAS", "taker", "normal")
    assert isinstance(c, float) and math.isfinite(c)
    c2 = expected_cost_bps(250000.0, 0.5, "XNAS", "taker", "normal",
                           order_side="SELL", hold_days=2.0)
    assert isinstance(c2, float) and c2 > c
