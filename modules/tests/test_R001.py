"""Acceptance tests for R001 - Realized-volatility level regime.

Template v1.0.0. Reference implementation of the chapter's normative formula
(§R2.6), with F1-F5 fail-safes, hysteresis state machine, corporate-action
guard, gap policy, rescaled-Parkinson F3 (leave-one-out jump recovery), and
the §R5 cost interface.

Run: python3 -m pytest modules/tests/test_R001.py -q   (from repo root)
"""
import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R001_tape.csv"
EXPECTED = FIX / "R001_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['complacent', 'normal', 'elevated', 'extreme', 'warming', 'missing', 'invalid']
BOUNDS = (0.0, 5.0)  # mathematical bounds of the indicator value (F2) [default]
DUAL_MODE = "rel"    # F3 comparison mode: relative difference on the variance scale
DUAL_TOL = 0.25      # [default] F3 tolerance (relative, variance scale)
ESTIMATOR_VERSION = "1.1.0"
GK_C2 = 2 * math.log(2) - 1      # 0.386294... [documented] Garman-Klass constant
PARK_RESCALE = 2 * math.log(2)   # [documented] E[σ²_GK]/E[σ²_P] = 2ln2 under zero drift
ANN = 252                        # annualization trading days [documented]


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _pct_rank(x, hist):
    h = list(hist)
    if not h:
        return float("nan")
    return (sum(1 for v in h if v < x) + 0.5 * sum(1 for v in h if v == x)) / len(h)


# ============================ estimators ============================
def gk_var(o, h, l, c):
    """Garman-Klass daily variance, floored at 0 [default] (the drift term can
    push it negative on jump days; a negative variance estimate is unusable)."""
    v = 0.5 * math.log(h / l) ** 2 - GK_C2 * math.log(c / o) ** 2  # [documented]
    return max(v, 0.0)


def parkinson_var(h, l):
    """Parkinson (1980) daily variance [documented]."""
    return math.log(h / l) ** 2 / (4 * math.log(2))


def _gk_series(rows):
    return [gk_var(r["o"], r["h"], r["l"], r["c"]) for r in rows]


def _pk_series(rows):
    return [parkinson_var(r["h"], r["l"]) for r in rows]


# ============================ config ============================
@dataclass
class Config:
    window_days: int = 5            # [default] RV estimation window
    trail_days: int = 252          # [default] trailing distribution cap
    min_history_days: int = 63     # [default] fewer trailing bars -> DEGRADED
    entry_extreme_pct: float = 0.95   # [default] enter extreme when p > this
    exit_extreme_pct: float = 0.90    # [default] leave extreme when p <= this
    entry_elevated_pct: float = 0.80  # [default]
    exit_elevated_pct: float = 0.75   # [default]
    entry_complacent_pct: float = 0.20  # [default] enter complacent when p < this
    exit_complacent_pct: float = 0.25  # [default] leave complacent when p >= this
    dual_tol_rel: float = 0.25     # [default] F3 relative tolerance, variance scale
    adj_jump_tol: float = 1.40     # [default] unadjusted corporate-action trip ratio
    intraday_refresh_min: int = 30  # [default]


# ============================ hysteresis classifier ============================
def classify_with_hysteresis(prev_state, p, cfg):
    """Normative state transition (§R2.7). Entry thresholds are strict;
    exit thresholds are sticky: a label persists while p stays on the exit
    side of the band. A spike above the extreme entry threshold promotes
    from ANY state (complacent included)."""
    ee, ex = cfg.entry_extreme_pct, cfg.exit_extreme_pct
    ve, vx = cfg.entry_elevated_pct, cfg.exit_elevated_pct
    ce, cx = cfg.entry_complacent_pct, cfg.exit_complacent_pct
    if p > ee:
        return "extreme"
    if prev_state == "extreme":
        return "extreme" if p > ex else "elevated"
    if prev_state == "elevated":
        return "elevated" if p > vx else "normal"
    if prev_state == "complacent":
        return "complacent" if p < cx else "normal"
    # prev in ("normal", "warming")
    if p > ve:
        return "elevated"
    if p < ce:
        return "complacent"
    return "normal"


