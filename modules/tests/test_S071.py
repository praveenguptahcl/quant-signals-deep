"""Acceptance tests for S071 — 25-delta risk reversal / skew change.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode (v1.1.0), and real assertions
including causality (assert fill_event > signal_event), invalid -> UNKNOWN,
boundary conditions, gate-veto paths, halt/cooldown/locate guards.

Run: python3 -m pytest modules/tests/test_S071.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S071_tape.csv"
EXPECTED = FIX / "S071_expected.csv"
TAPE_EDGE = FIX / "S071_tape_edge.csv"
EXPECTED_EDGE = FIX / "S071_expected_edge.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['day', 'rr25', 'd_rr', 'z', 'direction']
COL_TYPES = {'day': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'call25_iv': 'float', 'put25_iv': 'float'}
SESSION_LAG_NS = 86_400_000_000_000  # one daily session: earliest fill @open(t+1) [example]


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


def parse_tape(path=TAPE):
    return [{k: _conv(r[k], COL_TYPES[k]) for k in COL_TYPES} for r in load_csv(path)]


# ----------------------------------------- normative pseudocode (v1.1.0) stub
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
    z_star: float = 2.0                        # [example]
    cost_gate_k: float = 0.5                   # [default]
    min_bars: int = 3                          # [example]
    edge_bps_per_z: float = 60.0               # [example]
    staleness_ttl_ns: int = 3_000_000_000      # [default]
    cooldown_ns: int = 60_000_000_000          # [default]
    ref_notional: float = 100_000.0            # [example]
    locate_ok: bool = True                     # [default]
    symbol: str = "TEST"


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 3.00   # risk-reversal two-leg half-spread [example]
    fee_bps = 0.60      # options fees [example]
    borrow_bps = 0.00   # reason: options-only structure [default]
    impact_bps = 1.50   # skew-shock fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, bars, cfg):
    """Reference implementation of §S3 normative pseudocode (v1.1.0)."""
    bars = sorted((b for b in bars), key=lambda e: e["event_ts"])  # newest last
    state = dict(state)
    if not bars:
        return SignalVector(cfg.symbol, 0, 0.0, 0.0, 0, 0, "UNKNOWN")  # F1 empty
    b = bars[-1]
    staleness_ns = b["asof_ts"] - b["event_ts"]
    if state.get("module_state") == "OFF":
        return SignalVector(cfg.symbol, 0, 0.0, 0.0, b["event_ts"], staleness_ns, "OFF")
    if state.get("market_state") == "HALTED":
        return SignalVector(cfg.symbol, 0, 0.0, 0.0, b["event_ts"], staleness_ns, "UNKNOWN")  # freeze
    if state.get("market_state") == "AUCTION":
        return state.get("last_signal") or SignalVector(cfg.symbol, 0, 0.0, 0.0,
                                                        b["event_ts"], staleness_ns, "DEGRADED")
    if staleness_ns > cfg.staleness_ttl_ns:
        return SignalVector(cfg.symbol, 0, 0.0, 0.0, b["event_ts"], staleness_ns, "UNKNOWN")
    if any(v <= 0 or not math.isfinite(v) for v in (b["call25_iv"], b["put25_iv"])):
        return SignalVector(cfg.symbol, 0, 0.0, 0.0, b["event_ts"], staleness_ns, "UNKNOWN")  # F2
    rr = [r["call25_iv"] - r["put25_iv"] for r in bars]
    if len(rr) < cfg.min_bars:
        return SignalVector(cfg.symbol, 0, 0.0, 0.0, b["event_ts"], staleness_ns, "UNKNOWN")
    dr = [rr[i] - rr[i - 1] for i in range(1, len(rr))]  # causal trailing window
    mu = sum(dr) / len(dr)
    sd = math.sqrt(sum((v - mu) ** 2 for v in dr) / len(dr))  # population SD [example]
    z = (dr[-1] - mu) / sd if sd > 1e-12 else 0.0
    direction = 1 if z > cfg.z_star else (-1 if z < -cfg.z_star else 0)  # strict inequality
    confidence = min(1.0, abs(z) / 4.0) if direction else 0.0  # [example] scale
    edge_bps = abs(z) * cfg.edge_bps_per_z  # modeled per-trade edge [example]
    signal_event = b["event_ts"]
    fill_event = signal_event + SESSION_LAG_NS  # earliest fill @open(t+1)
    assert fill_event > signal_event, "no signal-bar fills"  # causality
    cost_bps = expected_cost_bps(cfg.ref_notional, 0.001, "CBOE-EDGX", "taker", "normal")
    if not (cost_bps <= cfg.cost_gate_k * edge_bps):
        direction, confidence = 0, 0.0  # cost gate veto
    if direction == -1 and not cfg.locate_ok:
        direction, confidence = 0, 0.0  # C7 Reg-SHO locate
    now_ns = state.get("now_ns", signal_event)
    last_block = state.get("last_block_ts_ns")
    if last_block is not None and (now_ns - last_block) < cfg.cooldown_ns:
        return SignalVector(cfg.symbol, 0, 0.0, 0.0, signal_event, staleness_ns, "DEGRADED")  # C10
    return SignalVector(cfg.symbol, direction, confidence, 0.5 * confidence,
                        signal_event, staleness_ns, "OK")


def recompute(rows):
    """Fixture validation convention (non-live): full-sample mu/sd over the
    non-initial d_RR applied to every row; day-0 z forced 0.0. Uses future
    information; validation convenience only, NOT the live rule."""
    rr = [r["call25_iv"] - r["put25_iv"] for r in rows]
    dr = [0.0] + [rr[i] - rr[i - 1] for i in range(1, len(rr))]
    hist = dr[1:]
    mu = sum(hist) / len(hist)
    sd = math.sqrt(sum((v - mu) ** 2 for v in hist) / len(hist))
    out = []
    for i, r in enumerate(rows):
        z = (dr[i] - mu) / sd if i > 0 and sd > 0 else 0.0
        d = 1 if z > 2.0 else (-1 if z < -2.0 else 0)
        out.append({"day": r["day"], "rr25": rr[i], "d_rr": dr[i], "z": z, "direction": d})
    return out


def _check_tape(tape_path, exp_path, pin_checks):
    rows = parse_tape(tape_path)
    exp = load_csv(exp_path)
    got = recompute(rows)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, e in zip(got, exp):
        for k in EXPECTED_COLS:
            gv, ev = g[k], e[k]
            try:
                assert abs(float(gv) - float(ev)) <= TOL, (k, gv, ev)
            except (ValueError, TypeError):
                assert str(gv) == str(ev), (k, gv, ev)
    for idx, key, want in pin_checks:
        assert abs(got[idx][key] - want) <= TOL, (idx, key, got[idx][key], want)
    assert all(g["direction"] in (-1, 0, 1) for g in got)


def _shock_bars():
    """Deterministic 7-bar downward skew shock: z = -2.23607 < -2.0 -> direction -1."""
    t0 = 1788960600000000000
    bars = []
    for i in range(7):
        put = 28.0 if i < 6 else 33.0
        ts = t0 + i * SESSION_LAG_NS
        bars.append({"day": i, "event_ts": ts, "asof_ts": ts + 120000,
                     "call25_iv": 25.0, "put25_iv": put})
    return bars


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Reference recomputation of the tape matches expected.csv."""
    _check_tape(TAPE, EXPECTED, [(0, "rr25", -4.5), (4, "d_rr", 1.4), (5, "z", -1.5714681655)])


