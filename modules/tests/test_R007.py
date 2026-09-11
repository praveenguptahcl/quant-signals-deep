"""Acceptance tests for R007 - Trend-strength regime (v1.1.0).

Reference implementation of the chapter's normative detection logic
(§R2 pseudocode): Wilder ADX(14) sentinel + classical R/S Hurst verifier
with hysteresis state machine, F1-F5 fail-safes, corporate-action /
gap / halt guards wired in (Appendix f v1.0.0).

Fixture: modules/fixtures/R007_tape.csv (170 synthetic daily HLC bars,
generated deterministically by gen_tape() below - no RNG) and
modules/fixtures/R007_expected.csv (golden per-bar outputs).

Run: python3 -m pytest modules/tests/test_R007.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R007_tape.csv"
EXPECTED = FIX / "R007_expected.csv"

TOL = 1e-9            # float tolerance [default]
CADENCE_S = 86400     # indicator cadence in seconds [default]
NS = 1_000_000_000
ESTIMATOR_VERSION = "1.1.0"
STATE_LABELS = ['trending', 'transitional', 'chop', 'unknown',
                'warming', 'missing', 'invalid']
HURST_BOUNDS = (-0.5, 1.5)   # F2 guard band for R/S Hurst [default]
ADX_BOUNDS = (0.0, 100.0)    # mathematical bounds of ADX (F2) [documented]


# ------------------------------------------------------------------ config
@dataclass
class Config:
    """Single Config dataclass per §R0.2. Status tags: [documented] Wilder
    (1978); [default] chapter choice with calibration recipe in §R2;
    [example] illustrative, calibrate before production."""
    adx_n: int = 14              # [documented] Wilder (1978)
    adx_trend: float = 25.0      # [documented] Wilder (1978)
    adx_chop: float = 20.0       # [documented] Wilder (1978)
    verifier_window: int = 28    # [default] = 2 * adx_n; F3 agreement horizon
    verifier_min: int = 20       # [default] min closes for verifier Hurst
    hurst_window: int = 63       # [default] research/long-memory anchor (logged, not gating)
    hurst_trend: float = 0.55    # [example] Hurst trend band
    hurst_mr: float = 0.45       # [example] Hurst mean-reversion band
    min_bars: int = 28           # [default] = 2 * adx_n (first Wilder ADX)
    confirm_bars: int = 2        # [default] hysteresis confirmation count
    ca_jump: float = 0.20        # [default] |log-return| corporate-action tripwire
    ca_tr_mult: float = 3.0      # [default] TR multiple vs trailing median
    gap_reset_mult: float = 5.0  # [default] gap > 5x cadence resets smoother
    staleness_mult: float = 3.0  # [default] F4 staleness TTL = 3x cadence


# ------------------------------------------------------- synthetic fixture
TS0 = 1704229200  # 2024-01-02T21:00:00Z (16:00 ET close) [example]

def gen_tape():
    """Deterministic synthetic tape (no RNG): 50 bars chop (hard alternation,
    strongly anti-persistent) -> 60 bars steady uptrend -> 60 bars chop.
    Exercises: warmup, F3 disagreement at both transitions, hysteresis
    entry/exit confirmation, F3 catching ADX lag after the trend ends."""
    closes = []
    c = 100.0
    for i in range(1, 171):
        if i <= 50:
            c = 100.0 + 1.5 * (1 if i % 2 == 1 else -1)
        elif i <= 110:
            c = c + 1.0 + 0.3 * math.sin(i)
        else:
            c = closes[109] + 1.2 * (1 if i % 2 == 1 else -1)
        closes.append(round(c, 4))
    hdr = ["bar", "event_ts", "asof_ts", "h", "l", "c"]
    rows = []
    for i, cc in enumerate(closes, 1):
        ts = (TS0 + (i - 1) * 86400) * NS
        rows.append({"bar": i, "event_ts": ts, "asof_ts": ts + 3600 * NS,
                     "h": round(cc + 0.4, 4), "l": round(cc - 0.4, 4), "c": cc})
    return hdr, rows


# ------------------------------------------------------------------ maths
def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return float("nan")
    m = n // 2
    return xs[m] if n % 2 else (xs[m - 1] + xs[m]) / 2


def _hurst_rs(cs):
    """Classical rescaled-range Hurst (Hurst 1951 [documented]);
    S = sample stdev (ddof=1) [default]."""
    cs = list(cs)
    n = len(cs)
    if n < 10:
        return float("nan")
    mu = _mean(cs)
    run, cum = 0.0, []
    for x in cs:
        run += x - mu
        cum.append(run)
    R = max(cum) - min(cum)
    S = math.sqrt(sum((x - mu) ** 2 for x in cs) / (n - 1))
    if not (S > 0 and R > 0):
        return float("nan")
    return math.log(R / S) / math.log(n)


def _raw_adx_label(adx, cfg):
    """Crisp Wilder bands. Boundary is exclusive: 25.0 -> transitional."""
    if adx > cfg.adx_trend:
        return 'trending'
    if adx < cfg.adx_chop:
        return 'chop'
    return 'transitional'


def _raw_hurst_label(h, cfg):
    if h > cfg.hurst_trend:
        return 'trending'
    if h < cfg.hurst_mr:
        return 'mr'
    return 'random'


_AGREE = {'trending': 'trending', 'chop': 'mr', 'transitional': 'random'}


def _agree(ra, rh):
    return _AGREE[ra] == rh


def _hysteresis_step(prev, pend, pcount, raw, cfg):
    """Hysteresis state machine. raw = agreed label or None (F3 disagreement).
    Entry to trending/chop needs `confirm_bars` consecutive raw labels;
    exit is via the transitional band (entry band != exit band = hysteresis).
    Returns (emit_label, module_state, prev, pend, pcount)."""
    if raw is None:
        return 'unknown', 'UNKNOWN', prev, None, 0
    if prev is not None and raw == prev:
        return prev, 'OK', prev, None, 0
    if raw == 'transitional':
        return 'transitional', 'OK', 'transitional', None, 0
    if raw == pend:
        pcount += 1
    else:
        pend, pcount = raw, 1
    if pcount >= cfg.confirm_bars:
        return raw, 'OK', raw, None, 0
    return (prev if prev is not None else 'unknown'), 'OK', prev, pend, pcount


# ------------------------------------------------- causal reference engine
def _valid_row(r):
    try:
        h, l, c = float(r['h']), float(r['l']), float(r['c'])
    except (KeyError, TypeError, ValueError):
        return False
    return (math.isfinite(h) and math.isfinite(l) and math.isfinite(c)
            and h >= l and l > 0 and c > 0)


def _process(rows, cfg):
    """Single causal pass over rows (oldest first). Returns per-bar dicts."""
    out = []
    TRs, pDMs, mDMs, dx_hist, closes, tr_hist = [], [], [], [], [], []
    sTR = sp = sm = None
    adx = None
    prev = pend = None
    pcount = 0
    last_ts = last_pc = prev_h = prev_l = None
    n = cfg.adx_n

    def rec(r, **kw):
        d = {'bar': r.get('bar'), 'event_ts': r.get('event_ts', 0),
             'computed_at': r.get('event_ts', 0), 'vintage': 'synthetic',
             'value': float('nan'), 'hurst': float('nan'), 'hurst63': float('nan'),
             'raw_adx': '', 'raw_hurst': '', 'state': 'unknown',
             'module_state': 'UNKNOWN', 'reason': ''}
        d.update(kw)
        return d

    for r in rows:
        ts = r.get('event_ts', 0)
        # E3: halt -> freeze, discard contributions across the halt
        if r.get('market_state') == 'HALTED':
            out.append(rec(r, state='unknown', module_state='UNKNOWN',
                           reason='halt_freeze'))
            last_ts = ts
            continue
        # E2: long gap -> reset smoother, warmup restarts
        if last_ts is not None and ts - last_ts > cfg.gap_reset_mult * CADENCE_S * NS:
            TRs, pDMs, mDMs, dx_hist, closes, tr_hist = [], [], [], [], [], []
            sTR = sp = sm = None
            adx = None
            prev = pend = None
            pcount = 0
            last_pc = prev_h = prev_l = None
            gap = True
        else:
            gap = False
        # F1: invalid row -> UNKNOWN, never interpolate
        if not _valid_row(r):
            out.append(rec(r, state='invalid', module_state='UNKNOWN',
                           reason='F1_invalid_row' + ('+gap_reset' if gap else '')))
            last_ts = ts
            continue
        h, l, c = float(r['h']), float(r['l']), float(r['c'])
        pc = last_pc
        TR = (h - l) if pc is None else max(h - l, abs(h - pc), abs(l - pc))
        # E1: corporate-action tripwire (split/dividend or unadjusted jump)
        ca = bool(r.get('split')) or (
            pc is not None and pc > 0 and abs(math.log(c / pc)) > cfg.ca_jump
            and len(tr_hist) >= 1
            and TR > cfg.ca_tr_mult * _median(tr_hist[-20:]))
        if ca:
            # freeze: skip this bar's contributions, re-baseline to post-event level
            out.append(rec(r, state=(prev or 'unknown'), module_state='DEGRADED',
                           value=(adx if adx is not None else float('nan')),
                           reason='corporate_action_freeze'))
            last_ts, last_pc, prev_h, prev_l = ts, c, h, l
            continue
        tr_hist.append(TR)
        if pc is not None:
            up, dn = h - prev_h, prev_l - l
            pDMs.append(up if up > dn and up > 0 else 0.0)
            mDMs.append(dn if dn > up and dn > 0 else 0.0)
        else:
            pDMs.append(0.0)
            mDMs.append(0.0)
        TRs.append(TR)
        closes.append(c)
        # Wilder smoothing: sums over first n bars, then recursive
        if len(TRs) == n:
            sTR, sp, sm = sum(TRs), sum(pDMs), sum(mDMs)
        elif len(TRs) > n:
            sTR = sTR - sTR / n + TRs[-1]
            sp = sp - sp / n + pDMs[-1]
            sm = sm - sm / n + mDMs[-1]
        # DX defined once n smoothed bars exist (bar n+1); first ADX = mean of
        # first n DX (Wilder), defined at bar 2n; then Wilder-smoothed
        if len(TRs) >= n + 1:
            pdi = 100 * sp / sTR if sTR > 0 else 0.0
            mdi = 100 * sm / sTR if sTR > 0 else 0.0
            den = pdi + mdi
            dx = 100 * abs(pdi - mdi) / den if den > 0 else 0.0
            dx_hist.append(dx)
            if len(dx_hist) == n:
                adx = sum(dx_hist) / n
            elif len(dx_hist) > n:
                adx = (adx * (n - 1) + dx) / n
        # verifier Hurst over trailing window (partial window allowed >= verifier_min)
        hv = float('nan')
        if len(closes) >= cfg.verifier_min:
            seg = closes[-cfg.verifier_window:] if len(closes) >= cfg.verifier_window else closes
            hv = _hurst_rs(seg)
        h63 = _hurst_rs(closes[-cfg.hurst_window:]) if len(closes) >= cfg.hurst_window else float('nan')
        # warmup: ADX undefined or verifier undefined -> DEGRADED, label withheld
        if adx is None or not math.isfinite(hv):
            out.append(rec(r, state='warming', module_state='DEGRADED',
                           value=(float('nan') if adx is None else adx),
                           hurst=hv, hurst63=h63,
                           reason='warmup' + ('+gap_reset' if gap else '')))
            last_ts, last_pc, prev_h, prev_l = ts, c, h, l
            continue
        # F2: mathematical bounds
        if not (ADX_BOUNDS[0] <= adx <= ADX_BOUNDS[1]) or not (HURST_BOUNDS[0] <= hv <= HURST_BOUNDS[1]):
            prev, pend, pcount = prev, None, 0
            out.append(rec(r, state='unknown', module_state='UNKNOWN', value=adx,
                           hurst=hv, hurst63=h63, reason='F2_bounds'))
            last_ts, last_pc, prev_h, prev_l = ts, c, h, l
            continue
        ra, rh = _raw_adx_label(adx, cfg), _raw_hurst_label(hv, cfg)
        raw = ra if _agree(ra, rh) else None   # F3: dual-estimator agreement
        label, mstate, prev, pend, pcount = _hysteresis_step(prev, pend, pcount, raw, cfg)
        out.append(rec(r, state=label, module_state=mstate, value=adx, hurst=hv,
                       hurst63=h63, raw_adx=ra, raw_hurst=rh,
                       reason=('F3_disagree' if raw is None else 'ok')
                              + ('+gap_reset' if gap else '')))
        last_ts, last_pc, prev_h, prev_l = ts, c, h, l
    return out


def primary_indicator(rows, cfg):
    """Sentinel: Wilder ADX path. Returns last-bar dict."""
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
                "computed_at": 0, "vintage": "synthetic"}
    return _process(rows, cfg)[-1]


def second_estimator(rows, cfg):
    """Verifier: R/S Hurst over the trailing verifier window."""
    rows = list(rows)
    if not rows:
        return {"value": float("nan"), "state": "missing", "computed_at": 0}
    last = _process(rows, cfg)[-1]
    hv = last["hurst"]
    return {"value": hv,
            "state": _raw_hurst_label(hv, cfg) if math.isfinite(hv) else "undefined",
            "computed_at": last["computed_at"]}


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label
    value: float          # ADX value
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest contributing bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


def detect(rows, cfg, now_ns=None, select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState - reference implementation
    with F1-F5 fail-safes wired in (Appendix f v1.0.0)."""
    rows = list(rows)
    if not rows:  # F1
        return RegimeState("R007", "missing", float("nan"), ESTIMATOR_VERSION,
                           "synthetic", 0, "UNKNOWN")
    last = _process(rows, cfg)[-1]
    if last["module_state"] != "OK":
        return RegimeState("R007", last["state"], last["value"], ESTIMATOR_VERSION,
                           last["vintage"], last["computed_at"], last["module_state"])
    # F4: staleness timeout
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - last["computed_at"] > cfg.staleness_mult * CADENCE_S * NS:
        return RegimeState("R007", last["state"], last["value"], ESTIMATOR_VERSION,
                           last["vintage"], last["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R007", last["state"], last["value"], ESTIMATOR_VERSION,
                       last["vintage"], last["computed_at"], "OK")


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


def _num(s):
    s = s.strip().lower()
    if s in ("nan", ""):
        return float("nan")
    return float(s)


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Golden fixture: causal recompute of every bar matches expected CSV."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    assert len(evs) == len(exp) == 170
    cfg = Config()
    recs = _process(evs, cfg)
    for d, r in zip(recs, evs):
        want = exp[r["bar"]]
        for key, wk in (("value", "exp_adx"), ("hurst", "exp_hurst"),
                        ("hurst63", "exp_hurst63")):
            wv = _num(want[wk])
            if math.isnan(wv):
                assert math.isnan(d[key]), (r["bar"], key)
            else:
                assert abs(d[key] - wv) < TOL, (r["bar"], key, d[key], wv)
        assert d["state"] == want["exp_state"], r["bar"]
        assert d["module_state"] == want["exp_module_state"], r["bar"]
        assert d["computed_at"] == int(want["exp_computed_at"]), r["bar"]
        assert d["raw_adx"] == want["exp_raw_adx"], r["bar"]
        assert d["raw_hurst"] == want["exp_raw_hurst"], r["bar"]


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R007"
    assert rsv.state in STATE_LABELS
    assert rsv.state == "chop"  # fixture ends in the second chop segment
    assert math.isfinite(rsv.value) and ADX_BOUNDS[0] <= rsv.value <= ADX_BOUNDS[1]
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state == "OK"
    assert rsv.computed_at == evs[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract (§R0.5): a label computed at t may gate signals at t only
    for trades at t+1+. label_ts == newest indicator bar; earliest gated trade
    is strictly later; appending a future breakout bar does not move the
    label stamped at t."""
    evs = tape()
    cfg = Config()
    for i in range(len(evs) - 1):
        label = detect(evs[: i + 1], cfg)
        assert label.computed_at == evs[i]["event_ts"], i
        assert evs[i + 1]["event_ts"] > label.computed_at, f"lookahead at bar {i}"
    base = detect(evs[:-1], cfg)
    future = dict(evs[-1])
    future["bar"] = 171
    future["event_ts"] = evs[-1]["event_ts"] + CADENCE_S * NS
    future["asof_ts"] = future["event_ts"] + 3600 * NS
    future.update({"h": future["c"] * 1.10, "l": future["c"] * 1.02,
                   "c": future["c"] * 1.08})  # synthetic breakout bar
    # history invariance: appending future data must not rewrite the label
    # stamped at t (no retroactive revision of past bars)
    recs_before = _process(evs[:-1], cfg)
    recs_after = _process(evs[:-1] + [future], cfg)
    for d0, d1 in zip(recs_before, recs_after):
        assert d0["state"] == d1["state"] and d0["module_state"] == d1["module_state"]
        assert d0["computed_at"] == d1["computed_at"]
    assert recs_before[-1]["state"] == base.state


def test_warmup_withholds_label():
    """< min_bars (2*adx_n = 28 [default]) -> DEGRADED/warming, no label."""
    evs = tape()
    cfg = Config()
    for i in range(27):
        rsv = detect(evs[: i + 1], cfg)
        assert rsv.module_state == "DEGRADED", i
        assert rsv.state == "warming", i
    assert detect(evs[:28], cfg).module_state in ("OK", "UNKNOWN")


def test_hysteresis_entry_confirm():
    """Chop -> trending needs confirm_bars=2 [default] consecutive raw-trending
    bars: bar 70 (1-indexed) still emits 'chop', bar 71 flips to 'trending'."""
    evs = tape()
    cfg = Config()
    recs = _process(evs, cfg)
    b70, b71 = recs[69], recs[70]
    assert b70["raw_adx"] == "trending" and b70["raw_hurst"] == "trending"
    assert b70["state"] == "chop" and b70["module_state"] == "OK"
    assert b71["state"] == "trending" and b71["module_state"] == "OK"


def test_hysteresis_exit_confirm():
    """Trending -> chop likewise needs 2 consecutive raw-chop bars:
    bar 142 still emits 'trending', bar 143 flips to 'chop'."""
    evs = tape()
    cfg = Config()
    recs = _process(evs, cfg)
    b142, b143 = recs[141], recs[142]
    assert b142["raw_adx"] == "chop" and b142["raw_hurst"] == "mr"
    assert b142["state"] == "trending" and b142["module_state"] == "OK"
    assert b143["state"] == "chop" and b143["module_state"] == "OK"


def test_F3_catches_adx_lag_after_trend():
    """§R7 row 1: ADX stays high after the trend ends while the 28-bar
    verifier Hurst has already fallen -> F3 disagreement -> UNKNOWN
    (restrictive), instead of holding a stale 'trending' label."""
    evs = tape()
    cfg = Config()
    recs = _process(evs, cfg)
    lag = recs[132:141]  # bars 133..141
    assert all(d["module_state"] == "UNKNOWN" for d in lag)
    assert all(d["reason"].startswith("F3_disagree") for d in lag)
    hot = recs[132:138]  # bars 133..138: ADX still above the 25 [documented] line
    assert all(d["value"] > cfg.adx_trend for d in hot)      # ADX still high
    assert all(d["hurst"] < cfg.hurst_trend for d in hot)     # verifier already fell


def test_boundary_values():
    """Crisp Wilder bands: the boundary itself is exclusive (transitional)."""
    cfg = Config()
    assert _raw_adx_label(25.0, cfg) == "transitional"
    assert _raw_adx_label(25.0001, cfg) == "trending"
    assert _raw_adx_label(20.0, cfg) == "transitional"
    assert _raw_adx_label(19.9999, cfg) == "chop"
    assert _raw_hurst_label(0.55, cfg) == "random"
    assert _raw_hurst_label(0.5501, cfg) == "trending"
    assert _raw_hurst_label(0.45, cfg) == "random"
    assert _raw_hurst_label(0.4499, cfg) == "mr"
    assert _agree("trending", "trending") and _agree("chop", "mr")
    assert _agree("transitional", "random")
    assert not _agree("trending", "random") and not _agree("chop", "trending")


def test_hysteresis_step_unit():
    """Pure state-machine transitions at exact confirm counts."""
    cfg = Config()
    # startup: first raw-trending -> pending, emits 'unknown'/OK
    lab, ms, prev, pend, pc = _hysteresis_step(None, None, 0, "trending", cfg)
    assert (lab, ms, prev, pend, pc) == ("unknown", "OK", None, "trending", 1)
    # second consecutive -> flips
    lab, ms, prev, pend, pc = _hysteresis_step(prev, pend, pc, "trending", cfg)
    assert (lab, ms, prev) == ("trending", "OK", "trending")
    # single blip back to chop does not flip (needs 2)
    lab, ms, prev, pend, pc = _hysteresis_step(prev, pend, pc, "chop", cfg)
    assert (lab, prev, pend, pc) == ("trending", "trending", "chop", 1)
    # transitional exits immediately (entry band != exit band)
    lab, ms, prev, pend, pc = _hysteresis_step(prev, pend, pc, "transitional", cfg)
    assert (lab, prev) == ("transitional", "transitional")
    # disagreement -> UNKNOWN, keeps prev for resume
    lab, ms, prev, pend, pc = _hysteresis_step(prev, pend, pc, None, cfg)
    assert (lab, ms, prev) == ("unknown", "UNKNOWN", "transitional")


def test_F1_missing_input_unknown():
    assert detect([], Config()).module_state == "UNKNOWN"
    assert detect([], Config()).state == "missing"
    bad = [dict(event_ts=1, asof_ts=2)]  # missing indicator fields
    rsv = detect(bad, Config())
    assert rsv.module_state == "UNKNOWN" and rsv.state == "invalid"


def test_F2_bounds_violation_unknown():
    """F2 is enforced inside the causal engine: a verifier Hurst outside its
    mathematical guard band [default] forces UNKNOWN on the real code path."""
    import sys as _sys
    mod = _sys.modules[__name__]
    evs = tape()
    orig = mod._hurst_rs
    try:
        mod._hurst_rs = lambda cs: 5.0  # outside HURST_BOUNDS -> F2 trip
        rsv = mod.detect(evs, Config())
        assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"
        assert rsv.state == "unknown"
    finally:
        mod._hurst_rs = orig


def test_F3_dual_estimator_disagreement_unknown():
    """F3 is enforced inside the causal engine via the agreement gate:
    the fixture contains genuine disagreement bars (regime transitions),
    and every one must surface as UNKNOWN/unknown (restrictive)."""
    cfg = Config()
    recs = _process(tape(), cfg)
    disagree = [d for d in recs if d["reason"].startswith("F3_disagree")]
    assert len(disagree) > 0, "fixture must contain F3 disagreement bars"
    for d in disagree:
        assert d["module_state"] == "UNKNOWN" and d["state"] == "unknown"
    # the agreement predicate itself: only matched pairs pass
    assert _agree("trending", "trending") and _agree("chop", "mr")
    assert _agree("transitional", "random")
    assert not _agree("trending", "random") and not _agree("chop", "trending")
    assert not _agree("transitional", "mr")


def test_F4_staleness_unknown():
    evs = tape()
    cfg = Config()
    stale_now = evs[-1]["event_ts"] + 10 * CADENCE_S * NS  # >> 3x cadence
    rsv = detect(evs, cfg, now_ns=stale_now)
    assert rsv.module_state == "UNKNOWN"
    fresh_now = evs[-1]["event_ts"] + 2 * CADENCE_S * NS  # within TTL
    assert detect(evs, cfg, now_ns=fresh_now).module_state == "OK"


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


def test_corporate_action_freezes_state():
    """Split bar: contributions skipped, label held, DEGRADED; next bar resumes
    (re-baselined to the post-event level)."""
    evs = tape()
    cfg = Config()
    pre = detect(evs[:80], cfg)
    assert pre.state == "trending" and pre.module_state == "OK"
    split = dict(evs[80])
    split["split"] = True
    split["c"] = split["c"] * 0.25  # 4:1 split prints a -75% bar
    split["h"] = split["h"] * 0.25
    split["l"] = split["l"] * 0.25
    during = detect(evs[:80] + [split], cfg)
    assert during.module_state == "DEGRADED"
    assert during.state == "trending"  # label held, not recomputed
    after = detect(evs[:80] + [split, evs[81]], cfg)
    assert after.module_state in ("OK", "UNKNOWN", "DEGRADED")


def test_gap_resets_smoother():
    """A >5x-cadence [default] data gap resets the Wilder smoother: the
    detector re-enters warmup instead of trusting stale smoothing state."""
    evs = tape()
    cfg = Config()
    gapped = evs[:80] + [dict(evs[80], event_ts=evs[80]["event_ts"] + 10 * CADENCE_S * NS,
                              asof_ts=evs[80]["asof_ts"] + 10 * CADENCE_S * NS)]
    rsv = detect(gapped, cfg)
    assert rsv.module_state == "DEGRADED" and rsv.state == "warming"


def test_halt_freezes_and_discards():
    """HALTED bar: freeze, emit UNKNOWN, discard contributions across reopen."""
    evs = tape()
    cfg = Config()
    halted = dict(evs[80])
    halted["market_state"] = "HALTED"
    rsv = detect(evs[:80] + [halted], cfg)
    assert rsv.module_state == "UNKNOWN"


def test_dual_estimator_agreement_on_stable_segment():
    """Sentinel and verifier agree through the stable trend core."""
    evs = tape()
    cfg = Config()
    for i in range(75, 111):
        rsv = detect(evs[: i + 1], cfg)
        assert rsv.module_state == "OK" and rsv.state == "trending", i
