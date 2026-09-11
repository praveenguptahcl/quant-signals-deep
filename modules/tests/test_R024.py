"""Acceptance tests for R024 - Interest-rate level/direction regime.

Template v1.0.0 + deep-review pass (module v1.1.0): normative detector with a
hysteresis state machine (§R2), calibration recipe, contract-roll strip
builder, concrete §R5 cost interface, and trigger->detect->action->recovery
failure modes. 18 acceptance tests; any logic drift in the FSM, bounds,
dual-estimator, warm-up, rollover, or cost interface fails the suite.

Run: python3 -m pytest modules/tests/test_R024.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R024_tape.csv"
EXPECTED = FIX / "R024_expected.csv"
TTAPE = FIX / "R024_transitions_tape.csv"
TEXPECTED = FIX / "R024_transitions_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['hike_biased', 'on_hold', 'cut_biased', 'undefined', 'warming',
                'missing', 'invalid', 'out_of_bounds']
BOUNDS = (-1.5, 1.5)  # mathematical bounds of the indicator value (F2)
ESTIMATOR_VERSION = "1.1.0"


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


# ------------------------------------------------------------------ config
@dataclass
class Config:
    """Mirrors §R0.2. Defaults are [default]; see §R2 for the calibration recipe."""
    hike_p_entry: float = 0.6
    hike_p_exit: float = 0.45
    cut_p_entry: float = -0.2
    cut_p_exit: float = -0.05
    dual_tol: float = 0.15
    min_bars: int = 3
    churn_window: int = 5
    churn_max_flips: int = 2
    churn_widen: float = 0.05
    fomc_window_days: int = 3
    fomc_dates: tuple = ()

    def __post_init__(self):
        assert self.hike_p_exit < self.hike_p_entry, "hysteresis invariant"
        assert self.cut_p_entry < self.cut_p_exit, "hysteresis invariant"


# ------------------------------------------------------- core computation
def primary_indicator_value(r):
    """Normative §R2 binary block: P(+25bp) = (implied EOM EFFR - start)/0.25."""
    return (r["effr_implied"] - r["effr_start"]) / 0.25


def second_estimator_value(rows):
    """Verifier: probability from the 3-obs average implied path (independent)."""
    rows = list(rows)
    m = _mean([x["effr_implied"] for x in rows[-3:]])
    return (m - rows[-1]["effr_start"]) / 0.25


def label_hysteresis(prev, p, cfg):
    """Normative hysteresis FSM (§R2). Boundaries are inclusive as documented."""
    if prev == "hike_biased":
        if p <= cfg.hike_p_exit:
            return "cut_biased" if p <= cfg.cut_p_entry else "on_hold"
        return "hike_biased"
    if prev == "cut_biased":
        if p >= cfg.cut_p_exit:
            return "hike_biased" if p >= cfg.hike_p_entry else "on_hold"
        return "cut_biased"
    # on_hold
    if p >= cfg.hike_p_entry:
        return "hike_biased"
    if p <= cfg.cut_p_entry:
        return "cut_biased"
    return "on_hold"


def label_walk(rows, cfg):
    """Causal per-bar walk: (values, labels). Pure function of past bars."""
    values, labels = [], []
    prev = "on_hold"
    for r in rows:
        p = primary_indicator_value(r)
        values.append(p)
        prev = label_hysteresis(prev, p, cfg)
        labels.append(prev)
    return values, labels


def select_front(contracts, event_ts):
    """Strip builder: front ZQ contract = earliest contract month whose
    last_trading_day >= event_ts (expired months never contribute)."""
    live = [c for c in contracts if c["last_trading_day"] >= event_ts]
    if not live:
        raise LookupError("no live ZQ contract for event_ts")
    return min(live, key=lambda c: c["contract_month"])


def strip_implied(contracts, event_ts):
    """Implied EFFR from the front contract settle: 100 - price [documented]."""
    return 100.0 - select_front(contracts, event_ts)["settle"]


# Back-compat aliases for the original 9-test surface ---------------------
def primary_indicator(rows, cfg):
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "vintage": "synthetic"}
    if any("effr_implied" not in r or "effr_start" not in r
           or not (0 <= r["effr_implied"] <= 20 and 0 <= r["effr_start"] <= 20)
           for r in rows):
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1].get("event_ts", 0), "vintage": "synthetic"}
    values, labels = label_walk(rows, cfg)
    return {"value": values[-1], "state": labels[-1], "module_state": "OK",
            "computed_at": rows[-1]["event_ts"], "vintage": "synthetic"}


def second_estimator(rows, cfg):
    rows = list(rows)
    r = rows[-1] if rows else None
    if r is None:
        return {"value": float("nan"), "state": "undefined", "computed_at": 0}
    return {"value": second_estimator_value(rows), "state": "n/a",
            "computed_at": r["event_ts"]}


F2_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1001, "effr_start": 4.33,
     "effr_implied": 4.75},
]  # p = (4.75-4.33)/0.25 = 1.68 > 1.5 bound -> F2


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
    state: str            # regime label, e.g. "hike_biased"
    value: float          # indicator value
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


def _churn_flips(labels, window):
    seq = [l for l in labels[-window:] if l]
    return sum(1 for a, b in zip(seq, seq[1:]) if a != b)


def detect(rows, cfg, now_ns=None, select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState — normative reference
    implementation with the hysteresis FSM and F1-F5 fail-safes (§R2, App. f)."""
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError(
            "F5: regime-gated period selection needs a pre-registered definition")
    # F1: empty input / invalid fields -> UNKNOWN, never interpolate.
    # Corporate-action and non-BAR records are ignored (futures: none apply).
    bars = [r for r in rows if r.get("type", "BAR") == "BAR"]
    if not bars:
        return RegimeState("R024", "missing", float("nan"), ESTIMATOR_VERSION,
                           "synthetic", 0, "UNKNOWN")
    if any("effr_implied" not in r or "effr_start" not in r
           or not (0 <= r["effr_implied"] <= 20 and 0 <= r["effr_start"] <= 20)
           for r in bars):
        return RegimeState("R024", "invalid", float("nan"), ESTIMATOR_VERSION,
                           "synthetic", bars[-1].get("event_ts", 0), "UNKNOWN")
    values, labels = label_walk(bars, cfg)
    v, lab = values[-1], labels[-1]
    ts = bars[-1]["event_ts"]
    # F2: mathematical bounds
    if not (math.isfinite(v) and BOUNDS[0] <= v <= BOUNDS[1]):
        return RegimeState("R024", "out_of_bounds", v, ESTIMATOR_VERSION,
                           "synthetic", ts, "UNKNOWN")
    # F3: dual-estimator agreement (one-shot at the newest bar, per §R4)
    q = second_estimator_value(bars)
    if not (math.isfinite(q) and abs(v - q) <= cfg.dual_tol):
        return RegimeState("R024", lab, v, ESTIMATOR_VERSION, "synthetic", ts,
                           "UNKNOWN")
    # Warm-up: insufficient lookback -> DEGRADED, label withheld
    if len(bars) < cfg.min_bars:
        return RegimeState("R024", "warming", v, ESTIMATOR_VERSION, "synthetic",
                           ts, "DEGRADED")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else ts + CADENCE_S * NS
    if now - ts > 3 * CADENCE_S * NS:
        return RegimeState("R024", lab, v, ESTIMATOR_VERSION, "synthetic", ts,
                           "UNKNOWN")
    # Churn guard: rapid label flips -> DEGRADED, widen hysteresis exits
    if _churn_flips(labels, cfg.churn_window) >= cfg.churn_max_flips:
        return RegimeState("R024", lab, v, ESTIMATOR_VERSION, "synthetic", ts,
                           "DEGRADED")
    return RegimeState("R024", lab, v, ESTIMATOR_VERSION, "synthetic", ts, "OK")


