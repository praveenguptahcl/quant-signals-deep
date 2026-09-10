"""Acceptance tests for R020 - Options gamma positioning (GEX) regime.

Template v1.0.0. Concrete sketch: loads the fixture tape, runs a reference
implementation of the chapter's normative formula, and asserts causality,
F1-F5 fail-safes, and dual-estimator agreement.

Run: python3 -m pytest modules/tests/test_R020.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R020_tape.csv"
EXPECTED = FIX / "R020_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['long_gamma', 'neutral', 'short_gamma', 'undefined', 'warming', 'missing', 'invalid']
BOUNDS = (-1000000000000.0, 1000000000000.0)  # mathematical bounds of the indicator value (F2)
DUAL_MODE = "sign"  # rel | abs | sign | state
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

# ============================ R020 ============================
# RB-list: R020 Options gamma positioning (GEX) regime. Grok RB2 worked example
# (S=100): raw signed = -800k -2450k +3200k -2400k +1500k +450k = -$0.5M;
# with the xS^2x0.01 factor (=100): NetGEX = -$50M -> short-gamma/amplifying.
# [VERIFICATION FLAG: Grok's own figures are internally inconsistent as shown;
# the fixture uses the full formula and documents the flag.]
R020_CHAIN = [  # (strike, type, gamma, oi)
    (96, "P", 0.04, 2000), (98, "P", 0.07, 3500), (100, "C", 0.08, 4000),
    (100, "P", 0.08, 3000), (102, "C", 0.06, 2500), (104, "C", 0.03, 1500),
]
R020_S = 100.0

def r020_tape():
    hdr = ["bar", "event_ts", "asof_ts", "strike", "otype", "gamma", "oi", "spot"]
    rows = []
    for i, (k, t, gm, oi) in enumerate(R020_CHAIN, 1):
        ts = TS0 + (i - 1) * 60
        rows.append({"bar": i, "event_ts": ts, "asof_ts": ts + 60 * NS, "strike": k,
                     "otype": t, "gamma": gm, "oi": oi, "spot": R020_S})
    return hdr, rows

def _gex_row(r):
    s = 1.0 if r["otype"] == "C" else -1.0  # standard dealer convention [documented]
    return s * r["gamma"] * r["oi"] * 100 * r["spot"] ** 2 * 0.01

def _net_gex(rows):
    return sum(_gex_row(r) for r in rows)

def _r020_state(v):
    if not math.isfinite(v):
        return "undefined"
    return "long_gamma" if v > 0 else ("short_gamma" if v < 0 else "neutral")

def primary_indicator_r020(rows, cfg):
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN", "computed_at": 0, "vintage": "synthetic"}
    if any("gamma" not in r or "oi" not in r or "otype" not in r or "spot" not in r
           or r["gamma"] < 0 or r["oi"] < 0 or r["otype"] not in ("C", "P") or not r["spot"] > 0
           for r in rows):
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1].get("event_ts", 0), "vintage": "synthetic"}
    if len(rows) < 4:
        return {"value": float("nan"), "state": "warming", "module_state": "DEGRADED",
                "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}
    v = _net_gex(rows)
    return {"value": v, "state": _r020_state(v), "module_state": "OK",
            "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}

def second_estimator_r020(rows, cfg):
    # chain-completeness robustness: drop the farthest strike; sign must hold
    rows = list(rows)
    if len(rows) < 5:
        return {"value": float("nan"), "state": "undefined", "computed_at": 0}
    s0 = rows[0]["spot"]
    trimmed = sorted(rows, key=lambda r: abs(r["strike"] - s0))[:-1]
    v = _net_gex(trimmed)
    return {"value": v, "state": _r020_state(v), "computed_at": rows[-1]["event_ts"] if rows else 0}

F2_POISON_R020 = '''
F2_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1060, "strike": 100, "otype": "C",
     "gamma": 1e9, "oi": 1500, "spot": 100.0},
    {"bar": 2, "event_ts": 1060, "asof_ts": 1120, "strike": 100, "otype": "P",
     "gamma": 0.08, "oi": 3000, "spot": 100.0},
    {"bar": 3, "event_ts": 1120, "asof_ts": 1180, "strike": 102, "otype": "C",
     "gamma": 0.06, "oi": 2500, "spot": 100.0},
    {"bar": 4, "event_ts": 1180, "asof_ts": 1240, "strike": 104, "otype": "C",
     "gamma": 0.03, "oi": 1500, "spot": 100.0},
]  # gamma = 1e9 -> |NetGEX| ~ 1.5e14 > 1e12 bound -> F2
'''


primary_indicator = primary_indicator_r020
second_estimator = second_estimator_r020


F2_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1060, "strike": 100, "otype": "C",
     "gamma": 1e9, "oi": 1500, "spot": 100.0},
    {"bar": 2, "event_ts": 1060, "asof_ts": 1120, "strike": 100, "otype": "P",
     "gamma": 0.08, "oi": 3000, "spot": 100.0},
    {"bar": 3, "event_ts": 1120, "asof_ts": 1180, "strike": 102, "otype": "C",
     "gamma": 0.06, "oi": 2500, "spot": 100.0},
    {"bar": 4, "event_ts": 1180, "asof_ts": 1240, "strike": 104, "otype": "C",
     "gamma": 0.03, "oi": 1500, "spot": 100.0},
]  # gamma = 1e9 -> |NetGEX| ~ 1.5e14 > 1e12 bound -> F2


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
        return RegimeState("R020", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R020", "out_of_bounds", v, ESTIMATOR_VERSION,
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
        return RegimeState("R020", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R020", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R020", r["state"], v, ESTIMATOR_VERSION,
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
    assert rsv.regime_id == "R020"
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
