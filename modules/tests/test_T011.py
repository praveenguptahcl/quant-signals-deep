"""Concrete sketch: T011 Short-Term Reversal + Bounce Timing.

Run: python3 -m pytest modules/tests/test_T011.py -q
"""
import csv
import math
import os

SID = "T011"
TAPE = os.path.join("modules", "fixtures", "T011_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T011_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T011 COST block (single source of truth)."""
    spread_bps = 8.0    # [example] $0.02 spread crossed/aggressive leg x 2 @ $50
    fee_bps = 2.0       # [example] $0.005/share each way @ $50 = 1 bps/leg
    borrow_bps = 0.0    # [default] long-bounce reference; shorts add C7
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


def test_intent_schema():
    # C19: the strategy emits OrderTicket intents only; every tape row must
    # carry the intent-schema fields, and causality must hold through the
    # intent: signal < intent <= fill
    _, tape = load_csv(TAPE)
    for t in tape:
        assert t["parent_signal"].startswith("S036@"), "parent_signal provenance"
        assert t["tif"] == "DAY", "time-in-force present"
        signal_event = int(t["signal_ts"])
        intent_event = int(t["intent_ts"])
        fill_event = int(t["fill_ts"])
        assert fill_event >= intent_event > signal_event, \
            "signal < intent <= fill (intentions only, t->t+1)"


def test_cost_gate_predicate():
    # the normative C12 predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5
    c = expected_cost_bps(100000.0, 0.1, "XNAS", "taker", "normal")
    if c <= 0:
        # zero/negative cost (overlay, maker rebate): the gate passes any positive edge
        assert c <= k * 0.05, "non-positive cost must clear the gate"
    else:
        assert c <= k * 50.0, "cost gate must pass when edge >> cost"
        assert not (c <= k * 0.05), "cost gate must block when edge << cost"


class KillSwitch:
    """Minimal ARMED -> TRIPPED -> RECOVERY -> ARMED machine (C11)."""

    def __init__(self, trip_conditions):
        assert len(trip_conditions) >= 3, "need >=3 kill conditions"
        self.state = "ARMED"
        self.trip_conditions = trip_conditions

    def trip(self, condition):
        assert self.state == "ARMED", "can only trip from ARMED"
        assert condition in self.trip_conditions
        self.state = "TRIPPED"  # stop emits, flatten per exit rule, page
        return self.state

    def rearm(self, checklist):
        # the six-item §T0.7 re-arm checklist, in order
        assert self.state == "TRIPPED", "can only re-arm from TRIPPED"
        assert len(checklist) == 6 and all(checklist), "checklist incomplete"
        self.state = "RECOVERY"
        self.state = "ARMED"
        return self.state


def test_kill_switch_cycle():
    ks = KillSwitch([
        "3 consecutive adverse bounces [example]",
        "feed heartbeat missed > 2 s [example]",
        "clock skew > 50 ms [example]",
        "4 concurrent reversals [example]",
    ])
    assert ks.state == "ARMED"
    assert ks.trip("3 consecutive adverse bounces [example]") == "TRIPPED"
    checklist = [
        True,  # 1. root cause identified and logged
        True,  # 2. post-exit cooldown expired
        True,  # 3. feed heartbeat healthy 5 min
        True,  # 4. clock skew within 50 ms
        True,  # 5. manual reviewer sign-off logged
        True,  # 6. all managed positions flat
    ]
    assert ks.rearm(checklist) == "ARMED"


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
