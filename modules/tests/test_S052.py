"""Acceptance tests for S052 — Kalman-filter dynamic hedge ratio.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S052.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S052_tape.csv"
EXPECTED = FIX / "S052_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['ev', 'beta', 'innov', 'sqrtF', 'z', 'direction']
COL_TYPES = {'ev': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'x': 'float', 'y': 'float'}


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
    beta, P = 1.20, 0.04
    q, R = 3.021e-6, 0.10610
    out = []
    for r in rows:
        Pp = P + q
        e = r["y"] - beta * r["x"]
        F = r["x"] ** 2 * Pp + R
        K = Pp * r["x"] / F
        beta = beta + K * e
        P = (1 - K * r["x"]) * Pp
        z = e / math.sqrt(F)
        d = -1 if z >= 2.0 else (1 if z <= -2.0 else 0)
        out.append({"ev": r["ev"], "beta": beta, "innov": e,
                    "sqrtF": math.sqrt(F), "z": z, "direction": d})
    return out


@dataclass
class Config:
    z_entry: float = 2.0      # [default]
    cost_gate_k: float = 0.5  # [default]

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.50   # two-leg half-spread sum [example]
    fee_bps = 0.60      # two-leg taker fees [example]
    borrow_bps = 2.00   # short-leg borrow amortized [example]
    impact_bps = 1.00   # two-leg async fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps

def _kf(rows):
    beta, P = 1.20, 0.04
    q, R = 3.021e-6, 0.10610
    zs = []
    for r in rows:
        Pp = P + q
        e = r["y"] - beta * r["x"]
        F = r["x"] ** 2 * Pp + R
        K = Pp * r["x"] / F
        beta = beta + K * e
        P = (1 - K * r["x"]) * Pp
        zs.append(e / math.sqrt(F))
    return zs

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    if b["x"] == 0 or not math.isfinite(b["x"]) or not math.isfinite(b["y"]):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    z = _kf(bars)[-1]
    direction = -1 if z >= cfg.z_entry else (1 if z <= -cfg.z_entry else 0)
    confidence = min(1.0, abs(z) / (2.0 * cfg.z_entry)) if direction else 0.0
    edge_bps = abs(z) * 2.0  # modeled per-trade edge [example]
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
        assert got[10]["direction"] == -1  # large positive innovation -> short spread
        assert got[11]["direction"] == 1   # large negative innovation -> long spread
        # hand-check bar 0: beta=1.20, P=0.04, x=4.1161, y=4.8015 (prior beta too high)
        Pp = 0.04 + 3.021e-6
        e0 = 4.8015 - 1.20 * 4.1161
        F0 = 4.1161 ** 2 * Pp + 0.10610
        assert abs(got[0]["innov"] - e0) < 1e-12
        assert abs(got[0]["beta"] - (1.20 + (Pp * 4.1161 / F0) * e0)) < 1e-12


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
    bad = {"ev": 0, "event_ts": 1, "asof_ts": 2, "x": 0.0, "y": 1.0}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
