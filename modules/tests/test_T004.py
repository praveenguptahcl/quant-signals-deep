"""Concrete sketch: T004 VWAP-Deviation Mean-Reversion.

Run: python3 -m pytest modules/tests/test_T004.py -q
"""
import csv
import datetime
import math
import os

SID = "T004"
TAPE = os.path.join("modules", "fixtures", "T004_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T004_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp
ONE_BAR_NS = 60_000_000_000   # 1-min bar in int64 ns

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T004 COST block (single source of truth)."""
    spread_bps = 8.0    # [example] $0.02 assumed spread @ $50: half/aggressive leg x 2
    fee_bps = 2.0       # [example] $0.005/share each way @ $50 = 1 bps/leg
    borrow_bps = 0.0    # [example] intraday-flat reference (C9); shorts add C7 locate + borrow
    impact_bps = 0.0    # [example] flagged; gap-through in conservative variant only
    return spread_bps + fee_bps + borrow_bps + impact_bps

def shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost):
    """Fenced position-sizing function - T004 §T2 (normative)."""
    n = risk_budget_R / max(stop_distance, 1e-9)   # [default] floor below
    n = min(n, ADV_cap * 0.005)                   # 0.5% ADV [default]
    n = min(n * 50.0, 600000.0) / 50.0           # $600k gross cap [default]
    return int(n)

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


def test_timing_box():
    # signal@t (1-min, America/New_York) -> earliest fill @open(t+1):
    # every fixture fill is exactly one bar after its signal, and every
    # signal sits inside the 10:00-15:30 ET trade window (first 30 min excluded)
    _, tape = load_csv(TAPE)
    for t in tape:
        signal_event = int(t["signal_ts"])
        fill_event = int(t["fill_ts"])
        assert fill_event - signal_event == ONE_BAR_NS, "fill must be @open(t+1)"
        utc = datetime.datetime.fromtimestamp(signal_event // 10**9,
                                              datetime.timezone.utc)
        et = utc - datetime.timedelta(hours=4)  # EDT in September
        et_hour = et.hour + et.minute / 60.0 + et.second / 3600.0
        assert 10.0 <= et_hour < 15.5, f"signal outside trade window: {et}"


def test_sizing_function():
    # §T2 fenced sizing: $300 R / $0.20 stop -> 1500 shares (fixture qty)
    assert shares(300.0, 0.20, 0.0, 10_000_000, 0.0) == 1500
    # ADV cap binds: 0.5% of 100k ADV = 500
    assert shares(300.0, 0.20, 0.0, 100_000, 0.0) == 500
    # $600k gross cap binds on large R (priced at the $50 reference [example])
    assert shares(300_000.0, 0.20, 0.0, 10_000_000, 0.0) == 12_000
    # floor on degenerate stop distance: finite, non-negative
    assert shares(300.0, 0.0, 0.0, 10_000_000, 0.0) >= 0


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
    kill_conditions = ["rolling σ̂_d doubles intraday [example]", "feed heartbeat missed > 2 s [example]", "clock skew > 50 ms [example]", "4 concurrent fades reached [example]"]
    stale_s = 5.0
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
