#!/usr/bin/env python3
"""Acceptance tests for S002 — Multi-level / integrated OFI (MLOFI) (sketch-level, concrete)."""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S002_tape.csv"
EXP = FIX / "S002_expected.csv"
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
    """Integrated OFI, equal-weight reference: iofi = sum of per-level OFI."""
    out = []
    for r in trows:
        vals = [float(x) for x in r[1:6]]
        out.append([r[0], sum(vals)])
    return out


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.43   # [example]
    fee_bps = 0.60      # [documented] $0.0030/share (Nasdaq Rule 7018) at $50 reference [example]
    borrow_bps = 0.0    # [default] long-biased reference; reason in table
    impact_bps = 0.0    # [example] flagged; calibrate per venue at scale-up
    if side == "maker":
        fee_bps = -0.20  # rebate [example]; verify against the live tier at scale
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
        # iofi columns only (bucket, iofi); z_iofi is pinned separately in test_07
        assert len(g) == 2, f"row {i}: recompute col count {len(g)} != 2"
        for j, (gv, ev) in enumerate(zip(g, e[:2])):
            assert close_enough(gv, ev), f"row {i} col {eheader[j]}: {gv!r} != {ev!r}"


def test_06_deep_levels_carry_signal():
    # Bucket 6: touch-only (L1) OFI = +300 disagrees with the mid move (-0.8 ticks);
    # integrated iOFI = -100 agrees with it — the documented deep-book value-add.
    theader, trows = load(TAPE)
    eheader, erows = load(EXP)
    l1, iofi, dmid = float(trows[5][1]), float(erows[5][1]), float(trows[5][6])
    assert (l1 > 0) != (dmid > 0), "touch-only OFI points the wrong way here"
    assert (iofi > 0) == (dmid > 0), "integrated OFI must agree with the mid move"


def test_02_signal_vector_shape():
    sig = signal_stub(2.6, 2.0, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(2.6, 2.0, computed_at=computed_at)
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


def zscore_population(vals):
    mu = sum(vals) / len(vals)
    var = sum((x - mu) ** 2 for x in vals) / len(vals)  # ddof=0 [default] per S3
    sd = math.sqrt(var)
    return [(x - mu) / sd for x in vals] if sd > 0 else [0.0] * len(vals)


def test_07_zscore_recomputes():
    # S3 z-score spec: population z of iOFI over the full 8-bucket tape [example]
    theader, trows = load(TAPE)
    eheader, erows = load(EXP)
    assert eheader[2] == "z_iofi"
    iofi = [g[1] for g in recompute(trows)]
    got_z = zscore_population(iofi)
    z_entry = 2.0  # [default]
    for i, (z, e) in enumerate(zip(got_z, erows)):
        assert close_enough(z, e[2]), f"row {i} z_iofi: {z!r} != {e[2]!r}"
    # bucket 3 crosses z_entry -> LONG candidate; no other bucket crosses
    assert got_z[2] >= z_entry
    assert all(abs(z) < z_entry for j, z in enumerate(got_z) if j != 2)


def test_08_entry_predicate_cost_gate():
    # S2 entry rule pinned: bucket-3 LONG candidate, cost gate is normative
    z = 2.0677  # [example] fixture z_iofi for bucket 3
    z_entry = 2.0  # [default]
    edge_bps = abs(z) * 0.35  # [example] modeled per-trade edge -> 0.7237 bps
    cost = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")  # 1.03 bps [example]
    assert abs(cost - 1.03) < 1e-9
    assert abs(z) >= z_entry  # threshold crossed
    assert not (cost <= 0.5 * edge_bps), "default k=0.5 blocks: 1.03 > 0.3618"
    assert cost <= 2.0 * edge_bps, "k=2.0 passes: 1.03 <= 1.4474"
    # short-side mirror: bucket 2 z=-1.0450 -> edge 0.3658 bps, blocked at k=0.5
    z2 = -1.0450
    assert abs(z2) < z_entry  # not even a candidate
    assert not (cost <= 0.5 * abs(z2) * 0.35)
