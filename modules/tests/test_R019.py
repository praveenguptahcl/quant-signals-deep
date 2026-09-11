"""Acceptance tests for R019 - Crypto funding-rate regime.

Template v1.0.0. Reference implementation of the chapter's normative
detection algorithm (trailing-window cross-venue mean, sign agreement,
hysteresis state machine with entry confirmation), plus F1-F5 fail-safes.

Run: python3 -m pytest modules/tests/test_R019.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, fields
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R019_tape.csv"
EXPECTED = FIX / "R019_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 8 * 3600  # indicator cadence in seconds [default]
NS = 1_000_000_000
BOUNDS = (-500.0, 500.0)  # mathematical bounds of the indicator value (F2) [default]
DUAL_MODE = "rel"  # rel | abs | sign | state
ESTIMATOR_VERSION = "1.1.0"
STATE_LABELS = ['balanced', 'leaning', 'crowded', 'extreme', 'undefined',
                'warming', 'missing', 'invalid', 'out_of_bounds']
ORDER = {'balanced': 0, 'leaning': 1, 'crowded': 2, 'extreme': 3}


# ============================ R019 ============================
# RB-list: R019 Crypto funding-rate regime. Grok RB2 worked example:
# 8h rates 0.020%, 0.015%, 0.025% on $10k -> $6/day; mean 0.020% ->
# annualized (simple) 0.00020*3*365 = 21.9% -> moderately elevated.


def _ann(f8):
    return f8 * 3 * 365 * 100  # simple annualization, in percent [documented]


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _sign(x):
    return 1 if x > 0 else (-1 if x < 0 else 0)


@dataclass
class Config:
    # Mirrors the §R0.2 Config table (status default => [default] per tag law).
    venues: int = 3
    window_intervals: int = 3
    min_intervals: int = 2
    min_venues: int = 2
    lean_entry_ann: float = 5.0
    lean_exit_ann: float = 4.0
    crowded_entry_ann: float = 20.0
    crowded_exit_ann: float = 15.0
    extreme_entry_ann: float = 50.0
    extreme_exit_ann: float = 40.0
    confirm_n: int = 2
    confirm_k: int = 3
    dual_tol: float = 0.3
    staleness_mult: float = 3.0


def _cfg_get(cfg, name):
    return getattr(cfg, name, getattr(Config, name))


def _grid(rows, cfg):
    """Group raw prints into settlement intervals.

    Returns a list of dicts {ts, venue_means, n} sorted by ts, one entry per
    distinct event_ts. Intervals with fewer than min_venues reporting venues
    are masked (venue_means=None).
    """
    min_venues = _cfg_get(cfg, "min_venues")
    by_ts = {}
    for r in rows:
        d = by_ts.setdefault(r["event_ts"], {})
        d.setdefault(r["venue"], []).append(r["f_8h"])
    out = []
    for ts in sorted(by_ts):
        vm = {v: _mean(fs) for v, fs in by_ts[ts].items()}
        out.append({"ts": ts, "venue_means": vm if len(vm) >= min_venues else None})
    return out


def _confirm(vals, threshold, cfg):
    """Entry confirmation: >= confirm_n of the last confirm_k indicator
    values at or beyond the entry threshold."""
    n = _cfg_get(cfg, "confirm_n")
    k = _cfg_get(cfg, "confirm_k")
    tail = vals[-k:]
    return sum(1 for v in tail if v >= threshold) >= n


def _step(prev, v, vals, cfg):
    """Hysteresis state machine: entries need confirmation, exits are
    immediate once the value drops below the (lower) exit threshold."""
    if prev == "balanced":
        return "leaning" if _confirm(vals, _cfg_get(cfg, "lean_entry_ann"), cfg) else "balanced"
    if prev == "leaning":
        if v < _cfg_get(cfg, "lean_exit_ann"):
            return "balanced"
        if _confirm(vals, _cfg_get(cfg, "crowded_entry_ann"), cfg):
            return "crowded"
        return "leaning"
    if prev == "crowded":
        if v < _cfg_get(cfg, "crowded_exit_ann"):
            return "leaning"
        if _confirm(vals, _cfg_get(cfg, "extreme_entry_ann"), cfg):
            return "extreme"
        return "crowded"
    # prev == "extreme"
    return "crowded" if v < _cfg_get(cfg, "extreme_exit_ann") else "extreme"


def primary_indicator(rows, cfg):
    """Normative detection. Returns dict(value, state, module_state,
    computed_at, vintage). Stateless across calls: hysteresis is replayed
    causally from the first interval, so prefixes give prefix labels."""
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "vintage": "synthetic"}
    need = ("event_ts", "venue", "f_8h")
    if any(any(k not in r for k in need) or not math.isfinite(r["f_8h"]) for r in rows):
        ts = rows[-1].get("event_ts", 0)
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": ts, "vintage": "synthetic"}
    W = _cfg_get(cfg, "window_intervals")
    min_intervals = _cfg_get(cfg, "min_intervals")
    grid = _grid(rows, cfg)
    vals = []          # (ts, annualized value) for valid evaluations
    prev = "balanced"  # hysteresis entry state [default]
    last = None
    for i, g in enumerate(grid):
        window = grid[max(0, i - W + 1): i + 1]
        valid = [gg for gg in window if gg["venue_means"] is not None]
        if len(valid) < min_intervals:
            last = {"value": float("nan"), "state": "warming",
                    "module_state": "DEGRADED", "computed_at": g["ts"],
                    "vintage": "synthetic"}
            continue
        cross = _mean(_mean(gg["venue_means"].values()) for gg in valid)
        v = _ann(cross)
        # Sign agreement (F3 input hygiene): venues must agree on the sign of
        # the window mean when the cross-venue mean is material.
        if abs(v) > 1.0:
            for venue in {vv for gg in valid for vv in gg["venue_means"]}:
                vm = _mean(gg["venue_means"][venue]
                           for gg in valid if venue in gg["venue_means"])
                if _sign(vm) != _sign(cross):
                    return {"value": v, "state": "invalid", "module_state": "UNKNOWN",
                            "computed_at": g["ts"], "vintage": "synthetic"}
        vals.append((g["ts"], v))
        state = _step(prev, v, [vv for _, vv in vals], cfg)
        prev = state
        last = {"value": v, "state": state, "module_state": "OK",
                "computed_at": g["ts"], "vintage": "synthetic"}
    return last


def second_estimator(rows, cfg):
    """Verifier: median-based cross-venue estimator over the same trailing
    window. Must agree with the mean-based Sentinel within dual_tol (F3)."""
    rows = list(rows)
    W = _cfg_get(cfg, "window_intervals")
    min_intervals = _cfg_get(cfg, "min_intervals")
    grid = _grid(rows, cfg)
    window = [g for g in grid[-W:] if g["venue_means"] is not None]
    if len(window) < min_intervals:
        return {"value": float("nan"), "state": "n/a",
                "computed_at": rows[-1]["event_ts"] if rows else 0}
    per_venue = {}
    for g in window:
        for venue, f in g["venue_means"].items():
            per_venue.setdefault(venue, []).append(f)
    medians = sorted(_mean(fs) for fs in per_venue.values())
    med = medians[len(medians) // 2]
    return {"value": _ann(med), "state": "n/a",
            "computed_at": grid[-1]["ts"]}


F2_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1001, "venue": "binance", "f_8h": 0.05},
    {"bar": 1, "event_ts": 1000, "asof_ts": 1001, "venue": "bybit", "f_8h": 0.05},
    {"bar": 2, "event_ts": 1002, "asof_ts": 1003, "venue": "binance", "f_8h": 0.05},
    {"bar": 2, "event_ts": 1002, "asof_ts": 1003, "venue": "bybit", "f_8h": 0.05},
]  # annualized = 5475% > 500 bound -> F2


SIGN_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1001, "venue": "binance", "f_8h": 0.00030},
    {"bar": 1, "event_ts": 1000, "asof_ts": 1001, "venue": "bybit", "f_8h": -0.00010},
    {"bar": 2, "event_ts": 2000, "asof_ts": 2001, "venue": "binance", "f_8h": 0.00030},
    {"bar": 2, "event_ts": 2000, "asof_ts": 2001, "venue": "bybit", "f_8h": -0.00010},
]  # cross-venue mean +10.95% ann. but venues disagree on sign -> F3 hygiene -> UNKNOWN


primary_indicator_r019 = primary_indicator
second_estimator_r019 = second_estimator
primary_indicator_fn = primary_indicator
second_estimator_fn = second_estimator


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


def settlement_ts():
    """Distinct settlement timestamps of the tape, in order."""
    seen = []
    for r in tape():
        if r["event_ts"] not in seen:
            seen.append(r["event_ts"])
    return seen


def prefix(ts):
    """All tape rows with event_ts <= ts (causal prefix)."""
    return [r for r in tape() if r["event_ts"] <= ts]


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label, e.g. "crowded"
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
    r = primary_indicator(rows, cfg)  # dict(value, state, module_state, computed_at)
    if r["module_state"] != "OK":
        return RegimeState("R019", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R019", "out_of_bounds", v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F3: dual-estimator agreement (rel mode, DUAL_TOL from cfg)
    s = second_estimator(rows, cfg)
    tol = _cfg_get(cfg, "dual_tol")
    if not (math.isfinite(v) and math.isfinite(s["value"])
            and within_tolerance(v, s["value"], DUAL_MODE, tol)):
        return RegimeState("R019", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — staleness_mult x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > _cfg_get(cfg, "staleness_mult") * CADENCE_S * NS:
        return RegimeState("R019", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R019", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each settlement matches expected CSV."""
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = Config()
    for i, ts in enumerate(settlement_ts(), 1):
        r = primary_indicator(prefix(ts), cfg)
        want = exp[i]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(r["value"]), i
        elif math.isinf(wv):
            assert math.isinf(r["value"]) and (r["value"] > 0) == (wv > 0), i
        else:
            assert abs(r["value"] - wv) < TOL, (i, r["value"], wv)
        assert r["state"] == want["exp_state"], (i, r["state"])
        assert r["computed_at"] == int(want["exp_computed_at"]), i
        assert r["computed_at"] == ts, i
        assert r["module_state"] == want["exp_module_state"], i


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R019"
    assert rsv.state in STATE_LABELS
    assert math.isfinite(rsv.value) and BOUNDS[0] <= rsv.value <= BOUNDS[1]
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. Assert label_ts > indicator_ts for the earliest trade."""
    cfg = Config()
    tss = settlement_ts()
    for i, ts in enumerate(tss[:-1]):
        label = detect(prefix(ts), cfg)
        assert label.computed_at == ts  # label stamped at t, not later
        assert tss[i + 1] > label.computed_at, f"lookahead at settlement {i}"
    # appending a future breakout bar must not move the label stamped at t
    label_t = detect(prefix(tss[-2]), cfg)
    assert label_t.computed_at == tss[-2]


def test_warmup_degraded_label_withheld():
    """Insufficient lookback: first settlement -> DEGRADED, label withheld."""
    cfg = Config()
    tss = settlement_ts()
    rsv = detect(prefix(tss[0]), cfg)
    assert rsv.module_state == "DEGRADED"
    assert rsv.state == "warming"
    # second settlement: window has min_intervals -> OK
    rsv2 = detect(prefix(tss[1]), cfg)
    assert rsv2.module_state == "OK"


def test_entry_confirmation_rejects_single_spike():
    """A one-interval funding spike (settlement 6, ~60% ann. mean) must NOT
    flip leaning -> crowded: 2-of-3 confirmation fails on a lone spike."""
    cfg = Config()
    tss = settlement_ts()
    assert detect(prefix(tss[5]), cfg).state == "leaning"   # spike settlement
    assert detect(prefix(tss[6]), cfg).state == "crowded"   # confirmed next


def test_hysteresis_holds_on_dip_above_exit():
    """Crowded holds when the indicator dips below the 20% entry but stays
    above the 15% exit (settlements 9-10)."""
    cfg = Config()
    tss = settlement_ts()
    for ts in tss[8:10]:
        rsv = detect(prefix(ts), cfg)
        assert rsv.state == "crowded", (ts, rsv.value)
        assert 15.0 <= abs(rsv.value) < 20.0, rsv.value
    # below the 15% exit -> steps down to leaning (settlement 11)
    rsv = detect(prefix(tss[10]), cfg)
    assert rsv.state == "leaning"


def test_extreme_entry_needs_confirmation_and_exit_hysteresis():
    """Extreme requires 2-of-3 confirmations >= 50% (settlement 15, not 14);
    then holds while the value sits between the 40% exit and 50% entry
    (settlements 16-17), and steps down to crowded below 40% (settlement 18)."""
    cfg = Config()
    tss = settlement_ts()
    assert detect(prefix(tss[12]), cfg).state == "crowded"   # 1st >= 50 eval
    assert detect(prefix(tss[13]), cfg).state == "crowded"   # still 1 of 3? -> 2 of 3
    assert detect(prefix(tss[14]), cfg).state == "extreme"
    for ts in tss[15:17]:
        rsv = detect(prefix(ts), cfg)
        assert rsv.state == "extreme", (ts, rsv.value)
        assert 40.0 <= abs(rsv.value) < 50.0 or abs(rsv.value) >= 50.0, rsv.value
    assert detect(prefix(tss[17]), cfg).state == "crowded"


def test_missing_venue_interval_masked_not_interpolated():
    """Settlement 12 has no OKX print: the interval mean uses 2 venues and
    the detector never interpolates the missing print."""
    cfg = Config()
    tss = settlement_ts()
    rows12 = [r for r in prefix(tss[11]) if r["event_ts"] == tss[11]]
    venues = {r["venue"] for r in rows12}
    assert venues == {"binance", "bybit"}, venues
    rsv = detect(prefix(tss[11]), cfg)
    assert rsv.module_state == "OK"
    assert math.isfinite(rsv.value)


def test_F1_missing_input_unknown():
    assert detect([], Config()).module_state == "UNKNOWN"
    bad = [dict(event_ts=1, asof_ts=2)]  # missing indicator fields
    assert detect(bad, Config()).module_state == "UNKNOWN"


def test_F2_bounds_violation_unknown():
    rsv = detect(F2_POISON_TAPE, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"


def test_F3_sign_disagreement_unknown():
    """Venues disagreeing on the sign of funding -> UNKNOWN (F3 hygiene)."""
    rsv = detect(SIGN_POISON_TAPE, Config())
    assert rsv.module_state == "UNKNOWN"


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
    cfg = Config()
    stale_now = evs[-1]["event_ts"] + 10 * _cfg_get(cfg, "staleness_mult") * CADENCE_S * NS
    rsv = detect(evs, cfg, now_ns=stale_now)
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
    assert within_tolerance(r["value"], s["value"], DUAL_MODE, _cfg_get(cfg, "dual_tol")), (r, s)
    assert detect(evs, cfg).module_state == "OK"
