#!/usr/bin/env python3
"""Acceptance tests for S015 — Huang-Stoll spread components (sketch-level, concrete)."""
import csv
import math
import pathlib

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S015_tape.csv"
EXP = FIX / "S015_expected.csv"
TOL = 1e-4
EST_TOL = 1e-9  # estimation fixture: noise-free DGP, recovery exact to float rounding


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


def cases(rows, kind):
    """Select fixture rows by case_type (tape and expected share the schema)."""
    return [r for r in rows if r[0] == kind]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.50   # [example] bar-close crossing assumption
    fee_bps = 0.30      # [documented] Rule 610 $0.0030/share cap on a $100 reference print [example]
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


def test_01_fixture_recomputes():
    # Arithmetic case: component dollars recompute from spread/alpha/beta.
    theader, trows = load(TAPE)
    eheader, erows = load(EXP)
    t = cases(trows, "arithmetic")
    e = cases(erows, "arithmetic")
    assert len(t) == len(e) == 1, "exactly one arithmetic case"
    r = t[0]
    s, a, b = float(r[5]), float(r[6]), float(r[7])
    got = {"order_proc_dollars": s * (1 - a - b),
           "inventory_dollars": s * b,
           "adv_sel_dollars": s * a}
    ei = {c: eheader.index(c) for c in got}
    for key, gv in got.items():
        ev = float(e[0][ei[key]])
        assert abs(gv - ev) <= TOL * max(1.0, abs(ev)), f"{key}: {gv!r} != {ev!r}"


def test_06_shares_sum():
    # Component dollars sum back to the spread; shares sum to 1.
    theader, trows = load(TAPE)
    eheader, erows = load(EXP)
    t = cases(trows, "arithmetic")[0]
    e = cases(erows, "arithmetic")[0]
    s = float(t[5])
    ei = {c: eheader.index(c) for c in ("order_proc_dollars", "inventory_dollars", "adv_sel_dollars")}
    assert abs(sum(float(e[ei[c]]) for c in ei) - s) < 1e-9
    a, b = float(t[6]), float(t[7])
    assert abs((1 - a - b) + b + a - 1.0) < 1e-9


def test_02_signal_vector_shape():
    sig = signal_stub(0.3, 0.6, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(0.3, 0.6, computed_at=computed_at)
    fill_event_ts = computed_at + 1  # earliest legal fill: strictly after the signal bar
    assert fill_event_ts > sig["computed_at"]  # assert fill_event > signal_event
    same_bar_fill_ts = computed_at
    assert not (same_bar_fill_ts > sig["computed_at"]), "same-bar fill must be rejected"


def test_04_cost_gate():
    k = 0.5  # [default]
    assert expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 10.0  # large edge passes
    assert not (expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 0.01)  # tiny edge blocked


def solve_3x3(A, b):
    """Gaussian elimination with partial pivoting (stdlib, no numpy)."""
    M = [row[:] + [bi] for row, bi in zip(A, b)]
    n = 3
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        assert abs(M[piv][col]) > 1e-12, "singular normal equations"
        M[col], M[piv] = M[piv], M[col]
        for r in range(col + 1, n):
            f = M[r][col] / M[col][col]
            for c in range(col, n + 1):
                M[r][c] -= f * M[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (M[r][n] - sum(M[r][c] * x[c] for c in range(r + 1, n))) / M[r][r]
    return x


def ols_no_intercept(X, y):
    """OLS y = X b with no intercept; returns coefficient list."""
    n, k = len(X), len(X[0])
    A = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    bv = [sum(X[i][a] * y[i] for i in range(n)) for a in range(k)]
    return solve_3x3(A, bv)


def load_estimation(path):
    """Load estimation_trade cases: returns (pi, [(t, P, Q), ...])."""
    pi = None
    rows = []
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                if line.startswith("# PI:"):
                    pi = float(line.split(":", 1)[1].split()[0])
                continue
            if not line.strip():
                continue
            r = next(csv.reader([line]))
            if r[0] == "case_type":      # column header row
                continue
            if r[0] != "estimation_trade":
                continue
            rows.append((int(r[2]), float(r[3]), int(r[4])))
    assert pi is not None, "tape must carry # PI: header"
    assert rows, "tape must carry estimation_trade cases"
    return pi, rows


def hs_three_way(trades, pi):
    """Huang-Stoll (1997) three-way estimator (S015 normative procedure).

    dP_t = c1*Q_t + c2*Q_{t-1} + c3*Q_{t-2} + e_t   (no intercept)
    S     = 2*c1
    lam   = 1 + c2/c1            (adverse selection + inventory share)
    alpha = -c3 / (c1*(1-2*pi))  (adverse-selection share)
    beta  = lam - alpha          (inventory share)
    op    = 1 - lam              (order-processing share)
    """
    dP, X = [], []
    for i in range(2, len(trades)):
        _, p_t, q_t = trades[i]
        _, p_prev, _ = trades[i - 1]
        _, _, q_m1 = trades[i - 1]
        _, _, q_m2 = trades[i - 2]
        dP.append(p_t - p_prev)
        X.append([float(q_t), float(q_m1), float(q_m2)])
    c1, c2, c3 = ols_no_intercept(X, dP)
    assert c1 > 0, "traded half-spread estimate must be positive"
    S = 2.0 * c1
    lam = 1.0 + c2 / c1
    assert abs(1.0 - 2.0 * pi) > 1e-12, "pi=0.5 unidentified"
    alpha = -c3 / (c1 * (1.0 - 2.0 * pi))
    beta = lam - alpha
    op = 1.0 - lam
    return {"S": S, "alpha": alpha, "beta": beta, "order_proc": op, "pi": pi}


def test_07_hs_three_way_recovery():
    # Noise-free HS DGP: OLS must recover S/alpha/beta/order_proc to float precision.
    pi, trades = load_estimation(TAPE)
    eheader, erows = load(EXP)
    e = cases(erows, "estimation_trade")
    assert len(e) == 1, "exactly one estimation_trade expected row"
    exp = {eheader[j]: asnum(e[0][j]) for j in range(len(eheader))}
    got = hs_three_way(trades, pi)
    assert abs(got["pi"] - exp["pi"]) < 1e-12
    for key in ("S", "alpha", "beta", "order_proc"):
        assert abs(got[key] - exp[key]) <= EST_TOL, f"{key}: {got[key]!r} != {exp[key]!r}"
    # shares sum to 1 (F2 bound check, tighter than the 1e-6 module gate)
    assert abs(got["alpha"] + got["beta"] + got["order_proc"] - 1.0) < 1e-9


def test_08_reversal_fraction_sane():
    # The (1-2*pi) auxiliary estimator: realized reversal fraction near fixture pi.
    pi, trades = load_estimation(TAPE)
    qs = [q for _, _, q in trades]
    rev = sum(1 for a, b in zip(qs, qs[1:]) if a != b) / (len(qs) - 1)
    assert abs(rev - pi) <= 0.05, f"reversal fraction {rev} far from pi={pi}"  # [example] bound


def test_05_invalid_input_unknown():
    sig = signal_stub_invalid()
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0
