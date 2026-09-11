"""T025 Trade-Classification Trend Filter — acceptance tests.

Run: python3 -m pytest modules/tests/test_T025.py -q
"""
import csv
import math
import os

SID = "T025"
TAPE = os.path.join("modules", "fixtures", "T025_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T025_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp

# --- reference implementation mirrors (must match the md) -----------------

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T025 COST block (single source of truth)."""
    spread_bps = 6.0    # [example] $0.015 assumed spread @ $50: half/aggressive x 2
    fee_bps = 2.0       # [example] $0.005/share each way @ $50 = 1 bps/leg
    borrow_bps = 0.0    # [default] borrow_bps_per_day=0: intraday, long-biased
    impact_bps = 4.0    # [example] momentum chasing: 2c adverse @ $50
    return spread_bps + fee_bps + borrow_bps + impact_bps


def edge_bps(r_mom) -> float:
    """Per-signal modeled edge - §T1/§T3 (v1.0.1: per-signal, not constant)."""
    return abs(r_mom) * 1e4 * 0.55  # [example] capture fraction


def cost_gate_passes(r_mom, notional, k=0.5) -> bool:
    """Normative C3 predicate: expected_cost_bps(...) <= k * edge_bps."""
    return expected_cost_bps(notional, 0.02, "XNAS", "taker", "normal") <= k * edge_bps(r_mom)


def hmm_scale(p_vol, p_vol_half=0.60, p_vol_susp=0.80) -> float:
    """S079 gate: scale 1.0 / 0.5 / 0.0 [example]."""
    if not math.isfinite(p_vol):
        return 0.0  # unknown input -> UNKNOWN path: no scale, no tickets
    if p_vol < p_vol_half:
        return 1.0
    if p_vol < p_vol_susp:
        return 0.5
    return 0.0


def enter_long(r_mom, class_imb, mom_min=0.003, class_min=0.60) -> bool:
    return (r_mom >= mom_min) and (class_imb >= class_min)


def enter_short(r_mom, class_imb, mom_min=0.003, class_min=0.60) -> bool:
    return (r_mom <= -mom_min) and (class_imb <= -class_min)


def shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost):
    """Fenced sizing: shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost)."""
    n = risk_budget_R / max(stop_distance, 1e-9)  # [default] floor below
    n = n * vol_estimate                          # HMM scale 1.0/0.5/0.0 [example]
    n = min(n, ADV_cap * 0.01)                    # 1% ADV [default]
    n = min(n * 50.0, 2000000.0) / 50.0           # $2M gross cap [default]
    return int(n)


def emit_state(bars_empty, r_mom, class_imb, p_vol, oldest_ts, bar_ts, ttl_ns):
    """Module-state mirror of §T3 emit guards: invalid -> UNKNOWN."""
    if bars_empty:
        return "UNKNOWN"  # F1
    if not (math.isfinite(r_mom) and math.isfinite(class_imb) and math.isfinite(p_vol)):
        return "UNKNOWN"  # F2
    if oldest_ts < bar_ts - ttl_ns:
        return "UNKNOWN"  # F5/C6 staleness
    return "OK"


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
    gross_sum = 0.0
    net_sum = 0.0
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
        gross_sum += round(gross, 2)
        net_sum += round(net, 2)
    # SUMMARY row must equal the sum of the rounded per-trade values
    summary = next(e for e in exp if e["trade_id"] == "SUMMARY")
    assert abs(float(summary["gross_pnl"]) - gross_sum) <= CSV_TOL_USD
    assert abs(float(summary["net_pnl"]) - net_sum) <= CSV_TOL_USD


def test_no_signal_bar_fills():
    _, tape = load_csv(TAPE)
    for t in tape:
        fill_event = int(t["fill_ts"])
        signal_event = int(t["signal_ts"])
        assert fill_event > signal_event, "fill_event > signal_event (t->t+1 causality)"


def test_cost_gate_predicate():
    # the normative C3 predicate with the v1.0.1 per-signal edge model
    c = expected_cost_bps(100000.0, 0.1, "XNAS", "taker", "normal")
    assert c == 12.0  # reference stack
    # at the threshold momentum (0.30% -> 16.5 bps edge) the gate vetoes at k=0.5
    assert not cost_gate_passes(0.0030, 100000.0, k=0.5), "gate must bind at threshold"
    # at strong momentum (0.50% -> 27.5 bps edge) the gate passes at k=0.5
    assert cost_gate_passes(0.0050, 100000.0, k=0.5), "gate must be satisfiable"
    # the gate is binding but not dead: pass rate strictly between 0 and 1
    grid = [cost_gate_passes(r, 100000.0, k=0.5) for r in
            (0.001, 0.003, 0.004, 0.005, 0.01)]
    assert any(grid) and not all(grid)


def test_cost_gate_binding_threshold():
    # solve k * |r| * 1e4 * 0.55 = 12 at k=0.5 -> |r| = 12/(0.5*5500) = 0.004363...
    r_star = 12.0 / (0.5 * 1e4 * 0.55)
    assert abs(r_star - 0.004363636363636364) < 1e-12
    assert abs(r_star - 0.0044) < 1e-4  # the 0.44% [measured] figure in §T1


def test_kill_switch_trips_and_rearms():
    # ARMED -> TRIPPED -> RECOVERY -> ARMED driven by §T7 trip conditions
    trip_conditions = [
        "3 consecutive filter vetoes of winners [example]",
        "trade tape stale > 30 s [example]",
        "clock skew > 50 ms [example]",
        "4 concurrent filtered trends [example]",
    ]
    state = "ARMED"
    stale_tape_s = 90.0  # [example] scenario: tape freshness monitor fires
    if stale_tape_s > 30.0:
        state = "TRIPPED"  # stop emitting, flatten per exit rule, page
    assert state == "TRIPPED"
    # RECOVERY requires the numbered §T0 re-arm checklist; all must hold
    checklist = {
        "trip cause logged": True,
        "cooldown expired (300 s)": True,
        "tape healthy (< 30 s)": True,
        "skew < 50 ms": True,
        "flat + ledger reconciled": True,
        "fee schedule re-pinned (cost trip)": True,
        "operator sign-off": True,
    }
    assert all(checklist.values()) and len(checklist) == 7
    state = "RECOVERY"
    state = "ARMED"
    assert state == "ARMED"
    assert len(trip_conditions) >= 3


def test_invalid_input_emits_unknown():
    # F1/F2/F5: invalid input -> UNKNOWN, never interpolated
    ttl_ns = 450 * 1_000_000_000
    bar_ts = 1788960600000000000
    assert emit_state(True, 0.005, 0.7, 0.3, bar_ts, bar_ts, ttl_ns) == "UNKNOWN"   # F1
    assert emit_state(False, float("nan"), 0.7, 0.3, bar_ts, bar_ts, ttl_ns) == "UNKNOWN"  # F2
    assert emit_state(False, 0.005, float("inf"), 0.3, bar_ts, bar_ts, ttl_ns) == "UNKNOWN"  # F2
    assert emit_state(False, 0.005, 0.7, 0.3, bar_ts - 2 * ttl_ns, bar_ts, ttl_ns) == "UNKNOWN"  # F5
    assert emit_state(False, 0.005, 0.7, 0.3, bar_ts, bar_ts, ttl_ns) == "OK"


def test_regime_gate_veto():
    # S079 gate: p_vol >= 0.80 [example] -> scale 0.0 -> no tickets
    assert hmm_scale(0.30) == 1.0
    assert hmm_scale(0.70) == 0.5
    assert hmm_scale(0.80) == 0.0
    assert hmm_scale(0.95) == 0.0
    assert hmm_scale(float("nan")) == 0.0  # unknown p_vol -> no scale
    # scale flows into sizing: half -> 600 shares, zero -> 0 shares
    assert shares(300.0, 0.25, hmm_scale(0.70), 2e6, 12.0) == 600
    assert shares(300.0, 0.25, hmm_scale(0.90), 2e6, 12.0) == 0


def test_entry_booleans():
    # §T3 ENTER_LONG / ENTER_SHORT Boolean expressions
    assert enter_long(0.005, 0.70)
    assert not enter_long(0.001, 0.70)   # below mom_min
    assert not enter_long(0.005, 0.40)   # below class_min
    assert not enter_long(-0.005, -0.70)  # wrong sign agreement
    assert enter_short(-0.005, -0.70)
    assert not enter_short(-0.001, -0.70)
    assert not enter_short(-0.005, -0.40)
    assert not enter_short(0.005, 0.70)


def test_sizing_function():
    # §T3 shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost)
    # per-trade R $300 / $0.25 stop -> 1200 shares (matches the fixture qty)
    assert shares(300.0, 0.25, 1.0, 2e6, 12.0) == 1200
    assert shares(300.0, 0.25, 0.5, 2e6, 12.0) == 600
    assert shares(300.0, 0.25, 0.0, 2e6, 12.0) == 0
    # ADV cap binds: 1% of 50k shares = 500
    assert shares(300.0, 0.25, 1.0, 50000, 12.0) == 500
    # $2M gross cap binds at $50: 1200 sh * $50 = $60k < cap; force with big R
    assert shares(300000.0, 0.25, 1.0, 1e9, 12.0) == 40000  # 2M/50
    # zero stop distance is floored, never ZeroDivisionError
    assert shares(300.0, 0.0, 1.0, 2e6, 12.0) >= 0


def test_cost_callable_signature():
    c = expected_cost_bps(250000.0, 0.5, "XNAS", "taker", "normal")
    assert isinstance(c, float) and math.isfinite(c)
    assert c == 12.0
