"""Acceptance tests for R020 - Options gamma positioning (GEX) regime.

Template v1.0.0. Concrete sketch: loads the fixture tapes, runs a reference
implementation of the chapter's normative formula + hysteresis state machine
(§R2.4), and asserts causality, F1-F5 fail-safes, dual-estimator agreement,
regime transitions, and the §R5 cost interface.

Run: python3 -m pytest modules/tests/test_R020.py -q   (from repo root)
"""
import csv
import math
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R020_tape.csv"
EXPECTED = FIX / "R020_expected.csv"
TRANS = FIX / "R020_transitions.csv"
TRANS_EXPECTED = FIX / "R020_transitions_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['long_gamma', 'neutral', 'short_gamma', 'undefined', 'warming', 'missing', 'invalid']
BOUNDS = (-1e12, 1e12)  # mathematical bounds of the indicator value (F2) [default]
ESTIMATOR_VERSION = "1.1.0"

# Hand-computed anchors (independent of the CSVs): fail on logic drift.
ANCHOR_TAPE_BAR5_VALUE = -950000.0    # rows 1..5: -800k-2450k+3200k-2400k+1500k
ANCHOR_TAPE_BAR6_VALUE = -500000.0    # rows 1..6: bar5 total +450k
ANCHOR_TRANS_VALUES = {
    1: 40000.0, 2: 24000.0, 3: -5000.0, 4: -19000.0, 5: -26000.0,
    6: 3000.0, 7: -1000.0,
}  # sid 8 is thin-chain warming: value withheld (nan), label held
ANCHOR_TRANS_COMMITTED = {
    1: 'long_gamma', 2: 'long_gamma', 3: 'long_gamma', 4: 'long_gamma',
    5: 'short_gamma', 6: 'short_gamma', 7: 'neutral', 8: 'neutral',
    9: 'neutral', 10: 'neutral',
}


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def _num(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        try:
            return float(v)
        except (ValueError, TypeError):
            return v


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({k: _num(v) for k, v in r.items()})
    return rows


def transitions():
    """Rows grouped by snapshot id, in snapshot order."""
    snaps, order = {}, []
    for r in load_csv(TRANS):
        row = {k: _num(v) for k, v in r.items()}
        sid = int(row["snapshot"])
        snaps.setdefault(sid, []).append(row)
        if sid not in order:
            order.append(sid)
    return [(sid, snaps[sid]) for sid in sorted(order)]


def trans_expected():
    return {int(r["snapshot"]): r for r in load_csv(TRANS_EXPECTED)}


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # committed regime label
    value: float          # indicator value (NetGEX, $ per 1% move)
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of the snapshot)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF
    raw_state: str = ""   # pre-hysteresis label (audit)
    data_quality: dict = field(default_factory=dict)


@dataclass
class Config:
    """§R0.2 knobs. All defaults tagged [default]; see chapter for ranges."""
    snapshot: str = "15:30 ET"
    min_strikes: int = 5
    enter_frac: float = 0.20      # enter band = enter_frac * trailing_scale
    exit_frac: float = 0.10       # exit band  = exit_frac  * trailing_scale
    persist_n: int = 2            # consecutive snapshots to confirm a flip
    trailing_window: int = 60     # snapshots in the trailing |v| scale
    min_abs_net_gex: float = 0.0  # per-underlier absolute floor ($)
    dual_mode: str = "sign"
    dual_tol: float = None
    bounds: tuple = BOUNDS
    corp_action_tol: float = 0.20  # spot jump fraction -> DEGRADED hold
    staleness_mult: float = 3.0


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


# ------------------------------------------------- reference implementation
def _gex_row(r, spot):
    s = 1.0 if r["otype"] == "C" else -1.0  # standard dealer convention [documented]
    return s * r["gamma"] * r["oi"] * 100 * spot ** 2 * 0.01