def cost_adjustment(rsv, base):
    """§R5 cost interface: regime state -> cost-function adjustment.
    Pure function of (rsv, base); never mutates base."""
    adj = dict(base)
    adj["trade_ok"] = True
    s = rsv["state"]
    adj["duration_mult"] = {"hike_biased": 0.5, "cut_biased": 1.5}.get(s, 1.0)
    effr = rsv.get("effr_level")
    adj["funding_bps_floor"] = (effr * 100.0) if effr is not None else None
    adj["spread_mult"] = 1.5 if rsv.get("fomc_window") else 1.0
    adj["fees_scale"] = 1.0
    adj["regime_id"] = rsv["regime_id"]
    return adj


# ------------------------------------------------------------------- tests
def _check_fixture(tape_path, exp_path):
    evs = tape(tape_path)
    exp = {int(r["bar"]): r for r in load_csv(exp_path)}
    cfg = Config()
    values, labels = label_walk(evs, cfg)
    assert len(values) == len(exp) == len(evs)
    for i, (v, lab) in enumerate(zip(values, labels), 1):
        want = exp[i]
        wv = float(want["exp_value"])
        assert abs(v - wv) < TOL, (i, v, wv)
        assert lab == want["exp_state"], (i, lab, want["exp_state"])
        assert evs[i - 1]["event_ts"] == int(want["exp_computed_at"]), i
        assert want["exp_module_state"] == "OK", i


