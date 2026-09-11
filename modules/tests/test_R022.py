"""Acceptance tests for R022 - Hard-to-borrow / short-squeeze regime.

Template v1.0.0, deep-reviewed to v1.1.0. Reference implementation of the
chapter's normative detection algorithm (§R2): entry thresholds with
asymmetric hysteresis (immediate escalation, hold-gated step-down), dual
estimator (trailing-3 medians) F3 check, warm-up DEGRADED, gap masking,
corporate-action freeze, halt/auction handling, and the §R5 cost interface.

Run: python3 -m pytest modules/tests/test_R022.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R022_tape.csv"
EXPECTED = FIX / "R022_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
DAY = CADENCE_S
NS = 1_000_000_000
LEVELS = ["normal", "elevated", "squeeze_candidate", "hard_to_borrow"]
RANK = {lv: i for i, lv in enumerate(LEVELS)}
ESTIMATOR_VERSION = "1.1.0"


# ------------------------------------------------------------------ config
@dataclass(frozen=True)
class Config:
    """§R0.2 — every default traces to the §R2 calibration recipe grid."""
    fee_entry: tuple = (0.05, 0.10, 0.15)    # elevated/SC/HTB entry [default]
    util_entry: tuple = (0.75, 0.90, 0.97)  # [default]
    dtc_entry: tuple = (4.0, 6.0, 10.0)      # [default]
    exit_dfee: float = 0.02                 # exit = entry - delta [default]
    exit_dutil: float = 0.02                # [default]
    exit_ddtc: tuple = (0.5, 0.5, 1.0)      # per level EL/SC/HTB [default]
    hold_bars: int = 3                      # de-escalation hold [default]
    dual_tol: float = 0.2                   # F3 relative tolerance [default]
    abs_tol_fee: float = 0.005              # F3 absolute floors [default]
    abs_tol_util: float = 0.01              # [default]
    abs_tol_dtc: float = 0.25               # [default]
    warmup_bars: int = 3                    # [default]
    stale_mult: float = 5.0                 # staleness TTL = 5x cadence [default]
    gap_mult: float = 1.5                   # gap mask threshold [default]
    bounds_dtc: tuple = (0.0, 500.0)        # F2 [default]
    bounds_fee: tuple = (0.0, 10.0)         # F2 [default]
    freeze_bars: int = 5                    # corporate-action freeze [default]


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label, e.g. "squeeze_candidate"
    value: float          # indicator value (days-to-cover)
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


# ------------------------------------------------------- normative detector
def _dtc(r):
    return r["si"] / r["adv"]


def entry_level(fee, util, dtc, cfg):
    """Instantaneous entry level: strict > on any of the three inputs. [default]"""
    if fee > cfg.fee_entry[2] or util > cfg.util_entry[2] or dtc > cfg.dtc_entry[2]:
        return "hard_to_borrow"
    if fee > cfg.fee_entry[1] or util > cfg.util_entry[1] or dtc > cfg.dtc_entry[1]:
        return "squeeze_candidate"
    if fee > cfg.fee_entry[0] or util > cfg.util_entry[0] or dtc > cfg.dtc_entry[0]:
        return "elevated"
    return "normal"


def exit_thresholds(level, cfg):
    """Exit = entry - hysteresis delta; ALL three must clear to de-escalate."""
    i = RANK[level] - 1  # index into the entry tuples of this level
    return (cfg.fee_entry[i] - cfg.exit_dfee,
            cfg.util_entry[i] - cfg.exit_dutil,
            cfg.dtc_entry[i] - cfg.exit_ddtc[i])


def label_path(rows, cfg):
    """Causal label path with asymmetric hysteresis: escalation is immediate,
    de-escalation steps down one level per `hold_bars` qualifying bars."""
    state, hold = "normal", 0
    out = []
    for r in rows:
        dtc = _dtc(r)
        el = entry_level(r["fee_ann"], r["util"], dtc, cfg)
        if RANK[el] > RANK[state]:
            state, hold = el, 0
        elif RANK[el] == RANK[state]:
            hold = 0
        else:
            fe, ue, de = exit_thresholds(state, cfg)
            if r["fee_ann"] < fe and r["util"] < ue and dtc < de:
                hold += 1
            else:
                hold = 0
            if hold >= cfg.hold_bars:
                state = LEVELS[RANK[state] - 1]
                hold = 0
        out.append({"dtc": dtc, "entry_level": el, "state": state})
    return out


def _median(xs):
    s = sorted(xs)
    return s[len(s) // 2]


def second_estimator(rows, cfg):
    """Verifier: trailing-3-observation medians of (fee, util, DTC), independent
    recomputation of the inputs. In production this pulls the secondary feed."""
    w = rows[-3:]
    fm = _median(r["fee_ann"] for r in w)
    um = _median(r["util"] for r in w)
    dm = _median(_dtc(r) for r in w)
    return {"fee": fm, "util": um, "dtc": dm,
            "entry_level": entry_level(fm, um, dm, cfg),
            "computed_at": rows[-1]["event_ts"]}


def _rel_ok(a, b, tol, floor):
    return abs(a - b) <= tol * max(abs(a), abs(b), 1e-12) or abs(a - b) <= floor


def primary_indicator(rows, cfg):
    """Full per-prefix pipeline: F1/F2 validation, hysteresis labels, warm-up,
    gap mask, corporate-action freeze, market-state handling, F3 dual check."""
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "entry_level": "normal",
                "module_state": "UNKNOWN", "computed_at": 0, "vintage": "synthetic",
                "reason": "no_input"}
    # F1: required fields, finite, sane
    for r in rows:
        try:
            ok = (math.isfinite(r["fee_ann"]) and math.isfinite(r["util"])
                  and math.isfinite(r["si"]) and math.isfinite(r["adv"])
                  and r["adv"] > 0 and r["si"] >= 0
                  and 0.0 <= r["util"] <= 1.0
                  and cfg.bounds_fee[0] <= r["fee_ann"] <= cfg.bounds_fee[1])
        except (KeyError, TypeError):
            ok = False
        if not ok:
            return {"value": float("nan"), "state": "invalid", "entry_level": "normal",
                    "module_state": "UNKNOWN",
                    "computed_at": r.get("event_ts", 0) if isinstance(r, dict) else 0,
                    "vintage": "synthetic", "reason": "invalid_input"}
    # market-state table (newest event wins)
    ms = rows[-1].get("mkt_state", "CONTINUOUS_TRADING")
    if ms == "CLOSED":
        return {"value": float("nan"), "state": "off", "entry_level": "normal",
                "module_state": "OFF", "computed_at": rows[-1]["event_ts"],
                "vintage": "synthetic", "reason": "market_closed"}
    if ms == "HALTED":
        return {"value": float("nan"), "state": "unknown_halt",
                "entry_level": "normal", "module_state": "UNKNOWN",
                "computed_at": rows[-1]["event_ts"], "vintage": "synthetic",
                "reason": "halt_freeze"}
    # gap policy: mask, no interpolation
    gaps = [rows[i + 1]["event_ts"] - rows[i]["event_ts"]
            for i in range(len(rows) - 1)]
    gap_hit = any(g > cfg.gap_mult * CADENCE_S * NS for g in gaps)
    # corporate-action freeze: hold pre-event label for `freeze_bars` bars
    ca_idx = [i for i, r in enumerate(rows) if r.get("corp_action")]
    frozen = bool(ca_idx) and (len(rows) - 1 - ca_idx[-1]) < cfg.freeze_bars
    path = label_path(rows, cfg)
    last = path[-1]
    # F2: indicator bounds
    if not (cfg.bounds_dtc[0] <= last["dtc"] <= cfg.bounds_dtc[1]):
        return {"value": last["dtc"], "state": "out_of_bounds",
                "entry_level": last["entry_level"], "module_state": "UNKNOWN",
                "computed_at": rows[-1]["event_ts"], "vintage": "synthetic",
                "reason": "bounds_violation"}
    module_state, reason = "OK", "ok"
    if frozen:
        pre = path[ca_idx[-1] - 1] if ca_idx[-1] > 0 else None
        return {"value": pre["dtc"] if pre else float("nan"),
                "state": pre["state"] if pre else "warming",
                "entry_level": pre["entry_level"] if pre else "normal",
                "module_state": "DEGRADED", "computed_at": rows[-1]["event_ts"],
                "vintage": "synthetic", "reason": "corporate_action_freeze"}
    if ms == "AUCTION":
        module_state, reason = "DEGRADED", "auction_hold"
    elif gap_hit:
        module_state, reason = "DEGRADED", "gap_masked"
    elif len(rows) < cfg.warmup_bars:
        module_state, reason = "DEGRADED", "warmup"
    else:
        # F3: dual-estimator agreement on the three inputs
        s = second_estimator(rows, cfg)
        r0 = rows[-1]
        agree = (_rel_ok(r0["fee_ann"], s["fee"], cfg.dual_tol, cfg.abs_tol_fee)
                 and _rel_ok(r0["util"], s["util"], cfg.dual_tol, cfg.abs_tol_util)
                 and _rel_ok(last["dtc"], s["dtc"], cfg.dual_tol, cfg.abs_tol_dtc))
        if not agree:
            module_state, reason = "UNKNOWN", "dual_disagreement"
    return {"value": last["dtc"], "state": last["state"],
            "entry_level": last["entry_level"], "module_state": module_state,
            "computed_at": rows[-1]["event_ts"], "vintage": "synthetic",
            "reason": reason}


def detect(rows, cfg, now_ns=None, select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState — reference implementation
    with F1-F5 fail-safes wired in (Appendix f v1.0.0)."""
    rows = list(rows)
    r = primary_indicator(rows, cfg)
    if r["module_state"] not in ("OK", "DEGRADED"):
        return RegimeState("R022", r["state"], r["value"], ESTIMATOR_VERSION,
                           r["vintage"], r["computed_at"], r["module_state"])
    # F4: staleness timeout — 5x cadence (absorbs weekends + 1 missed session)
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > cfg.stale_mult * CADENCE_S * NS:
        return RegimeState("R022", r["state"], r["value"], ESTIMATOR_VERSION,
                           r["vintage"], r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError(
            "F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R022", r["state"], r["value"], ESTIMATOR_VERSION,
                       r["vintage"], r["computed_at"], r["module_state"])


# ------------------------------------------------- §R5 cost interface
def cost_adjustment(rsv_state, module_state, fee_ann, base):
    """Regime state -> cost-function adjustment (§R5, reference implementation).

    base: 4-component cost stack {spread_bps, fees_bps, borrow_bps, impact_bps}.
    Adds the daily borrow carry (fee/360, [documented] BIS CPSS 1999), scales
    spread in squeeze states, vetoes new shorts in hard-to-borrow / UNKNOWN.
    """
    adj = dict(base)
    adj["regime"] = rsv_state
    adj["borrow_carry_bps_day"] = fee_ann / 360.0 * 10000.0  # [documented]
    adj["trade_ok"] = True
    adj["size_mult"] = 1.0  # [default]
    if module_state == "UNKNOWN":
        adj["trade_ok"] = False
        adj["reason"] = "regime_unknown"  # [default] restrictive
    elif module_state == "DEGRADED":
        adj["size_mult"] = 0.5  # [default]
        adj["reason"] = "regime_degraded"
    if rsv_state == "hard_to_borrow":
        adj["trade_ok"] = False  # [default] recall risk: new shorts vetoed
        adj["reason"] = "hard_to_borrow"
    elif rsv_state == "squeeze_candidate":
        adj["size_mult"] = min(adj["size_mult"], 0.5)  # [example]
        adj["spread_bps"] = adj["spread_bps"] * 1.5  # [example] squeeze widening
    return adj


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


def synth_tape(specs, ts0=1_788_220_800_000_000_000, adv=2e6):
    """Build an in-memory tape from (fee, util, si) triples, 1-day spacing."""
    rows = []
    for i, (f, u, si) in enumerate(specs):
        ts = ts0 + i * DAY * NS
        rows.append({"bar": i + 1, "event_ts": ts, "asof_ts": ts + 3600 * NS,
                     "fee_ann": f, "util": u, "si": si, "adv": adv})
    return rows


F2_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1001, "fee_ann": 0.12, "util": 0.93,
     "si": 2e9, "adv": 2e6},
]  # DTC = 1000 > 500 bound -> F2


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = Config()
    assert len(evs) == len(exp) > 10, "fixture must pin a full regime cycle"
    for i in range(len(evs)):
        r = primary_indicator(evs[: i + 1], cfg)
        want = exp[i + 1]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(r["value"]), i
        else:
            assert abs(r["value"] - wv) < TOL, (i, r["value"], wv)
        assert r["state"] == want["exp_state"], (i, r["state"], want["exp_state"])
        assert r["computed_at"] == int(want["exp_computed_at"]), i
        assert r["module_state"] == want["exp_module_state"], (
            i, r["module_state"], want["exp_module_state"])


