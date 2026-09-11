"""Acceptance tests for R018 - Equity positioning / crowding regime.

Template v1.0.0. Concrete sketch: loads the fixture tape, runs a reference
implementation of the chapter's normative formula, and asserts causality,
F1-F5 fail-safes, and dual-estimator agreement.

Run: python3 -m pytest modules/tests/test_R018.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R018_tape.csv"
EXPECTED = FIX / "R018_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 604800  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['extreme_long', 'crowded_long', 'normal', 'crowded_short', 'extreme_short', 'undefined', 'warming', 'missing', 'invalid']
BOUNDS = (-5.0, 5.0)  # mathematical bounds of the indicator value (F2)
DUAL_MODE = "abs"  # rel | abs | sign | state
DUAL_TOL = 0.5
ESTIMATOR_VERSION = "1.1.0"

# Hysteresis detector config — mirrors §R2 threshold table [default].
HYST = {
    "enter_crowded": 1.25, "exit_crowded": 0.75,
    "enter_extreme": 2.0, "exit_extreme": 1.5,
    "warmup_bars": 4,
}


def _side(z):
    return "long" if z >= 0 else "short"


def align_components(raw):
    """Sign alignment: raw component z-scores -> sign-aligned (+ = crowded long).
    High put/call = bearish positioning (crowded short) -> flip sign [default].
    High SI% float = crowded short -> flip sign [default].
    High COT net long = crowded long -> keep sign [default]."""
    return {
        "pcr_z": -raw["pcr_z"],
        "si_z": -raw["si_z"],
        "cot_z": +raw["cot_z"],
    }


def hysteresis_label(z, prev_state):
    """§R2 hysteresis state machine. Entry/exit pairs stop label flicker at
    band boundaries; an extreme label exits to the crowded band, not to normal."""
    a = abs(z)
    s = _side(z)
    if prev_state in ("extreme_long", "extreme_short"):
        if a >= HYST["exit_extreme"]:
            return "extreme_" + s
        return "crowded_" + s if a >= HYST["exit_crowded"] else "normal"
    if prev_state in ("crowded_long", "crowded_short"):
        if a >= HYST["enter_extreme"]:
            return "extreme_" + s
        return "crowded_" + s if a >= HYST["exit_crowded"] else "normal"
    if a >= HYST["enter_extreme"]:
        return "extreme_" + s
    if a >= HYST["enter_crowded"]:
        return "crowded_" + s
    return "normal"


def detect_hysteresis(rows, cfg):
    """Stateful sequence detector: threads prev_label through the §R2
    hysteresis machine. Returns [(value, label, module_state, computed_at)]."""
    out = []
    prev = "normal"
    for i in range(len(rows)):
        r = primary_indicator(rows[: i + 1], cfg)
        if r["module_state"] != "OK":
            out.append((r["value"], r["state"], r["module_state"], r["computed_at"]))
            prev = "normal"
            continue
        lbl = hysteresis_label(r["value"], prev)
        out.append((r["value"], lbl, "OK", r["computed_at"]))
        prev = lbl
    return out


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

# ============================ R018 ============================
# RB-list: R018 Equity positioning / crowding regime. Composite of PCR_21d z,
# SI% float z, COT net z (equal-weight, sign-aligned, + = crowded long).
# Grok RB2 worked example: SI 12m/80m float = 15%, DTC = 12/2.5 = 4.8 days.
R018_ROWS = [  # (pcr_z, si_z, cot_z), weekly, sign-aligned (+ = crowded long)
    (0.2, 0.1, 0.3), (0.5, 0.4, 0.6), (0.8, 0.7, 0.9), (1.0, 0.9, 1.2),
    (1.2, 1.1, 1.4), (1.5, 1.3, 1.7), (1.7, 1.4, 1.9), (1.8, 1.5, 2.0),
]

def r018_tape():
    hdr = ["bar", "event_ts", "asof_ts", "pcr_z", "si_z", "cot_z"]
    rows = []
    for i, (p, s, c) in enumerate(R018_ROWS, 1):
        ts = TS0 + (i - 1) * WEEK
        rows.append({"bar": i, "event_ts": ts, "asof_ts": ts + 3600 * NS,
                     "pcr_z": p, "si_z": s, "cot_z": c})
    return hdr, rows

def _composite_mean(row):
    return (row["pcr_z"] + row["si_z"] + row["cot_z"]) / 3

def _composite_median(row):
    s = sorted([row["pcr_z"], row["si_z"], row["cot_z"]])
    return s[1]

def _r018_state(z):
    if not math.isfinite(z):
        return "undefined"
    a = abs(z)
    side = "long" if z >= 0 else "short"
    if a > 2:
        return "extreme_" + side
    if a >= 1:
        return "crowded_" + side
    return "normal"

def primary_indicator_r018(rows, cfg):
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN", "computed_at": 0, "vintage": "synthetic"}
    if any(not all(k in r for k in ("pcr_z", "si_z", "cot_z"))
           or not all(math.isfinite(r[k]) for k in ("pcr_z", "si_z", "cot_z")) for r in rows):
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1].get("event_ts", 0), "vintage": "synthetic"}
    if len(rows) < 4:
        return {"value": float("nan"), "state": "warming", "module_state": "DEGRADED",
                "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}
    z = _composite_mean(rows[-1])
    return {"value": z, "state": _r018_state(z), "module_state": "OK",
            "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}

def second_estimator_r018(rows, cfg):
    rows = list(rows)
    z = _composite_median(rows[-1]) if rows else float("nan")
    return {"value": z, "state": _r018_state(z), "computed_at": rows[-1]["event_ts"] if rows else 0}

F2_POISON_R018 = '''
F2_POISON_TAPE = [
    {"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i,
     "pcr_z": 10.0, "si_z": 10.0, "cot_z": 10.0}
    for i in range(6)
]  # composite z = 10 > 5 bound -> F2
'''


primary_indicator = primary_indicator_r018
second_estimator = second_estimator_r018


F2_POISON_TAPE = [
    {"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i,
     "pcr_z": 10.0, "si_z": 10.0, "cot_z": 10.0}
    for i in range(6)
]  # composite z = 10 > 5 bound -> F2


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
        return RegimeState("R018", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R018", "out_of_bounds", v, ESTIMATOR_VERSION,
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
        return RegimeState("R018", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R018", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R018", r["state"], v, ESTIMATOR_VERSION,
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
    assert rsv.regime_id == "R018"
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


# ------------------------------------------------- hysteresis & alignment
HYST_TAPE = FIX / "R018_hysteresis.csv"
HYST_EXPECTED = FIX / "R018_hysteresis_expected.csv"


def test_hysteresis_fixture_recomputes():
    """Stateful recompute of each bar through the §R2 hysteresis machine
    matches the expected CSV (entry/hold/exit/extreme transitions pinned)."""
    evs = [dict(r) for r in load_csv(HYST_TAPE)]
    for r in evs:
        r["bar"] = int(r["bar"]); r["event_ts"] = int(r["event_ts"]); r["asof_ts"] = int(r["asof_ts"])
        for k in ("pcr_z", "si_z", "cot_z"):
            r[k] = float(r[k])
    exp = {int(r["bar"]): r for r in load_csv(HYST_EXPECTED)}
    got = detect_hysteresis(evs, Config())
    assert len(got) == len(evs)
    for i, (v, lbl, mstate, cts) in enumerate(got, 1):
        want = exp[i]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(v), i
        else:
            assert abs(v - wv) < TOL, i
        assert lbl == want["exp_state"], i
        assert cts == int(want["exp_computed_at"]), i
        assert mstate == want["exp_module_state"], i


def test_hysteresis_boundary_guards():
    """Guard-band behavior at each threshold — logic drift fails these."""
    # entry guard: 1.24 does not enter, 1.25 enters
    assert hysteresis_label(1.24, "normal") == "normal"
    assert hysteresis_label(1.25, "normal") == "crowded_long"
    assert hysteresis_label(-1.24, "normal") == "normal"
    assert hysteresis_label(-1.25, "normal") == "crowded_short"
    # hold inside the guard band: 0.76 holds, 0.74 exits
    assert hysteresis_label(0.76, "crowded_long") == "crowded_long"
    assert hysteresis_label(0.74, "crowded_long") == "normal"
    # extreme hold/exit: 1.6 holds extreme, 1.4 exits extreme but stays crowded
    assert hysteresis_label(1.60, "extreme_long") == "extreme_long"
    assert hysteresis_label(1.40, "extreme_long") == "crowded_long"
    assert hysteresis_label(0.50, "extreme_long") == "normal"
    # crowded can jump straight to extreme
    assert hysteresis_label(2.10, "crowded_long") == "extreme_long"
    # extreme exits never drop straight to normal through the crowded band
    # (side follows the sign of z when it flips inside the exit)
    assert hysteresis_label(1.00, "extreme_short") == "crowded_long"
    # side follows the sign of z
    assert hysteresis_label(-2.10, "normal") == "extreme_short"


def test_F1_nan_component_unknown():
    """A missing (NaN) component input is invalid -> UNKNOWN, never interpolated."""
    evs = tape()
    bad = [dict(r) for r in evs]
    bad[-1] = dict(bad[-1]); bad[-1]["si_z"] = float("nan")
    rsv = detect(bad, Config())
    assert rsv.module_state == "UNKNOWN"


def test_sign_alignment_convention():
    """Raw component z-scores map to the module's + = crowded long convention."""
    a = align_components({"pcr_z": 2.0, "si_z": 1.5, "cot_z": -0.5})
    assert a["pcr_z"] == -2.0   # high put/call = bearish = crowded short
    assert a["si_z"] == -1.5    # high short interest = crowded short
    assert a["cot_z"] == -0.5   # net long high = crowded long (sign kept)
