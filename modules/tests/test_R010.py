"""Acceptance tests for R010 - Spread regime.

Template v1.0.0. Reference implementation of the chapter's normative formula
(§R2): time-weighted quoted spread, dual-estimator agreement (F3), percentile
label with hysteresis entry/release bands, F1-F5 fail-safes, split-invariance
of the proportional spread, and the §R5 cost interface.

Run: python3 -m pytest modules/tests/test_R010.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R010_tape.csv"
EXPECTED = FIX / "R010_expected.csv"
HYST = FIX / "R010_hysteresis.csv"
HIST = FIX / "R010_history.csv"

TOL = 1e-9          # float tolerance [default]
CADENCE_S = 86400   # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['normal', 'wide', 'extreme', 'undefined', 'warming', 'missing',
                'invalid', 'insufficient', 'out_of_bounds']
BOUNDS = (0.0, 1000.0)   # mathematical bounds of the indicator value, bps (F2) [default]
DUAL_MODE = "rel"        # sentinel/verifier agreement mode [default]
DUAL_TOL = 0.25          # sentinel/verifier relative tolerance [default]
ESTIMATOR_VERSION = "1.1.0"
SEV = {'normal': 0, 'wide': 1, 'extreme': 2}  # label severity order [default]


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
    h = list(hist)
    if not h:
        return float("nan")
    return (sum(1 for v in h if v < x) + 0.5 * sum(1 for v in h if v == x)) / len(h)

def _ols_slope(xs, ys):
    xs, ys = list(xs), list(ys)
    mx, my = _mean(xs), _mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den

def _sign(x):
    return 1 if x > 0 else (-1 if x < 0 else 0)

# ============================ R010 ============================
R010_QUOTES = [
    (100.00, 100.03, 100.0), (100.02, 100.04, 300.0), (100.01, 100.03, 50.0),
    (100.00, 100.05, 200.0), (100.03, 100.06, 150.0), (100.02, 100.05, 400.0),
    (100.01, 100.04, 250.0), (100.04, 100.06, 100.0), (100.02, 100.05, 300.0),
    (100.03, 100.05, 200.0),
]
HIST_SPREAD_BPS = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 2.2, 3.3,
                   4.4, 5.5, 6.0, 2.8, 3.8, 4.8, 5.8, 6.8, 7.5, 8.0]  # [example] synthetic trailing history

def r010_tape():
    hdr = ["bar", "event_ts", "asof_ts", "bid", "ask", "life"]
    rows = []
    for i, (b, a, lf) in enumerate(R010_QUOTES, 1):
        ts = TS0 + (i - 1) * 60
        rows.append({"bar": i, "event_ts": ts, "asof_ts": ts + int(lf * NS),
                     "bid": b, "ask": a, "life": lf})
    return hdr, rows

def _tw_spread_bps(rows):
    tot_w, acc = 0.0, 0.0
    for r in rows:
        mid = (r["bid"] + r["ask"]) / 2
        if mid <= 0:
            return float("nan")
        acc += 20000 * (r["ask"] - r["bid"]) / (r["ask"] + r["bid"]) * r["life"]
        tot_w += r["life"]
    return acc / tot_w if tot_w > 0 else float("nan")

def _avg_spread_bps(rows):
    vals = []
    for r in rows:
        mid = (r["bid"] + r["ask"]) / 2
        if mid <= 0:
            return float("nan")
        vals.append(20000 * (r["ask"] - r["bid"]) / (r["ask"] + r["bid"]))
    return _mean(vals)

def _raw_label(pct, cfg):
    """Raw label from percentile entry bands (§R2.6). Boundaries inclusive."""
    if not math.isfinite(pct):
        return "undefined"
    if pct >= cfg.extreme_pct / 100.0:
        return "extreme"
    if pct >= cfg.wide_pct / 100.0:
        return "wide"
    return "normal"

def _release_band(label, cfg):
    """Percentile value below which a held label is released (§R2.6)."""
    return {'extreme': cfg.extreme_pct - cfg.hyst_band,
            'wide': cfg.wide_pct - cfg.hyst_band}.get(label, 0.0)

def label_state(tw_bps, history, prev_label, cfg):
    """Normative hysteresis state machine (§R2.6).

    Returns (pct, raw_label, label). Worsening adopts the raw label
    immediately; an improving raw label is adopted only once the percentile
    crosses the release band of the held label (no flip-flop).
    """
    hist = list(history) if history is not None else list(HIST_SPREAD_BPS)
    pct = _pct_rank(tw_bps, hist)
    raw = _raw_label(pct, cfg)
    if prev_label is None or prev_label not in SEV:
        return pct, raw, raw
    if SEV[raw] >= SEV[prev_label]:
        return pct, raw, raw
    if pct * 100.0 < _release_band(prev_label, cfg):
        return pct, raw, raw
    return pct, raw, prev_label

def primary_indicator_r010(rows, cfg):
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "vintage": "synthetic"}
    valid, rejected = [], 0
    for r in rows:
        # crossed/locked NBBO (ask <= bid) and non-positive prices/lifetimes
        # are rejected, never interpolated (F1, §R2.2)
        if not all(k in r for k in ("bid", "ask", "life")) \
                or not (r["ask"] > r["bid"] > 0) or not r["life"] > 0:
            rejected += 1
        else:
            valid.append(r)
    if not valid:
        return {"value": float("nan"), "state": "invalid", "module_state": "UNKNOWN",
                "computed_at": rows[-1].get("event_ts", 0), "vintage": "synthetic",
                "rejected": rejected}
    v = _tw_spread_bps(valid)
    if len(valid) < cfg.min_quotes_per_day:
        # thin session: value computed, label withheld (DEGRADED) (§R2.2)
        return {"value": v, "state": "insufficient", "module_state": "DEGRADED",
                "computed_at": valid[-1]["event_ts"], "vintage": "synthetic",
                "rejected": rejected}
    hist = cfg.trailing if cfg.trailing is not None else HIST_SPREAD_BPS
    pct, raw, label = label_state(v, hist, cfg.prev_label, cfg)
    return {"value": v, "state": label, "module_state": "OK",
            "computed_at": valid[-1]["event_ts"], "vintage": "synthetic",
            "pct": pct, "raw": raw, "rejected": rejected}

def second_estimator_r010(rows, cfg):
    rows = [r for r in rows if r.get("ask", 0) > r.get("bid", 0) > 0]
    return {"value": _avg_spread_bps(rows), "state": "n/a",
            "computed_at": rows[-1]["event_ts"] if rows else 0}


primary_indicator = primary_indicator_r010
second_estimator = second_estimator_r010


F2_POISON_TAPE = [
    {"bar": 1, "event_ts": 1000, "asof_ts": 1060, "bid": 1.0, "ask": 1000.0, "life": 60.0}
]  # absurd spread ~19960 bps -> out of bounds -> F2


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


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label, e.g. "wide"
    value: float          # indicator value (TW-QS, bps)
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


@dataclass
class Config:
    wide_pct: float = 50.0        # [default] entry band for 'wide'
    extreme_pct: float = 90.0     # [default] entry band for 'extreme'
    hyst_band: float = 5.0        # [default] release-band width (percentile points)
    dual_tol: float = 0.25        # [default] sentinel/verifier relative tolerance
    min_quotes_per_day: int = 50  # [default] below -> DEGRADED, label withheld
    hist_window: int = 252        # [default] trailing history length (days)
    trailing: list = None         # [example] override trailing history (default: synthetic)
    prev_label: str = None        # prior emitted label (None = first run)


# The 10-quote tape is an illustrative intraday snippet [example]; the normative
# floor is min_quotes_per_day=50 [default]. Tests of arithmetic use this
# explicit override; test_insufficient_quotes_degraded pins the default.
TAPE_CFG = Config(min_quotes_per_day=1)  # [example] illustrative override


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
        return RegimeState("R010", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    lo, hi = BOUNDS
    v = r["value"]
    if not (math.isfinite(v) and lo <= v <= hi):
        return RegimeState("R010", "out_of_bounds", v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F3: dual-estimator agreement (relative tolerance [default])
    s = second_estimator(rows, cfg)
    if DUAL_MODE == "state":
        agree = (r["state"] == s["state"]) or (
            DUAL_TOL is not None and math.isfinite(v) and math.isfinite(s["value"])
            and abs(v - s["value"]) <= DUAL_TOL)
    else:
        agree = within_tolerance(v, s["value"], DUAL_MODE, DUAL_TOL)
    if not agree:
        return RegimeState("R010", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R010", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R010", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


def cost_adjustment(rsv, base):
    """§R5 cost interface: regime state -> cost-function adjustment.

    Only the spread adder of the 4-component cost stack scales; fees, borrow,
    and impact are untouched by this regime. The measured TW-QS is passed
    through as the spread-cost basis (no invented level).
    """
    adj = dict(base)
    tw = rsv["value"]  # TW-QS in bps, measured this cadence
    if rsv["state"] == "extreme":
        adj["trade_ok"] = False    # [default] cost dominates edge
        adj["spread_mult"] = 4.0   # [default] forward conservatism
    elif rsv["state"] == "wide":
        adj["trade_ok"] = True
        adj["limit_only"] = True   # [default] no marketable flow
        adj["spread_mult"] = 2.0   # [default] forward conservatism
    else:
        adj["trade_ok"] = True
        adj["spread_mult"] = 1.0   # [default]
    adj["spread_bps_per_side"] = 0.5 * tw * adj["spread_mult"]
    adj["spread_bps_roundtrip"] = tw * adj["spread_mult"]
    adj["regime_tag"] = "R010:%s@%s" % (rsv["state"], rsv["data_vintage"])
    return adj


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = TAPE_CFG
    for i in range(len(evs)):
        r = primary_indicator(evs[: i + 1], cfg)
        want = exp[i + 1]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(r["value"]), i
        elif math.isinf(wv):
            assert math.isinf(r["value"]) and (r["value"] > 0) == (wv > 0), i
        else:
            assert abs(r["value"] - wv) < TOL, i
        assert r["state"] == want["exp_state"], i
        assert r["computed_at"] == int(want["exp_computed_at"]), i
        assert r["module_state"] == want["exp_module_state"], i


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, TAPE_CFG)
    assert rsv.regime_id == "R010"
    assert rsv.state in STATE_LABELS
    assert math.isfinite(rsv.value) and BOUNDS[0] <= rsv.value <= BOUNDS[1]
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. Assert label_ts > indicator_ts for the earliest trade."""
    evs = tape()
    cfg = TAPE_CFG
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
    # min_quotes_per_day=1 override so the poison tape reaches the F2 check
    rsv = detect(F2_POISON_TAPE, Config(min_quotes_per_day=1))
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"
    assert rsv.state == "out_of_bounds"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = tape()
    orig = mod.second_estimator
    p0 = primary_indicator(evs, TAPE_CFG)["value"]
    bad_val = -1e9 if (p0 >= 0) else 1e9  # opposite sign: disagrees in sign/rel/abs/state modes
    try:
        mod.second_estimator = lambda rows, cfg: {"value": bad_val, "state": "bogus",
                                                 "computed_at": evs[-1]["event_ts"]}
        rsv = mod.detect(evs, TAPE_CFG)
        assert rsv.module_state == "UNKNOWN"
    finally:
        mod.second_estimator = orig


