"""Acceptance tests for S052 — Kalman-filter dynamic hedge ratio.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode (S3), and real assertions
including causality (assert fill_event > signal_event), the executable
cost-gate predicate, invalid -> UNKNOWN, cooldown suppression, halt/staleness
handling, and config guards.

Run: python3 -m pytest modules/tests/test_S052.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S052_tape.csv"
EXPECTED = FIX / "S052_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['ev', 'beta', 'innov', 'sqrtF', 'z', 'direction']
COL_TYPES = {'ev': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'x': 'float', 'y': 'float'}


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
    """S0.2 Config dataclass — single source of truth for tunables."""
    z_entry: float = 2.0           # [default] calibrate (recipe R1)
    cost_gate_k: float = 0.5       # [default] calibrate (recipe R1)
    q_beta: float = 3.021e-6       # [example] fixture instance; calibrate (recipe R2)
    R: float = 0.10610             # [example] fixture instance; calibrate (recipe R2)
    beta0: float = 1.20            # [default] diffuse prior
    P0: float = 0.04               # [default] diffuse prior
    cooldown_s: float = 60.0       # [default] C10 post-exit cooldown
    staleness_ttl_s: float = 3.0   # [default] live-event staleness TTL
    exit_band: float = 0.5         # [example]
    edge_bps_per_sigma: float = 2.0  # [example] modeled edge per |z|


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Callable cost model — reference stack for S052 (S2 COST block)."""
    spread_bps = 0.50   # two-leg half-spread sum [example]
    fee_bps = 0.60      # two-leg taker fees [example]
    borrow_bps = 2.00   # short-leg borrow amortized [example]
    impact_bps = 1.00   # two-leg async fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def kf_replay(bars, cfg, beta=None, P=None):
    """Normative 1-state Kalman recursion over bars; returns final (beta, P, e, F)."""
    beta = cfg.beta0 if beta is None else beta
    P = cfg.P0 if P is None else P
    e = F = 0.0
    for r in bars:
        Pp = P + cfg.q_beta
        e = r["y"] - beta * r["x"]            # innovation
        F = r["x"] ** 2 * Pp + cfg.R          # forecast variance
        K = Pp * r["x"] / F                   # Kalman gain
        beta = beta + K * e
        P = (1 - K * r["x"]) * Pp
    return beta, P, e, F


def recompute(rows, cfg=None):
    """Per-bar recomputation of the fixture tape -> rows matching expected.csv."""
    cfg = cfg or Config()
    out = []
    for i, r in enumerate(rows):
        beta, P, e, F = kf_replay(rows[: i + 1], cfg)
        z = e / math.sqrt(F)
        d = -1 if z >= cfg.z_entry else (1 if z <= -cfg.z_entry else 0)
        out.append({"ev": r["ev"], "beta": beta, "innov": e,
                    "sqrtF": math.sqrt(F), "z": z, "direction": d})
    return out


def signal(state, bars, cfg, asof_now=None):
    """Normative signal() per S3: guards -> KF -> cost gate -> SignalVector."""
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")          # F1
    b = bars[-1]
    if not math.isfinite(b["x"]) or not math.isfinite(b["y"]):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F1
    if b["x"] == 0:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F2
    if not (math.isfinite(cfg.z_entry) and cfg.z_entry > 0):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F2 config guard
    if not (math.isfinite(cfg.q_beta) and cfg.q_beta >= 0
            and math.isfinite(cfg.R) and cfg.R > 0):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F2 config guard
    market = state.get("market_state", "CONTINUOUS_TRADING")               # S0.5
    if market == "HALTED":
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    if market == "CLOSED":
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "OFF")
    if market == "AUCTION":
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "DEGRADED")
    now = b["asof_ts"] + 1_000_000 if asof_now is None else asof_now       # injectable clock
    if now - b["asof_ts"] > cfg.staleness_ttl_s * 1e9:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # staleness TTL
    # priors: continue from state if it holds the previous prefix, else from cfg priors
    prior = (state.get("beta"), state.get("P")) if state.get("_n") == len(bars) - 1 else (None, None)
    beta, P, e, F = kf_replay(bars, cfg, *prior)
    z = e / math.sqrt(F)
    if not math.isfinite(z):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F2
    edge_bps = abs(z) * cfg.edge_bps_per_sigma                             # [example]
    cost_ok = (expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
               <= cfg.cost_gate_k * edge_bps)                              # normative cost-gate predicate
    in_cooldown = now < state.get("cooldown_until", 0)                      # C10
    raw_dir = -1 if z >= cfg.z_entry else (1 if z <= -cfg.z_entry else 0)
    direction = 0 if (in_cooldown or not cost_ok) else raw_dir
    confidence = min(1.0, abs(z) / (2.0 * cfg.z_entry)) if direction else 0.0
    state.update({"beta": beta, "P": P, "_n": len(bars)})
    return SignalVector("TEST", direction, confidence, 0.5 * confidence,   # [default] capital
                        b["event_ts"], now - b["asof_ts"], "OK")


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
    assert got[10]["direction"] == -1  # large positive innovation -> short spread
    assert got[11]["direction"] == 1   # large negative innovation -> long spread
    # hand-check bar 0: beta=1.20, P=0.04, x=4.1161, y=4.8015 (prior beta too high)
    Pp = 0.04 + 3.021e-6
    e0 = 4.8015 - 1.20 * 4.1161
    F0 = 4.1161 ** 2 * Pp + 0.10610
    assert abs(got[0]["innov"] - e0) < 1e-12
    assert abs(got[0]["beta"] - (1.20 + (Pp * 4.1161 / F0) * e0)) < 1e-12


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
    bad = {"ev": 0, "event_ts": 1, "asof_ts": 2, "x": 0.0, "y": 1.0}
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_cooldown_suppresses_reentry():
    """C10: entries suppressed while now() < cooldown_until."""
    rows = parse_tape()
    cfg = Config()
    state = {}
    s1 = signal(state, rows[:11], cfg)  # bar 10: large positive innovation
    assert s1.direction == -1, "fixture bar 10 must fire short"
    state["cooldown_until"] = rows[10]["event_ts"] + 10 ** 12  # far future
    s2 = signal(state, rows[:11], cfg, asof_now=rows[10]["asof_ts"] + 1_000_000)
    assert s2.direction == 0 and s2.module_state == "OK"
    assert s2.confidence == 0.0


def test_halt_and_staleness_yield_unknown():
    rows = parse_tape()
    cfg = Config()
    s = signal({"market_state": "HALTED"}, rows[:5], cfg)
    assert s.module_state == "UNKNOWN" and s.direction == 0
    stale_now = rows[4]["asof_ts"] + 60 * 10 ** 9  # 60 s > 3 s TTL
    s = signal({}, rows[:5], cfg, asof_now=stale_now)
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_invalid_config_yields_unknown():
    rows = parse_tape()
    s = signal({}, rows[:5], Config(z_entry=-1.0))
    assert s.module_state == "UNKNOWN" and s.direction == 0
    s = signal({}, rows[:5], Config(R=-0.5))
    assert s.module_state == "UNKNOWN" and s.direction == 0
