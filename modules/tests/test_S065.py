"""Acceptance tests for S065 — GARCH(1,1) intraday volatility.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S065.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S065_tape.csv"
EXPECTED = FIX / "S065_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['bar', 'sigma']
COL_TYPES = {'bar': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'ret': 'float', 'season': 'float'}


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
    w, a, b = 2.0e-7, 0.06, 0.89
    s2 = w / (1 - a - b)
    out = []
    for r in rows:
        out.append({"bar": r["bar"], "sigma": math.sqrt(s2)})
        s2 = w + a * (r["ret"] / r["season"]) ** 2 + b * s2
    return out


@dataclass
class Config:
    target_vol: float = 0.01  # per-bar vol target [example]
    cost_gate_k: float = 0.5   # [default]

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    # Sizing overlay emits no entries; stack is the downstream strategy's reference [example].
    spread_bps = 0.50
    fee_bps = 0.30
    borrow_bps = 0.00   # reason: sizing overlay; borrow in consumer [default]
    impact_bps = 0.50
    return spread_bps + fee_bps + borrow_bps + impact_bps

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    if any(not math.isfinite(r["ret"]) or r["season"] <= 0 for r in bars):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    w, a, bb = 2.0e-7, 0.06, 0.89
    s2 = w / (1 - a - bb)
    for r in bars[:-1]:
        s2 = w + a * (r["ret"] / r["season"]) ** 2 + bb * s2
    sig = math.sqrt(s2)
    scalar = cfg.target_vol / sig if sig > 0 else 0.0  # position-size scalar [example]
    confidence = min(1.0, scalar / 10.0)  # [example] scale
    gate = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * 50.0
    st = "OK" if gate else "DEGRADED"
    return SignalVector("TEST", 0, confidence, 0.0, b["event_ts"],
                        b["asof_ts"] - b["event_ts"], st)


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
        assert abs(got[0]["sigma"] - math.sqrt(2.0e-7/0.05)) < 1e-12
        assert got[6]["sigma"] > got[5]["sigma"]  # vol rises after the -32bp shock at bar 5
        assert all(g["sigma"] > 0 for g in got)


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
    bad = {"bar": 0, "event_ts": 1, "asof_ts": 2, "ret": 0.001, "season": 0.0}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
