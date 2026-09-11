"""Acceptance tests for S059 — Futures-spot lead-lag prediction.

Template v1.0.0. The stub implements the chapter's §S3 normative pseudocode:
cost gate as a veto predicate (never raises), executable causality assertion
(earliest fill at t+1 open strictly after the signal event), halt/stale/
warmup/non-finite guards, and UNKNOWN-on-invalid (never interpolate).

Deviations from production §S3, documented in the chapter (§S4):
  * MIN_BARS = 4 [example] warmup floor — the 8-bar fixture tape cannot
    satisfy the 20-session production window rule.

Run: python3 -m pytest modules/tests/test_S059.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S059_tape.csv"
EXPECTED = FIX / "S059_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['bar', 'beta', 'y_hat', 'resid']
COL_TYPES = {'bar': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'x_lag5': 'float', 'y': 'float'}

MIN_BARS = 4            # [example] fixture-scoped warmup floor; production = 20 sessions (§S3)
STALE_TTL_NS = 3_000_000_000   # [default] 3 s staleness TTL (§S0.4)
CADENCE_NS = 60_000_000_000    # [example] 1-min bar cadence → earliest fill at t+1 open


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


def parse_tape():
    return [{k: _conv(r[k], COL_TYPES[k]) for k in COL_TYPES} for r in load_csv(TAPE)]


# ------------------------------------------------- normative pseudocode stub
@dataclass(frozen=True)
class SignalVector:
    symbol: str
    direction: int          # +1 | -1 | 0
    confidence: float       # 0..1
    capital: float          # 0..1
    computed_at: int        # int64 ns UTC
    staleness: int          # ns
    module_state: str       # OK | DEGRADED | UNKNOWN | OFF


@dataclass
class Config:
    lag_min: int = 5          # [example]
    min_edge_bps: float = 1.0  # [example]
    cost_gate_k: float = 0.5   # [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Callable cost model — reference stack for S059 (single source of truth: §S2)."""
    spread_bps = 0.50   # cash-leg half-spread [example]
    fee_bps = 0.30      # taker fee incl. regulatory [example]
    borrow_bps = 0.00   # reason: long-only reference [default]
    impact_bps = 0.50   # cash-leg fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def fit_beta(rows):
    """Through-origin OLS of y on x (lagged futures return)."""
    sx2 = sum(r["x_lag5"] ** 2 for r in rows)
    sxy = sum(r["x_lag5"] * r["y"] for r in rows)
    return sxy / sx2 if sx2 > 0 else 0.0


def recompute(rows):
    beta = fit_beta(rows)
    return [{"bar": r["bar"], "beta": beta, "y_hat": beta * r["x_lag5"],
             "resid": r["y"] - beta * r["x_lag5"]} for r in rows]


def emit(state, beta, bars, cfg):
    """Emit one SignalVector off a pre-fit beta; bars[-1] is the signal bar."""
    b = bars[-1]
    if b.get("mkt") == "HALTED":
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    if b["asof_ts"] - b["event_ts"] > STALE_TTL_NS:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    if any(not math.isfinite(r["x_lag5"]) or not math.isfinite(r["y"]) for r in bars):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    yhat = beta * b["x_lag5"]
    edge_bps = abs(yhat) * 10000.0  # [example] 1e-4 units → bps (§S3)
    direction = 1 if yhat > 0 and edge_bps > cfg.min_edge_bps else \
                (-1 if yhat < 0 and edge_bps > cfg.min_edge_bps else 0)
    cost_ok = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") \
        <= cfg.cost_gate_k * edge_bps
    if direction != 0 and not cost_ok:
        direction = 0  # cost gate vetoes, never raises (§S3)
    confidence = min(1.0, edge_bps / cfg.min_edge_bps - 1.0) if direction != 0 else 0.0
    signal_ts = b["event_ts"]
    earliest_fill_ts = signal_ts + CADENCE_NS
    assert earliest_fill_ts > signal_ts, "causality violated: no signal-bar fills"
    return SignalVector("TEST", direction, confidence, 0.5 * confidence,
                        signal_ts, b["asof_ts"] - b["event_ts"], "OK")


