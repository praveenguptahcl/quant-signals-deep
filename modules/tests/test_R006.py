"""Acceptance tests for R006 - Vol-of-vol regime.

Template v1.0.0. Reference implementation of the chapter's normative
detection (hysteresis state machine, §R2) with F1-F5 fail-safes wired in.
The fixture tape pins state transitions, hysteresis re-tests, and boundary
values; expected.csv is the causal recompute of the tape.

Run: python3 -m pytest modules/tests/test_R006.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R006_tape.csv"
EXPECTED = FIX / "R006_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['calm', 'normal', 'stressed', 'unstable', 'warming', 'missing', 'invalid']
BOUNDS = (0.0, 300.0)  # mathematical bounds of the VVIX indicator value (F2) [default]
DUAL_MODE = "state"  # rel | abs | sign | state
DUAL_TOL = None
ESTIMATOR_VERSION = "1.0.0"

# Config defaults mirrored from §R0.2 (fixed-band mode [default])
CFG_T_CALM = 85.0     # vvix_calm [default]
CFG_T_STRESS = 110.0  # vvix_stressed [default]
CFG_HB = 5.0          # hysteresis_band_pts [default]
CFG_WARMUP = 21       # warmup_bars [default] (20 changes + 1)
CFG_HIST_WINDOW = 20  # hist_window_days [default]
# verifier cuts for the historical-VoV leg [default]
VER_CALM = 0.05
VER_STRESS = 0.12


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


def transition(prev, v, t_calm=CFG_T_CALM, t_stress=CFG_T_STRESS, hb=CFG_HB):
    """Normative hysteresis state machine (§R2). Pure function of the
    previous label and the current VVIX print — no lookahead by construction."""
    if prev == "stressed":
        return "normal" if v < t_stress - hb else "stressed"
    if prev == "calm":
        if v > t_stress:
            return "stressed"
        if v > t_calm + hb:
            return "normal"
        return "calm"
    # prev == "normal" (initial prior [default])
    if v > t_stress:
        return "stressed"
    if v <= t_calm:
        return "calm"
    return "normal"


def primary_indicator_r006(rows, cfg):
    """Sentinel leg: causal replay of the hysteresis machine over usable
    (non-masked) bars. Returns the last bar's label."""
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "vintage": "synthetic"}
    usable = [r for r in rows
              if all(k in r for k in ("vvix", "iv30"))
              and isinstance(r["vvix"], (int, float)) and math.isfinite(r["vvix"])]
    if not usable:
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1].get("event_ts", 0), "vintage": "synthetic"}
    prev = "normal"  # initial prior [default]
    for r in usable:
        prev = transition(prev, r["vvix"])
    last = usable[-1]
    return {"value": last["vvix"], "state": prev, "module_state": "OK",
            "computed_at": last["event_ts"], "vintage": "synthetic"}


def second_estimator_r006(rows, cfg):
    """Verifier leg: historical VoV = stdev(dIV30, 20d) / mean(IV30) [documented
    construction], three-band cut. Needs warmup_bars; else 'warming'."""
    rows = list(rows)
    usable = [r for r in rows
              if all(k in r for k in ("iv30",)) and isinstance(r["iv30"], (int, float))
              and math.isfinite(r["iv30"])]
    if len(usable) < CFG_WARMUP:
        return {"value": float("nan"), "state": "warming",
                "computed_at": rows[-1]["event_ts"] if rows else 0}
    iv = [r["iv30"] for r in usable]
    chg = [iv[i] - iv[i - 1] for i in range(1, len(iv))]
    vov = _stdev(chg[-CFG_HIST_WINDOW:], ddof=1) / _mean(iv[-CFG_HIST_WINDOW:])
    state = "calm" if vov < VER_CALM else ("normal" if vov <= VER_STRESS else "stressed")
    return {"value": vov, "state": state, "computed_at": usable[-1]["event_ts"]}


primary_indicator = primary_indicator_r006
second_estimator = second_estimator_r006


