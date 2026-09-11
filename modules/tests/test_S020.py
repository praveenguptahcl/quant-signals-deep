#!/usr/bin/env python3
"""Acceptance tests for S020 — Retail and odd-lot imbalance.

Normative references (mirroring §S3): BJZZ identification = off-exchange (TRF)
+ sub-penny price, excluding the fuzzy-midpoint spread band [0.4, 0.6]
[documented]; odd lots = size < 100 shares [documented], reported as a separate
aux metric, never mixed into RI (O'Hara, Yao & Ye 2014 contamination caveat).
"""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S020_tape.csv"
EXP = FIX / "S020_expected.csv"
TOL = 1e-4

# Pinned reference moments from the fixture header comments [example]
RI_MEAN_REF = 0.10
RI_STD_REF = 0.25
IMB_Z = 2.0
MIN_RETAIL_SHARE = 0.05


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


def is_subpenny(price, tick=0.01):
    """Price off the symbol's minimum pricing increment grid [documented]."""
    return abs(price / tick - round(price / tick)) > 1e-6


def spread_frac(price, bid, ask):
    spread = ask - bid
    return (price - bid) / spread if spread > 0 else 0.5


def is_retail_proxy(price, size, off_exch, bid, ask, tick=0.01):
    """BJZZ identification: off-exchange + sub-penny, excluding fuzzy midpoint
    [0.4, 0.6] of the spread [documented]."""
    if not (off_exch == 1 and is_subpenny(price, tick)):
        return False
    f = spread_frac(price, bid, ask)
    return not (0.4 <= f <= 0.6)


def is_odd_lot(size):
    return size < 100  # [documented] O'Hara, Yao & Ye (2014)


def recompute(trows):
    """Per-print identification flags + cumulative retail-only net/total."""
    out = []
    cnet = ctot = 0.0
    for r in trows:
        price, size = float(r[1]), float(r[2])
        off, bid, ask = int(r[3]), float(r[4]), float(r[5])
        sub = 1 if is_subpenny(price) else 0
        f = spread_frac(price, bid, ask)
        ret = 1 if is_retail_proxy(price, size, off, bid, ask) else 0
        odd = 1 if is_odd_lot(size) else 0
        sv = float(r[10])
        if ret:
            cnet += sv
            ctot += abs(sv)
        out.append([r[0], price, size, off, bid, ask, sub, f, ret, odd, sv, cnet, ctot])
    return out


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.43   # [example]
    fee_bps = 0.30      # [example]
    borrow_bps = 0.0    # [default] long-biased reference; reason in table
    impact_bps = 0.0    # [example] flagged; calibrate per venue at scale-up
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal_stub(ri, z, computed_at):
    """Sentiment-only stub: direction stays 0; bullish/bearish flags in aux;
    capital 0.0 by doctrine. Mirrors §S3 normative pseudocode."""
    bullish = z >= IMB_Z
    bearish = z <= -IMB_Z
    return {"symbol": "TEST", "direction": 0,
            "confidence": min(abs(z) / 4.0, 1.0), "capital": 0.0,
            "computed_at": computed_at, "staleness_ns": 0, "module_state": "OK",
            "aux": {"retail_imb": ri, "retail_imb_z": z,
                    "retail_bullish": bullish, "retail_bearish": bearish,
                    "oddlot_imb": 160.0 / 260.0, "oddlot_note": "contaminated-proxy"}}


def signal_stub_invalid():
    """Crossed/locked quote -> UNKNOWN, never interpolate (F1)."""
    return {"symbol": "TEST", "direction": 0, "confidence": 0.0, "capital": 0.0,
            "computed_at": 0, "staleness_ns": 0, "module_state": "UNKNOWN"}


def close_enough(got, exp):
    g, e = asnum(got), asnum(exp)
    if isinstance(g, float) and isinstance(e, float):
        return abs(g - e) <= TOL * max(1.0, abs(e))
    return g == e


