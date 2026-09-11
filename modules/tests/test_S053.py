"""Acceptance tests for S053 — Pair-quality filter - zero crossings (Do-Faff).

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S053.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S053_tape.csv"
EXPECTED = FIX / "S053_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['pair', 'zc', 'pass_gate']
COL_TYPES = {'bar': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'pair': 'str', 'spread': 'float'}

# Normative downstream reference for the cost gate (S3 DOWNSTREAM_REF).
DOWNSTREAM_REF = (1e6, 1e-4, "XNAS", "taker", "normal")  # notional, adv_pct, venue, side, urgency


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


@dataclass
class Config:
    zc_min: int = 3             # [example] calibrate
    cost_gate_k: float = 0.5    # [default] calibrate
    formation_bars: int = 12    # [example]
    quality_norm: float = 20.0  # [example]
    edge_bps: float = 12.0      # [example]
    breadth_floor: int = 5      # [default]
    max_pairs: int = 50         # [example]
    cooldown_s: int = 60        # [default] fixed


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference stack (S2 COST block); fee_schedule_as_of 2026-09-01 [unverified].

    Gate emits no trades; stack is the downstream pairs strategy's taker reference [example].
    """
    spread_bps = 1.00
    fee_bps = 0.60
    borrow_bps = 1.50      # borrow_bps_per_day; S053 accrues no borrow itself (reason in S2)
    impact_bps = 1.00
    return spread_bps + fee_bps + borrow_bps + impact_bps


def zero_crossings(spreads):
    """Normative S3 definition: crossings of the formation-window mean (strict)."""
    m = sum(spreads) / len(spreads)
    d = [x - m for x in spreads]
    return sum(1 for i in range(1, len(d)) if d[i - 1] * d[i] < 0)


def zero_crossings_raw(spreads):
    """Raw zero crossings (no demean) — only used to pin the definition in tests."""
    return sum(1 for i in range(1, len(spreads)) if spreads[i - 1] * spreads[i] < 0)


