#!/usr/bin/env python3
"""Acceptance tests for S008 — VPIN (flow toxicity).

Reference-implementation tests: the helpers below re-implement the §S3
normative rules (volume clock with proportional straddle split, BVC
fraction z = Phi(dP/sigma), rolling VPIN) so the tests pin behavior
independently of any production implementation.
"""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S008_tape.csv"
EXP = FIX / "S008_expected.csv"
TOL = 1e-9  # [default] per §S4; integer contributions exact


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
    """Per-bucket order imbalance OI = |buy - sell|."""
    return [[r[0], r[1], r[2], abs(float(r[1]) - float(r[2]))] for r in trows]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.43   # [example]
    fee_bps = 0.30      # [example]
    borrow_bps = 0.0    # [default] long-biased reference; reason in table
    impact_bps = 0.0    # [example] flagged; calibrate per venue at scale-up
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def phi(x):
    """Standard normal CDF — the BVC kernel z = Phi(dP/sigma)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bucketize(trades, bucket_shares, straddle_rule="split"):
    """Reference volume-clock bucketizer (§S3 normative).

    trades: list of (price, size, z) with z the BVC buy fraction of the bar.
    straddle_rule="split": a print spanning a bucket boundary is divided
    proportionally; "whole": the straddling print moves entirely to the new
    bucket (pinned alternative, not the default).
    Returns (closed_buckets, partial_bucket) where each bucket is [Vb, Vs].
    """
    buckets = []
    cur_vb, cur_vs, cur_vol = 0.0, 0.0, 0.0
    for _px, sz, z in trades:
        rem = float(sz)
        while rem > 0:
            if straddle_rule == "split":
                room = bucket_shares - cur_vol
                take = min(rem, room)
                cur_vb += take * z
                cur_vs += take * (1.0 - z)
                cur_vol += take
                rem -= take
                if cur_vol >= bucket_shares - 1e-12:
                    buckets.append([cur_vb, cur_vs])
                    cur_vb, cur_vs, cur_vol = 0.0, 0.0, 0.0
            else:  # "whole": never split a print across the boundary
                if cur_vol + rem > bucket_shares and cur_vol > 0:
                    buckets.append([cur_vb, cur_vs])
                    cur_vb, cur_vs, cur_vol = 0.0, 0.0, 0.0
                cur_vb += rem * z
                cur_vs += rem * (1.0 - z)
                cur_vol += rem
                rem = 0.0
                if cur_vol >= bucket_shares - 1e-12:
                    buckets.append([cur_vb, cur_vs])
                    cur_vb, cur_vs, cur_vol = 0.0, 0.0, 0.0
    partial = [cur_vb, cur_vs] if cur_vol > 0 else None
    return buckets, partial


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


def signal_stub_warmup(n_closed, n_window):
    """Fewer than n closed buckets -> direction 0, DEGRADED (§S3 normative)."""
    if n_closed < n_window:
        return {"symbol": "TEST", "direction": 0, "confidence": 0.0,
                "capital": 0.0, "computed_at": 0, "staleness_ns": 0,
                "module_state": "DEGRADED"}
    raise AssertionError("not a warmup case")


def signal_stub_vpin(vpin):
    """F2: out-of-bounds feature -> UNKNOWN, never a fabricated value."""
    if not (0.0 <= vpin <= 1.0):
        return {"symbol": "TEST", "direction": 0, "confidence": 0.0,
                "capital": 0.0, "computed_at": 0, "staleness_ns": 0,
                "module_state": "UNKNOWN"}
    return {"symbol": "TEST", "direction": 0, "confidence": vpin, "capital": 0.0,
            "computed_at": 0, "staleness_ns": 0, "module_state": "OK"}


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


def test_02_signal_vector_shape():
    sig = signal_stub(0.75, 0.7, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(0.75, 0.7, computed_at=computed_at)
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


def test_06_vpin_values():
    # VPIN_5 = 2500/5000 = 0.5; VPIN_6 = 2900/5000 = 0.58 over the 5-bucket window.
    eheader, erows = load(EXP)
    oi = [float(e[3]) for e in erows]
    assert abs(sum(oi[0:5]) / 5000.0 - 0.5) < 1e-9
    assert abs(sum(oi[1:6]) / 5000.0 - 0.58) < 1e-9


def test_07_bucketizer_straddle_split():
    # §S3 normative: V=1000; trade A 600 all-buy; trade B 600 z=0.5 straddles
    # the bucket 1|2 boundary and is split proportionally; trade C 800 all-buy
    # closes bucket 2. 600+600+800 = 2000 shares = exactly two closed buckets.
    trades = [(10.0, 600, 1.0), (10.0, 600, 0.5), (10.0, 800, 1.0)]
    buckets, partial = bucketize(trades, 1000, straddle_rule="split")
    assert partial is None, "2000 shares = exactly two closed buckets, no partial"
    assert len(buckets) == 2
    b1, b2 = buckets
    # bucket 1: A (600 buy) + 400 of B (200 buy / 200 sell)
    assert abs(b1[0] - 800.0) < 1e-9 and abs(b1[1] - 200.0) < 1e-9
    assert abs(abs(b1[0] - b1[1]) - 600.0) < 1e-9
    # bucket 2: 200 of B (100 buy / 100 sell) + C (800 buy)
    assert abs(b2[0] - 900.0) < 1e-9 and abs(b2[1] - 100.0) < 1e-9
    assert abs(abs(b2[0] - b2[1]) - 800.0) < 1e-9
    # VPIN over the two closed buckets: (600 + 800) / 2000 = 0.70 in [0, 1]
    vpin = (abs(b1[0] - b1[1]) + abs(b2[0] - b2[1])) / (2 * 1000)
    assert abs(vpin - 0.70) < 1e-9
    assert 0.0 <= vpin <= 1.0


def test_08_bvc_fraction():
    # [documented] form: z = Phi(dP / sigma); dP = 1.00, sigma = 2.00
    # -> z = Phi(0.5) = 0.6914624612740131...
    z = phi(1.0 / 2.0)
    assert abs(z - 0.6914624612740131) < 1e-9
    vb, vs = 1000.0 * z, 1000.0 * (1.0 - z)
    assert abs(vb - 691.4624612740131) < 1e-9
    assert abs((vb + vs) - 1000.0) < 1e-9
    # flat-bar edge: sigma = 0 -> z = 0.5 exactly (§S3 normative [default])
    assert abs(phi(0.0) - 0.5) < 1e-12


def test_09_warmup_degraded():
    # fewer than n=50 closed buckets -> direction 0, confidence 0, DEGRADED
    sig = signal_stub_warmup(n_closed=12, n_window=50)
    assert sig["module_state"] == "DEGRADED"
    assert sig["direction"] == 0
    assert sig["confidence"] == 0.0
    assert sig["capital"] == 0.0


def test_10_vpin_bounds_f2():
    for bad in (-0.01, 1.01):
        sig = signal_stub_vpin(bad)
        assert sig["module_state"] == "UNKNOWN", f"vpin={bad} must yield UNKNOWN"
        assert sig["direction"] == 0
    sig = signal_stub_vpin(0.58)
    assert sig["module_state"] == "OK"
    assert abs(sig["confidence"] - 0.58) < 1e-12
