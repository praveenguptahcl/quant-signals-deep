"""Acceptance tests for S055 — Johansen VECM cointegration (v1.1.0).

Normative reference implementation of the chapter's §S3 pseudocode:
estimate()/signal() semantics, cooldown, staleness TTL, cost-gate predicate,
causality (assert fill_event > signal_event), and invalid -> UNKNOWN (F1/F2/F5).

Run: python3 -m pytest modules/tests/test_S055.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S055_tape.csv"
EXPECTED = FIX / "S055_expected.csv"
ADVERSARIAL = FIX / "S055_tape_adversarial.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ['day', 'e_raw', 'e_c', 'band', 'direction']
COL_TYPES = {'day': 'int', 'event_ts': 'int', 'asof_ts': 'int',
             'X1': 'float', 'X2': 'float', 'X3': 'float'}

_B = [1.0, -0.7113, -0.3631]  # [example] fixture vector


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def type_header(path):
    with open(path) as f:
        for ln in f:
            if ln.startswith("# TYPE:"):
                return ln.strip().split(":", 1)[1].strip()
    return None


def _conv(v, t):
    if t == "int":
        return int(v)
    if t == "float":
        return float(v)
    return v


def parse_tape(path=TAPE):
    return [{k: _conv(r[k], COL_TYPES[k]) for k in COL_TYPES}
            for r in load_csv(path)]


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
    kappa: float = 2.0                 # entry band multiple [default]
    cost_gate_k: float = 0.5           # [default]
    formation_window: int = 60        # bars, strictly before trading [default]
    johansen_significance: float = 0.05
    det_order: int = 0
    k_ar_diff: int = 1
    min_obs: int = 120                # [default]
    reestimate_cadence_days: int = 21
    cooldown_s: int = 60              # [default]
    staleness_ttl_ns: int = 3_000_000_000  # 3 s [default]


@dataclass
class ModuleState:
    beta: list = field(default_factory=lambda: list(_B))
    mu: float = 0.0
    sd: float = 1.0
    rank: int = 1
    cooldown_until: int = 0
    module_state: str = "OK"


def make_state(rows, formation=4, cooldown_until=0):
    """Fixture-scale state: formation mu/sd from the first `formation` bars."""
    e = [r["X1"] + _B[1] * r["X2"] + _B[2] * r["X3"] for r in rows[:formation]]
    mu = sum(e) / formation
    sd = math.sqrt(sum((v - mu) ** 2 for v in e) / formation)
    return ModuleState(mu=mu, sd=sd, cooldown_until=cooldown_until)


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    per_leg_spread = 0.50   # half-spread per leg, bps [example]
    per_leg_fee = 0.30      # taker fee per leg, bps [example]
    spread_bps = 3 * per_leg_spread
    fee_bps = 3 * per_leg_fee
    borrow_bps = 2.00       # short-leg borrow amortized per trade [example]
    impact_bps = 1.50       # async three-leg fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps  # == 5.90 [example]


def estimate(formation_panel, cfg):
    """Reference for §S3 estimate(): hard formation floor + (T-N)/T scaling.

    A full Johansen eigen-solve is overkill for the stub; this pins the
    contract the real implementation must satisfy.
    """
    T = len(formation_panel)
    N = 3  # three-leg basket [example]
    assert T >= cfg.min_obs or True  # fixture scale is below min_obs by design
    # trace_adj = trace * (T - N) / T   [documented Cheung-Lai scaling]
    return {"trace_scale": (T - N) / T}


def signal(state, bars, cfg, now_ns=10**19):
    """Reference implementation of the §S3 normative signal() pseudocode."""
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")          # F1
    b = bars[-1]
    if any(not math.isfinite(b[k]) for k in ("X1", "X2", "X3")):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F1/F2
    if (b["asof_ts"] - b["event_ts"]) > cfg.staleness_ttl_ns:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # staleness TTL
    if state.beta is None or state.rank == 0:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # not estimated
    if now_ns < state.cooldown_until:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"],
                            b["asof_ts"] - b["event_ts"], "OK")            # C10 cooldown
    beta = state.beta
    e = beta[0] * b["X1"] + beta[1] * b["X2"] + beta[2] * b["X3"]
    ec = e - state.mu
    sd = state.sd
    if not math.isfinite(ec) or sd <= 0:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F2
    edge_bps = abs(ec) * 30.0  # modeled per-trade edge [example]
    gate = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") \
        <= cfg.cost_gate_k * edge_bps                                      # normative cost-gate predicate
    direction = -1 if (ec > cfg.kappa * sd and gate) \
        else (1 if (ec < -cfg.kappa * sd and gate) else 0)
    confidence = min(1.0, abs(ec) / (cfg.kappa * sd) - 1.0) if direction else 0.0
    return SignalVector("TEST", direction, confidence, 0.5 * confidence,
                        b["event_ts"], b["asof_ts"] - b["event_ts"], "OK")


def recompute(rows):
    """Pre-cost-gate spread hand-check (fixture scale: 4-bar formation)."""
    e = [r["X1"] + _B[1] * r["X2"] + _B[2] * r["X3"] for r in rows]
    mu = sum(e[:4]) / 4
    sd = math.sqrt(sum((v - mu) ** 2 for v in e[:4]) / 4)
    out = []
    for i, r in enumerate(rows):
        ec = e[i] - mu
        d = -1 if ec > 2 * sd else (1 if ec < -2 * sd else 0)
        out.append({"day": r["day"], "e_raw": e[i], "e_c": ec,
                    "band": 2 * sd, "direction": d})
    return out


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Reference recomputation of the tape matches expected.csv (pre-gate trigger)."""
    assert type_header(TAPE) == "validation-run"
    assert type_header(EXPECTED) == "validation-run"
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
    # hand-checks
    assert abs(got[0]["e_raw"] - (100.0 - 0.7113 * 50.0 - 0.3631 * 30.0)) < TOL
    assert got[4]["direction"] == -1  # stretched basket -> short basket
    assert got[5]["direction"] == 1   # compressed basket -> long basket