def test_emits_valid_regime_state_vector():
    rsv = detect(tape(), Config())
    assert rsv.regime_id == "R022"
    assert rsv.state in LEVELS
    assert math.isfinite(rsv.value) and 0.0 <= rsv.value <= 500.0
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == tape()[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. Assert label_ts == indicator_ts and earliest gated trade
    is strictly later; appending a future bar must not move the label at t."""
    evs = tape()
    cfg = Config()
    for i in range(len(evs) - 1):
        r = primary_indicator(evs[: i + 1], cfg)
        assert r["computed_at"] == evs[i]["event_ts"]
        assert evs[i + 1]["event_ts"] > r["computed_at"], f"lookahead at bar {i}"
    r_t = primary_indicator(evs[:-1], cfg)
    assert r_t["computed_at"] == evs[-2]["event_ts"]


def test_F1_missing_input_unknown():
    assert detect([], Config()).module_state == "UNKNOWN"
    bad = [dict(event_ts=1, asof_ts=2)]  # missing indicator fields
    assert detect(bad, Config()).module_state == "UNKNOWN"
    bad2 = [dict(event_ts=1, asof_ts=2, fee_ann=0.1, util=1.5, si=1e6, adv=2e6)]
    assert detect(bad2, Config()).module_state == "UNKNOWN"  # util > 1


def test_F2_bounds_violation_unknown():
    rsv = detect(F2_POISON_TAPE, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]
    evs = tape()
    orig = second_estimator
    try:
        mod.second_estimator = lambda rows, cfg: {
            "fee": -1e9, "util": -1e9, "dtc": -1e9,
            "entry_level": "bogus", "computed_at": evs[-1]["event_ts"]}
        rsv = detect(evs, Config())
        assert rsv.module_state == "UNKNOWN"
    finally:
        mod.second_estimator = orig


def test_F4_staleness_unknown():
    evs = tape()
    stale_now = evs[-1]["event_ts"] + 10 * CADENCE_S * NS  # >> 5x cadence
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
    """Sentinel vs Verifier agree within tolerance on the full fixture tape."""
    evs = tape()
    cfg = Config()
    for i in range(cfg.warmup_bars, len(evs)):
        r = primary_indicator(evs[: i + 1], cfg)
        assert r["module_state"] == "OK", (i, r)
    assert detect(evs, cfg).module_state == "OK"


def test_warmup_is_degraded_not_ok():
    """Honest warm-up: < 3 bars => DEGRADED (label emitted, flagged)."""
    evs = tape()
    cfg = Config()
    assert primary_indicator(evs[:1], cfg)["module_state"] == "DEGRADED"
    assert primary_indicator(evs[:2], cfg)["module_state"] == "DEGRADED"
    assert primary_indicator(evs[:3], cfg)["module_state"] == "OK"


def test_hysteresis_hold_pins_state():
    """Bar 12 of the fixture: inputs fall below HTB entry but stay HTB
    because the exit band is not cleared."""
    evs = tape()
    cfg = Config()
    r11 = primary_indicator(evs[:11], cfg)
    r12 = primary_indicator(evs[:12], cfg)
    assert r11["state"] == "hard_to_borrow"
    assert r12["entry_level"] == "squeeze_candidate"  # entry fell...
    assert r12["state"] == "hard_to_borrow"          # ...but label holds


def test_deescalation_steps_one_level_per_hold():
    """Fixture bars 13-15: HTB holds through 2 qualifying bars, steps down
    exactly one level (to squeeze_candidate, not elevated) on the 3rd."""
    evs = tape()
    cfg = Config()
    assert primary_indicator(evs[:13], cfg)["state"] == "hard_to_borrow"
    assert primary_indicator(evs[:14], cfg)["state"] == "hard_to_borrow"
    r15 = primary_indicator(evs[:15], cfg)
    assert r15["state"] == "squeeze_candidate"


def test_hold_counter_resets_on_nonqualifying_bar():
    """Two qualifying bars then a bar inside the exit band => no step-down."""
    cfg = Config()
    specs = [
        (0.16, 0.98, 22e6),   # HTB (fee)
        (0.12, 0.94, 17e6),   # below HTB exit -> hold 1
        (0.11, 0.93, 16e6),   # below HTB exit -> hold 2
        (0.14, 0.96, 19e6),   # inside exit band -> counter resets
        (0.12, 0.94, 17e6),   # below exit -> hold 1 again, not 3
    ]
    rows = synth_tape(specs)
    states = [primary_indicator(rows[:i + 1], cfg)["state"] for i in range(5)]
    assert states[0] == "hard_to_borrow"
    assert states[3] == "hard_to_borrow"
    assert states[4] == "hard_to_borrow", states  # must NOT have stepped down


def test_boundary_strict_greater_than():
    """Thresholds are strict >: sitting exactly on all three SC-entry values
    must NOT escalate (fixture bar 16 pins this too)."""
    cfg = Config()
    rows = synth_tape([(0.10, 0.90, 12e6)] * 3)  # fee=0.10, util=0.90, DTC=6.0
    r = primary_indicator(rows, cfg)
    assert r["entry_level"] == "elevated", r
    assert r["state"] == "elevated", r


def test_escalation_is_immediate():
    """A single bar breaching HTB entry escalates at once (no hold on entry)."""
    cfg = Config()
    rows = synth_tape([(0.08, 0.80, 8e6)] * 3 + [(0.16, 0.98, 22e6)])
    r = primary_indicator(rows, cfg)
    assert r["state"] == "hard_to_borrow", r


def test_corporate_action_freezes_label():
    """Split event: labels freeze at the pre-event level, DEGRADED, for 5 bars."""
    cfg = Config()
    rows = synth_tape([(0.16, 0.98, 22e6)] * 3)
    rows.append(dict(bar=4, event_ts=rows[-1]["event_ts"] + DAY * NS,
                     asof_ts=rows[-1]["event_ts"] + DAY * NS + 3600 * NS,
                     fee_ann=0.16, util=0.98, si=44e6, adv=4e6,  # 2:1 split
                     corp_action="SPLIT:2:1"))
    r = primary_indicator(rows, cfg)
    assert r["module_state"] == "DEGRADED", r
    assert r["reason"] == "corporate_action_freeze", r
    assert r["state"] == "hard_to_borrow", r  # frozen, not recomputed


def test_gap_masks_and_degrades():
    """A missing trading day (2-day gap) => DEGRADED 'gap_masked', no
    interpolation across the gap."""
    evs = tape()
    cfg = Config()
    gapped = evs[:5] + evs[6:]  # drop bar 6 -> 2-day gap
    r = primary_indicator(gapped, cfg)
    assert r["module_state"] == "DEGRADED", r
    assert r["reason"] == "gap_masked", r


def test_halt_freezes_unknown():
    evs = tape()
    cfg = Config()
    halted = [dict(r) for r in evs]
    halted[-1] = dict(halted[-1], mkt_state="HALTED")
    r = primary_indicator(halted, cfg)
    assert r["module_state"] == "UNKNOWN", r


def test_cost_interface_hard_to_borrow_veto():
    base = {"spread_bps": 5.0, "fees_bps": 0.5, "borrow_bps": 1.0, "impact_bps": 3.0}
    adj = cost_adjustment("hard_to_borrow", "OK", 0.12, base)
    assert adj["trade_ok"] is False
    assert adj["reason"] == "hard_to_borrow"
    assert abs(adj["borrow_carry_bps_day"] - 0.12 / 360 * 10000) < 1e-9


def test_cost_interface_squeeze_candidate_scales():
    base = {"spread_bps": 5.0, "fees_bps": 0.5, "borrow_bps": 1.0, "impact_bps": 3.0}
    adj = cost_adjustment("squeeze_candidate", "OK", 0.12, base)
    assert adj["trade_ok"] is True
    assert adj["size_mult"] == 0.5
    assert adj["spread_bps"] == 7.5  # 1.5x squeeze widening [example]
    assert abs(adj["borrow_carry_bps_day"] - 0.12 / 360 * 10000) < 1e-9


def test_cost_interface_unknown_is_restrictive():
    base = {"spread_bps": 5.0, "fees_bps": 0.5, "borrow_bps": 1.0, "impact_bps": 3.0}
    adj = cost_adjustment("normal", "UNKNOWN", 0.02, base)
    assert adj["trade_ok"] is False
    adj2 = cost_adjustment("elevated", "DEGRADED", 0.06, base)
    assert adj2["trade_ok"] is True and adj2["size_mult"] == 0.5


def test_config_defaults_within_ranges():
    """No magic numbers: every default sits inside its declared range and
    every exit threshold sits strictly below its entry threshold."""
    cfg = Config()
    for i in range(3):
        assert cfg.fee_entry[i] - cfg.exit_dfee < cfg.fee_entry[i]
        assert cfg.util_entry[i] - cfg.exit_dutil < cfg.util_entry[i]
        assert cfg.dtc_entry[i] - cfg.exit_ddtc[i] < cfg.dtc_entry[i]
    assert list(cfg.fee_entry) == sorted(cfg.fee_entry)
    assert list(cfg.util_entry) == sorted(cfg.util_entry)
    assert list(cfg.dtc_entry) == sorted(cfg.dtc_entry)
    assert cfg.hold_bars >= 2 and cfg.warmup_bars >= 3
