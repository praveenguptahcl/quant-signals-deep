"""Acceptance tests for R017 - Funding-stress regime (v1.1.0).

Normative detector (R017.md §R2): point-in-time spread
    S_t = (SOFR_t - bench_t) * 100  [bps]
with hysteresis entry/exit bands, a dual-estimator cross-check (F3), and an
expected-gap carry for the business-day-only SOFR publication (a missing bar
<= 3 calendar days after the last valid bar carries the label as DEGRADED;
longer gaps go UNKNOWN, never interpolated).

Run: python3 -m pytest modules/tests/test_R017.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R017_tape.csv"
EXPECTED = FIX / "R017_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
PUB_LAG_S = 129600  # synthetic T+1 publication lag used in the fixture: 36 h [example]
OPEN_OFFSET_S = 48600  # 13:30 UTC ~= US equity open, earliest gated trade [example]
EXPECTED_GAP_S = 3 * 86400  # weekend/holiday carry window, calendar days [default]
BOUNDS = (-100.0, 500.0)  # F2 mathematical sanity bounds on the spread, bps [default]
RATE_SANITY = (0.0, 50.0)  # F1 sanity bounds on raw rate inputs, percent [default]
SPREAD_PRECISION = 6  # spread rounded to 1e-6 bps (float64) before band/dual comparisons [default]
ESTIMATOR_VERSION = "1.1.0"

STATE_LABELS = ["normal", "tight", "stressed", "missing", "invalid", "out_of_bounds"]


def _num(v):
    """Parse a possibly-missing CSV field to float; None if absent/invalid."""
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _leg_rate(r, leg):
    # 'ioer' is the deprecated pre-2021-07-29 alias of 'iorb' [documented FRED].
    key = leg
    if key == "iorb" and r.get("iorb") in ("", None) and r.get("ioer") not in ("", None):
        key = "ioer"
    return _num(r.get(key))


def _spread(r, leg):
    """(SOFR - leg) * 100 in bps; None if a leg is missing; 'invalid' if a raw
    rate is outside RATE_SANITY (F1)."""
    sofr = _num(r.get("sofr"))
    lv = _leg_rate(r, leg)
    if sofr is None or lv is None:
        return None
    if not (RATE_SANITY[0] <= sofr <= RATE_SANITY[1]
            and RATE_SANITY[0] <= lv <= RATE_SANITY[1]):
        return "invalid"
    return (sofr - lv) * 100.0


def _hysteresis_step(s, prev, cfg):
    """Normative §R2 state machine. Entry is eager, exit needs the band low:
    normal->tight at S >= entry_tight; tight->stressed at S > entry_stressed;
    stressed exits only below exit_stressed, then re-evaluates the tight exit
    so a collapse to calm lands in normal in one bar."""
    if prev in (None, "normal"):
        if s > cfg.entry_stressed:
            return "stressed"
        if s >= cfg.entry_tight:
            return "tight"
        return "normal"
    if prev == "tight":
        if s > cfg.entry_stressed:
            return "stressed"
        if s < cfg.exit_tight:
            return "normal"
        return "tight"
    if prev == "stressed":
        if s < cfg.exit_stressed:
            return "normal" if s < cfg.exit_tight else "tight"
        return "stressed"
    raise ValueError(prev)


def label_series(rows, cfg):
    """Causal per-bar labels. Returns a list of dicts with keys:
    bar, event_ts, asof_ts, value, state, computed_at, module_state, note."""
    rows = list(rows)
    out = []
    prev_label = "normal"
    last_valid = None  # {value, state, computed_at, event_ts}
    for r in rows:
        bar = r.get("bar")
        ev = int(r["event_ts"])
        asof = int(r.get("asof_ts", ev))
        base = {"bar": bar, "event_ts": ev, "asof_ts": asof}
        s = _spread(r, cfg.bench)
        v = _spread(r, cfg.verifier)
        if s is None:
            # Missing bar (weekend/holiday/feed gap): expected-gap carry, else F1.
            if last_valid is not None and (ev - last_valid["event_ts"]) <= EXPECTED_GAP_S * NS:
                out.append({**base, "value": last_valid["value"], "state": last_valid["state"],
                            "computed_at": last_valid["computed_at"],
                            "module_state": "DEGRADED", "note": "expected-gap carry"})
            else:
                out.append({**base, "value": float("nan"), "state": "missing",
                            "computed_at": last_valid["computed_at"] if last_valid else 0,
                            "module_state": "UNKNOWN", "note": "F1 missing input"})
            continue
        if s == "invalid":
            out.append({**base, "value": float("nan"), "state": "invalid",
                        "computed_at": asof, "module_state": "UNKNOWN",
                        "note": "F1 invalid field"})
            continue
        # Precision rule (§R2): round to 1e-6 bps before band/dual comparisons so
        # documented boundaries (10.0/25.0/22.0/8.0) compare deterministically.
        s = round(s, SPREAD_PRECISION)
        if isinstance(v, float):
            v = round(v, SPREAD_PRECISION)
        if not (BOUNDS[0] <= s <= BOUNDS[1]) or (isinstance(v, float)
                                                 and not (BOUNDS[0] <= v <= BOUNDS[1])):
            out.append({**base, "value": s, "state": "out_of_bounds",
                        "computed_at": asof, "module_state": "UNKNOWN", "note": "F2 bounds"})
            continue
        label = _hysteresis_step(s, prev_label, cfg)
        if v is None or v == "invalid":
            ms, note = "DEGRADED", "F3 verifier unavailable"
        elif abs(s - v) > cfg.dual_tol_bps:
            out.append({**base, "value": s, "state": label, "computed_at": asof,
                        "module_state": "UNKNOWN", "note": "F3 disagreement"})
            continue
        else:
            ms, note = "OK", ""
        out.append({**base, "value": s, "state": label, "computed_at": asof,
                    "module_state": ms, "note": note})
        prev_label = label
        last_valid = {"value": s, "state": label, "computed_at": asof, "event_ts": ev}
    return out


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
            if isinstance(v, str) and v.strip() == "":
                row[k] = ""
            else:
                try:
                    row[k] = int(v)
                except (ValueError, TypeError):
                    try:
                        row[k] = float(v)
                    except (ValueError, TypeError):
                        row[k] = v
        rows.append(row)
    return rows


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label, e.g. "stressed"
    value: float          # indicator value
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= asof_ts of the vintage used)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


@dataclass(frozen=True)
class Config:
    entry_tight: float = 10.0    # normal -> tight at S >= entry_tight [default]
    exit_tight: float = 8.0      # tight -> normal at S < exit_tight [default]
    entry_stressed: float = 25.0  # -> stressed at S > entry_stressed [default]
    exit_stressed: float = 22.0  # stressed exits at S < exit_stressed [default]
    dual_tol_bps: float = 10.0   # F3 dual-estimator tolerance [default]
    bench: str = "ois"           # primary benchmark leg: "ois" | "iorb" [default]
    verifier: str = "iorb"        # cross-check leg: "iorb" [default]


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


def detect(rows, cfg, now_ns=None, select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState — reference implementation
    with F1-F5 fail-safes wired in (Appendix f v1.0.0)."""
    series = label_series(rows, cfg)
    if not series:
        return RegimeState("R017", "missing", float("nan"), ESTIMATOR_VERSION,
                           "synthetic", 0, "UNKNOWN")
    last = series[-1]
    module_state = last["module_state"]
    # F4: staleness timeout — 3x cadence on the vintage actually used.
    now = now_ns if now_ns is not None else int(rows[-1]["event_ts"]) + CADENCE_S * NS
    if module_state == "OK" and now - last["computed_at"] > 3 * CADENCE_S * NS:
        module_state = "UNKNOWN"
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R017", last["state"], last["value"], ESTIMATOR_VERSION,
                       "synthetic", last["computed_at"], module_state)


