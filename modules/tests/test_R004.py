"""Acceptance tests for R004 - Volatility clustering / persistence state.

Template v1.0.0. Loads the fixture tape, runs the reference implementation of
the chapter's normative formula (§R2: estimator + hysteresis state machine),
and asserts causality, F1-F5 fail-safes, dual-estimator agreement, and the
§R5 cost interface.

Reference estimator honesty (§R6): the stdlib-only coarse-grid QMLE below is
an *operational proxy / smoke test*. Dev measurements (seed 9004, /tmp
r004dev*.py): on 252-bar true-GARCH(1,1) simulations with true pi in
{0.80, 0.90, 0.97} plus iid noise, the 25-point grid returned pi = 0.93 on
all 16 runs [measured] -- i.e. it cannot discriminate persistence states.
Production MUST use a real QMLE optimizer (Gate check, §R4). State-machine
behavior (transitions, hysteresis, boundaries) is pinned deterministically
via the injected-pi fixture R004_pi_path.csv + boundary unit tests.

Run: python3 -m pytest modules/tests/test_R004.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R004_tape.csv"
EXPECTED = FIX / "R004_expected.csv"
PI_PATH = FIX / "R004_pi_path.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 604800  # weekly refit cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['low', 'normal', 'extreme', 'unstable', 'warming', 'missing', 'invalid']
VALID_STATES = ('low', 'normal', 'extreme')  # label-emitting states
BOUNDS = (0.0, 0.9999)  # mathematical bounds of the indicator value (F2)
DUAL_MODE = "state"  # rel | abs | sign | state
DUAL_TOL = 0.05
ESTIMATOR_VERSION = "1.1.0"


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


# ============================ R004 ============================
@dataclass
class Config:
    """Chapter Config table (§R0.2). Statuses: default | calibrate | fixed."""
    garch_window_days: int = 252      # [default] rolling estimation window
    min_obs: int = 252                # [default] production warmup (obs)
    refit_cadence: str = "weekly"     # [default]
    pi_low_enter: float = 0.85        # [example] calibrate
    pi_low_exit: float = 0.88         # [example] calibrate
    pi_extreme_enter: float = 0.95    # [example] calibrate
    pi_extreme_exit: float = 0.92     # [example] calibrate
    hl_baseline_d: float = 14.0       # [default] baseline half-life (stop scaling)
    use_split_adjusted: bool = True   # [fixed] production must assert adjusted closes


def _garch_pi(rets):
    """Coarse-grid QMLE GARCH(1,1) persistence — operational proxy ONLY.

    [measured] degeneracy: on 252-bar true-GARCH simulations (true pi in
    {0.80, 0.90, 0.97}, seed 9004) this 25-point grid returned pi = 0.93 on
    all 16 runs; it cannot discriminate persistence states. Production must
    use a real optimizer (arch/scipy-class QMLE); see §R4 Gate + §R6.
    """
    n = len(rets)
    m = _mean(rets)
    e = [r - m for r in rets]
    v0 = _mean([x * x for x in e])
    if not (v0 > 0):
        return float("nan")
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
                if s2 <= 0:
                    ll = float("-inf")
                    break
                ll += -0.5 * (math.log(s2) + x * x / s2)
            if best is None or ll > best[0]:
                best = (ll, a + b)
    return best[1] if best else float("nan")


def classify_pi(prev_state, pi, cfg):
    """Hysteresis state machine (§R2.1) — NORMATIVE, pure function.

    prev_state in {'low', 'normal', 'extreme'} (warming treated as
    normal-base once an estimate exists). Enter/exit bands differ by the
    hysteresis width (enter - exit = 0.03 [default]) to prevent flicker.
    Non-finite pi -> 'unstable' (F2) regardless of prev.
    """
    if not math.isfinite(pi):
        return "unstable"
    if prev_state == "extreme":
        return "extreme" if pi > cfg.pi_extreme_exit else "normal"
    if prev_state == "low":
        return "low" if pi < cfg.pi_low_exit else "normal"
    if pi >= cfg.pi_extreme_enter:
        return "extreme"
    if pi <= cfg.pi_low_enter:
        return "low"
    return "normal"


def primary_indicator(rows, cfg, prev_state="normal"):
    """Per-bar causal estimate + hysteresis classification (§R2).

    rows: closes with event_ts <= t, newest last (split-adjusted per cfg).
    prev_state: last VALID label ('low' | 'normal' | 'extreme'); the caller
    threads it (see causal_path). Returns dict(value, state, half_life_d,
    module_state, computed_at, vintage).
    """
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "half_life_d": float("nan"), "vintage": "synthetic"}
    if any((not isinstance(r, dict)) or ("c" not in r) or (not isinstance(r["c"], (int, float)))
           or (not math.isfinite(r["c"])) or (not r["c"] > 0) for r in rows):
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1].get("event_ts", 0) if isinstance(rows[-1], dict) else 0,
                "half_life_d": float("nan"), "vintage": "synthetic"}
    if len(rows) < cfg.min_obs:
        return {"value": float("nan"), "state": "warming", "module_state": "DEGRADED",
                "computed_at": rows[-1]["event_ts"], "half_life_d": float("nan"),
                "vintage": "synthetic"}
    window = rows[-cfg.garch_window_days:] if cfg.garch_window_days < len(rows) else rows
    rets = [math.log(window[i]["c"] / window[i - 1]["c"]) for i in range(1, len(window))]
    pi = _garch_pi(rets)
    state = classify_pi(prev_state if prev_state in VALID_STATES else "normal", pi, cfg)
    hl = math.log(0.5) / math.log(pi) if (math.isfinite(pi) and 0.0 < pi < 1.0) else float("nan")
    return {"value": pi, "state": state, "module_state": "OK",
            "computed_at": rows[-1]["event_ts"], "half_life_d": hl, "vintage": "synthetic"}


def causal_path(rows, cfg, prev_state="normal"):
    """Per-bar causal recompute threading the last valid label (§R2).

    After an 'unstable' bar the previous VALID label is held (no reset).
    Shared by the fixture generator and the recompute test so both pin the
    same path.
    """
    prev = prev_state
    out = []
    for i in range(len(rows)):
        r = primary_indicator(rows[:i + 1], cfg, prev)
        out.append(r)
        if r["state"] in VALID_STATES:
            prev = r["state"]
    return out


def _garch_pi_coarse(rets):
    """Independent coarse-grid GARCH(1,1) fit — the test's second estimator.

    Production verifier fits HAR-RV (see §R4); this coarser grid is the
    deterministic operational proxy used in the reference test. F3 tolerance
    is on the *state*, not the parameter (§R4).
    """
    m = _mean(rets)
    e = [r - m for r in rets]
    v0 = _mean([x * x for x in e])
    if not (v0 > 0):
        return float("nan")
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
                if s2 <= 0:
                    ll = float("-inf")
                    break
                ll += -0.5 * (math.log(s2) + x * x / s2)
            if best is None or ll > best[0]:
                best = (ll, a + b)
    return best[1] if best else float("nan")


def second_estimator(rows, cfg):
    rows = list(rows)
    if len(rows) < cfg.min_obs:
        return {"value": float("nan"), "state": "warming",
                "computed_at": rows[-1]["event_ts"] if rows else 0}
    window = rows[-cfg.garch_window_days:] if cfg.garch_window_days < len(rows) else rows
    rets = [math.log(window[i]["c"] / window[i - 1]["c"]) for i in range(1, len(window))]
    pi = _garch_pi_coarse(rets)
    return {"value": pi, "state": classify_pi("normal", pi, cfg),
            "computed_at": rows[-1]["event_ts"]}


def cost_adjustment(rsv, base):
    """§R5 cost interface: regime state -> cost-function adjustment (normative).

    rsv: dict(state, half_life_d, module_state). base: dict from
    expected_cost_bps(...) with keys spread_bps, fees_bps, borrow_bps,
    impact_bps. Returns a NEW dict; every multiplier tagged per the tag law.
    """
    adj = dict(base)
    state = rsv.get("state")
    ms = rsv.get("module_state")
    hl = rsv.get("half_life_d")
    if not (isinstance(hl, (int, float)) and math.isfinite(hl) and hl > 0):
        hl = 14.0  # [default] baseline half-life
    tag = "R004:" + str(state)
    if ms in ("UNKNOWN", "OFF"):
        adj["size_mult"] = 0.5       # [default] restrictive: halve size
        adj["impact_bps"] = adj["impact_bps"] * 1.5  # [example] adverse-selection buffer
        adj["trade_ok"] = False      # [default]
        adj["tag"] = tag + ":unknown-restrictive"
        return adj
    if state == "extreme":
        adj["impact_bps"] = adj["impact_bps"] * 1.5  # [example]
        adj["spread_bps"] = adj["spread_bps"] * 1.25  # [example]
        adj["stop_mult"] = max(1.0, (hl / 14.0) ** 0.5)  # [default] sqrt(HL/HL_baseline)
        adj["size_mult"] = 0.5  # [example]
    elif state == "low":
        adj["impact_bps"] = adj["impact_bps"] * 0.9   # [example]
        adj["spread_bps"] = adj["spread_bps"] * 0.95  # [example]
        adj["stop_mult"] = 1.0  # [default]
        adj["size_mult"] = 1.0  # [default]
    else:  # normal / warming / unstable / missing / invalid
        adj["stop_mult"] = 1.0  # [default]
        adj["size_mult"] = 1.0 if state == "normal" else 0.5  # [default]
    adj["trade_ok"] = state != "unstable"  # [default]
    adj["tag"] = tag
    return adj


F2_POISON_TAPE = [
    {"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i, "c": 100.0}
    for i in range(300)
]  # zero variance -> v0 = 0 -> pi = nan -> F2 bounds -> UNKNOWN (n >= min_obs)


primary_indicator_r004 = primary_indicator
second_estimator_r004 = second_estimator


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


def detect(rows, cfg, prev_state="normal", now_ns=None, select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState — reference implementation
    with F1-F5 fail-safes wired in (Appendix f v1.0.0). prev_state is the
    module-owned last valid label ('low' | 'normal' | 'extreme')."""
    rows = list(rows)
    r = primary_indicator(rows, cfg, prev_state)  # dict(value, state, module_state, computed_at)
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
    # F3: dual-estimator agreement — tolerance is on the STATE (§R4)
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
def _feq(a, b):
    return (math.isnan(a) and math.isnan(b)) or (
        math.isinf(a) and math.isinf(b) and (a > 0) == (b > 0)) or abs(a - b) < TOL


