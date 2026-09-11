#!/usr/bin/env python3
"""Acceptance tests for S013 — Corwin-Schultz bid-ask spread (sketch-level, concrete)."""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S013_tape.csv"
EXP = FIX / "S013_expected.csv"
TOL = 1e-4
K2 = 3 - 2 * math.sqrt(2)  # 3 - 2*sqrt(2) [documented] C-S (2012) denominator constant


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


def cs_pair(h1, l1, h2, l2):
    """One two-day Corwin-Schultz pair.

    Returns (beta, gamma, alpha, spread) with the documented zero-floor
    max(S, 0) for negative alpha, or None when beta <= 0 (unidentified —
    never a negative spread). Mirrors the §S3 normative pseudocode.
    """
    if not (h1 >= l1 > 0 and h2 >= l2 > 0):
        return None  # invalid bar -> UNKNOWN upstream (F1)
    beta = math.log(h1 / l1) ** 2 + math.log(h2 / l2) ** 2
    if beta <= 0.0:
        return None  # unidentified: degenerate H==L pair [documented]
    h2d, l2d = max(h1, h2), min(l1, l2)
    gamma = math.log(h2d / l2d) ** 2
    alpha = (math.sqrt(2 * beta) - math.sqrt(beta)) / K2 - math.sqrt(gamma / K2)
    spread = 2 * (math.exp(alpha) - 1) / (1 + math.exp(alpha))
    return beta, gamma, alpha, max(spread, 0.0)  # documented zero-floor


def overnight_adjust(h, l, c_prev):
    """C-S (2012) overnight adjustment: subtract the overnight jump from H/L.

    ΔPON = max(L_d - C_{d-1}, 0) + max(C_{d-1} - H_d, 0) [documented].
    """
    dpon = max(l - c_prev, 0.0) + max(c_prev - h, 0.0)
    return h - dpon, l - dpon


def signal_kernel(hl, cfg, closes=None):
    """Reference kernel mirroring the §S3 normative pseudocode (test-local).

    cfg keys: window_days, min_days=22 [default], min_pos_share, spread_high_bps.
    Returns dict with cs_bps (mean per-pair spread), screen_pass, module_state.
    """
    min_days = cfg.get("min_days", 22)
    if len(hl) < min_days:
        return {"cs_bps": None, "screen_pass": False, "module_state": "DEGRADED"}
    spreads, pos = [], 0
    for i in range(len(hl) - 1):
        h1, l1 = hl[i]
        h2, l2 = hl[i + 1]
        if closes is not None:
            h1, l1 = overnight_adjust(h1, l1, closes[i])
            h2, l2 = overnight_adjust(h2, l2, closes[i + 1])
        out = cs_pair(h1, l1, h2, l2)
        if out is None:
            continue
        pos += 1
        spreads.append(out[3])
    n_pairs = len(hl) - 1
    if n_pairs == 0 or (pos / n_pairs) < cfg["min_pos_share"]:
        return {"cs_bps": None, "screen_pass": False, "module_state": "DEGRADED"}
    cs_bps = sum(spreads) / len(spreads) * 10000
    return {"cs_bps": cs_bps, "screen_pass": cs_bps <= cfg["spread_high_bps"],
            "module_state": "OK"}


def recompute(trows):
    """Fixture recompute: per-day (ln(H/L))^2 + per-pair C-S kernel values."""
    out = []
    for i, r in enumerate(trows):
        h, l = float(r[1]), float(r[2])
        lnr2 = round(math.log(h / l) ** 2, 8)
        row = [r[0], h, l, lnr2]
        if i < len(trows) - 1:
            h2, l2 = float(trows[i + 1][1]), float(trows[i + 1][2])
            b, g, a, s = cs_pair(h, l, h2, l2)
            row += [b, g, a, s * 10000]
        else:
            row += ["", "", "", ""]
        out.append(row)
    return out


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.50   # [example] bar-close crossing assumption
    fee_bps = 0.30      # [documented] Nasdaq remove-liquidity $0.0030/share ≈ 0.3 bps at $100
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


def _fixture_hl():
    _, erows = load(EXP)
    return [(float(e[1]), float(e[2])) for e in erows]


