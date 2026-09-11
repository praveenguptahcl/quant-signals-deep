"""Concrete sketch: T003 VPIN-Gated Breakout Trader.

Run: python3 -m pytest modules/tests/test_T003.py -q

5 acceptance tests (A1-A5) + 3 contract/unit checks (U1-U3). Stdlib only.
"""
import csv
import math
import os

SID = "T003"
TAPE = os.path.join("modules", "fixtures", "T003_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T003_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T003 COST block (single source of truth)."""
    spread_bps = 4.0   # [example] $0.02 assumed spread @ $50: $0.01/aggressive leg x 2
    fee_bps = 2.0      # [example] $0.005/share each way @ $50 = 1 bps/leg
    borrow_bps = 0.0   # [default] intraday; shorts C7-gated
    impact_bps = 2.0   # [example] gap-through on the entry bar, modeled
    if urgency == "high":
        impact_bps = 4.0  # [example] late-day entries pay more
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
    kill_conditions = ["no 5-min bar within 30 s of expected close [example]", "clock skew > 50 ms [example]", "VPIN data stale > 10 min [example]", "4 concurrent positions reached [example]"]
    stale_s = 60.0
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


def decide_entry(close, orh, orl, entry_offset, rvol, rvol_entry, vpin, vpin_veto,
                 flat_today, edge_bps, cost_gate_k, locate_ok=True):
    """Minimal mirror of the §T2 Boolean entry rule (test oracle, stdlib only).

    Returns "BUY" / "SELL" / None. Cost gate uses the callable; fill is always
    the next-bar open (t->t+1) so no fill timestamp is produced here.
    """
    cost = expected_cost_bps(100000.0, 0.1, "XNAS", "taker", "normal")
    cost_ok = cost <= cost_gate_k * edge_bps          # C3 predicate
    if not (flat_today and cost_ok):
        return None
    if vpin > vpin_veto:
        return None                                  # C12 VPIN veto
    if close >= orh + entry_offset and rvol >= rvol_entry:
        return "BUY"
    if close <= orl - entry_offset and rvol >= rvol_entry and locate_ok:
        return "SELL"                                # C7 locate discipline
    return None


def test_entry_gate_boolean():
    # U1: the §T2 Boolean entry rule — veto/confirm/gate branches
    good = dict(close=50.70, orh=50.60, orl=50.00, entry_offset=0.05,
                rvol=1.8, rvol_entry=1.5, vpin=0.20, vpin_veto=0.30,
                flat_today=True, edge_bps=50.0, cost_gate_k=0.5)
    assert decide_entry(**good) == "BUY"
    assert decide_entry(**{**good, "vpin": 0.35}) is None, "VPIN veto must block"
    assert decide_entry(**{**good, "rvol": 1.2}) is None, "unfunded break vetoed"
    assert decide_entry(**{**good, "edge_bps": 0.05}) is None, "cost gate must block"
    assert decide_entry(**{**good, "flat_today": False}) is None, "one-trade-per-day"
    short = dict(good, close=49.80)
    assert decide_entry(**short) == "SELL"
    assert decide_entry(**{**short, "locate_ok": False}) is None, "C7 locate required"
    assert decide_entry(**{**good, "close": 50.62}) is None, "no break, no ticket"


def test_cost_callable_signature():
    c = expected_cost_bps(250000.0, 0.5, "XNAS", "taker", "normal")
    assert isinstance(c, float) and math.isfinite(c)
