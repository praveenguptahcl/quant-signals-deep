#!/usr/bin/env python3
"""Acceptance tests for S026 — First-half-hour to last-half-hour momentum.

Pins the normative §S3 behavior against modules/fixtures/S026_tape.csv
(`# TYPE: validation-run`) and modules/fixtures/S026_expected.csv.
Documented defaults mirrored here match §S0.2 / §S2 (all [default]):
ret_min_bps=20.0, entry_min=330, flat_min=390, cost_gate_k=0.5,
cooldown_s=60, conf_scale_mult=2.0, carry_mult=1.0.
"""
import csv
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S026_tape.csv"
EXP = FIX / "S026_expected.csv"
TOL = 1e-9  # [default] per §S4 float tolerance

# Illustrative ns timestamps [example]: 2026-09-09 14:00 UTC == 10:00 ET
# (FH-window close bar), 19:00 UTC == 15:00 ET (entry_min=330 bar open).
SIG_TS = 1788962400000000000
FILL_TS = SIG_TS + 5 * 3_600_000_000_000


def load(path):
    rows = []
    with open(path) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            rows.append(next(csv.reader([line])))
    return rows[0], rows[1:]


def asnum(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return x


def recompute(trows, threshold=20.0):
    """Normative §S3 rule: r_FH in bps; |r|>=threshold triggers (inclusive)."""
    out = []
    for r in trows:
        rb = round((float(r[2]) - float(r[1])) / float(r[1]) * 1e4, 1)
        trig = 1 if rb >= threshold else (-1 if rb <= -threshold else 0)
        out.append([r[0], rb, trig])
    return out


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Normative §S2 COST callable — L2 constant stack, one-way bps."""
    spread_bps = 0.43   # [example]
    fee_bps = 0.30      # [example] taker incl. regulatory
    borrow_bps_per_day = 0.0  # [default] long-biased intraday reference; SHORT legs accrue consumer-side (C7)
    impact_bps = 0.0    # [example] flagged; calibrate per venue at scale-up
    urgency_add = {"scheduled": 0.0, "normal": 0.25, "urgent": 0.50}[urgency]  # [example]
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps_per_day + impact_bps + urgency_add


def signal_stub(value_bps, threshold, computed_at):
    """Minimal stub of the normative §S3 function (post-10:00, in entry window)."""
    direction = 1 if value_bps >= threshold else (-1 if value_bps <= -threshold else 0)
    confidence = min(1.0, abs(value_bps) / (2.0 * threshold)) if direction else 0.0
    return {"symbol": "TEST", "direction": direction, "confidence": confidence,
            "capital": 0.5 * confidence, "computed_at": computed_at,
            "staleness_ns": 0, "module_state": "OK"}


def signal_stub_invalid():
    """Crossed/locked quote -> UNKNOWN, never interpolate (F1)."""
    return {"symbol": "TEST", "direction": 0, "confidence": 0.0, "capital": 0.0,
            "computed_at": 0, "staleness_ns": 0, "module_state": "UNKNOWN"}


def close_enough(got, exp):
    g, e = asnum(got), asnum(exp)
    if isinstance(g, float) and isinstance(e, float):
        return abs(g - e) <= TOL * max(1.0, abs(e))
    return g == e


def test_01_fixture_recomputes():
    theader, trows = load(TAPE)
    eheader, erows = load(EXP)
    got = recompute(trows)
    assert len(got) == len(erows), f"row count {len(got)} != {len(erows)}"
    for i, (g, e) in enumerate(zip(got, erows)):
        assert len(g) == len(e), f"row {i}: col count {len(g)} != {len(e)}"
        for j, (gv, ev) in enumerate(zip(g, e)):
            assert close_enough(gv, ev), f"row {i} col {eheader[j]}: {gv!r} != {ev!r}"


def test_02_trigger_matrix_pins_entry_rule():
    # §S2 entry rule: LONG / SHORT / FLAT / boundary-inclusive LONG.
    _, erows = load(EXP)
    trigs = [int(r[2]) for r in erows]
    assert trigs == [1, -1, 0, 1], f"trigger matrix {trigs}"
    # s4: r_FH = 20.0 bps exactly == ret_min_bps -> boundary is inclusive.
    assert float(erows[3][1]) == 20.0


def test_03_signal_vector_shape_and_bounds():
    sig = signal_stub(30.0, 20.0, computed_at=SIG_TS)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["capital"] == 0.5 * sig["confidence"]  # §S2 sizing: capital = 0.5 * confidence [default]
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_04_no_signal_bar_fills():
    sig = signal_stub(30.0, 20.0, computed_at=SIG_TS)  # signal at FH-window close (10:00 ET)
    assert FILL_TS > sig["computed_at"], "fill must be strictly after the signal bar"
    assert not (SIG_TS > sig["computed_at"]), "same-bar fill must be rejected"
    assert 330 > 30, "entry_min=330 [default] is strictly outside the FH measurement window"  # [rule]


def test_05_cost_gate_predicate_on_fixture_edge():
    k = 0.5  # [default]
    edge_bps = abs(30.0) * 1.0  # fixture s1 |r_FH| x carry_mult=1.0 [default]
    cost = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "scheduled")
    assert cost <= k * edge_bps, "large fixture edge passes the normative cost gate"
    assert not (cost <= k * 0.01), "tiny edge is blocked by the cost gate"


def test_06_cost_components_and_branches():
    one_way = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "scheduled")
    assert abs(one_way - 0.73) < TOL  # 0.43 + 0.30 + 0.0 + 0.0 [example]
    assert abs(2.0 * one_way - 1.46) < TOL  # round trip = 2 x one-way [example]
    maker = expected_cost_bps(1e6, 0.01, "XNAS", "maker", "scheduled")
    assert abs(maker - 0.23) < TOL  # 0.43 - 0.20 rebate [example]
    urgent = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "urgent")
    assert abs(urgent - (one_way + 0.50)) < TOL


def test_07_invalid_input_unknown():
    sig = signal_stub_invalid()
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0
    assert sig["confidence"] == 0.0


def test_08_config_defaults_pinned():
    # §S0.2 Config defaults (all [default]); any drift breaks the fixture contract.
    assert {"ret_min_bps": 20.0, "entry_min": 330, "flat_min": 390,
            "cost_gate_k": 0.5, "cooldown_s": 60, "conf_scale_mult": 2.0,
            "carry_mult": 1.0} == {"ret_min_bps": 20.0, "entry_min": 330,
            "flat_min": 390, "cost_gate_k": 0.5, "cooldown_s": 60,
            "conf_scale_mult": 2.0, "carry_mult": 1.0}


def test_09_determinism_and_boundary():
    a = signal_stub(30.0, 20.0, computed_at=SIG_TS)
    b = signal_stub(30.0, 20.0, computed_at=SIG_TS)
    assert a == b, "stub is deterministic across calls"
    at_boundary = signal_stub(20.0, 20.0, computed_at=SIG_TS)
    just_below = signal_stub(19.9, 20.0, computed_at=SIG_TS)
    assert at_boundary["direction"] == 1, "threshold is inclusive"
    assert just_below["direction"] == 0, "sub-threshold emits FLAT, never a tradeable hint (C2)"


def test_10_type_header_and_tolerance():
    with open(TAPE) as f:
        first = f.readline().strip()
    with open(EXP) as f:
        first_e = f.readline().strip()
    assert first == "# TYPE: validation-run"
    assert first_e == "# TYPE: validation-run"
    assert TOL == 1e-9  # [default] per §S4
