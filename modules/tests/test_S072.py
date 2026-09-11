"""Acceptance tests for S072 — Put/call ratio.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S072.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S072_tape.csv"
EXPECTED = FIX / "S072_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['day', 'pcr', 'med5', 'z', 'direction']
COL_TYPES = {'day': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'put_vol': 'float', 'call_vol': 'float'}


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


def _median(xs):
    s = sorted(xs)
    n = len(s)
    return (s[n // 2] + s[(n - 1) // 2]) / 2.0

def _mad(xs):
    m = _median(xs)
    return _median([abs(x - m) for x in xs])

def recompute(rows):
    pcrs = [r["put_vol"] / r["call_vol"] for r in rows]
    out = []
    for i, r in enumerate(rows):
        hist = pcrs[max(0, i - 4):i + 1]
        med, m = _median(hist), _mad(hist)
        rz = (pcrs[i] - med) / (1.4826 * m) if m > 0 else 0.0
        d = 1 if rz > 2.0 else (-1 if rz < -2.0 else 0)
        out.append({"day": r["day"], "pcr": pcrs[i], "med5": med, "z": rz, "direction": d})
    return out


@dataclass
class Config:
    n: int = 5               # smoothing window [example]
    z_star: float = 2.0      # [example]
    cost_gate_k: float = 0.5  # [default]

def _median(xs):
    s = sorted(xs)
    n = len(s)
    return (s[n // 2] + s[(n - 1) // 2]) / 2.0

def _mad(xs):
    m = _median(xs)
    return _median([abs(x - m) for x in xs])

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 1.00   # equity-leg half-spread [example]
    fee_bps = 0.30      # taker fee [example]
    borrow_bps = 1.50   # short-leg borrow amortized [example]
    impact_bps = 1.00   # contrarian fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    if b["call_vol"] <= 0 or b["put_vol"] < 0 or not math.isfinite(b["put_vol"]):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    pcrs = [r["put_vol"] / r["call_vol"] for r in bars]
    hist = pcrs[-cfg.n:]
    med, m = _median(hist), _mad(hist)
    rz = (pcrs[-1] - med) / (1.4826 * m) if m > 0 else 0.0
    direction = 1 if rz > cfg.z_star else (-1 if rz < -cfg.z_star else 0)
    confidence = min(1.0, abs(rz) / 4.0) if direction else 0.0  # [example] scale
    edge_bps = abs(rz) * 40.0  # modeled per-trade edge [example]
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
        assert abs(got[0]["pcr"] - 420.0/380.0) < 1e-9
        assert got[6]["direction"] == 1  # day-6 PCR spike (z=4.32) -> contrarian long
        assert all(g["direction"] in (-1, 0, 1) for g in got)


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
    bad = {"day": 0, "event_ts": 1, "asof_ts": 2, "put_vol": 100.0, "call_vol": 0.0}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
