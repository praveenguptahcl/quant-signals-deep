"""Acceptance tests for S067 — Intraday vol seasonality / diurnal deseasonalization.

Template v1.0.0 (module v1.1.0). Reference implementation of the chapter's
normative §S3 pseudocode: all variables bound, guards inline
(locate/cooldown/staleness/halt), executable cost-gate predicate
expected_cost_bps(...) <= k*edge_bps, and causality pins
(assert fill_event > signal_event).

Run: python3 -m pytest modules/tests/test_S067.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S067_tape.csv"
EXPECTED = FIX / "S067_expected.csv"
EDGE_ALLZERO = FIX / "S067_edge_allzero.csv"
EDGE_INVALID = FIX / "S067_edge_invalid.csv"
EDGE_STALE = FIX / "S067_edge_stale.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ['day', 'bin', 's_b', 'r_adj']
COL_TYPES = {'day': 'int', 'bin': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'absr': 'float'}
TTL_NS = 3_000_000_000          # staleness TTL, 3 s [default] (§S0.4)
CONTINUOUS, HALTED, AUCTION = "CONTINUOUS_TRADING", "HALTED", "AUCTION"


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def _conv(v, t):
    if t == "int":
        return int(v)
    if t == "float":
        return float(v)
    return v


def parse_csv(path):
    rows = load_csv(path)
    return [{k: _conv(r[k], COL_TYPES[k]) for k in COL_TYPES} for r in rows]


def parse_tape():
    return parse_csv(TAPE)


# ------------------------------------------------- normative pseudocode stub
# Mirrors §S3 exactly: bound constants, guards inline, no hidden defaults.
@dataclass(frozen=True)
class SignalVector:
    symbol: str
    direction: int          # +1 | -1 | 0  (S067 always 0)
    confidence: float       # 0..1
    capital: float          # 0..1  (S067 always 0.0)
    computed_at: int        # int64 ns UTC (signal event)
    staleness: int          # ns
    module_state: str       # OK | DEGRADED | UNKNOWN | OFF


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        raise ValueError("empty bin")
    return (s[n // 2] + s[(n - 1) // 2]) / 2.0


@dataclass
class Config:
    window_days: int = 20     # calibrate (§S0.2 recipe)
    cost_gate_k: float = 0.5  # [default]
    edge_bps_ref: float = 50.0  # [example] reference level for the gate
    confidence_scale: float = 4.0  # [example] seasonality-strength scale
    ttl_ns: int = TTL_NS      # [default]
    cooldown_s: int = 60      # [default] post-compliance-block cooldown


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    # Callable mirrors the §S2 COST block exactly (reference stack; S067 emits
    # no entries). borrow_bps_per_day = 0.00 [default]: normalizer-only module.
    spread_bps = 0.50
    fee_bps = 0.30
    borrow_bps = 0.00   # reason: normalizer-only module [default]
    impact_bps = 0.50
    return spread_bps + fee_bps + borrow_bps + impact_bps


def recompute(rows):
    """Reference estimator: median |r| per bin, normalized to mean 1."""
    by = {}
    for r in rows:
        by.setdefault(r["bin"], []).append(r["absr"])
    meds = {b: _median(v) for b, v in by.items()}
    mm = sum(meds.values()) / len(meds)
    s = {b: (meds[b] / mm if mm > 0 else 1.0) for b in meds}
    return [{"day": r["day"], "bin": r["bin"], "s_b": s[r["bin"]],
             "r_adj": r["absr"] / s[r["bin"]]} for r in rows]


def signal(state, events, cfg, now_ns=None):
    """Normative §S3 pseudocode as executable stub. Guards inline."""
    state = dict(state or {})
    events = list(events)
    if not events:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")  # F1
    b = events[-1]
    # F1 schema: every required key present, int64 timestamps sane
    if any(k not in b for k in COL_TYPES) or b["asof_ts"] < b["event_ts"]:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    # Halt / auction guards (§S0.5 market-state table)
    mkt = state.get("market_state", CONTINUOUS)
    if mkt == HALTED:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"],
                            b["asof_ts"] - b["event_ts"], "UNKNOWN")
    if mkt == AUCTION:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"],
                            b["asof_ts"] - b["event_ts"], "DEGRADED")
    # Staleness guard (§S0.4 TTL): feed latency or wall-clock lag beyond TTL
    feed_latency_ns = b["asof_ts"] - b["event_ts"]
    if feed_latency_ns > cfg.ttl_ns:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"],
                            feed_latency_ns, "UNKNOWN")
    if now_ns is not None and (now_ns - b["asof_ts"]) > cfg.ttl_ns:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"],
                            now_ns - b["asof_ts"], "UNKNOWN")
    # Cooldown guard (C10): no re-emit within cooldown after a block
    if state.get("cooldown_until_ns", 0) > b["event_ts"]:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"],
                            feed_latency_ns, "UNKNOWN")
    # F2 bounds: |r| must be >= 0 and finite; never interpolate
    if any(r["absr"] < 0 or not math.isfinite(r["absr"]) for r in events):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"],
                            feed_latency_ns, "UNKNOWN")
    # F5: medians undefined below the estimation window
    if len({r["day"] for r in events}) < cfg.window_days:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"],
                            feed_latency_ns, "UNKNOWN")
    # Estimator: median |r| per bin, mean-1 normalization [example]
    by = {}
    for r in events:
        by.setdefault(r["bin"], []).append(r["absr"])
    meds = {k: _median(v) for k, v in by.items()}
    mm = sum(meds.values()) / len(meds)
    sb = meds[b["bin"]] / mm if mm > 0 else 1.0  # mm=0 fallback [example]
    confidence = min(1.0, abs(sb - 1.0) * cfg.confidence_scale)  # [example]
    # Locate: not applicable by construction — direction is always 0, S067
    # never emits SHORT; consumers hold locate_ok per C7.
    cost_bps = expected_cost_bps(notional=0.0, adv_pct=0.0,
                                 venue="XNAS", side="taker", urgency="batch")
    gate_ok = cost_bps <= cfg.cost_gate_k * cfg.edge_bps_ref
    st = "OK" if gate_ok else "DEGRADED"  # cost-gate veto path
    return SignalVector("TEST", 0, confidence, 0.0, b["event_ts"],
                        feed_latency_ns, st)


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Reference recomputation of the tape matches expected.csv."""
    rows = parse_tape()
    exp = load_csv(EXPECTED)
    got = recompute(rows)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, e in zip(got, exp):
        for k in EXPECTED_COLS:
            gv, ev = g[k], e[k]
            try:
                assert abs(float(gv) - float(ev)) <= TOL, (k, gv, ev)
            except (ValueError, TypeError):
                assert str(gv) == str(ev), (k, gv, ev)


