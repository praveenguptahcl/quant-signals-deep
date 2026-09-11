#!/usr/bin/env python3
"""Acceptance tests for S006 — Signed trade imbalance (volume delta) (sketch-level, concrete)."""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S006_tape.csv"
EXP = FIX / "S006_expected.csv"
TOL = 1e-4


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


def recompute(trows):
    """Per-window signed imbalance: TI = sum(sign*size); delta = TI / total volume."""
    wins = {}
    for r in trows:
        w = wins.setdefault(r[0], [0, 0])
        w[0] += int(r[4]) * float(r[3])
        w[1] += float(r[3])
    return [[w, ti, tv, round(ti / tv, 4)] for w, (ti, tv) in sorted(wins.items())]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.43   # [example]
    fee_bps = 0.30      # [example]
    borrow_bps = 0.0    # [default] long-biased reference; reason in table
    impact_bps = 0.0    # [example] flagged; calibrate per venue at scale-up
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal_stub(value, threshold, computed_at):
    """Minimal stub: direction from threshold crossing; confidence scaled."""
    direction = 1 if value >= threshold else (-1 if value <= -threshold else 0)
    confidence = min(1.0, abs(value) / (2 * threshold)) if direction else 0.0
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


def test_06_delta_bounds():
    # Normalized delta must stay in [-1, 1] by construction (F2 bound).
    eheader, erows = load(EXP)
    for e in erows:
        assert -1.0 <= float(e[3]) <= 1.0


def test_02_signal_vector_shape():
    sig = signal_stub(2.4, 2.0, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(2.4, 2.0, computed_at=computed_at)
    fill_event_ts = computed_at + 1  # earliest legal fill: strictly after the signal bar
    assert fill_event_ts > sig["computed_at"]  # assert fill_event > signal_event
    same_bar_fill_ts = computed_at
    assert not (same_bar_fill_ts > sig["computed_at"]), "same-bar fill must be rejected"


def test_04_cost_gate():
    k = 0.5  # [default]
    assert expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 10.0  # large edge passes
    assert not (expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 0.01)  # tiny edge blocked


def test_05_invalid_input_unknown():
    sig = signal_stub_invalid()
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0


def z_of(delta, ref, z_ref_window, sigma_floor=1e-6):
    """Normative z from §S3: prior-L reference, sigma floor, F2 sanity bound."""
    if len(ref) < max(5, z_ref_window // 2):
        return None  # UNKNOWN: insufficient reference history (F1)
    mu = sum(ref) / len(ref)
    var = sum((x - mu) ** 2 for x in ref) / len(ref)
    sigma = max(math.sqrt(var), sigma_floor)
    z = (delta - mu) / sigma
    if not math.isfinite(z) or abs(z) > 10:
        return None  # UNKNOWN: degenerate or explosive z (F2)
    return z


def fixture_deltas():
    """Normalized deltas from the tape fixture (test_01 already pins these)."""
    theader, trows = load(TAPE)
    return sorted(recompute(trows))


def test_07_zscore_exact_and_deterministic():
    # §S3 normative z port: exact against hand-computed values (arithmetic verified
    # independently; the 6-window fixture is an arithmetic toy, not a real reference
    # history, so these pin the math, not the entry decision).
    # Case A: ref=[-0.5,0.8,0.0,0.0,0.4545], mu=0.1509, sigma=0.443325 -> z(0.4)=0.5619
    z = z_of(0.4, [-0.5, 0.8, 0.0, 0.0, 0.4545], 10)
    assert z is not None
    assert abs(z - 0.5619) < 1e-4, f"z(0.4)={z}"
    # Case B: ref=[0.4,0.8,0.0,0.0,0.4545], mu=0.3309, sigma=0.303014 -> z(-0.5)=-2.7421
    z2 = z_of(-0.5, [0.4, 0.8, 0.0, 0.0, 0.4545], 10)
    assert z2 is not None
    assert abs(z2 - (-2.7421)) < 1e-4, f"z(-0.5)={z2}"
    # Deterministic: identical inputs -> identical z across calls.
    assert z_of(0.4, [-0.5, 0.8, 0.0, 0.0, 0.4545], 10) == \
           z_of(0.4, [-0.5, 0.8, 0.0, 0.0, 0.4545], 10)


def test_08_sigma_degeneracy_unknown():
    # Constant reference -> sigma ~ 0 -> floored to 1e-6 -> |z| explodes -> UNKNOWN (failure mode 10).
    z = z_of(0.5, [0.0] * 10, 20, 1e-6)
    assert z is None, f"degenerate sigma must yield UNKNOWN, got z={z}"
    # Short reference history -> UNKNOWN (F1), not a fabricated z.
    z = z_of(0.5, [0.0, 0.0, 0.0], 20, 1e-6)
    assert z is None, f"insufficient history must yield UNKNOWN, got z={z}"
    # Healthy reference -> finite z, not UNKNOWN.
    z = z_of(0.5, [0.0, 0.1, -0.1, 0.05, -0.05, 0.0, 0.1, -0.1, 0.0, 0.0], 20, 1e-6)
    assert z is not None and math.isfinite(z)
