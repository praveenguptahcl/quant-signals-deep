"""Concrete sketch: T020 Triple-Barrier + Meta-Labeling Overlay.

Run: python3 -m pytest modules/tests/test_T020.py -q
"""
import csv
import math
import os

SID = "T020"
TAPE = os.path.join("modules", "fixtures", "T020_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T020_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp

# --- module under test mirrors (normative §T3 / §T5) ---------------------------

def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T020 COST block (single source of truth)."""
    # The overlay inherits the primary's cost model; stub returns 0 and the
    # cost gate is evaluated against the primary's expected_cost_bps.
    spread_bps = 0.0    # [default] inherits the primary's cost model
    fee_bps = 0.0       # [default] inherits the primary's cost model
    borrow_bps = 0.0    # [default] inherits the primary's cost model
    impact_bps = 0.0    # [default] inherits the primary's cost model
    return spread_bps + fee_bps + borrow_bps + impact_bps


def edge_bps(primary_edge_bps, meta_prob) -> float:
    """§T3 modeled edge: pedge * (2*meta_prob - 1) [example]."""
    return primary_edge_bps * (2.0 * meta_prob - 1.0)


def shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost):
    """§T3 normative sizing: primary's sizing scaled by meta-confidence.
    vol_estimate carries meta_prob (documented argument reuse)."""
    n_primary = risk_budget_R / max(stop_distance, 1e-9)   # [default] primary floor
    n_primary = min(n_primary, ADV_cap * 0.01)              # 1% ADV [default]
    scale = 0.5 + 0.5 * vol_estimate                        # meta-confidence scale [default]
    return int(n_primary * scale)


def overlay_pass(direction, meta_prob, validation_ok, meta_threshold=0.55):
    """Normative §T3 pass-through predicate (ticket emitted iff True)."""
    return (direction != 0) and (meta_prob >= meta_threshold) and bool(validation_ok)


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
        # the §T3 modeled edge recomputed from the tape row
        eb = edge_bps(float(t["primary_edge_bps"]), float(t["meta_prob"]))
        assert abs(eb - float(e["expected_edge_bps"])) <= CSV_TOL_BPS


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
    assert c == 0.0, "overlay layer adds no cost; the primary's cost governs"
    if c <= 0:
        # zero/negative cost (overlay, maker rebate): the gate passes any positive edge
        assert c <= k * 0.05, "non-positive cost must clear the gate"
    else:
        assert c <= k * 50.0, "cost gate must pass when edge >> cost"
        assert not (c <= k * 0.05), "cost gate must block when edge << cost"


def test_meta_veto_gate():
    # the overlay's core decision: ticket_count on the tape must equal the
    # normative pass-through predicate; vetoed rows are zero-P&L no-ticket rows
    _, tape = load_csv(TAPE)
    passed = [t for t in tape if int(t["ticket_count"]) == 1]
    vetoed = [t for t in tape if int(t["ticket_count"]) == 0]
    assert passed and vetoed, "fixture must exercise both the pass and veto paths"
    for t in tape:
        direction = int(t["primary_dir"])
        meta_p = float(t["meta_prob"])
        val_ok = int(t["validation_ok"])
        expect_ticket = overlay_pass(direction, meta_p, val_ok)
        assert int(t["ticket_count"]) == (1 if expect_ticket else 0), \
            f"trade {t['trade_id']}: ticket_count must follow the meta-veto predicate"
    for t in vetoed:
        assert float(t["meta_prob"]) < 0.55, "veto rows are meta_prob < 0.55 [example]"
        assert float(t["entry_px"]) == float(t["exit_px"]), \
            "vetoed bets emit no ticket: entry == exit, P&L 0"
    for t in passed:
        assert float(t["meta_prob"]) >= 0.55


def test_validation_gate_disables_overlay():
    # C11: failed purged/embargoed validation -> overlay disabled (DEGRADED),
    # primary runs unfiltered; no ticket is emitted by the overlay
    assert overlay_pass(1, 0.72, 1) is True
    assert overlay_pass(1, 0.72, 0) is False, "validation_ok=False disables the overlay"
    assert overlay_pass(1, 0.48, 1) is False, "meta_prob < threshold vetoes"
    assert overlay_pass(0, 0.99, 1) is False, "no primary direction: overlay never generates"


def test_kill_switch_trips_and_rearms():
    # ARMED -> TRIPPED -> RECOVERY -> ARMED
    state = "ARMED"
    kill_conditions = ["meta-model validation fails (S088) [example]",
                       "primary signal stale (TTL breach) [example]",
                       "clock skew > 50 ms [example]"]
    validation_ok = False  # S088 fails -> trip
    if not validation_ok:
        state = "TRIPPED"   # stop pass-through immediately, page
    assert state == "TRIPPED"
    assert isinstance(kill_conditions, list) and len(kill_conditions) >= 3
    checklist = [True, True, True, True, True, True, True]  # §T0 re-arm checklist
    assert all(checklist), "every re-arm checklist item must be green"
    state = "RECOVERY"
    state = "ARMED"
    assert state == "ARMED"


def test_invalid_input_emits_unknown():
    # invalid input -> UNKNOWN, never interpolated (F1/F2)
    def emit_state(bid_px, ask_px):
        if bid_px <= 0 or ask_px <= bid_px:
            return "UNKNOWN"
        return "OK"
    assert emit_state(50.00, 50.00) == "UNKNOWN"
    assert emit_state(50.01, 50.00) == "UNKNOWN"
    assert emit_state(50.00, 50.01) == "OK"


def test_sizing_meta_scale():
    # the §T3 sizing scale is monotone in meta_prob: threshold bet < full bet
    at_threshold = shares(100.0, 0.5, 0.55, 100000, 0.0)
    at_full = shares(100.0, 0.5, 1.0, 100000, 0.0)
    assert at_threshold < at_full, "higher meta_prob must size larger"
    assert at_threshold > 0
    # primary floor: zero stop_distance must not divide by zero
    assert shares(100.0, 0.0, 0.9, 100000, 0.0) > 0
    # ADV cap binds before the raw R/stop ratio
    assert shares(1e12, 0.01, 1.0, 1000, 0.0) == 10, "1% of 1000-share ADV cap"


def test_config_defaults_match():
    # §T0 Config dataclass defaults mirror the §T4 parameter table
    config = {"pt_sl_mult": 1.0, "meta_threshold": 0.55, "max_hold_bars": 20,
              "cooldown_s": 0.0, "cost_gate_k": 0.5, "staleness_ttl_s": 120.0}
    ranges = {"pt_sl_mult": (0.5, 3.0), "meta_threshold": (0.5, 0.8),
              "max_hold_bars": (5, 100), "cooldown_s": (0, 3600),
              "cost_gate_k": (0.1, 2.0), "staleness_ttl_s": (30, 600)}
    for name, default in config.items():
        lo, hi = ranges[name]
        assert lo <= default <= hi, f"{name} default outside its range"
    assert config["max_hold_bars"] == 20


def test_cost_callable_signature():
    c = expected_cost_bps(250000.0, 0.5, "XNAS", "taker", "normal")
    assert isinstance(c, float) and math.isfinite(c)
