"""Acceptance tests for R025 - Yield-curve shape regime (v1.1.0).

Template v1.0.0. Reference implementation of the chapter's normative §R2.3
pseudocode: causal hysteresis state machine + F1-F5 fail-safes + dual
estimator (3-obs moving-average surrogate for the Treasury-XML Verifier,
marked [example] in the chapter) + the §R5 cost interface.

Run: python3 -m pytest modules/tests/test_R025.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R025_tape.csv"
EXPECTED = FIX / "R025_expected.csv"
HYST = FIX / "R025_hyst.csv"
EXPECTED_HYST = FIX / "R025_expected_hyst.csv"
GAP = FIX / "R025_gap.csv"
EXPECTED_GAP = FIX / "R025_expected_gap.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['inverted', 'flat', 'normal', 'undefined', 'warming', 'missing', 'invalid']
BOUNDS = (-1000.0, 1000.0)  # mathematical bounds of the indicator value (F2) [default]
DUAL_MODE = "abs"  # rel | abs | sign | state
DUAL_TOL = 1.0  # bps [default]; matches §R0.2 dual_tol_bps
ESTIMATOR_VERSION = "1.1.0"


# ---------------------------------------------------------------- config
@dataclass(frozen=True)
class Config:
    """Mirrors the §R0.2 Config table. test_config_defaults_match_chapter
    pins these against the chapter so logic drift fails loudly."""
    inv_cut: float = -25.0        # entry band, bp [default]
    inv_relief: float = -10.0     # inverted-exit band, bp [default]
    flat_cut: float = 25.0        # normal-entry band, bp [default]
    flat_relief: float = 10.0     # normal-exit band, bp [default]
    dual_tol_bps: float = 1.0     # F3 verifier tolerance, bp [default]
    warmup_bars: int = 1          # [default]
    staleness_mult: float = 3.0   # F4 multiplier on cadence [default]
    revision_tol_bps: float = 1.0  # §R7 FRED restatement trigger, bp [default]


# ------------------------------------------------- reference implementation
def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _transition(prev, v, cfg):
    """Normative hysteresis transition (§R2.3). prev in {None,'flat','inverted','normal'}.

    Band-edge comparisons use v rounded to 1e-9 bp [default]: a float-jitter
    guard so a feed value printed as -10 bp does not flip on 1e-12 noise."""
    v = round(v, 9)
    if prev == "inverted":
        return "flat" if v > cfg.inv_relief else "inverted"
    if prev == "normal":
        return "flat" if v < cfg.flat_relief else "normal"
    if v <= cfg.inv_cut:
        return "inverted"
    if v >= cfg.flat_cut:
        return "normal"
    return "flat"


def state_machine(rows, cfg):
    """Causal replay of the hysteresis state machine.

    Returns (labels, module_state, reason) where labels is a list of
    (event_ts, value, label). Stops at the first F1/F2 violation and reports
    UNKNOWN — never interpolates.
    """
    labels = []
    prev = None
    for r in rows:
        y10, y2 = _num(r.get("y10")), _num(r.get("y2"))
        if y10 is None or y2 is None:
            return labels, "UNKNOWN", "F1: missing field"
        v = (y10 - y2) * 100.0  # percent -> bps [documented construction]
        if not (BOUNDS[0] <= v <= BOUNDS[1]):
            return labels, "UNKNOWN", "F2: out of mathematical bounds"
        prev = _transition(prev, v, cfg)
        labels.append((r["event_ts"], v, prev))
    return labels, "OK", ""


def primary_indicator(rows, cfg):
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "vintage": "synthetic"}
    labels, mstate, reason = state_machine(rows, cfg)
    if mstate != "OK":
        tag = "invalid" if reason.startswith("F2") else "invalid"
        return {"value": float("nan"), "state": tag, "module_state": "UNKNOWN",
                "computed_at": rows[-1].get("event_ts", 0), "vintage": "synthetic"}
    _, v, label = labels[-1]
    return {"value": v, "state": label, "module_state": "OK",
            "computed_at": labels[-1][0], "vintage": "synthetic"}


def second_estimator(rows, cfg):
    """[example] surrogate for the Treasury-XML Verifier: 3-obs average spread.
    Production wires the independent Treasury feed (§R4 honesty note)."""
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "undefined", "computed_at": 0}
    vals = []
    for r in rows[-3:]:
        y10, y2 = _num(r.get("y10")), _num(r.get("y2"))
        if y10 is None or y2 is None:
            return {"value": float("nan"), "state": "undefined",
                    "computed_at": rows[-1].get("event_ts", 0)}
        vals.append((y10 - y2) * 100.0)
    return {"value": sum(vals) / len(vals), "state": "n/a",
            "computed_at": rows[-1]["event_ts"]}


def cost_adjustment(rsv_state, base):
    """§R5 cost interface: regime state -> cost-function adjustment.
    rsv_state in {'inverted','flat','normal'}. base holds
    spread_bps, borrow_bps, impact_bps, fee_bps [example schema]."""
    adj = dict(base)
    s = rsv_state
    adj["trade_ok"] = True  # [default]; veto decisions live in the T-module
    adj["spread_mult"] = 1.5 if s == "inverted" else (1.1 if s == "flat" else 1.0)
    adj["borrow_bps_add"] = 2.0 if s == "inverted" else 0.0  # bps/day
    adj["impact_mult"] = 1.3 if s == "inverted" else (1.1 if s == "flat" else 1.0)
    adj["fee_mult"] = 1.0
    adj["quality_tilt"] = 1.25 if s == "inverted" else 1.0
    adj["duration_tilt"] = 0.75 if s == "inverted" else 1.0
    return adj


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label, e.g. "inverted"
    value: float          # indicator value, bps
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
    of the §R2.3 normative pseudocode with F1-F5 fail-safes (Appendix f v1.0.0)."""
    rows = list(rows)
    r = primary_indicator(rows, cfg)
    if r["module_state"] != "OK":
        return RegimeState("R025", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    v = r["value"]
    # F3: dual-estimator agreement (abs mode; the surrogate is slow-moving,
    # so disagreement only fires on genuinely divergent feeds)
    s = second_estimator(rows, cfg)
    if not (math.isfinite(s["value"]) and within_tolerance(v, s["value"], DUAL_MODE, DUAL_TOL)):
        return RegimeState("R025", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — staleness_mult x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > cfg.staleness_mult * CADENCE_S * NS:
        return RegimeState("R025", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R025", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


F2_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1001, "y10": 20.0, "y2": 0.0},
]  # spread = 2000 bp > 1000 bound -> F2


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


def named_tape(path):
    return tape_from(path)


def tape_from(path):
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


def check_fixture_recomputes(tape_path, expected_path):
    evs = tape_from(tape_path)
    exp = {int(r["bar"]): r for r in load_csv(expected_path)}
    cfg = Config()
    for i in range(len(evs)):
        r = primary_indicator(evs[: i + 1], cfg)
        want = exp[i + 1]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(r["value"]), (tape_path, i)
        else:
            assert abs(r["value"] - wv) < TOL, (tape_path, i)
        assert r["state"] == want["exp_state"], (tape_path, i)
        assert r["computed_at"] == int(want["exp_computed_at"]), (tape_path, i)
        assert r["module_state"] == want["exp_module_state"], (tape_path, i)


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    check_fixture_recomputes(TAPE, EXPECTED)


def test_hysteresis_fixture_recomputes_to_expected():
    check_fixture_recomputes(HYST, EXPECTED_HYST)


def test_gap_fixture_recomputes_to_expected():
    check_fixture_recomputes(GAP, EXPECTED_GAP)


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R025"
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
        assert earliest_trade_ts > label.computed_at, f"lookahead at bar {{i}}"
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
    """Sentinel vs Verifier agree within tolerance on the fixture."""
    evs = tape()
    cfg = Config()
    r = primary_indicator(evs, cfg)
    s = second_estimator(evs, cfg)
    assert within_tolerance(r["value"], s["value"], DUAL_MODE, DUAL_TOL), (r, s)
    assert detect(evs, cfg).module_state == "OK"


def test_hysteresis_transitions_pinned():
    """Every row of the §R2.3 transition table that the hyst pin exercises:
    entry at -26, hold at -22/-18, exit at -8, no re-entry at -24,
    re-entry at -27."""
    evs = tape_from(HYST)
    labels, mstate, _ = state_machine(evs, Config())
    assert mstate == "OK"
    want = ["flat", "inverted", "inverted", "inverted", "flat", "flat", "inverted"]
    assert [lab for _, _, lab in labels] == want
    # hysteresis is a property of history: the same value maps to different
    # labels depending on the carry — logic drift that drops the carry fails here
    assert labels[2][2] == "inverted" and labels[5][2] == "flat"  # both ~-23/-24 region
    assert abs(labels[1][1] - -26.0) < TOL and abs(labels[4][1] - -8.0) < TOL


def test_hysteresis_boundary_values():
    """Exact boundary semantics: entry is inclusive (<=), exit is exclusive (>)."""
    cfg = Config()
    mk = lambda v: {"event_ts": 1, "asof_ts": 2, "y10": v / 100.0 + 4.5, "y2": 4.5}
    # from flat: -25 enters, -24.9 does not; +25 enters, +24.9 does not
    assert _transition("flat", -25.0, cfg) == "inverted"
    assert _transition("flat", -24.9, cfg) == "flat"
    assert _transition("flat", 25.0, cfg) == "normal"
    assert _transition("flat", 24.9, cfg) == "flat"
    assert _transition(None, -25.0, cfg) == "inverted"  # first bar: plain bands
    # from inverted: -10 holds, -9.9 exits
    assert _transition("inverted", -10.0, cfg) == "inverted"
    assert _transition("inverted", -9.9, cfg) == "flat"
    # from normal: +10 holds, +9.9 exits
    assert _transition("normal", 10.0, cfg) == "normal"
    assert _transition("normal", 9.9, cfg) == "flat"
    # through the harness, not just the helper
    rows = [mk(-25.0)]
    assert primary_indicator(rows, cfg)["state"] == "inverted"
    rows.append(mk(-10.0))
    assert primary_indicator(rows, cfg)["state"] == "inverted"  # hold, not exit
    rows.append(mk(-9.9))
    assert primary_indicator(rows, cfg)["state"] == "flat"       # exit


def test_gap_weekend_holds_label_ok():
    """Expected calendar gap (3-day weekend): label carried, stays OK.

    The 3-obs surrogate Verifier is only valid on slow-moving series, so the
    gap tests patch in a healthy Verifier (echoes primary) to isolate the
    gap-handling logic from F3 (§R4 honesty note)."""
    import sys as _sys
    mod = _sys.modules[__name__]
    evs = tape_from(GAP)
    ok_part = evs[:4]
    assert ok_part[3]["event_ts"] - ok_part[2]["event_ts"] == 3 * CADENCE_S * NS
    labels, mstate, _ = state_machine(ok_part, Config())
    assert mstate == "OK"
    assert [lab for _, _, lab in labels] == ["flat", "inverted", "inverted", "inverted"]
    orig = mod.second_estimator
    try:
        mod.second_estimator = lambda rows, cfg: {
            "value": primary_indicator(rows, cfg)["value"], "state": "n/a",
            "computed_at": rows[-1]["event_ts"]}
        rsv = detect(ok_part, Config())
    finally:
        mod.second_estimator = orig
    assert rsv.module_state == "OK" and rsv.state == "inverted"


def test_gap_outage_beyond_ttl_unknown():
    """Unscheduled staleness: evaluation 4 days after the last bar > 3x cadence."""
    import sys as _sys
    mod = _sys.modules[__name__]
    evs = tape_from(GAP)[:4]
    orig = mod.second_estimator
    try:
        mod.second_estimator = lambda rows, cfg: {
            "value": primary_indicator(rows, cfg)["value"], "state": "n/a",
            "computed_at": rows[-1]["event_ts"]}
        rsv = detect(evs, Config(), now_ns=evs[-1]["event_ts"] + 4 * CADENCE_S * NS)
        assert rsv.module_state == "UNKNOWN"
        # but within the TTL it is fine
        rsv2 = detect(evs, Config(), now_ns=evs[-1]["event_ts"] + 2 * CADENCE_S * NS)
        assert rsv2.module_state == "OK"
    finally:
        mod.second_estimator = orig


def test_cost_interface_matches_chapter():
    """§R5 cost interface: named fields, inverted vs normal deltas, fee flat."""
    base = {"spread_bps": 10.0, "borrow_bps": 1.0, "impact_bps": 5.0, "fee_bps": 0.5}
    inv = cost_adjustment("inverted", base)
    nrm = cost_adjustment("normal", base)
    flt = cost_adjustment("flat", base)
    for adj in (inv, nrm, flt):
        assert set(adj) == {"spread_bps", "borrow_bps", "impact_bps", "fee_bps",
                            "trade_ok", "spread_mult", "borrow_bps_add",
                            "impact_mult", "fee_mult", "quality_tilt", "duration_tilt"}
        assert adj["trade_ok"] is True
        assert adj["fee_mult"] == 1.0  # fees never depend on curve shape
    assert inv["spread_mult"] == 1.5 and nrm["spread_mult"] == 1.0 and flt["spread_mult"] == 1.1
    assert inv["borrow_bps_add"] == 2.0 and nrm["borrow_bps_add"] == 0.0
    assert inv["impact_mult"] == 1.3 and nrm["impact_mult"] == 1.0 and flt["impact_mult"] == 1.1
    assert inv["quality_tilt"] == 1.25 and nrm["quality_tilt"] == 1.0
    assert inv["duration_tilt"] == 0.75 and nrm["duration_tilt"] == 1.0


def test_config_defaults_match_chapter():
    """Logic-drift guard: Config defaults must equal the §R0.2 table."""
    cfg = Config()
    assert (cfg.inv_cut, cfg.inv_relief) == (-25.0, -10.0)
    assert (cfg.flat_cut, cfg.flat_relief) == (25.0, 10.0)
    assert cfg.dual_tol_bps == 1.0
    assert cfg.warmup_bars == 1
    assert cfg.staleness_mult == 3.0
    assert cfg.revision_tol_bps == 1.0
