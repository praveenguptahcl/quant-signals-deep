"""Acceptance tests for S070 — Straddle-implied move vs realized.

Template v1.0.0 / module v1.1.0. Reference implementation of the chapter's
normative §S3 pseudocode, with all guards inline: F1/F2 input validation,
iv_pct bounds, staleness TTL, market-state gates (halt/auction/closed),
post-block cooldown (C10), locate gate (C7), executable cost-gate predicate,
and the causality pin (fill_event > signal_event; no-signal-bar fills).

Fixtures:
  modules/fixtures/S070_tape.csv        # TYPE: validation-run, 6-event tape
  modules/fixtures/S070_expected.csv    # hand-checked edge/z/direction
  modules/fixtures/S070_edge_cases.csv  # boundary / invalid / market-state rows

Run: python3 -m pytest modules/tests/test_S070.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S070_tape.csv"
EXPECTED = FIX / "S070_expected.csv"
EDGE = FIX / "S070_edge_cases.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ['event', 'edge', 'z', 'direction']
COL_TYPES = {'event': 'int', 'symbol': 'str', 'event_ts': 'int', 'asof_ts': 'int',
             'implied_move': 'float', 'realized_move': 'float', 'iv_pct': 'float',
             'market_state': 'str', 'case_id': 'str', 'expected_state': 'str',
             'expected_direction': 'int', 'note': 'str'}
SESSION_NS = 6_600_000_000_000  # one US equity session, 6.5 h in ns [fixed]


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
    rows = []
    for r in load_csv(TAPE):
        rows.append({k: _conv(r[k], COL_TYPES[k]) for k in
                     ('event', 'symbol', 'event_ts', 'asof_ts',
                      'implied_move', 'realized_move', 'iv_pct')})
    return rows


def parse_edge_cases():
    rows = []
    for r in load_csv(EDGE):
        rows.append({k: _conv(r[k], COL_TYPES[k]) for k in COL_TYPES if k in r})
    return rows


def make_bar(implied, realized, iv_pct, ts, asof=None, market_state="",
            symbol="FICT"):
    return {"event": 0, "symbol": symbol, "event_ts": ts,
            "asof_ts": asof if asof is not None else ts + 120_000,
            "implied_move": implied, "realized_move": realized,
            "iv_pct": iv_pct, "market_state": market_state}


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
    z_star: float = 1.0            # [example] -> calibrate per §S2 recipe
    iv_pct_gate: float = 70.0      # [example] -> calibrate per §S2 recipe
    cost_gate_k: float = 0.5       # [default] frozen, not fitted
    L: int = 6                     # [example] -> calibrate per §S2 recipe
    staleness_ttl_ns: int = 3_000_000_000   # [default] 3 s
    cooldown_s: float = 60.0       # [default] post-block cooldown (C10)
    equity_leg: bool = False       # [default] S070 fade is options-only
    equity_locate_ok: bool = True  # [default] consumer asserts per C7


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Callable cost model — mirrors the §S2 COST block exactly."""
    spread_bps = 6.00   # straddle two-leg half-spread on event [example]
    fee_bps = 0.60      # options fees [example]
    borrow_bps = 0.00   # reason: short premium via straddle; no stock borrow [default]
    impact_bps = 3.00   # event-day fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _unknown(symbol, ts):
    return SignalVector(symbol, 0, 0.0, 0.0, ts, 0, "UNKNOWN")