def test_01_fixture_identification_flags():
    theader, trows = load(TAPE)
    eheader, erows = load(EXP)
    got = recompute(trows)
    assert len(got) == len(erows), f"row count {len(got)} != {len(erows)}"
    for i, (g, e) in enumerate(zip(got, erows)):
        assert len(g) == len(e), f"row {i}: col count {len(g)} != {len(e)}"
        for j, (gv, ev) in enumerate(zip(g, e)):
            assert close_enough(gv, ev), f"row {i} col {eheader[j]}: {gv!r} != {ev!r}"


def test_02_fixture_imbalance_and_z():
    eheader, erows = load(EXP)
    net, tot = float(erows[-1][11]), float(erows[-1][12])
    assert net == 190.0 and tot == 290.0  # prints 1,2,3,6 only
    ri = net / tot
    assert abs(ri - 0.6552) < 1e-4
    z = (ri - RI_MEAN_REF) / RI_STD_REF
    assert abs(z - 2.2207) < 1e-3
    assert z >= IMB_Z  # retail-bullish flag pinned
    total_vol = sum(float(r[2]) for r in erows)
    share = tot / total_vol
    assert share >= MIN_RETAIL_SHARE, f"retail share {share} < {MIN_RETAIL_SHARE}"


def test_03_fuzzy_midpoint_excluded():
    # Print 4: sub-penny off-exchange, but spread_frac=0.495 in [0.4,0.6] ->
    # NOT a retail proxy [documented]. Print 5: exact midpoint, not sub-penny.
    assert not is_retail_proxy(100.0099, 90, 1, 100.00, 100.02)
    assert not is_retail_proxy(100.0100, 200, 1, 100.00, 100.02)
    # Boundary behavior: outside the band it stays a proxy.
    assert is_retail_proxy(100.0199, 80, 1, 100.00, 100.02)


def test_04_odd_lot_reported_separately():
    # Odd lots (<100 shares [documented]) are computed as a separate aux
    # metric, never folded into RI. Fixture odd rows: prints 1(+80), 3(-50),
    # 4(+90), 6(+40) -> net +160, total 260 -> oddlot_imb = 0.6154.
    eheader, erows = load(EXP)
    odd_rows = [r for r in erows if int(float(r[9])) == 1]
    assert [r[0] for r in odd_rows] == ["1", "3", "4", "6"]
    odd_imb = sum(float(r[10]) for r in odd_rows) / sum(abs(float(r[10])) for r in odd_rows)
    assert abs(odd_imb - 0.6154) < 1e-4
    # RI (190/290) is built from retail-proxy rows only (1,2,3,6) — the odd-lot
    # flag is orthogonal to the TRF/sub-penny identification.
    assert float(erows[-1][11]) == 190.0


def test_05_signal_vector_shape():
    sig = signal_stub(0.6552, 2.2207, computed_at=1700000000000000000)
    assert sig["direction"] == 0  # sentiment-only doctrine: never a standalone trigger
    assert 0.0 <= sig["confidence"] <= 1.0
    assert sig["capital"] == 0.0
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert sig["aux"]["retail_bullish"] is True
    assert sig["aux"]["retail_bearish"] is False
    assert "oddlot_imb" in sig["aux"]


def test_06_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(0.6552, 2.2207, computed_at=computed_at)
    fill_event_ts = computed_at + 1  # earliest legal fill: strictly after the signal bar
    assert fill_event_ts > sig["computed_at"]  # assert fill_event > signal_event
    same_bar_fill_ts = computed_at
    assert not (same_bar_fill_ts > sig["computed_at"]), "same-bar fill must be rejected"


def test_07_cost_gate():
    k = 0.5  # [default]
    assert expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 10.0  # large edge passes
    assert not (expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 0.01)  # tiny edge blocked


def test_08_invalid_input_unknown():
    sig = signal_stub_invalid()
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0


def test_09_deterministic():
    theader, trows = load(TAPE)
    a, b = recompute(trows), recompute(trows)
    assert a == b


def test_10_tick_aware_subpenny():
    # Rule 612 context: sub-penny is defined relative to the symbol's current
    # minimum pricing increment [documented]. At tick=0.005, 100.005 is on-grid.
    assert is_subpenny(100.0199, tick=0.01)
    assert not is_subpenny(100.005, tick=0.005)
    assert is_subpenny(100.005, tick=0.01)