def test_F4_staleness_unknown():
    evs = tape()
    stale_now = evs[-1]["event_ts"] + 10 * CADENCE_S * NS  # >> 3x cadence
    rsv = detect(evs, TAPE_CFG, now_ns=stale_now)
    assert rsv.module_state == "UNKNOWN"


def test_F5_regime_mining_guard():
    evs = tape()
    try:
        detect(evs, TAPE_CFG, select_periods=True, preregistered=False)
    except RegimeMiningError:
        pass
    else:
        raise AssertionError("F5: unregistered period selection must raise")
    rsv = detect(evs, TAPE_CFG, select_periods=True, preregistered=True)
    assert rsv.module_state == "OK"


def test_dual_estimator_agreement():
    """Sentinel vs Verifier agree within tolerance on the fixture."""
    evs = tape()
    cfg = TAPE_CFG
    r = primary_indicator(evs, cfg)
    s = second_estimator(evs, cfg)
    if DUAL_MODE == "state":
        ok = (r["state"] == s["state"]) or (
            DUAL_TOL is not None and abs(r["value"] - s["value"]) <= DUAL_TOL)
        assert ok, (r, s)
    else:
        assert within_tolerance(r["value"], s["value"], DUAL_MODE, DUAL_TOL), (r, s)
    assert detect(evs, cfg).module_state == "OK"


