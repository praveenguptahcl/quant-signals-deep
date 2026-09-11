"""Acceptance tests for R008 - Range compression / expansion (squeeze) regime.

Module version 1.1.0. Reference implementation of the chapter's normative
detection algorithm (see R008.md section R2): Bollinger Bandwidth percentile
with hysteresis entry/exit bands, a Keltner/ATR-bandwidth Verifier
(dual-estimator agreement, F3), calendar-gap and corporate-action guards,
and F1/F2/F4/F5 fail-safes.

Fixture: modules/fixtures/R008_tape.csv (130 synthetic daily bars, seed 9008
[example]) with phases normal(1-80) -> compression(81-100) -> breakout(101-116)
-> decay(117-130); expected labels in modules/fixtures/R008_expected.csv.

Run: python3 -m pytest modules/tests/test_R008.py -q   (from repo root)
"""
import csv
import math
import random
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R008_tape.csv"
EXPECTED = FIX / "R008_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['squeeze', 'normal', 'expansion', 'undefined', 'warming',
                'missing', 'invalid', 'corp_action', 'out_of_bounds']
ESTIMATOR_VERSION = "1.1.0"

# US market holidays intersecting the fixture window [example] (NYSE 2025).
US_HOLIDAYS_2025 = frozenset({
    "2025-06-19",  # Juneteenth
    "2025-07-04",  # Independence Day
    "2025-09-01",  # Labor Day
    "2025-11-27",  # Thanksgiving
})


def is_trading_day(d: dt.date) -> bool:
    """Weekday and not a listed exchange holiday [example]."""
    return d.weekday() < 5 and d.isoformat() not in US_HOLIDAYS_2025


def expected_trading_days(d0: dt.date, d1: dt.date):
    day = d0
    out = []
    while day <= d1:
        if is_trading_day(day):
            out.append(day)
        day += dt.timedelta(days=1)
    return out


# ============================ config ============================
@dataclass
class Config:
    bb_n: int = 20                    # [default]
    bb_k: float = 2.0                 # [default]
    kc_n: int = 20                    # [default]
    kc_m: float = 1.5                 # [documented] Carter TTM-Squeeze convention
    pct_window: int = 252             # [default]
    pct_min_history: int = 60         # [default]
    squeeze_entry: float = 10.0       # [example] percentile, strict <
    squeeze_exit: float = 20.0        # [example] percentile, exit when >
    expansion_entry: float = 90.0     # [example] percentile, strict >
    expansion_exit: float = 80.0      # [example] percentile, exit when <
    min_compression_bars: int = 6     # [example]
    max_single_bar_logret: float = 0.693  # [example] ln(2)
    f2_bw_max: float = 5.0            # [example]
    max_stale_mult: int = 3           # [default] x cadence


# ============================ statistics ============================
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


def _pct_rank(x, hist):
    """Mid-rank percentile of x against prior values, in [0,1] [default]."""
    h = [v for v in hist if math.isfinite(v)]
    if not h:
        return float("nan")
    return (sum(1 for v in h if v < x) + 0.5 * sum(1 for v in h if v == x)) / len(h)


# ============================ bandwidth series ============================
def _bb_bw_series(cs, n, k):
    """Bollinger Bandwidth per bar; NaN where the window is incomplete."""
    out = [float("nan")] * len(cs)
    for i in range(n - 1, len(cs)):
        w = cs[i - n + 1:i + 1]
        mu = _mean(w)
        sd = _stdev(w, ddof=1)
        out[i] = (2.0 * k * sd) / mu if mu > 0 and math.isfinite(sd) else float("nan")
    return out


def _true_range(rows, i):
    """Wilder's true range when h/l present [documented]; close-to-close
    fallback on a closes-only feed [example]."""
    r, p = rows[i], rows[i - 1]
    c_prev = p["c"]
    if "h" in r and "l" in r and r["h"] is not None and r["l"] is not None:
        return max(r["h"] - r["l"], abs(r["h"] - c_prev), abs(r["l"] - c_prev))
    return abs(r["c"] - c_prev)


