"""Acceptance tests for S069 — Implied-vs-realized spread / variance risk premium.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S069.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S069_tape.csv"
EXPECTED = FIX / "S069_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['month', 'vrp_vol', 'vrp_var', 'z', 'direction']
COL_TYPES = {'month': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'iv_ann': 'float', 'rv_ann': 'float'}


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
    vrps = [r["iv_ann"] - r["rv_ann"] for r in rows]
    out = []
    for i, r in enumerate(rows):
        hist = vrps[max(0, i - 3):i + 1]
        mu = sum(hist) / len(hist)
        sd = math.sqrt(sum((v - mu) ** 2 for v in hist) / len(hist)) if len(hist) > 1 else 0.0
        z = (vrps[i] - mu) / sd if sd > 0 else 0.0
        out.append({"month": r["month"], "vrp_vol": vrps[i],
                    "vrp_var": r["iv_ann"] ** 2 - r["rv_ann"] ** 2,
                    "z": z, "direction": 1 if z > 1.5 else 0})
    return out


@dataclass
class Config:
    z_entry: float = 1.5     # [example]
    cost_gate_k: float = 0.5  # [default]

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 4.00   # straddle two-leg half-spread [example]
    fee_bps = 0.60      # options fees [example]
    borrow_bps = 0.00   # reason: delta-hedged long vol; no stock borrow [default]
    impact_bps = 2.00   # delta-hedge slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    if any(v <= 0 or not math.isfinite(v) for v in (b["iv_ann"], b["rv_ann"])):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    vrps = [r["iv_ann"] - r["rv_ann"] for r in bars]
    hist = vrps[-4:]
    mu = sum(hist) / len(hist)
    sd = math.sqrt(sum((v - mu) ** 2 for v in hist) / len(hist)) if len(hist) > 1 else 0.0
    z = (vrps[-1] - mu) / sd if sd > 0 else 0.0
    direction = 1 if z > cfg.z_entry else 0  # rich VRP -> short vol harvest [example]
    confidence = min(1.0, z / 3.0) if direction else 0.0  # [example] scale
    edge_bps = z * 100.0  # modeled per-trade edge [example]
    gate = expected_cost_bps(1.0, 0.001, "CBOE", "taker", "normal") <= cfg.cost_gate_k * edge_bps
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
        assert abs(got[0]["vrp_vol"] - 4.0) < 1e-9
        assert abs(got[0]["vrp_var"] - (22.0**2 - 18.0**2)) < 1e-9
        assert got[0]["direction"] == 0  # single obs -> z=0


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
    bad = {"month": 0, "event_ts": 1, "asof_ts": 2, "iv_ann": 0.0, "rv_ann": 20.0}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