def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = Config()
    assert len(evs) == len(exp) == 280
    for i, r in enumerate(causal_path(evs, cfg)):
        want = exp[i + 1]
        assert _feq(r["value"], float(want["exp_value"])), i
        assert _feq(r["half_life_d"], float(want["exp_half_life_d"])), i
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
    prev = "normal"
    for i in range(len(evs) - 1):
        label = detect(evs[: i + 1], cfg, prev)
        if label.state in VALID_STATES:
            prev = label.state
        indicator_ts = evs[i]["event_ts"]          # newest data used
        assert label.computed_at == indicator_ts  # label stamped at t, not later
        earliest_trade_ts = evs[i + 1]["event_ts"]
        assert earliest_trade_ts > label.computed_at, f"lookahead at bar {{i}}"
    # appending a future breakout bar must not move the label stamped at t
    label_t = detect(evs[:-1], cfg, prev)
    assert label_t.computed_at == evs[-2]["event_ts"]


def test_state_machine_path_fixture():
    """Injected-pi fixture pins every hysteresis transition + unstable recovery."""
    cfg = Config()
    prev = "normal"
    rows = load_csv(PI_PATH)
    assert len(rows) == 13
    for r in rows:
        pi = float(r["inj_pi"])
        st = classify_pi(prev, pi, cfg)
        assert st == r["exp_state"], (r, prev)
        if st in VALID_STATES:
            prev = st  # unstable holds the previous valid label


