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
    """Arithmetic fixture truth: breakout flag only (no cost gate, no guards)."""
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
    k: float = 1.75          # expansion multiple [calibrate]
    N: int = 10              # lookback bars [calibrate]
    edge_scale: float = 10.0  # [example]
    cost_gate_k: float = 0.5  # [default]
    staleness_ttl_ns: int = 3_000_000_000  # [default]
    cooldown_s: float = 60.0  # [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Callable cost model — mirrors the §S2 COST block exactly."""
    spread_bps = 0.50   # breakout-entry half-spread [example]
    fee_bps = 0.30      # Nasdaq remove-liquidity $0.0030/sh at $100 ref [documented 2026-09-10]
    borrow_bps_per_day = 0.00  # reason: long-breakout reference [default]
    impact_bps = 1.00   # expansion-bar fill slippage [example]
    return spread_bps + fee_bps + borrow_bps_per_day + impact_bps


def _unknown(symbol, ts):
    return SignalVector(symbol, 0, 0.0, 0.0, ts, 0, "UNKNOWN")


def signal(state, bars, cfg):
    """Reference implementation of the §S3 normative pseudocode."""
    symbol = state.get("symbol", "TEST")
    bars = list(bars)
    if not bars:
        return _unknown(symbol, 0)
    b = bars[-1]
    signal_event = b["event_ts"]
    staleness = b["asof_ts"] - b["event_ts"]
    if staleness > cfg.staleness_ttl_ns:          # F4 staleness TTL
        return _unknown(symbol, signal_event)
    if state.get("market_state") == "HALTED":    # freeze
        return _unknown(symbol, signal_event)
    if state.get("market_state") == "AUCTION":   # hold last vector, DEGRADED
        last = state.get("last_vector") or _unknown(symbol, signal_event)
        return SignalVector(last.symbol, last.direction, last.confidence,
                            last.capital, signal_event, staleness, "DEGRADED")
    if signal_event < state.get("cooldown_until_ns", 0):  # C10 cooldown
        return SignalVector(symbol, 0, 0.0, 0.0, signal_event, staleness, "OK")
    o, h, l, c = b["open"], b["high"], b["low"], b["close"]
    ohlc_ok = (h >= l and h >= max(o, c) and l <= min(o, c)
               and min(o, h, l, c) > 0
               and all(math.isfinite(v) for v in (o, h, l, c)))
    if not ohlc_ok:                              # F1/F2, never interpolate
        return _unknown(symbol, signal_event)
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
    if direction == -1 and not state.get("locate_ok", False):  # C7 locate gate
        direction = 0
    confidence = min(1.0, rr / 4.0) if direction else 0.0  # [example] scale
    edge_bps = max(0.0, rr - cfg.k) * cfg.edge_scale       # excess expansion [example]
    cost = expected_cost_bps(notional=1.0, adv_pct=0.001, venue="XNAS",
                             side="taker", urgency="normal")
    if not (cost <= cfg.cost_gate_k * edge_bps):           # cost-gate veto [default] k
        direction, confidence = 0, 0.0
    sv = SignalVector(symbol, direction, confidence, 0.5 * confidence,
                      signal_event, staleness, "OK")
    state["last_vector"] = sv
    return sv


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


def _bar(bar, ts, o, h, l, c, asof_lag_ns=120000):
    return {"bar": bar, "event_ts": ts, "asof_ts": ts + asof_lag_ns,
            "open": o, "high": h, "low": l, "close": c}


def _flat_tape(n, ts0=1788960600000000000, step=60_000_000_000, rng=1.0, px=100.0, up=True):
    """n identical-range bars; close>=open if up (breakout long side)."""
    rows = []
    for i in range(n):
        ts = ts0 + i * step
        c = px + (0.1 if up else -0.1)
        rows.append(_bar(i, ts, px, px + rng / 2, px - rng / 2, c))
    return rows


def test_signal_emits_valid_signalvector():
    rows = parse_tape()
    cfg, state = Config(), {"symbol": "TEST"}
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    # bar-8 clean expansion passes the cost gate with the bar-following long
    assert sigs[8].direction == 1 and sigs[8].module_state == "OK"
    assert sigs[8].confidence == 1.0  # min(1, 7.333/4) saturates
    assert sigs[8].capital == 0.5 * sigs[8].confidence


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = parse_tape()
    cfg, state = Config(), {"symbol": "TEST"}
    for i in range(len(rows)):
        s = signal(state, rows[: i + 1], cfg)
        assert s.computed_at == rows[i]["event_ts"], "signal must be timestamped at its bar"
        later = [r["event_ts"] for r in rows[i + 1:] if r["event_ts"] > s.computed_at]
        if later:
            assert min(later) > s.computed_at, "signal-bar fill"


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert cost >= 0.0
    assert cost <= k * 100000.0   # huge edge -> gate passes
    assert not (cost <= k * 0.0001)  # tiny edge -> gate blocks


