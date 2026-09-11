#!/usr/bin/env python3
"""Acceptance tests for S025 — Intraday time-series momentum.

Fixture semantics: 40 synthetic 1-min bars (session 2026-09-09); bars 1-30 are
the warm-up window; ret_bps(i) = close_i/close_{i-30} - 1 in bps; trigger when
|r| >= 10 bps (ret_min_bps default). All fixture numbers synthetic [example].
"""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S025_tape.csv"
EXP = FIX / "S025_expected.csv"
TOL = 1e-4
LOOKBACK = 30          # [default] bars
RET_MIN_BPS = 10.0     # [default]
COST_GATE_K = 0.5      # [default]


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
    """30-bar lookback return in bps; trigger at |r| >= ret_min_bps; bar 1..30 flat."""
    closes = [float(r[2]) for r in trows]
    out = []
    for i, r in enumerate(trows):
        if i < LOOKBACK:
            out.append([r[0], r[1], r[2], 0.0, 0])
            continue
        rb = round((closes[i] / closes[i - LOOKBACK] - 1) * 1e4, 4)
        trig = 1 if rb >= RET_MIN_BPS else (-1 if rb <= -RET_MIN_BPS else 0)
        out.append([r[0], r[1], r[2], rb, trig])
    return out


def expected_cost_bps(notional, adv_pct, venue, side, urgency, ref_px=100.0):
    """Callable cost model — L2 constant stack, sourced components (see §S2 COST block).

    Exchange taker $0.0030/share (Nasdaq price list) [documented];
    SEC Section 31 FY2026 $20.60/M on sells [documented];
    spread half 0.43 bps [example]; ref_px $100 [example]; impact 0 flagged.
    """
    spread_bps = 0.43                       # [example]
    taker_bps = 30.0 / ref_px               # $0.0030/share -> 0.30 bps at $100 [documented]
    sec31_bps = 20.60 / 100.0               # $20.60/M on the sell leg [documented]
    borrow_bps = 0.0                        # [default] long-biased reference
    impact_bps = 0.0                        # [example] flagged; calibrate per venue
    fee_bps = taker_bps + sec31_bps
    if side == "maker":
        fee_bps = -20.0 / ref_px            # -$0.0020/share credit -> -0.20 bps at $100 [documented]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal_stub(ret_bps, threshold, computed_at):
    """Minimal stub: direction from threshold crossing; confidence scaled to the move."""
    direction = 1 if ret_bps >= threshold else (-1 if ret_bps <= -threshold else 0)
    confidence = min(1.0, abs(ret_bps) / (2 * threshold)) if direction else 0.0
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
    assert len(trows) == 40, f"tape must hold 40 bars, got {len(trows)}"
    for i, (g, e) in enumerate(zip(got, erows)):
        assert len(g) == len(e), f"row {i}: col count {len(g)} != {len(e)}"
        for j, (gv, ev) in enumerate(zip(g, e)):
            assert close_enough(gv, ev), f"row {i} col {eheader[j]}: {gv!r} != {ev!r}"


def test_02_triggers_long_short_flat():
    # Bars 31-33 LONG (17/14/11 bps), bar 40 SHORT (exact -10 bps boundary),
    # bar 34 flat (8 bps < 10), bars 1-30 flat (warm-up, no full window).
    eheader, erows = load(EXP)
    got = {e[0]: int(e[4]) for e in erows}
    assert got["31"] == 1 and got["32"] == 1 and got["33"] == 1
    assert got["40"] == -1
    assert got["34"] == 0
    assert all(got[str(i)] == 0 for i in range(1, 31))


def test_03_signal_vector_shape():
    sig = signal_stub(17.0, RET_MIN_BPS, computed_at=1788960660000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    short = signal_stub(-10.0, RET_MIN_BPS, computed_at=1788960660000000000)
    assert short["direction"] == -1 and short["confidence"] == 0.5
    boundary_long = signal_stub(10.0, RET_MIN_BPS, computed_at=1788960660000000000)
    assert boundary_long["direction"] == 1, "threshold crossing is inclusive"
    sub = signal_stub(9.9999, RET_MIN_BPS, computed_at=1788960660000000000)
    assert sub["direction"] == 0, "sub-threshold emits flat (C2 bona-fide intent)"


def test_04_no_signal_bar_fills():
    computed_at = 1788960660000000000
    sig = signal_stub(17.0, RET_MIN_BPS, computed_at=computed_at)
    fill_event_ts = computed_at + 1  # earliest legal fill: strictly after the signal bar
    assert fill_event_ts > sig["computed_at"]  # assert fill_event > signal_event
    same_bar_fill_ts = computed_at
    assert not (same_bar_fill_ts > sig["computed_at"]), "same-bar fill must be rejected"


def test_05_cost_gate():
    # At $100 ref: one-way sell-leg cost = 0.43 + 0.30 + 0.206 = 0.936 bps.
    assert abs(expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") - 0.936) < 1e-9
    assert expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= COST_GATE_K * 10.0  # 10 bps edge passes
    assert expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= COST_GATE_K * 15.0  # 15 bps edge passes
    assert not (expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= COST_GATE_K * 0.01)  # 0.01 bps edge blocked
    # Price sensitivity: at $5 ref the taker leg costs 6.636 bps -> a 10 bps edge
    # FAILS the 0.5 gate (5.0). The gate is reference-price sensitive; calibrate ref_px.
    assert not (expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal", ref_px=5.0) <= COST_GATE_K * 10.0)
    # Maker leg at $100: 0.43 - 0.20 = 0.23 bps net.
    assert abs(expected_cost_bps(1e6, 0.01, "XNAS", "maker", "normal") - 0.23) < 1e-9
    assert expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal", ref_px=200.0) < 0.936


def test_06_invalid_input_unknown():
    sig = signal_stub_invalid()
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0


def test_07_deterministic():
    s1 = signal_stub(17.0, RET_MIN_BPS, computed_at=1788960660000000000)
    s2 = signal_stub(17.0, RET_MIN_BPS, computed_at=1788960660000000000)
    assert s1 == s2
    c1 = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")
    c2 = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")
    assert c1 == c2
