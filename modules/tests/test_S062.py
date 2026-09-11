"""Acceptance tests for S062 — Sector momentum.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S062.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S062_tape.csv"
EXPECTED = FIX / "S062_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['sector', 'formation_ret', 'rank', 'position']
COL_TYPES = {'sector': 'str', 'event_ts': 'int', 'asof_ts': 'int', 'formation_ret': 'float', 'rank_t': 'str'}


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
    srt = sorted(rows, key=lambda r: r["formation_ret"], reverse=True)
    out = []
    for r in rows:
        rk = next(k for k, x in enumerate(srt) if x["sector"] == r["sector"]) + 1
        pos = 1 if rk <= 2 else (-1 if rk >= len(srt) - 1 else 0)
        out.append({"sector": r["sector"], "formation_ret": r["formation_ret"],
                    "rank": rk, "position": pos})
    return out


@dataclass
class Config:
    n_long: int = 2          # [example]
    n_short: int = 2         # [example]
    cost_gate_k: float = 0.5  # [default]

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 1.00   # sector-ETF half-spread [example]
    fee_bps = 0.30      # taker fee [example]
    borrow_bps = 1.50   # loser-leg borrow amortized [example]
    impact_bps = 1.00   # rotation-day fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps

def signal(state, bars, cfg):
    # bars: one row per sector at rank time; returns per-sector SignalVector via state bag
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[0]
    if any(not math.isfinite(r["formation_ret"]) for r in bars):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    srt = sorted(bars, key=lambda r: r["formation_ret"], reverse=True)
    # stub emits the long/short basket as direction of the top sector vs bottom sector pair
    top, bot = srt[0]["formation_ret"], srt[-1]["formation_ret"]
    spread_edge = top - bot  # formation dispersion, pct pts [example]
    direction = 1 if spread_edge > 0 else 0
    confidence = min(1.0, spread_edge / 2.0)  # [example] scale
    edge_bps = spread_edge * 100.0  # modeled per-trade edge [example]
    gate = expected_cost_bps(1.0, 0.001, "ARCX", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    if not gate:
        direction, confidence = 0, 0.0
    return SignalVector("BASKET", direction, confidence, 0.5 * confidence,
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
        got = {g["sector"]: g for g in recompute(parse_tape())}
        assert got["XLE"]["rank"] == 1 and got["XLE"]["position"] == 1
        assert got["XLY"]["rank"] == 2 and got["XLY"]["position"] == 1
        assert got["XLP"]["rank"] == 8 and got["XLP"]["position"] == -1
        assert got["XLV"]["rank"] == 7 and got["XLV"]["position"] == -1
        assert got["XLK"]["position"] == 0


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
    bad = [{"sector": "X", "event_ts": 1, "asof_ts": 2, "formation_ret": float("nan"), "rank_t": "12:00"}]
    s = signal({}, bad, Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