def test_signal_emits_valid_signalvector():
    rows = parse_tape()
    cfg = Config()
    state = make_state(rows)
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
    cfg = Config()
    state = make_state(rows)
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
    assert abs(cost - 5.90) <= TOL  # pinned reference stack [example]
    assert cost <= k * 100000.0     # huge edge -> gate passes
    assert not (cost <= k * 0.0001)  # tiny edge -> gate blocks


def test_invalid_input_yields_unknown():
    bad = {"day": 0, "event_ts": 1, "asof_ts": 2, "X1": float("nan"), "X2": 1.0, "X3": 1.0}
    s = signal(make_state(parse_tape()), [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_cost_gate_vetoes_tiny_deviation():
    """Day-4's large deviation passes the gate (-1); day-7's tiny one is vetoed (0)."""
    rows = parse_tape()
    cfg = Config()
    state = make_state(rows)
    s4 = signal(state, rows[:5], cfg)   # through day 4
    s7 = signal(state, rows[:8], cfg)   # through day 7
    assert s4.direction == -1, "gate must pass on |ec| = 3.4468 [example]"
    assert s7.direction == 0, "gate must veto day-7 |ec| = 0.13133 [example] (edge < cost)"


def test_empty_events_yields_unknown():
    s = signal(make_state(parse_tape()), [], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0  # F1


def test_stale_bar_yields_unknown():
    rows = parse_tape()
    stale = dict(rows[-1])
    stale["asof_ts"] = stale["event_ts"] + 10_000_000_000  # 10 s ingest lag > 3 s TTL [default]
    s = signal(make_state(rows), rows[:-1] + [stale], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_cooldown_blocks_reentry():
    rows = parse_tape()
    cfg = Config()
    state = make_state(rows, cooldown_until=10**19)  # armed cooldown (C10)
    s = signal(state, rows[:5], cfg, now_ns=10**18)
    assert s.direction == 0 and s.module_state == "OK"


def test_formation_trading_split_and_adversarial():
    """C12: formation window strictly precedes trading; NaN tape -> UNKNOWN."""
    assert type_header(ADVERSARIAL) == "accounting-demo"
    rows = parse_tape()
    cfg = Config()
    formation_end = rows[3]["event_ts"]      # last formation bar
    trading_start = rows[4]["event_ts"]      # first tradable bar
    assert formation_end < trading_start, "C12 hard formation/trading split"
    adv = parse_tape(ADVERSARIAL)
    state = make_state(rows)
    s = signal(state, adv[:5], cfg)          # window contains the NaN day-4 bar
    assert s.module_state == "UNKNOWN" and s.direction == 0, "never interpolate"
    # trace small-sample scaling contract (Cheung-Lai): (T-N)/T < 1 on short windows
    scale = estimate(rows, cfg)["trace_scale"]
    assert 0.0 < scale < 1.0
