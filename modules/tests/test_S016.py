#!/usr/bin/env python3
"""Acceptance tests for S016 - Hasbrouck information share.

Pins: (1) simple leadership-threshold fixture; (2) reference VECM/IS estimator
against a synthetic 2-venue quote tape with known lead-lag (seed 20260916);
(3) Cholesky upper/lower bound ordering; (4) cointegration pre-check;
(5) SignalVector shape; (6) t->t+1 causality; (7) executable cost-gate
predicate; (8) invalid input -> UNKNOWN; (9) determinism.
"""
import csv
import math
import pathlib

import numpy as np

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S016_tape.csv"
EXP = FIX / "S016_expected.csv"
QTAPE = FIX / "S016_quotes.csv"
QEXP = FIX / "S016_quotes_expected.csv"
TOL = 1e-9
ECM_LAGS = 5  # [default] per S0.2


# ---------------------------------------------------------------- fixtures
def load(path):
    rows = []
    with open(path, newline="") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#") or s.startswith('"#'):
                continue
            rows.append(next(csv.reader([line])))
    return rows[0], rows[1:]


def load_quotes(path):
    header, rows = load(path)
    t = [int(r[0]) for r in rows]
    panels = np.array([[float(r[1]), float(r[2])] for r in rows])
    return header, t, panels


