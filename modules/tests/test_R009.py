"""Acceptance tests for R009 - Mean-reversion vs momentum dominance.

Template v1.0.0. Reference implementation of the chapter's normative
pseudocode (§R2): trailing-window Lo-MacKinlay VR(q) with homoskedastic z
(documented simplification; production uses z*), hysteresis entry/exit bands,
z-significance gate, gap/halt/corporate-action edge cases, F1-F5 fail-safes,
and dual-estimator (Sentinel VR vs Verifier AC1) agreement.

Run: python3 -m pytest modules/tests/test_R009.py -q   (from repo root)
"""
import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R009_tape.csv"
EXPECTED = FIX / "R009_expected.csv"
TAPE2 = FIX / "R009_tape_transitions.csv"
EXPECTED2 = FIX / "R009_expected_transitions.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 604800  # indicator cadence in seconds (weekly) [default]
NS = 1_000_000_000
DAY_NS = 86400 * NS
STATE_LABELS = ['mr', 'indeterminate', 'momentum']  # regime state vocabulary (§1)
BOUNDS = (0.0, 4.0)  # mathematical bounds of VR value (F2)
DUAL_MODE = "state"  # rel | abs | sign | state
DUAL_TOL = None
ESTIMATOR_VERSION = "1.1.0"


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _vr2(rets):
    """Lo-MacKinlay VR(2), overlapping estimator [documented].

    rets: one-period log returns. sigma2_a = sum((r-mu)^2)/(n-1) [documented];
    overlapping q-period variance sigma2_c = (1/m) sum_{i}(sum(rets[i:i+q]) -
    q*mu)^2 with m = n-q+1 overlapping windows [documented]. VR = sigma2_c/(q*sigma2_a).
    """
    n = len(rets)
    if n < 8:
        return float("nan")
    mu = _mean(rets)
    va = sum((r - mu) ** 2 for r in rets) / (n - 1)
    if va <= 0:
        return float("nan")  # zero variance -> 0/0 undefined (F2)
    q = 2
    m = n - q + 1
    vc = sum((sum(rets[i:i + q]) - q * mu) ** 2 for i in range(m)) / m
    return vc / (q * va)


def _z_homo(v, n, q=2):
    """Homoskedastic z: sqrt(nq)(VR-1) / sqrt(2(2q-1)(q-1)/(3q)) [documented].

    n = number of one-period returns. Reference-implementation simplification;
    production uses the heteroskedasticity-robust z* (§R2).
    """
    if not math.isfinite(v) or n < 2:
        return float("nan")
    den = math.sqrt(2 * (2 * q - 1) * (q - 1) / (3 * q))
    return math.sqrt(n * q) * (v - 1.0) / den


def _z_robust(rets, q=2):
    """Heteroskedasticity-robust z*: sqrt(nq)(VR-1) / sqrt(theta_hat) [documented].

    theta_hat(q) = sum_{j=1}^{q-1} (2(q-j)/q)^2 * delta_hat_j, with
    delta_hat_j = [sum_t (x_t-mu)^2 (x_{t-j}-mu)^2] / [sum_t (x_t-mu)^2]^2
    (Lo-MacKinlay 1988, Theorem 2) [documented]. q=2 here: single j=1 term.
    """
    rets = list(rets)
    n = len(rets)
    v = _vr2(rets)
    if not math.isfinite(v) or n < 8:
        return float("nan")
    mu = _mean(rets)
    sq = [(r - mu) ** 2 for r in rets]
    den = sum(sq) ** 2
    if den <= 0:
        return float("nan")
    theta = 0.0
    for j in range(1, q):
        w = 2 * (q - j) / q
        delta = sum(sq[t] * sq[t - j] for t in range(j, n)) / den
        theta += (w ** 2) * delta
    if theta <= 0:
        return float("nan")
    return math.sqrt(n * q) * (v - 1.0) / math.sqrt(theta)


def _ac1(rets):
    """First-order autocorrelation (Verifier's second estimator)."""
    n = len(rets)
    if n < 4:
        return float("nan")
    mu = _mean(rets)
    den = sum((r - mu) ** 2 for r in rets)
    if den <= 0:
        return float("nan")
    return sum((rets[i] - mu) * (rets[i - 1] - mu) for i in range(1, n)) / den


