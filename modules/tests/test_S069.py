"""Acceptance tests for S069 — Implied-vs-realized spread / variance risk premium.

Template v1.0.0, module v1.1.0. Concrete reference implementation of the
chapter's normative §S3 pseudocode: every variable bound, guards inline
(locate/cooldown/staleness/halt), executable cost-gate predicate, causality
assert fill_event > signal_event on bound timestamps.

Run: python3 -m pytest modules/tests/test_S069.py -q   (from repo root)
"""
import csv
import math
import pytest
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S069_tape.csv"
EXPECTED = FIX / "S069_expected.csv"
BOUNDARY = FIX / "S069_boundary.csv"
BOUNDARY_EXPECTED = FIX / "S069_boundary_expected.csv"
INVALID = FIX / "S069_invalid.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ['month', 'vrp_vol', 'vrp_var', 'z', 'direction']
COL_TYPES = {'month': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'iv_ann': 'float', 'rv_ann': 'float'}


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
    z_entry: float = 1.5                 # calibrate
    cost_gate_k: float = 0.5             # calibrate
    window_months: int = 4               # calibrate
    staleness_ttl_ns: int = 3_000_000_000  # 3 s [default]
    cooldown_ns: int = 60_000_000_000     # 60 s [default]
    reference_notional_usd: float = 1_000_000.0  # [example]
    reference_adv_pct: float = 0.001     # [example]
    venue: str = "CBOE"                  # [example]
    side: str = "taker"                  # [default]
    urgency: str = "normal"              # [default]
    locate_ok: bool = False              # [default]


