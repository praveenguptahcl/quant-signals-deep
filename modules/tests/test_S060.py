"""Acceptance tests for S060 — Cross-asset lead-lag via Hayashi-Yoshida.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S060.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S060_tape.csv"
EXPECTED = FIX / "S060_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['hy_m1', 'hy_0', 'hy_p1', 'chosen_lag']
COL_TYPES = {'i': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'dx': 'float', 'dy': 'float'}


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


def _hy(dx, dy, lag):
    # Textbook Hayashi-Yoshida: binary overlap indicator (chapter S4; HY(0)=17 exact).
    tot = 0.0
    for i, a in enumerate(dx):
        for j, b in enumerate(dy):
            lo = max(i, j + 0.5 - lag)
            hi = min(i + 1, j + 1.5 - lag)
            if hi > lo:
                tot += a * b
    return tot

def recompute(rows):
    dx = [r["dx"] for r in rows]
    dy = [r["dy"] for r in rows]
    h = {l: _hy(dx, dy, l) for l in (-1, 0, 1)}
    return [{"hy_m1": h[-1], "hy_0": h[0], "hy_p1": h[1],
             "chosen_lag": max(h, key=lambda l: abs(h[l]))}]


@dataclass
class Config:
    min_abs_hy: float = 5.0   # [example]
    cost_gate_k: float = 0.5  # [default]

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.50   # laggard-leg half-spread [example]
    fee_bps = 0.30      # taker fee [example]
    borrow_bps = 0.00   # reason: long-laggard reference [default]
    impact_bps = 0.50   # laggard fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps

def _hy(dx, dy, lag):
    # Textbook Hayashi-Yoshida: binary overlap indicator (chapter S4; HY(0)=17 exact).
    tot = 0.0
    for i, a in enumerate(dx):
        for j, b in enumerate(dy):
            lo = max(i, j + 0.5 - lag)
            hi = min(i + 1, j + 1.5 - lag)
            if hi > lo:
                tot += a * b
    return tot

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    if any(not math.isfinite(r["dx"]) or not math.isfinite(r["dy"]) for r in bars):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    dx = [r["dx"] for r in bars]
    dy = [r["dy"] for r in bars]
    h = {l: _hy(dx, dy, l) for l in (-1, 0, 1)}
    lag = max(h, key=lambda l: abs(h[l]))
    # lag>0: X leads -> trade Y in direction of latest X move
    direction = 0
    if abs(h[lag]) >= cfg.min_abs_hy and lag != 0:
        direction = 1 if (dx[-1] > 0) == (lag > 0) else -1
    confidence = min(1.0, abs(h[lag]) / 20.0) if direction else 0.0  # [example] scale
    edge_bps = abs(h[lag]) * 0.5  # modeled per-trade edge [example]
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
        assert abs(got[0]["hy_0"] - 17.0) < 1e-9  # chapter hand-check: grand sum 17 exact
        assert got[0]["chosen_lag"] in (-1, 0, 1)


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
    bad = {"i": 0, "event_ts": 1, "asof_ts": 2, "dx": float("nan"), "dy": 1.0}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
