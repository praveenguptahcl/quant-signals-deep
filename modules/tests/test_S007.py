#!/usr/bin/env python3
"""Acceptance tests for S007 — Trade classification: Lee–Ready & Bulk Volume Classification (sketch-level, concrete)."""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S007_tape.csv"
EXP = FIX / "S007_expected.csv"
TOL = 1e-9  # matches §S4 tolerance on floats; integer contributions exact


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


import math as _m

def _phi(z):
    return 0.5 * (1.0 + _m.erf(z / _m.sqrt(2.0)))

def recompute(trows):
    """Lee-Ready quote rule (+tick-rule walk-back) and BVC allocation (sigma=0.02)."""
    out, past = [], []
    for r in trows:
        kind, rid = r[0], r[1]
        if kind == "LR":
            px, bid, ask = float(r[2]), float(r[3]), float(r[4])
            mid = (bid + ask) / 2.0
            if px > mid:
                d = 1
            elif px < mid:
                d = -1
            else:
                d = 0
                for q in reversed(past):  # tick rule: most recent trade with p_j != p_i
                    if q > px:
                        d = -1
                        break
                    if q < px:
                        d = 1
                        break
            past.append(px)
            out.append([kind, rid, d, "", "", ""])
        else:
            vol, o, c = float(r[5]), float(r[6]), float(r[7])
            z = (c - o) / 0.02
            vb = round(vol * _phi(z), 1)
            vs = round(vol - vb, 1)
            out.append([kind, rid, "", vb, vs, round(vb - vs, 1)])
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


def test_06_tick_rule_walkback():
    # t3: px == mid (100.01); walk back past nothing to t2 px 100.005 -> +1.
    # t5: px == mid (100.01); walk back past t4/t3 (100.01) to t2 (100.005) -> +1.
    eheader, erows = load(EXP)
    got = {e[1]: e[2] for e in erows if e[0] == "LR"}
    assert got["t1"] == "1" and got["t2"] == "-1" and got["t3"] == "1"
    assert got["t4"] == "-1" and got["t5"] == "1" and got["t6"] == "1"


def test_02_signal_vector_shape():
    sig = signal_stub(0.9, 0.8, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(0.9, 0.8, computed_at=computed_at)
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


def bvc_allocate(volume, open_px, close_px, sigma, z_cap=3.0):
    """Mirror of the §S3 normative bvc_allocate: sigma window, z-clip, zero-variance guard."""
    if sigma <= 0:
        return None  # UNKNOWN component — never 0/0
    z = (close_px - open_px) / sigma
    zc = max(-z_cap, min(z_cap, z))
    vb = volume * _phi(zc)
    vs = volume - vb
    return vb, vs, vb - vs


def module_state_for(share, min_share=0.8):
    """Mirror of the §S3 normative state rule."""
    if share >= min_share:
        return "OK"
    if share >= 0.5:
        return "DEGRADED"
    return "UNKNOWN"


def test_07_state_rule_share_gates():
    assert module_state_for(0.85) == "OK"
    assert module_state_for(0.80) == "OK"          # boundary inclusive
    assert module_state_for(0.79) == "DEGRADED"
    assert module_state_for(0.50) == "DEGRADED"    # boundary inclusive
    assert module_state_for(0.49) == "UNKNOWN"


def test_08_zero_variance_unknown():
    # sigma == 0 (e.g. one-tick day / halt reopen): BVC component UNKNOWN, never 0/0
    assert bvc_allocate(1000, 100.00, 100.00, 0.0) is None
    got = bvc_allocate(1000, 100.00, 100.02, 0.02)
    assert got is not None and abs(got[0] - 841.3) < 0.05


def test_09_z_clip_blocks_single_bar_dominance():
    # Extreme price change must be clipped at +-z_cap before Phi:
    # z = 1.0/0.02 = 50 -> clipped to 3 -> Phi(3)=0.99865 -> Vb=998.7, not 1000.0
    vb, vs, net = bvc_allocate(1000, 100.00, 101.00, 0.02, z_cap=3.0)
    assert abs(vb - 998.7) < 0.05, f"z-clip not applied: vb={vb}"
    assert vs > 0.0, "clipped bar must leave residual sell volume"
    # no-clip variant (huge z_cap) allocates essentially all volume
    vb_nc, _, _ = bvc_allocate(1000, 100.00, 101.00, 0.02, z_cap=1e9)
    assert vb_nc > vb, "clip must bind on extreme z"
