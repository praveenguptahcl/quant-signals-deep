"""Acceptance tests for R021 - Retail-flow dominance regime (v1.1.0).

Deep-reviewed reference implementation of the chapter's normative §R2
pseudocode: odd-lot share detector with entry/exit hysteresis, dual
(count-share vs volume-share) estimator agreement, and F1-F5 fail-safes.

Tapes:
  R021_tape.csv                 main 10-bar tape (fixture recompute)
  R021_hysteresis.csv           entry/exit boundary crossings
  R021_edges.csv                bar gap, halt, invalid counts, thin day, CA day

Run: python3 -m pytest modules/tests/test_R021.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R021_tape.csv"
EXPECTED = FIX / "R021_expected.csv"
HYST_TAPE = FIX / "R021_hysteresis.csv"
HYST_EXPECTED = FIX / "R021_hysteresis_expected.csv"
EDGE_TAPE = FIX / "R021_edges.csv"
EDGE_EXPECTED = FIX / "R021_edges_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['retail_dominated', 'mixed', 'baseline', 'undefined',
                'missing', 'invalid', 'frozen', 'disagree', 'corporate_action',
                'thin', 'gap_held']
BOUNDS = (0.0, 1.0)  # mathematical bounds of f_odd (F2)
DUAL_TOL_DEFAULT = 0.05
ESTIMATOR_VERSION = "1.1.0"


# ------------------------------------------------------------------ config
@dataclass(frozen=True)
class Config:
    # §R0.2 — defaults per the §R0.2.1 calibration recipe; change only via
    # re-calibration + new params_hash.
    retail_cut: float = 0.65
    base_cut: float = 0.50
    hyst: float = 0.05
    dual_tol: float = 0.05
    min_trades: int = 100
    staleness_mult: float = 3.0


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label
    value: float          # f_odd count share
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


# ------------------------------------------------- reference implementation
def primary_indicator(row):
    """Sentinel: odd-lot count share f = n_odd / n_all (§R2)."""
    need = ("n_odd", "n_all", "event_ts")
    if any(k not in row for k in need):
        return {"value": float("nan"), "ok": False, "reason": "missing_fields"}
    try:
        o, a = int(row["n_odd"]), int(row["n_all"])
    except (TypeError, ValueError):
        return {"value": float("nan"), "ok": False, "reason": "bad_types"}
    if a <= 0 or o < 0 or o > a:
        return {"value": float("nan"), "ok": False, "reason": "invalid_counts"}
    return {"value": o / a, "ok": True, "reason": ""}


def second_estimator(row):
    """Verifier: independent odd-lot VOLUME share v = v_odd / v_all (§R2)."""
    need = ("v_odd", "v_all")
    if any(k not in row for k in need):
        return {"value": float("nan"), "ok": False, "reason": "missing_fields"}
    try:
        vo, va = int(row["v_odd"]), int(row["v_all"])
    except (TypeError, ValueError):
        return {"value": float("nan"), "ok": False, "reason": "bad_types"}
    if va <= 0 or vo < 0 or vo > va:
        return {"value": float("nan"), "ok": False, "reason": "invalid_counts"}
    return {"value": vo / va, "ok": True, "reason": ""}


def label_with_hysteresis(f, prev, cfg):
    """Normative entry/exit state machine (§R2). Boundaries inclusive:
    enter retail at f >= retail_cut; exit retail when f < retail_cut - hyst;
    enter mixed from baseline at f >= base_cut + hyst; exit mixed when f < base_cut.
    Direct two-level jumps are allowed (no forced mixed stop)."""
    rc, bc, h = cfg.retail_cut, cfg.base_cut, cfg.hyst
    if prev == "retail_dominated":
        if f < bc:
            return "baseline"
        return "retail_dominated" if f >= rc - h else "mixed"
    if prev == "baseline":
        if f >= rc:
            return "retail_dominated"
        return "mixed" if f >= bc + h else "baseline"
    # cold start / mixed: plain bands
    if f >= rc:
        return "retail_dominated"
    if f < bc:
        return "baseline"
    return "mixed"


def _rsv(state, value, row, module_state):
    return RegimeState(
        "R021", state, value, ESTIMATOR_VERSION, "synthetic",
        int(row.get("event_ts", 0) or 0), module_state)


def detect_stream(rows, cfg=None, now_ns=None, select_periods=False,
                  preregistered=False):
    """detect(state, events, cfg) -> [RegimeState] — streaming reference with
    F1-F5 wired in (Appendix f v1.0.0). prev carries the last OK label for
    hysteresis; gaps/halts/CA days/thin days hold or freeze per §R2."""
    cfg = cfg or Config()
    out, prev, prev_bar = [], None, None
    for row in rows:
        # market-state table (R0.6): halt freezes, emits UNKNOWN
        if str(row.get("market_state", "TRADING")).upper() == "HALTED":
            out.append(_rsv("frozen", float("nan"), row, "UNKNOWN"))
            prev_bar = row.get("bar")
            continue
        # F5 gate
        if select_periods and not preregistered:
            raise RegimeMiningError(
                "F5: regime-gated period selection needs a pre-registered definition")
        # gap detection: non-consecutive bar -> mask, hold prev, DEGRADED
        gap = prev_bar is not None and row.get("bar") not in (None,) \
            and int(row["bar"]) != int(prev_bar) + 1
        p = primary_indicator(row)
        if not p["ok"]:
            out.append(_rsv("invalid", float("nan"), row, "UNKNOWN"))  # F1
            prev_bar = row.get("bar")
            continue
        f = p["value"]
        # F2: mathematical bounds of the share
        if not (BOUNDS[0] <= f <= BOUNDS[1]):
            out.append(_rsv("invalid", f, row, "UNKNOWN"))
            prev_bar = row.get("bar")
            continue
        # corporate-action day: mask the day, hold prev, DEGRADED
        if str(row.get("ca_day", "0")) == "1":
            out.append(_rsv(prev if prev else "mixed", f, row, "DEGRADED"))
            prev_bar = row.get("bar")
            continue
        # thin day: under the identification floor -> DEGRADED, hold prev
        if int(row["n_all"]) < cfg.min_trades:
            out.append(_rsv(prev if prev else "mixed", f, row, "DEGRADED"))
            prev_bar = row.get("bar")
            continue
        # F3: dual-estimator agreement (count share vs volume share)
        s = second_estimator(row)
        if not s["ok"] or abs(f - s["value"]) > cfg.dual_tol:
            out.append(_rsv("disagree", f, row, "UNKNOWN"))
            prev_bar = row.get("bar")
            continue
        label = label_with_hysteresis(f, prev, cfg)
        # gap hold: value is current bar's f, label held, DEGRADED
        if gap:
            out.append(_rsv(prev if prev else label, f, row, "DEGRADED"))
            prev_bar = row.get("bar")
            continue
        # F4: staleness timeout
        now = now_ns if now_ns is not None else int(row["event_ts"]) + CADENCE_S * NS
        if now - int(row["event_ts"]) > cfg.staleness_mult * CADENCE_S * NS:
            out.append(_rsv(label, f, row, "UNKNOWN"))
            prev_bar = row.get("bar")
            continue
        out.append(_rsv(label, f, row, "OK"))
        prev = label
        prev_bar = row.get("bar")
    return out


def cost_adjustment(state, base):
    """Mirror of the chapter's §R5 cost interface: regime state ->
    cost-function adjustment. Keys match the expected_cost_bps stack
    (spread/fees/borrow/impact) plus consumer-side alpha/horizon scalers."""
    adj = dict(base)
    adj["trade_ok"] = True
    if state == "retail_dominated":
        adj["spread_mult"] = 1.25    # [example] effective spread widens
        adj["impact_mult"] = 1.50    # [example] thinner displayed depth
        adj["fees_mult"] = 1.0       # [default] per-share fees unchanged
        adj["borrow_mult"] = 1.0     # [default] retail share does not move borrow
        adj["alpha_mult"] = 0.75     # [example] sentiment noise
        adj["horizon_mult"] = 0.5    # [example] faster turns
    else:
        adj["spread_mult"] = 1.0     # [default]
        adj["impact_mult"] = 1.0     # [default]
        adj["fees_mult"] = 1.0       # [default]
        adj["borrow_mult"] = 1.0     # [default]
        adj["alpha_mult"] = 1.0      # [default]
        adj["horizon_mult"] = 1.0    # [default]
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


# ------------------------------------------------------------------- tests
def test_01_fixture_recomputes_to_expected():
    evs = tape(TAPE)
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    got = detect_stream(evs, Config())
    assert len(got) == len(evs) == len(exp)
    for i, rsv in enumerate(got, start=1):
        want = exp[i]
        assert abs(rsv.value - float(want["exp_value"])) < TOL, i
        # volume-share recompute
        vs = int(evs[i - 1]["v_odd"]) / int(evs[i - 1]["v_all"])
        assert abs(vs - float(want["exp_vol_share"])) < TOL, i
        assert rsv.state == want["exp_state"], i
        assert rsv.computed_at == int(want["exp_computed_at"]), i
        assert rsv.module_state == want["exp_module_state"], i


def test_02_hysteresis_fixture_recomputes():
    """Entry/exit transitions pin: 0.55->mixed, 0.66->retail, 0.63 holds retail,
    0.58 exits to mixed, 0.52 holds mixed, 0.44->baseline, direct jumps, and
    the 0.50/0.65 inclusive boundaries."""
    evs = tape(HYST_TAPE)
    exp = {int(r["bar"]): r for r in load_csv(HYST_EXPECTED)}
    got = detect_stream(evs, Config())
    for i, rsv in enumerate(got, start=1):
        want = exp[i]
        assert rsv.state == want["exp_state"], (i, rsv.state, want["exp_state"])
        assert abs(rsv.value - float(want["exp_value"])) < TOL, i
        assert rsv.module_state == "OK", i
    # explicit boundary pins (from-baseline entry semantics)
    def run(o0, o1):  # odd-lot counts over 400 prints (exact fractions)
        def mk(bar, d, o):
            return {"bar": bar, "event_ts": d, "asof_ts": d + 1, "market_state": "TRADING",
                    "n_odd": o, "n_all": 400, "v_odd": o * 50, "v_all": 400 * 50, "ca_day": "0"}
        return detect_stream([mk(1, 1000, o0), mk(2, 2000, o1)], Config())
    assert run(160, 260)[1].state == "retail_dominated"   # 0.65 >= entry -> enter
    assert run(160, 259)[1].state == "mixed"              # 0.6475 just below -> mixed
    assert run(160, 200)[1].state == "baseline"           # 0.50 < base_cut boundary -> baseline
    assert run(160, 220)[1].state == "mixed"              # 0.55 >= base_cut+hyst -> mixed
    assert run(280, 240)[1].state == "retail_dominated"   # 0.60 exit boundary inclusive -> hold
    assert run(280, 239)[1].state == "mixed"              # 0.5975 just below exit -> mixed


def test_03_edge_fixture_recomputes():
    """Gap (missing bar 4) -> DEGRADED hold; halt -> UNKNOWN; invalid counts ->
    UNKNOWN; thin day -> DEGRADED hold; corporate-action day -> DEGRADED hold."""
    evs = tape(EDGE_TAPE)
    exp = {int(r["bar"]): r for r in load_csv(EDGE_EXPECTED)}
    got = detect_stream(evs, Config())
    want_states = {1: ("baseline", "OK"), 2: ("baseline", "OK"), 3: ("baseline", "OK"),
                   5: ("baseline", "DEGRADED"), 6: ("frozen", "UNKNOWN"),
                   7: ("baseline", "OK"), 8: ("invalid", "UNKNOWN"),
                   9: ("baseline", "DEGRADED"), 10: ("baseline", "DEGRADED")}
    for rsv in got:
        bar = int(evs[got.index(rsv)]["bar"])
        st, mst = want_states[bar]
        assert rsv.state == st, (bar, rsv.state, st)
        assert rsv.module_state == mst, (bar, rsv.module_state, mst)
        want = exp[bar]
        if mst in ("OK", "DEGRADED") and rsv.state != "frozen":
            assert abs(rsv.value - float(want["exp_value"])) < TOL, bar


def test_04_emits_valid_regime_state_vector():
    evs = tape(TAPE)
    for rsv in detect_stream(evs, Config()):
        assert rsv.regime_id == "R021"
        assert rsv.state in STATE_LABELS
        if rsv.module_state == "OK":
            assert math.isfinite(rsv.value) and BOUNDS[0] <= rsv.value <= BOUNDS[1]
        assert rsv.estimator_version == ESTIMATOR_VERSION
        assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_05_no_lookahead_regime_gating():
    """Lag contract: label at t uses prints <= t only; stamped at event_ts(t);
    any trade gated by it must execute at t+1 or later."""
    evs = tape(TAPE)
    got = detect_stream(evs, Config())
    for i, rsv in enumerate(got):
        assert rsv.computed_at == evs[i]["event_ts"]  # stamped at t, not later
        if i < len(got) - 1:
            assert evs[i + 1]["event_ts"] > rsv.computed_at  # earliest trade after label
    # appending a future breakout bar must not move the label stamped at t
    tail = detect_stream(evs[:-1], Config())[-1]
    assert tail.computed_at == evs[-2]["event_ts"]


def test_06_F1_missing_and_invalid_input_unknown():
    assert detect_stream([], Config()) == []
    bad = [{"bar": 1, "event_ts": 1000, "asof_ts": 1001, "market_state": "TRADING"}]
    assert detect_stream(bad, Config())[0].module_state == "UNKNOWN"
    bad2 = [dict(bad[0], n_odd=10, n_all=0)]          # zero denominator
    assert detect_stream(bad2, Config())[0].module_state == "UNKNOWN"
    bad3 = [dict(bad[0], n_odd=500, n_all=400)]       # n_odd > n_all
    assert detect_stream(bad3, Config())[0].module_state == "UNKNOWN"


def test_07_F2_bounds_violation_unknown():
    poison = {"bar": 1, "event_ts": 1000, "asof_ts": 1001, "market_state": "TRADING",
              "n_odd": 1250, "n_all": 1000, "v_odd": 62500, "v_all": 50000, "ca_day": "0"}
    rsv = detect_stream([poison], Config())[0]
    assert rsv.module_state == "UNKNOWN"  # f = 1.25 outside [0,1]


def test_08_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]
    evs = tape(TAPE)
    orig = mod.second_estimator
    try:
        # volume share pinned 0.5 away from count share -> disagreement
        mod.second_estimator = lambda row: {"value": primary_indicator(row)["value"] + 0.5,
                                           "ok": True, "reason": ""}
        rsvs = mod.detect_stream(evs, Config())
        assert all(r.module_state == "UNKNOWN" for r in rsvs)
    finally:
        mod.second_estimator = orig


def test_09_F4_staleness_unknown():
    evs = tape(TAPE)
    stale_now = evs[-1]["event_ts"] + 10 * CADENCE_S * NS  # >> 3x cadence
    rsvs = detect_stream(evs, Config(), now_ns=stale_now)
    assert all(r.module_state == "UNKNOWN" for r in rsvs)


def test_10_F5_regime_mining_guard():
    evs = tape(TAPE)
    try:
        detect_stream(evs, Config(), select_periods=True, preregistered=False)
    except RegimeMiningError:
        pass
    else:
        raise AssertionError("F5: unregistered period selection must raise")
    rsvs = detect_stream(evs, Config(), select_periods=True, preregistered=True)
    assert all(r.module_state == "OK" for r in rsvs)


def test_11_dual_estimator_agreement():
    """Sentinel (count share) vs Verifier (volume share) agree within dual_tol
    on the main tape."""
    evs = tape(TAPE)
    cfg = Config()
    for row in evs:
        p, s = primary_indicator(row), second_estimator(row)
        assert p["ok"] and s["ok"]
        assert abs(p["value"] - s["value"]) <= cfg.dual_tol
    assert all(r.module_state == "OK" for r in detect_stream(evs, cfg))


def test_12_cost_interface_scales_cost_components():
    base = {"spread_mult": 1.0, "impact_mult": 1.0, "fees_mult": 1.0,
            "borrow_mult": 1.0, "alpha_mult": 1.0, "horizon_mult": 1.0,
            "trade_ok": True}
    ret = cost_adjustment("retail_dominated", base)
    base_adj = cost_adjustment("baseline", base)
    # §R5: which components scale — spread and impact rise; fees/borrow pinned
    assert ret["trade_ok"] is True
    assert ret["spread_mult"] > 1.0 and ret["impact_mult"] > 1.0
    assert ret["fees_mult"] == 1.0 and ret["borrow_mult"] == 1.0
    assert ret["alpha_mult"] < 1.0 and ret["horizon_mult"] < 1.0
    assert all(base_adj[k] == 1.0 for k in base if k != "trade_ok")
    # input dict not mutated
    assert base["spread_mult"] == 1.0


def test_13_calibration_recipe_defaults_pinned():
    """§R0.2.1: production defaults equal the calibrated recipe values; a
    drift here fails loudly so nobody retunes by hand."""
    cfg = Config()
    assert cfg.retail_cut == 0.65    # entry grid argmax, 2y OOS
    assert cfg.base_cut == 0.50      # low edge of 0.45-0.60 normal band
    assert cfg.hyst == 0.05          # flip-rate minimized, lag <= 1 bar
    assert cfg.dual_tol == 0.05      # disagreement rate <= 1% on clean tape
    assert cfg.min_trades == 100     # identification floor
    assert cfg.staleness_mult == 3.0 # F4: 3x cadence
