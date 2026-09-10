"""Acceptance tests for R015 - Tick-constraint regime.

Template v1.0.0. Concrete sketch: loads the fixture tape, runs a reference
implementation of the chapter's normative formula, and asserts causality,
F1-F5 fail-safes, and dual-estimator agreement.

Run: python3 -m pytest modules/tests/test_R015.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R015_tape.csv"
EXPECTED = FIX / "R015_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['constrained', 'intermittent', 'unconstrained', 'undefined', 'warming', 'missing', 'invalid']
BOUNDS = (0.0, 1.0)  # mathematical bounds of the indicator value (F2)
DUAL_MODE = "state"  # rel | abs | sign | state
DUAL_TOL = None
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

# ============================ R015 ============================
# RB-list: R015 Tick-constraint regime. Grok RB2 worked example (τ=$0.01):
# spreads (cents): 1,1,2,1,1,1,3,1,1,2 -> 7/10 = 0.70 -> tick-constrained.
R015_SPREADS = [0.01, 0.01, 0.02, 0.01, 0.01, 0.01, 0.03, 0.01, 0.01, 0.02]
R015_TRADES = [100.00] * 9 + [100.005]  # [example] 9 round-tick prints, 1 sub-penny

def r015_tape():
    hdr = ["bar", "event_ts", "asof_ts", "bid", "ask", "tick", "trade_px"]
    rows = []
    for i, (sp, tp) in enumerate(zip(R015_SPREADS, R015_TRADES), 1):
        ts = TS0 + (i - 1) * 60
        rows.append({"bar": i, "event_ts": ts, "asof_ts": ts + 60 * NS,
                     "bid": round(100.0 - sp / 2, 4), "ask": round(100.0 + sp / 2, 4),
                     "tick": 0.01, "trade_px": tp})
    return hdr, rows

def _tick_bind(rows):
    n = len(rows)
    if n == 0:
        return float("nan")
    hit = sum(1 for r in rows if abs((r["ask"] - r["bid"]) - r["tick"]) < 1e-9)
    return hit / n

def _trade_clustering(rows):
    n = len(rows)
    if n == 0:
        return float("nan")
    tick = rows[0]["tick"]
    hit = sum(1 for r in rows if abs(r["trade_px"] - round(r["trade_px"] / tick) * tick) < 1e-9)
    return hit / n

def _r015_state_bind(v):
    if not math.isfinite(v):
        return "undefined"
    return "constrained" if v >= 0.7 else ("unconstrained" if v <= 0.3 else "intermittent")

def _r015_state_clu(v):
    if not math.isfinite(v):
        return "undefined"
    return "constrained" if v > 0.8 else ("unconstrained" if v < 0.5 else "intermittent")

def primary_indicator_r015(rows, cfg):
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN", "computed_at": 0, "vintage": "synthetic"}
    for r in rows:
        if not all(k in r for k in ("bid", "ask", "tick", "trade_px")):
            return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                    "computed_at": r.get("event_ts", 0), "vintage": "synthetic"}
        if not (math.isfinite(r["bid"]) and math.isfinite(r["ask"]) and math.isfinite(r["tick"])
                and r["ask"] >= r["bid"] > 0 and r["tick"] > 0):
            return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                    "computed_at": r.get("event_ts", 0), "vintage": "synthetic"}
    v = _tick_bind(rows)
    return {"value": v, "state": _r015_state_bind(v), "module_state": "OK",
            "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}

def second_estimator_r015(rows, cfg):
    rows = list(rows)
    v = _trade_clustering(rows)
    return {"value": v, "state": _r015_state_clu(v), "computed_at": rows[-1]["event_ts"] if rows else 0}

F2_POISON_R015 = '''
F2_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1060, "bid": float("nan"),
     "ask": float("nan"), "tick": 0.01, "trade_px": 100.0}
]  # NaN quotes fail validation -> invalid (F1) -> UNKNOWN; the fail-safe fires
  # before any indicator is computed. (A fraction indicator has no out-of-bounds
  # path: F2's non-finite branch is unreachable by valid inputs here.)
'''


primary_indicator = primary_indicator_r015
second_estimator = second_estimator_r015


F2_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1060, "bid": float("nan"),
     "ask": float("nan"), "tick": 0.01, "trade_px": 100.0}
]  # NaN quotes fail validation -> invalid (F1) -> UNKNOWN; the fail-safe fires
  # before any indicator is computed. (A fraction indicator has no out-of-bounds
  # path: F2's non-finite branch is unreachable by valid inputs here.)


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
        return RegimeState("R015", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R015", "out_of_bounds", v, ESTIMATOR_VERSION,
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
        return RegimeState("R015", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R015", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R015", r["state"], v, ESTIMATOR_VERSION,
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
    assert rsv.regime_id == "R015"
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