def _keltner_bw_series(rows, n, m):
    """ATR-bandwidth per bar: (2*m*ATR)/EMA [default EMA seeding]."""
    cs = [r["c"] for r in rows]
    out = [float("nan")] * len(rows)
    if len(rows) < n + 1:
        return out
    ema = _mean(cs[:n])  # SMA seed [default]
    alpha = 2.0 / (n + 1)
    trs = [abs(cs[i] - cs[i - 1]) for i in range(1, n)]
    atr = _mean(trs) if trs else float("nan")
    for i in range(n, len(rows)):
        tr = _true_range(rows, i)
        atr = (atr * (n - 1) + tr) / n  # Wilder's smoothing [documented]
        ema = alpha * cs[i] + (1.0 - alpha) * ema
        out[i] = (2.0 * m * atr) / ema if ema > 0 and math.isfinite(atr) else float("nan")
    return out


# ============================ hysteresis FSM ============================
def _hysteresis_states(pcts, ages_out, cfg):
    """Causal squeeze/expansion state machine with hysteresis bands.

    Entry uses strict inequality (boundary stays out); exit only when the
    percentile crosses the far side of the band. Undefined percentiles
    (warm-up) hold 'undefined' and never advance compression age.
    """
    states = []
    state = "normal"
    age = 0
    for p in pcts:
        if not math.isfinite(p):
            states.append("undefined")
            ages_out.append(age)
            continue
        age = age + 1 if p < cfg.squeeze_entry / 100.0 else 0
        if state == "squeeze":
            state = "squeeze" if p <= cfg.squeeze_exit / 100.0 else "normal"
        elif state == "expansion":
            state = "expansion" if p >= cfg.expansion_exit / 100.0 else "normal"
        else:
            if age >= cfg.min_compression_bars and p < cfg.squeeze_entry / 100.0:
                state = "squeeze"
            elif p > cfg.expansion_entry / 100.0:
                state = "expansion"
            else:
                state = "normal"
        states.append(state)
        ages_out.append(age)
    return states


def _label_series(bw, cfg):
    """Percentile + FSM for one bandwidth series. Returns (pcts, ages, states)."""
    pcts, ages = [], []
    valid = [v for v in bw if math.isfinite(v)]
    seen = 0
    for v in bw:
        if not math.isfinite(v):
            pcts.append(float("nan"))
            continue
        hist = valid[max(0, seen - cfg.pct_window):seen]
        pcts.append(_pct_rank(v, hist) if len(hist) >= cfg.pct_min_history else float("nan"))
        seen += 1
    states = _hysteresis_states(pcts, ages, cfg)
    return pcts, ages, states


# ============================ reference detect ============================
@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str
    value: float
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


def _within_f2_bounds(v, cfg):
    """F2 predicate: the emitted bandwidth must lie in [0, f2_bw_max] [example]."""
    return math.isfinite(v) and 0.0 <= v <= cfg.f2_bw_max


def _validate(rows):
    """F1 + calendar + corporate-action guards. Returns an error tag or None."""
    if not rows:
        return "missing"
    for r in rows:
        c, ts = r.get("c"), r.get("event_ts")
        if not (isinstance(c, (int, float)) and math.isfinite(c) and c > 0):
            return "invalid"
        if not (isinstance(ts, int) and ts > 0):
            return "invalid"
    dates = [dt.datetime.fromtimestamp(r["event_ts"] / NS, tz=dt.timezone.utc).date()
             for r in rows]
    for d in dates:  # feed must contain trading days only
        if not is_trading_day(d):
            return "invalid"
    missing = [d.isoformat() for d in expected_trading_days(dates[0], dates[-1])
               if d not in set(dates)]
    if missing:
        return "missing"  # a trading-day bar is absent: never interpolate [F1]
    return None


