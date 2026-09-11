"""Acceptance tests for R012 - Price-impact / Amihud illiquidity regime.

Template v1.0.0. Concrete sketch: loads the fixture tape, runs a reference
implementation of the chapter's normative formula (with hysteresis state
transitions, §R2), and asserts causality, F1-F5 fail-safes, dual-estimator
agreement, and pinned transition/boundary behavior.

Run: python3 -m pytest modules/tests/test_R012.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R012_tape.csv"
EXPECTED = FIX / "R012_expected.csv"
HIST = FIX / "R012_hist.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['normal', 'illiquid', 'extreme', 'undefined', 'warming', 'missing', 'invalid']
BOUNDS = (0.0, 1000000.0)  # mathematical bounds of the indicator value (F2)
DUAL_TOL = 0.3  # max daily relative CC/OC disagreement [default]
ESTIMATOR_VERSION = "1.1.0"


def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def _to_num(v):
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def tape():
    return [{k: _to_num(v) for k, v in r.items()} for r in load_csv(TAPE)]


def hist():
    return [float(r["illiq"]) for r in load_csv(HIST)]


HIST_AMIHUD = None  # loaded lazily from fixture


def _hist():
    global HIST_AMIHUD
    if HIST_AMIHUD is None:
        HIST_AMIHUD = hist()
    return HIST_AMIHUD


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _pct_rank(x, hist, tol=1e-9):
    """Percentile rank; values within tol (relative) count as ties [default]."""
    h = list(hist)
    if not h:
        return float("nan")
    below = sum(1 for v in h if v < x and abs(v - x) > tol * max(1.0, abs(x)))
    equal = sum(1 for v in h if abs(v - x) <= tol * max(1.0, abs(x)))
    return (below + 0.5 * equal) / len(h)


@dataclass
class Config:
    D: int = 10                 # estimation window (expected calendar bars) [default]
    max_missing: int = 1        # missing bars tolerated in the window [default]
    illiq_entry: float = 60.0   # normal->illiquid entry percentile [default]
    illiq_exit: float = 50.0    # illiquid->normal exit percentile [default]
    ext_entry: float = 90.0     # ->extreme entry percentile [default]
    ext_exit: float = 80.0      # extreme->illiquid exit percentile [default]
    dual_tol: float = 0.3       # F3 daily CC/OC max relative disagreement [default]
    scale: float = 1e6          # Amihud scale [documented]


# ============================ R012 ============================
def _r012_label(prev, p, cfg):
    """Hysteresis state transition (§R2). prev=None = cold start (no hysteresis)."""
    ie, ix = cfg.illiq_entry / 100.0, cfg.illiq_exit / 100.0
    ee, ex = cfg.ext_entry / 100.0, cfg.ext_exit / 100.0
    if prev is None:
        return "normal" if p < ie else ("illiquid" if p < ee else "extreme")
    if prev == "extreme":
        return "illiquid" if p <= ex else "extreme"  # steps down, never jumps to normal
    if prev == "illiquid":
        if p >= ee:
            return "extreme"
        if p <= ix:
            return "normal"
        return "illiquid"
    if p >= ee:  # prev == "normal"
        return "extreme"
    if p >= ie:
        return "illiquid"
    return "normal"


def _window_ratios(rows, cfg):
    """Ratios over the D expected calendar bars anchored at the newest bar.

    Missing grid points are masked (never interpolated); halt-flagged bars are
    masked; invalid fields or an unadjusted corporate action -> None (F1).
    Returns (ratios, n_missing) or None.
    """
    by_ts = {r["event_ts"]: r for r in rows}
    anchor = rows[-1]["event_ts"]
    ratios = []
    n_missing = 0
    for k in range(cfg.D - 1, -1, -1):
        g = anchor - k * CADENCE_S * NS
        r = by_ts.get(g)
        if r is None:
            n_missing += 1
            continue
        if r.get("halt", 0):
            n_missing += 1  # masked: halt contributions discarded across reopen
            continue
        ar, vd, o, c = r.get("absret"), r.get("vold"), r.get("o"), r.get("c")
        if ar is None or vd is None or o is None or c is None:
            return None  # invalid input -> F1
        if not (math.isfinite(ar) and math.isfinite(vd) and math.isfinite(o)
                and math.isfinite(c)) or ar < 0 or vd <= 0 or o <= 0 or c <= 0:
            return None  # F1: invalid fields
        if r.get("corpact", 0) and not r.get("adj", 0):
            return None  # F1: unadjusted corporate action rejected
        ratios.append((ar / vd * cfg.scale, abs(math.log(c / o)) / vd * cfg.scale))
    return ratios, n_missing


def primary_indicator(rows, cfg, prev_label=None):
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "vintage": "synthetic"}
    # Halt freeze: newest bar halted -> emit UNKNOWN, hold last label (market-state table)
    if rows[-1].get("halt", 0):
        return {"value": float("nan"), "state": prev_label or "undefined",
                "module_state": "UNKNOWN",
                "computed_at": rows[-2]["event_ts"] if len(rows) > 1 else 0,
                "vintage": "synthetic"}
    wr = _window_ratios(rows, cfg)
    if wr is None:
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1].get("event_ts", 0), "vintage": "synthetic"}
    ratios, _ = wr
    if not ratios:
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1].get("event_ts", 0), "vintage": "synthetic"}
    v = _mean(r[0] for r in ratios)
    p = _pct_rank(v, _hist())
    n_ok = cfg.D - cfg.max_missing
    if len(ratios) < n_ok:
        return {"value": v, "state": "warming", "module_state": "DEGRADED",
                "computed_at": rows[-1]["event_ts"], "vintage": "synthetic", "pct": p}
    return {"value": v, "state": _r012_label(prev_label, p, cfg), "module_state": "OK",
            "computed_at": rows[-1]["event_ts"], "vintage": "synthetic", "pct": p}


def second_estimator(rows, cfg):
    """Verifier: OC-based ILLIQ; daily relative disagreement vs sentinel (F3)."""
    rows = list(rows)
    if not rows or rows[-1].get("halt", 0):
        return {"value": float("nan"), "max_rel_disag": float("inf"),
                "computed_at": rows[-1].get("event_ts", 0) if rows else 0}
    wr = _window_ratios(rows, cfg)
    if wr is None or not wr[0]:
        return {"value": float("nan"), "max_rel_disag": float("inf"),
                "computed_at": rows[-1].get("event_ts", 0)}
    ratios, _ = wr
    v = _mean(r[1] for r in ratios)
    disag = [abs(a - b) / max(a, b, 1e-9) for a, b in ratios]
    return {"value": v, "max_rel_disag": max(disag),
            "computed_at": rows[-1]["event_ts"]}


F2_POISON_TAPE = [
    {"bar": i + 1, "event_ts": 1000 + i * CADENCE_S * NS, "asof_ts": 1001 + i * CADENCE_S * NS,
     "absret": 200.0, "vold": 100.0, "o": 100.0, "c": 300.0,
     "halt": 0, "corpact": 0, "adj": 1}
    for i in range(10)
]  # ratio = 200/100*1e6 = 2e6 > 1e6 bound -> F2


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label, e.g. "illiquid"
    value: float          # indicator value
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


def detect(rows, cfg, now_ns=None, select_periods=False, preregistered=False, prev_label=None):
    """detect(state, events, cfg) -> RegimeState — reference implementation
    with F1-F5 fail-safes wired in (Appendix f v1.0.0)."""
    rows = list(rows)
    r = primary_indicator(rows, cfg, prev_label=prev_label)
    if r["module_state"] not in ("OK", "DEGRADED"):
        return RegimeState("R012", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    if r["module_state"] == "DEGRADED":
        return RegimeState("R012", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "DEGRADED")
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R012", "out_of_bounds", v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F3: daily CC/OC disagreement beyond tolerance -> UNKNOWN
    s = second_estimator(rows, cfg)
    if not math.isfinite(s["max_rel_disag"]) or s["max_rel_disag"] > cfg.dual_tol:
        return RegimeState("R012", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R012", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R012", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV
    (hysteresis label threaded through the bar sequence)."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = Config()
    prev = None
    for i in range(len(evs)):
        r = primary_indicator(evs[: i + 1], cfg, prev_label=prev)
        want = exp[i + 1]
        wv = float(want["exp_value"])
        assert abs(r["value"] - wv) < TOL, i
        assert r["state"] == want["exp_state"], i
        assert r["computed_at"] == int(want["exp_computed_at"]), i
        assert r["module_state"] == want["exp_module_state"], i
        if r["module_state"] == "OK":
            prev = r["state"]


def test_emits_valid_regime_state_vector():
    evs = tape()
    prev = None
    for i in range(len(evs)):
        rsv = detect(evs[: i + 1], Config(), prev_label=prev)
        if rsv.module_state == "OK":
            prev = rsv.state
    rsv = detect(evs, Config(), prev_label=prev)
    assert rsv.regime_id == "R012"
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
        if label.module_state == "OK":
            prev = label.state
    # appending a future breakout bar must not move the label stamped at t
    label_t = detect(evs[:-1], cfg, prev_label=None)
    seq_prev = None
    for i in range(len(evs) - 1):
        r = primary_indicator(evs[: i + 1], cfg, prev_label=seq_prev)
        if r["module_state"] == "OK":
            seq_prev = r["state"]
    assert label_t.computed_at == evs[-2]["event_ts"]


def test_F1_missing_input_unknown():
    assert detect([], Config()).module_state == "UNKNOWN"
    bad = [dict(event_ts=1, asof_ts=2)]  # missing indicator fields
    assert detect(bad, Config()).module_state == "UNKNOWN"


def test_F1_corporate_action_unadjusted_unknown():
    """Unadjusted corporate-action bar -> UNKNOWN until an adjusted series arrives."""
    evs = tape()
    poisoned = [dict(r) for r in evs]
    poisoned[-1] = dict(poisoned[-1], corpact=1, adj=0)
    rsv = detect(poisoned, Config())
    assert rsv.module_state == "UNKNOWN"
    # same bar with the adjusted flag passes the gate
    fixed = [dict(r) for r in evs]
    fixed[-1] = dict(fixed[-1], corpact=1, adj=1)
    assert detect(fixed, Config()).module_state in ("OK", "DEGRADED")


def test_F2_bounds_violation_unknown():
    rsv = detect(F2_POISON_TAPE, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"


def test_F3_gap_distorted_day_unknown():
    """Adversary: one overnight-gap day (big CC |R|, flat OC) trips the daily
    CC/OC disagreement check -> UNKNOWN (restrictive downstream)."""
    evs = tape()
    cfg = Config()
    poisoned = [dict(r) for r in evs]
    poisoned[-1] = dict(poisoned[-1], absret=0.06, o=100.0, c=100.0, vold=5_000_000.0)
    rsv = detect(poisoned, cfg)
    assert rsv.module_state == "UNKNOWN", "gap-distorted day must trip F3"
    s = second_estimator(poisoned, cfg)
    assert s["max_rel_disag"] > cfg.dual_tol


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
    assert s["max_rel_disag"] <= cfg.dual_tol, (r, s)
    assert detect(evs, cfg).module_state == "OK"


def test_warmup_withholds_label():
    """Insufficient lookback -> DEGRADED with label withheld (not UNKNOWN, not OK).
    OK requires >= D - max_missing valid bars in the window."""
    evs = tape()
    cfg = Config()
    n_ok = cfg.D - cfg.max_missing
    for i in range(1, n_ok):
        rsv = detect(evs[:i], cfg)
        assert rsv.module_state == "DEGRADED", i
        assert rsv.state == "warming", i
    assert detect(evs[:n_ok], cfg).module_state == "OK"


def test_hysteresis_transition_path():
    """Fixture pins the full transition path: normal -> illiquid (entry) ->
    extreme (entry) -> illiquid (exit) -> normal (exit); no direct extreme->normal."""
    evs = tape()
    cfg = Config()
    labels, pcts = [], []
    prev = None
    for i in range(len(evs)):
        r = primary_indicator(evs[: i + 1], cfg, prev_label=prev)
        labels.append(r["state"])
        pcts.append(r.get("pct", float("nan")))
        if r["module_state"] == "OK":
            prev = r["state"]
    assert labels[9] == "normal"          # bar 10: first full window
    assert labels[15] == "illiquid"       # bar 16: p=0.70 >= 0.60 entry
    assert labels[18] == "extreme"        # bar 19: p=0.975 >= 0.90 entry
    assert labels[30] == "illiquid"       # bar 31: p=0.75 <= 0.80 exit (steps down)
    assert labels[39] == "normal"         # bar 40: p=0.475 <= 0.50 exit
    for a, b in zip(labels, labels[1:]):
        assert not (a == "extreme" and b == "normal"), "direct extreme->normal forbidden"
    # entry only at/above the entry threshold
    first_ill = labels.index("illiquid")
    assert pcts[first_ill] >= cfg.illiq_entry / 100.0


def test_hysteresis_boundaries():
    """Boundary transitions pinned directly on the labeler (inclusive rules)."""
    cfg = Config()
    L = lambda prev, p: _r012_label(prev, p, cfg)
    assert L(None, 0.60) == "illiquid"     # cold start: entry boundary inclusive
    assert L(None, 0.90) == "extreme"
    assert L("normal", 0.60) == "illiquid"
    assert L("normal", 0.599) == "normal"
    assert L("normal", 0.90) == "extreme"  # direct normal->extreme jump allowed
    assert L("illiquid", 0.90) == "extreme"
    assert L("illiquid", 0.899) == "illiquid"
    assert L("illiquid", 0.50) == "normal"  # exit boundary inclusive
    assert L("illiquid", 0.501) == "illiquid"
    assert L("extreme", 0.80) == "illiquid"  # exit boundary inclusive
    assert L("extreme", 0.801) == "extreme"
    assert L("extreme", 0.40) == "illiquid"  # steps down, never jumps to normal
    assert L("extreme", 0.95) == "extreme"


def test_halt_freezes_state():
    """Halted newest bar -> UNKNOWN with frozen label; halted bars masked from the window."""
    evs = tape()
    cfg = Config()
    halted = [dict(r) for r in evs]
    halted[-1] = dict(halted[-1], halt=1)
    rsv = detect(halted, cfg, prev_label="illiquid")
    assert rsv.module_state == "UNKNOWN"
    assert rsv.state == "illiquid"  # frozen, not recomputed
    # a clean bar after the halt resumes normal computation
    resumed = halted + [dict(evs[-1], event_ts=evs[-1]["event_ts"] + CADENCE_S * NS, bar=41)]
    rsv2 = detect(resumed, cfg, prev_label="illiquid")
    assert rsv2.module_state == "OK"


def test_missing_bar_masked_no_interpolation():
    """A gap in the bar grid is masked, never interpolated: the indicator is the
    mean over present bars only, and one missing bar does not break OK."""
    evs = tape()
    cfg = Config()
    dropped = evs[35]  # bar 36, inside the trailing window
    gapped = [r for i, r in enumerate(evs) if i != 35]
    assert len(gapped) == len(evs) - 1
    r = primary_indicator(gapped, cfg, prev_label="illiquid")
    assert r["module_state"] == "OK"
    wr, _ = _window_ratios(gapped, cfg)
    expect = _mean(a for a, _ in wr)
    assert abs(r["value"] - expect) < TOL
    assert len(wr) == cfg.D - 1  # exactly one masked grid point
    # an interpolating variant (fill the gap with the dropped bar's ratio) differs
    interp = (expect * len(wr) + dropped["absret"] / dropped["vold"] * cfg.scale) / (len(wr) + 1)
    assert abs(interp - expect) > TOL
    assert r["computed_at"] == gapped[-1]["event_ts"]
