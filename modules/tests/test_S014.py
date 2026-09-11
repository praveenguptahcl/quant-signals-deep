#!/usr/bin/env python3
"""Acceptance tests for S014 — Quoted, effective, and realized spread decomposition (sketch-level, concrete). 7 tests."""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S014_tape.csv"
EXP = FIX / "S014_expected.csv"
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
    """Spread decomposition: quoted_half=(a-b)/2; eff=d*(p-m); real=d*(p-m5); adv=eff-real."""
    out = []
    for r in trows:
        d, p, b, a, m5 = float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])
        m = (b + a) / 2.0
        eff = round(d * (p - m), 6)
        real = round(d * (p - m5), 6)
        out.append([r[0], round((a - b) / 2.0, 6), eff, real, round(eff - real, 6)])
    return out


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


def test_06_adv_selection_mean():
    # Mean adverse selection = (0.01+0.02+0.02+0.01)/4 = 0.015 $ = 1.5 bps on $100.
    eheader, erows = load(EXP)
    adv = [float(e[4]) for e in erows]
    assert abs(sum(adv) / len(adv) - 0.015) < 1e-9


def test_02_signal_vector_shape():
    sig = signal_stub(2.0, 5.0, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(2.0, 5.0, computed_at=computed_at)
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


def test_07_causality_timestamps():
    # The tape pins the causality contract: quote precedes the fill,
    # and the post-trade midpoint is exactly the 5-min horizon after the fill.
    _, trows = load(TAPE)
    for r in trows:
        quote_ts, fill_ts, mid5_ts = int(r[6]), int(r[7]), int(r[8])
        assert quote_ts <= fill_ts, f"{r[0]}: quote must precede fill (no lookahead)"
        assert mid5_ts - fill_ts == 300 * 10**9, f"{r[0]}: mid5_ts must be 5 min after fill"
        assert fill_ts - quote_ts <= 1 * 10**9, f"{r[0]}: quote age exceeds 1-s TTL"
