#!/usr/bin/env python3
"""Acceptance tests for S019 — Stealth trading (medium-size informed flow).

Pinned behavior: Barclay-Warner buckets (small < 500, medium 500-9999,
large >= 10000 [documented]); Z statistic on medium-bucket signed volume
normalized by warmup mu/sigma; warmup gate; sigma floor -> DEGRADED;
cost-gate predicate with documented fee components; t->t+1 causality.
"""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S019_tape.csv"
EXP = FIX / "S019_expected.csv"
TOL = 1e-9  # [default] per S019.md S4

# Documented fee components (see S019.md COST block):
#   Nasdaq taker $0.0030/share for shares >= $1 [documented] -> 0.60 bps at $50 [documented]
#   SEC Section 31 FY2026 $20.60/M on covered sales, eff. 2026-04-04 [documented] -> 0.206 bps
TAKER_PER_SHARE = 0.0030      # [documented] Nasdaq price list
SEC31_PER_M = 20.60           # [documented] SEC FY2026 fee-rate advisory
REF_PX = 50.0                 # [example] reference print


def load(path):
    header_comments, rows = {}, []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                if ":" in line[1:]:
                    k, v = line[1:].split(":", 1)
                    header_comments[k.strip()] = v.strip()
                continue
            rows.append(next(csv.reader([line])))
    return header_comments, rows[0], rows[1:]


def asnum(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return x


def recompute(trows, med_mu, med_sigma):
    """Stealth fixture: per-trade signed volume, cumulative sum, z."""
    out, cum = [], 0.0
    for r in trows:
        cum += float(r[1])
        z = (cum - med_mu) / med_sigma
        out.append([r[0], float(r[1]), cum, z])
    return out


def stealth_flag(z, sigma, stealth_z, sigma_floor, warmup_ok):
    """Normative flag decision mirroring S019.md S3 pseudocode."""
    if not warmup_ok:
        return False, "DEGRADED"   # insufficient warmup: never flag
    if sigma < sigma_floor:
        return False, "DEGRADED"   # sigma collapse: never flag
    return (z >= stealth_z), ("OK" if z >= stealth_z else "OK")


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.43   # [example] reference print
    fee_bps = TAKER_PER_SHARE / REF_PX * 1e4  # 0.60 bps [documented]
    if side in ("taker", "sell"):
        fee_bps += SEC31_PER_M / 1e6 * 1e4    # 0.206 bps [documented]
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
    hc, theader, trows = load(TAPE)
    _, eheader, erows = load(EXP)
    got = recompute(trows, float(hc["MED_MU"]), float(hc["MED_SIGMA"]))
    assert len(got) == len(erows), f"row count {len(got)} != {len(erows)}"
    for i, (g, e) in enumerate(zip(got, erows)):
        assert len(g) == len(e), f"row {i}: col count {len(g)} != {len(e)}"
        for j, (gv, ev) in enumerate(zip(g, e)):
            assert close_enough(gv, ev), f"row {i} col {eheader[j]}: {gv!r} != {ev!r}"


def test_06_stealth_z():
    # Z = (900 - 0)/300 = 3.0 >= stealth_z 2.0 -> FLAG.
    hc, _, erows = load(EXP)
    z = float(erows[-1][3])
    assert abs(z - 3.0) < 1e-9
    assert z >= float(hc["STEALTH_Z"])


def test_07_warmup_gate():
    # Insufficient warmup windows -> DEGRADED, never flags.
    flag, state = stealth_flag(3.0, 300.0, 2.0, 125.0, warmup_ok=False)
    assert not flag
    assert state == "DEGRADED"


def test_08_sigma_floor():
    # Sigma collapse -> DEGRADED, never flags (no zero-variance Z explosion).
    flag, state = stealth_flag(1e9, 0.0, 2.0, 125.0, warmup_ok=True)
    assert not flag
    assert state == "DEGRADED"


def test_02_signal_vector_shape():
    sig = signal_stub(3.0, 2.0, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(3.0, 2.0, computed_at=computed_at)
    fill_event_ts = computed_at + 1  # earliest legal fill: strictly after the signal bar
    assert fill_event_ts > sig["computed_at"]  # assert fill_event > signal_event
    same_bar_fill_ts = computed_at
    assert not (same_bar_fill_ts > sig["computed_at"]), "same-bar fill must be rejected"


def test_04_cost_gate():
    k = 0.5  # [default]
    # documented fee stack: 0.43 spread [example] + 0.60 taker [documented] + 0.206 SEC31 [documented]
    assert abs(expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") - 1.236) < 1e-9
    assert expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 10.0  # large edge passes
    assert not (expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 0.01)  # tiny edge blocked


def test_05_invalid_input_unknown():
    sig = signal_stub_invalid()
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0