def test_hysteresis_boundary_values():
    """Exact boundary values: enter/exit/hold semantics at the band edges."""
    cfg = Config()
    # entry boundaries (from normal)
    assert classify_pi("normal", 0.95, cfg) == "extreme"
    assert classify_pi("normal", 0.949999, cfg) == "normal"
    assert classify_pi("normal", 0.85, cfg) == "low"
    assert classify_pi("normal", 0.850001, cfg) == "normal"
    # extreme exit boundary (hysteresis: hold while pi > 0.92)
    assert classify_pi("extreme", 0.92, cfg) == "normal"
    assert classify_pi("extreme", 0.920001, cfg) == "extreme"
    # low exit boundary (hysteresis: hold while pi < 0.88)
    assert classify_pi("low", 0.88, cfg) == "normal"
    assert classify_pi("low", 0.879999, cfg) == "low"
    # non-finite -> unstable from any prev
    for prev in ("low", "normal", "extreme"):
        assert classify_pi(prev, float("nan"), cfg) == "unstable"
        assert classify_pi(prev, float("inf"), cfg) == "unstable"


def test_F1_missing_input_unknown():
    assert detect([], Config()).module_state == "UNKNOWN"
    bad = [dict(event_ts=1, asof_ts=2)]  # missing indicator fields
    assert detect(bad, Config()).module_state == "UNKNOWN"
    bad2 = [{"bar": 1, "event_ts": 1, "asof_ts": 2, "c": -5.0}]  # non-positive close
    assert detect(bad2, Config()).module_state == "UNKNOWN"


