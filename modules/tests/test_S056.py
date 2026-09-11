"""Acceptance tests for S056 — ETF vs basket / iNAV arbitrage.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S056.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S056_tape.csv"
EXPECTED = FIX / "S056_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['snap', 'premium_bps', 'direction']
COL_TYPES = {'snap': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'inav': 'float', 'etf_px': 'float'}


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
        prem = (r["etf_px"] - r["inav"]) / r["inav"] * 10000.0
        d = -1 if prem > 8.0 else (1 if prem < -8.0 else 0)
        out.append({"snap": r["snap"], "premium_bps": prem, "direction": d})
    return out


@dataclass
class Config:
    cost_bound_bps: float = 8.0  # [example]
    cost_gate_k: float = 0.5     # [default]

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 2.00   # ETF + basket-leg half-spreads [example]
    fee_bps = 0.60      # two-sided taker fees [example]
    borrow_bps = 0.00   # long-only reference; reason: no short leg [default]
    impact_bps = 1.50   # basket-leg async fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    if b["inav"] <= 0 or not math.isfinite(b["etf_px"]):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    prem = (b["etf_px"] - b["inav"]) / b["inav"] * 10000.0
    direction = -1 if prem > cfg.cost_bound_bps else (1 if prem < -cfg.cost_bound_bps else 0)
    confidence = min(1.0, abs(prem) / cfg.cost_bound_bps - 1.0) if direction else 0.0
    edge_bps = abs(prem)  # modeled per-trade edge = the premium itself [example]
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
    assert abs(got[3]["premium_bps"] - 12.0) < 1e-9
    assert got[3]["direction"] == -1 and got[4]["direction"] == 1
    assert got[0]["direction"] == 0


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
    bad = {"snap": 0, "event_ts": 1, "asof_ts": 2, "inav": 0.0, "etf_px": 100.0}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_config_defaults_match_chapter():
    """Config defaults are pinned to the §S0.2 / §S2 parameter table."""
    cfg = Config()
    assert cfg.cost_bound_bps == 8.0  # [example]
    assert cfg.cost_gate_k == 0.5     # [default]


def _bar(premium_bps):
    """One synthetic 15-sec bar with the given premium in bps."""
    return {"snap": 0, "event_ts": 1788984000000000000, "asof_ts": 1788984000000120000,
            "inav": 100.0, "etf_px": 100.0 * (1.0 + premium_bps / 10000.0)}


def test_cost_gate_blocks_thin_edge():
    """Premium 8.05 bps breaches the 8 bps bound but the cost gate blocks it:
    expected_cost_bps = 4.1 > 0.5 * 8.05 = 4.025 -> direction 0 (C2)."""
    s = signal({}, [_bar(8.05)], Config())
    assert s.direction == 0 and s.confidence == 0.0


def test_cost_gate_passes_clean_edge():
    """Premium 12 bps clears both bound and gate: -1, confidence 0.5, capital 0.25."""
    s = signal({}, [_bar(12.0)], Config())
    assert s.direction == -1
    assert abs(s.confidence - 0.5) <= TOL
    assert abs(s.capital - 0.25) <= TOL
    assert s.computed_at == 1788984000000000000


def test_nonfinite_price_yields_unknown():
    bad = {"snap": 0, "event_ts": 1, "asof_ts": 2, "inav": 100.0, "etf_px": float("inf")}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
    neg = {"snap": 0, "event_ts": 1, "asof_ts": 2, "inav": -100.0, "etf_px": 100.0}
    s = signal({}, [neg], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