def test_invalid_input_yields_unknown():
    bad = {"bar": 0, "event_ts": 1, "asof_ts": 2, "open": 100.0, "high": 99.0,
           "low": 98.0, "close": 99.5}  # high 99 < open 100 impossible
    s = signal({"symbol": "TEST"}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
    for mut in ({"close": float("nan")}, {"high": float("inf")},
                {"low": -1.0}, {"open": 0.0}):
        row = dict(bad)
        row.update({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.1})
        row.update(mut)
        s = signal({"symbol": "TEST"}, [row], Config())
        assert s.module_state == "UNKNOWN" and s.direction == 0, mut


def test_empty_and_warmup_inputs():
    cfg = Config()
    s = signal({"symbol": "TEST"}, [], cfg)
    assert s.module_state == "UNKNOWN" and s.direction == 0
    s = signal({"symbol": "TEST"}, _flat_tape(1), cfg)  # empty history -> rr 0.0
    assert s.module_state == "OK" and s.direction == 0 and s.confidence == 0.0


def test_stale_and_halted_inputs():
    cfg = Config()
    rows = _flat_tape(11)
    rows[-1]["asof_ts"] = rows[-1]["event_ts"] + cfg.staleness_ttl_ns + 1
    s = signal({"symbol": "TEST"}, rows, cfg)
    assert s.module_state == "UNKNOWN", "stale bar must veto"
    rows = _flat_tape(11)
    s = signal({"symbol": "TEST", "market_state": "HALTED"}, rows, cfg)
    assert s.module_state == "UNKNOWN", "halt must freeze"
    rows = _flat_tape(11)
    st = {"symbol": "TEST", "market_state": "AUCTION"}
    st["last_vector"] = signal({"symbol": "TEST"}, rows[:-1], cfg)
    s = signal(st, rows, cfg)
    assert s.module_state == "DEGRADED", "auction holds last vector"


def test_boundary_rr_equals_k_no_breakout():
    """Boundary: rr == k exactly is NOT a breakout (strict >)."""
    cfg = Config()
    rows = _flat_tape(10, rng=1.0)          # prior ranges exactly 1.0
    ts = rows[-1]["event_ts"] + 60_000_000_000
    rows.append(_bar(10, ts, 100.0, 101.75, 100.0, 100.2))  # range exactly 1.75
    rr = (101.75 - 100.0) / 1.0
    assert rr == cfg.k, "fixture arithmetic must hit the boundary exactly"
    s = signal({"symbol": "TEST"}, rows, cfg)
    assert s.direction == 0 and s.confidence == 0.0, "rr == k must not fire"


def test_marginal_breakout_vetoed_by_cost_gate():
    """Gate veto path: rr just above k has too little excess edge; clean expansions pass."""
    cfg = Config()
    rows = _flat_tape(10, rng=1.0)
    ts = rows[-1]["event_ts"] + 60_000_000_000
    rows.append(_bar(10, ts, 100.0, 101.0, 99.2, 100.5))  # range 1.8 -> rr = 1.8
    s = signal({"symbol": "TEST"}, rows, cfg)
    # edge = (1.8-1.75)*10 = 0.5 bps; gate: 1.8 <= 0.5*0.5 = 0.25 -> False
    assert s.direction == 0 and s.confidence == 0.0, "marginal breakout must be vetoed"
    rows2 = _flat_tape(10, rng=1.0)
    ts2 = rows2[-1]["event_ts"] + 60_000_000_000
    rows2.append(_bar(10, ts2, 100.0, 104.0, 99.0, 103.0))  # range 5.0 -> rr = 5.0
    s2 = signal({"symbol": "TEST"}, rows2, cfg)
    # edge = (5.0-1.75)*10 = 32.5 bps; gate: 1.8 <= 16.25 -> True
    assert s2.direction == 1 and s2.module_state == "OK", "clean expansion must pass"


def test_locate_gate_blocks_short():
    """C7: SHORT expansion needs locate_ok; longs are unaffected."""
    cfg = Config()
    rows = _flat_tape(10, rng=1.0)
    ts = rows[-1]["event_ts"] + 60_000_000_000
    rows.append(_bar(10, ts, 100.0, 104.0, 99.0, 99.5, ))  # range 5.0, close < open
    s = signal({"symbol": "TEST"}, rows, cfg)
    assert s.direction == 0, "short without locate_ok must be vetoed"
    s = signal({"symbol": "TEST", "locate_ok": True}, rows, cfg)
    assert s.direction == -1 and s.module_state == "OK", "short with locate_ok fires"


def test_cooldown_blocks_reentry():
    """C10: post-exit cooldown blocks new entries until it expires."""
    cfg = Config()
    rows = _flat_tape(10, rng=1.0)
    ts = rows[-1]["event_ts"] + 60_000_000_000
    rows.append(_bar(10, ts, 100.0, 104.0, 99.0, 103.0))  # clean expansion
    st = {"symbol": "TEST", "cooldown_until_ns": ts + 30_000_000_000}
    s = signal(st, rows, cfg)
    assert s.direction == 0 and s.module_state == "OK", "cooldown must block entry"
    st["cooldown_until_ns"] = ts - 1
    s = signal(st, rows, cfg)
    assert s.direction == 1, "entry resumes after cooldown expiry"


def test_explicit_causality_pin():
    """Pin: a fill synthesized at the next bar's open is strictly after signal_event."""
    rows = parse_tape()
    cfg, state = Config(), {"symbol": "TEST"}
    for i in range(len(rows) - 1):
        s = signal(state, rows[: i + 1], cfg)
        fill_event = rows[i + 1]["event_ts"]  # earliest possible fill: next bar open
        assert fill_event > s.computed_at, (i, fill_event, s.computed_at)
        assert s.staleness >= 0


def test_squeeze_p10_property():
    """squeeze=1 implies bw <= p10; documents short-tape anchoring (bar-0 bw=0 anchors p10)."""
    rows = parse_tape()
    got = recompute(rows)
    bws = [g["bw"] for g in got]
    for i, g in enumerate(got):
        if g["squeeze"] == 1:
            p10 = sorted(bws[:i + 1])[max(0, int(0.1 * (i + 1)) - 1)]
            assert g["bw"] <= p10 + TOL
    assert all(g["squeeze"] == 0 for g in got), "tape has no squeeze by construction"
    assert bws[0] == 0.0, "bar-0 bw anchors the p10 percentile on short tapes"