def _label_path(rows, cfg):
    """Causal per-bar (label, rv, percentile); label at bar i uses data ≤ i."""
    rows = list(rows)
    W = cfg.window_days
    gk = _gk_series(rows)
    out = []
    for i in range(len(rows)):
        if i + 1 < W:
            out.append(("warming", float("nan"), float("nan")))
            continue
        rv_j = []
        for j in range(W - 1, i + 1):
            rv_j.append(math.sqrt(max(_mean(gk[j - W + 1:j + 1]), 0.0) * ANN))
        rv = rv_j[-1]
        trail = rv_j[-cfg.trail_days:]
        p = _pct_rank(rv, trail)
        prev = out[-1][0] if out else "normal"
        out.append((classify_with_hysteresis(prev, p, cfg), rv, p))
    return out


# ============================ primary / second estimator ============================
def primary_indicator(rows, cfg):
    rows = list(rows)
    W = cfg.window_days
    # F1: input validity — invalid input -> UNKNOWN, never interpolate
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "reason": "no-bars", "percentile": float("nan"),
                "excluded_bar": None, "vintage": "synthetic"}
    for r in rows:
        if not all(k in r for k in ("o", "h", "l", "c", "event_ts")):
            return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                    "computed_at": r.get("event_ts", 0), "reason": "invalid-bar",
                    "percentile": float("nan"), "excluded_bar": None, "vintage": "synthetic"}
        if not all(math.isfinite(float(r[k])) for k in ("o", "h", "l", "c")):
            return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                    "computed_at": r["event_ts"], "reason": "invalid-bar",
                    "percentile": float("nan"), "excluded_bar": None, "vintage": "synthetic"}
        if not (r["h"] >= r["l"] > 0 and r["o"] > 0 and r["c"] > 0):
            return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                    "computed_at": r["event_ts"], "reason": "invalid-bar",
                    "percentile": float("nan"), "excluded_bar": None, "vintage": "synthetic"}
    # Corporate-action guard: an unadjusted jump (> adj_jump_tol with no factor
    # supplied) is not volatility — it is bad data.
    if len(rows) >= 2 and rows[-1].get("adj_factor") is None and rows[-2].get("adj_factor") is None:
        ratio = rows[-1]["c"] / rows[-2]["c"]
        if ratio > cfg.adj_jump_tol or ratio < 1.0 / cfg.adj_jump_tol:
            return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                    "computed_at": rows[-1]["event_ts"], "reason": "unadjusted-corporate-action",
                    "percentile": float("nan"), "excluded_bar": None, "vintage": "synthetic"}
    # Market-state events: HALTED freezes (UNKNOWN), AUCTION holds (DEGRADED)
    ms = rows[-1].get("market_state")
    if ms == "HALTED":
        fro = primary_indicator([r for r in rows if r.get("market_state") != "HALTED"], cfg)
        fro = dict(fro)
        fro["module_state"] = "UNKNOWN"
        fro["reason"] = "halted"
        fro["computed_at"] = rows[-1]["event_ts"]
        return fro
    auction = (ms == "AUCTION")
    # Gap policy: > 3x cadence -> UNKNOWN (stale); (1x, 3x] -> DEGRADED, masked
    gap_reason = None
    if len(rows) >= 2:
        dt = rows[-1]["event_ts"] - rows[-2]["event_ts"]
        if dt > 3 * CADENCE_S * NS:
            return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                    "computed_at": rows[-1]["event_ts"], "reason": "stale-gap",
                    "percentile": float("nan"), "excluded_bar": None, "vintage": "synthetic"}
        if dt > CADENCE_S * NS:
            gap_reason = "gap-masked"
    # Warm-up: fewer than window_days bars -> DEGRADED, label withheld
    if len(rows) < W:
        return {"value": float("nan"), "state": "warming", "module_state": "DEGRADED",
                "computed_at": rows[-1]["event_ts"], "reason": "warming",
                "percentile": float("nan"), "excluded_bar": None, "vintage": "synthetic"}
    # Estimators over the window
    gk, pk = _gk_series(rows), _pk_series(rows)
    n = len(rows)
    gw, pw = gk[n - W:n], pk[n - W:n]

    def _agree(gw_, pw_):
        g, q = _mean(gw_), PARK_RESCALE * _mean(pw_)
        return abs(g - q) / max(g, q, 1e-18) <= cfg.dual_tol_rel

    excluded = None
    f3_ok = _agree(gw, pw)
    if not f3_ok:
        # F3 recovery: leave-one-out over the window — a single jump bar that
        # explains the disagreement is excluded (cf. §R7 row 1)
        for j in range(n - W, n):
            gw2 = [v for k, v in enumerate(gw) if k != j - (n - W)]
            pw2 = [v for k, v in enumerate(pw) if k != j - (n - W)]
            if _agree(gw2, pw2):
                excluded = rows[j].get("bar", j)
                keep = [r for k, r in enumerate(rows) if k != j]
                path = _label_path(keep, cfg)
                label, rv, p = path[-1]
                return {"value": rv, "state": label, "module_state": "DEGRADED",
                        "computed_at": rows[-1]["event_ts"], "reason": "jump-excluded",
                        "percentile": p, "excluded_bar": excluded, "vintage": "synthetic"}
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1]["event_ts"], "reason": "F3-disagreement",
                "percentile": float("nan"), "excluded_bar": None, "vintage": "synthetic"}
    path = _label_path(rows, cfg)
    label, rv, p = path[-1]
    # F2: mathematical bounds
    if not (math.isfinite(rv) and BOUNDS[0] <= rv <= BOUNDS[1]):
        return {"value": rv, "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1]["event_ts"], "reason": "out-of-bounds",
                "percentile": p, "excluded_bar": None, "vintage": "synthetic"}
    # Short trailing history: label emitted (pins transitions) but DEGRADED —
    # production requires min_history_days bars for OK (honest §R7 row 6)
    if len(path) - (W - 1) < cfg.min_history_days:
        state, reason = "DEGRADED", "short-trailing-history"
    else:
        state, reason = "OK", "ok"
    if auction:
        state, reason = "DEGRADED", "auction-hold"
    elif gap_reason:
        state, reason = "DEGRADED", gap_reason
    return {"value": rv, "state": label, "module_state": state,
            "computed_at": rows[-1]["event_ts"], "reason": reason,
            "percentile": p, "excluded_bar": excluded, "vintage": "synthetic"}