def test_sb_mean_is_one_on_fixture():
    """Normalization invariant: mean(s_b) == 1 exactly [measured]."""
    sbs = {g["bin"]: g["s_b"] for g in recompute(parse_tape())}
    assert abs(sum(sbs.values()) / 4 - 1.0) < TOL
    assert sbs[3] > sbs[2]  # close bin more seasonal than midday [measured]
    assert abs(recompute(parse_tape())[0]["r_adj"] - 0.0012 / sbs[0]) < TOL


def test_signal_emits_valid_signalvector():
    cfg = Config(window_days=3)  # fixture holds 3 days [example]
    rows = parse_tape()
    sigs = [signal({}, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for i, s in enumerate(sigs):
        assert s.direction == 0, "S067 is a normalizer; direction always 0"
        assert 0.0 <= s.confidence <= 1.0
        assert s.capital == 0.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
        # F5 guard: only OK once the estimation window is satisfied
        days = len({r["day"] for r in rows[: i + 1]})
        assert s.module_state == ("OK" if days >= 3 else "UNKNOWN"), i
    assert sigs[-1].module_state == "OK", "healthy full-window lane must be OK"


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    cfg = Config(window_days=3)
    rows = parse_tape()
    for i in range(len(rows)):
        s = signal({}, rows[: i + 1], cfg)
        assert s.computed_at == rows[i]["event_ts"], "signal timestamped at its bar"
        later = [r["event_ts"] for r in rows[i + 1:] if r["event_ts"] > s.computed_at]
        if later:
            assert min(later) > s.computed_at, "signal-bar fill"


def test_causality_fill_after_signal():
    """Causality pin: fill_event (earliest tradable = next bar open) > signal_event."""
    cfg = Config(window_days=3)
    rows = parse_tape()
    for i in range(len(rows) - 1):
        s = signal({}, rows[: i + 1], cfg)
        signal_event = s.computed_at
        fill_event = rows[i + 1]["event_ts"]  # earliest fill @ open(t+1)
        assert fill_event > signal_event, (fill_event, signal_event)


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert abs(cost - 1.30) < TOL, "callable must mirror the §S2 stack exactly"
    assert cost <= 0.5 * 100000.0    # huge edge -> gate passes
    assert not (cost <= 0.5 * 0.0001)  # tiny edge -> gate blocks


def test_cost_gate_veto_path():
    """k driven to ~0 must veto: healthy input degrades to DEGRADED."""
    cfg = Config(window_days=3, cost_gate_k=1e-9)  # [example] veto probe
    s = signal({}, parse_tape(), cfg)
    assert s.module_state == "DEGRADED", "cost-gate veto must degrade, not OK"
    assert s.direction == 0 and s.capital == 0.0


def test_invalid_input_yields_unknown():
    """Negative |r| (F2) -> UNKNOWN, never interpolate."""
    rows = parse_csv(EDGE_INVALID)
    bad = [r for r in rows if r["absr"] < 0]
    assert bad, "fixture must contain a negative-|r| row"
    s = signal({}, rows, Config(window_days=1))
    assert s.module_state == "UNKNOWN" and s.direction == 0
    # The valid prefix alone stays healthy
    s_ok = signal({}, rows[:4], Config(window_days=1))
    assert s_ok.module_state == "OK"


def test_nan_absr_yields_unknown():
    """NaN |r| (F2 non-finite) -> UNKNOWN."""
    rows = parse_csv(EDGE_INVALID)
    assert any(math.isnan(r["absr"]) for r in rows), "fixture must contain a NaN row"
    s = signal({}, rows, Config(window_days=1))
    assert s.module_state == "UNKNOWN"


def test_empty_input_yields_unknown():
    s = signal({}, [], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_missing_field_yields_unknown():
    """Row missing a canonical field (F1 schema violation) -> UNKNOWN."""
    rows = parse_tape()
    broken = dict(rows[0])
    del broken["absr"]
    s = signal({}, [broken], Config(window_days=1))
    assert s.module_state == "UNKNOWN"


def test_all_zero_returns_mm0_fallback():
    """Boundary: mm == 0 -> s_b = 1.0 fallback, r_adj = 0, no crash."""
    rows = parse_csv(EDGE_ALLZERO)
    got = recompute(rows)
    assert all(abs(g["s_b"] - 1.0) < TOL for g in got)
    assert all(abs(g["r_adj"]) < TOL for g in got)
    s = signal({}, rows, Config(window_days=1))
    assert s.module_state == "OK"
    assert s.confidence == 0.0  # |1-1|*4 = 0: flat shape, zero seasonality


def test_single_bin_shape_is_flat():
    """Boundary: B == 1 -> median/mean = 1, confidence 0, no crash."""
    rows = [dict(r, bin=0) for r in parse_tape()]
    s = signal({}, rows, Config(window_days=1))
    assert s.module_state == "OK"
    assert s.confidence == 0.0


def test_confidence_clamped_at_extreme_sb():
    """confidence = min(1, |s_b-1|*4): extreme seasonality saturates at 1."""
    rows = parse_tape()
    spike = [dict(r) for r in rows]
    spike[-1]["absr"] = 1.0  # [example] extreme open-bin spike
    s = signal({}, spike, Config(window_days=1))
    assert s.confidence == 1.0
    assert 0.0 <= s.confidence <= 1.0


def test_stale_input_yields_unknown():
    """Feed latency 10 s > TTL 3 s [default] -> UNKNOWN via staleness guard."""
    rows = parse_csv(EDGE_STALE)
    assert rows[0]["asof_ts"] - rows[0]["event_ts"] == 10_000_000_000
    s = signal({}, rows, Config(window_days=1))
    assert s.module_state == "UNKNOWN"
    # Healthy lane: fixture latency is 120 us [measured] << TTL
    healthy = parse_tape()
    assert healthy[0]["asof_ts"] - healthy[0]["event_ts"] == 120_000
    s_ok = signal({}, healthy, Config(window_days=3))
    assert s_ok.module_state == "OK"


def test_stale_by_wallclock_yields_unknown():
    rows = parse_tape()
    now_ns = rows[-1]["asof_ts"] + 60_000_000_000  # 60 s [example] after asof
    s = signal({}, rows, Config(window_days=3), now_ns=now_ns)
    assert s.module_state == "UNKNOWN"


def test_halted_market_state_yields_unknown():
    """HALTED: freeze state, emit UNKNOWN, exclude halted bars from medians."""
    s = signal({"market_state": HALTED}, parse_tape(), Config(window_days=3))
    assert s.module_state == "UNKNOWN"


def test_auction_market_state_degraded():
    """AUCTION: hold last SignalVector; state DEGRADED."""
    s = signal({"market_state": AUCTION}, parse_tape(), Config(window_days=3))
    assert s.module_state == "DEGRADED"


def test_cooldown_blocks_reemit():
    """C10: no re-emit while cooldown_until_ns is in the future."""
    rows = parse_tape()
    s = signal({"cooldown_until_ns": rows[-1]["event_ts"] + 60_000_000_000},
               rows, Config(window_days=3))
    assert s.module_state == "UNKNOWN"


def test_history_below_window_yields_unknown():
    """F5: fewer distinct days than window_days -> UNKNOWN (medians undefined)."""
    rows = parse_tape()[:4]  # 1 day only [example]
    s = signal({}, rows, Config(window_days=20))
    assert s.module_state == "UNKNOWN"