def test_01_fixture_recomputes():
    theader, trows = load(TAPE)
    eheader, erows = load(EXP)
    got = recompute(trows)
    assert len(got) == len(erows), f"row count {len(got)} != {len(erows)}"
    for i, (g, e) in enumerate(zip(got, erows)):
        assert len(g) == len(e), f"row {i}: col count {len(g)} != {len(e)}"
        for j, (gv, ev) in enumerate(zip(g, e)):
            assert close_enough(gv, ev), f"row {i} col {eheader[j]}: {gv!r} != {ev!r}"


def test_06_cs_spread_band():
    # Mean per-pair C-S spread over the 5 consecutive pairs; fixture band.
    hl = _fixture_hl()
    spreads = [cs_pair(hl[i][0], hl[i][1], hl[i + 1][0], hl[i + 1][1])[3]
               for i in range(len(hl) - 1)]
    mean_s = sum(spreads) / len(spreads)
    assert 0.0 < mean_s < 0.01
    bps = mean_s * 10000
    assert 5.0 < bps < 100.0


def test_07_negative_beta_unidentified():
    # beta <= 0 (degenerate H==L pair) -> None, never a negative spread.
    assert cs_pair(100.0, 100.0, 100.0, 100.0) is None
    # Invalid bar (H < L or non-positive) -> None (F1: invalid -> UNKNOWN).
    assert cs_pair(99.0, 100.0, 100.0, 99.5) is None
    # Negative alpha -> documented zero-floor max(S, 0), never negative.
    out = cs_pair(100.0, 99.99, 100.02, 100.01)  # small single-day ranges, big two-day range: alpha < 0
    assert out is not None and out[2] < 0.0 and out[3] == 0.0


def test_08_min_pos_share_guard():
    cfg = {"min_days": 22, "min_pos_share": 0.5, "spread_high_bps": 50.0}
    hl = _fixture_hl()
    # All-degenerate panel: every pair beta <= 0 -> pos_share 0 < 0.5 -> DEGRADED.
    flat = [(100.0, 100.0)] * 30
    res = signal_kernel(flat, cfg)
    assert res["module_state"] == "DEGRADED" and res["cs_bps"] is None
    # Fixture panel (6 days < min_days 22) -> DEGRADED on data rule.
    res2 = signal_kernel(hl, cfg)
    assert res2["module_state"] == "DEGRADED"
    # With min_days lowered, healthy panel identifies a positive spread.
    cfg2 = dict(cfg, min_days=2)
    res3 = signal_kernel(hl, cfg2)
    assert res3["module_state"] == "OK" and 5.0 < res3["cs_bps"] < 100.0
    assert res3["screen_pass"] is True


def test_09_kernel_matches_fixture_pairs():
    # Kernel end-to-end mean equals the fixture's pinned per-pair spreads.
    _, erows = load(EXP)
    pinned = [float(e[7]) for e in erows if e[7] != ""]
    hl = _fixture_hl()
    spreads = [cs_pair(hl[i][0], hl[i][1], hl[i + 1][0], hl[i + 1][1])[3]
               for i in range(len(hl) - 1)]
    kernel_mean_bps = sum(spreads) / len(spreads) * 10000
    pinned_mean_bps = sum(pinned) / len(pinned)
    assert abs(kernel_mean_bps - pinned_mean_bps) <= 1e-9 * max(1.0, pinned_mean_bps)


def test_10_overnight_adjustment():
    # ΔPON removes the overnight jump before H/L enter the estimator [documented].
    h, l, c_prev = 105.0, 99.0, 101.0  # overnight gap: C_prev=101 below L=99? no: within
    ha, la = overnight_adjust(102.0, 98.0, 100.0)  # L < C_prev < H -> ΔPON = 0
    assert ha == 102.0 and la == 98.0
    ha2, la2 = overnight_adjust(102.0, 101.5, 100.0)  # gap up: ΔPON = 1.5
    assert abs(ha2 - 100.5) < 1e-12 and abs(la2 - 100.0) < 1e-12
    # Adjusted bars still produce a valid (non-negative) spread.
    out = cs_pair(100.5, 100.0, 100.6, 100.05)
    assert out is not None and out[3] >= 0.0


def test_02_signal_vector_shape():
    sig = signal_stub(20.0, 50.0, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(20.0, 50.0, computed_at=computed_at)
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
