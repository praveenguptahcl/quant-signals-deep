"""Acceptance tests for R023 - Liquidation-cascade regime (crypto).

Template v1.0.0. Concrete sketch: loads the fixture tape, runs a reference
implementation of the chapter's normative formula (robust z on reported daily
liquidations, hysteresis entry/exit bands), and asserts causality, F1-F5
fail-safes, hysteresis transitions, gap/vintage-break edge cases, the cost
interface, and dual-estimator agreement.

Run: python3 -m pytest modules/tests/test_R023.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R023_tape.csv"
EXPECTED = FIX / "R023_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['normal', 'stress', 'cascade', 'undefined', 'warming',
                'missing', 'invalid', 'gap']
# F2: a z-score has no mathematical bounds; F2 catches garbage (inf/nan/absurd)
BOUNDS = (-1e4, 1e4)  # [default]
DUAL_MODE = "rel"  # rel | abs | sign | state
DUAL_TOL = 0.5
ESTIMATOR_VERSION = "1.1.0"
MAD_SCALE = 1.4826  # 1/Phi^-1(3/4), MAD->sigma consistency [documented]


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

# ============================ R023 ============================
# RB-list: R023 Liquidation-cascade regime (crypto). Grok RB3 worked example:
# reported $480M vs median30 $90M, MAD $25M -> robust z = (480-90)/(1.4826*25)
# = 390/37.065 = 10.523...; raw ratio 5.33x.
# Bars 30-36 pin the decay sequence: cascade entry, persistence under
# hysteresis, exit to stress, exit to normal.
R023_LIQ = [60, 70, 65, 80, 75, 90, 85, 95, 100, 90, 70, 85, 95, 110, 100,
            90, 80, 75, 85, 90, 95, 105, 100, 90, 85, 95, 100, 90, 80,
            480, 300, 200, 150, 130, 110, 105]

TS0 = 1788220800000000000  # fixture epoch [example]
DAY = 86400 * NS


def r023_tape():
    hdr = ["bar", "event_ts", "asof_ts", "reported_liq"]
    rows = []
    for i, v in enumerate(R023_LIQ, 1):
        ts = TS0 + (i - 1) * DAY
        rows.append({"bar": i, "event_ts": ts, "asof_ts": ts + 3600 * NS,
                     "reported_liq": v * 1e6})
    return hdr, rows


def _med(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _mad(xs, m):
    return _med([abs(x - m) for x in xs])


def _robust_z(x, hist):
    """Robust z of x vs trailing baseline hist (excludes current bar)."""
    m = _med(hist)
    mad = _mad(hist, m)
    scl = MAD_SCALE * mad
    if scl > 0:
        return (x - m) / scl
    if x > m:
        return float("inf")
    if x < m:
        return float("-inf")
    return 0.0


def transition(prev_state, z, cfg):
    """Hysteresis state machine (§R2.1). Entry bands are strict (>=);
    exit bands release below the exit threshold. Guard bands in between
    hold the prior state — this is what stops flapping."""
    if prev_state == "cascade":
        return "cascade" if z >= cfg.cascade_exit else "stress"
    if prev_state == "stress":
        if z >= cfg.cascade_entry:
            return "cascade"
        if z < cfg.stress_exit:
            return "normal"
        return "stress"
    # normal / warming / undefined: entries only
    if z >= cfg.cascade_entry:
        return "cascade"
    if z >= cfg.stress_entry:
        return "stress"
    return "normal"


def primary_indicator(rows, cfg, prev_state="normal"):
    """Reference indicator for the NEWEST bar in rows (causal).

    Handles: empty/missing input (F1), invalid values (F1), bar gaps
    (mask, no interpolation), vintage breaks (re-baseline), warm-up
    (DEGRADED), hysteresis transitions.
    """
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing",
                "module_state": "UNKNOWN", "computed_at": 0,
                "vintage": "synthetic"}
    # causal replay up to the newest bar
    baseline = []          # reported_liq in $M, masked at breaks/gaps
    prev = prev_state
    label = None
    for i, r in enumerate(rows):
        if r.get("vintage_break"):
            baseline = []
            prev = "normal"
        ts = r.get("event_ts", 0)
        v = r.get("reported_liq")
        if v is None or (isinstance(v, float) and math.isnan(v)) or not (v >= 0):
            label = (ts, float("nan"), "invalid", "UNKNOWN")
            continue
        if i > 0:
            dt = ts - rows[i - 1].get("event_ts", ts)
            if dt > 1.5 * CADENCE_S * NS:
                # gap: mask the bar, keep the value in the baseline,
                # never interpolate the missing bar's z
                baseline.append(v / 1e6)
                label = (ts, float("nan"), "gap", "UNKNOWN")
                continue
        baseline.append(v / 1e6)
        if len(baseline) < cfg.base_days:
            label = (ts, float("nan"), "warming", "DEGRADED")
            continue
        hist = baseline[-cfg.base_days:-1]  # trailing window, excludes current
        z = _robust_z(v / 1e6, hist)
        prev = transition(prev, z, cfg)
        label = (ts, z, prev, "OK")
    ts, z, state, mstate = label
    return {"value": z, "state": state, "module_state": mstate,
            "computed_at": ts, "vintage": "synthetic"}


def second_estimator(rows, cfg):
    """Verifier: robust z on a shorter verify_base_days baseline."""
    rows = list(rows)
    vals = [r["reported_liq"] / 1e6 for r in rows[:-1]
            if r.get("reported_liq") is not None]
    hist = vals[-cfg.verify_base_days:]
    if len(hist) < cfg.verify_base_days:
        return {"value": float("nan"), "state": "undefined", "computed_at": 0}
    z = _robust_z(rows[-1]["reported_liq"] / 1e6, hist)
    return {"value": z, "state": "n/a", "computed_at": rows[-1]["event_ts"]}


def cost_adjustment(rsv, base):
    """§R5 reference: regime state -> cost-function adjustment.

    rsv: dict(state, module_state). base: T-module COST-block dict.
    Cascade = hard veto (no cost curve survives a mechanical unwind).
    Stress = multiplicative cost widening + halved size. UNKNOWN is
    restrictive. borrow_mult stays 1.0: perps have no stock-borrow leg;
    funding is priced in the T-module cost block.
    """
    adj = dict(base)
    st = rsv.get("state")
    if st == "cascade":
        adj["trade_ok"] = False
        adj["size_mult"] = 0.0
        adj["reason"] = "R023 cascade - mechanical unwind; stand aside"
    elif st == "stress":
        adj["trade_ok"] = True
        adj["size_mult"] = 0.5          # [example]
        adj["spread_mult"] = 2.0        # [example] spreads widen
        adj["impact_mult"] = 3.0        # [example] impact blows out
        adj["slippage_buffer_bps"] = 50  # [example]
        adj["reason"] = "R023 stress - halve size, widen cost"
    else:  # normal
        adj["trade_ok"] = True
        adj["size_mult"] = 1.0          # [default]
        adj["spread_mult"] = 1.0        # [default]
        adj["impact_mult"] = 1.0        # [default]
        adj["fee_mult"] = 1.0           # [default] fees do not scale
        adj["borrow_mult"] = 1.0        # [default] no borrow leg in perps
        adj["reason"] = "R023 normal"
    if rsv.get("module_state") == "UNKNOWN":
        adj["trade_ok"] = False
        adj["reason"] = "R023 UNKNOWN - restrictive default"
    return adj


F2_POISON_TAPE = [
    {"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i,
     "reported_liq": 90e6}
    for i in range(29)
] + [{"bar": 30, "event_ts": 1029, "asof_ts": 1030, "reported_liq": 1e12}]
# degenerate baseline (MAD = 0) + $1T print -> z = +inf -> F2


primary_indicator = primary_indicator
second_estimator = second_estimator


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
    state: str            # regime label, e.g. "cascade"
    value: float          # indicator value (robust z)
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


@dataclass
class Config:
    base_days: int = 30
    stress_entry: float = 3.0
    stress_exit: float = 2.5
    cascade_entry: float = 6.0
    cascade_exit: float = 4.5
    verify_base_days: int = 25
    dual_tol: float = 0.5


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
        return RegimeState("R023", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: garbage bounds (a z-score itself is unbounded, so this only
    # catches degenerate/invalid numerics)
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R023", "out_of_bounds", v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           "UNKNOWN")
    # F3: dual-estimator agreement (rel mode on values)
    s = second_estimator(rows, cfg)
    if DUAL_MODE == "state":
        agree = (r["state"] == s["state"]) or (
            DUAL_TOL is not None and math.isfinite(v) and math.isfinite(s["value"])
            and abs(v - s["value"]) <= DUAL_TOL)
    else:
        agree = within_tolerance(v, s["value"], DUAL_MODE, DUAL_TOL)
    if not agree:
        return RegimeState("R023", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           "UNKNOWN")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R023", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R023", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = Config()
    for i in range(len(evs)):
        rsv = detect(evs[: i + 1], cfg)
        want = exp[i + 1]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(rsv.value), i
        elif math.isinf(wv):
            assert math.isinf(rsv.value) and (rsv.value > 0) == (wv > 0), i
        else:
            assert abs(rsv.value - wv) < TOL, (i, rsv.value, wv)
        assert rsv.state == want["exp_state"], (i, rsv.state, want["exp_state"])
        assert rsv.computed_at == int(want["exp_computed_at"]), i
        assert rsv.module_state == want["exp_module_state"], i


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R023"
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
    neg = [{"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i,
            "reported_liq": 90e6} for i in range(30)]
    neg.append({"bar": 31, "event_ts": 1030, "asof_ts": 1031,
                "reported_liq": -5e6})  # negative print: invalid, never clamped
    assert detect(neg, Config()).module_state == "UNKNOWN"


def test_F2_bounds_violation_unknown():
    rsv = detect(F2_POISON_TAPE, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = tape()
    orig = mod.second_estimator
    p0 = primary_indicator(evs, Config())["value"]
    bad_val = -1e9 if (p0 >= 0) else 1e9  # opposite sign: disagrees in rel/abs/state modes
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
    for i in range(29, len(evs)):  # labeled bars only
        sub = evs[: i + 1]
        r = primary_indicator(sub, cfg)
        s = second_estimator(sub, cfg)
        if DUAL_MODE == "state":
            ok = (r["state"] == s["state"]) or (
                DUAL_TOL is not None and abs(r["value"] - s["value"]) <= DUAL_TOL)
            assert ok, (i, r, s)
        else:
            assert within_tolerance(r["value"], s["value"], DUAL_MODE, DUAL_TOL), (i, r, s)
    assert detect(evs, cfg).module_state == "OK"


def test_hysteresis_transition_table():
    """§R2.1 pinning: guard bands hold the prior state; entries are strict."""
    cfg = Config()
    cases = [
        # (prev, z, expected)
        ("normal", 2.99, "normal"), ("normal", 3.0, "stress"),
        ("normal", 5.99, "stress"), ("normal", 6.0, "cascade"),
        ("stress", 2.49, "normal"), ("stress", 2.5, "stress"),
        ("stress", 2.7, "stress"), ("stress", 5.9, "stress"),
        ("stress", 6.0, "cascade"),
        ("cascade", 4.49, "stress"), ("cascade", 4.5, "cascade"),
        ("cascade", 5.0, "cascade"), ("cascade", 6.5, "cascade"),
    ]
    for prev, z, want in cases:
        assert transition(prev, z, cfg) == want, (prev, z)


def test_cascade_decay_sequence():
    """Bars 30-36 pin the full lifecycle: entry -> persistence under
    hysteresis -> exit to stress -> exit to normal (no flapping)."""
    evs = tape()
    cfg = Config()
    states = [detect(evs[: i + 1], cfg).state for i in range(29, len(evs))]
    assert states[0] == "cascade", states           # bar 30: entry
    assert states[-1] == "normal", states            # bar 36: fully exited
    assert "stress" in states, states                 # exit passes through stress
    # hysteresis: once in cascade, a sub-entry z still reads cascade
    assert states[1] == "cascade" and states[2] == "cascade", states
    # no re-entry after exit
    first_normal = states.index("normal")
    assert all(s == "normal" for s in states[first_normal:]), states


def test_gap_in_tape_unknown():
    """A missing bar masks to UNKNOWN (never interpolated); the next good
    bar recovers causally."""
    evs = tape()
    cfg = Config()
    sub = evs[:4] + evs[5:]          # drop bar 5 -> 2-day jump in event_ts
    gap_bar = detect(sub[:5], cfg)   # newest bar sits after the gap
    assert gap_bar.module_state == "UNKNOWN" and gap_bar.state == "gap"
    full = detect(sub, cfg)          # 35 bars, gap masked in baseline
    assert full.module_state == "OK", (full.state, full.module_state)


def test_vintage_break_rebaselines():
    """Symbol redenomination / contract migration (the crypto analogue of a
    corporate action): vintage_break restarts the baseline; the module is
    DEGRADED until base_days post-break bars exist."""
    cfg = Config()
    base = [{"bar": i + 1, "event_ts": TS0 + i * DAY,
             "asof_ts": TS0 + i * DAY + 3600 * NS, "reported_liq": 90e6}
            for i in range(60)]
    base[30] = dict(base[30], vintage_break=True)   # break at bar 31
    late = detect(base, cfg)                          # 30 post-break bars
    assert late.module_state == "OK", (late.state, late.module_state)
    early = detect(base[:40], cfg)                    # only 10 post-break bars
    assert early.module_state == "DEGRADED" and early.state == "warming"


def test_negative_z_within_bounds():
    """A quiet day (below-median liquidations) gives a finite negative z and
    stays OK/normal — F2 must not fire on legitimate negative values."""
    cfg = Config()
    cyc = [86, 88, 90, 92, 94]  # non-degenerate baseline: median 90, MAD 2
    rows = [{"bar": i + 1, "event_ts": TS0 + i * DAY,
             "asof_ts": TS0 + i * DAY + 3600 * NS,
             "reported_liq": cyc[i % 5] * 1e6}
            for i in range(30)]
    rows.append({"bar": 31, "event_ts": TS0 + 30 * DAY,
                 "asof_ts": TS0 + 30 * DAY + 3600 * NS, "reported_liq": 70e6})
    rsv = detect(rows, cfg)
    assert rsv.module_state == "OK", (rsv.state, rsv.module_state)
    assert rsv.value < 0 and math.isfinite(rsv.value)
    assert rsv.state == "normal"


def test_cost_adjustment_states():
    base = {"spread_bps": 5.0, "impact_bps": 10.0}
    c = cost_adjustment({"state": "cascade", "module_state": "OK"}, base)
    assert c["trade_ok"] is False and c["size_mult"] == 0.0
    s = cost_adjustment({"state": "stress", "module_state": "OK"}, base)
    assert s["trade_ok"] is True
    assert s["size_mult"] == 0.5 and s["spread_mult"] == 2.0
    assert s["impact_mult"] == 3.0 and s["slippage_buffer_bps"] == 50
    n = cost_adjustment({"state": "normal", "module_state": "OK"}, base)
    assert n["trade_ok"] is True and n["size_mult"] == 1.0
    assert n["spread_mult"] == 1.0 and n["fee_mult"] == 1.0
    assert n["borrow_mult"] == 1.0
    u = cost_adjustment({"state": "normal", "module_state": "UNKNOWN"}, base)
    assert u["trade_ok"] is False  # restrictive default
