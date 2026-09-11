"""Acceptance tests for R014 - Informed-flow toxicity (VPIN) regime.

Template v1.0.0. Concrete sketch: loads the fixture tape, runs a reference
implementation of the chapter's normative formula (incl. the §R2 hysteresis
transition table), and asserts causality, F1-F5 fail-safes, dual-estimator
agreement, boundary/hysteresis behavior, and the §R5 cost interface.

Run: python3 -m pytest modules/tests/test_R014.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R014_tape.csv"
EXPECTED = FIX / "R014_expected.csv"
HYS_TAPE = FIX / "R014_hysteresis_tape.csv"
HYS_EXPECTED = FIX / "R014_hysteresis_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 60  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['clean', 'elevated', 'extreme', 'undefined', 'warming',
                'missing', 'invalid', 'halted', 'corporate_action_suspect',
                'out_of_bounds']
BOUNDS = (0.0, 1.0)  # mathematical bounds of the indicator value (F2)
DUAL_MODE = "abs"  # rel | abs | sign | state
ESTIMATOR_VERSION = "1.1.0"


# ============================ R014 ============================
# RB-list: R014 Informed-flow toxicity (VPIN). Grok RB2 worked example (6 buckets,
# V=10000, sig_dp=0.20 given): VPIN = 30838/60000 = 0.514 -> toxic/elevated.
R014_DP = [0.30, -0.10, 0.05, -0.40, 0.20, 0.00]
R014_BUYF = [0.85, 0.35, 0.60, 0.10, 0.75, 0.50]  # [example] tick-rule buy fractions per bucket
R014_V = 10000
R014_SIG = 0.20  # [documented Grok RB2] rolling sigma_dP input

SPLIT_TAPE_ROWS = [  # corporate-action jump: dp=6.0 at 30x sigma -> DEGRADED
    {"bar": i + 1, "event_ts": 2000 + i, "asof_ts": 2060 + i,
     "dp": (6.0 if i == 2 else 0.1), "buy_frac": 0.5, "v": 10000, "sig_dp": 0.2}
    for i in range(6)
]
DROUGHT_TAPE_ROWS = [  # volume drought: one zero-volume bucket -> F2 NaN -> UNKNOWN
    {"bar": i + 1, "event_ts": 3000 + i, "asof_ts": 3060 + i, "dp": 0.1,
     "buy_frac": 0.5, "v": (0 if i == 3 else 10000), "sig_dp": 0.2}
    for i in range(6)
]
HALT_TAPE_ROWS = [  # halt event mid-tape -> freeze per market-state table
    dict({"bar": i + 1, "event_ts": 4000 + i, "asof_ts": 4060 + i, "dp": 0.1,
          "buy_frac": 0.5, "v": 10000, "sig_dp": 0.2},
         **({"market_state": "HALTED"} if i == 3 else {}))
    for i in range(6)
]

TS0 = 1788220800000000000


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _vpin_bvc(rows, sigma_min):
    imbs = []
    for r in rows:
        sig = r["sig_dp"]
        if not (r["v"] > 0 and sig > sigma_min):
            return float("nan")
        vb = r["v"] * _phi(r["dp"] / sig)
        imbs.append(abs(vb - (r["v"] - vb)) / r["v"])
    return _mean(imbs) if imbs else float("nan")


def _vpin_tick(rows):
    imbs = []
    for r in rows:
        if not (r["v"] > 0 and 0 <= r["buy_frac"] <= 1):
            return float("nan")
        imbs.append(abs(2 * r["buy_frac"] - 1))
    return _mean(imbs) if imbs else float("nan")


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
    """Chapter §R0.2 Config — status default unless noted (production must run
    the §R2 calibration recipe; shipped defaults are literature-anchored
    starting points, not tuned values)."""
    buckets: int = 50                 # n, window size
    bucket_adv_frac: float = 0.02     # V = frac * ADV
    enter_extreme: float = 0.70       # entry into extreme (strict >)
    exit_extreme: float = 0.60        # hysteresis release (stay extreme while >=)
    enter_elevated: float = 0.30      # entry into elevated (>=)
    exit_elevated: float = 0.25       # hysteresis release (stay elevated while >=)
    min_buckets: int = 4              # warm-up floor
    dual_tol: float = 0.1             # F3 BVC/tick agreement
    sigma_min: float = 1e-8           # sigma estimation collapse guard
    split_guard_sigmas: float = 20.0  # |dp|/sigma above this -> corporate action suspect


def label_value(v, prev_label, cfg):
    """§R2 hysteresis transition table (normative). Entry into extreme is
    strict (>); exits are sticky (>=) so a label does not flicker on noise."""
    if not math.isfinite(v):
        return "undefined"
    if prev_label == "extreme":
        if v >= cfg.exit_extreme:
            return "extreme"
        if v >= cfg.enter_elevated:
            return "elevated"
        return "clean"
    if prev_label == "elevated":
        if v > cfg.enter_extreme:
            return "extreme"
        if v >= cfg.exit_elevated:
            return "elevated"
        return "clean"
    # cold start / clean / warming / degraded states: stateless entry
    if v > cfg.enter_extreme:
        return "extreme"
    if v >= cfg.enter_elevated:
        return "elevated"
    return "clean"


def primary_indicator(rows, cfg, prev_label=None):
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "vintage": "synthetic"}
    if any("dp" not in r or "buy_frac" not in r or "v" not in r or "sig_dp" not in r
           for r in rows):
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1].get("event_ts", 0), "vintage": "synthetic"}
    if any(r.get("market_state") == "HALTED" for r in rows):
        return {"value": float("nan"), "state": "halted", "module_state": "UNKNOWN",
                "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}
    if len(rows) < cfg.min_buckets:
        return {"value": float("nan"), "state": "warming", "module_state": "DEGRADED",
                "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}
    for r in rows:  # corporate-action jump guard (split/dividend on raw tape)
        sig = r["sig_dp"]
        if sig > cfg.sigma_min and abs(r["dp"]) / sig > cfg.split_guard_sigmas:
            return {"value": float("nan"), "state": "corporate_action_suspect",
                    "module_state": "DEGRADED", "computed_at": rows[-1]["event_ts"],
                    "vintage": "synthetic"}
    v = _vpin_bvc(rows, cfg.sigma_min)
    return {"value": v, "state": label_value(v, prev_label, cfg),
            "module_state": "OK", "computed_at": rows[-1]["event_ts"],
            "vintage": "synthetic"}


def second_estimator(rows, cfg):
    rows = list(rows)
    return {"value": _vpin_tick(rows), "state": "n/a",
            "computed_at": rows[-1]["event_ts"] if rows else 0}


primary_indicator_fn = primary_indicator
second_estimator_fn = second_estimator


def cost_adjustment(rsv, base):
    """§R5 cost interface: regime state -> cost-function adjustment.
    Components named per the 4-component stack (spread/fees/borrow/impact)."""
    adj = dict(base)
    st = rsv["state"] if isinstance(rsv, dict) else rsv.state
    if st == "extreme":
        adj["trade_ok"] = False       # [default] stand down: no fills assumed
        adj["passive_ok"] = False     # [default]
        adj["spread_bps_mult"] = 3.0  # [example] top of practitioner 2-3x band
        adj["impact_bps_add"] = 0.0   # [default] impact not modeled at this tier
    elif st == "elevated":
        adj["trade_ok"] = True
        adj["passive_ok"] = False     # [default] no passive fills in toxic flow
        adj["spread_bps_mult"] = 2.0  # [example] mid of practitioner 2-3x band
        adj["impact_bps_add"] = 0.0   # [default]
    elif st in ("halted", "corporate_action_suspect", "warming", "missing",
                "invalid", "undefined"):
        adj["trade_ok"] = True
        adj["passive_ok"] = False     # [default] restrictive default on degradation
        adj["spread_bps_mult"] = 2.0  # [default] widen on degradation
        adj["impact_bps_add"] = 0.0   # [default]
    else:  # clean
        adj["trade_ok"] = True
        adj["passive_ok"] = True
        adj["spread_bps_mult"] = 1.0  # [default]
        adj["impact_bps_add"] = 0.0   # [default]
    # borrow: MM inventory assumed flat, no overnight short -> 0 [default]
    adj.setdefault("borrow_bps_per_day", 0.0)
    return adj


F2_POISON_TAPE = [
    {"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1060 + i, "dp": 0.0,
     "buy_frac": 0.5, "v": 10000, "sig_dp": 0.0}
    for i in range(6)
]  # sig_dp = 0 -> BVC undefined (guard returns NaN) -> F2


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


def detect(rows, cfg, prev_label=None, now_ns=None, select_periods=False,
           preregistered=False):
    """detect(state, events, cfg) -> RegimeState — reference implementation
    with F1-F5 fail-safes wired in (Appendix f v1.0.0). prev_label feeds the
    §R2 hysteresis transition table; omit for cold start."""
    rows = list(rows)
    r = primary_indicator(rows, cfg, prev_label)
    if r["module_state"] != "OK":
        return RegimeState("R014", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R014", "out_of_bounds", v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F3: dual-estimator agreement (BVC sentinel vs tick-rule verifier)
    s = second_estimator(rows, cfg)
    if DUAL_MODE == "state":
        agree = (r["state"] == s["state"]) or (
            math.isfinite(v) and math.isfinite(s["value"])
            and abs(v - s["value"]) <= cfg.dual_tol)
    else:
        agree = within_tolerance(v, s["value"], DUAL_MODE, cfg.dual_tol)
    if not agree:
        return RegimeState("R014", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R014", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R014", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def tape(path=TAPE):
    rows = []
    for r in load_csv(path):
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


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = Config()
    prev = None
    for i in range(len(evs)):
        r = primary_indicator(evs[: i + 1], cfg, prev_label=prev)
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
        prev = r["state"]


def test_hysteresis_fixture_recomputes():
    """Hysteresis tape: causal recompute with chained prev_label matches."""
    evs = tape(HYS_TAPE)
    exp = {int(r["bar"]): r for r in load_csv(HYS_EXPECTED)}
    cfg = Config()
    prev = None
    for i in range(len(evs)):
        r = primary_indicator(evs[: i + 1], cfg, prev)
        want = exp[i + 1]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(r["value"]), i
        else:
            assert abs(r["value"] - wv) < TOL, i
        assert r["state"] == want["exp_state"], i
        assert r["module_state"] == want["exp_module_state"], i
        assert want["exp_prev_label"] in ("none", prev if prev else "none"), i
        prev = r["state"]
    # the pinning row: final VPIN 0.6584 is held 'extreme' ONLY by hysteresis
    assert exp[9]["exp_state"] == "extreme"
    assert float(exp[9]["exp_value"]) < cfg.enter_extreme


def test_hysteresis_end_to_end():
    """Same final value, different history -> different label. Fails on any
    drift in the hysteresis transition table (e.g. stateless 0.70 threshold)."""
    evs = tape(HYS_TAPE)
    cfg = Config()
    cold = detect(evs, cfg, prev_label=None)          # cold start
    hot = detect(evs, cfg, prev_label="extreme")     # came from extreme
    assert 0.60 < cold.value < 0.70, cold.value
    assert cold.state == "elevated", cold
    assert hot.state == "extreme", hot
    assert cold.module_state == "OK" and hot.module_state == "OK"


def test_hysteresis_transition_table():
    """Unit pin of the §R2 transition table incl. strict-inequality boundaries."""
    cfg = Config()
    cases = [
        # (value, prev_label, expected)
        (0.7001, None, "extreme"),      # entry into extreme is strict >
        (0.70, None, "elevated"),       # 0.70 exactly is NOT extreme
        (0.30, None, "elevated"),       # entry into elevated is >=
        (0.2999, None, "clean"),
        (0.60, "extreme", "extreme"),   # exit is sticky >=
        (0.5999, "extreme", "elevated"),
        (0.30, "extreme", "elevated"),  # falls through to elevated entry band
        (0.2999, "extreme", "clean"),
        (0.25, "elevated", "elevated"), # elevated exit sticky
        (0.2499, "elevated", "clean"),
        (0.75, "elevated", "extreme"),  # re-entry from elevated
        (0.65, "elevated", "elevated"), # between bands: hysteresis holds
        (0.65, "extreme", "extreme"),   # between bands: hysteresis holds
        (0.65, "clean", "elevated"),    # cold: stateless entry
        (float("nan"), "extreme", "undefined"),
    ]
    for v, prev, want in cases:
        got = label_value(v, prev, cfg)
        assert got == want, (v, prev, got, want)


def test_config_thresholds_in_range():
    """Config defaults sit inside their documented ranges; exits below entries."""
    cfg = Config()
    assert 0.60 <= cfg.enter_extreme <= 0.80
    assert 0.50 <= cfg.exit_extreme <= 0.70
    assert cfg.exit_extreme < cfg.enter_extreme
    assert 0.20 <= cfg.enter_elevated <= 0.40
    assert 0.15 <= cfg.exit_elevated <= 0.35
    assert cfg.exit_elevated < cfg.enter_elevated
    assert cfg.exit_extreme > cfg.enter_elevated  # bands do not overlap
    assert 4 <= cfg.min_buckets <= 20
    assert cfg.dual_tol == 0.1


def test_boundary_entry_exact_070():
    """A value of exactly 0.70 must NOT label extreme (strict > entry)."""
    cfg = Config()
    assert label_value(0.70, None, cfg) == "elevated"
    assert label_value(0.70 + 1e-12, None, cfg) == "extreme"


def test_volume_drought_unknown():
    """Zero-volume bucket -> BVC undefined -> F2 bounds -> UNKNOWN, never a guess."""
    rsv = detect(DROUGHT_TAPE_ROWS, Config())
    assert rsv.module_state == "UNKNOWN"


def test_split_jump_degraded():
    """Corporate-action jump (|dp| > 20 sigma) -> DEGRADED, label withheld."""
    rsv = detect(SPLIT_TAPE_ROWS, Config())
    assert rsv.module_state == "DEGRADED"
    assert rsv.state == "corporate_action_suspect"


def test_halt_freezes_unknown():
    """Halt event in the window -> freeze, UNKNOWN (market-state table)."""
    rsv = detect(HALT_TAPE_ROWS, Config())
    assert rsv.module_state == "UNKNOWN"
    assert rsv.state == "halted"


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R014"
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
    prev = None
    for i in range(len(evs) - 1):
        label = detect(evs[: i + 1], cfg, prev_label=prev)
        indicator_ts = evs[i]["event_ts"]          # newest data used
        assert label.computed_at == indicator_ts  # label stamped at t, not later
        earliest_trade_ts = evs[i + 1]["event_ts"]
        assert earliest_trade_ts > label.computed_at, f"lookahead at bar {{i}}"
        prev = label.state
    # appending a future breakout bar must not move the label stamped at t
    label_t = detect(evs[:-1], cfg, prev_label=None)
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
    p0 = primary_indicator(evs, Config(), None)["value"]
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
    r = primary_indicator(evs, cfg, None)
    s = second_estimator(evs, cfg)
    if DUAL_MODE == "state":
        ok = (r["state"] == s["state"]) or (
            abs(r["value"] - s["value"]) <= cfg.dual_tol)
        assert ok, (r, s)
    else:
        assert within_tolerance(r["value"], s["value"], DUAL_MODE, cfg.dual_tol), (r, s)
    assert detect(evs, cfg).module_state == "OK"


def test_cost_adjustment_interface():
    """§R5 cost interface: regime state -> cost-function adjustment, per component."""
    base = {"spread_bps": 2.0, "fee_bps": 0.3, "borrow_bps_per_day": 0.0,
            "impact_bps": 1.5}
    mk = lambda st: {"state": st}

    clean = cost_adjustment(mk("clean"), base)
    assert clean["trade_ok"] is True
    assert clean["passive_ok"] is True
    assert clean["spread_bps_mult"] == 1.0
    assert clean["impact_bps_add"] == 0.0

    elev = cost_adjustment(mk("elevated"), base)
    assert elev["trade_ok"] is True
    assert elev["passive_ok"] is False       # no passive fills in toxic flow
    assert elev["spread_bps_mult"] == 2.0

    extr = cost_adjustment(mk("extreme"), base)
    assert extr["trade_ok"] is False        # stand down: no fills assumed
    assert extr["passive_ok"] is False
    assert extr["spread_bps_mult"] == 3.0

    degr = cost_adjustment(mk("halted"), base)
    assert degr["passive_ok"] is False      # restrictive default on degradation
    assert degr["spread_bps_mult"] == 2.0

    # base dict is not mutated
    assert base == {"spread_bps": 2.0, "fee_bps": 0.3, "borrow_bps_per_day": 0.0,
                    "impact_bps": 1.5}
