"""Acceptance tests for R005 - Jump regime (discontinuity state).

Template v1.0.0. Reference implementation of the chapter's normative formula
(§R2): BNS jump-share J = 1 - BV/RV with hysteresis state machine, Lee-Mykland
jump-count auxiliary, corporate-action adj_flag contract, F1-F5 fail-safes.

Run: python3 -m pytest modules/tests/test_R005.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R005_tape.csv"
EXPECTED = FIX / "R005_expected.csv"
TAPE_HYS = FIX / "R005_tape_hysteresis.csv"
EXPECTED_HYS = FIX / "R005_expected_hysteresis.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['diffusion', 'jumpy', 'jump_dominated', 'degenerate',
                'warming', 'missing', 'invalid', 'unadjusted']
BOUNDS = (0.0, 1.0)  # mathematical bounds of the indicator value (F2)
DUAL_MODE = "abs"  # rel | abs | sign | state
DUAL_TOL = 0.1  # dual-estimator agreement tolerance [example]
ESTIMATOR_VERSION = "1.1.0"
# Gumbel 1%-quantile for the Lee-Mykland normalized max statistic:
# c = -ln(-ln(1 - alpha)), alpha = 0.01 -> 4.6001 [documented] (Lee & Mykland 2008, RFS 21(6))
GUMBEL_1PCT = -math.log(-math.log(1.0 - 0.01))


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _jump_share(rs):
    """BNS jump variance share J = 1 - BV/RV [documented]."""
    n = len(rs)
    if n < 2:
        return float("nan")
    rv = sum(x * x for x in rs)
    bv = (math.pi / 2) * sum(abs(rs[i] * rs[i - 1]) for i in range(1, n))
    if rv <= 0:
        return float("nan")
    return max(0.0, min(1.0, 1.0 - bv / rv))


def _lm_jumps(rs, threshold):
    """Lee-Mykland skeleton: local vol from neighbor |r|, threshold [default]."""
    jumps = []
    for i in range(len(rs)):
        nb = [abs(rs[j]) for j in (i - 2, i - 1, i + 1, i + 2) if 0 <= j < len(rs)]
        if not nb:
            continue
        sig = _mean(nb) * math.sqrt(math.pi / 2)
        if sig > 1e-12 and abs(rs[i]) / sig > threshold:
            jumps.append(i)
    return jumps


def label_state(J, prev, cfg):
    """Normative hysteresis state machine (§R2). Bands: lo = jumpy_entry,
    hi = jump_share_extreme, hysteresis = h, all [default]."""
    if not math.isfinite(J):
        return "degenerate"
    lo, hi, h = cfg.jumpy_entry, cfg.jump_share_extreme, cfg.hysteresis
    if prev in (None, "warming", "diffusion"):
        if J > hi:
            return "jump_dominated"
        if J >= lo:
            return "jumpy"
        return "diffusion"
    if prev == "jumpy":
        if J > hi:
            return "jump_dominated"
        if J < lo - h:
            return "diffusion"
        return "jumpy"
    if prev == "jump_dominated":
        if J <= hi - h:
            return "jumpy" if J >= lo - h else "diffusion"
        return "jump_dominated"
    raise ValueError(prev)


def stateless_label(J, cfg):
    """Label without hysteresis (used to prove the hysteresis holds are real)."""
    if not math.isfinite(J):
        return "degenerate"
    return ("diffusion" if J < cfg.jumpy_entry
            else ("jumpy" if J <= cfg.jump_share_extreme else "jump_dominated"))


# ============================ R005 ===========================
@dataclass
class Config:
    lm_threshold: float = 4.5      # [default] skeleton LM threshold (≈ GUMBEL_1PCT)
    lm_alpha: float = 0.01         # [default] LM test size
    jumpy_entry: float = 0.10      # [default] J >= lo -> jumpy
    jump_share_extreme: float = 0.25  # [default] J > hi -> jump_dominated
    hysteresis: float = 0.05       # [default] exit band offset
    min_bars: int = 10             # [default] warm-up bars


def primary_indicator(rows, cfg):
    """Causal reference implementation: recomputes the full label path over the
    prefix (deterministic; no state carried between calls) and returns the last
    bar's result. Corporate-action contract: every bar must be split-adjusted."""
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "vintage": "synthetic"}
    if any("r" not in r or not math.isfinite(r["r"]) for r in rows):
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1].get("event_ts", 0), "vintage": "synthetic"}
    rs = [r["r"] for r in rows]
    if any(r.get("adj_flag") != "split_adjusted" for r in rows):
        return {"value": float("nan"), "state": "unadjusted", "module_state": "DEGRADED",
                "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}
    if len(rows) < cfg.min_bars:
        return {"value": float("nan"), "state": "warming", "module_state": "DEGRADED",
                "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}
    J = _jump_share(rs)
    if not math.isfinite(J):  # F2: non-finite value -> UNKNOWN
        return {"value": J, "state": "degenerate", "module_state": "UNKNOWN",
                "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}
    prev = "diffusion"
    for k in range(cfg.min_bars, len(rows) + 1):
        prev = label_state(_jump_share(rs[:k]), prev, cfg)
    return {"value": J, "state": prev, "module_state": "OK",
            "computed_at": rows[-1]["event_ts"], "vintage": "synthetic",
            "n_jumps": len(_lm_jumps(rs, cfg.lm_threshold))}


def second_estimator(rows, cfg):
    """Verifier: BNS J on the second half of the window."""
    rows = list(rows)
    rs = [r["r"] for r in rows]
    half = rs[len(rs) // 2:]
    J2 = _jump_share(half)
    return {"value": J2, "state": stateless_label(J2, cfg),
            "computed_at": rows[-1]["event_ts"] if rows else 0}


primary_indicator_fn = primary_indicator
second_estimator_fn = second_estimator

F2_POISON_TAPE = [
    {"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i, "r": 0.0,
     "adj_flag": "split_adjusted"}
    for i in range(12)
]  # zero variance -> J = NaN -> F2 non-finite -> UNKNOWN


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


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label, e.g. "jumpy"
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
        return RegimeState("R005", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R005", "out_of_bounds", v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F3: dual-estimator agreement within DUAL_TOL (abs mode) [example]
    s = second_estimator(rows, cfg)
    agree = within_tolerance(v, s["value"], DUAL_MODE, DUAL_TOL)
    if not agree:
        return RegimeState("R005", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R005", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R005", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


# ------------------------------------------------------------------- tests
FIXTURE_PAIRS = [(TAPE, EXPECTED), (TAPE_HYS, EXPECTED_HYS)]


def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSVs."""
    cfg = Config()
    for tpath, epath in FIXTURE_PAIRS:
        evs = tape(tpath)
        exp = {int(r["bar"]): r for r in load_csv(epath)}
        for i in range(len(evs)):
            r = primary_indicator(evs[: i + 1], cfg)
            want = exp[i + 1]
            wv = float(want["exp_value"])
            if math.isnan(wv):
                assert math.isnan(r["value"]), (tpath, i)
            else:
                assert abs(r["value"] - wv) < TOL, (tpath, i)
            assert r["state"] == want["exp_state"], (tpath, i)
            assert r["computed_at"] == int(want["exp_computed_at"]), (tpath, i)
            assert r["module_state"] == want["exp_module_state"], (tpath, i)


def test_hysteresis_state_transitions():
    """Canonical hysteresis path on the hysteresis fixture:
    diffusion -> jumpy -> jump_dominated -> jumpy -> diffusion, with
    hysteresis holds that a stateless label would exit early."""
    cfg = Config()
    evs = tape(TAPE_HYS)
    per_bar = [primary_indicator(evs[: i + 1], cfg) for i in range(len(evs))]
    st = lambda b: per_bar[b - 1]["state"]
    J = lambda b: per_bar[b - 1]["value"]
    # entry path
    assert st(10) == "diffusion"
    assert st(11) == "jumpy" and st(12) == "jumpy"      # 0.05 <= J < 0.10: hysteresis hold
    assert st(13) == "jump_dominated"
    # upper hysteresis hold: 0.20 < J <= 0.25 while jump_dominated
    for b in range(42, 48):
        assert st(b) == "jump_dominated", b
        assert 0.20 < J(b) <= 0.25, (b, J(b))
        assert stateless_label(J(b), cfg) == "jumpy", (b,)  # stateless would exit
    # exit path
    assert st(54) == "jumpy"
    for b in range(84, 89):                            # 0.05 <= J < 0.10: hysteresis hold
        assert st(b) == "jumpy", b
        assert 0.05 <= J(b) < 0.10, (b, J(b))
        assert stateless_label(J(b), cfg) == "diffusion", (b,)
    assert st(102) == "diffusion"


def test_label_boundary_values():
    """Exact band edges: entry inclusive, domination strictly greater,
    exits inclusive on the hysteresis-offset band."""
    cfg = Config()
    d, jy, dom = "diffusion", "jumpy", "jump_dominated"
    lo, hi, h = cfg.jumpy_entry, cfg.jump_share_extreme, cfg.hysteresis
    assert label_state(lo, d, cfg) == jy            # J == 0.10 -> jumpy
    assert label_state(lo - 1e-12, d, cfg) == d     # just under -> diffusion
    assert label_state(hi, d, cfg) == jy            # J == 0.25 -> jumpy (strict >)
    assert label_state(hi + 1e-12, d, cfg) == dom   # just over -> jump_dominated
    assert label_state(hi - h, dom, cfg) == jy     # exit edge inclusive
    assert label_state(hi - h + 1e-9, dom, cfg) == dom  # just inside -> hold
    assert label_state(lo - h, jy, cfg) == jy      # lower hold edge inclusive
    assert label_state(lo - h - 1e-9, jy, cfg) == d  # just under -> diffusion
    assert label_state(float("nan"), d, cfg) == "degenerate"


def test_gumbel_critical_value_pin():
    """Lee-Mykland normalized threshold: Gumbel 1%-quantile = 4.6001 [documented];
    the skeleton default 4.5 [default] is that value rounded."""
    assert abs(GUMBEL_1PCT - 4.6001) < 1e-3
    assert abs(Config().lm_threshold - GUMBEL_1PCT) < 0.15


def test_corporate_action_contract():
    """Unadjusted closes masquerade as jumps: adj_flag != 'split_adjusted'
    withholds the label (DEGRADED), never a jump call."""
    cfg = Config()
    evs = tape()
    bad = [dict(r, adj_flag="unadjusted") for r in evs]
    r = primary_indicator(bad, cfg)
    assert r["module_state"] == "DEGRADED" and r["state"] == "unadjusted"
    mixed = [dict(r) for r in evs]
    mixed[10]["adj_flag"] = "unadjusted"  # single unadjusted bar poisons the window
    assert primary_indicator(mixed, cfg)["module_state"] == "DEGRADED"


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R005"
    assert rsv.state in STATE_LABELS
    assert math.isfinite(rsv.value) and BOUNDS[0] <= rsv.value <= BOUNDS[1]
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. Assert label_ts > indicator_ts for the earliest trade."""
    for tpath, _ in FIXTURE_PAIRS:
        evs = tape(tpath)
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


def test_F2_bounds_violation_unknown():
    rsv = detect(F2_POISON_TAPE, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = tape()
    orig = mod.second_estimator
    p0 = primary_indicator(evs, Config())["value"]
    bad_val = -1e9 if (p0 >= 0) else 1e9  # opposite sign: disagrees in every mode
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
    """Sentinel vs Verifier agree within tolerance on both fixtures."""
    for tpath, _ in FIXTURE_PAIRS:
        evs = tape(tpath)
        cfg = Config()
        r = primary_indicator(evs, cfg)
        s = second_estimator(evs, cfg)
        assert within_tolerance(r["value"], s["value"], DUAL_MODE, DUAL_TOL), (tpath, r, s)
        assert detect(evs, cfg).module_state == "OK", tpath
