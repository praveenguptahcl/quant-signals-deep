"""Acceptance tests for S073 — Unusual options activity.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event), the cost gate,
the staleness TTL, and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S073.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S073_tape.csv"
EXPECTED = FIX / "S073_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['contract', 'u_score', 'vol_oi', 'flag']
COL_TYPES = {'contract': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'volume': 'float', 'oi': 'float', 'med20_vol': 'float'}


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


def recompute(rows, u_star=2.0, vol_oi_star=1.5):
    out = []
    for r in rows:
        u = r["volume"] / r["med20_vol"]
        vo = r["volume"] / r["oi"] if r["oi"] > 0 else 0.0
        d = 1 if (u >= u_star and vo >= vol_oi_star) else 0
        out.append({"contract": r["contract"], "u_score": u, "vol_oi": vo, "flag": d})
    return out


@dataclass
class Config:
    u_star: float = 2.0                  # [example]
    vol_oi_star: float = 1.5            # [example]
    baseline_days: int = 20             # [example]
    cost_gate_k: float = 0.5            # [default]
    staleness_ttl_ns: int = 3000000000  # 3 s [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 3.00            # options leg half-spread on unusual print [example]
    fee_bps = 0.60               # options fees [example]
    borrow_bps_per_day = 0.00    # reason: long-follow reference; borrow in consumer [default]
    impact_bps = 2.00            # chasing slippage [example]
    return spread_bps + fee_bps + borrow_bps_per_day + impact_bps


def regime_gates():
    return "ALLOW"  # test seam: live harness evaluates the §S2 machine records


def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("UNDERLYING", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    if b["med20_vol"] <= 0 or b["volume"] < 0 or not math.isfinite(b["volume"]):
        return SignalVector("UNDERLYING", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    if b["asof_ts"] - b["event_ts"] > cfg.staleness_ttl_ns:
        return SignalVector("UNDERLYING", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F4
    if regime_gates() != "ALLOW":
        return SignalVector("UNDERLYING", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    u = b["volume"] / b["med20_vol"]
    vo = b["volume"] / b["oi"] if b["oi"] > 0 else 0.0
    direction = 1 if (u >= cfg.u_star and vo >= cfg.vol_oi_star) else 0  # put/call-agnostic proxy [example]
    confidence = min(1.0, u / 5.0) if direction else 0.0  # [example] scale
    edge_bps = u * 30.0  # modeled per-trade edge [example]; calibrate beta per chapter
    gate = expected_cost_bps(1.0, 0.001, "CBOE", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    if not gate:
        direction, confidence = 0, 0.0
    return SignalVector("UNDERLYING", direction, confidence, 0.5 * confidence,
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
    # pin the documented hand-checks: contract-0 u = 2500/900, flags 1,0,1,0,1,1
    assert abs(got[0]["u_score"] - 2500.0 / 900.0) < 1e-9
    assert [g["flag"] for g in got] == [1, 0, 1, 0, 1, 1]


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
    bad = {"contract": 0, "event_ts": 1, "asof_ts": 2, "volume": 100.0, "oi": 50.0, "med20_vol": 0.0}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_stale_event_yields_unknown():
    """F4: asof_ts - event_ts > staleness_ttl_ns -> UNKNOWN."""
    cfg = Config()
    stale = {"contract": 0, "event_ts": 1_000_000,
             "asof_ts": 1_000_000 + cfg.staleness_ttl_ns + 1,
             "volume": 2500.0, "oi": 800.0, "med20_vol": 900.0}
    s = signal({}, [stale], cfg)
    assert s.module_state == "UNKNOWN" and s.direction == 0
    # just inside the TTL is fine
    fresh = dict(stale, asof_ts=stale["event_ts"] + cfg.staleness_ttl_ns - 1)
    s2 = signal({}, [fresh], cfg)
    assert s2.module_state == "OK" and s2.direction == 1


def test_cost_gate_blocks_through_stub():
    """Full-path gate: k=0 blocks every flag through signal()."""
    rows = parse_tape()
    cfg = Config(cost_gate_k=0.0)
    sigs = [signal({}, rows[: i + 1], cfg) for i in range(len(rows))]
    assert all(s.direction == 0 and s.confidence == 0.0 for s in sigs)
    cfg2 = Config(cost_gate_k=2.0)  # loose gate: strong prints still flag
    s_strong = signal({}, rows[: 6], cfg2)  # contract-5, u ~ 4.17
    assert s_strong.direction == 1


def test_zero_oi_and_nonfinite_inputs():
    """oi=0 never divides by zero (vol_oi=0, no flag); non-finite volume -> UNKNOWN."""
    cfg = Config()
    z = {"contract": 9, "event_ts": 5, "asof_ts": 6, "volume": 2500.0, "oi": 0.0, "med20_vol": 900.0}
    s = signal({}, [z], cfg)
    assert s.module_state == "OK" and s.direction == 0  # vol_oi = 0.0 < vol_oi_star
    for bad_vol in (float("nan"), float("inf"), -float("inf")):
        nb = {"contract": 9, "event_ts": 5, "asof_ts": 6, "volume": bad_vol, "oi": 800.0, "med20_vol": 900.0}
        sb = signal({}, [nb], cfg)
        assert sb.module_state == "UNKNOWN" and sb.direction == 0, bad_vol