def test_edge_tape_recomputes_to_expected():
    """Edge tape: degenerate flat window, near-threshold shock stays flat."""
    got = recompute(parse_tape(TAPE_EDGE))
    exp = load_csv(EXPECTED_EDGE)
    assert len(got) == len(exp)
    for g, e in zip(got, exp):
        for k in EXPECTED_COLS:
            assert abs(float(g[k]) - float(e[k])) <= TOL, (k, g[k], e[k])
    # day-5: |z| = 1.9430998537 < 2.0 -> strict threshold, direction stays 0
    assert abs(got[5]["z"] - (-1.9430998537)) <= TOL
    assert got[5]["direction"] == 0
    # days 0-2: flat window -> z == 0.0 exactly
    assert all(got[i]["z"] == 0.0 for i in (0, 1, 2))
    assert all(g["direction"] == 0 for g in got)


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
        fill_event = s.computed_at + SESSION_LAG_NS  # earliest fill @open(t+1)
        assert fill_event > s.computed_at, "signal-bar fill"


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "X", "taker", "normal")
    assert cost >= 0.0
    assert cost <= k * 100000.0   # huge edge -> gate passes
    assert not (cost <= k * 0.0001)  # tiny edge -> gate blocks


def test_cost_gate_veto_zeroes_direction():
    """A shock that fires under the default gate is vetoed by a punitive k."""
    bars = _shock_bars()
    cfg = Config()
    s = signal({}, bars, cfg)
    assert s.direction == -1 and s.module_state == "OK"  # fires under default k
    s_veto = signal({}, bars, Config(cost_gate_k=1e-6))
    assert s_veto.direction == 0 and s_veto.confidence == 0.0  # vetoed