def test_insufficient_quotes_degraded():
    """A thin session (below the normative floor) withholds the label."""
    evs = tape()  # 10 quotes < min_quotes_per_day=50 [default]
    rsv = detect(evs, Config())
    assert rsv.module_state == "DEGRADED"
    assert rsv.state == "insufficient"
    assert math.isfinite(rsv.value)  # value still computed, label withheld


def test_crossed_nbbo_rejection_unknown():
    """Crossed/locked NBBO quotes are rejected; all rejected -> UNKNOWN (F1)."""
    crossed = [
        {"bar": 1, "event_ts": 1000, "asof_ts": 1060, "bid": 100.05, "ask": 100.03, "life": 60.0},
        {"bar": 2, "event_ts": 1060, "asof_ts": 1120, "bid": 100.04, "ask": 100.04, "life": 60.0},
    ]
    rsv = detect(crossed, Config(min_quotes_per_day=1))
    assert rsv.module_state == "UNKNOWN"
    assert rsv.state == "invalid"


def _hyst_rows():
    hist = [float(r["tw_qs_bps"]) for r in load_csv(HIST)]
    return hist, load_csv(HYST)


def test_hysteresis_boundary_values():
    """Entry bands are inclusive: pct == 50 -> wide, pct == 90 -> extreme."""
    hist, rows = _hyst_rows()
    cfg = Config()
    by_day = {int(r["day"]): r for r in rows}
    for day in (8, 9):
        r = by_day[day]
        pct, raw, label = label_state(float(r["tw_qs_bps"]), hist, r["prev_label"], cfg)
        assert abs(pct - float(r["exp_pct"])) < TOL, day
        assert raw == r["exp_label"], (day, raw)
        assert label == r["exp_label"], (day, label)


