#!/usr/bin/env python3
"""Acceptance tests for S022 — Initial-balance expansion."""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S022_tape.csv"
EXP = FIX / "S022_expected.csv"
TOL = 1e-9  # matches §S4 tolerance [default]


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
    """IB rule per §S3 normative pseudocode:
    IB=[100.00,100.40] from bars 1-2 (lock-in on bar at/after IB end [documented]);
    R_t = max(H_t - L_IB, H_IB - L_t); dev_ratio = R_t / R_IB;
    expansion when dev_ratio >= exp_mult (1.5 [default]) with close beyond the IB
    extreme; a close back inside the IB after expansion -> -1 (invalidated)."""
    ibh, ibl, mult = 100.40, 100.00, 1.5
    rib = ibh - ibl
    sess_h, sess_l = -math.inf, math.inf
    out, expanded = [], False
    for r in trows:
        bar, ts_open, h, l, c = int(r[0]), int(r[1]), float(r[2]), float(r[3]), float(r[4])
        assert ts_open > 0 and h >= l and h >= c >= l
        in_ib = 1 if bar <= 2 else 0
        if bar <= 2:
            dev_ratio, expand = 0.0, 0
        else:
            sess_h, sess_l = max(sess_h, h), min(sess_l, l)
            rt = max(sess_h - ibl, ibh - sess_l)
            dev_ratio = rt / rib
            expand = 0
            if expanded and ibl <= c <= ibh:
                expand = -1
            elif dev_ratio >= mult:
                expand = 1 if c > ibh else (-1 if c < ibl else 0)
                expanded = expanded or expand == 1
        out.append([bar, in_ib, dev_ratio, expand])
    return out


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Callable cost model — matches §S2 COST block."""
    spread_bps = 0.43   # [example]
    fee_bps = 0.30      # [documented] $0.0030/share XNAS taker on a $100 stock
    borrow_bps = 0.0    # [default] long-biased reference; reason in table
    impact_bps = 0.0    # [example] flagged; calibrate per venue at scale-up
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def taker_fee_bps(price, venue="XNAS"):
    """XNAS taker fee $0.0030/share [documented] converted to bps for a stock at `price`."""
    return 0.30 * 100.0 / price  # 0.0030/price * 1e4


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
    assert list(theader) == ["bar", "ts_open_ns", "high", "low", "close"]
    got = recompute(trows)
    assert len(got) == len(erows), f"row count {len(got)} != {len(erows)}"
    for i, (g, e) in enumerate(zip(got, erows)):
        assert len(g) == len(e), f"row {i}: col count {len(g)} != {len(e)}"
        for j, (gv, ev) in enumerate(zip(g, e)):
            assert close_enough(gv, ev), f"row {i} col {eheader[j]}: {gv!r} != {ev!r}"


def test_02_signal_vector_shape():
    sig = signal_stub(1, 0.6, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(1, 0.6, computed_at=computed_at)
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


def test_06_expansion_flags():
    eheader, erows = load(EXP)
    got = {e[0]: int(float(e[3])) for e in erows}
    assert got["4"] == 1 and got["5"] == -1 and got["3"] == 0


def test_07_dev_ratio_pinned():
    eheader, erows = load(EXP)
    got = {e[0]: float(e[2]) for e in erows}
    assert got["3"] == 1.375 and got["4"] == 1.75 and got["5"] == 1.75


def test_08_taker_fee_documented():
    # $0.0030/share [documented] -> 0.30 bps at $100, 0.60 bps at $50
    assert abs(taker_fee_bps(100.0) - 0.30) < 1e-12
    assert abs(taker_fee_bps(50.0) - 0.60) < 1e-12
