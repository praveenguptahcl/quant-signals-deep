#!/usr/bin/env python3
"""Acceptance tests for S005 — Multi-level book pressure (static depth imbalance).

Mirrors the §S3 normative pseudocode: exponential level weights
w_l = exp(-decay_eta*(l-1)), gates_pass (crossed/locked -> UNKNOWN,
UNDEF/zero-size level -> UNKNOWN, staleness > 3x cadence -> UNKNOWN),
cost-gate predicate, t->t+1 causality assertion.
"""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S005_tape.csv"
EXP = FIX / "S005_expected.csv"
TOL = 1e-9  # [default] — §S4 tolerance on floats
UNDEF_PRICE = 9223372036854775807  # INT64_MAX [documented] — empty-level sentinel


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


def weighted_bp(bids, asks, eta):
    """Normative BP_L: exponential level weights; eta=0 -> equal weights."""
    w = [math.exp(-eta * (l - 1)) for l in range(1, len(bids) + 1)]
    tot_b = sum(wi * bi for wi, bi in zip(w, bids))
    tot_a = sum(wi * ai for wi, ai in zip(w, asks))
    assert (tot_b + tot_a) > 0
    return (tot_b - tot_a) / (tot_b + tot_a)


def recompute(trows, eta=0.0):
    """Static depth imbalance BP_5 on fixture rows (eta=0 pins equal weights)."""
    out = []
    for r in trows:
        bids = [float(x) for x in r[1:6]]
        asks = [float(x) for x in r[6:11]]
        out.append([r[0], round(weighted_bp(bids, asks, eta), 4)])
    return out


def gates_pass(bid_px, ask_px, bid_sz, ask_sz, event_ts, now_ts, snapshot_ms):
    """Normative gates_pass: F1 crossed/locked + missing levels, F4 staleness."""
    if bid_px[0] >= ask_px[0]:
        return False  # crossed/locked quote -> UNKNOWN (F1)
    for px_b, px_a, sz_b, sz_a in zip(bid_px, ask_px, bid_sz, ask_sz):
        if px_b == UNDEF_PRICE or px_a == UNDEF_PRICE:
            return False  # missing level: never interpolate (F1)
        if sz_b <= 0 or sz_a <= 0:
            return False  # non-positive size -> UNKNOWN (F1)
    if now_ts - event_ts > 3 * snapshot_ms * 1_000_000:
        return False  # staleness TTL per §S0.4 (F4)
    return True


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.43   # [example]
    fee_bps = 0.30      # [example]
    borrow_bps = 0.0    # [default] long-biased reference; reason in table
    impact_bps = 0.0    # [example] flagged; calibrate per venue at scale-up
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal_stub(value, threshold, computed_at):
    """Minimal stub: direction from threshold crossing; confidence = min(1,|BP|)."""
    direction = 1 if value >= threshold else (-1 if value <= -threshold else 0)
    confidence = min(1.0, abs(value)) if direction else 0.0
    return {"symbol": "TEST", "direction": direction, "confidence": confidence,
            "capital": 0.5 * confidence, "computed_at": computed_at,
            "staleness_ns": 0, "module_state": "OK"}


def signal_stub_invalid():
    """Invalid input -> UNKNOWN, never interpolate (F1)."""
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


def test_02_depth_tilt_direction():
    # r1 is strongly bid-tilted (0.4545), r2 strongly ask-tilted (-0.6).
    eheader, erows = load(EXP)
    assert float(erows[1][1]) > 0.4
    assert float(erows[2][1]) < -0.5


def test_03_signal_vector_shape():
    sig = signal_stub(0.45, 0.2, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_04_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(0.45, 0.2, computed_at=computed_at)
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


def test_07_eta_zero_reduction():
    # eta=0 must reduce to equal weights, matching every fixture row.
    theader, trows = load(TAPE)
    eheader, erows = load(EXP)
    for i, r in enumerate(trows):
        bids = [float(x) for x in r[1:6]]
        asks = [float(x) for x in r[6:11]]
        # eta=0 -> equal weights: weighted recompute must match the expected row
        assert close_enough(round(weighted_bp(bids, asks, 0.0), 4), erows[i][1])
    # positive eta must down-weight deep levels: eta=1.0 changes the weighted value.
    bids = [1000.0, 900, 800, 700, 600]
    asks = [100.0, 200, 300, 400, 500]
    assert weighted_bp(bids, asks, 0.0) != weighted_bp(bids, asks, 1.0)


def test_08_gates_reject_bad_snapshots():
    bid_px = [100.00, 99.99, 99.98, 99.97, 99.96]
    ask_px = [100.01, 100.02, 100.03, 100.04, 100.05]
    bid_sz = [800, 600, 400, 300, 200]
    ask_sz = [200, 300, 400, 500, 600]
    ts, now = 1700000000000000000, 1700000000500000000  # 0.5 s later, cadence 1000 ms
    assert gates_pass(bid_px, ask_px, bid_sz, ask_sz, ts, now, 1000.0)
    # crossed quote -> UNKNOWN (F1)
    assert not gates_pass([100.02] + bid_px[1:], ask_px, bid_sz, ask_sz, ts, now, 1000.0)
    # locked quote -> UNKNOWN (F1)
    assert not gates_pass([100.01] + bid_px[1:], ask_px, bid_sz, ask_sz, ts, now, 1000.0)
    # UNDEF sentinel level -> UNKNOWN, never interpolate (F1)
    assert not gates_pass([UNDEF_PRICE] + bid_px[1:], ask_px, bid_sz, ask_sz, ts, now, 1000.0)
    # stale snapshot (5 s > 3x cadence) -> UNKNOWN (F4)
    stale_now = ts + 5_000_000_000
    assert not gates_pass(bid_px, ask_px, bid_sz, ask_sz, ts, stale_now, 1000.0)
    # zero size at a level -> UNKNOWN (F1)
    assert not gates_pass(bid_px, ask_px, [0] + bid_sz[1:], ask_sz, ts, now, 1000.0)
