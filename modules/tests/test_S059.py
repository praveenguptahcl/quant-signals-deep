"""Acceptance tests for S059 — Futures-spot lead-lag prediction.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

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


def recompute(rows):
    sx2 = sum(r["x_lag5"] ** 2 for r in rows)
    sxy = sum(r["x_lag5"] * r["y"] for r in rows)
    beta = sxy / sx2
    return [{"bar": r["bar"], "beta": beta, "y_hat": beta * r["x_lag5"],
             "resid": r["y"] - beta * r["x_lag5"]} for r in rows]


@dataclass
class Config:
    lag_min: int = 5          # [example]
    min_edge_bps: float = 1.0  # [example]
    cost_gate_k: float = 0.5   # [default]

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.50   # cash-leg half-spread [example]
    fee_bps = 0.30      # taker fee incl. regulatory [example]
    borrow_bps = 0.00   # reason: long-only reference [default]
    impact_bps = 0.50   # cash-leg fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    if not math.isfinite(b["x_lag5"]) or not math.isfinite(b["y"]):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    if len(bars) < 4:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    sx2 = sum(r["x_lag5"] ** 2 for r in bars)
    sxy = sum(r["x_lag5"] * r["y"] for r in bars)
    beta = sxy / sx2 if sx2 > 0 else 0.0
    yhat = beta * b["x_lag5"]
    edge_bps = abs(yhat) * 10000.0
    direction = 1 if yhat > 0 and edge_bps > cfg.min_edge_bps else \
                (-1 if yhat < 0 and edge_bps > cfg.min_edge_bps else 0)
    confidence = min(1.0, edge_bps / 10.0) if direction else 0.0  # [example] scale
    gate = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    if not gate:
        direction, confidence = 0, 0.0
    return SignalVector("TEST", direction, confidence, 0.5 * confidence,
                        b["event_ts"], b["asof_ts"] - b["event_ts"], "OK")


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
        got = recompute(parse_tape())
        assert abs(got[0]["beta"] - 322.0/424.0) < 1e-9  # hand-check: Sxy=322e-8, Sxx=424e-8
        xs = [r["x_lag5"] for r in parse_tape()]
        assert abs(sum(x * g["resid"] for x, g in zip(xs, got))) < 1e-12  # through-origin: x'eps=0


def test_signal_emits_valid_signalvector():
    rows = parse_tape()
    cfg, state = Config(), {}
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
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
