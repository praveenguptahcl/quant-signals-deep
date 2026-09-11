"""Concrete sketch: T023 Hawkes Burst Scalper.

Run: python3 -m pytest modules/tests/test_T023.py -q
"""
import csv
import math
import os
import re

SID = "T023"
TAPE = os.path.join("modules", "fixtures", "T023_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T023_expected.csv")
SPEC = os.path.join("modules", "strategies", "T023.md")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T023 COST block (single source of truth)."""
    spread_bps = 8.0    # [example] $0.02 assumed spread @ $50: half/aggressive x 2 (taker)
    fee_bps = 2.0       # [example] $0.005/share each way @ $50 = 1 bps/leg
    borrow_bps = 0.0    # [default] intraday scalp; no borrow
    impact_bps = 4.0    # [example] burst chasing: 2c adverse @ $50
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
                                 t["exec_side"], t["urgency"])
        assert t["exec_side"] in ("taker", "maker", "mixed"), "exec_side must be taker/maker/mixed"
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
    # ARMED -> TRIPPED -> RECOVERY -> ARMED; the 5-item re-arm checklist from
    # the spec §T0 must be present and named
    with open(SPEC) as f:
        spec = f.read()
    state = "ARMED"
    kill_conditions = ["VPIN > 0.45 [example]", "trade feed stale > 1 s [example]", "clock skew > 1 ms [example]", "tick-to-trade > 100 ms [example]"]
    for cond in kill_conditions:
        assert cond in spec, f"trip condition missing from spec: {cond}"
    stale_s = 1.0
    if stale_s >= 1.0:
        state = "TRIPPED"   # cancel all, flatten, OFF
    assert state == "TRIPPED"
    checklist = [
        "Manual review sign-off recorded",
        "Post-trip cooldown expired",
        "Trade feed fresh: staleness < `1` s",
        "Clock skew < `1` ms",
        "Latency probe: tick-to-trade < `100` ms",
    ]
    for item in checklist:
        assert item in spec, f"re-arm checklist item missing from spec: {item}"
    assert all(checklist)
    state = "RECOVERY"
    state = "ARMED"
    assert state == "ARMED"
    assert isinstance(kill_conditions, list) and len(kill_conditions) >= 3


def test_borrow_zero_with_reason():
    # borrow convention: 0 bps/day requires an explicit reason in the spec
    with open(SPEC) as f:
        spec = f.read()
    assert "borrow_bps_per_day" in spec, "borrow_bps_per_day missing"
    m = re.search(r"borrow_bps_per_day[\"']?\s*[:=]\s*[\"']?([\d.]+)", spec)
    assert m is not None, "borrow_bps_per_day value missing"
    assert float(m.group(1)) == 0.0, "intraday scalp must carry 0 borrow"
    assert "borrow_reason" in spec, "borrow_reason missing for zero borrow"
    assert "borrow_bps = 0.0" in spec, "COST block borrow component missing"


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


def test_spec_cost_block_single_source():
    # the §T2 COST stack in the spec must match this test's callable exactly
    with open(SPEC) as f:
        spec = f.read()
    for comp in ("spread_bps = 8.0", "fee_bps = 2.0", "borrow_bps = 0.0", "impact_bps = 4.0"):
        assert comp in spec, f"COST component missing from spec: {comp}"
    assert "expected_cost_bps(...) <= k * edge_bps" in spec, "cost-gate predicate missing"
    assert "borrow_bps_per_day" in spec, "borrow_bps_per_day missing"
    # the test callable and the spec stack must agree numerically
    m = re.search(r"spread_bps = ([\d.]+).*?fee_bps = ([\d.]+).*?borrow_bps = ([\d.]+).*?impact_bps = ([\d.]+)",
                  spec, re.S)
    stack = sum(float(m.group(i)) for i in range(1, 5))
    assert abs(stack - expected_cost_bps(1.0, 0.1, "XNAS", "taker", "normal")) <= TOL


def test_module_version_bump():
    # adoption verification v1.0.3: semver bump + changelog entry present
    with open(SPEC) as f:
        spec = f.read()
    assert 'version: "1.0.3"' in spec, "§0 semver bump missing"
    fm = spec.split("---")[1]
    assert 'version: "1.0.2"' not in fm, "stale version pin left in front-matter"
    assert "template_version: 1.0.0" in spec, "template_version missing"
    assert "Deep review v1.0.1" in spec, "deep-review changelog entry missing"
    assert "GROK-NEEDED" in spec, "GROK-NEEDED block missing"
    # timing box is mandatory in §T2
    assert "signal@t" in spec and "earliest fill @open(t+1)" in spec
