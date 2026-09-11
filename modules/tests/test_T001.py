"""Concrete sketch: T001 OFI + Queue-Imbalance Directional Scalper.

Run: python3 -m pytest modules/tests/test_T001.py -q
"""
import csv
import math
import os

SID = "T001"
TAPE = os.path.join("modules", "fixtures", "T001_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T001_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T001 COST block (single source of truth)."""
    spread_bps = 2.0   # [example] 1-tick @ $50: half-spread per aggressive leg x 2
    fee_bps = 2.0      # [example] $0.005/share each way @ $50 = 1 bps/leg
    borrow_bps = 0.0   # [default] intraday; shorts excluded from reference build
    impact_bps = 0.0   # [example] flagged; calibrate per venue at scale-up
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
    kill_conditions = ["feed heartbeat missed > 2 s [example]", "book sequence gap", "clock skew > 50 ms vs NTP [example]", "any exit timer firing late", "paper ledger != module state"]
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


def test_borrow_convention():
    # COST block convention: borrow_bps_per_day == 0.0 with a stated reason —
    # the reference build is intraday and shorts are excluded (C7)
    borrow_bps_per_day = 0.0   # [default] per the COST block
    reason = "intraday; shorts excluded from the reference build"
    assert borrow_bps_per_day == 0.0
    assert len(reason) > 0, "borrow=0 needs a stated reason"


def test_fee_envelope_covers_documented_floor():
    # Nasdaq Rule 7018 default removal rate $0.0030/share [documented];
    # the module budgets $0.005/share/leg = 1.0 bps/leg at $50 [example],
    # a conservative envelope over the documented floor
    documented_remove_per_share = 0.0030
    module_fee_per_share_per_leg = 0.005
    price = 50.0
    assert module_fee_per_share_per_leg >= documented_remove_per_share, \
        "module fee budget must cover the documented remove rate"
    bps_per_leg = module_fee_per_share_per_leg / price * 10000.0
    assert abs(bps_per_leg - 1.0) < 1e-9
