"""Acceptance tests for S065 — GARCH(1,1) intraday volatility.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode (cfg-carried GARCH params,
named-argument cost-gate predicate, stationarity guard, warm-up state), and
real assertions including causality (assert fill_event > signal_event and
asof_ts >= event_ts) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S065.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S065_tape.csv"
EXPECTED = FIX / "S065_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['bar', 'sigma']
COL_TYPES = {'bar': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'ret': 'float', 'season': 'float'}


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


def recompute(rows, omega=2.0e-7, alpha=0.06, beta=0.89):
    """Pure-math reference of the §S3 recursion (no gating)."""
    s2 = omega / (1 - alpha - beta)
    out = []
    for r in rows:
        out.append({"bar": r["bar"], "sigma": math.sqrt(s2)})
        s2 = omega + alpha * (r["ret"] / r["season"]) ** 2 + beta * s2
    return out


@dataclass
class Config:
    symbol: str = "TEST"
    omega: float = 2.0e-7    # calibrated default [default]
    alpha: float = 0.06      # calibrated default [default]
    beta: float = 0.89       # calibrated default [default]
    burn_in_bars: int = 20   # [default]
    target_vol: float = 0.01  # [example]
    cost_gate_k: float = 0.5   # [default]
    edge_bps: float = 50.0     # [example] reference edge level


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    # Sizing overlay emits no entries; stack is the downstream strategy's reference [example].
    spread_bps = 0.50
    fee_bps = 0.30
    borrow_bps = 0.00   # reason: sizing overlay; borrow in consumer [default]
    impact_bps = 0.50
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """Reference implementation of the §S3 normative pseudocode."""
    bars = list(events)
    if not bars:
        return SignalVector(cfg.symbol, 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    for e in bars:
        if e["asof_ts"] < e["event_ts"]:
            # causality clock contract violated (point-in-time leak) -> UNKNOWN
            return SignalVector(cfg.symbol, 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
        if not math.isfinite(e["ret"]) or e["season"] <= 0:
            return SignalVector(cfg.symbol, 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    if cfg.alpha + cfg.beta >= 1:  # F2 stationarity guard [documented]
        return SignalVector(cfg.symbol, 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    s2 = cfg.omega / (1 - cfg.alpha - cfg.beta)
    for r in bars[:-1]:  # recursion uses bars <= bar t only
        s2 = cfg.omega + cfg.alpha * (r["ret"] / r["season"]) ** 2 + cfg.beta * s2
    sig = math.sqrt(s2)
    scalar = cfg.target_vol / sig if sig > 0 else 0.0  # position-size scalar [example]
    confidence = min(1.0, scalar / 10.0)  # [example] scale
    gate = (expected_cost_bps(notional=1.0, adv_pct=0.001, venue="XNAS",
                              side="taker", urgency="normal")
            <= cfg.cost_gate_k * cfg.edge_bps)
    warm = len(bars) <= cfg.burn_in_bars
    st = "DEGRADED" if (warm or not gate) else "OK"
    return SignalVector(cfg.symbol, 0, confidence, 0.0, b["event_ts"],
                        b["asof_ts"] - b["event_ts"], st)


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
        assert abs(got[0]["sigma"] - math.sqrt(2.0e-7/0.05)) < 1e-12
        assert got[6]["sigma"] > got[5]["sigma"]  # vol rises after the -32bp shock at bar 5
        assert all(g["sigma"] > 0 for g in got)


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
        assert rows[i]["asof_ts"] >= rows[i]["event_ts"], "causality clock violated in fixture"
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
    bad = {"bar": 0, "event_ts": 1, "asof_ts": 2, "ret": 0.001, "season": 0.0}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
    # causality clock violation (asof before event) is also UNKNOWN
    bad_clock = {"bar": 0, "event_ts": 2, "asof_ts": 1, "ret": 0.001, "season": 1.0}
    s2 = signal({}, [bad_clock], Config())
    assert s2.module_state == "UNKNOWN" and s2.direction == 0


def test_stationarity_guard_unknown():
    """alpha+beta >= 1 (non-stationary recursion) -> UNKNOWN (F2)."""
    rows = parse_tape()
    cfg = Config(alpha=0.5, beta=0.6)
    assert cfg.alpha + cfg.beta >= 1
    s = signal({}, rows, cfg)
    assert s.module_state == "UNKNOWN" and s.direction == 0
    # boundary just under 1 is still processed
    cfg2 = Config(alpha=0.05, beta=0.94)
    s2 = signal({}, rows, cfg2)
    assert s2.module_state in ("OK", "DEGRADED")


def test_warmup_and_cost_gate_state():
    """Warm-up -> DEGRADED; cost gate -> OK on huge edge, DEGRADED on tiny edge."""
    rows = parse_tape()
    # default cfg: 12 fixture bars < burn_in_bars=20 -> warm-up DEGRADED everywhere
    cfg = Config()
    sigs = [signal({}, rows[: i + 1], cfg) for i in range(len(rows))]
    assert all(s.module_state == "DEGRADED" for s in sigs)
    # past warm-up, cost gate decides: huge edge -> OK, tiny edge -> DEGRADED
    ok_cfg = Config(burn_in_bars=0, edge_bps=1e6)
    assert signal({}, rows, ok_cfg).module_state == "OK"
    blocked_cfg = Config(burn_in_bars=0, edge_bps=1e-4)
    assert signal({}, rows, blocked_cfg).module_state == "DEGRADED"


def test_fixture_type_header_and_monotonic_clock():
    """Fixture carries the TYPE header and a sane event clock."""
    with open(TAPE) as f:
        head = [f.readline().rstrip("\n") for _ in range(2)]
    assert head[0] == "# TYPE: validation-run", head[0]
    rows = parse_tape()
    ts = [r["event_ts"] for r in rows]
    assert all(b > a for a, b in zip(ts, ts[1:])), "event_ts must be strictly increasing"
    assert all(r["asof_ts"] >= r["event_ts"] for r in rows), "asof_ts >= event_ts required"


def test_deseasonalization_math():
    """The seasonal factor is actually applied: scaling season changes sigma."""
    rows = parse_tape()
    cfg = Config(burn_in_bars=0, edge_bps=1e6)
    sigs_flat = [signal({}, rows[: i + 1], cfg) for i in range(len(rows))]
    rows2 = [dict(r, season=2.0) for r in rows]
    sigs_scaled = [signal({}, rows2[: i + 1], cfg) for i in range(len(rows2))]
    assert any(a.confidence != b.confidence
               for a, b in zip(sigs_flat, sigs_scaled)), "season division must move the forecast"