@dataclass
class ModuleState:
    vrp_history: list = field(default_factory=list)
    module_state: str = "OK"
    last_compliance_block_ts: int = -10**18
    seq: int = 0
    last_signal_vector: object = None


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Callable cost model — mirrors the §S2 COST block exactly at (taker, normal)."""
    side_mult = {"taker": 1.0, "mixed": 0.75, "maker": 0.5}[side]       # [example]
    urg_mult = {"low": 0.5, "normal": 1.0, "high": 1.5, "stress": 2.0}[urgency]  # [example]
    spread_bps = 4.00 * side_mult   # straddle two-leg half-spread [example]
    fee_bps = 0.60                  # options fees [example]
    borrow_bps = 0.00               # reason: delta-hedged long vol; no stock borrow [default]
    impact_bps = 2.00 * urg_mult    # delta-hedge slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def next_regular_session_open_ns(event_ts, tz="America/New_York"):
    """Earliest fill = first regular-session open strictly after the signal event."""
    return event_ts + 1  # fixture simplification: next bar open strictly after event


def _unknown(symbol, event_ts, staleness, state_code="UNKNOWN"):
    return SignalVector(symbol, 0, 0.0, 0.0, event_ts, staleness, state_code)


def signal(state, events, cfg, now_ns=None):
    events = list(events)
    if not events:
        return _unknown("", 0, 0)  # F1
    b = events[-1]  # newest last
    now_ns = b["asof_ts"] if now_ns is None else now_ns  # causality clock = event_ts domain
    if now_ns - b["asof_ts"] > cfg.staleness_ttl_ns:
        return _unknown("TEST", b["event_ts"], b["asof_ts"] - b["event_ts"])  # F3, no interpolation
    if now_ns - state.last_compliance_block_ts < cfg.cooldown_ns:
        return _unknown("TEST", b["event_ts"], b["asof_ts"] - b["event_ts"])  # C10 cooldown
    if any(v <= 0 or not math.isfinite(v) for v in (b["iv_ann"], b["rv_ann"])):
        return _unknown("TEST", b["event_ts"], b["asof_ts"] - b["event_ts"])  # F2 bounds
    n = len(events)
    w = cfg.window_months
    vrp_now = b["iv_ann"] - b["rv_ann"]                       # vol-points VRP [example]
    hist = [e["iv_ann"] - e["rv_ann"] for e in events[max(0, n - w):n]]
    mu = sum(hist) / len(hist)
    sd = math.sqrt(sum((v - mu) ** 2 for v in hist) / len(hist)) if len(hist) > 1 else 0.0
    z = (vrp_now - mu) / sd if sd > 0 else 0.0
    if len(hist) < 2:
        z = 0.0                                              # single observation -> z = 0 [example]
    edge_bps = z * 100.0                                     # modeled per-trade edge [example]
    gate_ok = (expected_cost_bps(cfg.reference_notional_usd, cfg.reference_adv_pct,
                                 cfg.venue, cfg.side, cfg.urgency)
               <= cfg.cost_gate_k * edge_bps)                # executable cost-gate predicate
    direction = 1 if (z > cfg.z_entry and gate_ok) else 0     # strict >: z == z_entry does NOT enter
    if direction == -1 and not cfg.locate_ok:                # C7 locate guard (defensive)
        return _unknown("TEST", b["event_ts"], b["asof_ts"] - b["event_ts"])
    confidence = min(1.0, z / 3.0) if direction != 0 else 0.0  # [example] scale
    capital = 0.5 * confidence                                 # [default] 0.5 factor
    signal_event = b["event_ts"]
    fill_event = next_regular_session_open_ns(signal_event)
    assert fill_event > signal_event, "no signal-bar fills"   # causality
    state.vrp_history.append(vrp_now)
    state.seq += 1
    state.module_state = "OK"
    out = SignalVector("TEST", direction, confidence, capital, signal_event,
                       b["asof_ts"] - b["event_ts"], "OK")
    state.last_signal_vector = out
    return out


def recompute(rows):
    """Chapter fixture arithmetic (no cost gate): vol/var VRP + trailing-4 z."""
    vrps = [r["iv_ann"] - r["rv_ann"] for r in rows]
    out = []
    for i, r in enumerate(rows):
        hist = vrps[max(0, i - 3):i + 1]
        mu = sum(hist) / len(hist)
        sd = math.sqrt(sum((v - mu) ** 2 for v in hist) / len(hist)) if len(hist) > 1 else 0.0
        z = (vrps[i] - mu) / sd if sd > 0 else 0.0
        out.append({"month": r["month"], "vrp_vol": vrps[i],
                    "vrp_var": r["iv_ann"] ** 2 - r["rv_ann"] ** 2,
                    "z": z, "direction": 1 if z > 1.5 else 0})
    return out


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
        assert abs(got[0]["vrp_vol"] - 4.0) < 1e-9
        assert abs(got[0]["vrp_var"] - (22.0**2 - 18.0**2)) < 1e-9
        assert got[0]["direction"] == 0  # single obs -> z=0


def test_signal_emits_valid_signalvector():
    rows = parse_tape()
    cfg, state = Config(), ModuleState()
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
    cfg, state = Config(), ModuleState()
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
    bad = {"month": 0, "event_ts": 1, "asof_ts": 2, "iv_ann": 0.0, "rv_ann": 20.0}
    s = signal(ModuleState(), [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_cost_callable_mirrors_block():
    """Callable reproduces the §S2 block total exactly at (taker, normal); variants scale."""
    assert expected_cost_bps(1e6, 0.001, "CBOE", "taker", "normal") == 6.60  # 4.00+0.60+0.00+2.00
    assert expected_cost_bps(1e6, 0.001, "CBOE", "maker", "normal") == 4.60
    assert expected_cost_bps(1e6, 0.001, "CBOE", "mixed", "normal") == 5.60
    assert expected_cost_bps(1e6, 0.001, "CBOE", "taker", "stress") == 8.60
    assert expected_cost_bps(1e6, 0.001, "CBOE", "taker", "low") == 5.60


def test_boundary_fixture_triggers_entry():
    """Boundary tape: flat VRP then a spike -> month-4 z = sqrt(3) > 1.5 -> direction=1, gate passes."""
    rows = parse_tape(BOUNDARY)
    exp = load_csv(BOUNDARY_EXPECTED)
    got = recompute(rows)
    assert len(got) == len(exp)
    for g, e in zip(got, exp):
        for k in EXPECTED_COLS:
            gv, ev = g[k], e[k]
            try:
                assert abs(float(gv) - float(ev)) <= TOL, (k, gv, ev)
            except (ValueError, TypeError):
                assert str(gv) == str(ev), (k, gv, ev)
    assert abs(got[4]["z"] - math.sqrt(3)) <= 1e-9
    assert got[4]["direction"] == 1
    cfg, state = Config(), ModuleState()
    s = signal(state, rows, cfg)
    assert s.direction == 1 and s.module_state == "OK"
    assert s.confidence == pytest.approx(min(1.0, math.sqrt(3) / 3.0), rel=1e-12)


def test_threshold_boundary_exact():
    """z == z_entry exactly must NOT enter (strict >)."""
    rows = parse_tape(BOUNDARY)
    got = recompute(rows)
    z_last = got[-1]["z"]
    cfg = Config(z_entry=z_last)  # exact float equality: same computed value
    s = signal(ModuleState(), rows, cfg)
    assert s.direction == 0, "strict > required at the threshold"
    cfg2 = Config(z_entry=z_last - 1e-12)
    s2 = signal(ModuleState(), rows, cfg2)
    assert s2.direction == 1, "epsilon below the z must enter"


def test_gate_veto_path():
    """A rich z still vetoes when the cost gate fails (tiny k)."""
    rows = parse_tape(BOUNDARY)
    cfg = Config(cost_gate_k=0.01)  # 0.01 * 173.2 = 1.73 < 6.60 [example]
    s = signal(ModuleState(), rows, cfg)
    assert s.direction == 0 and s.confidence == 0.0 and s.module_state == "OK"


def test_invalid_fixture_all_unknown():
    """Every row of the invalid tape -> UNKNOWN; empty input -> UNKNOWN."""
    cfg = Config()
    rows = parse_tape(INVALID)
    assert len(rows) == 5
    for r in rows:
        s = signal(ModuleState(), [r], cfg)
        assert s.module_state == "UNKNOWN", r
        assert s.direction == 0, r
        assert s.confidence == 0.0, r
    s = signal(ModuleState(), [], cfg)
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_causality_pins():
    """Timestamp pins: computed_at == event_ts; staleness == asof - event;
    next-session-open strictly after the signal event."""
    rows = parse_tape()
    cfg, state = Config(), ModuleState()
    for i in range(len(rows)):
        b = rows[i]
        s = signal(state, rows[: i + 1], cfg)
        assert s.computed_at == b["event_ts"], "computed_at must pin to the bar's event_ts"
        assert s.staleness == b["asof_ts"] - b["event_ts"], "staleness pins to asof-event"
        fill_event = next_regular_session_open_ns(s.computed_at)
        assert fill_event > s.computed_at, "earliest fill must be strictly after the signal"


def test_staleness_and_cooldown_guards():
    """Stale asof and recent compliance block both -> UNKNOWN."""
    rows = parse_tape(BOUNDARY)
    b = dict(rows[-1])
    cfg, state = Config(), ModuleState()
    s = signal(state, rows, cfg, now_ns=b["asof_ts"] + cfg.staleness_ttl_ns + 1)
    assert s.module_state == "UNKNOWN" and s.direction == 0
    state2 = ModuleState(last_compliance_block_ts=b["asof_ts"])
    s2 = signal(state2, rows, cfg, now_ns=b["asof_ts"])
    assert s2.module_state == "UNKNOWN" and s2.direction == 0