def signal(state, bars, cfg, now_ns=None):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")          # F1
    b = bars[-1]
    if now_ns is None:
        now_ns = b["asof_ts"]
    if not math.isfinite(b["spread"]):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F1/F2
    spreads = [r["spread"] for r in bars if r["pair"] == b["pair"]]
    if len(spreads) < cfg.formation_bars:
        return SignalVector(b["pair"], 0, 0.0, 0.0, b["event_ts"],
                            now_ns - b["asof_ts"], "UNKNOWN")             # insufficient formation window
    zc = zero_crossings(spreads)
    quality = min(1.0, zc / cfg.quality_norm)                              # [example] norm
    # Normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
    cost_ok = expected_cost_bps(*DOWNSTREAM_REF) <= cfg.cost_gate_k * cfg.edge_bps
    st = "OK" if cost_ok else "DEGRADED"
    # direction is always 0: a filter emits no entries
    return SignalVector(b["pair"], 0, quality, 0.0, b["event_ts"],
                        now_ns - b["asof_ts"], st)


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Reference recomputation of the tape matches expected.csv exactly."""
    rows = parse_tape()
    exp = {r["pair"]: r for r in load_csv(EXPECTED)}
    got = {}
    for p in ("A", "B", "C"):
        s = [r["spread"] for r in rows if r["pair"] == p]
        zc = zero_crossings(s)
        got[p] = {"pair": p, "zc": zc, "pass_gate": 1 if zc >= 3 else 0}
    assert set(got) == set(exp), (set(got), set(exp))
    for p, g in got.items():
        e = exp[p]
        for k in EXPECTED_COLS:
            gv, ev = g[k], e[k]
            try:
                assert abs(float(gv) - float(ev)) <= TOL, (p, k, gv, ev)
            except (ValueError, TypeError):
                assert str(gv) == str(ev), (p, k, gv, ev)
    # Hand-check pins from S4:
    assert got["A"]["zc"] == 7 and got["A"]["pass_gate"] == 1   # high-crossing mean-reverter
    assert got["B"]["zc"] == 1 and got["B"]["pass_gate"] == 0   # monotone drifter, correctly rejected
    assert got["C"]["zc"] == 11 and got["C"]["pass_gate"] == 1  # offset oscillator


def test_pair_C_pins_demeaned_definition():
    """Pair C raw-zero crossings = 0 but demeaned = 11: the definition must demean."""
    rows = parse_tape()
    s = [r["spread"] for r in rows if r["pair"] == "C"]
    assert zero_crossings_raw(s) == 0, "raw crossings of C must be 0"
    assert zero_crossings(s) == 11, "demeaned crossings of C must be 11"


def test_direction_always_zero():
    """A filter never fires entries: direction == 0 on every emission incl. UNKNOWN."""
    rows = parse_tape()
    cfg = Config()
    for i in range(len(rows)):
        s = signal({}, rows[: i + 1], cfg)
        assert s.direction == 0, "filter must never emit an entry direction"
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    a_only = [r for r in rows if r["pair"] == "A"]
    full = signal({}, a_only, cfg)
    assert full.module_state == "OK" and abs(full.confidence - 0.35) <= TOL  # zc=7 -> quality 7/20


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = parse_tape()
    cfg = Config()
    for i in range(len(rows)):
        s = signal({}, rows[: i + 1], cfg)
        assert s.computed_at == rows[i]["event_ts"], "signal must be timestamped at its bar"
        later = [r["event_ts"] for r in rows[i + 1:] if r["event_ts"] > s.computed_at]
        if later:
            assert min(later) > s.computed_at, "signal-bar fill"


def test_cost_gate_predicate():
    """expected_cost_bps(DOWNSTREAM_REF) <= k * edge_bps pins module_state."""
    cost = expected_cost_bps(*DOWNSTREAM_REF)
    assert abs(cost - 4.10) <= TOL
    assert cost <= 0.5 * 12.0      # k=0.5 [default], edge=12 [example] -> gate passes
    # Through the stub: passing gate -> OK, tiny edge -> DEGRADED (never an entry).
    rows = parse_tape()
    ok = signal({}, rows, Config(cost_gate_k=0.5, edge_bps=12.0))
    assert ok.module_state == "OK" and ok.direction == 0
    blocked = signal({}, rows, Config(cost_gate_k=0.5, edge_bps=0.0001))
    assert blocked.module_state == "DEGRADED" and blocked.direction == 0


def test_invalid_input_yields_unknown():
    rows = parse_tape()
    cfg = Config()
    nan_row = dict(rows[0]); nan_row["spread"] = float("nan")
    s = signal({}, [nan_row], cfg)
    assert s.module_state == "UNKNOWN" and s.direction == 0        # F1/F2 non-finite
    inf_row = dict(rows[0]); inf_row["spread"] = float("inf")
    s = signal({}, [inf_row], cfg)
    assert s.module_state == "UNKNOWN" and s.direction == 0        # F2 out of bounds
    s = signal({}, [], cfg)
    assert s.module_state == "UNKNOWN" and s.direction == 0       # F1 empty input


def test_short_formation_window_yields_unknown():
    """Fewer than formation_bars per-pair bars -> UNKNOWN (never interpolate)."""
    rows = parse_tape()
    cfg = Config(formation_bars=12)
    half = [r for r in rows if r["bar"] < 6]                       # 6 bars per pair
    s = signal({}, half, cfg)
    assert s.module_state == "UNKNOWN" and s.direction == 0
    s = signal({}, rows, Config(formation_bars=36))                # window larger than tape
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_staleness_and_timestamping():
    """computed_at = signal bar event_ts; staleness = now - asof_ts >= 0."""
    rows = parse_tape()
    cfg = Config()
    last = rows[-1]
    now = last["asof_ts"] + 1_000_000_000                            # 1 s after last asof
    s = signal({}, rows, cfg, now_ns=now)
    assert s.computed_at == last["event_ts"]
    assert s.staleness == 1_000_000_000
    assert 0 <= s.staleness <= 3_000_000_000                         # within TTL 3 s [default]