F2_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1001, "vvix": 500.0, "iv30": 0.20}
]  # VVIX 500 outside bounds (0, 300)


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
    state: str            # regime label, e.g. "stressed"
    value: float          # indicator value
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest usable input bar)
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
        return RegimeState("R006", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R006", "out_of_bounds", v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F3: dual-estimator agreement (state mode: same label)
    s = second_estimator(rows, cfg)
    if DUAL_MODE == "state":
        agree = (r["state"] == s["state"])
    else:
        agree = within_tolerance(v, s["value"], DUAL_MODE, DUAL_TOL)
    if not agree:
        return RegimeState("R006", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence [default]
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R006", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R006", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = Config()
    assert len(evs) == len(exp) == 35, "tape and expected must cover 35 bars"
    for i in range(len(evs)):
        r = primary_indicator(evs[: i + 1], cfg)
        want = exp[i + 1]
        wv = float(want["exp_value"])
        assert abs(r["value"] - wv) < TOL, i
        assert r["state"] == want["exp_state"], i
        assert r["computed_at"] == int(want["exp_computed_at"]), i
        assert r["module_state"] == want["exp_module_state"], i


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R006"
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
        assert earliest_trade_ts > label.computed_at, f"lookahead at bar {i}"
    # appending a future breakout bar must not move the label stamped at t
    label_t = detect(evs[:-1], cfg)
    assert label_t.computed_at == evs[-2]["event_ts"]


def test_F1_missing_input_unknown():
    assert detect([], Config()).module_state == "UNKNOWN"
    bad = [dict(event_ts=1, asof_ts=2)]  # missing indicator fields
    assert detect(bad, Config()).module_state == "UNKNOWN"
    # masked bar: vvix missing on one bar -> hold last label, no interpolation
    evs = tape()
    gapped = [dict(r) for r in evs]
    gapped[10]["vvix"] = float("nan")
    rsv = detect(gapped, Config())
    assert rsv.computed_at == evs[-1]["event_ts"]
    assert rsv.state == detect(evs, Config()).state


def test_F2_bounds_violation_unknown():
    rsv = detect(F2_POISON_TAPE, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = tape()
    orig = mod.second_estimator
    try:
        mod.second_estimator = lambda rows, cfg: {"value": 9e-9, "state": "bogus",
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
    """Sentinel vs Verifier agree on the fixture's final label."""
    evs = tape()
    cfg = Config()
    r = primary_indicator(evs, cfg)
    s = second_estimator(evs, cfg)
    assert r["state"] == s["state"] == "stressed", (r, s)
    assert detect(evs, cfg).module_state == "OK"


# --------------------------------------- hysteresis & boundary acceptance
def test_hysteresis_stress_hold():
    """vvix in [105, 110] while stressed holds the stressed label (no chatter)."""
    assert transition("stressed", 109.0) == "stressed"
    assert transition("stressed", 106.0) == "stressed"
    assert transition("stressed", 110.0) == "stressed"
    assert transition("stressed", 104.9) == "normal"


def test_hysteresis_calm_hold():
    """vvix in (85, 90] while calm holds the calm label (no chatter)."""
    assert transition("calm", 87.0) == "calm"
    assert transition("calm", 90.0) == "calm"
    assert transition("calm", 90.1) == "normal"
    assert transition("calm", 111.0) == "stressed"


def test_boundary_values():
    """Exact band edges resolve per the normative inclusive/exclusive rules."""
    assert transition("normal", 85.0) == "calm"      # calm entry is <= 85
    assert transition("normal", 110.0) == "normal"    # stress entry needs > 110
    assert transition("normal", 110.1) == "stressed"
    assert transition("stressed", 105.0) == "stressed"  # stress exit needs < 105
    assert transition("stressed", 104.9) == "normal"
    assert transition("calm", 90.0) == "calm"        # calm exit needs > 90
    assert transition("calm", 85.0) == "calm"


def test_hysteresis_sequence_on_tape():
    """End-to-end: the tape's labeled transition bars pin hysteresis behavior."""
    evs = tape()
    cfg = Config()
    got = {i + 1: primary_indicator(evs[: i + 1], cfg)["state"] for i in range(len(evs))}
    assert got[7] == "calm"      # 87 while calm -> hold (no hysteresis: would flip)
    assert got[8] == "normal"   # 92 > 90 -> exit calm
    assert got[11] == "normal"   # exactly 110 -> not > 110
    assert got[12] == "calm"     # exactly 85 -> <= 85
    assert got[14] == "calm"     # 89 while calm -> hold
    assert got[18] == "stressed"  # 112 > 110 -> entry
    assert got[22] == "stressed"  # 109 while stressed -> hold
    assert got[23] == "stressed"  # 106 while stressed -> hold
    assert got[24] == "normal"   # 104 < 105 -> exit
    assert got[28] == "calm"     # exactly 90 while calm -> hold
    assert got[32] == "stressed"  # exactly 110 while stressed -> hold


def test_transition_no_lookahead_property():
    """The transition is a pure function of (prev, current print): a future
    breakout bar cannot change any already-emitted label (adversary check)."""
    seq = [78.0, 87.0, 92.0, 110.0, 112.0, 109.0, 104.0]
    labels = []
    prev = "normal"
    for v in seq:
        prev = transition(prev, v)
        labels.append(prev)
    future = [118.0, 125.0, 135.0, 118.0]  # synthetic breakout appended later
    labels2 = []
    prev = "normal"
    for v in seq + future:
        prev = transition(prev, v)
        labels2.append(prev)
    assert labels2[: len(seq)] == labels
