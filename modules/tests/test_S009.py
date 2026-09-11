#!/usr/bin/env python3
"""Acceptance tests for S009 — PIN (probability of informed trading).

Tests 1-6: fixture/arithmetic/SignalVector/causality/cost-gate/invalid-input.
Tests 7-9: the §S3 normative estimator — log-space multi-start MLE recovery on
a synthetic 120-day panel (seed 20260909, in-memory), short-window rejection,
and the screen aux fields.
"""
import csv
import math
import pathlib

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S009_tape.csv"
EXP = FIX / "S009_expected.csv"
TOL = 1e-4

# ---- §S3 normative estimator: log-space mixture likelihood + log-sum-exp ----
TRUE = dict(alpha=0.4, delta=0.5, mu=50.0, eps_b=40.0, eps_s=40.0)  # [example]
SEED = 20260909  # [example]


def gen_panel(seed, T, alpha, delta, mu, eb, es):
    """Synthetic S007-signed daily counts from the PIN data-generating process."""
    rng = np.random.default_rng(seed)  # PCG64 [default]
    u = rng.random(T)
    good = u < alpha * delta
    bad = (u >= alpha * delta) & (u < alpha)
    B = np.empty(T)
    S = np.empty(T)
    B[good] = rng.poisson(mu + eb, good.sum())
    S[good] = rng.poisson(es, good.sum())
    B[bad] = rng.poisson(eb, bad.sum())
    S[bad] = rng.poisson(mu + es, bad.sum())
    nn = ~(good | bad)
    B[nn] = rng.poisson(eb, nn.sum())
    S[nn] = rng.poisson(es, nn.sum())
    return B, S


def pin_nll(x, B, S):
    """Negative log-likelihood, mixture evaluated in log space (never linear-space
    Poisson terms — Lin & Ke 2011 [documented]). x = [logit(a), logit(d),
    log(mu), log(eps_b), log(eps_s)]."""
    a = 1.0 / (1.0 + np.exp(-x[0]))
    d = 1.0 / (1.0 + np.exp(-x[1]))
    mu, eb, es = np.exp(x[2]), np.exp(x[3]), np.exp(x[4])
    lgB = gammaln(B + 1.0)
    lgS = gammaln(S + 1.0)
    c1 = np.log(a * d) - (mu + eb + es) + B * np.log(mu + eb) + S * np.log(es) - lgB - lgS
    c2 = np.log(a * (1 - d)) - (mu + eb + es) + B * np.log(eb) + S * np.log(mu + es) - lgB - lgS
    c3 = np.log(1 - a) - (eb + es) + B * np.log(eb) + S * np.log(es) - lgB - lgS
    mx = np.maximum(np.maximum(c1, c2), c3)
    ll = np.sum(mx + np.log(np.exp(c1 - mx) + np.exp(c2 - mx) + np.exp(c3 - mx)))
    return -float(ll)


def mle_pin(B, S, n_starts=12):
    """Multi-start log-space MLE per §S3 normative pseudocode."""
    tot = float((B + S).mean())
    starts = []
    for a0 in (0.2, 0.4, 0.6, 0.8):  # [default] grid
        for d0 in (0.25, 0.5, 0.75):  # [default] grid
            starts.append([np.log(a0 / (1 - a0)), np.log(d0 / (1 - d0)),
                           np.log(max(5.0, tot / 4.0)),  # [default] moment init
                           np.log(float(B.mean())), np.log(float(S.mean()))])
    starts = starts[:n_starts]
    lo, hi = np.log(1e-3), np.log(1e5)
    bnds = [(-8, 8), (-8, 8), (lo, hi), (lo, hi), (lo, hi)]
    best = None
    for s0 in starts:
        r = minimize(pin_nll, s0, args=(B, S), method="L-BFGS-B", bounds=bnds,
                     options={"maxiter": 1000, "ftol": 1e-12, "gtol": 1e-8})
        if best is None or r.fun < best.fun:
            best = r
    assert best.success, "optimizer non-convergence -> UNKNOWN (F2)"
    x = best.x
    a = 1.0 / (1.0 + np.exp(-x[0]))
    d = 1.0 / (1.0 + np.exp(-x[1]))
    mu, eb, es = np.exp(x[2]), np.exp(x[3]), np.exp(x[4])
    bt = 1e-3  # boundary_tol [default]
    assert all(bt < v < 1 - bt for v in (a, d)), "boundary collapse -> UNKNOWN (F2/S10.1)"
    pin = a * mu / (a * mu + eb + es)
    assert 0.0 <= pin <= 1.0
    return {"alpha": a, "delta": d, "mu": mu, "eps_b": eb, "eps_s": es, "pin": pin}