def validate_chain(rows):
    """Returns (problems, skipped, spot). problems is a list of F1 reasons."""
    problems, skipped = [], 0
    if not rows:
        return ["empty_chain"], 0, None
    for i, r in enumerate(rows):
        if any(k not in r for k in ("strike", "otype", "gamma", "oi", "spot")):
            problems.append(f"row{i}_missing_fields")
            continue
        g, oi = r["gamma"], r["oi"]
        if g is None or oi is None:
            skipped += 1
            continue
        if not isinstance(g, (int, float)) or not isinstance(oi, (int, float)):
            problems.append(f"row{i}_non_numeric")
        elif g < 0 or oi < 0:
            problems.append(f"row{i}_negative_gamma_or_oi")
        if r["otype"] not in ("C", "P"):
            problems.append(f"row{i}_bad_otype")
        if not (isinstance(r["spot"], (int, float)) and r["spot"] > 0):
            problems.append(f"row{i}_bad_spot")
    if problems:
        return problems, skipped, None
    spots = [r["spot"] for r in rows if r["spot"] is not None]
    if max(spots) - min(spots) > 1e-9:  # spot must be uniform in a snapshot [default]
        return ["spot_mismatch"], skipped, None
    return [], skipped, rows[-1]["spot"]


def second_estimator(rows, cfg):
    """Verifier: chain-completeness robustness — drop the farthest strike;
    the sign must hold (gated by the dual floor in the detector)."""
    rows = [r for r in rows if r.get("gamma") is not None and r.get("oi") is not None]
    if len(rows) < cfg.min_strikes:
        return {"value": float("nan"), "computed_at": 0}
    spots = [r["spot"] for r in rows]
    s0 = spots[-1]
    trimmed = sorted(rows, key=lambda r: abs(r["strike"] - s0))[:-1]
    return {"value": sum(_gex_row(r, s0) for r in trimmed),
            "computed_at": rows[-1]["event_ts"]}


