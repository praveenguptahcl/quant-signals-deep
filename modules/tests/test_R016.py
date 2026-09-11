"""Acceptance tests for R016 - Fragmentation / off-exchange regime.

Template v1.0.0. Reference implementation of the chapter's normative detector:
trailing-window mean of per-bar OffEx with entry/exit hysteresis, bar masking
(zero-total / halted bars excluded, never interpolated), warm-up DEGRADED,
F1-F5 fail-safes, and dual-estimator agreement (mean-of-ratios vs
aggregate-share ratio).

Run: python3 -m pytest modules/tests/test_R016.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R016_tape.csv"
EXPECTED = FIX / "R016_expected.csv"

TOL = 1e-9            # float tolerance [default]
CADENCE_S = 604800    # indicator cadence in seconds [default]
NS = 1_000_000_000
BOUNDS = (0.0, 1.0)   # mathematical bounds of the indicator value (F2)
DUAL_TOL = 0.05       # abs tolerance, mean-of-ratios vs aggregate ratio [default]
ESTIMATOR_VERSION = "1.0.0"
STATE_LABELS = ["lit_dominated", "normal", "dark_dominated",
                "warming", "undefined", "missing", "invalid"]


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label
    value: float          # indicator value
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


@dataclass
class Config:
    window_bars: int = 10       # trailing window for v [default]
    warmup_bars: int = 5        # valid bars before OK label [default]
    dark_entry: float = 0.45    # enter dark only if v > this, strictly [calibrate]
    dark_exit: float = 0.43     # exit dark only if v < this, strictly [calibrate]
    lit_entry: float = 0.35     # enter lit only if v < this, strictly [calibrate]
    lit_exit: float = 0.37      # exit lit only if v > this, strictly [calibrate]
    dual_tol: float = DUAL_TOL


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


def _masked(r):
    """Zero-total or halted bars are masked: excluded, never interpolated."""
    if r.get("halt"):
        return True
    lit, trf = r.get("lit"), r.get("trf")
    return lit is None or trf is None or (lit + trf) == 0


def primary_indicator(rows, cfg):
    """Sentinel: trailing-window mean of per-bar OfEx; warm-up -> DEGRADED."""
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing",
                "module_state": "UNKNOWN", "computed_at": 0, "vintage": "synthetic"}
    if any(r.get("lit") is not None and r.get("lit") < 0 or
           r.get("trf") is not None and r.get("trf") < 0 for r in rows):
        return {"value": float("nan"), "state": "invalid",
                "module_state": "UNKNOWN", "computed_at": rows[-1].get("event_ts", 0),
                "vintage": "synthetic"}
    vals = [r["trf"] / (r["lit"] + r["trf"]) for r in rows if not _masked(r)]
    if not vals:
        # F1: no usable bars at all (all missing / zero-total / halted)
        return {"value": float("nan"), "state": "missing",
                "module_state": "UNKNOWN", "computed_at": rows[-1].get("event_ts", 0),
                "vintage": "synthetic"}
    if len(vals) < cfg.warmup_bars:
        v = sum(vals) / len(vals)
        return {"value": v, "state": "warming", "module_state": "DEGRADED",
                "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}
    win = vals[-cfg.window_bars:]
    v = sum(win) / len(win)
    return {"value": v, "state": "n/a", "module_state": "OK",
            "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}


def transition(prev, v, cfg):
    """Hysteresis state machine: entry thresholds are strict; exit uses the
    wider band so labels do not flap at the boundary."""
    if prev == "dark_dominated":
        return "normal" if v < cfg.dark_exit else "dark_dominated"
    if prev == "lit_dominated":
        return "normal" if v > cfg.lit_exit else "lit_dominated"
    if v > cfg.dark_entry:
        return "dark_dominated"
    if v < cfg.lit_entry:
        return "lit_dominated"
    return "normal"


def second_estimator(rows, cfg):
    """Verifier: aggregate share ratio sum(V_trf)/sum(V_total) over the same
    unmasked window (FINRA's published-aggregate convention)."""
    rows = list(rows)
    vals = [(r["lit"], r["trf"]) for r in rows if not _masked(r)]
    win = vals[-cfg.window_bars:] if vals else []
    tot = sum(l + t for l, t in win)
    v = sum(t for _, t in win) / tot if tot > 0 else float("nan")
    return {"value": v, "state": "n/a",
            "computed_at": rows[-1]["event_ts"] if rows else 0}


def detect(rows, cfg, now_ns=None, select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState — reference implementation
    with F1-F5 fail-safes wired in (Appendix f v1.0.0)."""
    rows = list(rows)
    r = primary_indicator(rows, cfg)
    if r["module_state"] == "DEGRADED":
        return RegimeState("R016", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "DEGRADED")
    if r["module_state"] != "OK":
        return RegimeState("R016", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R016", "out_of_bounds", v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # apply hysteresis across the causal state path
    state = None
    for i in range(len(rows)):
        p = primary_indicator(rows[: i + 1], cfg)
        if p["module_state"] != "OK":
            continue
        state = transition(state, p["value"], cfg)
    # F3: dual-estimator agreement (abs tolerance)
    s = second_estimator(rows, cfg)
    if not (math.isfinite(v) and math.isfinite(s["value"])
            and abs(v - s["value"]) <= cfg.dual_tol):
        return RegimeState("R016", state, v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R016", state, v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R016", state, v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


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


def _synth_tape(ofex_list, ts0=1_000_000_000, total=60.0, step=86_400_000_000_000):
    rows = []
    for i, ofex in enumerate(ofex_list):
        ts = ts0 + i * step
        # round to 10 dp so the stored (lit, trf) legs are exact decimals;
        # the ratio then recomputes to the same double everywhere
        lit, trf = round(total * (1 - ofex), 10), round(total * ofex, 10)
        rows.append({"bar": i + 1, "event_ts": ts, "asof_ts": ts + 3_600_000_000_000,
                     "lit": lit, "trf": trf})
    return rows


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Causal recompute of each bar matches expected CSV incl. hysteresis states."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = Config()
    for i in range(len(evs)):
        p = primary_indicator(evs[: i + 1], cfg)
        want = exp[i + 1]
        assert abs(p["value"] - float(want["exp_value"])) < TOL, i
        assert p["computed_at"] == int(want["exp_computed_at"]), i
        assert p["module_state"] == want["exp_module_state"], i
    # states come from the hysteresis path: check via full detect at each prefix
    for i in (5, 9, 14, 15, 18):
        rsv = detect(evs[:i], cfg)
        assert rsv.state == exp[i]["exp_state"], (i, rsv.state, exp[i]["exp_state"])


def test_hysteresis_transitions_pinned():
    """Exit bands are wider than entry: no flapping at the boundary."""
    cfg = Config()
    evs = tape()
    r14 = detect(evs[:14], cfg)   # v = 0.438: below entry, above exit -> stays dark
    assert abs(r14.value - 0.438) < TOL and r14.state == "dark_dominated"
    r15 = detect(evs[:15], cfg)   # v = 0.425: below dark_exit -> normal
    assert abs(r15.value - 0.425) < TOL and r15.state == "normal"
    r17 = detect(evs[:17], cfg)   # v = 0.355: above lit_entry -> stays normal
    assert abs(r17.value - 0.355) < TOL and r17.state == "normal"
    r18 = detect(evs[:18], cfg)   # v = 0.320: below lit_entry -> lit_dominated
    assert abs(r18.value - 0.320) < TOL and r18.state == "lit_dominated"


def test_boundary_values_no_spurious_entry():
    """Strict entry/exit: a value exactly on a cut keeps the old state.
    Pinned on transition() directly (windowed means can drift 1 ulp, so the
    strictness contract lives in the hysteresis function, not float equality
    of the tape path)."""
    cfg = Config()
    assert transition("normal", 0.45, cfg) == "normal"            # entry needs strictly greater
    assert transition("normal", 0.4500000001, cfg) == "dark_dominated"
    assert transition("dark_dominated", 0.43, cfg) == "dark_dominated"  # exit needs strictly less
    assert transition("dark_dominated", 0.4299999999, cfg) == "normal"
    assert transition("normal", 0.35, cfg) == "normal"           # lit entry needs strictly less
    assert transition("normal", 0.3499999999, cfg) == "lit_dominated"
    assert transition("lit_dominated", 0.37, cfg) == "lit_dominated"    # lit exit needs strictly greater
    assert transition("lit_dominated", 0.3700000001, cfg) == "normal"


def test_warmup_withholds_label():
    """< warmup valid bars -> DEGRADED, label withheld, never UNKNOWN-as-benign."""
    cfg = Config()
    evs = tape()
    for i in range(1, 5):
        rsv = detect(evs[:i], cfg)
        assert rsv.module_state == "DEGRADED", i
        assert rsv.state == "warming", i
    assert detect(evs[:5], cfg).module_state == "OK"


def test_missing_bar_masked_not_interpolated():
    """Zero-total bar is excluded from the window; the path never sees NaN."""
    cfg = Config()
    evs = _synth_tape([0.40] * 8)
    poisoned = evs[:4] + [{"bar": 99, "event_ts": 4_000_000_001, "asof_ts": 4_000_000_002,
                           "lit": 0.0, "trf": 0.0}] + evs[4:]
    rsv = detect(poisoned, cfg)
    assert rsv.module_state == "OK" and math.isfinite(rsv.value)
    assert abs(rsv.value - 0.40) < TOL  # masked bar contributes nothing


def test_halted_bar_discarded_across_reopen():
    """Halted bars are dropped; they must not leak into the trailing window."""
    cfg = Config()
    evs = _synth_tape([0.40] * 8)
    halted = evs[:4] + [dict(evs[4], halt=True)] + evs[5:]
    rsv = detect(halted, cfg)
    assert rsv.module_state == "OK" and abs(rsv.value - 0.40) < TOL


def test_split_invariance():
    """2:1 split doubles both legs -> OffEx ratio (and the label path) unchanged."""
    cfg = Config()
    pre = _synth_tape([0.42] * 12, total=60.0)
    post = _synth_tape([0.42] * 12, total=120.0)   # volumes doubled, ratio identical
    r1, r2 = detect(pre, cfg), detect(post, cfg)
    assert r1.state == r2.state and abs(r1.value - r2.value) < TOL


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R016"
    assert rsv.state in STATE_LABELS
    assert math.isfinite(rsv.value) and BOUNDS[0] <= rsv.value <= BOUNDS[1]
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. label_ts == indicator_ts; earliest trade ts > label_ts."""
    evs = tape()
    cfg = Config()
    for i in range(5, len(evs) - 1):
        label = detect(evs[: i + 1], cfg)
        assert label.computed_at == evs[i]["event_ts"]
        assert evs[i + 1]["event_ts"] > label.computed_at
    # appending a future breakout bar must not move the label stamped at t
    label_t = detect(evs[:-1], cfg)
    assert label_t.computed_at == evs[-2]["event_ts"]


def test_F1_missing_input_unknown():
    assert detect([], Config()).module_state == "UNKNOWN"
    bad = [dict(event_ts=1, asof_ts=2)]  # missing indicator fields
    assert detect(bad, Config()).module_state == "UNKNOWN"
    neg = [{"bar": 1, "event_ts": 1, "asof_ts": 2, "lit": -1.0, "trf": 5.0}]
    assert detect(neg, Config()).module_state == "UNKNOWN"


def test_F2_all_masked_unknown():
    """Every bar masked (zero totals) -> no finite indicator -> UNKNOWN."""
    rows = [{"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i,
             "lit": 0.0, "trf": 0.0} for i in range(12)]
    rsv = detect(rows, Config())
    assert rsv.module_state == "UNKNOWN"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = tape()
    orig = mod.second_estimator
    try:
        mod.second_estimator = lambda rows, cfg: {"value": 0.99, "state": "n/a",
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
    """Sentinel (mean of ratios) vs Verifier (aggregate share ratio) agree
    within tolerance on the fixture."""
    evs = tape()
    cfg = Config()
    r = primary_indicator(evs, cfg)
    s = second_estimator(evs, cfg)
    assert math.isfinite(r["value"]) and math.isfinite(s["value"])
    assert abs(r["value"] - s["value"]) <= cfg.dual_tol, (r, s)
    assert detect(evs, cfg).module_state == "OK"