def _run_series(rows, cfg):
    """Causal per-bar computation. Returns a list of per-bar result dicts."""
    rows = list(rows)
    err = _validate(rows)
    n = len(rows)
    out = []
    if err:
        for r in rows:
            out.append({"value": float("nan"), "pct": float("nan"), "age": 0,
                        "state": err, "module_state": "UNKNOWN",
                        "computed_at": r.get("event_ts", 0) if isinstance(r.get("event_ts"), int) else 0,
                        "vintage": "synthetic"})
        return out
    cs = [r["c"] for r in rows]
    # corporate-action guard: single-bar jump beyond ln(2) [example]
    corp_hit = [False] * n
    for i in range(1, n):
        if abs(math.log(cs[i] / cs[i - 1])) > cfg.max_single_bar_logret:
            corp_hit[i] = True
    bb = _bb_bw_series(cs, cfg.bb_n, cfg.bb_k)
    kb = _keltner_bw_series(rows, cfg.kc_n, cfg.kc_m)
    bb_pcts, bb_ages, bb_states = _label_series(bb, cfg)
    kb_pcts, kb_ages, kb_states = _label_series(kb, cfg)
    for i in range(n):
        ts = rows[i]["event_ts"]
        if corp_hit[i]:
            out.append({"value": float("nan"), "pct": float("nan"), "age": 0,
                        "state": "corp_action", "module_state": "UNKNOWN",
                        "computed_at": ts, "vintage": "synthetic"})
            continue
        v = bb[i]
        p, age, st = bb_pcts[i], bb_ages[i], bb_states[i]
        # Warm-up: a bar is labeled only when BOTH estimators have enough
        # history (aligned readiness); until then labels are withheld [F1].
        if st == "undefined" or kb_states[i] == "undefined":
            out.append({"value": float("nan"), "pct": float("nan"), "age": age,
                        "state": "warming", "module_state": "DEGRADED",
                        "computed_at": ts, "vintage": "synthetic"})
            continue
        # F2: mathematical bounds on the emitted value
        if not _within_f2_bounds(v, cfg):
            out.append({"value": v, "pct": p, "age": age,
                        "state": "out_of_bounds", "module_state": "UNKNOWN",
                        "computed_at": ts, "vintage": "synthetic"})
            continue
        # F3: dual-estimator agreement on the state label
        if kb_states[i] != st:
            out.append({"value": v, "pct": p, "age": age,
                        "state": st, "module_state": "UNKNOWN",
                        "computed_at": ts, "vintage": "synthetic"})
            continue
        out.append({"value": v, "pct": p, "age": age,
                    "state": st, "module_state": "OK",
                    "computed_at": ts, "vintage": "synthetic"})
    return out


def primary_indicator(rows, cfg):
    """Result for the newest bar of the given (causal) prefix."""
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "pct": float("nan"), "age": 0,
                "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "vintage": "synthetic"}
    return _run_series(rows, cfg)[-1]


def second_estimator(rows, cfg):
    """Verifier (Keltner/ATR bandwidth) result for the newest bar."""
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing",
                "computed_at": 0}
    cs = [r["c"] for r in rows]
    kb = _keltner_bw_series(rows, cfg.kc_n, cfg.kc_m)
    pcts, ages, states = _label_series(kb, cfg)
    st = states[-1]
    return {"value": kb[-1],
            "state": "warming" if st == "undefined" else st,
            "computed_at": rows[-1]["event_ts"]}