class SnapshotDetector:
    """Stateful per-snapshot detector implementing §R2.4."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.committed = None      # committed label
        self.pending = None        # candidate label awaiting confirmation
        self.pending_n = 0
        self.abs_history = deque(maxlen=cfg.trailing_window)
        self.prev_spot = None
        self.prev_v = None
        self.verifier = second_estimator

    def observe(self, rows, now_ns=None, select_periods=False, preregistered=False):
        cfg = self.cfg
        rows = list(rows)
        ts = rows[-1]["event_ts"] if rows else 0
        dq = {"skipped_rows": 0}

        def _unknown(reason, v=float("nan")):
            return RegimeState("R020", self.committed or "undefined", v,
                               ESTIMATOR_VERSION, "synthetic", ts, "UNKNOWN",
                               raw_state=reason, data_quality=dict(dq, reason=reason))

        # Halt/auction: freeze — hold committed label, module UNKNOWN (R0.6).
        if rows and any(r.get("halt", 0) == 1 for r in rows):
            return _unknown("halt_freeze")

        # F1: validation (never interpolate).
        problems, skipped, spot = validate_chain(rows)
        dq["skipped_rows"] = skipped
        if problems:
            return _unknown("F1_" + problems[0])
        if len([r for r in rows if r.get("gamma") is not None]) == 0:
            return _unknown("F1_all_rows_skipped")

        # Corporate-action guard: spot jump > tol with no adjustment calendar.
        if self.prev_spot is not None and spot is not None:
            if abs(spot / self.prev_spot - 1.0) > cfg.corp_action_tol:
                return RegimeState("R020", self.committed or "undefined",
                                   float("nan"), ESTIMATOR_VERSION, "synthetic",
                                   ts, "DEGRADED", raw_state="corp_action_hold",
                                   data_quality=dict(dq, reason="spot_jump"))

        # Warm-up: thin chain -> DEGRADED, label withheld.
        usable = [r for r in rows if r.get("gamma") is not None and r.get("oi") is not None]
        if len(usable) < cfg.min_strikes:
            return RegimeState("R020", self.committed or "warming", float("nan"),
                               ESTIMATOR_VERSION, "synthetic", ts, "DEGRADED",
                               raw_state="warming",
                               data_quality=dict(dq, reason="thin_chain"))

        v = sum(_gex_row(r, spot) for r in usable)

        # F2: mathematical bounds.
        lo, hi = cfg.bounds
        if not (math.isfinite(v) and lo <= v <= hi):
            return _unknown("F2_out_of_bounds", v)

        # Trailing scale + hysteresis bands.
        scale = max(self.abs_history) if self.abs_history else abs(v)
        if scale <= 0:
            scale = abs(v) if v != 0 else 1.0
        t_enter = cfg.enter_frac * scale
        t_exit = cfg.exit_frac * scale
        prev_raw = self.pending if self.pending is not None else self.committed
        if abs(v) < cfg.min_abs_net_gex or abs(v) < t_exit:
            raw = "neutral"
        elif v > t_enter:
            raw = "long_gamma"
        elif v < -t_enter:
            raw = "short_gamma"
        else:
            raw = prev_raw if prev_raw in ("long_gamma", "short_gamma", "neutral") else "neutral"

        # Persist/confirm (debounce flip-flop).
        if self.committed is None:
            self.committed, self.pending, self.pending_n = raw, None, 0
        elif raw == self.committed:
            self.pending, self.pending_n = None, 0
        elif raw == self.pending:
            self.pending_n += 1
            if self.pending_n >= cfg.persist_n:
                self.committed, self.pending, self.pending_n = raw, None, 0
        else:
            self.pending, self.pending_n = raw, 1

        self.abs_history.append(abs(v))
        self.prev_spot, self.prev_v = spot, v

        # F3: dual-estimator agreement, gated — arbitration only matters when
        # |v| >= the dual floor (default: t_enter); below it the magnitude is
        # noise and the Verifier defers to the Sentinel's hysteresis state.
        dual_floor = t_enter
        if abs(v) >= dual_floor:
            s = self.verifier(rows, cfg)
            sv = s["value"]
            if not (math.isfinite(sv) and (sv > 0) == (v > 0) and (sv < 0) == (v < 0)):
                return RegimeState("R020", self.committed, v, ESTIMATOR_VERSION,
                                   "synthetic", ts, "UNKNOWN", raw_state=raw,
                                   data_quality=dict(dq, reason="F3_dual_disagree"))

        # F4: staleness timeout.
        now = now_ns if now_ns is not None else ts + CADENCE_S * NS
        if now - ts > cfg.staleness_mult * CADENCE_S * NS:
            return RegimeState("R020", self.committed, v, ESTIMATOR_VERSION,
                               "synthetic", ts, "UNKNOWN", raw_state=raw,
                               data_quality=dict(dq, reason="F4_stale"))

        # F5: no ex-post backtest-period selection without a pre-registered definition.
        if select_periods and not preregistered:
            raise RegimeMiningError(
                "F5: regime-gated period selection needs a pre-registered definition")

        return RegimeState("R020", self.committed, v, ESTIMATOR_VERSION,
                           "synthetic", ts, "OK", raw_state=raw,
                           data_quality=dict(dq))


def detect(rows, cfg, now_ns=None, select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState — reference implementation
    with F1-F5 fail-safes wired in (Appendix f v1.0.0). One call = one snapshot."""
    return SnapshotDetector(cfg).observe(rows, now_ns=now_ns,
                                         select_periods=select_periods,
                                         preregistered=preregistered)


