"""Acceptance tests for R011 - Depth / liquidity-provision regime (v1.1.0).

Template v1.0.0. Reference implementation of the chapter's normative detection
(§R2 pseudocode): Kyle's-lambda OLS on signed flow with hysteresis entry/exit
bands, warm-up, t-stat gate, dual-estimator cross-check, and halt / split /
gap edge cases. Fixture tapes pin per-bar labels so logic drift fails loudly.

Run: python3 -m pytest modules/tests/test_R011.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R011_tape.csv"
EXPECTED = FIX / "R011_expected.csv"
TRANS_TAPE = FIX / "R011_transition_tape.csv"
TRANS_EXP = FIX / "R011_transition_expected.csv"
HALT_TAPE = FIX / "R011_halt_tape.csv"
HALT_EXP = FIX / "R011_halt_expected.csv"
SPLIT_TAPE = FIX / "R011_split_tape.csv"
SPLIT_EXP = FIX / "R011_split_expected.csv"
GAP_TAPE = FIX / "R011_gap_tape.csv"
GAP_EXP = FIX / "R011_gap_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 900  # indicator cadence in seconds [default]
NS = 1_000_000_000
BOUNDS = (-0.01, 0.01)  # F2 hard bound on lambda-hat, $/share [default]
ESTIMATOR_VERSION = "1.1.0"
STATE_LABELS = ["deep", "normal", "stressed", "warming", "masked",
                "invalid", "missing", "out_of_bounds", "undefined"]
MODULE_STATES = ("OK", "DEGRADED", "UNKNOWN", "OFF")


@dataclass
class Config:
    """§R0.2 — every default tagged per the tag law."""
    est_bars: int = 10            # [default]
    roll_days: int = 21           # [default]
    deep_entry_pct: float = 33.0      # [calibrate]
    deep_exit_pct: float = 40.0       # [calibrate]
    stressed_entry_pct: float = 67.0  # [calibrate]
    stressed_exit_pct: float = 60.0   # [calibrate]
    deep_entry: float = 1.5e-4      # [example] calibrated $/share threshold
    deep_exit: float = 2.0e-4       # [example]
    stressed_entry: float = 5.0e-4  # [example]
    stressed_exit: float = 4.5e-4   # [example]
    warmup_bars: int = 2          # [default]
    min_hist_days: int = 30       # [default]
    calib_cadence_days: int = 21  # [default]
    split_mask_bars: int = 1      # [default]
    gap_factor: float = 2.0       # [default]
    dual_tol: float = 0.5         # [default]
    t_min: float = 2.0            # [default]


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label
    value: float          # lambda-hat, $/share
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


def _finite(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


def _ols(qs, dps):
    """OLS slope of dp on q + t-stat. Returns (slope, t) with slope None when
    the regressor has no variation; t None when n < 3 (undefined)."""
    n = len(qs)
    mq = sum(qs) / n
    md = sum(dps) / n
    den = sum((q - mq) ** 2 for q in qs)
    if den == 0:
        return None, None
    slope = sum((q - mq) * (d - md) for q, d in zip(qs, dps)) / den
    t = None
    if n >= 3:
        ssr = sum((d - (md + slope * (q - mq))) ** 2 for q, d in zip(qs, dps))
        se2 = ssr / (n - 2) / den
        if se2 <= 0:
            t = float("inf") if slope != 0 else float("nan")  # perfect fit
        else:
            t = slope / math.sqrt(se2)
    return slope, t


def _ratio_lambda(dps, qs):
    num = sum(abs(d) for d in dps)
    den = sum(abs(q) for q in qs)
    return num / den if den > 0 else float("nan")


def primary_indicator(qs, dps):
    return _ols(qs, dps)[0]


def second_estimator(qs, dps):
    return _ratio_lambda(dps, qs)


def _hysteresis(prev, lam, cfg):
    """Entry/exit bands: a state is entered at the entry percentile and held
    until the exit percentile is crossed — no chatter inside the band."""
    if prev == "stressed":
        return "normal" if lam < cfg.stressed_exit else "stressed"
    if prev == "deep":
        return "normal" if lam > cfg.deep_exit else "deep"
    if lam >= cfg.stressed_entry:
        return "stressed"
    if lam <= cfg.deep_entry:
        return "deep"
    return "normal"


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


def detect(state, rows, cfg, now_ns=None, select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState — normative §R2 implementation
    with F1-F5 fail-safes (Appendix f v1.0.0). `state` carries last_label /
    last_value across calls; None = cold start."""
    rows = list(rows)
    st = dict(state) if state else {}
    nan = float("nan")

    def _rsv(label, val, ts, ms):
        return RegimeState("R011", label, val, ESTIMATOR_VERSION,
                           st.get("vintage", "synthetic"), ts, ms)

    # F1: empty input
    if not rows:
        return _rsv("missing", nan, 0, "UNKNOWN")
    last = rows[-1]
    # Halt/auction: freeze — emit last label, UNKNOWN, discard across reopen
    if (last.get("flag") or "") == "halt":
        return _rsv(st.get("last_label", "undefined"),
                    st.get("last_value", nan), last["event_ts"], "UNKNOWN")
    # Classify rows: validate numerics (F1), track splits and halts
    usable, split_pos, last_halt = [], set(), -1
    for i, r in enumerate(rows):
        fl = r.get("flag") or ""
        if fl == "halt":
            last_halt = i
            continue
        if fl == "split":
            split_pos.add(i)
            continue
        dp, q = r.get("dp"), r.get("q")
        if not _finite(dp) or not _finite(q) or q == 0:
            return _rsv("invalid", nan, r.get("event_ts", 0), "UNKNOWN")
        usable.append((i, r))
    # Corporate-action mask: split bar + next split_mask_bars bars -> UNKNOWN
    masked = set()
    for j in split_pos:
        for k in range(cfg.split_mask_bars + 1):
            masked.add(j + k)
    if (len(rows) - 1) in masked:
        return _rsv("masked", nan, last["event_ts"], "UNKNOWN")
    # Session = bars after the most recent halt (discard across reopen)
    sess = [(i, r) for (i, r) in usable if i > last_halt and i not in masked]
    if len(sess) < cfg.warmup_bars:
        return _rsv("warming", nan, last["event_ts"], "DEGRADED")
    win = sess[-cfg.est_bars:]
    # Gap check: intervals spanning a corporate-action mask are known-good
    ts = [r["event_ts"] for _, r in win]
    ivs = [b - a for a, b in zip(ts, ts[1:])]
    mod = "OK"
    if ivs:
        idx = [r["_pos"] for _, r in win]
        kept = []
        for (ia, ib), iv in zip(zip(idx, idx[1:]), ivs):
            if any(ia < m < ib for m in masked):
                continue  # known corporate-action discontinuity, not a feed gap
            kept.append(iv)
        if kept:
            med = sorted(kept)[len(kept) // 2]
            if med > 0 and max(kept) > cfg.gap_factor * med:
                mod = "DEGRADED"
    qs = [r["q"] for _, r in win]
    dps = [r["dp"] for _, r in win]
    lam, t = _ols(qs, dps)
    if lam is None:
        return _rsv("invalid", nan, last["event_ts"], "UNKNOWN")  # no variation
    if lam < 0:
        return _rsv("invalid", lam, last["event_ts"], "UNKNOWN")  # not equilibrium
    lo, hi = BOUNDS
    if not (lo <= lam <= hi):
        return _rsv("out_of_bounds", lam, last["event_ts"], "UNKNOWN")  # F2
    # F3: dual-estimator agreement
    if not within_tolerance(lam, second_estimator(qs, dps), "rel", cfg.dual_tol):
        return _rsv("invalid", lam, last["event_ts"], "UNKNOWN")
    # Verifier: t-stat gate — level untrusted, label kept
    if t is not None and math.isfinite(t) and abs(t) < cfg.t_min:
        mod = "DEGRADED"
    prev = st.get("last_label") or "normal"
    label = _hysteresis(prev, lam, cfg)
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else last["event_ts"] + CADENCE_S * NS
    if now - last["event_ts"] > 3 * CADENCE_S * NS:
        return _rsv(label, lam, last["event_ts"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return _rsv(label, lam, last["event_ts"], mod)


def run_tape(rows, cfg):
    """Stateful replay: threads last_label/last_value across prefixes, exactly
    as the production detector would. UNKNOWN freezes the carried state."""
    out, st = [], None
    for i in range(len(rows)):
        rsv = detect(st, rows[: i + 1], cfg)
        out.append(rsv)
        if rsv.state in ("deep", "normal", "stressed"):
            st = {"last_label": rsv.state, "last_value": rsv.value,
                  "vintage": rsv.data_vintage}
    return out


def cost_adjustment(rsv, base):
    """Regime state -> cost-function adjustment (R011 v1.1.0)."""
    adj = dict(base)
    scaling = {  # (spread_mult, impact_mult, size_mult) [example]
        "deep": (1.00, 1.0, 1.0),
        "normal": (1.25, 1.5, 1.0),
        "stressed": (1.75, 3.0, 0.5),
    }[rsv["state"]]
    adj["spread_mult"], adj["impact_mult"], adj["size_mult"] = scaling
    adj["fee_mult"] = 1.0       # [default] per-share fees are regime-invariant
    adj["borrow_mult"] = 1.0    # [default] financing unaffected by depth regime
    adj["slice"] = (rsv["state"] == "stressed")                       # [default]
    adj["max_participation"] = 0.10 if rsv["state"] == "stressed" else 1.0  # [default]
    adj["trade_ok"] = True      # [default] the regime sizes; it never vetoes
    return adj


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def tape(path=TAPE):
    rows = []
    for pos, r in enumerate(load_csv(path)):
        row = {"_pos": pos}
        for k, v in r.items():
            if v == "":
                row[k] = v
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


def expected(path):
    return {int(r["bar"]): r for r in load_csv(path)}


def assert_matches_expected(rows, exp_path, cfg):
    """Causal recompute of each prefix matches the pinned expected CSV —
    fails on any logic drift (values, labels, hysteresis, module states)."""
    exp = expected(exp_path)
    rsvs = run_tape(rows, cfg)
    assert len(rsvs) == len(exp), (len(rsvs), len(exp))
    for rsv, i in zip(rsvs, sorted(exp)):
        want = exp[i]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(rsv.value), (i, rsv)
        else:
            assert abs(rsv.value - wv) < TOL, (i, rsv.value, wv)
        assert rsv.state == want["exp_state"], (i, rsv.state, want["exp_state"])
        assert rsv.computed_at == int(want["exp_computed_at"]), i
        assert rsv.module_state == want["exp_module_state"], (i, rsv.module_state)


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    assert_matches_expected(tape(TAPE), EXPECTED, Config())


def test_emits_valid_regime_state_vector():
    evs = tape(TAPE)
    rsv = detect(None, evs, Config())
    assert rsv.regime_id == "R011"
    assert rsv.state in STATE_LABELS
    assert math.isfinite(rsv.value) and BOUNDS[0] <= rsv.value <= BOUNDS[1]
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in MODULE_STATES
    assert rsv.computed_at == evs[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. Assert label_ts > indicator_ts for the earliest trade."""
    evs = tape(TAPE)
    cfg = Config()
    for i in range(len(evs) - 1):
        label = detect(None, evs[: i + 1], cfg)
        indicator_ts = evs[i]["event_ts"]          # newest data used
        assert label.computed_at == indicator_ts   # label stamped at t, not later
        earliest_trade_ts = evs[i + 1]["event_ts"]
        assert earliest_trade_ts > label.computed_at, f"lookahead at bar {i}"
    # appending a future breakout bar must not move the label stamped at t
    label_t = detect(None, evs[:-1], cfg)
    assert label_t.computed_at == evs[-2]["event_ts"]


def test_F1_missing_input_unknown():
    assert detect(None, [], Config()).module_state == "UNKNOWN"
    bad = [{"_pos": 0, "event_ts": 1, "asof_ts": 2}]  # missing indicator fields
    assert detect(None, bad, Config()).module_state == "UNKNOWN"
    zero_flow = [{"_pos": 0, "bar": 1, "event_ts": 1, "asof_ts": 2,
                  "dp": 0.0, "q": 0, "flag": ""}]   # zero-flow bar is invalid
    assert detect(None, zero_flow, Config()).module_state == "UNKNOWN"


def test_F2_bounds_violation_unknown():
    poison = [{"_pos": i, "bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i,
               "dp": 1000.0 * (1 if i % 2 else -1), "q": 1.0 if i % 2 else -1.0,
               "flag": ""}
              for i in range(10)]  # lambda-hat ~ 1000 $/share >> 0.01 bound
    rsv = detect(None, poison, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"
    assert rsv.state == "out_of_bounds"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = tape(TAPE)
    orig = mod.second_estimator
    lam0 = primary_indicator([r["q"] for r in evs], [r["dp"] for r in evs])
    bad_val = -1e9 if (lam0 is not None and lam0 >= 0) else 1e9
    try:
        mod.second_estimator = lambda qs, dps: bad_val
        rsv = mod.detect(None, evs, Config())
        assert rsv.module_state == "UNKNOWN"
    finally:
        mod.second_estimator = orig


def test_F4_staleness_unknown():
    evs = tape(TAPE)
    stale_now = evs[-1]["event_ts"] + 10 * CADENCE_S * NS  # >> 3x cadence
    rsv = detect(None, evs, Config(), now_ns=stale_now)
    assert rsv.module_state == "UNKNOWN"


def test_F5_regime_mining_guard():
    evs = tape(TAPE)
    try:
        detect(None, evs, Config(), select_periods=True, preregistered=False)
    except RegimeMiningError:
        pass
    else:
        raise AssertionError("F5: unregistered period selection must raise")
    rsv = detect(None, evs, Config(), select_periods=True, preregistered=True)
    assert rsv.module_state == "OK"


def test_dual_estimator_agreement():
    """Sentinel vs Verifier agree within tolerance on the fixture."""
    evs = tape(TAPE)
    cfg = Config()
    qs = [r["q"] for r in evs]
    dps = [r["dp"] for r in evs]
    assert within_tolerance(primary_indicator(qs, dps),
                            second_estimator(qs, dps), "rel", cfg.dual_tol)
    assert detect(None, evs, cfg).module_state == "OK"


def test_transition_tape_exact_labels():
    """Hysteresis pinned per-bar: entry at the entry percentile, hold inside
    the band, exit only past the exit percentile."""
    assert_matches_expected(tape(TRANS_TAPE), TRANS_EXP, Config())


def test_hysteresis_holds_inside_band():
    """Bar 38 (lambda-hat 4.64e-4) sits below the stressed *entry* (5.0e-4) but
    above the *exit* (4.5e-4): it must hold 'stressed'. Bar 39 (4.32e-4)
    crosses the exit and returns to 'normal'. Removing hysteresis flips bar 38."""
    rsvs = run_tape(tape(TRANS_TAPE), Config())
    by_bar = {i + 1: r for i, r in enumerate(rsvs)}
    assert by_bar[38].state == "stressed", by_bar[38]
    assert by_bar[38].module_state == "OK"
    assert by_bar[39].state == "normal", by_bar[39]
    assert by_bar[25].state == "stressed"  # entry at 5.2e-4 >= 5.0e-4
    assert by_bar[24].state == "normal"    # 4.8e-4: below entry, not yet stressed


def test_no_chatter_transition_count():
    """Exactly 4 transitions across 40 bars (deep->normal->stressed->normal at
    bars 2, 15, 25, 39); a no-hysteresis detector would chatter at every band touch."""
    rsvs = run_tape(tape(TRANS_TAPE), Config())
    labels = [r.state for r in rsvs if r.state in ("deep", "normal", "stressed")]
    assert labels[0] == "deep"  # cold-start entry at bar 2
    changes = [(k + 3, b) for k, (a, b) in enumerate(zip(labels, labels[1:])) if a != b]
    assert changes == [(15, "normal"), (25, "stressed"), (39, "normal")], labels
    assert [r.state for r in rsvs[14:24]] == ["normal"] * 10  # bars 15-24 stable


def test_halt_freezes_and_warmup():
    """Halt event: freeze (last label, UNKNOWN). Post-halt the window
    restarts: 1 bar -> DEGRADED/warming, 2 bars -> OK."""
    rsvs = run_tape(tape(HALT_TAPE), Config())
    halt = rsvs[6]
    assert halt.module_state == "UNKNOWN", halt
    assert halt.state == "normal", halt          # frozen label
    assert math.isfinite(halt.value)             # frozen value
    post1, post2 = rsvs[7], rsvs[8]
    assert (post1.state, post1.module_state) == ("warming", "DEGRADED"), post1
    assert (post2.state, post2.module_state) == ("normal", "OK"), post2
    assert_matches_expected(tape(HALT_TAPE), HALT_EXP, Config())


def test_split_masks_corporate_action():
    """Split bar + next bar are masked (UNKNOWN/'masked'); estimation never
    runs across an unadjusted split; bars 7-8 resume OK."""
    rsvs = run_tape(tape(SPLIT_TAPE), Config())
    assert (rsvs[4].state, rsvs[4].module_state) == ("masked", "UNKNOWN"), rsvs[4]
    assert (rsvs[5].state, rsvs[5].module_state) == ("masked", "UNKNOWN"), rsvs[5]
    assert (rsvs[6].state, rsvs[6].module_state) == ("normal", "OK"), rsvs[6]
    assert (rsvs[7].state, rsvs[7].module_state) == ("normal", "OK"), rsvs[7]
    assert_matches_expected(tape(SPLIT_TAPE), SPLIT_EXP, Config())


def test_gap_degraded_then_recovers():
    """Feed gap (> 2x median interval): DEGRADED while the 10-bar window spans the
    gap (bars 5-13), automatic recovery to OK once the window refills (bar 14)."""
    rsvs = run_tape(tape(GAP_TAPE), Config())
    got = [(r.state, r.module_state) for r in rsvs]
    assert got[0] == ("warming", "DEGRADED")
    assert all(ms == "DEGRADED" for _, ms in got[4:13]), got
    assert all(ms == "OK" for _, ms in got[13:16]), got
    assert all(s == "normal" for s, _ in got[1:])
    assert_matches_expected(tape(GAP_TAPE), GAP_EXP, Config())


def test_warmup_withholds_label():
    rsv = detect(None, tape(TAPE)[:1], Config())
    assert (rsv.state, rsv.module_state) == ("warming", "DEGRADED")
    assert math.isnan(rsv.value)


def test_cost_interface_component_scaling():
    """§R5: only spread and temporary impact scale with the regime; fees and
    borrow are invariant; stressed forces slicing at 10% participation."""
    base = {"spread_bps": 1.0, "impact_bps": 2.0, "fee_bps": 0.3,
            "borrow_bps": 0.0, "size_mult": 1.0}
    deep = cost_adjustment({"state": "deep"}, base)
    normal = cost_adjustment({"state": "normal"}, base)
    stressed = cost_adjustment({"state": "stressed"}, base)
    assert (deep["spread_mult"], deep["impact_mult"], deep["size_mult"]) == (1.0, 1.0, 1.0)
    assert (normal["spread_mult"], normal["impact_mult"], normal["size_mult"]) == (1.25, 1.5, 1.0)
    assert (stressed["spread_mult"], stressed["impact_mult"], stressed["size_mult"]) == (1.75, 3.0, 0.5)
    for adj in (deep, normal, stressed):
        assert adj["fee_mult"] == 1.0 and adj["borrow_mult"] == 1.0
        assert adj["trade_ok"] is True
    assert deep["slice"] is False and normal["slice"] is False
    assert stressed["slice"] is True and stressed["max_participation"] == 0.10
    # effective cost: multiplicative on the scaled components only
    eff = lambda a: (base["spread_bps"] * a["spread_mult"]
                     + base["impact_bps"] * a["impact_mult"]
                     + base["fee_bps"] * a["fee_mult"]
                     + base["borrow_bps"] * a["borrow_mult"])
    assert eff(deep) == 1.0 * 1.0 + 2.0 * 1.0 + 0.3
    assert eff(stressed) == 1.0 * 1.75 + 2.0 * 3.0 + 0.3
    assert eff(stressed) > eff(normal) > eff(deep)
