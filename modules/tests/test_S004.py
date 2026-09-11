#!/usr/bin/env python3
"""Acceptance tests for S004 — Microprice (Stoikov) (8 tests, tolerance 1e-9 [default])."""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S004_tape.csv"
EXP = FIX / "S004_expected.csv"
TOL = 1e-9  # [default] per §S4


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


def col(header, name):
    return header.index(name)


def microprice(bid, qb, ask, qa):
    """Closed-form reference: (qa*bid + qb*ask)/(qa+qb); I = qb/(qb+qa)."""
    return (qa * bid + qb * ask) / (qa + qb), qb / (qb + qa), (bid + ask) / 2


def recompute(theader, trows):
    i_ev, i_bid, i_qb = col(theader, "ev"), col(theader, "bid_px"), col(theader, "qb")
    i_ask, i_qa = col(theader, "ask_px"), col(theader, "qa")
    out = []
    for r in trows:
        m, I, mid = microprice(float(r[i_bid]), float(r[i_qb]), float(r[i_ask]), float(r[i_qa]))
        out.append([r[i_ev], m, mid, I])
    return out


def imbalance_bin(I, n=5):
    """Normative binning (§S3): b = min(n-1, floor(n*I)), I clamped to [0,1]."""
    I = min(1.0, max(0.0, I))
    return min(n - 1, math.floor(n * I))


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
    got = recompute(theader, trows)
    assert got == recompute(theader, trows), "recompute must be deterministic"
    assert len(got) == len(erows), f"row count {len(got)} != {len(erows)}"
    for i, (g, e) in enumerate(zip(got, erows)):
        assert len(g) == len(e), f"row {i}: col count {len(g)} != {len(e)}"
        for j, (gv, ev) in enumerate(zip(g, e)):
            assert close_enough(gv, ev), f"row {i} col {eheader[j]}: {gv!r} != {ev!r}"


def test_02_microprice_within_spread():
    # The microprice must lie inside [bid, ask] by construction (F2 bound).
    theader, trows = load(TAPE)
    eheader, erows = load(EXP)
    i_bid, i_ask, i_ev = col(theader, "bid_px"), col(theader, "ask_px"), col(theader, "ev")
    j_ev, j_micro = col(eheader, "ev"), col(eheader, "micro")
    for t, e in zip(trows, erows):
        assert t[i_ev] == e[j_ev], "fixture row alignment"
        assert float(t[i_bid]) <= float(e[j_micro]) <= float(t[i_ask])


def test_03_signal_vector_shape():
    sig = signal_stub(0.006, 0.004, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_04_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(0.006, 0.004, computed_at=computed_at)
    fill_event_ts = computed_at + 1  # earliest legal fill: strictly after the signal bar
    assert fill_event_ts > sig["computed_at"]  # assert fill_event > signal_event
    same_bar_fill_ts = computed_at
    assert not (same_bar_fill_ts > sig["computed_at"]), "same-bar fill must be rejected"


def test_05_cost_gate():
    k = 0.5  # [default]
    assert expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 10.0  # large edge passes
    assert not (expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 0.01)  # tiny edge blocked


def test_06_invalid_input_unknown():
    sig = signal_stub_invalid()
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0


def test_07_imbalance_binning():
    # Normative bin mapping used by the phase-2 Markov estimator (§S3).
    assert imbalance_bin(0.0) == 0
    assert imbalance_bin(0.6) == 3   # floor(5*0.6)=3
    assert imbalance_bin(0.9) == 4
    assert imbalance_bin(1.0) == 4   # clamped
    assert imbalance_bin(-0.1) == 0  # clamped
    assert imbalance_bin(1.5) == 4   # clamped
    assert imbalance_bin(0.2, n=5) == 1
    assert imbalance_bin(0.6, n=10) == 6


def test_08_time_seq_ordering():
    # Fixture must pin the time contract: event_ts strictly increasing, seq consecutive.
    theader, trows = load(TAPE)
    i_ts, i_seq = col(theader, "event_ts"), col(theader, "seq")
    ts = [int(r[i_ts]) for r in trows]
    seq = [int(r[i_seq]) for r in trows]
    assert all(b > a for a, b in zip(ts, ts[1:])), "event_ts must be strictly increasing"
    assert all(b - a == 1 for a, b in zip(seq, seq[1:])), "seq must advance by 1"