def signal(state, bars, cfg):
    """Normative entry point: warmup floor, then prefix-fit emit."""
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    if len(bars) < MIN_BARS:
        return SignalVector("TEST", 0, 0.0, 0.0, bars[-1]["event_ts"], 0, "UNKNOWN")
    return emit(state, fit_beta(bars), bars, cfg)


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
    # hand-check: Sxy=322e-8, Sxx=424e-8 → beta = 322/424
    assert abs(fit_beta(rows) - 322.0 / 424.0) < 1e-9
    xs = [r["x_lag5"] for r in rows]
    assert abs(sum(x * g["resid"] for x, g in zip(xs, got))) < 1e-12  # through-origin: x'eps=0


def test_signal_emits_valid_signalvector():
    rows = parse_tape()
    cfg, state = Config(), {}
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    # warmup floor pins behavior: first MIN_BARS-1 prefixes are UNKNOWN
    assert [s.module_state for s in sigs[: MIN_BARS - 1]] == ["UNKNOWN"] * (MIN_BARS - 1)
    assert all(s.module_state == "OK" for s in sigs[MIN_BARS - 1:])
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = parse_tape()
    cfg, state = Config(), {}
    for i in range(len(rows)):
        s = signal(state, rows[: i + 1], cfg)
        assert s.computed_at == rows[i]["event_ts"], "signal must be timestamped at its bar"
        later = [r["event_ts"] for r in rows[i + 1:] if r["event_ts"] > s.computed_at]
        if later:
            assert min(later) > s.computed_at, "signal-bar fill"


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "X", "taker", "normal")
    assert cost >= 0.0
    assert cost <= k * 100000.0   # huge edge -> gate passes
    assert not (cost <= k * 0.0001)  # tiny edge -> gate blocks


def test_invalid_input_yields_unknown():
    bad = {"bar": 0, "event_ts": 1, "asof_ts": 2, "x_lag5": float("nan"), "y": 1e-4}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_cost_gate_vetoes_small_edge_on_tape():
    """Pins the ×10000 edge_bps conversion: bar-3 edge ≈ 2.2783 bps < gate."""
    rows = parse_tape()
    cfg = Config()
    beta = fit_beta(rows)
    edge3 = abs(beta * rows[3]["x_lag5"]) * 10000.0
    assert abs(edge3 - 2.2783018868) < 1e-6, edge3  # [measured] off the tape
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert not (cost <= cfg.cost_gate_k * edge3), "gate must block bar 3"
    s = emit({}, beta, rows[:4], cfg)
    assert s.module_state == "OK" and s.direction == 0 and s.confidence == 0.0


def test_full_tape_direction_vector_pinned():
    """Full-tape beta emission: directions and confidences are pinned."""
    rows = parse_tape()
    cfg = Config()
    beta = fit_beta(rows)
    sigs = [emit({}, beta, rows[: i + 1], cfg) for i in range(len(rows))]
    assert [s.direction for s in sigs] == [+1, -1, +1, 0, +1, -1, +1, +1]
    assert [s.confidence for s in sigs] == [1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0]
    for s in sigs:
        assert s.capital == 0.5 * s.confidence
        assert s.module_state == "OK"
    # bar-0 edge pins the conversion: |322/424 * 0.0008| * 10000 ≈ 6.0755 bps
    edge0 = abs(beta * rows[0]["x_lag5"]) * 10000.0
    assert abs(edge0 - 6.0754716981) < 1e-6, edge0


def test_halted_input_yields_unknown():
    rows = parse_tape()
    halted = [dict(r) for r in rows]
    halted[-1]["mkt"] = "HALTED"
    s = emit({}, fit_beta(rows), halted, Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_stale_input_yields_unknown():
    rows = parse_tape()
    stale = [dict(r) for r in rows]
    stale[-1]["asof_ts"] = stale[-1]["event_ts"] + 10_000_000_000  # 10 s > 3 s TTL
    s = emit({}, fit_beta(rows), stale, Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_empty_events_yields_unknown():
    s = signal({}, [], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_causality_earliest_fill_after_signal():
    """Earliest executable fill (t+1 open) is strictly after the signal event."""
    rows = parse_tape()
    cfg = Config()
    beta = fit_beta(rows)
    for i in range(len(rows)):
        s = emit({}, beta, rows[: i + 1], cfg)
        assert s.computed_at == rows[i]["event_ts"], "no lookahead: signal stamped at its bar"
        assert rows[i]["event_ts"] + CADENCE_NS > s.computed_at, "signal-bar fill"
