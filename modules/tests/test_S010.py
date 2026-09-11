#!/usr/bin/env python3
"""Acceptance tests for S010 — Kyle lambda (price impact) (sketch-level, concrete)."""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S010_tape.csv"
EXP = FIX / "S010_expected.csv"
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
    """Kyle lambda fixture: q = d*v, q2, q*dp per trade."""
    out = []
    for r in trows:
        d, v, dp = float(r[1]), float(r[2]), float(r[3])
        q = d * v
        out.append([r[0], q, q * q, round(q * dp, 3)])
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


CFG = {"lambda_high_z": 2.0, "min_trades": 30}  # [default] per §S0.2


def kyle_gate(n_trades, lam_hat, lam_z, cfg=CFG):
    """Sketch of the §S3 normative gating logic (behavior-pinning, not production code).

    lam_z may be None when rolling stats are unavailable (no veto on missing history).
    """
    if n_trades < cfg["min_trades"]:  # [default] identification floor (S10: under-identified)
        return {"direction": 0, "confidence": 0.0, "capital": 0.0,
                "module_state": "DEGRADED", "impact_ok": True, "reason": "under-identified"}
    if lam_hat < 0:  # F2: sign-convention flip (S10.1)
        return {"direction": 0, "confidence": 0.0, "capital": 0.0,
                "module_state": "UNKNOWN", "impact_ok": False, "reason": "negative-lambda"}
    if lam_z is None:  # S10.10: no veto on missing history
        return {"direction": 0, "confidence": 0.0, "capital": 0.0,
                "module_state": "DEGRADED", "impact_ok": True, "reason": "no-history"}
    impact_ok = lam_z <= cfg["lambda_high_z"]  # normative gate
    return {"direction": 0,
            "confidence": min(abs(lam_z) / 3.0, 1.0),
            "capital": 0.0,  # gauge-only: never directs size
            "module_state": "OK" if impact_ok else "DEGRADED",
            "impact_ok": impact_ok}


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


def test_06_lambda_hat():
    # lambda_hat = sum(q*dp)/sum(q^2) = 24.072/25,176,900 = 9.5611e-07 (fixture-calibrated).
    eheader, erows = load(EXP)
    num = sum(float(e[3]) for e in erows)
    den = sum(float(e[2]) for e in erows)
    lam = num / den
    assert abs(lam - 9.5611e-07) < 5e-10
    assert lam >= 0


def test_02_signal_vector_shape():
    sig = signal_stub(1.5, 2.0, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(1.5, 2.0, computed_at=computed_at)
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


def flip_dp(trows):
    """Negate every price change: simulates an S007 sign-convention flip."""
    out = []
    for r in trows:
        out.append([r[0], r[1], r[2], str(-float(r[3]))])
    return out


def test_07_sign_flip_unknown():
    # S10.1: reversing d_i (here: flipping dp sign) negates lambda_hat -> UNKNOWN (F2).
    theader, trows = load(TAPE)
    flipped = flip_dp(trows)
    n = len(flipped)
    num = sum(float(r[1]) * float(r[2]) * float(r[3]) for r in flipped)
    den = sum((float(r[1]) * float(r[2])) ** 2 for r in flipped)
    lam = num / den
    assert lam < 0, f"flipped tape should give negative lambda, got {lam}"
    sig = kyle_gate(100, lam, None)  # n >= 30 so the F2 negative-lambda path is pinned
    assert sig["module_state"] == "UNKNOWN"
    assert sig["impact_ok"] is False
    assert sig["direction"] == 0


def test_08_min_trades_degraded():
    # Fewer than 30 signed trades -> DEGRADED, direction 0, no veto (S10 under-identified).
    sig = kyle_gate(6, 9.5611e-07, 0.5)
    assert sig["module_state"] == "DEGRADED"
    assert sig["direction"] == 0
    assert sig["impact_ok"] is True
    assert sig["capital"] == 0.0


def test_09_deterministic():
    a = kyle_gate(100, 9.5611e-07, 1.2)
    b = kyle_gate(100, 9.5611e-07, 1.2)
    assert a == b


def test_10_impact_halt():
    # lambda_z = 2.5 > lambda_high_z = 2.0 -> impact_ok False, DEGRADED halt guidance.
    sig = kyle_gate(100, 9.5611e-07, 2.5)
    assert sig["impact_ok"] is False
    assert sig["module_state"] == "DEGRADED"
    assert sig["direction"] == 0
    ok = kyle_gate(100, 9.5611e-07, 1.9)
    assert ok["impact_ok"] is True and ok["module_state"] == "OK"
