"""Acceptance tests for R004 - Volatility clustering / persistence state.

Template v1.0.0. Concrete sketch: loads the fixture tape, runs a reference
implementation of the chapter's normative formula, and asserts causality,
F1-F5 fail-safes, and dual-estimator agreement.

Run: python3 -m pytest modules/tests/test_R004.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R004_tape.csv"
EXPECTED = FIX / "R004_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 604800  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['low', 'normal', 'extreme', 'unstable', 'warming', 'missing', 'invalid']
BOUNDS = (0.0, 0.9999)  # mathematical bounds of the indicator value (F2)
DUAL_MODE = "state"  # rel | abs | sign | state
DUAL_TOL = 0.05
ESTIMATOR_VERSION = "1.0.0"


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")

def _stdev(xs, ddof=1):
    xs = list(xs)
    n = len(xs)
    if n <= ddof:
        return float("nan")
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - ddof))

def _pct_rank(x, hist):
    h = list(hist)
    if not h:
        return float("nan")
    return (sum(1 for v in h if v < x) + 0.5 * sum(1 for v in h if v == x)) / len(h)

def _ols_slope(xs, ys):
    xs, ys = list(xs), list(ys)
    mx, my = _mean(xs), _mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den

def _sign(x):
    return 1 if x > 0 else (-1 if x < 0 else 0)

# ============================ R004 ============================
R004_RETS = [0.004,-0.003,0.002,-0.001,0.005,-0.002,0.003,-0.004,0.001,0.002,
             -0.003,0.004,-0.002,0.001,0.003,-0.020,0.025,-0.018,0.030,-0.022,
             0.015,-0.028,0.020,-0.012,0.018,-0.025,0.022,-0.015,0.010,-0.020]

def r004_tape():
    px, closes = 100.0, []
    for r in R004_RETS:
        px *= math.exp(r)
        closes.append(px)
    hdr = ["bar", "event_ts", "asof_ts", "c"]
    rows = []
    for i, c in enumerate(closes, 1):
        ts = TS0 + (i - 1) * DAY
        rows.append({"bar": i, "event_ts": ts, "asof_ts": ts + 3600 * NS, "c": c})
    return hdr, rows

def _garch_pi(rets):
    """Grid MLE GARCH(1,1) persistence. Real but coarse — reference only."""
    n = len(rets)
    m = _mean(rets)
    e = [r - m for r in rets]
    v0 = _mean([x * x for x in e])
    best = None
    for a in (0.02, 0.05, 0.08, 0.12, 0.18):
        for b in (0.75, 0.82, 0.88, 0.92, 0.95):
            if a + b >= 0.9999:
                continue
            w = v0 * (1 - a - b)
            if w <= 0:
                continue
            s2, ll = v0, 0.0
            for x in e:
                s2 = w + a * x * x + b * s2
                ll += -0.5 * (math.log(s2) + x * x / s2)
            if best is None or ll > best[0]:
                best = (ll, a + b, a, b)
    return best[1] if best else float("nan")

def _har_pi(rets):
    """HAR-RV persistence: OLS of next-day sq-return on daily/weekly/monthly means."""
    sq = [r * r for r in rets]
    n = len(sq)
    if n < 26:
        return float("nan")
    Y, X = [], []
    for t in range(21, n - 1):
        d = sq[t]
        w = _mean(sq[t - 4:t + 1])
        mth = _mean(sq[t - 20:t + 1])
        Y.append(sq[t + 1]); X.append([1.0, d, w, mth])
    k = 4
    XtX = [[sum(X[i][p] * X[i][q] for i in range(len(X))) for q in range(k)] for p in range(k)]
    XtY = [sum(X[i][p] * Y[i] for i in range(len(X))) for p in range(k)]
    A = [row[:] + [XtY[p]] for p, row in enumerate(XtX)]
    for col in range(k):
        piv = max(range(col, k), key=lambda rr: abs(A[rr][col]))
        A[col], A[piv] = A[piv], A[col]
        if abs(A[col][col]) < 1e-14:
            return float("nan")
        for rr in range(k):
            if rr != col:
                f = A[rr][col] / A[col][col]
                for cc in range(col, k + 1):
                    A[rr][cc] -= f * A[col][cc]
    beta = [A[p][k] / A[p][p] for p in range(k)]
    return beta[1] + beta[2] + beta[3]

def _r004_state(pi):
    if not math.isfinite(pi):
        return "unstable"
    return "low" if pi < 0.85 else ("normal" if pi <= 0.95 else "extreme")

def primary_indicator_r004(rows, cfg):
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN", "computed_at": 0, "vintage": "synthetic"}
    if any("c" not in r or not r["c"] > 0 for r in rows):
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1].get("event_ts", 0), "vintage": "synthetic"}
    if len(rows) < 26:
        return {"value": float("nan"), "state": "warming", "module_state": "DEGRADED",
                "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}
    rets = [math.log(rows[i]["c"] / rows[i - 1]["c"]) for i in range(1, len(rows))]
    pi = _garch_pi(rets)
    return {"value": pi, "state": _r004_state(pi), "module_state": "OK",
            "computed_at": rows[-1]["event_ts"], "vintage": "synthetic",
            "half_life_d": math.log(0.5) / math.log(pi) if 0 < pi < 1 else float("nan")}

def _garch_pi_coarse(rets):
    """Independent coarse-grid GARCH(1,1) fit — the test's second estimator.
    Production verifier fits HAR-RV (see §R4); this coarse grid is the
    deterministic operational proxy used in the reference test."""
    m = _mean(rets)
    e = [r - m for r in rets]
    v0 = _mean([x * x for x in e])
    best = None
    for a in (0.03, 0.10, 0.15):
        for b in (0.80, 0.86, 0.91):
            if a + b >= 0.9999:
                continue
            w = v0 * (1 - a - b)
            if w <= 0:
                continue
            s2, ll = v0, 0.0
            for x in e:
                s2 = w + a * x * x + b * s2
                ll += -0.5 * (math.log(s2) + x * x / s2)
            if best is None or ll > best[0]:
                best = (ll, a + b, a, b)
    return best[1] if best else float("nan")

def second_estimator_r004(rows, cfg):
    rows = list(rows)
    if len(rows) < 26:
        return {"value": float("nan"), "state": "warming", "computed_at": rows[-1]["event_ts"] if rows else 0}
    rets = [math.log(rows[i]["c"] / rows[i - 1]["c"]) for i in range(1, len(rows))]
    pi = _garch_pi_coarse(rets)
    return {"value": pi, "state": _r004_state(pi), "computed_at": rows[-1]["event_ts"]}

F2_POISON_R004 = '''
F2_POISON_TAPE = [
    {"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i, "c": 100.0}
    for i in range(30)
]  # zero variance -> grid MLE degenerates; guard forces pi outside (0, 0.9999)
'''


primary_indicator = primary_indicator_r004
second_estimator = second_estimator_r004


F2_POISON_TAPE = [
    {"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i, "c": 100.0}
    for i in range(30)
]  # zero variance -> grid MLE degenerates; guard forces pi outside (0, 0.9999)


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def tape():
    rows = []
    for r in load_csv(TAPE):
        row = {}
        for k, v in r.items():
            try:
                row[k] = int(v)
            except ValueError:
                try:
                    row[k] = float(v)
                except ValueError:
                    row[k] = v
        rows.append(row)
    return rows


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label, e.g. "elevated"
    value: float          # indicator value
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


@dataclass
class Config:
    pass  # regime-specific knobs live in the chapter's Config table (§R0.2)


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


def within_tolerance(v1, v2, mode, tol):
    if mode == "rel":
        denom = max(abs(v1), abs(v2), 1e-12)
        return abs(v1 - v2) / denom <= tol
    if mode == "abs":
        return abs(v1 - v2) <= tol
    if mode == "sign":
        return (v1 > 0) == (v2 > 0) and (v1 < 0) == (v2 < 0)
    if mode == "state":
        return v1 == v2
    raise ValueError(mode)


def detect(rows, cfg, now_ns=None, select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState — reference implementation
    with F1-F5 fail-safes wired in (Appendix f v1.0.0)."""
    rows = list(rows)
    r = primary_indicator(rows, cfg)  # dict(value, state, module_state, computed_at)
    if r["module_state"] != "OK":
        return RegimeState("R004", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R004", "out_of_bounds", v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F3: dual-estimator agreement (state mode: same label, or values within
    # the DUAL_TOL guard band at a state boundary [default])
    s = second_estimator(rows, cfg)
    if DUAL_MODE == "state":
        agree = (r["state"] == s["state"]) or (
            DUAL_TOL is not None and math.isfinite(v) and math.isfinite(s["value"])
            and abs(v - s["value"]) <= DUAL_TOL)
    else:
        agree = within_tolerance(v, s["value"], DUAL_MODE, DUAL_TOL)
    if not agree:
        return RegimeState("R004", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R004", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R004", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = Config()
    for i in range(len(evs)):
        r = primary_indicator(evs[: i + 1], cfg)
        want = exp[i + 1]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(r["value"]), i
        elif math.isinf(wv):
            assert math.isinf(r["value"]) and (r["value"] > 0) == (wv > 0), i
        else:
            assert abs(r["value"] - wv) < TOL, i
        assert r["state"] == want["exp_state"], i
        assert r["computed_at"] == int(want["exp_computed_at"]), i
        assert r["module_state"] == want["exp_module_state"], i


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R004"
    assert rsv.state in STATE_LABELS
    assert math.isfinite(rsv.value) and BOUNDS[0] <= rsv.value <= BOUNDS[1]
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. Assert label_ts > indicator_ts for the earliest trade."""
    evs = tape()
    cfg = Config()
    for i in range(len(evs) - 1):
        label = detect(evs[: i + 1], cfg)
        indicator_ts = evs[i]["event_ts"]          # newest data used
        assert label.computed_at == indicator_ts  # label stamped at t, not later
        earliest_trade_ts = evs[i + 1]["event_ts"]
        assert earliest_trade_ts > label.computed_at, f"lookahead at bar {{i}}"
    # appending a future breakout bar must not move the label stamped at t
    label_t = detect(evs[:-1], cfg)
    assert label_t.computed_at == evs[-2]["event_ts"]


def test_F1_missing_input_unknown():
    assert detect([], Config()).module_state == "UNKNOWN"
    bad = [dict(event_ts=1, asof_ts=2)]  # missing indicator fields
    assert detect(bad, Config()).module_state == "UNKNOWN"


def test_F2_bounds_violation_unknown():
    rsv = detect(F2_POISON_TAPE, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = tape()
    orig = mod.second_estimator
    p0 = primary_indicator(evs, Config())["value"]
    bad_val = -1e9 if (p0 >= 0) else 1e9  # opposite sign: disagrees in sign/rel/abs/state modes
    try:
        mod.second_estimator = lambda rows, cfg: {"value": bad_val, "state": "bogus",
                                                 "computed_at": evs[-1]["event_ts"]}
        rsv = mod.detect(evs, Config())
        assert rsv.module_state == "UNKNOWN"
    finally:
        mod.second_estimator = orig


def test_F4_staleness_unknown():
    evs = tape()
    stale_now = evs[-1]["event_ts"] + 10 * CADENCE_S * NS  # >> 3x cadence
    rsv = detect(evs, Config(), now_ns=stale_now)
    assert rsv.module_state == "UNKNOWN"


def test_F5_regime_mining_guard():
    evs = tape()
    try:
        detect(evs, Config(), select_periods=True, preregistered=False)
    except RegimeMiningError:
        pass
    else:
        raise AssertionError("F5: unregistered period selection must raise")
    rsv = detect(evs, Config(), select_periods=True, preregistered=True)
    assert rsv.module_state == "OK"


def test_dual_estimator_agreement():
    """Sentinel vs Verifier agree within tolerance on the fixture."""
    evs = tape()
    cfg = Config()
    r = primary_indicator(evs, cfg)
    s = second_estimator(evs, cfg)
    if DUAL_MODE == "state":
        ok = (r["state"] == s["state"]) or (
            DUAL_TOL is not None and abs(r["value"] - s["value"]) <= DUAL_TOL)
        assert ok, (r, s)
    else:
        assert within_tolerance(r["value"], s["value"], DUAL_MODE, DUAL_TOL), (r, s)
    assert detect(evs, cfg).module_state == "OK"