def _ac_state(a):
    if not math.isfinite(a):
        return 'indeterminate'
    if a < -0.05:  # [example]
        return 'mr'
    if a > 0.05:  # [example]
        return 'momentum'
    return 'indeterminate'


# ============================ state machine ============================
def transition(value, z, prev, cfg):
    """Normative regime state machine with hysteresis + z-significance gate (§R2).

    - Entering a directional state requires |z| >= cfg.z_act; holding it
      requires only |z| >= cfg.z_hold (z-hysteresis), otherwise the label
      degrades to 'indeterminate' (restrictive; downstream halves size).
    - Value bands differ entry vs exit to kill flicker: mr exits above
      cfg.mr_exit (not at cfg.mr_enter); momentum exits below cfg.mom_exit.
    - Boundary: entry requires STRICT inequality (value == mr_enter stays).
    """
    if not math.isfinite(value):
        return 'indeterminate'
    zsig = math.isfinite(z) and abs(z) >= cfg.z_act
    zhold = math.isfinite(z) and abs(z) >= cfg.z_hold
    if prev == 'mr':
        if value > cfg.mr_exit or not zhold:
            return 'indeterminate'
        return 'mr'
    if prev == 'momentum':
        if value < cfg.mom_exit or not zhold:
            return 'indeterminate'
        return 'momentum'
    if zsig and value < cfg.mr_enter:
        return 'mr'
    if zsig and value > cfg.mom_enter:
        return 'momentum'
    return 'indeterminate'


# ============================ bar prep / edge cases ============================
def _validated_bars(rows):
    """Sort by event_ts, validate fields, return (bars, problem).

    bars: list of dicts with event_ts, c, halted. problem is None or a string:
    'empty' | 'invalid' (bad/missing fields, non-positive close, split jump on
    unadjusted data) — caller maps to UNKNOWN (F1).
    """
    rows = list(rows)
    if not rows:
        return [], 'empty'
    for r in rows:
        if ('event_ts' not in r or 'c' not in r
                or not isinstance(r.get('event_ts'), (int, float))
                or not isinstance(r.get('c'), (int, float))
                or not (r['c'] > 0)):
            return [], 'invalid'
    bars = sorted(rows, key=lambda r: r['event_ts'])
    for i in range(1, len(bars)):
        if bars[i]['event_ts'] <= bars[i - 1]['event_ts']:
            return [], 'invalid'  # duplicate or out-of-order ts
    # corporate-action guard: unadjusted 2:1-scale jumps are data errors, not alpha
    for i in range(1, len(bars)):
        ratio = bars[i]['c'] / bars[i - 1]['c']
        adjusted = bars[i].get('adjusted', True)  # vendor series default: adjusted [default]
        if (ratio > 3.0 or ratio < 1.0 / 3.0) and not adjusted:
            return [], 'invalid'
    return [{'event_ts': b['event_ts'], 'c': b['c'],
             'halted': bool(b.get('halted', False))} for b in bars], None


def _segments(bars, max_gap_ns):
    """Split bars into segments at gaps > max_gap_ns (no interpolation, F1).

    Halted bars are excluded from the return series (contributions discarded
    across reopen, per §R0.6 market-state table) but keep their slot for stamping.
    """
    segs, cur = [], []
    prev_ts = None
    for b in bars:
        if prev_ts is not None and b['event_ts'] - prev_ts > max_gap_ns:
            if cur:
                segs.append(cur)
            cur = []
        if not b['halted']:
            cur.append(b)
        prev_ts = b['event_ts']
    if cur:
        segs.append(cur)
    return segs


def _window_rets(seg, upto_ts, cfg):
    """Log returns of the trailing window ending at upto_ts (causal)."""
    closes = [b['c'] for b in seg if b['event_ts'] <= upto_ts]
    if len(closes) < 2:
        return []
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    return rets[-cfg.window:]


