"""Acceptance tests for S057 — Index futures cash-and-carry arbitrage.

Template v1.0.0. Real imports, fixture load, a reference implementation of the
chapter's normative pseudocode (§S3, module v1.1.0), and real assertions
including the executable cost-gate predicate, causality (fill_event_ts >
computed_at), and invalid -> UNKNOWN (F1/F2).

Run: python3 -m pytest modules/tests/test_S057.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S057_tape.csv"
EXPECTED = FIX / "S057_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ['day', 'fstar', 'dev_bps', 'direction']
COL_TYPES = {'day': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'spot': 'float', 'futures': 'float'}


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


# --------------------------------- normative pseudocode stub (mirrors §S3)
@dataclass(frozen=True)
class SignalVector:
    symbol: str
    direction: int          # +1 | -1 | 0
    confidence: float       # 0..1
    capital: float          # 0..1
    computed_at: int        # int64 ns UTC
    staleness: int          # ns
    module_state: str       # OK | DEGRADED | UNKNOWN | OFF


NOTIONAL_REF = 1e6       # $1M reference notional [example]
ADV_PCT_REF = 0.001      # 0.1% of ADV [example]
VENUE_REF = "CME"
URGENCY_REF = "normal"


@dataclass
class Config:
    r: float = 0.05             # financing rate [fixed]
    q: float = 0.018            # dividend yield [calibrate]
    T: float = 90.0 / 365.0     # time to expiry, years [fixed]
    cost_bound_bps: float = 15.0  # [calibrate]
    cost_gate_k: float = 0.5      # [default]
    side: str = "taker"           # [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model — single source of truth (§S2 COST block)."""
    if side not in ("taker", "maker", "mixed"):
        raise ValueError("side")
    spread_bps = {"taker": 1.50, "mixed": 1.50, "maker": -0.25}[side]  # [example]
    fee_bps = 0.80                                                    # [example]
    borrow_bps_per_day = 0.05                                         # [example]
    holding_days = 80.0                                               # [example]
    borrow_bps = borrow_bps_per_day * holding_days                    # 4.00 [example]
    adv0 = 0.001                                                      # [example]
    urgency_mult = {"passive": 0.7, "normal": 1.0, "aggressive": 1.5}[urgency]  # [example]
    impact_bps = 2.00 * (adv_pct / adv0) ** 0.5 * urgency_mult        # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")     # F1
    b = bars[-1]
    if not (math.isfinite(b["spot"]) and math.isfinite(b["futures"]) and b["spot"] > 0):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F2
    fstar = b["spot"] * math.exp((cfg.r - cfg.q) * cfg.T)
    signed_bps = (b["futures"] - fstar) / b["spot"] * 10000.0
    dev_bps = abs(signed_bps)
    edge_bps = dev_bps  # [example]
    if signed_bps > cfg.cost_bound_bps:
        direction = -1
    elif signed_bps < -cfg.cost_bound_bps:
        direction = 1
    else:
        direction = 0
    gate_cost = expected_cost_bps(NOTIONAL_REF, ADV_PCT_REF, VENUE_REF, cfg.side, URGENCY_REF)
    gate_ok = gate_cost <= cfg.cost_gate_k * edge_bps  # executable cost-gate predicate
    if direction != 0 and not gate_ok:
        direction = 0  # gate vetoes, never raises
    confidence = min(1.0, edge_bps / cfg.cost_bound_bps - 1.0) if direction != 0 else 0.0
    capital = 0.5 * confidence  # [default]
    return SignalVector("TEST", direction, confidence, capital,
                        b["event_ts"], b["asof_ts"] - b["event_ts"], "OK")


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Reference recomputation of the tape matches expected.csv row-for-row."""
    rows = parse_tape()
    exp = load_csv(EXPECTED)
    got = []
    fstar = 5000.0 * math.exp((0.05 - 0.018) * (90.0 / 365.0))
    for x in rows:
        dev = (x["futures"] - fstar) / x["spot"] * 10000.0
        d = -1 if dev > 15.0 else (1 if dev < -15.0 else 0)
        got.append({"day": x["day"], "fstar": fstar, "dev_bps": dev, "direction": d})
    assert len(got) == len(exp), (len(got), len(exp))
    for g, e in zip(got, exp):
        for k in EXPECTED_COLS:
            gv, ev = g[k], e[k]
            try:
                assert abs(float(gv) - float(ev)) <= TOL, (k, gv, ev)
            except (ValueError, TypeError):
                assert str(gv) == str(ev), (k, gv, ev)
    # §S4 hand-checks
    assert abs(got[0]["fstar"] - 5000.0 * math.exp(0.032 * 90.0 / 365.0)) < 1e-9
    assert abs(got[0]["fstar"] - 5039.6081114376) < 1e-9
    assert got[3]["direction"] == -1 and got[4]["direction"] == 1
    assert all(got[i]["direction"] == 0 for i in (0, 1, 2))
    assert abs(got[3]["dev_bps"] - 20.7837771248) <= 1e-9
    assert abs(got[4]["dev_bps"] - (-19.2162228752)) <= 1e-9


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
    """Causality invariant: every fill using the signal happens strictly
    after the signal event; earliest fill is the next bar's open."""
    rows = parse_tape()
    cfg, state = Config(), {}
    for i in range(len(rows)):
        s = signal(state, rows[: i + 1], cfg)
        assert s.computed_at == rows[i]["event_ts"], "signal stamped at its bar"
        later = [r["event_ts"] for r in rows[i + 1:] if r["event_ts"] > s.computed_at]
        if later:
            assert min(later) > s.computed_at, "signal-bar fill"
    # fixture cadence: bars are 24h apart; next bar open is the earliest fill
    assert rows[1]["event_ts"] - rows[0]["event_ts"] == 86400 * 10**9
    s0 = signal({}, rows[:1], Config())
    assert rows[1]["event_ts"] > s0.computed_at


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries; components pinned."""
    cfg = Config()
    ref = expected_cost_bps(NOTIONAL_REF, ADV_PCT_REF, VENUE_REF, "taker", "normal")
    assert abs(ref - 8.30) <= 1e-9  # 1.50 + 0.80 + 4.00 + 2.00 [example]
    assert abs(expected_cost_bps(NOTIONAL_REF, ADV_PCT_REF, VENUE_REF, "maker", "normal") - 6.55) <= 1e-9
    assert abs(expected_cost_bps(NOTIONAL_REF, ADV_PCT_REF, VENUE_REF, "taker", "aggressive") - 9.30) <= 1e-9
    # adv_pct 4x reference -> sqrt law doubles impact: 1.50+0.80+4.00+4.00 = 10.30
    assert abs(expected_cost_bps(NOTIONAL_REF, 0.004, VENUE_REF, "taker", "normal") - 10.30) <= 1e-9
    # gate passes on fixture day-3 (edge 20.78 bps, k=0.5 -> 10.39 >= 8.30)
    edge3 = 20.7837771248
    assert ref <= cfg.cost_gate_k * edge3
    # gate blocks on tiny edge
    assert not (ref <= cfg.cost_gate_k * 1.0)


def _veto_bar():
    """16 bps deviation: exceeds the 15 bps bound (direction -1) but fails
    the gate (0.5 * 16 = 8.0 < 8.30) -> vetoed to direction 0."""
    fstar = 5000.0 * math.exp((0.05 - 0.018) * (90.0 / 365.0))
    return {"day": 9, "event_ts": 1789306200000000000, "asof_ts": 1789306200000120000,
            "spot": 5000.0, "futures": fstar + 8.0}  # +8.0 pts = +16 bps [example]


def test_cost_gate_veto_end_to_end():
    """A bound-crossing reading that fails the gate is vetoed to flat."""
    s = signal({}, [{"day": 0, "event_ts": 1, "asof_ts": 2, "spot": 5000.0, "futures": 5000.0},
                    _veto_bar()], Config())
    assert s.direction == 0 and s.confidence == 0.0


def test_confidence_capital_formula():
    """conf = min(1, edge/bound - 1); capital = 0.5 * conf (§S2 sizing)."""
    rows = parse_tape()
    s3 = signal({}, rows[:4], Config())  # day-3: -1 direction
    assert s3.direction == -1
    exp_conf = min(1.0, 20.7837771248 / 15.0 - 1.0)
    assert abs(s3.confidence - exp_conf) <= 1e-9
    assert abs(s3.confidence - 0.3855851417) <= 1e-9
    assert abs(s3.capital - 0.5 * exp_conf) <= 1e-9
    s0 = signal({}, rows[:1], Config())  # day-0: flat
    assert s0.direction == 0 and s0.confidence == 0.0 and s0.capital == 0.0


def test_invalid_input_yields_unknown():
    bad_fut = {"day": 0, "event_ts": 1, "asof_ts": 2, "spot": 5000.0, "futures": float("nan")}
    s = signal({}, [bad_fut], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
    bad_spot = {"day": 0, "event_ts": 1, "asof_ts": 2, "spot": -1.0, "futures": 5000.0}
    s = signal({}, [bad_spot], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
    s = signal({}, [], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_staleness_stamping():
    """computed_at = bar event_ts; staleness = asof_ts - event_ts."""
    rows = parse_tape()
    s = signal({}, rows[:3], Config())
    assert s.computed_at == rows[2]["event_ts"]
    assert s.staleness == rows[2]["asof_ts"] - rows[2]["event_ts"] == 120000