def test_F2_bounds_violation_unknown():
    rsv = detect(F2_POISON_TAPE, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = tape()
    orig = mod.second_estimator
    p0 = primary_indicator(evs, Config(), "normal")["value"]
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
    r = primary_indicator(evs, cfg, "normal")
    s = second_estimator(evs, cfg)
    if DUAL_MODE == "state":
        ok = (r["state"] == s["state"]) or (
            DUAL_TOL is not None and abs(r["value"] - s["value"]) <= DUAL_TOL)
        assert ok, (r, s)
    else:
        assert within_tolerance(r["value"], s["value"], DUAL_MODE, DUAL_TOL), (r, s)
    assert detect(evs, cfg).module_state == "OK"


def _base_cost():
    return {"spread_bps": 2.0, "fees_bps": 0.5, "borrow_bps": 0.0, "impact_bps": 3.0}


def test_cost_interface_extreme():
    rsv = {"state": "extreme", "half_life_d": 34.3, "module_state": "OK"}
    adj = cost_adjustment(rsv, _base_cost())
    assert adj["impact_bps"] == 3.0 * 1.5
    assert adj["spread_bps"] == 2.0 * 1.25
    assert adj["size_mult"] == 0.5
    assert adj["stop_mult"] > 1.0
    assert adj["trade_ok"] is True
    assert adj["tag"] == "R004:extreme"
    assert _base_cost()["impact_bps"] == 3.0  # input not mutated


def test_cost_interface_normal_and_low():
    adj = cost_adjustment({"state": "normal", "half_life_d": 13.5, "module_state": "OK"},
                          _base_cost())
    assert adj["size_mult"] == 1.0 and adj["stop_mult"] == 1.0
    assert adj["impact_bps"] == 3.0 and adj["spread_bps"] == 2.0
    assert adj["trade_ok"] is True and adj["tag"] == "R004:normal"
    adj = cost_adjustment({"state": "low", "half_life_d": 6.6, "module_state": "OK"},
                          _base_cost())
    assert adj["impact_bps"] == 3.0 * 0.9
    assert adj["spread_bps"] == 2.0 * 0.95
    assert adj["trade_ok"] is True and adj["tag"] == "R004:low"


def test_cost_interface_unknown_restrictive():
    rsv = {"state": "extreme", "half_life_d": 34.3, "module_state": "UNKNOWN"}
    adj = cost_adjustment(rsv, _base_cost())
    assert adj["trade_ok"] is False
    assert adj["size_mult"] == 0.5
    assert adj["impact_bps"] == 3.0 * 1.5
    assert adj["tag"] == "R004:extreme:unknown-restrictive"
