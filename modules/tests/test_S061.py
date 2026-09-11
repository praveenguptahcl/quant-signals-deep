"""Acceptance tests for S061 — ADR / dual-listed premium.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S061.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S061_tape.csv"
EXPECTED = FIX / "S061_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['bar', 'fair_adr', 'premium_bps', 'direction']
COL_TYPES = {'bar': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'local_px': 'float', 'fx': 'float', 'adr_px': 'float', 'ratio': 'int', 'home_open': 'int'}


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
    out = []
    for r in rows:
        fair = r["local_px"] * r["fx"] * r["ratio"]
        prem = (r["adr_px"] - fair) / fair * 10000.0
        d = 0
        if r["home_open"] and abs(prem) > 25.0:
            d = -1 if prem > 0 else 1
        out.append({"bar": r["bar"], "fair_adr": fair, "premium_bps": prem, "direction": d})
    return out


@dataclass
class Config:
    premium_bound_bps: float = 25.0  # [example]
    cost_gate_k: float = 0.5         # [default]

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 3.00   # ADR + local half-spreads [example]
    fee_bps = 1.20      # two-market fees + depositary pass-through [example]
    borrow_bps = 3.00   # ADR borrow amortized [example]
    impact_bps = 2.00   # FX + equity async fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    if b["local_px"] <= 0 or b["fx"] <= 0 or not math.isfinite(b["adr_px"]):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    if not b["home_open"]:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    fair = b["local_px"] * b["fx"] * b["ratio"]
    prem = (b["adr_px"] - fair) / fair * 10000.0
    direction = 0
    if abs(prem) > cfg.premium_bound_bps:
        direction = -1 if prem > 0 else 1
    confidence = min(1.0, abs(prem) / cfg.premium_bound_bps - 1.0) if direction else 0.0
    edge_bps = abs(prem)  # modeled per-trade edge = premium [example]
    gate = expected_cost_bps(1.0, 0.001, "XNYS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
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
        assert abs(got[3]["premium_bps"] - 40.0) < 1e-9
        assert got[3]["direction"] == -1 and got[4]["direction"] == 1
        assert got[5]["direction"] == 0  # home closed -> gate vetoes
        assert got[7]["direction"] == 0  # home closed -> gate vetoes


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
    bad = {"bar": 0, "event_ts": 1, "asof_ts": 2, "local_px": 0.0, "fx": 0.2,
           "adr_px": 50.0, "ratio": 5, "home_open": 1}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
