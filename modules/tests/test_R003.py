"""Acceptance tests for R003 - Volatility term-structure slope.

Template v1.0.0. Concrete sketch: loads the fixture tapes, runs a reference
implementation of the chapter's normative formula + hysteresis state machine
(§R2 TRANSITION), and asserts causality, boundary/hysteresis behavior,
F1-F5 fail-safes, dual-estimator agreement, and the §R5 cost interface.

Run: python3 -m pytest modules/tests/test_R003.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R003_tape.csv"
EXPECTED = FIX / "R003_expected.csv"
EDGE_TAPE = FIX / "R003_edge_tape.csv"
EDGE_EXPECTED = FIX / "R003_edge_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['contango', 'flat', 'backwardation', 'missing', 'invalid', 'out_of_bounds']
BOUNDS = (-1.0, 5.0)  # F2: lower bound is mathematical (vix3m>0 => slope>-1
                      # [documented]); upper bound 5.0 is a plausibility guard [default]
DUAL_MODE = "sign"  # rel | abs | sign | state
DUAL_TOL = None
ESTIMATOR_VERSION = "1.1.0"


# ============================ R003 ============================
def transition(prev_label, slope, cfg):
    """§R2 TRANSITION (normative). Entries are strict (exact boundary from
    flat -> flat); exit bands hold the prior state strictly inside the band."""
    if slope < cfg.enter_backwardation:
        return "backwardation"
    if slope > cfg.enter_contango:
        return "contango"
    if prev_label == "backwardation" and slope < cfg.enter_backwardation + cfg.hysteresis:
        return "backwardation"
    if prev_label == "contango" and slope > cfg.enter_contango - cfg.hysteresis:
        return "contango"
    return "flat"


def primary_indicator_r003(rows, cfg, prev_label="flat"):
    """Newest-last rows -> dict(value, state, module_state, computed_at, vintage)."""
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "vintage": "synthetic"}
    r = rows[-1]
    vix, v3m = r.get("vix"), r.get("vix3m")
    if vix is None or v3m is None or not (isinstance(vix, (int, float)) and isinstance(v3m, (int, float))):
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": r.get("event_ts", 0), "vintage": "synthetic"}
    if not (math.isfinite(vix) and math.isfinite(v3m)) or vix <= 0 or v3m <= 0:
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": r.get("event_ts", 0), "vintage": "synthetic"}
    slope = (v3m - vix) / vix  # [documented] practitioner slope
    prev = prev_label if prev_label in ("contango", "backwardation") else "flat"
    state = transition(prev, slope, cfg)
    return {"value": slope, "state": state, "module_state": "OK",
            "computed_at": r["event_ts"], "vintage": "synthetic"}


def second_estimator_r003(rows, cfg):
    """F3: algebraic cross-check via the IVTS formulation (same inputs, so this
    guards implementation error, NOT vendor error — documented limitation)."""
    rows = list(rows)
    r = rows[-1]
    ivts = r["vix"] / r["vix3m"]  # [documented] practitioner ratio
    if ivts > 1:
        state = "backwardation"
    elif ivts < 1:
        state = "contango"
    else:
        state = "flat"
    return {"value": 1.0 - ivts, "state": state, "computed_at": r["event_ts"] if rows else 0}


def cost_adjustment(rsv_state, base):
    """§R5 cost interface: regime state -> cost-function adjustment (normative)."""
    adj = dict(base)
    adj.setdefault("edge_mult", 1.0)
    adj["trade_ok"] = True
    if rsv_state == "backwardation":
        adj["trade_ok"] = False                                   # [rule] stand down short-vol carry
        adj["edge_mult"] = 2.0                                    # [example]
        adj["spread_bps"] = base["spread_bps"] * 1.5              # [example] gap risk
        adj["impact_bps"] = base["impact_bps"] * 2.0              # [example] thin book
        adj["max_holding_days"] = base.get("max_holding_days", 5) * 0.5  # [example]
        adj["borrow_bps"] = base["borrow_bps"]                    # unchanged
        adj["fee_bps"] = base["fee_bps"]                          # unchanged
    elif rsv_state == "flat":
        adj["edge_mult"] = 1.25                                   # [example] watch state
    adj["rsv_state"] = rsv_state                                  # provenance tag
    return adj


F2_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1001, "vix": 1.0, "vix3m": 50.0}
]  # slope = 49, outside bounds


primary_indicator = primary_indicator_r003
second_estimator = second_estimator_r003


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
            v = v.strip()
            if v == "":
                row[k] = None
                continue
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
    state: str            # regime label, e.g. "backwardation"
    value: float          # indicator value
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


@dataclass(frozen=True)
class Config:
    # entry/exit thresholds + hysteresis; calibrate per §R2 recipe (status calibrate)
    enter_contango: float = 0.10       # strict > entry [default]
    enter_backwardation: float = -0.05  # strict < entry [default]
    hysteresis: float = 0.03          # exit band [default]
    max_surface_age_days: int = 1     # F4 staleness TTL [default]


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


def detect(rows, cfg, prev_state="flat", now_ns=None, select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState — reference implementation
    with the normative TRANSITION state machine and F1-F5 fail-safes
    (Appendix f v1.0.0)."""
    rows = list(rows)
    r = primary_indicator(rows, cfg, prev_state)
    if r["module_state"] != "OK":
        return RegimeState("R003", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo < v <= hi):
        return RegimeState("R003", "out_of_bounds", v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F3: dual-estimator agreement (sign mode: same sign of slope vs 1-IVTS)
    s = second_estimator(rows, cfg)
    agree = within_tolerance(v, s["value"], DUAL_MODE, DUAL_TOL)
    if not agree:
        return RegimeState("R003", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — max_surface_age_days of event time
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > cfg.max_surface_age_days * CADENCE_S * NS:
        return RegimeState("R003", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R003", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


def sequential_detect(evs, cfg, **kw):
    """Thread prev_state through a tape, returning the list of RegimeStates."""
    out, prev = [], "flat"
    for i in range(len(evs)):
        rsv = detect(evs[: i + 1], cfg, prev_state=prev, **kw)
        out.append(rsv)
        if rsv.module_state == "OK":
            prev = rsv.state
        else:
            prev = "flat"  # invalid/missing -> hysteresis memory resets [default]
    return out


# ------------------------------------------------------------------- tests
def _check_tape(path, expected_path):
    evs = tape(path)
    exp = {int(r["bar"]): r for r in load_csv(expected_path)}
    cfg = Config()
    got = sequential_detect(evs, cfg)
    assert len(got) == len(exp) == len(evs)
    for i, rsv in enumerate(got, 1):
        want = exp[i]
        wv_raw = want["exp_value"].strip()
        if wv_raw == "":
            assert math.isnan(rsv.value), i
        else:
            assert abs(rsv.value - float(wv_raw)) < TOL, i
        assert rsv.state == want["exp_state"], (i, rsv.state, want["exp_state"])
        assert rsv.computed_at == int(want["exp_computed_at"]), i
        assert rsv.module_state == want["exp_module_state"], i


def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar (with hysteresis
    memory) matches expected CSV. Bars 3/6 pin the hysteresis hold."""
    _check_tape(TAPE, EXPECTED)


def test_edge_tape_boundaries_and_hysteresis():
    """Exact entry boundaries (strict) -> no entry; exit bands hold then
    release; missing/non-positive inputs -> UNKNOWN; recovery after invalid."""
    _check_tape(EDGE_TAPE, EDGE_EXPECTED)


def test_hysteresis_hold_explicit():
    """Near-threshold slope does not flap the label (main tape bars 3 and 6)."""
    evs = tape()
    cfg = Config()
    got = sequential_detect(evs, cfg)
    assert got[2].state == "contango"       # slope 0.0952: inside exit band, holds
    assert got[5].state == "backwardation"  # slope -0.0417: inside exit band, holds


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = sequential_detect(evs, Config())[-1]
    assert rsv.regime_id == "R003"
    assert rsv.state in STATE_LABELS
    assert math.isfinite(rsv.value) and BOUNDS[0] < rsv.value <= BOUNDS[1]
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. Assert label_ts > indicator_ts for the earliest trade."""
    evs = tape()
    cfg = Config()
    prev = "flat"
    for i in range(len(evs) - 1):
        label = detect(evs[: i + 1], cfg, prev_state=prev)
        if label.module_state == "OK":
            prev = label.state
        indicator_ts = evs[i]["event_ts"]          # newest data used
        assert label.computed_at == indicator_ts  # label stamped at t, not later
        earliest_trade_ts = evs[i + 1]["event_ts"]
        assert earliest_trade_ts > label.computed_at, f"lookahead at bar {{i}}"
    # appending a future breakout bar must not move the label stamped at t
    label_t = detect(evs[:-1], cfg, prev_state="flat")
    assert label_t.computed_at == evs[-2]["event_ts"]


def test_F1_missing_input_unknown():
    assert detect([], Config()).module_state == "UNKNOWN"
    bad = [dict(event_ts=1, asof_ts=2)]  # missing indicator fields
    assert detect(bad, Config()).module_state == "UNKNOWN"
    bad2 = [dict(event_ts=1, asof_ts=2, vix=20.0, vix3m=None)]
    assert detect(bad2, Config()).module_state == "UNKNOWN"
    bad3 = [dict(event_ts=1, asof_ts=2, vix=0.0, vix3m=20.0)]  # non-positive
    assert detect(bad3, Config()).module_state == "UNKNOWN"


def test_F2_bounds_violation_unknown():
    rsv = detect(F2_POISON_TAPE, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"
    assert rsv.state == "out_of_bounds"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = tape()
    orig = mod.second_estimator
    p0 = primary_indicator(evs, Config())["value"]
    bad_val = -1e9 if (p0 >= 0) else 1e9  # opposite sign: disagrees in sign mode
    try:
        mod.second_estimator = lambda rows, cfg: {"value": bad_val, "state": "bogus",
                                                 "computed_at": evs[-1]["event_ts"]}
        rsv = mod.detect(evs, Config())
        assert rsv.module_state == "UNKNOWN"
    finally:
        mod.second_estimator = orig


def test_F4_staleness_unknown():
    evs = tape()
    cfg = Config()
    stale_now = evs[-1]["event_ts"] + 10 * CADENCE_S * NS  # >> max_surface_age_days
    rsv = detect(evs, cfg, now_ns=stale_now)
    assert rsv.module_state == "UNKNOWN"
    boundary_now = evs[-1]["event_ts"] + cfg.max_surface_age_days * CADENCE_S * NS
    assert detect(evs, cfg, now_ns=boundary_now).module_state == "OK"  # at TTL: still OK
    assert detect(evs, cfg, now_ns=boundary_now + 1).module_state == "UNKNOWN"  # past TTL: UNKNOWN


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
    """Sentinel vs Verifier agree (sign mode) on both fixture tapes."""
    cfg = Config()
    for path in (TAPE, EDGE_TAPE):
        prev = "flat"
        for i, ev in enumerate(tape(path)):
            r = primary_indicator(tape(path)[: i + 1], cfg, prev)
            if r["module_state"] != "OK":
                continue
            s = second_estimator(tape(path)[: i + 1], cfg)
            assert within_tolerance(r["value"], s["value"], DUAL_MODE, DUAL_TOL), (i, r, s)
            if r["module_state"] == "OK":
                prev = r["state"]


def test_cost_interface_adjustments():
    """§R5: backwardation vetoes short-vol carry and scales cost components;
    flat applies the watch multiplier; contango leaves the stack untouched."""
    base = {"spread_bps": 10.0, "fee_bps": 1.0, "borrow_bps": 5.0,
            "impact_bps": 4.0, "edge_mult": 1.0, "max_holding_days": 5}
    back = cost_adjustment("backwardation", base)
    assert back["trade_ok"] is False
    assert back["edge_mult"] == 2.0
    assert back["spread_bps"] == 15.0
    assert back["impact_bps"] == 8.0
    assert back["max_holding_days"] == 2.5
    assert back["borrow_bps"] == 5.0 and back["fee_bps"] == 1.0  # unchanged
    assert back["rsv_state"] == "backwardation"  # provenance tag
    flat = cost_adjustment("flat", base)
    assert flat["trade_ok"] is True and flat["edge_mult"] == 1.25
    assert flat["spread_bps"] == 10.0  # only edge_mult moves in flat
    calm = cost_adjustment("contango", base)
    assert calm["trade_ok"] is True and calm["edge_mult"] == 1.0
    assert calm["spread_bps"] == 10.0 and calm["impact_bps"] == 4.0
