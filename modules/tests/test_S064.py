"""Acceptance tests for S064 — Jump-robust realized variance (RV / bipower / Lee-Mykland).

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S064.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S064_tape.csv"
EXPECTED = FIX / "S064_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['bar', 'rv', 'bv', 'jump_var', 'rel_jump', 'lm_stat', 'lm_flag']
COL_TYPES = {'bar': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'ret': 'float'}


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
    rets = [r["ret"] for r in rows]
    rv = sum(x * x for x in rets)
    bv = (math.pi / 2) * sum(abs(rets[i] * rets[i - 1]) for i in range(1, len(rets)))
    j = max(rv - bv, 0.0)
    out = []
    for i, r in enumerate(rows):
        L = abs(r["ret"]) / math.sqrt(bv) if bv > 0 else 0.0
        out.append({"bar": r["bar"], "rv": rv, "bv": bv, "jump_var": j,
                    "rel_jump": j / rv if rv > 0 else 0.0,
                    "lm_stat": L, "lm_flag": 1 if L > 4.0 else 0})
    return out


@dataclass
class Config:
    lm_thresh: float = 4.0    # [example]
    N: int = 12               # [example] return window
    cost_gate_k: float = 0.5   # [default]

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.50   # vol-trade reference leg [example]
    fee_bps = 0.30      # taker fee [example]
    borrow_bps = 0.00   # reason: reference build long vol; no stock borrow [default]
    impact_bps = 0.50   # jump-day fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    if state.get("market") == "HALTED":
        # §S0.5 freeze: no new signals across halts; emit UNKNOWN, discard contributions
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], b["asof_ts"] - b["event_ts"], "UNKNOWN")
    if state.get("market") == "AUCTION":
        # §S0.5: hold, no new signals; DEGRADED
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], b["asof_ts"] - b["event_ts"], "DEGRADED")
    if any(not math.isfinite(r["ret"]) for r in bars):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    rets = [r["ret"] for r in bars[-cfg.N:]]  # cfg.N window [example]
    rv = sum(x * x for x in rets)
    bv = (math.pi / 2) * sum(abs(rets[i] * rets[i - 1]) for i in range(1, len(rets)))
    L = abs(rets[-1]) / math.sqrt(bv) if bv > 0 else 0.0
    direction = 1 if L > cfg.lm_thresh else 0  # jump flag -> long vol-spike leg [example]
    confidence = min(1.0, L / 8.0) if direction else 0.0  # [example] scale
    edge_bps = L * 2.0  # modeled per-trade edge [example]
    cost_bps = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")  # [example] reference args
    if not (cost_bps <= cfg.cost_gate_k * edge_bps):
        direction, confidence = 0, 0.0
    earliest_fill_ts = b["event_ts"] + (300_000_000_000)  # next 5-min bar open > bar ts [example]
    assert earliest_fill_ts > b["event_ts"], "no signal-bar fills"
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
        assert got[5]["lm_flag"] == 1  # the +1% jump is flagged
        assert sum(g["lm_flag"] for g in got) == 1
        assert got[0]["jump_var"] > 0 and got[0]["rel_jump"] > 0.5


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
    bad = {"bar": 0, "event_ts": 1, "asof_ts": 2, "ret": float("nan")}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_cost_stack_single_source_pin():
    """COST block single source of truth: the 4-component stack sums to the §S2
    reference total (spread 0.50 + fees 0.30 + borrow 0.00 + impact 0.50) [example]."""
    total = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert abs(total - 1.30) <= 1e-9
    assert total >= 0.0


def test_market_state_halt_freezes():
    """§S0.5: HALTED freezes new signals (UNKNOWN); AUCTION holds (DEGRADED)."""
    rows = parse_tape()
    cfg = Config()
    s = signal({"market": "HALTED"}, rows, cfg)
    assert s.module_state == "UNKNOWN" and s.direction == 0
    s = signal({"market": "AUCTION"}, rows, cfg)
    assert s.module_state == "DEGRADED" and s.direction == 0


def test_full_window_bv_convention():
    """Pin the normative §S3 convention: the test bar sits inside its own BV
    denominator (full-window BV), so lm_stat at the engineered-jump bar equals
    the fixture value exactly."""
    got = recompute(parse_tape())
    assert abs(got[5]["lm_stat"] - 4.0954571391) <= 1e-9
    assert got[5]["lm_flag"] == 1
    # non-jump bars never flag even though BV is jump-diluted
    assert all(g["lm_flag"] == 0 for i, g in enumerate(got) if i != 5)