# ------------------------------------------------------------------- tests
def _bar(**kw):
    r = {"bar": kw.get("bar", 1), "event_ts": kw.get("event_ts", 1000),
         "asof_ts": kw.get("asof_ts", 1000 + PUB_LAG_S * NS)}
    r.update({k: v for k, v in kw.items() if k not in ("bar", "event_ts", "asof_ts")})
    return r


def _const_tape(sofr, ois=5.15, iorb=5.14, n=1, ev0=1000, step=86400 * NS):
    return [_bar(sofr=sofr, ois=ois, iorb=iorb, bar=i + 1,
                 event_ts=ev0 + i * step) for i in range(n)]


def test_fixture_recomputes_to_expected():
    """Causal recompute of each bar matches the expected CSV (value, state,
    computed_at, module_state)."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    cfg = Config()
    series = label_series(evs, cfg)
    assert len(series) == len(exp) == len(evs)
    for i, got in enumerate(series):
        want = exp[i + 1]
        wv = float(want["exp_value"])
        if math.isnan(wv):
            assert math.isnan(got["value"]), i
        else:
            assert abs(got["value"] - wv) < TOL, (i, got["value"], wv)
        assert got["state"] == want["exp_state"], i
        assert got["computed_at"] == int(want["exp_computed_at"]), i
        assert got["module_state"] == want["exp_module_state"], i


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, Config())
    assert rsv.regime_id == "R017"
    assert rsv.state in STATE_LABELS
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["asof_ts"]


def test_hysteresis_transition_path():
    """Pins the full label path over the tape: entry eagerness, hysteresis
    holds, the stressed->normal collapse, and the exact 25.0/22.0 boundaries."""
    series = label_series(tape(), Config())
    got = [b["state"] for b in series[:11]]
    assert got == ["normal", "tight", "tight", "tight", "stressed", "stressed",
                   "tight", "tight", "normal", "stressed", "normal"], got


def test_boundary_pins():
    """Exact-boundary behavior of the hysteresis bands (defaults)."""
    cfg = Config()
    # from normal: 10.0 enters tight, 9.999 stays normal
    assert label_series(_const_tape(5.25, n=1), cfg)[-1]["state"] == "tight"    # S=10.0
    assert label_series(_const_tape(5.24999, n=1), cfg)[-1]["state"] == "normal"  # S=9.999
    # 25.0 exactly does NOT enter stressed from tight (entry needs > 25)
    rows = _const_tape(5.25, n=1) + _const_tape(5.40, n=1, ev0=1000 + 86400 * NS)
    assert label_series(rows, cfg)[-1]["state"] == "tight"                      # S=25.0
    # stressed holds at exactly 22.0 (exit needs < 22)
    rows = _const_tape(5.60, n=1) + _const_tape(5.37, n=1, ev0=1000 + 86400 * NS)
    assert label_series(rows, cfg)[-1]["state"] == "stressed"                    # S=22.0
    # tight holds at exactly 8.0 (exit needs < 8)
    rows = _const_tape(5.25, n=1) + _const_tape(5.23, n=1, ev0=1000 + 86400 * NS)
    assert label_series(rows, cfg)[-1]["state"] == "tight"                       # S=8.0


def test_no_lookahead_regime_gating():
    """Lag contract: a label at bar t uses only data with event_ts <= t
    (prefix-invariance); the vintage is T+1 (asof_ts > event_ts); the earliest
    gated trade (next bar's open) is strictly after computed_at."""
    evs = tape()
    cfg = Config()
    full = label_series(evs, cfg)
    for i in range(len(evs)):
        prefix = label_series(evs[: i + 1], cfg)[-1]
        assert prefix["computed_at"] == full[i]["computed_at"], f"future bar moved label at {i}"
        assert prefix["state"] == full[i]["state"], f"future bar moved state at {i}"
    for i, b in enumerate(full):
        if b["module_state"] in ("OK", "DEGRADED") and not math.isnan(b["value"]):
            assert b["asof_ts"] > b["event_ts"], f"T+1 vintage violated at bar {i}"
            assert b["computed_at"] > b["event_ts"], f"label_ts !> indicator_ts at bar {i}"
    for i in range(len(evs) - 1):
        if full[i]["module_state"] in ("OK", "DEGRADED"):
            earliest_trade = int(evs[i + 1]["event_ts"]) + OPEN_OFFSET_S * NS
            assert earliest_trade > full[i]["computed_at"], f"lookahead at bar {i}"


def test_publication_lag_T_plus_1():
    """Every tape bar carries a T+1 vintage: asof_ts - event_ts >= 1 day."""
    for r in tape():
        assert int(r["asof_ts"]) - int(r["event_ts"]) >= 86400 * NS, r["bar"]


def test_expected_gap_carry_degraded():
    """Bar 12 has no SOFR (weekend-style gap): the label is carried as
    DEGRADED, value/state pinned, computed_at pinned to bar 11's vintage."""
    series = label_series(tape(), Config())
    b12, b11 = series[11], series[10]
    assert b12["module_state"] == "DEGRADED"
    assert b12["state"] == b11["state"] == "normal"
    assert abs(b12["value"] - b11["value"]) < TOL
    assert b12["computed_at"] == b11["computed_at"]
    # carried vintage is pinned to bar 11; it predates bar 12's own vintage
    assert b12["computed_at"] < b12["asof_ts"]


def test_recovery_after_gap():
    """Bar 13 resumes on a valid print: OK, hysteresis state intact."""
    series = label_series(tape(), Config())
    b13 = series[12]
    assert b13["module_state"] == "OK"
    assert b13["state"] == "normal" and abs(b13["value"] - 1.0) < 1e-6


def test_gap_expiry_unknown():
    """A missing bar more than 3 calendar days after the last valid bar is
    UNKNOWN (no interpolation across long gaps)."""
    rows = _const_tape(5.20, n=1, ev0=1000)
    rows.append(_bar(bar=2, event_ts=1000 + 5 * 86400 * NS, sofr="", ois=5.15, iorb=5.14))
    got = label_series(rows, Config())[-1]
    assert got["module_state"] == "UNKNOWN" and got["state"] == "missing"


def test_F1_missing_input_unknown():
    assert detect([], Config()).module_state == "UNKNOWN"
    # missing bar with no prior valid label to carry -> UNKNOWN
    rows = [_bar(bar=1, event_ts=1000, sofr="", ois=5.15, iorb=5.14)]
    assert detect(rows, Config()).module_state == "UNKNOWN"


def test_F1_invalid_field_unknown():
    rows = _const_tape(999.0, n=1)  # raw rate outside RATE_SANITY
    rsv = detect(rows, Config())
    assert rsv.module_state == "UNKNOWN" and rsv.state == "invalid"


def test_F2_bounds_violation_unknown():
    poison = [_bar(bar=1, event_ts=1000, sofr=15.15, ois=5.15, iorb=5.15)]
    rsv = detect(poison, Config())  # SOFR-OIS = 1000 bps > 500 bound -> F2
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"


def test_F3_dual_disagreement_unknown():
    """Tape bar 14: SOFR-OIS = 15 bps vs SOFR-IORB = 130 bps -> F3 UNKNOWN."""
    series = label_series(tape(), Config())
    b14 = series[13]
    assert b14["module_state"] == "UNKNOWN" and abs(b14["value"] - 15.0) < 1e-6
    assert detect(tape(), Config()).module_state == "UNKNOWN"


def test_F3_verifier_missing_degraded():
    """Verifier leg absent but primary valid: honest DEGRADED, not silent OK."""
    rows = _const_tape(5.25, n=2, iorb="")
    got = label_series(rows, Config())[-1]
    assert got["module_state"] == "DEGRADED" and got["state"] == "tight"


def test_F4_staleness_unknown():
    evs = tape()[:11]  # end on a valid bar
    stale_now = int(evs[-1]["event_ts"]) + 10 * CADENCE_S * NS  # >> 3x cadence
    rsv = detect(evs, Config(), now_ns=stale_now)
    assert rsv.module_state == "UNKNOWN"


def test_F5_regime_mining_guard():
    evs = tape()[:11]
    try:
        detect(evs, Config(), select_periods=True, preregistered=False)
    except RegimeMiningError:
        pass
    else:
        raise AssertionError("F5: unregistered period selection must raise")
    rsv = detect(evs, Config(), select_periods=True, preregistered=True)
    assert rsv.module_state == "OK"


def test_dual_estimator_agreement():
    """Sentinel (SOFR-OIS) vs Verifier (SOFR-IORB) agree within tolerance on
    every valid fixture bar."""
    cfg = Config()
    evs = tape()
    for r, b in zip(evs, label_series(evs, cfg)):
        if b["module_state"] == "OK":
            s = (float(r["sofr"]) - float(r["ois"])) * 100
            v = (float(r["sofr"]) - float(r["iorb"])) * 100
            assert abs(s - v) <= cfg.dual_tol_bps, (r["bar"], s, v)


def test_ioer_alias():
    """Pre-2021-07-29 tapes carrying 'ioer' instead of 'iorb' still verify."""
    rows = [_bar(bar=1, event_ts=1000, sofr=5.25, ois=5.15, iorb="", ioer=5.14)]
    got = label_series(rows, Config())[-1]
    assert got["module_state"] == "OK" and got["state"] == "tight"