def signal(state, bars, cfg):
    """Reference implementation of the §S3 normative pseudocode."""
    bars = list(bars)
    if not bars:
        return _unknown("TEST", 0)                                   # F1
    b = bars[-1]
    sym = b.get("symbol") or "TEST"
    iv, rv, pct = b["implied_move"], b["realized_move"], b["iv_pct"]
    # --- F2: mathematical bounds, never interpolate
    if not (math.isfinite(iv) and iv > 0):
        return _unknown(sym, b["event_ts"])
    if not (math.isfinite(rv) and rv >= 0):
        return _unknown(sym, b["event_ts"])
    if not (math.isfinite(pct) and 0.0 <= pct <= 100.0):
        return _unknown(sym, b["event_ts"])
    # --- staleness guard
    staleness = b["asof_ts"] - b["event_ts"]
    if staleness > cfg.staleness_ttl_ns:
        return _unknown(sym, b["event_ts"])
    # --- market-state gates (§S0.5)
    mkt = b.get("market_state") or "CONTINUOUS_TRADING"
    if mkt == "HALTED":
        return _unknown(sym, b["event_ts"])
    if mkt == "AUCTION":
        return SignalVector(sym, state.get("last_direction", 0), 0.0, 0.0,
                            b["event_ts"], staleness, "DEGRADED")
    if mkt == "CLOSED":
        return SignalVector(sym, 0, 0.0, 0.0, b["event_ts"], 0, "OFF")
    # --- post-block cooldown (C10)
    last_block = state.get("last_block_ts")
    if last_block is not None and (b["event_ts"] - last_block) < cfg.cooldown_s * 1e9:
        return SignalVector(sym, 0, 0.0, 0.0, b["event_ts"], staleness, "OK")
    # --- edge arithmetic: all symbols bound; population std, ddof=0
    hist = bars[-cfg.L:]
    edges = [r["implied_move"] - r["realized_move"] for r in hist]
    n = len(edges)
    mu = sum(edges) / n
    sd = math.sqrt(sum((e - mu) ** 2 for e in edges) / n) if n > 1 else 0.0
    z = (edges[-1] - mu) / sd if sd > 0 else 0.0
    # --- fade rule: strict >, boundary stays flat
    direction = -1 if (z > cfg.z_star and pct > cfg.iv_pct_gate) else 0
    confidence = min(1.0, z / 2.0) if direction else 0.0
    # --- locate gate (C7)
    if direction == -1 and cfg.equity_leg and not cfg.equity_locate_ok:
        state["last_block_ts"] = b["event_ts"]
        return SignalVector(sym, 0, 0.0, 0.0, b["event_ts"], staleness, "OK")
    # --- executable cost-gate predicate
    edge_bps = z * 80.0  # modeled per-trade edge [example]
    cost = expected_cost_bps(notional=1.0, adv_pct=0.001, venue="CBOE",
                            side="taker", urgency="normal")
    if not (cost <= cfg.cost_gate_k * edge_bps):
        direction, confidence = 0, 0.0
    state["last_direction"] = direction
    # --- causality pin: earliest fill is @open(t+1), strictly after the signal
    fill_event_ts = b["event_ts"] + SESSION_NS
    assert fill_event_ts > b["event_ts"], "fill_event > signal_event"
    return SignalVector(sym, direction, confidence, 0.5 * confidence,
                        b["event_ts"], staleness, "OK")


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Reference recomputation of the tape matches expected.csv."""
    rows = parse_tape()
    assert all(r["symbol"] == "FICT" for r in rows)
    exp = load_csv(EXPECTED)
    edges = [r["implied_move"] - r["realized_move"] for r in rows]
    mu = sum(edges) / len(edges)
    sd = math.sqrt(sum((e - mu) ** 2 for e in edges) / len(edges))
    assert abs(mu - 2.0166666666666666) < TOL
    for i, (r, e) in enumerate(zip(rows, exp)):
        z = (edges[i] - mu) / sd
        d = -1 if (z > 1.0 and r["iv_pct"] > 70) else 0
        assert abs(edges[i] - float(e["edge"])) <= TOL, (i, edges[i], e["edge"])
        assert abs(z - float(e["z"])) <= TOL, (i, z, e["z"])
        assert d == int(e["direction"]), (i, d, e["direction"])
    assert int(exp[2]["direction"]) == -1  # richest implied, high IV pct -> fade


def test_signal_emits_valid_signalvector():
    rows = parse_tape()
    cfg, state = Config(), {}
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s, r in zip(sigs, rows):
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.capital == 0.5 * s.confidence
        assert s.computed_at == r["event_ts"]
        assert s.staleness == r["asof_ts"] - r["event_ts"]
        assert s.symbol == "FICT"
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = parse_tape()
    cfg, state = Config(), {}
    for i in range(len(rows)):
        s = signal(state, rows[: i + 1], cfg)
        assert s.computed_at == rows[i]["event_ts"], "signal timestamped at its bar"
        fill_ts = s.computed_at + SESSION_NS  # earliest fill @open(t+1)
        assert fill_ts > s.computed_at, "fill_event > signal_event"
        later = [r["event_ts"] for r in rows[i + 1:] if r["event_ts"] > s.computed_at]
        if later:
            assert min(later) > s.computed_at, "signal-bar fill"


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "CBOE", "taker", "normal")
    assert cost == 9.60  # mirrors the COST block exactly
    assert cost <= k * 100000.0   # huge edge -> gate passes
    assert not (cost <= k * 0.0001)  # tiny edge -> gate blocks


def test_cost_gate_veto_path():
    """Fade criteria met but the cost gate vetoes -> direction 0."""
    ts = 1788960600000000000
    bars = [make_bar(5.0, 5.0, 80.0, ts),          # edge 0
            make_bar(5.0, 5.0, 80.0, ts + 1),     # edge 0
            make_bar(8.0, 5.0, 80.0, ts + 2)]     # edge 3 -> z ~1.41 > 1
    tight = Config(cost_gate_k=0.01)  # [example] punitive k forces the veto
    s = signal({}, bars, tight)
    assert s.direction == 0 and s.confidence == 0.0 and s.module_state == "OK"
    s2 = signal({}, bars, Config())  # default k passes: 9.6 <= 0.5 * 113
    assert s2.direction == -1


def test_invalid_inputs_yield_unknown():
    for r in parse_edge_cases():
        if r["expected_state"] != "UNKNOWN":
            continue
        b = make_bar(r["implied_move"], r["realized_move"], r["iv_pct"],
                     r["event_ts"], r["asof_ts"], r["market_state"] or "")
        s = signal({}, [b], Config())
        assert s.module_state == "UNKNOWN" and s.direction == 0, r["case_id"]


def test_market_state_gates():
    ts = 1788960600000000000
    rows = parse_edge_cases()
    by_id = {r["case_id"]: r for r in rows}
    s = signal({}, [make_bar(8.0, 5.0, 80.0, ts, market_state="HALTED")], Config())
    assert (s.module_state, s.direction) == ("UNKNOWN", 0)
    st = {"last_direction": -1}
    s = signal(st, [make_bar(8.0, 5.0, 80.0, ts, market_state="AUCTION")], Config())
    assert (s.module_state, s.direction) == ("DEGRADED", -1), "hold last"
    s = signal({}, [make_bar(8.0, 5.0, 80.0, ts, market_state="CLOSED")], Config())
    assert (s.module_state, s.direction) == ("OFF", 0)
    assert by_id["auction"]["expected_state"] == "DEGRADED"
    assert by_id["closed"]["expected_state"] == "OFF"


def test_boundary_thresholds_strict():
    """z == z_star and iv_pct == gate stay flat (strict >); just above fires."""
    ts = 1788960600000000000
    # edges [0, 2] -> z exactly 1.0
    bars = [make_bar(5.0, 5.0, 80.0, ts), make_bar(7.0, 5.0, 80.0, ts + 1)]
    s = signal({}, bars, Config())
    assert s.direction == 0, "z == z_star must stay flat"
    # edges [0, 0, 3] -> z ~1.414 > 1, iv_pct exactly at gate -> flat
    bars2 = [make_bar(5.0, 5.0, 70.0, ts), make_bar(5.0, 5.0, 70.0, ts + 1),
             make_bar(8.0, 5.0, 70.0, ts + 2)]
    s = signal({}, bars2, Config())
    assert s.direction == 0, "iv_pct == gate must stay flat"
    # same edges, iv_pct above gate -> fade
    bars3 = [make_bar(5.0, 5.0, 80.0, ts), make_bar(5.0, 5.0, 80.0, ts + 1),
             make_bar(8.0, 5.0, 80.0, ts + 2)]
    s = signal({}, bars3, Config())
    assert s.direction == -1 and 0.0 < s.confidence <= 1.0


def test_staleness_ttl_veto():
    ts = 1788960600000000000
    b = make_bar(8.0, 5.0, 80.0, ts, ts + 10_000_000_000)  # 10 s > 3 s TTL
    s = signal({}, [b], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_cooldown_after_block():
    """C10: no re-entry within cooldown_s of a compliance block."""
    ts = 1788960600000000000
    bars = [make_bar(5.0, 5.0, 80.0, ts), make_bar(5.0, 5.0, 80.0, ts + 1),
            make_bar(8.0, 5.0, 80.0, ts + 2)]
    s = signal({"last_block_ts": ts + 2 - 30_000_000_000}, bars, Config())
    assert s.direction == 0 and s.module_state == "OK", "inside cooldown"
    s = signal({"last_block_ts": ts + 2 - 61_000_000_000}, bars, Config())
    assert s.direction == -1, "cooldown expired"


def test_locate_gate():
    """C7: fade needs no locate (options-only); an equity leg needs consumer locate."""
    ts = 1788960600000000000
    bars = [make_bar(5.0, 5.0, 80.0, ts), make_bar(5.0, 5.0, 80.0, ts + 1),
            make_bar(8.0, 5.0, 80.0, ts + 2)]
    cfg = Config(equity_leg=True, equity_locate_ok=False)
    st = {}
    s = signal(st, bars, cfg)
    assert s.direction == 0 and st.get("last_block_ts") == ts + 2
    s = signal({}, bars, Config(equity_leg=True, equity_locate_ok=True))
    assert s.direction == -1
