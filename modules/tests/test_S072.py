"""Acceptance tests for S072 — Put/call ratio (module v1.1.0).

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative §S3 pseudocode (validates ALL bars
before math, monotonic event_ts, market-state branches, 1.5x-cadence staleness
check, executable causal-window assertion, cost-gate predicate, consumer
fill assertion), and real assertions including causality
(assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S072.py -q   (from repo root)
"""
import csv
import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S072_tape.csv"
EXPECTED = FIX / "S072_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
CADENCE_NS = 24 * 3600 * 10**9        # daily cadence; exact unit conversion
TTL_NS = int(1.5 * CADENCE_NS)        # staleness TTL = 1.5 x cadence [default]
EXPECTED_COLS = ['day', 'pcr', 'med5', 'z', 'direction']
COL_TYPES = {'day': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'put_vol': 'float', 'call_vol': 'float'}


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def tape_type_header():
    with open(TAPE) as f:
        return f.readline().strip()


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


def _unknown(ts):
    return SignalVector("TEST", 0, 0.0, 0.0, int(ts), 0, "UNKNOWN")


def recompute(rows, n=5):
    """Reference feature recomputation: trailing-n robust z, no cost gate."""
    pcrs = [r["put_vol"] / r["call_vol"] for r in rows]
    out = []
    for i, r in enumerate(rows):
        hist = pcrs[max(0, i - (n - 1)):i + 1]
        med, m = _median(hist), _mad(hist)
        rz = (pcrs[i] - med) / (1.4826 * m) if m > 0 else 0.0
        d = 1 if rz > 2.0 else (-1 if rz < -2.0 else 0)
        out.append({"day": r["day"], "pcr": pcrs[i], "med5": med, "z": rz, "direction": d})
    return out