# ------------------------------------------------------- §R5 cost interface
def cost_adjustment(rsv_state, base_bps):
    """Regime state -> cost-function adjustment (§R5).

    base_bps: dict(spread_bps, fees_bps, borrow_bps, impact_bps) — the
    T-side 4-component stack. Returns (adjusted dict, meta dict).
    All multipliers tagged per the chapter's tag law.
    """
    mult = {"spread": 1.0, "fees": 1.0, "borrow": 1.0, "impact": 1.0}  # [default]
    meta = {"trade_ok": True, "fade_ok": True, "stop_mult": 1.0}       # [default]
    if isinstance(rsv_state, RegimeState):
        st, mstate = rsv_state.state, rsv_state.module_state
    else:
        st, mstate = rsv_state, "OK"
    # Degradation is checked first: a stale label in UNKNOWN/DEGRADED is
    # restrictive regardless of which label it happens to carry.
    if mstate == "UNKNOWN":
        mult["impact"] = 2.0    # [default] conservative when blind
        mult["spread"] = 1.25   # [default]
        meta.update(trade_ok=False, fade_ok=False, stop_mult=2.0)  # [default]
    elif mstate in ("DEGRADED", "OFF"):
        mult["impact"] = 1.5    # [default]
        meta.update(trade_ok=False, fade_ok=False, stop_mult=1.5)  # [default]
    elif st == "short_gamma":
        mult["impact"] = 1.50   # [example] trend-day violence: hedging chases moves
        mult["spread"] = 1.25   # [example] wider effective spreads on gap days
        meta.update(trade_ok=True, fade_ok=False, stop_mult=2.0)   # [example]/[default]
    elif st == "long_gamma":
        mult["impact"] = 0.80   # [example] pinning flow absorbs prints
        meta.update(trade_ok=True, fade_ok=True, stop_mult=1.0)    # [default]
    elif st == "neutral":
        meta.update(trade_ok=True, fade_ok=True, stop_mult=1.0)    # [default]
    else:  # unmapped label: restrictive
        mult["impact"] = 1.5    # [default]
        meta.update(trade_ok=False, fade_ok=False, stop_mult=1.5)  # [default]
    adj = {k: base_bps[k] * mult[k] for k in ("spread", "fees", "borrow", "impact")}
    return adj, meta


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = Config()
    for i in range(len(evs)):
        det = SnapshotDetector(cfg)
        rsv = det.observe(evs[: i + 1])
        want = exp[i + 1]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(rsv.value), i
        else:
            assert abs(rsv.value - wv) < TOL, i
        assert rsv.state == want["exp_state"], i
        assert rsv.raw_state == want["exp_raw"], i
        assert rsv.computed_at == int(want["exp_computed_at"]), i
        assert rsv.module_state == want["exp_module_state"], i
    # Anchors: hand-computed values that fail on logic drift.
    assert abs(SnapshotDetector(cfg).observe(evs[:5]).value - ANCHOR_TAPE_BAR5_VALUE) < TOL
    assert abs(SnapshotDetector(cfg).observe(evs[:6]).value - ANCHOR_TAPE_BAR6_VALUE) < TOL
    # min_strikes boundary: 4 strikes -> DEGRADED/warming; 5 -> OK.
    assert SnapshotDetector(cfg).observe(evs[:4]).module_state == "DEGRADED"
    assert SnapshotDetector(cfg).observe(evs[:5]).module_state == "OK"


