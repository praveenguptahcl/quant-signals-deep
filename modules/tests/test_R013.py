"""Acceptance tests for R013 - Abnormal volume / participation regime.

Template v1.0.0. Concrete sketch: loads the fixture tapes, runs a reference
implementation of the chapter's normative detector (hysteresis state machine,
corporate-action renormalization, F1-F5 fail-safes), and asserts causality,
threshold transitions, boundaries, and the cost interface.

Run: python3 -m pytest modules/tests/test_R013.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R013_tape.csv"
EXPECTED = FIX / "R013_expected.csv"
HYST_TAPE = FIX / "R013_hysteresis_tape.csv"
HYST_EXPECTED = FIX / "R013_hysteresis_expected.csv"
CORPA_TAPE = FIX / "R013_corpa_tape.csv"
CORPA_EXPECTED = FIX / "R013_corpa_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['normal', 'elevated', 'abnormal', 'undefined', 'warming',
                'missing', 'invalid', 'out_of_bounds']
BOUNDS = (-10.0, 20.0)  # mathematical bounds of the indicator value (F2)
DUAL_MODE = "abs"  # rel | abs | sign | state
DUAL_TOL = 1.0
ESTIMATOR_VERSION = "1.0.0"

# ============================ R013 detector ============================
# Normative reference per §R2: z^V_t = (V_t - mu_{t-L..t-1}) / sigma_{t-L..t-1},
# baseline excludes t (no lookahead), split-renormalized, hysteresis labels.


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


@dataclass(frozen=True)
class Config:
    lookback: int = 21          # [default] trailing bars in baseline
    min_warmup: int = 6         # [default] min bars before labels are OK
    elevated_entry_z: float = 2.0   # [default] hysteresis entry
    elevated_exit_z: float = 1.5    # [default] hysteresis exit
    abnormal_entry_z: float = 3.0   # [default] hysteresis entry
    abnormal_exit_z: float = 2.0     # [default] hysteresis exit
    dual_tol: float = 1.0           # [default] abs tolerance, primary vs robust z
    dead_pace_z: float = -1.0       # [default] z floor for dead-pace sizing


def _causal_z(rows, cfg, f=1.0):
    """z of newest bar against the trailing baseline, renormalized by the
    newest bar's split factor f (corporate-action hygiene)."""
    base = [r["vol"] * f for r in rows[:-1]][-cfg.lookback:]
    m, s = _mean(base), _stdev(base)
    if not math.isfinite(m) or not (s > 0):
        return float("nan")
    return (rows[-1]["vol"] - m) / s


