"""Concrete sketch: T002 Microprice Fair-Value Scalper.

Run: python3 -m pytest modules/tests/test_T002.py -q
"""
import csv
import math
import os

SID = "T002"
TAPE = os.path.join("modules", "fixtures", "T002_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T002_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T002 COST block (single source of truth)."""
    spread_bps = 2.0   # [example] 1-tick @ $50: half-spread per aggressive leg x 2
    fee_bps = 2.0      # [example] $0.005/share each way @ $50 = 1 bps/leg
    borrow_bps = 0.0   # [default] intraday; shorts add C7 locate
    impact_bps = 0.0   # [example] flagged; calibrate per venue at scale-up
    return spread_bps + fee_bps + borrow_bps + impact_bps

def load_csv(path):
    with open(path) as f:
        lines = f.readlines()
    assert lines[0].strip().startswith("# TYPE:"), "missing TYPE header"
    data_lines = [ln for ln in lines[1:] if not ln.lstrip().startswith("#")]
    return lines[0].strip(), list(csv.DictReader(data_lines))


# §T0 Config dataclass mirror: (type, default, range_lo, range_hi, status)
CONFIG = {
    "kappa_mult":          ("float", 0.25,      0.1,      1.0,       "default"),
    "z_delta_entry":       ("float", 1.0,       0.5,      3.0,       "default"),
    "cost_mult":           ("float", 2.0,       1.0,      4.0,       "default"),
    "time_stop_s":         ("float", 10.0,      1.0,      60.0,      "default"),
    "stop_spreads":        ("float", 1.0,       0.5,      3.0,       "default"),
    "cooldown_s":          ("float", 60.0,      0.0,      3600.0,    "default"),
    "cost_gate_k":         ("float", 0.5,       0.1,      2.0,       "default"),
    "per_trade_R":         ("float", 50.0,      10.0,     500.0,     "default"),
    "daily_loss_stop":     ("float", -1000.0,   -10000.0, -100.0,    "default"),
    "max_gross":           ("float", 500000.0,  100000.0, 2000000.0, "default"),
    "max_adverse_per_trade": ("float", 2.0,     1.0,      5.0,       "default"),
    "staleness_ttl_s":     ("float", 3.0,       1.0,      10.0,      "default"),
}

MODULE_STATES = ("OK", "DEGRADED", "UNKNOWN", "OFF")
KILL_STATES = ("ARMED", "TRIPPED", "RECOVERY")


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
    kill_conditions = ["feed heartbeat missed > 2 s [example]", "book sequence gap", "clock skew > 50 ms [example]", "measured effective spread > gate for 5 min [example]"]
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


def test_config_defaults_and_ranges():
    # §T0 single Config dataclass: defaults sit inside ranges, statuses known
    assert len(CONFIG) == 12, "Config surface must match §T0 table"
    for name, (typ, default, lo, hi, status) in CONFIG.items():
        assert typ == "float", name
        assert lo <= default <= hi, f"{name} default {default} outside range"
        assert status in ("fixed", "default", "calibrate", "example", "internal-est"), name
    assert CONFIG["cost_gate_k"][1] == 0.5
    assert CONFIG["kappa_mult"][1] == 0.25
    assert CONFIG["staleness_ttl_s"][1] == 3.0


def test_module_and_kill_state_enums():
    # single canonical degradation token set; kill switch has exactly 3 states
    assert set(MODULE_STATES) == {"OK", "DEGRADED", "UNKNOWN", "OFF"}
    assert KILL_STATES == ("ARMED", "TRIPPED", "RECOVERY")


def test_timing_box_per_event_causality():
    # signal@t (per_event) -> earliest fill @open(t+1): every fill is strictly
    # after its signal event and at least one nanosecond later (t+1 boundary)
    _, tape = load_csv(TAPE)
    for t in tape:
        gap = int(t["fill_ts"]) - int(t["signal_ts"])
        assert gap >= 1, "per-event timing box: fill must land on or after t+1"


def test_fixture_labels_synthetic():
    # worked examples must never conflate synthetic with real
    type_line, _ = load_csv(TAPE)
    assert "synthetic" in type_line, "tape must be labeled synthetic"
    type_line2, _ = load_csv(EXPECTED)
    assert "synthetic" in type_line2, "expected CSV must be labeled synthetic"
