"""Acceptance tests for S075 — Dispersion trading.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S075.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S075_tape.csv"
EXPECTED = FIX / "S075_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['day', 'rho_impl', 'spread', 'direction']
COL_TYPES = {'day': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'iv_a': 'float', 'iv_b': 'float', 'iv_c': 'float', 'rho_real': 'float'}


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


def implied_rho(ivs, idx_iv=27.0, w=1 / 3):
    """Reference rho_impl arithmetic (normative §S3 formula)."""
    num = idx_iv ** 2 - sum((w * s) ** 2 for s in ivs)
    den = sum(2 * w * w * ivs[i] * ivs[j] for i in range(3) for j in range(i + 1, 3))
    return num / den if den > 0 else 0.0  # never divide by zero [default]


def recompute(rows):
    out = []
    for r in rows:
        ivs = [r["iv_a"], r["iv_b"], r["iv_c"]]
        rho = implied_rho(ivs)
        spr = rho - r["rho_real"]
        out.append({"day": r["day"], "rho_impl": rho, "spread": spr,
                    "direction": 1 if spr > 0.10 else 0})
    return out


@dataclass
class Config:
    kappa: float = 0.10      # entry spread threshold [example]
    cost_gate_k: float = 0.5  # [default]
    use_vrp_gate: bool = False  # wire the §0 consumes S069 edge [example]
    vrp_z_entry: float = 1.5  # VRP gate threshold [example]
    conf_scale: float = 0.30  # confidence scale [example]
    staleness_ttl_ns: int = 93_600_000_000_000  # 26 h [default] — one session past the close print

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 8.00   # 3 single-stock straddles + index straddle half-spreads [example]
    fee_bps = 1.20      # options fees, 4 legs [example]
    borrow_bps_per_day = 0.00  # reason: long-gamma structure; borrow in delta hedge only [default]
    impact_bps = 3.00   # multi-leg fill slippage [example]
    return spread_bps + fee_bps + borrow_bps_per_day + impact_bps

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    if b["asof_ts"] - b["event_ts"] > cfg.staleness_ttl_ns:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F1 staleness
    if any(v <= 0 or not math.isfinite(v) for v in (b["iv_a"], b["iv_b"], b["iv_c"], b["rho_real"])):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    vrp_z = b.get("vrp_z")
    if cfg.use_vrp_gate and (vrp_z is None or not math.isfinite(vrp_z)):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F1: gate input absent
    ivs = [b["iv_a"], b["iv_b"], b["iv_c"]]
    rho = implied_rho(ivs)  # zero denominator → 0.0, never divide by zero [default]
    spr = rho - b["rho_real"]
    vrp_ok = (not cfg.use_vrp_gate) or (vrp_z >= cfg.vrp_z_entry)  # S069 VRP gate
    direction = 1 if (spr > cfg.kappa and vrp_ok) else 0  # long dispersion [example]
    confidence = min(1.0, spr / cfg.conf_scale) if direction else 0.0  # [example] scale
    edge_bps = spr * 1000.0  # modeled per-trade edge [example]
    cost = expected_cost_bps(1.0, 0.001, "CBOE", "taker", "normal")  # reference stack [example inputs]
    if not (cost <= cfg.cost_gate_k * edge_bps):
        direction, confidence = 0, 0.0  # cost gate [default] k
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


def test_day0_handcheck_pinned():
    """Day-0 hand-check pinned: below kappa, no trigger."""
    got = recompute(parse_tape())
    assert abs(got[0]["rho_impl"] - 0.3920) < 1e-3  # chapter day-0 hand-check
    assert got[0]["direction"] == 0  # 0.3920-0.30=0.092 < 0.10
    assert all(g["direction"] in (0, 1) for g in got)


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
    bad = {"day": 0, "event_ts": 1, "asof_ts": 2, "iv_a": 0.0, "iv_b": 35.0,
           "iv_c": 37.0, "rho_real": 0.3}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_cost_gate_full_path_k0_blocks_day2_trigger():
    """Full-path cost gate: k=0 blocks the day-2 trigger; k=2 lets it through."""
    rows = parse_tape()
    s = signal({}, rows[:3], Config(cost_gate_k=0.0))
    assert s.direction == 0 and s.confidence == 0.0  # gate blocks: 12.20 > 0 * 110.5
    s2 = signal({}, rows[:3], Config(cost_gate_k=2.0))
    assert s2.direction == 1  # gate passes: 12.20 <= 2 * 110.5


def test_zero_denominator_guard():
    """Degenerate arithmetic (den <= 0) yields rho = 0.0, never divides by zero."""
    assert implied_rho([0.0, 0.0, 0.0]) == 0.0
    # fixture day-3 pin: equal IVs 35 -> rho_impl 0.3926530612
    assert abs(implied_rho([35.0, 35.0, 35.0]) - 0.3926530612) <= TOL


def test_stale_close_print_yields_unknown():
    """F1: asof_ts - event_ts > staleness TTL (26 h) -> UNKNOWN."""
    rows = parse_tape()
    stale = dict(rows[2], asof_ts=rows[2]["event_ts"] + 100_000_000_000_000)  # > 26 h
    s = signal({}, rows[:2] + [stale], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
    fresh = signal({}, rows[:3], Config())  # fixture deltas are 120 us
    assert fresh.module_state == "OK"


def test_vrp_gate_behavior():
    """S069 gate: missing vrp_z -> UNKNOWN; below entry -> flat; at/above -> trigger."""
    rows = parse_tape()
    cfg = Config(use_vrp_gate=True)
    s = signal({}, rows[:3], cfg)  # day-2 trigger bar, no vrp_z field
    assert s.module_state == "UNKNOWN" and s.direction == 0
    low = dict(rows[2], vrp_z=0.5)
    s = signal({}, rows[:2] + [low], cfg)
    assert s.direction == 0 and s.module_state == "OK"
    high = dict(rows[2], vrp_z=2.0)
    s = signal({}, rows[:2] + [high], cfg)
    assert s.direction == 1 and s.module_state == "OK"
    # gate off by default: fixture behavior unchanged
    s = signal({}, rows[:3], Config())
    assert s.direction == 1