def test_hysteresis_holds_and_releases():
    """Fixture pins every row: holds inside the band, releases across it."""
    hist, rows = _hyst_rows()
    cfg = Config()
    for r in rows:
        pct, raw, label = label_state(float(r["tw_qs_bps"]), hist, r["prev_label"], cfg)
        assert abs(pct - float(r["exp_pct"])) < TOL, r
        assert label == r["exp_label"], (r, raw)


def test_hysteresis_chain():
    """Sequential prev-label application: no flip-flop across the band edge."""
    hist, rows = _hyst_rows()
    cfg = Config()
    prev = rows[0]["prev_label"]
    for r in rows:
        pct, raw, label = label_state(float(r["tw_qs_bps"]), hist, prev, cfg)
        assert label == r["exp_label"], (r, prev, raw)
        prev = label


def test_split_invariance():
    """Proportional QS is split-invariant (§R2.2): a 2:1 rescale of all
    prices leaves TW-QS unchanged."""
    evs = tape()
    doubled = [dict(r, bid=2 * r["bid"], ask=2 * r["ask"]) for r in evs]
    v0 = primary_indicator(evs, TAPE_CFG)["value"]
    v1 = primary_indicator(doubled, TAPE_CFG)["value"]
    assert abs(v0 - v1) < TOL, (v0, v1)


def test_cost_adjustment_mapping():
    """§R5: only the spread adder scales; extreme blocks flow."""
    base = {"spread_bps_per_side": 1.0, "fees_bps": 0.5, "borrow_bps": 0.0,
            "impact_bps": 0.3}
    tw = 6.0  # bps [example]

    def rsv(state):
        return {"state": state, "value": tw, "data_vintage": "2026-09-10"}

    n = cost_adjustment(rsv("normal"), base)
    assert n["trade_ok"] is True and n["spread_mult"] == 1.0
    assert n["spread_bps_per_side"] == 0.5 * tw * 1.0
    assert n["fees_bps"] == 0.5 and n["impact_bps"] == 0.3  # untouched

    w = cost_adjustment(rsv("wide"), base)
    assert w["trade_ok"] is True and w["limit_only"] is True
    assert w["spread_mult"] == 2.0
    assert w["spread_bps_roundtrip"] == tw * 2.0

    e = cost_adjustment(rsv("extreme"), base)
    assert e["trade_ok"] is False and e["spread_mult"] == 4.0
    assert e["regime_tag"] == "R010:extreme@2026-09-10"
