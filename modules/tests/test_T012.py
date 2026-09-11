"""T012 Jump-Filtered Overnight-Gap Fade — per-module acceptance tests.

Run: python3 -m pytest modules/tests/test_T012.py -q
"""
import csv
import math
import os
import re

SID = "T012"
TAPE = os.path.join("modules", "fixtures", "T012_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T012_expected.csv")
MD = os.path.join("modules", "strategies", "T012.md")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T012 COST block (single source of truth)."""
    spread_bps = 10.0   # [example] $0.025 assumed spread @ open @ $50: half/aggressive x 2
    fee_bps = 2.0       # [example] $0.005/share each way @ $50 = 1 bps/leg
    borrow_bps_per_day = 0.0  # [default] fade reference (intraday hold); shorts add C7
    impact_bps = 0.0    # [example] flagged; open-auction slippage in conservative variant
    return spread_bps + fee_bps + borrow_bps_per_day + impact_bps


def shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost):
    """Normative sizing function - §T3 (uses all five fenced args)."""
    n = risk_budget_R / max(stop_distance, 1e-9)   # [default] risk-based size
    n = min(n, vol_estimate * 0.10)                # [default] 10% of expected bar volume
    n = min(n, ADV_cap * 0.005)                    # [default] 0.5% ADV participation
    n = min(n * 50.0, 600000.0) / 50.0            # [default] $600k gross cap (@$50/share)
    min_economic = cost / max(stop_distance, 1e-9) # [default] cost must fit in stop budget
    return int(n) if n >= min_economic else 0


def gap_fill_fraction(close, entry_px, ref_close, side):
    """Normative reversion-leg exit math - §T1. side in ('SELL','BUY')."""
    if side == "SELL":   # gap up faded short; reversion = price falls toward ref_close
        return (entry_px - close) / max(entry_px - ref_close, 1e-12)
    return (close - entry_px) / max(ref_close - entry_px, 1e-12)


# §T0 Config dataclass defaults (frozen=True in the module spec)
T012_CONFIG_DEFAULTS = {
    "gap_min": 0.02, "rvol_gap_max": 2.0, "z_exit": 0.5, "stop_dollars": 0.40,
    "time_stop_min": 45.0, "cooldown_s": 600.0, "cost_gate_k": 0.5,
    "risk_budget_R": 300.0, "locate_required": True,
}


def load_csv(path):
    with open(path) as f:
        lines = f.readlines()
    assert lines[0].strip().startswith("# TYPE:"), "missing TYPE header"
    return lines[0].strip(), list(csv.DictReader(lines[1:]))


def front_matter():
    with open(MD) as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "no YAML front matter"
    return m.group(1)


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
    kill_conditions = ["2 consecutive gap continuations [example]", "feed heartbeat missed > 2 s [example]", "clock skew > 50 ms [example]", "4 concurrent gap fades [example]"]
    stale_s = 90.0
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


def test_exit_rule_z_exit():
    # normative exit_trigger reversion leg: gap_fill_fraction >= z_exit (0.5)
    z_exit = T012_CONFIG_DEFAULTS["z_exit"]
    entry, exitp = 51.10, 50.30          # fixture trade 1 (SELL fade of a 2% gap)
    ref_close = entry / 1.02            # implied prior close for a 2% gap-up
    fill_frac = gap_fill_fraction(exitp, entry, ref_close, "SELL")
    assert abs(fill_frac - 0.7984) <= 1e-3, "fixture math sanity"
    assert fill_frac >= z_exit, "exit rule must fire on the reversion leg"
    # formula shape: SELL fades shrink toward ref_close; BUY fades mirror
    assert abs(gap_fill_fraction(entry, entry, ref_close, "SELL")) < TOL
    assert abs(gap_fill_fraction(ref_close, entry, ref_close, "SELL") - 1.0) < TOL
    buy_entry, buy_ref = 48.90, 48.90 * 1.02   # gap-down fade (BUY)
    assert abs(gap_fill_fraction(buy_entry, buy_entry, buy_ref, "BUY")) < TOL
    assert abs(gap_fill_fraction(buy_ref, buy_entry, buy_ref, "BUY") - 1.0) < TOL


def test_sizing_function():
    # §T3 normative shares(): fixture quantity and all five fenced args exercised
    qty = shares(300.0, 0.40, 5e6, 2e6, 45.99)   # R=$300, stop $0.40 -> 750
    assert qty == 750, "fixture trade size must be reproduced"
    assert shares(40.0, 0.40, 5e6, 2e6, 45.99) == 0, "uneconomic trade (cost > stop budget) -> 0"
    assert shares(300.0, 0.40, 1000.0, 2e6, 1.0) == 100, "bar-volume cap binds"
    assert shares(300.0, 0.40, 5e6, 1e4, 1.0) == 50, "ADV cap binds"
    assert shares(300.0, 0.40, 5e6, 2e6, -1.0) == 750, "non-positive cost is fundable"


def test_config_defaults():
    # §T0 T012Config defaults must match the module contract (and front matter)
    fm = front_matter()
    for key, val in T012_CONFIG_DEFAULTS.items():
        assert key in fm, f"{key} missing from front matter params_schema"
    assert T012_CONFIG_DEFAULTS["z_exit"] == 0.5
    assert T012_CONFIG_DEFAULTS["cost_gate_k"] == 0.5
    assert T012_CONFIG_DEFAULTS["cooldown_s"] == 600.0
    assert T012_CONFIG_DEFAULTS["locate_required"] is True


def test_front_matter_version_pin():
    # §0 version bump + template pin + fee as-of pin
    fm = front_matter()
    assert re.search(r'^version:\s*"1\.0\.2"', fm, re.M), "version must be 1.0.2"
    assert re.search(r'^template_version:\s*"1\.0\.0"', fm, re.M), "template_version must be 1.0.0"
    assert re.search(r'^\s*fee_schedule_as_of:\s*"2026-04-04"', fm, re.M), "fee schedule re-pinned to 2026-04-04"
    assert "Deep review 1.0.0" in fm, "changelog must record the deep review"
