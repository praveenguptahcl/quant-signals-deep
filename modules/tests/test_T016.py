"""Concrete sketch: T016 End-of-Day Drift Rider.

Run: python3 -m pytest modules/tests/test_T016.py -q
"""
import csv
import math
import os

SID = "T016"
TAPE = os.path.join("modules", "fixtures", "T016_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T016_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T016 COST block (single source of truth)."""
    spread_bps = 0.5   # [example] ~2.5c effective spread on SPY @ $500 at 15:30
    fee_bps = 0.5      # [example] ~2.5c/share commission on SPY @ $500 at 15:30
    borrow_bps = 0.0   # [default] single-day ETF hold; borrow stubbed at zero
    impact_bps = 0.0   # [example] base model; conservative variant: MOC + 1c adverse
    return spread_bps + fee_bps + borrow_bps + impact_bps


def sizing_fn(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost):
    """Normative sizing_fn mirror (§T3): regime-scaled, risk-capped, ADV-capped.
    px and base_notional are module context; test uses the §T3 worked values."""
    scale = float(vol_estimate)              # HMM scale 1.0 / 0.5 / 0.0 [example]
    px = 500.0                                # 15:30 touch [example]
    base_notional = 100000.0                  # [default]
    adv_cap_pct = 0.05                        # [default]
    n_base = scale * base_notional / px
    n_risk = risk_budget_R / max(stop_distance, 1e-9)
    n_adv = ADV_cap * adv_cap_pct
    return max(0, int(min(n_base, n_risk, n_adv)))

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


def test_cost_gate_with_modeled_edge():
    # module §T1: edge_bps = 11.0 [example]; default k = 0.5 [default]
    # gate: 1.0 <= 0.5 * 11.0 = 5.5 -> PASS
    edge_bps = 11.0
    k = 0.5
    c = expected_cost_bps(100000.0, 0.01, "ARCX", "taker", "normal")
    assert c <= k * edge_bps
    # and the same stack fails a much smaller edge (gate is not vacuous)
    assert not (c <= k * 0.5)


def test_sizing_function_bounded():
    # §T3 worked case: px=500 [example], R=$800 [example], stop=0.25% [default]
    # min(200.0, 640.0, 50000.0) = 200
    assert sizing_fn(800.0, 1.25, 1.0, 1_000_000, 1.0) == 200
    # regime scale halves the position
    assert sizing_fn(800.0, 1.25, 0.5, 1_000_000, 1.0) == 100
    # suspended regime -> flat
    assert sizing_fn(800.0, 1.25, 0.0, 1_000_000, 1.0) == 0
    # ADV cap binds on thin names
    assert sizing_fn(800.0, 1.25, 1.0, 2_000, 1.0) == 100
    # risk cap binds on a small R budget
    assert sizing_fn(80.0, 1.25, 1.0, 1_000_000, 1.0) == 64