def rollout(rows, cfg):
    """Causal per-bar rollout: (value, z, state, module_state, computed_at) per bar.

    State transitions use the hysteresis machine with the previous bar's state;
    the value/z at each bar use only data with event_ts <= that bar (no lookahead).
    Halted bars: value/state frozen from prior bar, module_state DEGRADED/UNKNOWN
    per §R0.6 (freeze; emit UNKNOWN on HALTED).
    """
    bars, problem = _validated_bars(rows)
    if problem is not None:
        return []
    max_gap_ns = cfg.max_gap_days * DAY_NS
    segs = _segments(bars, max_gap_ns)
    seg_of = {}
    for s in segs:
        for b in s:
            seg_of[id(b)] = s
    halted_ts = {b['event_ts'] for b in bars if b['halted']}
    out, prev = [], 'indeterminate'
    for b in bars:
        ts = b['event_ts']
        if ts in halted_ts:
            out.append((float('nan'), float('nan'), prev, 'UNKNOWN', ts))
            continue
        seg = seg_of.get(id(b), [])
        rets = _window_rets(seg, ts, cfg)
        if len(rets) < cfg.min_bars:
            out.append((float('nan'), float('nan'), 'indeterminate', 'DEGRADED', ts))
            prev = 'indeterminate'
            continue
        v = _vr2(rets)
        z = _z_homo(v, len(rets), cfg.vr_q)
        st = transition(v, z, prev, cfg)
        out.append((v, z, st, 'OK', ts))
        prev = st
    return out


def primary_indicator(rows, cfg):
    """Latest-bar indicator: dict(value, state, module_state, computed_at)."""
    r = rollout(rows, cfg)
    if not r:
        return {"value": float("nan"), "state": "indeterminate",
                "module_state": "UNKNOWN", "computed_at": 0, "vintage": "synthetic"}
    v, z, st, ms, ts = r[-1]
    return {"value": v, "state": st, "module_state": ms, "computed_at": ts,
            "vintage": "synthetic"}


def second_estimator(rows, cfg):
    """Verifier: AC1 on the same trailing window."""
    bars, problem = _validated_bars(rows)
    if problem is not None or not bars:
        return {"value": float("nan"), "state": "indeterminate",
                "computed_at": rows[-1]["event_ts"] if rows else 0}
    segs = _segments(bars, cfg.max_gap_days * DAY_NS)
    seg = segs[-1] if segs else []
    rets = _window_rets(seg, bars[-1]['event_ts'], cfg)
    a = _ac1(rets)
    return {"value": a, "state": _ac_state(a), "computed_at": bars[-1]['event_ts']}


