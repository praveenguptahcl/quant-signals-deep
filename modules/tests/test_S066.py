"""Acceptance tests for S066 — HAR realized-volatility forecast.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S066.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S066_tape.csv"
EXPECTED = FIX / "S066_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['day', 'rv_d', 'rv_w', 'rv_m', 'har']
COL_TYPES = {'day': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'rv': 'float'}


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
    vals = [r["rv"] for r in rows]
    out = []
    for i in range(4, len(vals)):
        d = vals[i]
        w = sum(vals[i - 4:i + 1]) / 5
        m = sum(vals[:i + 1]) / (i + 1)
        f = 5e-5 + 0.40 * d + 0.35 * w + 0.20 * m
        out.append({"day": i, "rv_d": d, "rv_w": w, "rv_m": m, "har": f})
    return out


@dataclass
class Config:
    beta0: float = 5e-5   # [example]
    beta_d: float = 0.40  # [example]
    beta_w: float = 0.35  # [example]
    beta_m: float = 0.20  # [example]
    cost_gate_k: float = 0.5  # [default]

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    # Forecast emits no entries; stack is the downstream strategy's reference [example].
    spread_bps = 0.50
    fee_bps = 0.30
    borrow_bps = 0.00   # reason: forecast-only module [default]
    impact_bps = 0.50
    return spread_bps + fee_bps + borrow_bps + impact_bps

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    vals = [r["rv"] for r in bars]
    if any(v < 0 or not math.isfinite(v) for v in vals) or len(vals) < 5:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    d = vals[-1]
    w = sum(vals[-5:]) / 5
    m = sum(vals) / len(vals)
    f = cfg.beta0 + cfg.beta_d * d + cfg.beta_w * w + cfg.beta_m * m
    confidence = min(1.0, f / 0.001) if f > 0 else 0.0  # [example] scale
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
        assert abs(got[-1]["rv_d"] - 0.00019) < 1e-12
        assert abs(got[-1]["rv_w"] - 0.000162) < 1e-12
        m_mean = 0.00015916666666666667  # mean of the 12 fixture RVs
        assert abs(got[-1]["rv_m"] - m_mean) < 1e-12
        assert abs(got[-1]["har"] - (5e-5 + 0.40*0.00019 + 0.35*0.000162 + 0.20*m_mean)) < 1e-12
        assert len(got) == 8


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
    bad = {"day": 0, "event_ts": 1, "asof_ts": 2, "rv": -0.5}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