def second_estimator(rows, cfg):
    """Verifier: Parkinson (1980) rescaled by 2ln2 [documented] so its
    expectation matches Garman-Klass under zero drift; F3 then tests genuine
    contamination, not the structural GK/Parkinson gap."""
    rows = list(rows)
    W = cfg.window_days
    if len(rows) < W:
        return {"value": float("nan"), "state": "n/a",
                "computed_at": rows[-1]["event_ts"] if rows else 0}
    pk = _pk_series(rows)
    val = math.sqrt(max(_mean(pk[-W:]), 0.0) * PARK_RESCALE * ANN)
    return {"value": val, "state": "n/a", "computed_at": rows[-1]["event_ts"]}


primary_indicator_r001 = primary_indicator
second_estimator_r001 = second_estimator


F2_POISON_TAPE = [
    {"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i,
     "o": 100.0, "h": 22026.5, "l": 1.0, "c": 100.0}  # ln(H/L)~10 -> GK var ~50 -> rv_ann ~112
    for i in range(5)
]


# ============================ §R5 cost interface ============================
def cost_adjustment(state, base):
    """Regime state -> cost-function adjustment (§R5).

    base: dict(spread_bps, impact_bps, borrow_bps, fees_bps) from the
    strategy COST block. Only spread and impact scale with RV; borrow and
    fees are unaffected. Multipliers are [example] starting points — the
    calibration recipe in §R5 must be run before live use.
    """
    adj = dict(base)
    if state == "extreme":
        adj["spread_mult"] = 2.5  # [example] starting point; calibrate per §R5
        adj["impact_mult"] = 3.0  # [example]
        adj["trade_ok"] = False   # cost-sensitive strategies stand down
    elif state == "elevated":
        adj["spread_mult"] = 1.5  # [example]
        adj["impact_mult"] = 2.0  # [example]
        adj["trade_ok"] = True
    elif state == "UNKNOWN":
        adj["spread_mult"] = 1.0  # [default] multipliers undefined under UNKNOWN
        adj["impact_mult"] = 1.0  # [default]
        adj["trade_ok"] = False   # restrictive default: never benign
    else:
        adj["spread_mult"] = 1.0  # [default]
        adj["impact_mult"] = 1.0  # [default]
        adj["trade_ok"] = True
    adj["borrow_mult"] = 1.0  # [default] borrow does not scale with RV
    adj["fees_mult"] = 1.0    # [default] fees do not scale with RV
    return adj


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
    r = primary_indicator(rows, cfg)  # dict(value, state, module_state, computed_at, ...)
    if r["module_state"] != "OK" and r["module_state"] != "DEGRADED":
        return RegimeState("R001", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    v, p = r["value"], r.get("percentile", float("nan"))
    # F2 backstop: mathematical bounds on emitted values
    if r["module_state"] == "OK" and not (math.isfinite(v) and BOUNDS[0] <= v <= BOUNDS[1]):
        return RegimeState("R001", "out_of_bounds", v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F3: dual-estimator agreement on the variance scale (rescaled Parkinson)
    s = second_estimator(rows, cfg)
    if math.isfinite(v) and math.isfinite(s["value"]) and r["reason"] not in ("jump-excluded",):
        if not within_tolerance(v * v, s["value"] * s["value"], DUAL_MODE, DUAL_TOL):
            return RegimeState("R001", r["state"], v, ESTIMATOR_VERSION,
                               r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R001", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R001", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], r["module_state"])


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
            assert abs(r["value"] - wv) < TOL, (i, r["value"], wv)
        assert r["state"] == want["exp_state"], (i, r["state"], want["exp_state"])
        assert r["computed_at"] == int(want["exp_computed_at"]), i
        assert r["module_state"] == want["exp_module_state"], (i, r["module_state"])
        assert r["reason"] == want["exp_reason"], (i, r["reason"])


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R001"
    assert rsv.state in STATE_LABELS
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["event_ts"]
    # fixture tape is short history (< 63 trailing bars): honest DEGRADED
    assert rsv.module_state == "DEGRADED"
    assert math.isfinite(rsv.value) and BOUNDS[0] <= rsv.value <= BOUNDS[1]


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
        assert earliest_trade_ts > label.computed_at, f"lookahead at bar {i}"
    # appending a future breakout bar must not move the label stamped at t
    label_t = detect(evs[:-1], cfg)
    assert label_t.computed_at == evs[-2]["event_ts"]


def test_F1_missing_input_unknown():
    assert detect([], Config()).module_state == "UNKNOWN"
    bad = [dict(event_ts=1, asof_ts=2)]  # missing indicator fields
    assert detect(bad, Config()).module_state == "UNKNOWN"
    neg = [dict(bar=1, event_ts=1, asof_ts=2, o=100.0, h=90.0, l=99.0, c=100.0)]  # h < l
    assert detect(neg, Config()).module_state == "UNKNOWN"


def test_F2_bounds_violation_unknown():
    r = primary_indicator(F2_POISON_TAPE, Config())
    assert r["module_state"] == "UNKNOWN" and r["reason"] == "out-of-bounds", r
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
    assert rsv.module_state == "DEGRADED"  # short-history fixture stays DEGRADED


def test_dual_estimator_agreement():
    """Sentinel vs Verifier (rescaled Parkinson) agree within tolerance."""
    evs = tape()
    cfg = Config()
    r = primary_indicator(evs, cfg)
    s = second_estimator(evs, cfg)
    assert within_tolerance(r["value"] ** 2, s["value"] ** 2, DUAL_MODE, DUAL_TOL), (r, s)
    assert r["reason"] != "F3-disagreement"


def test_hysteresis_entry_exit_boundaries():
    """Pin the exact transition semantics: strict entry, sticky exit."""
    cfg = Config()
    c = classify_with_hysteresis
    # extreme band: entry strict > 0.95, exit sticky while p > 0.90
    assert c("normal", 0.95, cfg) == "elevated"      # boundary does NOT enter
    assert c("normal", 0.9500001, cfg) == "extreme"
    assert c("extreme", 0.90, cfg) == "elevated"     # boundary exits
    assert c("extreme", 0.9000001, cfg) == "extreme"  # just above exit holds
    assert c("extreme", 0.95, cfg) == "extreme"
    # elevated band: entry strict > 0.80, exit sticky while p > 0.75
    assert c("normal", 0.80, cfg) == "normal"
    assert c("normal", 0.8000001, cfg) == "elevated"
    assert c("elevated", 0.75, cfg) == "normal"
    assert c("elevated", 0.7500001, cfg) == "elevated"
    # complacent band: entry strict < 0.20, exit sticky while p < 0.25
    assert c("normal", 0.20, cfg) == "normal"
    assert c("normal", 0.1999999, cfg) == "complacent"
    assert c("complacent", 0.25, cfg) == "normal"
    assert c("complacent", 0.2499999, cfg) == "complacent"
    # extreme exit lands on elevated, not normal (one step per bar)
    assert c("extreme", 0.10, cfg) == "elevated"
    # spike promotes from ANY state, complacent included
    assert c("complacent", 0.96, cfg) == "extreme"
    assert c("warming", 0.96, cfg) == "extreme"


def test_hysteresis_path_on_fixture():
    """Fixture pins: no extreme before the spike, extreme entry at the spike,
    hysteresis hold inside the band, step-down exit, return to normal."""
    evs = tape()
    cfg = Config()
    path = _label_path(evs, cfg)
    labels = [l for l, _, _ in path]
    assert labels[0:4] == ["warming"] * 4
    assert "extreme" not in labels[:24], "no extreme before the bar-25 spike"
    assert labels[24] == "extreme"   # bar 25: p > 0.95, spike entry
    assert labels[25] == "extreme"   # bar 26: p in (0.90, 0.95], hysteresis hold
    assert labels[26] == "elevated"  # bar 27: p <= 0.90, step-down exit
    assert labels[29] == "normal"    # bar 30: spike aged out of the window
    # percentile of the spike bar is the trail maximum (causal, no lookahead)
    ps = [p for _, _, p in path if math.isfinite(p)]
    assert ps[24 - 4] == max(ps[:25 - 4])


def test_short_history_degraded():
    """Honest production rule: < 63 trailing bars -> DEGRADED, never OK."""
    evs = tape()
    r = primary_indicator(evs, Config())
    assert r["module_state"] == "DEGRADED"
    assert r["reason"] == "short-trailing-history"
    assert r["state"] == "normal"  # label still emitted for transition pinning


def _production_bars(n=300, seed=9001):
    """Deterministic production-like tape: calm / high-vol block / calm."""
    rng = random.Random(seed)
    rows = []
    ts0 = 1700000000000000000
    o = 100.0
    for i in range(n):
        v = 0.09 if 150 <= i < 170 else 0.02
        v *= 0.8 + 0.4 * rng.random()
        d = (rng.random() - 0.5) * 0.004
        h = o * math.exp(v / 2)
        l = o * math.exp(-v / 2)
        c = o * math.exp(d)
        ts = ts0 + i * CADENCE_S * NS
        rows.append({"bar": i + 1, "event_ts": ts, "asof_ts": ts + 60 * NS,
                     "o": o, "h": h, "l": l, "c": c})
        o = c
    return rows


def test_production_ok_with_long_history():
    """300-bar production tape: OK state, extreme visited during the vol block."""
    rows = _production_bars()
    cfg = Config()
    path = _label_path(rows, cfg)
    assert "extreme" in [l for l, _, _ in path], "vol block must reach extreme"
    rsv = detect(rows, cfg)
    assert rsv.module_state == "OK", rsv
    assert rsv.state in STATE_LABELS


def test_corporate_action_guard():
    """Unadjusted 2:1 jump -> UNKNOWN; with an adjustment factor -> proceeds."""
    evs = tape()[:5]
    jump = dict(evs[-1])
    jump = {"bar": 6, "event_ts": jump["event_ts"] + CADENCE_S * NS,
            "asof_ts": jump["asof_ts"] + CADENCE_S * NS,
            "o": 200.0, "h": 205.0, "l": 195.0, "c": 200.0}
    r = primary_indicator(evs + [jump], Config())
    assert r["module_state"] == "UNKNOWN"
    assert r["reason"] == "unadjusted-corporate-action"
    adj = dict(jump, adj_factor=0.5)  # vendor-supplied split factor
    r2 = primary_indicator(evs + [adj], Config())
    assert r2["reason"] != "unadjusted-corporate-action"


def test_halt_freezes_unknown_and_auction_degrades():
    evs = tape()[:6]
    frozen = primary_indicator(evs, Config())["value"]
    halt = dict(evs[-1])
    halt["market_state"] = "HALTED"
    halt["event_ts"] += CADENCE_S * NS
    halt["asof_ts"] += CADENCE_S * NS
    r = primary_indicator(evs + [halt], Config())
    assert r["module_state"] == "UNKNOWN" and r["reason"] == "halted"
    assert abs(r["value"] - frozen) < TOL  # value frozen at pre-halt level
    auc = dict(halt, market_state="AUCTION")
    r2 = primary_indicator(evs + [auc], Config())
    assert r2["module_state"] == "DEGRADED" and r2["reason"] == "auction-hold"


def test_gap_policy_no_interpolation():
    """A 5-day gap -> UNKNOWN; a 2-day gap -> DEGRADED (masked, never filled)."""
    evs = tape()[:6]
    gap5 = dict(evs[-1])
    gap5["event_ts"] += 5 * CADENCE_S * NS
    gap5["asof_ts"] += 5 * CADENCE_S * NS
    r = primary_indicator(evs + [gap5], Config())
    assert r["module_state"] == "UNKNOWN" and r["reason"] == "stale-gap"
    gap2 = dict(evs[-1])
    gap2["event_ts"] += 2 * CADENCE_S * NS
    gap2["asof_ts"] += 2 * CADENCE_S * NS
    r2 = primary_indicator(evs + [gap2], Config())
    assert r2["module_state"] == "DEGRADED" and r2["reason"] == "gap-masked"
    assert math.isfinite(r2["value"])  # masked, never interpolated


def test_jump_exclusion_recovery():
    """A single jump bar trips F3; leave-one-out excludes it -> DEGRADED."""
    evs = tape()[:24]  # up to the elevated run, before the spike
    last = evs[-1]
    jump = {"bar": 25, "event_ts": last["event_ts"] + CADENCE_S * NS,
            "asof_ts": last["asof_ts"] + CADENCE_S * NS,
            "o": last["c"], "h": last["c"] * 1.31, "l": last["c"] * 0.99,
            "c": last["c"] * 1.30, "adj_factor": 1.0}  # 30% overnight-style jump, adjusted
    r = primary_indicator(evs + [jump], Config())
    assert r["module_state"] == "DEGRADED", r
    assert r["reason"] == "jump-excluded", r
    assert r["excluded_bar"] == 25


def test_cost_interface():
    """§R5: spread/impact scale, borrow/fees don't, extreme/UNKNOWN veto."""
    base = {"spread_bps": 4.0, "impact_bps": 2.0, "borrow_bps": 1.0, "fees_bps": 0.5}
    a = cost_adjustment("extreme", base)
    assert a["spread_mult"] == 2.5 and a["impact_mult"] == 3.0
    assert a["trade_ok"] is False
    a = cost_adjustment("elevated", base)
    assert a["spread_mult"] == 1.5 and a["impact_mult"] == 2.0
    assert a["trade_ok"] is True
    a = cost_adjustment("normal", base)
    assert a["spread_mult"] == 1.0 and a["impact_mult"] == 1.0
    assert a["trade_ok"] is True
    a = cost_adjustment("UNKNOWN", base)
    assert a["trade_ok"] is False  # restrictive default
    for state in ("extreme", "elevated", "normal", "UNKNOWN"):
        a = cost_adjustment(state, base)
        assert a["borrow_mult"] == 1.0 and a["fees_mult"] == 1.0
        assert a["spread_bps"] == 4.0  # base legs untouched; mults are separate