def _robust_z(rows, cfg, f=1.0):
    base = sorted(r["vol"] * f for r in rows[:-1])[-cfg.lookback:]
    if not base:
        return float("nan")
    med = base[len(base) // 2]
    mad = sorted(abs(v - med) for v in base)[len(base) // 2]
    scl = 1.4826 * mad
    return (rows[-1]["vol"] - med) / scl if scl > 0 else float("nan")


def hysteresis(prev_state, z, cfg):
    """Hysteresis label transition — normative per §R2. Strict inequalities:
    z exactly on a threshold holds the current state (boundary test)."""
    if prev_state == "abnormal":
        return "elevated" if z < cfg.abnormal_exit_z else "abnormal"
    if prev_state == "elevated":
        if z > cfg.abnormal_entry_z:
            return "abnormal"
        if z < cfg.elevated_exit_z:
            return "normal"
        return "elevated"
    if z > cfg.abnormal_entry_z:
        return "abnormal"
    if z > cfg.elevated_entry_z:
        return "elevated"
    return "normal"


def detect_sequence(rows, cfg, now_ns=None, select_periods=False, preregistered=False):
    """Run the full detector over the tape, threading hysteresis state.
    Returns the final RegimeState."""
    rows = list(rows)
    if not rows:
        return _rsv("missing", float("nan"), 0, "UNKNOWN")
    # F1: invalid input
    if any("vol" not in r or not isinstance(r["vol"], (int, float))
           or not (r["vol"] >= 0) or not math.isfinite(r["vol"]) for r in rows):
        ts = rows[-1].get("event_ts", 0)
        return _rsv("invalid", float("nan"), ts, "UNKNOWN")
    if len(rows) < cfg.min_warmup:
        return _rsv("warming", float("nan"), rows[-1]["event_ts"], "DEGRADED")
    prev = "normal"
    final = None
    for i in range(cfg.min_warmup - 1, len(rows)):
        prefix = rows[: i + 1]
        f = float(prefix[-1].get("split_factor", 1.0) or 1.0)
        z = _causal_z(prefix, cfg, f)
        label = hysteresis(prev, z, cfg) if math.isfinite(z) else "undefined"
        state = "OK"
        if not math.isfinite(z) or not (BOUNDS[0] <= z <= BOUNDS[1]):
            state = "UNKNOWN"  # F2
            label = "undefined" if not math.isfinite(z) else "out_of_bounds"
        elif not within_tolerance(z, _robust_z(prefix, cfg, f), DUAL_MODE, DUAL_TOL):
            state = "UNKNOWN"  # F3: dual-estimator disagreement
        prev = label if label in ("normal", "elevated", "abnormal") else prev
        final = (label, z, state, prefix[-1]["event_ts"])
    label, z, state, computed_at = final
    # F4: staleness
    now = now_ns if now_ns is not None else computed_at + CADENCE_S * NS
    if now - computed_at > 3 * CADENCE_S * NS:
        state = "UNKNOWN"
    # F5
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return _rsv(label, z, computed_at, state)


def _rsv(state, value, computed_at, module_state):
    return RegimeState("R013", state, value, ESTIMATOR_VERSION, "synthetic",
                       computed_at, module_state)


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
    with F1-F5 fail-safes and hysteresis wired in (Appendix f v1.0.0)."""
    return detect_sequence(rows, cfg, now_ns=now_ns, select_periods=select_periods,
                           preregistered=preregistered)


def cost_adjustment(rsv, base):
    """§R5 reference: regime state -> cost-function adjustment."""
    adj = dict(base)
    adj['trade_ok'] = True
    adj['size_mult'] = 1.0
    if rsv.state == 'abnormal':
        adj['slip_mult'] = 1.5      # [example] urgent flow crosses wider spreads
        adj['impact_mult'] = 0.8    # [example] deeper book on heavy participation
        adj['horizon_mult'] = 0.5   # [example] volume clock runs ~2x
    elif rsv.state == 'elevated':
        adj['slip_mult'] = 1.25     # [example]
        adj['impact_mult'] = 0.9    # [example]
        adj['horizon_mult'] = 0.75  # [example]
    else:
        adj['slip_mult'] = 1.0      # [default]
        adj['impact_mult'] = 1.0    # [default]
        adj['horizon_mult'] = 1.0   # [default]
    if math.isfinite(rsv.value) and rsv.value < Config().dead_pace_z:
        adj['size_mult'] = 0.5      # [example] dead pace: no fuel, stand down breakouts
    return adj


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


def _check_expected(tape_rows, expected_path):
    cfg = Config()
    exp = {int(r["bar"]): r for r in load_csv(expected_path)}
    seq_label = "normal"
    for i, row in enumerate(tape_rows):
        prefix = tape_rows[: i + 1]
        want = exp[i + 1]
        if want["exp_module_state"] != "OK":
            r = detect(prefix, cfg)
            assert r.module_state == want["exp_module_state"], (i, r)
            assert r.state == want["exp_state"], (i, r)
            continue
        f = float(row.get("split_factor", 1.0) or 1.0)
        z = _causal_z(prefix, cfg, f)
        wv = float(want["exp_value"])
        assert abs(z - wv) < TOL, (i, z, wv)
        seq_label = hysteresis(seq_label, z, cfg)
        assert seq_label == want["exp_state"], (i, seq_label, want["exp_state"])
        r = detect(prefix, cfg)
        assert r.state == want["exp_state"], (i, r)
        assert r.computed_at == int(want["exp_computed_at"]), (i, r)
        assert r.module_state == "OK", (i, r)


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    _check_expected(tape(), EXPECTED)


def test_hysteresis_tape_recomputes_to_expected():
    """Hysteresis transitions pinned: elevated -> abnormal -> abnormal ->
    elevated -> normal across bars 10-14."""
    _check_expected(tape(HYST_TAPE), HYST_EXPECTED)


def test_corpa_tape_recomputes_to_expected():
    """2:1 split at bar 10: baseline renormalized x2 -> z ~ 0.1 normal, not a
    false abnormal from the doubled raw share print."""
    _check_expected(tape(CORPA_TAPE), CORPA_EXPECTED)


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R013"
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
    for i in range(cfg.min_warmup - 1, len(evs) - 1):
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
    bad_neg = [dict(event_ts=i, asof_ts=i + 1, vol=-1.0) for i in range(8)]
    assert detect(bad_neg, Config()).module_state == "UNKNOWN"


def test_F2_bounds_violation_unknown():
    zero_var = [{"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i,
                 "vol": 1.0} for i in range(8)]  # zero variance -> z NaN
    rsv = detect(zero_var, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]
    evs = tape()
    orig = mod._robust_z
    try:
        mod._robust_z = lambda rows, cfg, f=1.0: -1e9  # force disagreement
        rsv = mod.detect(evs, Config())
        assert rsv.module_state == "UNKNOWN"
    finally:
        mod._robust_z = orig


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
    z = _causal_z(evs, cfg)
    zr = _robust_z(evs, cfg)
    assert within_tolerance(z, zr, DUAL_MODE, DUAL_TOL), (z, zr)
    assert detect(evs, cfg).module_state == "OK"


def test_hysteresis_transitions():
    """Hysteresis entry/exit thresholds drive the pinned label sequence."""
    cfg = Config()
    seq = ["normal"]
    for z in (2.3, 3.2, 2.5, 1.7, 1.2):
        seq.append(hysteresis(seq[-1], z, cfg))
    assert seq[1:] == ["elevated", "abnormal", "abnormal", "elevated", "normal"]


def test_hysteresis_boundaries():
    """z exactly on a threshold holds the current state (strict inequalities);
    an abnormal-state bar at z == exit threshold stays abnormal."""
    cfg = Config()
    assert hysteresis("normal", 2.0, cfg) == "normal"     # entry needs >
    assert hysteresis("elevated", 1.5, cfg) == "elevated"  # exit needs <
    assert hysteresis("abnormal", 2.0, cfg) == "abnormal"  # exit needs <
    assert hysteresis("elevated", 3.0, cfg) == "elevated"  # entry needs >


def test_cost_interface_adjustments():
    """§R5: regime state scales slip/impact/horizon; dead pace halves size."""
    base = {"slip_mult": 1.0, "impact_mult": 1.0, "horizon_mult": 1.0,
            "size_mult": 1.0, "trade_ok": True}
    ab = cost_adjustment(_rsv("abnormal", 3.7, 0, "OK"), base)
    assert (ab["slip_mult"], ab["impact_mult"], ab["horizon_mult"]) == (1.5, 0.8, 0.5)
    assert ab["trade_ok"] is True
    el = cost_adjustment(_rsv("elevated", 2.4, 0, "OK"), base)
    assert (el["slip_mult"], el["impact_mult"], el["horizon_mult"]) == (1.25, 0.9, 0.75)
    no = cost_adjustment(_rsv("normal", 0.3, 0, "OK"), base)
    assert (no["slip_mult"], no["impact_mult"], no["horizon_mult"]) == (1.0, 1.0, 1.0)
    dead = cost_adjustment(_rsv("normal", -1.5, 0, "OK"), base)
    assert dead["size_mult"] == 0.5
    # base dict is not mutated
    assert base["slip_mult"] == 1.0