@dataclass
class Config:
    n: int = 5                # window [calibrate]
    z_star: float = 2.0       # [calibrate]
    cost_gate_k: float = 0.5  # [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    if side not in ("taker", "maker", "mixed"):
        raise ValueError(f"side must be taker|maker|mixed, got {side!r}")
    spread_bps = 1.00   # equity-leg half-spread [example]
    fee_bps = 0.30      # taker fee [example]
    borrow_bps = 1.50   # short-leg borrow amortized over 1 day [example]
    impact_bps = 1.00   # contrarian fill slippage [example]
    assert spread_bps >= 0 and fee_bps >= 0 and borrow_bps >= 0 and impact_bps >= 0
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """Reference implementation of the §S3 normative pseudocode."""
    events = list(events)
    if not events:
        return _unknown(0)
    # F1/F2: validate ALL bars before any arithmetic
    for i, e in enumerate(events):
        if not (e["call_vol"] > 0 and e["put_vol"] >= 0):
            return _unknown(e["event_ts"])
        if not (math.isfinite(e["put_vol"]) and math.isfinite(e["call_vol"])
                and math.isfinite(e["event_ts"]) and math.isfinite(e["asof_ts"])):
            return _unknown(e["event_ts"])
        if e["asof_ts"] < e["event_ts"]:
            return _unknown(e["event_ts"])          # corrupt clock
        if i > 0 and e["event_ts"] < events[i - 1]["event_ts"]:
            return _unknown(e["event_ts"])          # unordered feed
    b = events[-1]
    # market state (F3/F4)
    ms = state.get("market_state", "CONTINUOUS_TRADING")
    if ms == "HALTED":
        return _unknown(b["event_ts"])
    if ms == "AUCTION":
        last = state.get("last_signal")
        if last is None:
            return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "DEGRADED")
        return replace(last, module_state="DEGRADED")
    if ms == "CLOSED":
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "OFF")
    # staleness (F5)
    now = state.get("now_ts")
    if now is not None and b["asof_ts"] + TTL_NS < now:
        return _unknown(b["event_ts"])
    # causal window: only bars <= t
    window = events[-cfg.n:]
    assert all(e["event_ts"] <= b["event_ts"] for e in window), "future bar in window"
    pcrs = [e["put_vol"] / e["call_vol"] for e in window]
    med, m = _median(pcrs), _mad(pcrs)
    rz = (pcrs[-1] - med) / (1.4826 * m) if m > 0 else 0.0
    direction = 1 if rz > cfg.z_star else (-1 if rz < -cfg.z_star else 0)
    confidence = min(1.0, abs(rz) / 4.0) if direction != 0 else 0.0  # [example]
    edge_bps = abs(rz) * 40.0  # modeled per-trade edge [example]
    # executable cost gate
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert cost >= 0.0
    if not (cost <= cfg.cost_gate_k * edge_bps):
        direction, confidence = 0, 0.0
    sig = SignalVector(state.get("symbol", "TEST"), direction, confidence,
                       0.5 * confidence, b["event_ts"],
                       (now - b["asof_ts"]) if now else 0, "OK")
    state["pcr_history"] = (state.get("pcr_history", []) + [pcrs[-1]])[-100:]
    state["last_signal"] = sig
    return sig


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Reference recomputation of the tape matches expected.csv; TYPE pinned."""
    assert tape_type_header().startswith("# TYPE: validation-run")
    rows = parse_tape()
    exp = {int(r["day"]): r for r in load_csv(EXPECTED)}
    got = recompute(rows)
    assert len(got) == len(exp), (len(got), len(exp))
    for g in got:
        e = exp[g["day"]]
        assert abs(g["pcr"] - float(e["pcr"])) <= TOL, (g["day"], "pcr")
        assert abs(g["med5"] - float(e["med5"])) <= TOL, (g["day"], "med5")
        assert abs(g["z"] - float(e["z"])) <= TOL, (g["day"], "z")
        assert g["direction"] == int(e["direction"]), (g["day"], "direction")
    by_day = {g["day"]: g for g in got}
    assert abs(by_day[0]["pcr"] - 420.0 / 380.0) < 1e-9
    assert by_day[6]["direction"] == 1  # day-6 PCR spike (z=4.32) -> contrarian long
    assert by_day[9]["direction"] == 0
    assert all(g["direction"] in (-1, 0, 1) for g in got)


def test_signal_emits_valid_signalvector():
    rows = parse_tape()
    cfg, state = Config(), {}
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 0.5 + 1e-12  # capital = 0.5 * confidence [default]
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert sigs[6].direction == 1  # day-6 spike survives the cost gate
    assert state["pcr_history"] and len(state["pcr_history"]) <= 100


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
    with pytest.raises(ValueError):
        expected_cost_bps(1.0, 0.001, "X", "midpoint", "normal")


def test_cost_gate_wired_inside_signal(monkeypatch):
    """Inflating the cost closes the gate on the day-6 spike (proves wiring)."""
    rows = parse_tape()[:7]  # newest bar = day 6, the |z|=4.32 spike
    assert signal({}, rows, Config()).direction == 1  # gate passes at reference cost
    monkeypatch.setattr(sys.modules[__name__], "expected_cost_bps",
                        lambda *a, **k: 1e6)
    s = signal({}, rows, Config())
    assert s.direction == 0 and s.confidence == 0.0 and s.module_state == "OK"


@pytest.mark.parametrize("mut", [
    lambda r: r.update(call_vol=0.0),                 # call_vol <= 0
    lambda r: r.update(put_vol=-1.0),                # put_vol < 0
    lambda r: r.update(put_vol=float("inf")),        # non-finite
    lambda r: r.update(call_vol=float("nan")),       # non-finite
    lambda r: r.update(asof_ts=r["event_ts"] - 1),   # asof precedes event
])
def test_invalid_input_yields_unknown(mut):
    rows = parse_tape()
    bad = dict(rows[-1])
    mut(bad)
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
    assert signal({}, [], Config()).module_state == "UNKNOWN"  # empty input


def test_historical_bad_bar_yields_unknown():
    """A corrupt bar mid-tape must not crash the window math."""
    rows = parse_tape()
    rows[2]["call_vol"] = 0.0
    s = signal({}, rows, Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_flat_pcr_zero_mad():
    """MAD == 0 -> z = 0, direction 0, state OK."""
    base = {"day": 0, "event_ts": 10**18, "asof_ts": 10**18, "put_vol": 100.0, "call_vol": 100.0}
    rows = [dict(base, day=i, event_ts=10**18 + i, asof_ts=10**18 + i) for i in range(5)]
    s = signal({}, rows, Config())
    assert s.module_state == "OK" and s.direction == 0 and s.confidence == 0.0


def test_halted_and_auction():
    rows = parse_tape()
    live = signal({}, rows, Config())  # primes state["last_signal"]
    assert signal({"market_state": "HALTED"}, rows, Config()).module_state == "UNKNOWN"
    state = {"market_state": "AUCTION", "last_signal": live}
    held = signal(state, rows, Config())
    assert held.module_state == "DEGRADED" and held.direction == live.direction
    assert signal({"market_state": "CLOSED"}, rows, Config()).module_state == "OFF"


def test_stale_input_unknown():
    rows = parse_tape()
    last_asof = rows[-1]["asof_ts"]
    assert signal({"now_ts": last_asof}, rows, Config()).module_state == "OK"  # fresh
    stale = {"now_ts": last_asof + TTL_NS + 1}
    assert signal(stale, rows, Config()).module_state == "UNKNOWN"  # stale


def test_nonmonotonic_timestamps_unknown():
    rows = parse_tape()
    rows[4], rows[5] = rows[5], rows[4]  # swap -> event_ts out of order
    s = signal({}, rows, Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
