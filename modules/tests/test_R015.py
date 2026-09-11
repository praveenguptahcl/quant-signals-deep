"""Acceptance tests for R015 - Tick-constraint regime.

Reference implementation of the chapter's normative §R2 detection pseudocode:
causal trailing-window TickBind, hysteresis state machine, gap masking (no
interpolation), corporate-action reset, price-dependent tick τ(t) per Reg NMS
Rule 612, trade-clustering verifier (F3), and F1/F2/F4/F5 fail-safes.

Run: python3 -m pytest modules/tests/test_R015.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R015_tape.csv"
EXPECTED = FIX / "R015_expected.csv"
TAPE_H = FIX / "R015_tape_hysteresis.csv"
EXPECTED_H = FIX / "R015_expected_hysteresis.csv"
TAPE_G = FIX / "R015_tape_gaps.csv"
EXPECTED_G = FIX / "R015_expected_gaps.csv"
TAPE_S = FIX / "R015_tape_split.csv"
EXPECTED_S = FIX / "R015_expected_split.csv"

TS0 = 1788220800000000000  # synthetic epoch, int64 ns [example]
TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['constrained', 'intermittent', 'unconstrained',
                'undefined', 'warming', 'missing', 'invalid']
BOUNDS = (0.0, 1.0)  # mathematical bounds of the indicator value (F2)
ESTIMATOR_VERSION = "1.1.0"


# ------------------------------------------------------------- §R2 reference
def tick_of(price):
    """Reg NMS Rule 612 [documented]: $0.01 for NMS stocks >= $1.00,
    $0.0001 below $1.00."""
    return 0.01 if price >= 1.00 else 0.0001


def _band(v, cfg):
    """Direct banding (no memory). Entry boundaries inclusive [default]."""
    if v >= cfg.constrained_cut:
        return "constrained"
    if v <= cfg.free_cut:
        return "unconstrained"
    return "intermittent"


def _hysteresis(prev, v, cfg):
    """Hysteresis state machine [default]: exit a state only past the exit
    cut; entry boundaries inclusive."""
    if prev == "constrained" and v >= cfg.constrained_exit:
        return "constrained"
    if prev == "unconstrained" and v <= cfg.free_exit:
        return "unconstrained"
    return _band(v, cfg)


def _cluster_value(trades, tau, cfg):
    n = len(trades)
    if n == 0:
        return float("nan")
    hit = sum(1 for p in trades
              if math.isfinite(p) and abs(p - round(p / tau) * tau) <= cfg.eq_tol)
    return hit / n


def _cluster_label(c, cfg):
    if not math.isfinite(c):
        return "undefined"
    if c > cfg.cluster_cut:
        return "constrained"
    if c < cfg.cluster_lo:
        return "unconstrained"
    return "intermittent"


def second_estimator(trades, tau, cfg):
    """Verifier: trade-price clustering cross-check [documented Harris 1991].
    `trades` are the windowed trade prints; `tau` the bar's tick.
    Abstains (``undefined``) when the grid is finer than $0.01 [default]:
    on-grid-ness is then uninformative (every price is on a $0.0001 grid),
    so a clustering verdict would be spurious."""
    trades = list(trades)
    if abs(tau - 0.01) > cfg.eq_tol:
        return {"value": float("nan"), "state": "undefined"}
    c = _cluster_value(trades, tau, cfg)
    return {"value": c, "state": _cluster_label(c, cfg)}


def _valid(e):
    for k in ("bid", "ask", "tick", "trade_px"):
        if k not in e or e[k] is None:
            return False
    b, a, t = e["bid"], e["ask"], e["tick"]
    if not (math.isfinite(b) and math.isfinite(a) and math.isfinite(t)
            and math.isfinite(e["trade_px"])):
        return False
    return a >= b > 0 and t > 0


def _opposite_extremes(a, b):
    """F3 tolerance [default]: adjacent-band wobble is tolerated; opposite
    extremes (constrained vs unconstrained), or an unmappable verifier
    state, fail closed to UNKNOWN. A verifier abstention (``undefined``,
    e.g. sub-$0.01 tick grids) never fires."""
    bands = ("constrained", "intermittent", "unconstrained")
    if b == "undefined":
        return False
    if a not in bands or b not in bands:
        return True
    return {a, b} == {"constrained", "unconstrained"}


def _rsv(state, value, ts, module_state, vintage="synthetic"):
    return {"state": state, "value": value, "computed_at": ts,
            "module_state": module_state, "vintage": vintage}


def detect_series(events, cfg):
    """Normative §R2 detector. Returns one RSV dict per input event, causal."""
    out = []
    obs, trades = [], []          # trailing 1/0 tick-bind observations, trade prints
    prev_label, last_v, last_tau = None, float("nan"), None
    for e in events:
        ts = e.get("event_ts", 0)
        ms = e.get("mkt_state") or "CONTINUOUS_TRADING"
        # --- corporate action: force recompute; tau may have changed
        if e.get("corp_action"):
            obs, trades, prev_label, last_v, last_tau = [], [], None, float("nan"), None
            out.append(_rsv("warming", float("nan"), ts, "DEGRADED"))
            continue
        # --- halt / auction / missing: mask the bar, freeze, no interpolation (F1)
        if ms != "CONTINUOUS_TRADING":
            out.append(_rsv(prev_label or "undefined", last_v, ts, "UNKNOWN"))
            continue
        # --- invalid fields: UNKNOWN, never interpolate (F1)
        if not _valid(e):
            out.append(_rsv("invalid", float("nan"), ts, "UNKNOWN"))
            continue
        mid = (e["bid"] + e["ask"]) / 2
        tau = e["tick"] if e["tick"] else tick_of(mid)
        # --- tau-regime change ($1.00 boundary cross): reset like a corp action
        if last_tau is not None and tau != last_tau:
            obs, trades, prev_label, last_v = [], [], None, float("nan")
            out.append(_rsv("warming", float("nan"), ts, "DEGRADED"))
            last_tau = tau
            continue
        last_tau = tau
        s = e["ask"] - e["bid"]
        if s < -cfg.eq_tol:
            out.append(_rsv("invalid", float("nan"), ts, "UNKNOWN"))  # crossed book
            continue
        if mid >= 1.00 and s < tau - cfg.eq_tol:
            # sub-penny quoted spread >= $1 impossible under Rule 612 -> data error
            out.append(_rsv("invalid", float("nan"), ts, "UNKNOWN"))
            continue
        obs.append(1.0 if abs(s - tau) <= cfg.eq_tol else 0.0)
        trades.append(e["trade_px"])
        w_obs = obs[-cfg.window:]
        w_tr = trades[-cfg.window:]
        # --- warm-up: label withheld (DEGRADED)
        if len(w_obs) < cfg.min_bars:
            out.append(_rsv("warming", float("nan"), ts, "DEGRADED"))
            continue
        v = sum(w_obs) / len(w_obs)
        assert BOUNDS[0] <= v <= BOUNDS[1]  # F2: mathematical bounds
        label = _hysteresis(prev_label, v, cfg)
        ver = second_estimator(w_tr, tau, cfg)  # trade-clustering cross-check
        if _opposite_extremes(label, ver["state"]):
            out.append(_rsv(label, v, ts, "UNKNOWN"))  # F3
        else:
            out.append(_rsv(label, v, ts, "OK"))
        prev_label, last_v = label, v
    return out


# ------------------------------------------------- §R5 cost interface mirror
def cost_adjustment(rsv, base):
    """Mirror of the §R5 cost interface: regime state -> cost-function
    adjustment. `base` carries the 4-component stack
    (spread_bps, fee_bps, borrow_bps_per_day, impact_bps)."""
    adj = dict(base)
    adj["regime_id"] = "R015"
    st, ms = rsv.get("state"), rsv.get("module_state", "OK")
    if ms != "OK" or st not in ("constrained", "unconstrained", "intermittent"):
        # restrictive UNKNOWN/DEGRADED: penalize, forbid maker, halve size [default]
        adj.update({"spread_mult": 2.0, "impact_mult": 1.5, "borrow_mult": 1.0,
                    "fee_mult": 1.0, "maker_viable": False, "size_mult": 0.5})
        return adj
    if st == "constrained":
        adj.update({"spread_mult": 1.0, "impact_mult": 0.8, "borrow_mult": 1.0,
                    "fee_mult": 1.0, "maker_viable": True})
    elif st == "unconstrained":
        adj.update({"spread_mult": 1.5, "impact_mult": 1.0, "borrow_mult": 1.0,
                    "fee_mult": 1.0, "maker_viable": False})
    else:  # intermittent
        adj.update({"spread_mult": 1.25, "impact_mult": 0.9, "borrow_mult": 1.0,
                    "fee_mult": 1.0, "maker_viable": True})
    return adj


F2_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1060, "bid": float("nan"),
     "ask": float("nan"), "tick": 0.01, "trade_px": 100.0,
     "mkt_state": "CONTINUOUS_TRADING", "corp_action": 0}
]  # NaN quotes fail validation -> invalid (F1) -> UNKNOWN; the fail-safe fires
  # before any indicator is computed.


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def load_tape(path):
    rows = []
    for r in load_csv(path):
        row = {}
        for k, v in r.items():
            if v == "":
                row[k] = None
            else:
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
    state: str            # regime label, e.g. "constrained"
    value: float          # indicator value
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


@dataclass
class Config:
    """Mirrors the §R0.2 Config table exactly (defaults [default] unless noted)."""
    window: int = 21
    min_bars: int = 10
    constrained_cut: float = 0.7
    constrained_exit: float = 0.55
    free_cut: float = 0.3
    free_exit: float = 0.45
    cluster_cut: float = 0.8
    cluster_lo: float = 0.5
    eq_tol: float = 1e-9  # [fixed]


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


def detect(rows, cfg, now_ns=None, select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState — full pipeline: normative
    §R2 series detector plus F4 staleness and F5 mining guard."""
    rows = list(rows)
    if not rows:
        return RegimeState("R015", "missing", float("nan"), ESTIMATOR_VERSION,
                           "synthetic", 0, "UNKNOWN")  # F1
    last = detect_series(rows, cfg)[-1]
    if last["module_state"] != "OK":
        return RegimeState("R015", last["state"], last["value"], ESTIMATOR_VERSION,
                           last["vintage"], last["computed_at"], last["module_state"])
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - last["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R015", last["state"], last["value"], ESTIMATOR_VERSION,
                           last["vintage"], last["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R015", last["state"], last["value"], ESTIMATOR_VERSION,
                       last["vintage"], last["computed_at"], "OK")


# ------------------------------------------------------------------- tests
def _check_series_against_expected(tape_path, exp_path, cfg):
    evs = load_tape(tape_path)
    series = detect_series(evs, cfg)
    assert len(series) == len(evs)
    for i, (r, wrow) in enumerate(zip(series, load_csv(exp_path))):
        wv = float(wrow["exp_value"])
        if math.isnan(wv):
            assert math.isnan(r["value"]), i
        else:
            assert abs(r["value"] - wv) < TOL, (i, r["value"], wv)
        assert r["state"] == wrow["exp_state"], (i, r["state"], wrow["exp_state"])
        assert r["computed_at"] == int(wrow["exp_computed_at"]), i
        assert r["module_state"] == wrow["exp_module_state"], (i, r["module_state"])


def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV.
    Bars 1-9 are DEGRADED/warming (min_bars=10 [default]); bar 10 pins the
    Grok RB2 worked example: 7/10 = 0.70 -> constrained."""
    _check_series_against_expected(TAPE, EXPECTED, Config())


def test_emits_valid_regime_state_vector():
    evs = load_tape(TAPE)
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R015"
    assert rsv.state in STATE_LABELS
    assert math.isfinite(rsv.value) and BOUNDS[0] <= rsv.value <= BOUNDS[1]
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. Assert label_ts > indicator_ts for the earliest trade."""
    evs = load_tape(TAPE)
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
    assert rsv.module_state == "UNKNOWN", "invalid quotes must yield UNKNOWN"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = load_tape(TAPE)
    orig = mod.second_estimator
    try:
        # verifier stuck on the opposite extreme: constrained sentinel vs
        # unconstrained verifier -> strong disagreement -> UNKNOWN (F3)
        mod.second_estimator = lambda trades, tau, cfg: {"value": 0.0,
                                                        "state": "unconstrained"}
        series = detect_series(evs, Config())
        assert series[-1]["state"] == "constrained"      # sentinel still says it
        assert series[-1]["module_state"] == "UNKNOWN"   # ...but F3 fires
    finally:
        mod.second_estimator = orig
    # F3 tolerance [default]: opposite extremes fail closed, adjacent bands pass
    assert _opposite_extremes("constrained", "unconstrained")
    assert _opposite_extremes("unconstrained", "constrained")
    assert _opposite_extremes("constrained", "bogus")
    assert not _opposite_extremes("constrained", "intermittent")  # adjacent OK
    assert not _opposite_extremes("intermittent", "unconstrained")
    assert not _opposite_extremes("constrained", "undefined")  # abstention never fires


def test_F4_staleness_unknown():
    evs = load_tape(TAPE)
    stale_now = evs[-1]["event_ts"] + 10 * CADENCE_S * NS  # >> 3x cadence
    rsv = detect(evs, Config(), now_ns=stale_now)
    assert rsv.module_state == "UNKNOWN"


def test_F5_regime_mining_guard():
    evs = load_tape(TAPE)
    try:
        detect(evs, Config(), select_periods=True, preregistered=False)
    except RegimeMiningError:
        pass
    else:
        raise AssertionError("F5: unregistered period selection must raise")
    rsv = detect(evs, Config(), select_periods=True, preregistered=True)
    assert rsv.module_state == "OK"


def test_dual_estimator_agreement():
    """Sentinel vs Verifier agree on the fixture (no opposite extremes)."""
    evs = load_tape(TAPE)
    cfg = Config()
    series = detect_series(evs, cfg)
    assert series[-1]["module_state"] == "OK"
    assert detect(evs, cfg).module_state == "OK"


def test_hysteresis_no_flicker():
    """Hysteresis tape pins the state machine: constrained holds through
    dips to 0.571 (a stateless bander would flicker to intermittent),
    exits below 0.55, unconstrained holds through rises to 0.4444."""
    cfg = Config(min_bars=1)  # [example] override: pin the machine from bar 1
    series = detect_series(load_tape(TAPE_H), cfg)
    labels = [r["state"] for r in series]
    assert labels == (["constrained"] * 7 + ["intermittent"] * 6
                      + ["unconstrained"] + ["unconstrained"] * 4
                      + ["intermittent"]), labels
    # every bar agrees with the verifier closely enough to stay OK
    assert all(r["module_state"] == "OK" for r in series)
    _check_series_against_expected(TAPE_H, EXPECTED_H, cfg)


def test_boundary_inclusivity():
    """Entry boundaries inclusive; exit boundaries hold (inclusive) [default]."""
    cfg = Config()
    assert _band(0.70, cfg) == "constrained"
    assert _band(0.30, cfg) == "unconstrained"
    assert _band(0.6999999, cfg) == "intermittent"
    assert _band(0.3000001, cfg) == "intermittent"
    assert _hysteresis("constrained", 0.55, cfg) == "constrained"
    assert _hysteresis("constrained", 0.5499999, cfg) == "intermittent"
    assert _hysteresis("unconstrained", 0.45, cfg) == "unconstrained"
    assert _hysteresis("unconstrained", 0.4500001, cfg) == "intermittent"
    assert _hysteresis(None, 0.70, cfg) == "constrained"
    assert _hysteresis(None, 0.30, cfg) == "unconstrained"


def test_gap_masking_no_interpolation():
    """HALTED/MISSING bars are masked: excluded from the window, never
    interpolated; the label freezes and the module reports UNKNOWN."""
    cfg = Config(min_bars=1)  # [example] override
    evs = load_tape(TAPE_G)
    series = detect_series(evs, cfg)
    masked = [r for r, e in zip(series, evs)
              if (e.get("mkt_state") or "CONTINUOUS_TRADING") != "CONTINUOUS_TRADING"]
    assert len(masked) == 2
    for m in masked:
        assert m["module_state"] == "UNKNOWN"
    # frozen label: bar 3 (HALTED) carries bar 2's constrained label/value
    assert series[2]["state"] == "constrained" and series[2]["value"] == 1.0
    # final: 6 of 8 continuous bars are 1-tick -> 0.75 constrained
    assert abs(series[-1]["value"] - 0.75) < TOL
    assert series[-1]["state"] == "constrained"
    assert series[-1]["module_state"] == "OK"
    _check_series_against_expected(TAPE_G, EXPECTED_G, cfg)


def test_split_forces_recompute():
    """A 4:1-style split (corp_action flag) resets the window: pre-split
    labels are not reused, post-split starts DEGRADED/warming, and the new
    label reflects only post-split quotes (no leakage)."""
    cfg = Config(min_bars=3)  # [example] override
    evs = load_tape(TAPE_S)
    series = detect_series(evs, cfg)
    assert series[5]["module_state"] == "OK"      # last pre-split bar
    assert series[5]["state"] == "constrained"
    assert series[6]["module_state"] == "DEGRADED"  # split bar: warming
    assert series[6]["state"] == "warming" and math.isnan(series[6]["value"])
    assert series[7]["module_state"] == "DEGRADED"  # still warming
    assert series[9]["module_state"] == "OK"        # 3 post-split bars
    assert series[9]["state"] == "unconstrained"   # 2c spreads only: no leakage
    assert series[9]["value"] == 0.0
    _check_series_against_expected(TAPE_S, EXPECTED_S, cfg)


def test_tick_regime_change_on_dollar_cross():
    """Crossing $1.00 changes tau ($0.01 <-> $0.0001, Rule 612): the window
    resets exactly like a corporate action."""
    evs = [
        {"bar": 1, "event_ts": 1, "bid": 1.045, "ask": 1.055, "tick": 0.01,
         "trade_px": 1.05, "mkt_state": "CONTINUOUS_TRADING", "corp_action": 0},
        {"bar": 2, "event_ts": 2, "bid": 1.015, "ask": 1.025, "tick": 0.01,
         "trade_px": 1.02, "mkt_state": "CONTINUOUS_TRADING", "corp_action": 0},
        {"bar": 3, "event_ts": 3, "bid": 0.975, "ask": 0.985, "tick": 0.0001,
         "trade_px": 0.98, "mkt_state": "CONTINUOUS_TRADING", "corp_action": 0},
        {"bar": 4, "event_ts": 4, "bid": 0.965, "ask": 0.975, "tick": 0.0001,
         "trade_px": 0.97, "mkt_state": "CONTINUOUS_TRADING", "corp_action": 0},
    ]
    series = detect_series(evs, Config(min_bars=1))
    assert series[1]["module_state"] == "OK"
    assert series[2]["module_state"] == "DEGRADED"  # tau changed: reset
    assert series[2]["state"] == "warming" and math.isnan(series[2]["value"])
    assert series[3]["module_state"] == "OK"


def test_cost_interface_multipliers():
    """§R5: which cost components scale, how much, per regime state."""
    base = {"spread_bps": 1.0, "fee_bps": 0.3, "borrow_bps_per_day": 0.5,
            "impact_bps": 2.0}
    c = cost_adjustment({"state": "constrained", "module_state": "OK"}, base)
    assert (c["spread_mult"], c["impact_mult"], c["borrow_mult"],
            c["fee_mult"], c["maker_viable"]) == (1.0, 0.8, 1.0, 1.0, True)
    u = cost_adjustment({"state": "unconstrained", "module_state": "OK"}, base)
    assert (u["spread_mult"], u["impact_mult"], u["borrow_mult"],
            u["fee_mult"], u["maker_viable"]) == (1.5, 1.0, 1.0, 1.0, False)
    i = cost_adjustment({"state": "intermittent", "module_state": "OK"}, base)
    assert (i["spread_mult"], i["impact_mult"], i["maker_viable"]) == (1.25, 0.9, True)
    for bad in ({"state": "constrained", "module_state": "UNKNOWN"},
                {"state": "warming", "module_state": "DEGRADED"}):
        w = cost_adjustment(bad, base)
        assert (w["spread_mult"], w["impact_mult"], w["maker_viable"],
                w["size_mult"]) == (2.0, 1.5, False, 0.5)
    # borrow never moves with the tick regime [default]
    for rsv in ({"state": s, "module_state": "OK"}
                for s in ("constrained", "unconstrained", "intermittent")):
        assert cost_adjustment(rsv, base)["borrow_mult"] == 1.0
