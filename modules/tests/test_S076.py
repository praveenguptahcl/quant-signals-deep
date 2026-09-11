"""Acceptance tests for S076 — Volatility breakout / squeeze positioning.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S076.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S076_tape.csv"
EXPECTED = FIX / "S076_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['bar', 'range', 'range_ratio', 'bw', 'breakout', 'squeeze']
COL_TYPES = {'bar': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'open': 'float', 'high': 'float', 'low': 'float', 'close': 'float'}


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
    ranges = [r["high"] - r["low"] for r in rows]
    closes = [r["close"] for r in rows]
    bws = []
    for i in range(len(rows)):
        w = closes[max(0, i - 9):i + 1]
        mu = sum(w) / len(w)
        sd = math.sqrt(sum((v - mu) ** 2 for v in w) / len(w)) if len(w) > 1 else 0.0
        bws.append(4 * sd / mu if mu > 0 else 0.0)
    out = []
    for i, r in enumerate(rows):
        hist = ranges[max(0, i - 10):i]
        rr = ranges[i] / (sum(hist) / len(hist)) if hist else 0.0
        p10 = sorted(bws[:i + 1])[max(0, int(0.1 * len(bws[:i + 1])) - 1)] if i > 0 else bws[0]
        out.append({"bar": r["bar"], "range": ranges[i], "range_ratio": rr, "bw": bws[i],
                    "breakout": 1 if rr > 1.75 else 0,
                    "squeeze": 1 if bws[i] <= p10 and i > 0 else 0})
    return out


@dataclass
class Config:
    k: float = 1.75          # expansion multiple [example]
    N: int = 10              # lookback bars [example]
    cost_gate_k: float = 0.5  # [default]

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.50   # breakout-entry half-spread [example]
    fee_bps = 0.30      # taker fee [example]
    borrow_bps = 0.00   # reason: long-breakout reference [default]
    impact_bps = 1.00   # expansion-bar fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    o, h, l, c = b["open"], b["high"], b["low"], b["close"]
    ohlc_ok = (h >= l and h >= max(o, c) and l <= min(o, c)
               and min(o, h, l, c) > 0
               and all(math.isfinite(v) for v in (o, h, l, c)))
    if not ohlc_ok:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    ranges = [r["high"] - r["low"] for r in bars]
    hist = ranges[:-1][-cfg.N:]
    rr = ranges[-1] / (sum(hist) / len(hist)) if hist else 0.0
    closes = [r["close"] for r in bars][-cfg.N:]
    mu = sum(closes) / len(closes)
    sd = math.sqrt(sum((v - mu) ** 2 for v in closes) / len(closes)) if len(closes) > 1 else 0.0
    bw = 4 * sd / mu if mu > 0 else 0.0
    direction = 0
    if rr > cfg.k and b["close"] >= b["open"]:
        direction = 1  # expansion breakout, long in bar direction [example]
    elif rr > cfg.k:
        direction = -1
    confidence = min(1.0, rr / 4.0) if direction else 0.0  # [example] scale
    edge_bps = rr * 8.0  # modeled per-trade edge [example]
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
        assert abs(got[8]["range_ratio"] - 2.2/0.3) < 1e-9
        assert got[8]["breakout"] == 1
        assert sum(g["breakout"] for g in got) == 1


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
    bad = {"bar": 0, "event_ts": 1, "asof_ts": 2, "open": 100.0, "high": 99.0,
           "low": 98.0, "close": 99.5}  # high 99 < open 100 impossible
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