def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    _check_fixture(TAPE, EXPECTED)


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R024"
    assert rsv.state in STATE_LABELS
    assert math.isfinite(rsv.value) and BOUNDS[0] <= rsv.value <= BOUNDS[1]
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. Assert label_ts > indicator_ts for the earliest trade."""
    evs = tape()
    cfg = Config(min_bars=1)
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
    assert rsv.state == "out_of_bounds"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = tape()
    orig = mod.second_estimator_value
    p0 = primary_indicator_value(evs[-1])
    bad_val = -1e9 if (p0 >= 0) else 1e9
    try:
        mod.second_estimator_value = lambda rows: bad_val
        rsv = mod.detect(evs, Config())
        assert rsv.module_state == "UNKNOWN"
    finally:
        mod.second_estimator_value = orig


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
    v = primary_indicator_value(evs[-1])
    q = second_estimator_value(evs)
    assert abs(v - q) <= cfg.dual_tol, (v, q)
    assert detect(evs, cfg).module_state == "OK"


# --------------------------------- deep-review additions (module v1.1.0)
def test_hysteresis_transition_sequence():
    """§R2 FSM: entry needs the full entry threshold; exit needs the exit
    band; sub-entry dips do not flip the label (pins the whole sequence)."""
    _check_fixture(TTAPE, TEXPECTED)


def test_hysteresis_boundary_exactness():
    """Inclusive-boundary contract: logic drift at any boundary fails."""
    cfg = Config()
    H = lambda prev, p: label_hysteresis(prev, p, cfg)
    assert H("on_hold", 0.60) == "hike_biased"     # entry inclusive
    assert H("on_hold", 0.59) == "on_hold"         # just below entry
    assert H("hike_biased", 0.45) == "on_hold"     # exit inclusive
    assert H("hike_biased", 0.46) == "hike_biased"  # sticky above exit
    assert H("on_hold", -0.20) == "cut_biased"     # entry inclusive
    assert H("on_hold", -0.19) == "on_hold"
    assert H("cut_biased", -0.05) == "on_hold"     # exit inclusive
    assert H("cut_biased", -0.06) == "cut_biased"  # sticky below exit
    assert H("hike_biased", -0.21) == "cut_biased"  # direct flip only at cut entry


def test_warmup_degraded():
    """Fewer than min_bars -> DEGRADED with the label withheld (never a guess)."""
    evs = tape()
    rsv = detect(evs[:2], Config())
    assert rsv.module_state == "DEGRADED"
    assert rsv.state == "warming"
    assert math.isfinite(rsv.value)  # value still computed, label withheld


def test_missing_bar_masked_no_interpolation():
    """A missing bar is masked, never interpolated: labels exist only for
    present bars and each is stamped at its own event_ts."""
    evs = tape()
    gap = evs[:4] + evs[5:]  # drop bar 5: a 2-day hole
    cfg = Config()
    values, labels = label_walk(gap, cfg)
    assert len(values) == 9 == len(labels)  # no fabricated bar
    for r, v in zip(gap, values):
        assert abs(v - primary_indicator_value(r)) < TOL
    rsv = detect(gap, cfg)
    assert rsv.module_state == "OK"
    assert rsv.computed_at == gap[-1]["event_ts"]


def test_contract_roll_continuity():
    """Strip builder: expired ZQ months never contribute; the roll produces
    no spurious flip (continuity |Δp| <= 1e-9)."""
    ts = [1788220800000000000 + i * 86400 * NS for i in range(10)]
    contracts = [
        {"contract_month": "202610", "last_trading_day": ts[4], "settle": 95.50},
        {"contract_month": "202611", "last_trading_day": ts[4] + 30 * 86400 * NS,
         "settle": 95.50},
    ]
    implied = [strip_implied(contracts, t) for t in ts]
    assert all(abs(x - 4.50) < 1e-12 for x in implied)
    assert select_front(contracts, ts[4])["contract_month"] == "202610"
    assert select_front(contracts, ts[5])["contract_month"] == "202611"
    rows = [{"bar": i + 1, "event_ts": t, "asof_ts": t + 3600 * NS,
             "effr_start": 4.33, "effr_implied": x}
            for i, (t, x) in enumerate(zip(ts, implied))]
    rsv = detect(rows, Config())
    assert rsv.module_state == "OK" and rsv.state == "hike_biased"


def test_corporate_action_ignored():
    """Futures have no corporate actions: a CORPORATE_ACTION record is
    filtered and cannot move the label."""
    evs = tape()
    mixed = evs[:5] + [{"type": "CORPORATE_ACTION", "event_ts": evs[5]["event_ts"],
                        "note": "dividend"}] + evs[5:]
    a, b = detect(evs, Config()), detect(mixed, Config())
    assert (a.state, a.value, a.module_state) == (b.state, b.value, b.module_state)


def test_F3_trips_on_fast_regime_transition():
    """Honest limitation: the 3-obs verifier lags fast ramps, so a violent
    regime transition trips F3 -> UNKNOWN by design (see §R7 row 6)."""
    evs = tape(TTAPE)
    rsv = detect(evs, Config())
    assert rsv.module_state == "UNKNOWN"
    v = primary_indicator_value(evs[-1])
    assert abs(v - second_estimator_value(evs)) > Config().dual_tol


def test_churn_guard_degraded():
    """Rapid label flips (>=2 in the last 5 bars) -> DEGRADED and a
    documented hysteresis-widening action (§R7 row 7)."""
    base = 1788220800000000000
    p = [0.61, 0.44, 0.61, 0.44, 0.61]  # flips hike/on_hold 4 times
    rows = [{"bar": i + 1, "event_ts": base + i * 86400 * NS,
             "asof_ts": base + i * 86400 * NS + 3600 * NS,
             "effr_start": 4.33, "effr_implied": 4.33 + 0.25 * x}
            for i, x in enumerate(p)]
    cfg = Config(dual_tol=10.0)  # bypass F3: this test is about churn only
    rsv = detect(rows, cfg)
    assert rsv.module_state == "DEGRADED"
    _, labels = label_walk(rows, Config())
    assert _churn_flips(labels, cfg.churn_window) >= cfg.churn_max_flips


def test_cost_interface_components():
    """§R5: which cost components scale, how much, tagged; base untouched."""
    base = {"notional": 1e6, "adv_pct": 0.05, "venue": "CBOT", "side": "taker",
            "urgency": "normal", "borrow_bps_per_day": 12.0}
    mk = lambda st, effr, win: {"regime_id": "R024", "state": st,
                               "effr_level": effr, "fomc_window": win}
    a = cost_adjustment(mk("hike_biased", 4.50, False), base)
    assert a["duration_mult"] == 0.5          # underweight duration [example]
    assert abs(a["funding_bps_floor"] - 450.0) < 1e-9  # 4.50% -> bps [documented arith.]
    assert a["spread_mult"] == 1.0
    assert a["fees_scale"] == 1.0            # fees static
    b = cost_adjustment(mk("cut_biased", 4.10, True), base)
    assert b["duration_mult"] == 1.5
    assert abs(b["funding_bps_floor"] - 410.0) < 1e-9
    assert b["spread_mult"] == 1.5           # FOMC window [example]
    c = cost_adjustment(mk("on_hold", 4.33, False), base)
    assert c["duration_mult"] == 1.0
    assert base == {"notional": 1e6, "adv_pct": 0.05, "venue": "CBOT",
                    "side": "taker", "urgency": "normal",
                    "borrow_bps_per_day": 12.0}  # pure function
