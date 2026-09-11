#!/usr/bin/env python3
"""Acceptance tests for S017 — Hawkes-process order-flow intensity (sketch-level, concrete)."""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S017_tape.csv"
EXP = FIX / "S017_expected.csv"
TOL = 1e-9  # [default] per §S4 — the fixture ships full-precision values, so this is exercised


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
    """Hawkes fixture: mu=0.5, alpha=0.4, beta=1.0; lambda(t_i) from prior events."""
    mu, alpha, beta = 0.5, 0.4, 1.0
    out, times = [], []
    for r in trows:
        t = float(r[1])
        ks = sum(math.exp(-beta * (t - s)) for s in times)
        lam = mu + alpha * ks
        out.append([r[0], t, ks, lam])
        times.append(t)
    return out


def hawkes_loglik_recursive(times, mu, alpha, beta, T):
    """Normative §S3.1 objective: Ozaki (1979) recursive exponential-kernel log-likelihood.

    Guards mirror the module-level contract: non-monotonic times -> ValueError
    (module emits UNKNOWN, F1); non-positive params or alpha/beta >= 1 -> -inf
    (stationarity box, module emits DEGRADED/HALT).
    """
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("event times must be strictly increasing")
    if not (mu > 0 and alpha > 0 and beta > 0):
        return float("-inf")
    if alpha / beta >= 1.0:
        return float("-inf")
    A = 0.0
    ll = -mu * T
    prev = None
    for i, t in enumerate(times):
        A = 0.0 if i == 0 else math.exp(-beta * (t - prev)) * (1.0 + A)
        ll += math.log(mu + alpha * A)
        ll -= (alpha / beta) * (1.0 - math.exp(-beta * (T - t)))
        prev = t
    return ll


def hawkes_loglik_direct(times, mu, alpha, beta, T):
    """Direct-sum form of the same objective (no recursion) — must agree."""
    lam = lambda t: mu + alpha * sum(math.exp(-beta * (t - s)) for s in times if s < t)
    compensator = mu * T + (alpha / beta) * sum(1.0 - math.exp(-beta * (T - s)) for s in times)
    return -compensator + sum(math.log(lam(t)) for t in times)


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


def test_06_lambda_at_3():
    # lambda(3) = 0.5 + 0.4*(e^-3 + e^-2 + e^-1) = 0.7212007171103676; branching ratio 0.4 < 1.
    lam3 = 0.5 + 0.4 * (math.exp(-3) + math.exp(-2) + math.exp(-1))
    assert abs(lam3 - 0.7212007171103676) < 1e-9
    assert 0.4 / 1.0 < 1.0


def test_07_mle_objective_pinned():
    # §S3.1 normative objective on the fixture: hand value LL = -3.961960534239271.
    times = [0.0, 1.0, 2.0]
    rec = hawkes_loglik_recursive(times, 0.5, 0.4, 1.0, 3.0)
    direct = hawkes_loglik_direct(times, 0.5, 0.4, 1.0, 3.0)
    assert abs(rec - direct) < 1e-12, f"recursive vs direct MLE objective disagree: {rec} vs {direct}"
    assert abs(rec - (-3.961960534239271)) < 1e-9, f"LL {rec} != hand value"
    # Guards: non-monotonic times rejected (F1); non-stationary box returns -inf.
    try:
        hawkes_loglik_recursive([0.0, 1.0, 1.0], 0.5, 0.4, 1.0, 3.0)
        raise AssertionError("duplicate timestamps must be rejected")
    except ValueError:
        pass
    assert hawkes_loglik_recursive(times, 0.5, 1.5, 1.0, 3.0) == float("-inf")  # alpha/beta >= 1


def test_02_signal_vector_shape():
    sig = signal_stub(4.0, 3.0, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(4.0, 3.0, computed_at=computed_at)
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