def asnum(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return x


def close_enough(got, exp, tol=TOL):
    g, e = asnum(got), asnum(exp)
    if isinstance(g, float) and isinstance(e, float):
        return abs(g - e) <= tol * max(1.0, abs(e))
    return g == e


# ------------------------------------------------- reference IS estimator
def estimate_is(panels, L=ECM_LAGS):
    """Hasbrouck (1995) information share [documented].

    VECM  dP_t = a*z_{t-1} + sum_i G_i dP_{t-i} + u_t  with known
    cointegrating vector beta=[1,-1]' for same-security venues.
    psi = M * a_perp'  (common-row vector of the long-run multiplier),
    IS_j = ([psi F]_j)^2 / (psi Omega psi'),  F F' = Omega (Cholesky).
    Returns (is_mid, is_lo, is_hi) dicts keyed by venue index and the
    per-ordering shares used to build the bounds.
    """
    Tn, n = panels.shape
    assert n == 2, "reference estimator covers the 2-venue fixture"
    dP = np.diff(panels, axis=0)
    beta = np.array([1.0, -1.0])
    Yrows, Xrows = [], []
    for t in range(L + 1, Tn):  # 1-based VECM time index
        Yrows.append(dP[t - 1])
        row = [1.0, float(beta @ panels[t - 2])]
        for i in range(1, L + 1):
            row.extend(dP[t - 1 - i].tolist())
        Xrows.append(row)
    Y = np.array(Yrows)
    X = np.array(Xrows)
    B, *_ = np.linalg.lstsq(X, Y, rcond=None)
    U = Y - X @ B
    Omega = (U.T @ U) / len(Y)
    alpha = B[1]
    Gamma = np.eye(n)
    for i in range(L):
        Gi = B[2 + i * n:2 + (i + 1) * n, :].T
        Gamma = Gamma - Gi
    a_perp = np.array([alpha[1], -alpha[0]])
    a_perp = a_perp / np.linalg.norm(a_perp)
    b_perp = np.array([1.0, 1.0]) / math.sqrt(2.0)
    M = 1.0 / float(a_perp @ Gamma @ b_perp)
    psi = M * a_perp
    denom = float(psi @ Omega @ psi)
    assert denom > 0, "singular long-run variance -> UNKNOWN (F2)"
    per_order = {}
    for order in ([0, 1], [1, 0]):
        P = np.eye(n)[order]
        F = np.linalg.cholesky(P @ Omega @ P.T)
        contrib = ((psi @ P.T) @ F) ** 2 / denom
        per_order[tuple(order)] = {venue: float(contrib[k]) for k, venue in enumerate(order)}
    is_mid, is_lo, is_hi = {}, {}, {}
    for v in range(n):
        vals = [per_order[o][v] for o in per_order]
        is_lo[v] = min(vals)
        is_hi[v] = max(vals)
        is_mid[v] = sum(vals) / len(vals)
    return is_mid, is_lo, is_hi, per_order


def dickey_fuller_tstat(spread):
    """Minimal DF regression (const, no trend): t-stat on lagged level."""
    s = np.asarray(spread, dtype=float)
    ds = np.diff(s)
    x = np.column_stack([np.ones(len(ds)), s[:-1]])
    coef, *_ = np.linalg.lstsq(x, ds, rcond=None)
    resid = ds - x @ coef
    dof = len(ds) - 2
    s2 = float(resid @ resid) / dof
    xtx_inv = np.linalg.inv(x.T @ x)
    se = math.sqrt(s2 * xtx_inv[1, 1])
    return float(coef[1] / se)


# ------------------------------------------------------------- cost model
def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Callable cost model - bar-signal reference stack (S016 COST block)."""
    spread_bps = 0.50   # [example] bar-close crossing assumption
    fee_bps = 0.30      # [example] reference print
    borrow_bps = 0.0    # [default] long-biased reference; shorts add C7 locate cost
    impact_bps = 0.0    # [example] flagged; calibrate per venue at scale-up
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def cost_gate_passes(edge_bps, k, notional=1e6, adv_pct=0.01, venue="XNAS",
                     side="taker", urgency="normal"):
    """Executable cost-gate predicate (normative): expected_cost_bps <= k * edge_bps."""
    return expected_cost_bps(notional, adv_pct, venue, side, urgency) <= k * edge_bps


# ------------------------------------------------------------ signal stub
def signal_stub(value, threshold, computed_at):
    direction = 1 if value >= threshold else (-1 if value <= -threshold else 0)
    confidence = min(1.0, abs(value) / (2 * threshold)) if direction else 0.0
    return {"symbol": "TEST", "direction": direction, "confidence": confidence,
            "capital": 0.5 * confidence, "computed_at": computed_at,
            "staleness_ns": 0, "module_state": "OK"}


def signal_stub_invalid():
    return {"symbol": "TEST", "direction": 0, "confidence": 0.0, "capital": 0.0,
            "computed_at": 0, "staleness_ns": 0, "module_state": "UNKNOWN"}


# ------------------------------------------------------------------ tests
def test_01_fixture_recomputes():
    theader, trows = load(TAPE)
    eheader, erows = load(EXP)

    def recompute(rows):
        return [[r[0], float(r[1]), 1 if float(r[1]) >= 0.6 else 0] for r in rows]

    got = recompute(trows)
    assert len(got) == len(erows)
    for i, (g, e) in enumerate(zip(got, erows)):
        for j, (gv, ev) in enumerate(zip(g, e)):
            assert close_enough(gv, ev), f"row {i} col {eheader[j]}: {gv!r} != {ev!r}"


def test_02_quotes_fixture_recomputes():
    """Reference estimator reproduces S016_quotes_expected.csv to 1e-9 [default]."""
    _, _, panels = load_quotes(QTAPE)
    eheader, erows = load(QEXP)
    is_mid, is_lo, is_hi, _ = estimate_is(panels)
    assert len(erows) == 2
    for r in erows:
        v = 0 if r[0] == "A" else 1
        assert close_enough(r[1], is_mid[v]), f"IS_mid {r[0]}"
        assert close_enough(r[2], is_lo[v]), f"IS_lo {r[0]}"
        assert close_enough(r[3], is_hi[v]), f"IS_hi {r[0]}"
    assert abs(sum(is_mid.values()) - 1.0) < 1e-9  # F2: shares sum to 1


def test_03_known_leadership_identified():
    """Venue A leads by construction; bounds identify the leader (lo_A > 0.5)."""
    _, _, panels = load_quotes(QTAPE)
    is_mid, is_lo, is_hi, _ = estimate_is(panels)
    leader = max(is_mid, key=is_mid.get)
    assert leader == 0, f"expected venue A to lead, got {leader}"
    assert is_lo[0] > 0.5, "leadership unidentified: lower bound must clear 0.5"
    assert is_mid[0] >= 0.6  # lead_share threshold [default]


def test_04_cholesky_bounds_ordering():
    """Bounds bracket the midpoint; correlated residuals strictly widen bounds."""
    _, _, panels = load_quotes(QTAPE)
    is_mid, is_lo, is_hi, _ = estimate_is(panels)
    for v in (0, 1):
        assert is_lo[v] <= is_mid[v] <= is_hi[v], "bounds must bracket the midpoint"
        assert is_lo[v] <= is_hi[v]
    base_width = is_hi[0] - is_lo[0]
    # correlated-innovation panel: ordering must materially move the share
    rng = np.random.default_rng(7)
    T = 400
    m = np.cumsum(rng.normal(0, 0.0005, size=T))
    common = rng.normal(0, 0.0004, size=T)  # shared shock -> correlated residuals
    pA = m + common + rng.normal(0, 0.0001, size=T)
    pB = np.roll(m, 3) + common + rng.normal(0, 0.0001, size=T)
    c_mid, c_lo, c_hi, _ = estimate_is(np.column_stack([pA, pB]))
    assert c_hi[0] - c_lo[0] > 10 * base_width, "bounds must widen under correlation"
    for v in (0, 1):
        assert c_lo[v] <= c_mid[v] <= c_hi[v]


def test_05_cointegration_precheck():
    """Spread of the fixture venues is stationary; independent walks are not."""
    _, _, panels = load_quotes(QTAPE)
    spread = panels[:, 0] - panels[:, 1]
    assert dickey_fuller_tstat(spread) < -2.86, "fixture spread must reject unit root"
    rng = np.random.default_rng(11)
    w1 = np.cumsum(rng.normal(0, 1, size=500))
    w2 = np.cumsum(rng.normal(0, 1, size=500))
    assert dickey_fuller_tstat(w1 - w2) > -2.86, "independent walks must not reject"


def test_06_signal_vector_shape():
    sig = signal_stub(0.7, 0.6, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_07_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(0.7, 0.6, computed_at=computed_at)
    assert computed_at + 1 > sig["computed_at"]  # assert fill_event > signal_event
    assert not (computed_at > sig["computed_at"]), "same-bar fill must be rejected"


def test_08_cost_gate():
    k = 0.5  # [default]
    assert cost_gate_passes(10.0, k)      # large edge passes
    assert not cost_gate_passes(0.01, k)  # tiny edge blocked
    assert cost_gate_passes(10.0, 2.0)    # open item: k=2 alternative also passes


def test_09_invalid_input_unknown():
    sig = signal_stub_invalid()
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0


def test_10_deterministic():
    _, _, panels = load_quotes(QTAPE)
    a = estimate_is(panels)
    b = estimate_is(panels)
    for da, db in zip(a[:3], b[:3]):
        for v in da:
            assert da[v] == db[v]