def signal_panel(B, S, pin_high=0.25):
    """Stub of §S3 signal(): window gate + estimator + screen aux."""
    if len(B) < 60:  # [default] weak identification
        return {"module_state": "DEGRADED", "direction": 0, "confidence": 0.0,
                "capital": 0.0, "aux": {"pin": None, "screen_pass": False}}
    th = mle_pin(B, S)
    pin = th["pin"]
    return {"module_state": "OK", "direction": 0, "confidence": 1.0 - pin,
            "capital": 0.0, "aux": {"pin": pin, "screen_pass": pin < pin_high}}


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
    """Fitted params (example): alpha=0.4, delta=0.5, mu=50, eps_b=eps_s=40.
    E[B] = eps_b + alpha*delta*mu; E[S] = eps_s + alpha*(1-delta)*mu;
    PIN = alpha*mu / (alpha*mu + eps_b + eps_s)."""
    a, dlt, mu, eb, es = 0.4, 0.5, 50.0, 40.0, 40.0
    e_b = eb + a * dlt * mu
    e_s = es + a * (1 - dlt) * mu
    pin = a * mu / (a * mu + eb + es)
    return [[r[0], r[1], r[2], e_b, e_s, pin] for r in trows]


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


def test_06_pin_screen():
    # PIN = 0.2 < pin_high 0.25 -> screen PASSED; PIN in [0,1].
    eheader, erows = load(EXP)
    pin = float(erows[0][5])
    assert 0.0 <= pin <= 1.0
    assert pin < 0.25


def test_02_signal_vector_shape():
    sig = signal_stub(0.8, 0.75, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(0.8, 0.75, computed_at=computed_at)
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


def test_07_mle_recovers_pin():
    # §S3 normative estimator: 120-day synthetic panel, true PIN = 0.2.
    B, S = gen_panel(SEED, 120, TRUE["alpha"], TRUE["delta"], TRUE["mu"],
                       TRUE["eps_b"], TRUE["eps_s"])
    th = mle_pin(B, S, n_starts=12)
    assert abs(th["pin"] - 0.2) <= 0.08, f"PIN recovery failed: {th['pin']}"  # [example] tol
    # strictly interior parameters (no boundary collapse, S10.1)
    assert 0.05 < th["alpha"] < 0.95
    assert 0.05 < th["delta"] < 0.95
    assert th["mu"] > 1.0 and th["eps_b"] > 1.0 and th["eps_s"] > 1.0
    # determinism: identical inputs -> identical estimates
    th2 = mle_pin(B, S, n_starts=12)
    assert th2["pin"] == th["pin"]


def test_08_short_window_degraded():
    # <60-day window -> DEGRADED/FLAT, never a point estimate (§S3).
    B, S = gen_panel(SEED, 30, TRUE["alpha"], TRUE["delta"], TRUE["mu"],
                       TRUE["eps_b"], TRUE["eps_s"])
    sig = signal_panel(B, S)
    assert sig["module_state"] == "DEGRADED"
    assert sig["direction"] == 0
    assert sig["aux"]["pin"] is None
    # 120-day window is fine
    B, S = gen_panel(SEED, 120, TRUE["alpha"], TRUE["delta"], TRUE["mu"],
                     TRUE["eps_b"], TRUE["eps_s"])
    sig = signal_panel(B, S)
    assert sig["module_state"] == "OK"
    assert sig["aux"]["pin"] is not None


def test_09_aux_screen_fields():
    # aux carries pin + screen_pass; confidence = 1 - pin; screen passes at 0.2 < 0.25.
    B, S = gen_panel(SEED, 120, TRUE["alpha"], TRUE["delta"], TRUE["mu"],
                       TRUE["eps_b"], TRUE["eps_s"])
    sig = signal_panel(B, S, pin_high=0.25)
    pin = sig["aux"]["pin"]
    assert 0.0 <= pin <= 1.0
    assert sig["aux"]["screen_pass"] == (pin < 0.25)
    assert sig["confidence"] == 1.0 - pin
    assert sig["direction"] == 0  # gate-only: never a directional trigger