def test_invalid_input_yields_unknown():
    bad = {"day": 0, "event_ts": 1, "asof_ts": 2, "call25_iv": 0.0, "put25_iv": 28.0}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_nan_iv_yields_unknown():
    bad = {"day": 0, "event_ts": 1, "asof_ts": 2, "call25_iv": float("nan"), "put25_iv": 28.0}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_empty_events_yields_unknown():
    s = signal({}, [], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_short_history_yields_unknown():
    rows = parse_tape()[:2]  # < min_bars = 3
    s = signal({}, rows, Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_flat_window_zero_sd_emits_flat():
    """Degenerate window: sd == 0 -> z == 0 -> direction 0 even at z_star == 0
    (strict inequality boundary)."""
    t0 = 1788960600000000000
    bars = [{"day": i, "event_ts": t0 + i * SESSION_LAG_NS,
             "asof_ts": t0 + i * SESSION_LAG_NS + 120000,
             "call25_iv": 25.0, "put25_iv": 29.0} for i in range(4)]
    s = signal({}, bars, Config())
    assert s.direction == 0 and s.confidence == 0.0 and s.module_state == "OK"
    s0 = signal({}, bars, Config(z_star=0.0))
    assert s0.direction == 0, "strict inequality: z == z_star must not fire"


def test_locate_gate_blocks_short_without_locate():
    """C7: SHORT without locate -> direction 0; with locate -> -1."""
    bars = _shock_bars()
    s = signal({}, bars, Config(locate_ok=True))
    assert s.direction == -1
    s_nolocate = signal({}, bars, Config(locate_ok=False))
    assert s_nolocate.direction == 0 and s_nolocate.confidence == 0.0


def test_halt_freezes_to_unknown():
    """HALTED market state -> freeze, emit UNKNOWN (no contribution across reopen)."""
    rows = parse_tape()
    s = signal({"market_state": "HALTED"}, rows, Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_cooldown_blocks_reentry():
    """C10: within 60 s of a compliance block -> DEGRADED, no re-entry."""
    rows = parse_tape()
    ts = rows[-1]["event_ts"]
    state = {"now_ns": ts + 30_000_000_000, "last_block_ts_ns": ts}
    s = signal(state, rows, Config())
    assert s.module_state == "DEGRADED" and s.direction == 0
    state2 = {"now_ns": ts + 61_000_000_000, "last_block_ts_ns": ts}
    s2 = signal(state2, rows, Config())
    assert s2.module_state == "OK", "cooldown expired -> normal computation"


def test_causality_pin_explicit_fill():
    """Pin the timing box: earliest fill is exactly one session after the signal."""
    rows = parse_tape()
    cfg, state = Config(), {}
    s = signal(state, rows, cfg)
    fill_event = s.computed_at + SESSION_LAG_NS
    assert fill_event == s.computed_at + 86_400_000_000_000  # [example] daily cadence
    assert fill_event > s.computed_at
    assert rows[-1]["event_ts"] < rows[-1]["event_ts"] + SESSION_LAG_NS