F2_POISON_TAPE = [
    {"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i, "c": 100.0}
    for i in range(14)
]  # zero variance -> VR = 0/0 = NaN -> F2


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
    state: str            # mr | indeterminate | momentum
    value: float          # indicator value
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


@dataclass
class Config:
    vr_q: int = 2          # variance-ratio horizon [default]
    window: int = 120      # trailing window, bars [default]
    min_bars: int = 120    # warm-up: min returns before labeling [default]
    z_act: float = 1.96    # |z| gate to ENTER a directional state [default]
    z_hold: float = 1.64   # |z| gate to HOLD it (z-hysteresis) [default]
    mr_enter: float = 0.85     # enter MR below this VR [default]
    mr_exit: float = 0.92      # exit MR above this VR (hysteresis) [default]
    mom_enter: float = 1.15    # enter momentum above this VR [default]
    mom_exit: float = 1.08     # exit momentum below this VR (hysteresis) [default]
    max_gap_days: int = 4  # event_ts step that starts a fresh window [default]

    def __post_init__(self):
        assert self.mr_enter < self.mr_exit < 1.0 < self.mom_exit < self.mom_enter, \
            "hysteresis ordering violated (§R0.2)"
        assert self.z_hold <= self.z_act, "hold gate must be softer than entry gate"


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
        return RegimeState("R009", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R009", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F3: dual-estimator agreement (state mode: same label)
    s = second_estimator(rows, cfg)
    if DUAL_MODE == "state":
        agree = (r["state"] == s["state"])
    else:
        agree = within_tolerance(v, s["value"], DUAL_MODE, DUAL_TOL)
    if not agree:
        return RegimeState("R009", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R009", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R009", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


# ------------------------------------------------------------------- tests
def _cfg_example():
    """Fixture-run config: production defaults with window/min_bars reduced to
    fit a short synthetic tape [example]."""
    return Config(window=12, min_bars=12)


def _cfg_transitions():
    return Config(window=24, min_bars=24)


def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = _cfg_example()
    for i in range(len(evs)):
        r = rollout(evs[: i + 1], cfg)[-1]
        v, z, st, ms, ts = r
        want = exp[i + 1]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(v), i
        else:
            assert abs(v - wv) < TOL, i
        wz = float(want["exp_z"])
        if math.isnan(wz):
            assert math.isnan(z), i
        else:
            assert abs(z - wz) < TOL, i
        assert st == want["exp_state"], i
        assert ts == int(want["exp_computed_at"]), i
        assert ms == want["exp_module_state"], i


def test_transition_tape_pins_state_sequence():
    """Hysteresis pins behavior: the transition tape must move
    indeterminate -> mr -> indeterminate -> momentum with no flicker inside
    the hysteresis bands, and match the frozen expected CSV exactly."""
    evs = tape(TAPE2)
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED2)}
    cfg = _cfg_transitions()
    seq = []
    for i in range(len(evs)):
        v, z, st, ms, ts = rollout(evs[: i + 1], cfg)[-1]
        want = exp[i + 1]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(v), i
        else:
            assert abs(v - wv) < TOL, i
        assert st == want["exp_state"], i
        assert ms == want["exp_module_state"], i
        seq.append(st)
    # phase structure: warming (bars<25), mr entry, mr exit, momentum entry
    assert seq[0] == 'indeterminate' and 'mr' in seq
    mr_first = seq.index('mr')
    assert mr_first >= 24, "mr must not fire before the window is warm"
    assert 'momentum' in seq[mr_first:], "momentum must fire in the trending phase"
    mom_first = seq.index('momentum')
    # no mr->momentum jump without passing through indeterminate (hysteresis)
    for a, b in zip(seq[mr_first:mom_first], seq[mr_first + 1:mom_first + 1]):
        assert not (a == 'mr' and b == 'momentum'), "hysteresis bypassed"
    assert 'indeterminate' in seq[mr_first:mom_first]


def test_hysteresis_boundaries_and_z_gate():
    """Pin the state machine on crafted (value, z, prev) inputs."""
    cfg = Config()
    sig = 2.5   # |z| >= z_act
    hold = 1.8  # z_hold <= |z| < z_act
    weak = 1.0  # |z| < z_hold
    # entry requires strict inequality at the boundary
    assert transition(0.85, -sig, 'indeterminate', cfg) == 'indeterminate'
    assert transition(0.849, -sig, 'indeterminate', cfg) == 'mr'
    assert transition(1.15, sig, 'indeterminate', cfg) == 'indeterminate'
    assert transition(1.151, sig, 'indeterminate', cfg) == 'momentum'
    # value-hysteresis: inside the band the previous state holds (no flicker)
    assert transition(0.88, -sig, 'mr', cfg) == 'mr'
    assert transition(0.93, -sig, 'mr', cfg) == 'indeterminate'
    assert transition(1.12, sig, 'momentum', cfg) == 'momentum'
    assert transition(1.05, sig, 'momentum', cfg) == 'indeterminate'
    # z-hysteresis: hold band survives a softened z; below z_hold degrades
    assert transition(0.88, -hold, 'mr', cfg) == 'mr'
    assert transition(0.88, -weak, 'mr', cfg) == 'indeterminate'
    # z-gate: weak significance blocks entry from indeterminate
    assert transition(0.50, -weak, 'indeterminate', cfg) == 'indeterminate'
    assert transition(1.50, weak, 'indeterminate', cfg) == 'indeterminate'
    # non-finite value -> indeterminate
    assert transition(float('nan'), sig, 'mr', cfg) == 'indeterminate'


def test_z_robust_is_finite_on_fixture():
    """z* must compute (production uses it); the reference gates on homoskedastic z."""
    evs = tape()
    cfg = _cfg_example()
    bars, _ = _validated_bars(evs)
    segs = _segments(bars, cfg.max_gap_days * DAY_NS)
    rets = _window_rets(segs[-1], bars[-1]['event_ts'], cfg)
    zr = _z_robust(rets)
    assert math.isfinite(zr), "z* must be finite on a clean window"


def test_gap_resets_window():
    """A data gap > max_gap_days starts a fresh window (no interpolation, F1)."""
    evs = tape()
    gap = [{"bar": 100 + i, "event_ts": evs[-1]["event_ts"] + (5 + i) * DAY_NS,
            "asof_ts": evs[-1]["event_ts"] + (5 + i) * DAY_NS + 3600 * NS,
            "c": 100.0 + 0.01 * i} for i in range(6)]
    cfg = _cfg_example()
    rsv = detect(evs + gap, cfg)
    assert rsv.module_state == 'DEGRADED', "post-gap window must re-warm"
    assert rsv.state == 'indeterminate'


def test_halt_freezes_and_masks():
    """A halted bar freezes the label and discards its contribution (§R0.6)."""
    evs = tape()
    cfg = _cfg_example()
    before = primary_indicator(evs, cfg)
    halted = [dict(r) for r in evs]
    halted[-1]['halted'] = True
    r = rollout(halted, cfg)[-1]
    v, z, st, ms, ts = r
    assert ms == 'UNKNOWN', "halted bar emits UNKNOWN per the market-state table"
    assert st == before['state'], "halt freezes the prior label"


def test_unadjusted_split_is_invalid():
    """A 2:1 split jump on unadjusted data -> UNKNOWN (F1), not a regime."""
    evs = tape()
    cfg = _cfg_example()
    poisoned = [dict(r) for r in evs]
    poisoned[-1]['c'] = poisoned[-2]['c'] * 0.5  # 2:1 split, no adjustment
    poisoned[-1]['adjusted'] = False
    rsv = detect(poisoned, cfg)
    assert rsv.module_state == 'UNKNOWN'
    # same jump flagged as pre-adjusted passes validation, but the distorted
    # window still fails the F3 dual-estimator agreement -> UNKNOWN (restrictive)
    ok = [dict(r) for r in poisoned]
    ok[-1]['adjusted'] = True
    assert detect(ok, cfg).module_state == 'UNKNOWN'


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, _cfg_example())
    assert rsv.regime_id == "R009"
    assert rsv.state in STATE_LABELS
    assert math.isfinite(rsv.value) and BOUNDS[0] <= rsv.value <= BOUNDS[1]
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. Assert label_ts > indicator_ts for the earliest trade."""
    evs = tape()
    cfg = _cfg_example()
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
    # non-positive close is invalid
    neg = [dict(event_ts=1, asof_ts=2, c=0.0), dict(event_ts=2, asof_ts=3, c=1.0)]
    assert detect(neg, Config()).module_state == "UNKNOWN"


def test_F2_bounds_violation_unknown():
    rsv = detect(F2_POISON_TAPE, _cfg_example())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = tape()
    orig = mod.second_estimator
    try:
        mod.second_estimator = lambda rows, cfg: {"value": 1e9, "state": "bogus",
                                                 "computed_at": evs[-1]["event_ts"]}
        rsv = mod.detect(evs, _cfg_example())
        assert rsv.module_state == "UNKNOWN"
    finally:
        mod.second_estimator = orig


def test_F4_staleness_unknown():
    evs = tape()
    stale_now = evs[-1]["event_ts"] + 10 * CADENCE_S * NS  # >> 3x cadence
    rsv = detect(evs, _cfg_example(), now_ns=stale_now)
    assert rsv.module_state == "UNKNOWN"


def test_F5_regime_mining_guard():
    evs = tape()
    try:
        detect(evs, _cfg_example(), select_periods=True, preregistered=False)
    except RegimeMiningError:
        pass
    else:
        raise AssertionError("F5: unregistered period selection must raise")
    rsv = detect(evs, _cfg_example(), select_periods=True, preregistered=True)
    assert rsv.module_state == "OK"


def test_dual_estimator_agreement():
    """Sentinel vs Verifier agree within tolerance on the fixture."""
    evs = tape()
    cfg = _cfg_example()
    r = primary_indicator(evs, cfg)
    s = second_estimator(evs, cfg)
    if DUAL_MODE == "state":
        assert r["state"] == s["state"], (r, s)
    else:
        assert within_tolerance(r["value"], s["value"], DUAL_MODE, DUAL_TOL), (r, s)
    assert detect(evs, cfg).module_state == "OK"