def detect(rows, cfg, now_ns=None, select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState — reference implementation
    with F1-F5 fail-safes wired in (Appendix f v1.0.0)."""
    rows = list(rows)
    r = primary_indicator(rows, cfg)
    if r["module_state"] != "OK":
        return RegimeState("R008", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F4: staleness timeout — 3x cadence [default]
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > cfg.max_stale_mult * CADENCE_S * NS:
        return RegimeState("R008", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R008", r["state"], r["value"], ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


def _f2_poison_tape(n_flat=100):
    """Flat line then one 100x spike on trading days [example].

    The spike trips both the corporate-action guard (F1, |ln| = 4.6 > 0.693)
    and the F2 bounds predicate; the integration test pins the restrictive
    UNKNOWN outcome, while test_F2_bounds_predicate pins the predicate itself.
    """
    dates = []
    day = dt.date(2025, 6, 2)
    while len(dates) < n_flat + 1:
        if is_trading_day(day):
            dates.append(day)
        day += dt.timedelta(days=1)
    rows = _rows_from_dates(dates[:-1], [100.0] * n_flat)
    d = dates[-1]
    ts = int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * NS)
    rows.append({"bar": n_flat + 1, "event_ts": ts, "asof_ts": ts + 3600 * NS,
                 "c": 10000.0})
    return rows


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


def _rows_from_dates(dates, closes):
    rows = []
    for i, (d, c) in enumerate(zip(dates, closes)):
        ts = int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * NS)
        rows.append({"bar": i + 1, "event_ts": ts, "asof_ts": ts + 3600 * NS, "c": c})
    return rows


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = Config()
    assert len(evs) == len(exp) == 130
    for i in range(len(evs)):
        r = primary_indicator(evs[: i + 1], cfg)
        want = exp[i + 1]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(r["value"]), i
        else:
            assert abs(r["value"] - wv) < TOL, i
        wp = float(want["exp_pct"])
        if math.isnan(wp):
            assert math.isnan(r["pct"]), i
        else:
            assert abs(r["pct"] - wp) < TOL, i
        assert r["age"] == int(want["exp_age"]), i
        assert r["state"] == want["exp_state"], i
        assert r["computed_at"] == int(want["exp_computed_at"]), i
        assert r["module_state"] == want["exp_module_state"], i


def test_fixture_pins_regime_transitions():
    """The tape must traverse normal -> squeeze -> expansion -> normal, with
    the squeeze confirmed only after min_compression_bars sub-threshold bars,
    and F3 disagreement pinned (UNKNOWN) at the regime transitions."""
    evs = tape()
    cfg = Config()
    series = _run_series(evs, cfg)
    states = [s["state"] for s in series]
    assert "squeeze" in states and "expansion" in states
    first_sq = states.index("squeeze")
    first_ex = states.index("expansion")
    assert first_sq < first_ex, "squeeze must precede expansion on this tape"
    # confirmation gate: no squeeze before 6 consecutive sub-10% bars
    pre = series[first_sq]
    assert pre["age"] >= cfg.min_compression_bars
    assert pre["pct"] < cfg.squeeze_entry / 100.0
    # hysteresis exit side: the squeeze is exited only when the percentile
    # crosses the FAR side of the band (bar 101: pct 0.38 > exit 0.20)
    exit_bar = next(i for i in range(first_sq, len(series))
                    if series[i]["state"] == "normal")
    assert series[exit_bar]["pct"] > cfg.squeeze_exit / 100.0
    assert series[exit_bar - 1]["state"] == "squeeze"
    # expansion is exited only below its exit band (holds at pct 0.81 >= 0.80)
    last_ex = max(i for i, s in enumerate(series) if s["state"] == "expansion"
                  and s["module_state"] == "OK")
    assert series[last_ex]["pct"] >= cfg.expansion_exit / 100.0
    first_norm_after = next(i for i in range(last_ex, len(series))
                            if series[i]["state"] == "normal")
    assert series[first_norm_after]["pct"] < cfg.expansion_exit / 100.0
    # the tape ends back in a clean normal regime
    assert series[-1]["state"] == "normal"
    assert series[-1]["module_state"] == "OK"


def test_F3_fires_only_at_transitions():
    """On the clean tape, dual-estimator disagreement (F3 -> UNKNOWN) may only
    occur adjacent to a regime-state change — never mid-regime."""
    evs = tape()
    cfg = Config()
    series = _run_series(evs, cfg)
    unks = [i for i, s in enumerate(series)
            if s["module_state"] == "UNKNOWN"
            and s["state"] in ("squeeze", "normal", "expansion")]
    assert 1 <= len(unks) <= 25, f"F3 fired {len(unks)}x; expected a handful at transitions"
    changed = {i for i in range(1, len(series))
               if series[i]["state"] != series[i - 1]["state"]}
    for i in unks:
        near = [c for c in changed if abs(i - c) <= 3]
        assert near, f"F3 UNKNOWN at bar {i + 1} far from any transition"


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R008"
    assert rsv.state in STATE_LABELS
    assert math.isfinite(rsv.value) and 0.0 <= rsv.value <= 5.0
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["event_ts"]
    assert rsv.module_state == "OK"


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. Assert label_ts == indicator_ts and earliest trade > label."""
    evs = tape()
    cfg = Config()
    for i in range(len(evs) - 1):
        label = detect(evs[: i + 1], cfg)
        indicator_ts = evs[i]["event_ts"]          # newest data used
        assert label.computed_at == indicator_ts, i
        earliest_trade_ts = evs[i + 1]["event_ts"]
        assert earliest_trade_ts > label.computed_at, f"lookahead at bar {i}"
    # appending a future breakout bar must not move the label stamped at t
    label_t = detect(evs[:-1], cfg)
    assert label_t.computed_at == evs[-2]["event_ts"]


def test_hysteresis_entry_boundary():
    """pct == entry threshold (exactly 10%) must NOT enter the squeeze."""
    cfg = Config()
    ages = []
    states = _hysteresis_states([0.099] * 5 + [0.10] * 6, ages, cfg)
    assert all(s == "normal" for s in states), states
    ages = []
    states = _hysteresis_states([0.099] * 6, ages, cfg)
    assert states[-1] == "squeeze", states


def test_hysteresis_exit_boundary():
    """Squeeze survives pct == exit (20%); exits only when pct > exit."""
    cfg = Config()
    ages = []
    seq = [0.05] * 6 + [0.20] * 4          # confirm, then sit on the boundary
    states = _hysteresis_states(seq, ages, cfg)
    assert all(s == "squeeze" for s in states[5:]), states
    ages = []
    states = _hysteresis_states(seq + [0.200001], ages, cfg)
    assert states[-1] == "normal", states


def test_hysteresis_expansion_bands():
    cfg = Config()
    ages = []
    states = _hysteresis_states([0.90] * 3, ages, cfg)     # boundary: no entry
    assert all(s == "normal" for s in states), states
    ages = []
    states = _hysteresis_states([0.900001], ages, cfg)     # just over: entry
    assert states[-1] == "expansion", states
    ages = []
    states = _hysteresis_states([0.95, 0.80, 0.80], ages, cfg)  # boundary: hold
    assert states == ["expansion", "expansion", "expansion"], states
    ages = []
    states = _hysteresis_states([0.95, 0.799999], ages, cfg)     # below: exit
    assert states[-1] == "normal", states


def test_compression_age_resets_on_breach():
    """5 sub-threshold bars + 1 breach -> age resets, no squeeze."""
    cfg = Config()
    ages = []
    states = _hysteresis_states([0.05] * 5 + [0.15] + [0.05] * 5, ages, cfg)
    assert all(s == "normal" for s in states), states
    assert ages[5] == 0 and ages[-1] == 5, ages


def test_F1_missing_input_unknown():
    assert detect([], Config()).module_state == "UNKNOWN"
    bad = [dict(event_ts=1, asof_ts=2)]  # missing indicator fields
    assert detect(bad, Config()).module_state == "UNKNOWN"


def test_F1_missing_trading_day_bar_unknown():
    """Dropping one Wednesday bar -> calendar check fires UNKNOWN (no interpolation)."""
    evs = tape()
    # find a Wednesday strictly inside the tape (not first/last)
    idx = next(i for i, r in enumerate(evs[1:-1], 1)
               if dt.datetime.fromtimestamp(r["event_ts"] / NS,
                                            tz=dt.timezone.utc).weekday() == 2)
    gapped = evs[:idx] + evs[idx + 1:]
    rsv = detect(gapped, Config())
    assert rsv.module_state == "UNKNOWN", "missing trading-day bar must yield UNKNOWN"
    assert rsv.state == "missing"


def test_F1_weekend_gap_allowed():
    """The tape's own Fri->Mon gaps must not trip the calendar check."""
    evs = tape()
    cfg = Config()
    series = _run_series(evs, cfg)
    assert not any(s["state"] == "missing" for s in series)


def test_F1_corporate_action_guard_unknown():
    """A >2x single-bar jump (unadjusted split signature) -> UNKNOWN."""
    dates = expected_trading_days(dt.date(2025, 6, 2), dt.date(2025, 10, 10))
    closes = [100.0 + 0.05 * i for i in range(len(dates))]
    closes[-1] = closes[-2] * 2.5  # 2.5x jump: |ln| = 0.916 > 0.693 [example]
    rows = _rows_from_dates(dates, closes)
    rsv = detect(rows, Config())
    assert rsv.module_state == "UNKNOWN"
    assert rsv.state == "corp_action"


def test_F2_bounds_predicate():
    """F2 predicate pinned directly: [0, f2_bw_max] inclusive, NaN rejected."""
    cfg = Config()
    assert _within_f2_bounds(0.0, cfg)
    assert _within_f2_bounds(cfg.f2_bw_max, cfg)
    assert _within_f2_bounds(0.023, cfg)
    assert not _within_f2_bounds(cfg.f2_bw_max + 1e-9, cfg)
    assert not _within_f2_bounds(-1e-12, cfg)
    assert not _within_f2_bounds(float("nan"), cfg)
    assert not _within_f2_bounds(float("inf"), cfg)


def test_F2_bounds_violation_unknown():
    rows = _f2_poison_tape()
    rsv = detect(rows, Config())
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"
    assert rsv.state in ("out_of_bounds", "corp_action")


def test_F3_dual_estimator_disagreement_unknown():
    """F3 pinned on the fixture itself: at bar 102 the Sentinel (BB) reads
    expansion while the Verifier (Keltner) still reads normal -> the module
    must emit UNKNOWN rather than pick a side. The prefix ending one bar
    earlier is clean OK."""
    evs = tape()
    cfg = Config()
    r = primary_indicator(evs[:102], cfg)
    assert r["state"] == "expansion", r
    assert r["module_state"] == "UNKNOWN", r
    assert detect(evs[:102], cfg).module_state == "UNKNOWN"
    assert primary_indicator(evs[:101], cfg)["module_state"] == "OK"


def test_F4_staleness_unknown():
    evs = tape()
    stale_now = evs[-1]["event_ts"] + 10 * CADENCE_S * NS  # >> 3x cadence [default]
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
    """Sentinel vs Verifier agree on every OK-labeled bar of the fixture;
    the only labeled UNKNOWNs are F3 transition disagreements (pinned by
    test_F3_fires_only_at_transitions)."""
    evs = tape()
    cfg = Config()
    series = _run_series(evs, cfg)
    labeled = [s for s in series if s["module_state"] == "OK"]
    assert len(labeled) >= 30, "fixture must label a material stretch"
    for s in series:
        if s["module_state"] == "UNKNOWN":
            assert s["state"] in ("squeeze", "normal", "expansion"), s
    assert detect(evs, cfg).module_state == "OK"


def test_warmup_is_degraded_not_fake_labels():
    """Before pct_min_history bandwidths exist, labels are withheld (DEGRADED)."""
    evs = tape()[:50]
    rsv = detect(evs, Config())
    assert rsv.module_state == "DEGRADED"
    assert rsv.state == "warming"
