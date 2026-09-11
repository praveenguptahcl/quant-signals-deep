"""Acceptance tests: T015 First-Half-Hour to Close Continuation.

Covers: fixture arithmetic (tape cost stack == cost callable == expected CSV,
hand-recomputed P&L, SUMMARY exact-sum), t->t+1 causality (no signal-bar
fills), the normative C3 cost-gate predicate, the kill-switch state machine
cycle, invalid-input -> UNKNOWN, the cost-callable signature, the S079 regime
scale gate, the canonical §T2 sizing function, and the 15:00/16:00 ET
wall-clock of the fixture timestamps.

Run: python3 -m pytest modules/tests/test_T015.py -q
Stdlib only (csv, math, os).
"""
import csv
import math
import os

SID = "T015"
TAPE = os.path.join("modules", "fixtures", "T015_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T015_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp

# --- module under test: mirrors of the §T2 / §T5 normative blocks ---

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T015 COST block (single source of truth, §T2)."""
    spread_bps = 0.5   # [example] ~0.5c effective spread on SPY @ $500 at 15:00
    fee_bps = 0.5      # [example] ~0.5c commission on SPY @ $500 at 15:00
    borrow_bps = 0.0   # [default] single-day ETF hold; borrow stubbed at zero
    impact_bps = 0.0   # [example] conservative variant: MOC + 1c adverse
    return spread_bps + fee_bps + borrow_bps + impact_bps


def regime_scale(p_vol, p_vol_half=0.60, p_vol_susp=0.80) -> float:
    """S079 gate (§T2): 1.0 / 0.5 / 0.0 scale at P(vol) thresholds [example]."""
    if p_vol < p_vol_half:
        return 1.0
    if p_vol < p_vol_susp:
        return 0.5
    return 0.0


def shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost,
           base_notional=100000.0, ref_price=500.0) -> int:
    """Canonical §T2 sizing: base_notional x regime scale, 5% ADV cap."""
    scale = vol_estimate  # caller passes the S079 HMM scale [default]
    n = scale * base_notional / ref_price
    n = min(n, ADV_cap * 0.05)  # 5% ADV participation cap [default]
    return int(n)


def kill_step(state, tripped: bool, checklist_ok: bool) -> str:
    """Kill-switch FSM: ARMED -> TRIPPED -> RECOVERY -> ARMED (§T7)."""
    if state == "ARMED" and tripped:
        return "TRIPPED"
    if state == "TRIPPED" and checklist_ok:
        return "RECOVERY"
    if state == "RECOVERY":
        return "ARMED"
    return state


def emit_state(bid_px, ask_px):
    """Invalid input -> UNKNOWN, never interpolated (F1/F2, §T0)."""
    if bid_px <= 0 or ask_px <= bid_px:
        return "UNKNOWN"
    return "OK"


def load_csv(path):
    with open(path) as f:
        lines = f.readlines()
    assert lines[0].strip().startswith("# TYPE:"), "missing TYPE header"
    return lines[0].strip(), list(csv.DictReader(lines[1:]))


def test_type_header():
    type_line, _ = load_csv(TAPE)
    assert "validation-run" in type_line
    assert "synthetic" in type_line, "fixture must be labeled synthetic vs real"
    type_line2, _ = load_csv(EXPECTED)
    assert "validation-run" in type_line2
    assert "synthetic" in type_line2


def test_fixture_arithmetic():
    # the tape's stored cost stack, the module's cost callable, and the
    # expected CSV must all agree; P&L arithmetic is recomputed by hand
    _, tape = load_csv(TAPE)
    _, exp = load_csv(EXPECTED)
    assert len(tape) >= 5, "need >=5 hand-checked rows"
    exp_by_id = {e["trade_id"]: e for e in exp if e["trade_id"] != "SUMMARY"}
    exact_nets = []
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
        exact_nets.append(net)
        assert abs(gross - float(e["gross_pnl"])) <= CSV_TOL_USD
        assert abs(net - float(e["net_pnl"])) <= CSV_TOL_USD
    # SUMMARY row: rounded sum of the exact (unrounded) nets = 564.94
    summary = next(e for e in exp if e["trade_id"] == "SUMMARY")
    assert abs(sum(exact_nets) - float(summary["net_pnl"])) <= 0.005, (
        "SUMMARY net must equal round(sum of exact nets); "
        "rounding convention: round the exact total, not the sum of rounded rows"
    )


def test_no_signal_bar_fills():
    _, tape = load_csv(TAPE)
    for t in tape:
        fill_event = int(t["fill_ts"])
        signal_event = int(t["signal_ts"])
        assert fill_event > signal_event, "fill_event > signal_event (t->t+1 causality)"


def test_signal_wallclock():
    # fixture signal bars are the 15:00 ET snapshot; fills the 16:00 print.
    # 15:00 EDT = 19:00 UTC = 68400 s; 16:00 EDT = 20:00 UTC = 72000 s.
    _, tape = load_csv(TAPE)
    for t in tape:
        assert (int(t["signal_ts"]) // 10**9) % 86400 == 68400, "signal @ 15:00 ET"
        assert (int(t["fill_ts"]) // 10**9) % 86400 == 72000, "fill @ 16:00 ET"


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
    # module's own calibration: cost 1.0 bps [example] vs edge 11 bps [example]
    edge_bps = 0.0020 * 1e4 * 0.55  # 11.0 [example]
    assert expected_cost_bps(100000.0, 0.1, "ARCX", "taker", "normal") <= k * edge_bps


def test_kill_switch_trips_and_rearms():
    # ARMED -> TRIPPED -> RECOVERY -> ARMED, driven by the FSM (§T7)
    kill_conditions = ["15:00 bar stale > 3 min [example]",
                       "clock skew > 50 ms [example]",
                       "HMM inputs stale [example]"]
    assert isinstance(kill_conditions, list) and len(kill_conditions) >= 3
    state = "ARMED"
    state = kill_step(state, tripped=True, checklist_ok=False)
    assert state == "TRIPPED", "trip condition must move ARMED -> TRIPPED"
    state = kill_step(state, tripped=False, checklist_ok=False)
    assert state == "TRIPPED", "no re-arm without the checklist"
    state = kill_step(state, tripped=False, checklist_ok=True)
    assert state == "RECOVERY"
    state = kill_step(state, tripped=False, checklist_ok=True)
    assert state == "ARMED", "checklist complete -> RECOVERY -> ARMED"


def test_invalid_input_emits_unknown():
    # crossed/locked/empty input -> UNKNOWN, never interpolated
    assert emit_state(50.00, 50.00) == "UNKNOWN"
    assert emit_state(50.01, 50.00) == "UNKNOWN"
    assert emit_state(50.00, 50.01) == "OK"


def test_cost_callable_signature():
    c = expected_cost_bps(250000.0, 0.5, "XNAS", "taker", "normal")
    assert isinstance(c, float) and math.isfinite(c)


def test_regime_scale_gate():
    # S079 gate (§T2): 1.0 / 0.5 / 0.0 at P(vol) 0.60 / 0.80 [example]
    assert regime_scale(0.59) == 1.0
    assert regime_scale(0.60) == 0.5
    assert regime_scale(0.79) == 0.5
    assert regime_scale(0.80) == 0.0
    assert regime_scale(0.95) == 0.0


def test_sizing_fn():
    # canonical §T2 sizing: 200 shares at full scale, halved at 0.5, ADV-capped
    assert shares(800.0, 0.0, 1.0, 1e9, 1.0) == 200
    assert shares(800.0, 0.0, 0.5, 1e9, 1.0) == 100
    assert shares(800.0, 0.0, 0.0, 1e9, 1.0) == 0
    assert shares(800.0, 0.0, 1.0, 2000.0, 1.0) == 100  # 5% of ADV binds