def test_transitions_hysteresis_sequence():
    """§R2 hysteresis: deadband holds, persist_n confirms flips, thin/invalid
    snapshots withhold without clobbering the committed label."""
    cfg = Config()
    det = SnapshotDetector(cfg)
    want = trans_expected()
    for sid, rows in transitions():
        rsv = det.observe(rows)
        w = want[sid]
        wv = float(w["exp_value"])
        if math.isnan(wv):
            assert math.isnan(rsv.value), sid
        else:
            assert abs(rsv.value - wv) < TOL, (sid, rsv.value)
        assert rsv.raw_state == w["exp_raw"], (sid, rsv.raw_state)
        assert rsv.state == w["exp_committed"], (sid, rsv.state)
        assert rsv.module_state == w["exp_module_state"], (sid, rsv.module_state)
        assert rsv.computed_at == int(w["exp_computed_at"]), sid
    # Anchors: hand-computed NetGEX and committed labels.
    det2 = SnapshotDetector(cfg)
    for sid, rows in transitions():
        rsv = det2.observe(rows)
        if sid in ANCHOR_TRANS_VALUES:
            assert abs(rsv.value - ANCHOR_TRANS_VALUES[sid]) < TOL, sid
        if sid == 8:  # thin chain: value withheld, committed label held
            assert math.isnan(rsv.value) and rsv.module_state == "DEGRADED", sid
        assert rsv.state == ANCHOR_TRANS_COMMITTED[sid], sid


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R020"
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
    # negative gamma is invalid input -> UNKNOWN, never interpolated
    neg = [dict(event_ts=1, asof_ts=2, strike=100, otype="C", gamma=-0.05, oi=100, spot=100.0)
           for _ in range(5)]
    assert detect(neg, Config()).module_state == "UNKNOWN"
    # spot mismatch inside one snapshot -> UNKNOWN
    mm = [dict(event_ts=1, asof_ts=2, strike=100 + i, otype="C", gamma=0.05, oi=100,
               spot=100.0 if i < 4 else 101.0) for i in range(5)]
    assert detect(mm, Config()).module_state == "UNKNOWN"


