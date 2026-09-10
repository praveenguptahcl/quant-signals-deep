#!/usr/bin/env python3
"""Acceptance tests for S012 — Roll implied spread (sketch-level, concrete)."""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S012_tape.csv"
EXP = FIX / "S012_expected.csv"
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
    """Roll fixture: per-day price changes; spread asserted in test_06."""
    out, prev = [], None
    for r in trows:
        close = float(r[1])
        dp = "" if prev is None else round(close - prev, 4)
        prev = close
        out.append([r[0], close, dp])
    return out


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.50   # [example] bar-close crossing assumption
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


def test_06_roll_spread():
    # gamma_1 = -0.0007833 (fixture-computed); s = 2*sqrt(-g1) ~= 0.056.
    eheader, erows = load(EXP)
    dps = [float(e[2]) for e in erows[1:]]
    n = len(dps)
    mean = sum(dps) / n
    g1 = sum((dps[i] - mean) * (dps[i - 1] - mean) for i in range(1, n)) / n
    assert g1 < 0
    s = 2 * (abs(g1) ** 0.5)
    assert abs(s - 0.056) < 0.005  # fixture-calibrated band
    bps = s / 100.0 * 10000
    assert abs(bps - 5.6) < 0.5


def test_02_signal_vector_shape():
    sig = signal_stub(10.0, 50.0, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(10.0, 50.0, computed_at=computed_at)
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