def test_F2_bounds_violation_unknown():
    poison = [
        {"bar": 1, "event_ts": 1000, "asof_ts": 1060, "strike": 100, "otype": "C",
         "gamma": 1e9, "oi": 1500, "spot": 100.0},
        {"bar": 2, "event_ts": 1060, "asof_ts": 1120, "strike": 100, "otype": "P",
         "gamma": 0.08, "oi": 3000, "spot": 100.0},
        {"bar": 3, "event_ts": 1120, "asof_ts": 1180, "strike": 102, "otype": "C",
         "gamma": 0.06, "oi": 2500, "spot": 100.0},
        {"bar": 4, "event_ts": 1180, "asof_ts": 1240, "strike": 104, "otype": "C",
         "gamma": 0.03, "oi": 1500, "spot": 100.0},
        {"bar": 5, "event_ts": 1240, "asof_ts": 1300, "strike": 106, "otype": "C",
         "gamma": 0.02, "oi": 1000, "spot": 100.0},
    ]  # gamma = 1e9 -> |NetGEX| ~ 1.5e14 > 1e12 bound -> F2
    rsv = detect(poison, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"


def test_F3_dual_estimator_disagreement_unknown():
    evs = tape()  # bar-6 snapshot: |v| well above the dual floor
    cfg = Config()
    det = SnapshotDetector(cfg)
    p0 = sum(_gex_row(r, 100.0) for r in evs)
    bad_val = -1e9 if p0 >= 0 else 1e9  # opposite sign: must disagree
    det.verifier = lambda rows, c: {"value": bad_val, "computed_at": evs[-1]["event_ts"]}
    rsv = det.observe(evs)
    assert rsv.module_state == "UNKNOWN"
    assert rsv.data_quality.get("reason") == "F3_dual_disagree"


def test_F3_dual_gate_vacuous_below_band():
    """Below the dual floor (|v| < t_enter) the Verifier defers to the
    Sentinel's hysteresis state — disagreement must NOT force UNKNOWN."""
    det = SnapshotDetector(Config())
    # run snapshots 1..2 so |v| history exists, then a tiny-|v| snapshot
    for sid, rows in transitions():
        if sid <= 2:
            det.observe(rows)
    tiny = [dict(event_ts=10, asof_ts=70, strike=100 + i, otype="C" if i % 2 == 0 else "P",
                 gamma=0.001, oi=10, spot=100.0) for i in range(5)]
    det.verifier = lambda rows, c: {"value": 1e9, "computed_at": 10}  # wildly disagrees
    rsv = det.observe(tiny)
    assert rsv.module_state == "OK", "dual gate must be vacuous below the floor"


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
    det = SnapshotDetector(cfg)
    rsv = det.observe(evs)
    assert rsv.module_state == "OK"
    s = second_estimator(evs, cfg)
    assert (rsv.value > 0) == (s["value"] > 0) and (rsv.value < 0) == (s["value"] < 0)


def test_halt_freezes_label():
    """HALTED: freeze — committed label held, module UNKNOWN (R0.6)."""
    det = SnapshotDetector(Config())
    sid1, rows1 = transitions()[0]
    rsv1 = det.observe(rows1)
    assert rsv1.state == "long_gamma" and rsv1.module_state == "OK"
    halted = [dict(r, halt=1) for r in rows1]
    rsv2 = det.observe(halted)
    assert rsv2.module_state == "UNKNOWN"
    assert rsv2.state == "long_gamma", "halt must freeze, not clobber"


def test_corporate_action_spot_jump_degraded():
    """Spot jump > corp_action_tol with no adjustment calendar -> DEGRADED hold."""
    det = SnapshotDetector(Config())
    sid1, rows1 = transitions()[0]
    assert det.observe(rows1).module_state == "OK"
    jumped = [dict(r, spot=130.0) for r in rows1]  # +30% [example]
    rsv = det.observe(jumped)
    assert rsv.module_state == "DEGRADED"
    assert rsv.state == "long_gamma", "label held while the jump is reconciled"


def test_zero_oi_rows_are_valid():
    """oi=0 rows contribute 0 and do not invalidate the chain (snapshot 7)."""
    det = SnapshotDetector(Config())
    rsv = None
    for sid, rows in transitions():
        rsv = det.observe(rows)
        if sid == 7:
            assert rsv.module_state == "OK", sid
            zero_rows = [r for r in rows if r["oi"] == 0]
            assert zero_rows, "fixture must contain a zero-OI row"


def test_cost_interface_scales_components():
    base = {"spread": 4.0, "fees": 1.0, "borrow": 2.0, "impact": 6.0}  # bps [example]
    cases = {
        "short_gamma": ({"spread": 5.0, "fees": 1.0, "borrow": 2.0, "impact": 9.0},
                        {"trade_ok": True, "fade_ok": False, "stop_mult": 2.0}),
        "long_gamma": ({"spread": 4.0, "fees": 1.0, "borrow": 2.0, "impact": 4.8},
                       {"trade_ok": True, "fade_ok": True, "stop_mult": 1.0}),
        "neutral": (dict(base), {"trade_ok": True, "fade_ok": True, "stop_mult": 1.0}),
    }
    for st, (want_adj, want_meta) in cases.items():
        rsv = RegimeState("R020", st, 1.0, ESTIMATOR_VERSION, "synthetic", 1, "OK")
        adj, meta = cost_adjustment(rsv, base)
        for k, w in want_adj.items():
            assert abs(adj[k] - w) < 1e-12, (st, k)
        for k, w in want_meta.items():
            assert meta[k] == w, (st, k)
    # UNKNOWN: restrictive — conservative costs, trading gated off.
    rsv_u = RegimeState("R020", "neutral", 1.0, ESTIMATOR_VERSION, "synthetic", 1, "UNKNOWN")
    adj, meta = cost_adjustment(rsv_u, base)
    assert abs(adj["impact"] - 12.0) < 1e-12 and abs(adj["spread"] - 5.0) < 1e-12
    assert meta["trade_ok"] is False and meta["stop_mult"] == 2.0
    # DEGRADED/warming: restrictive.
    rsv_d = RegimeState("R020", "warming", float("nan"), ESTIMATOR_VERSION, "synthetic", 1, "DEGRADED")
    adj, meta = cost_adjustment(rsv_d, base)
    assert meta["trade_ok"] is False and abs(adj["impact"] - 9.0) < 1e-12
