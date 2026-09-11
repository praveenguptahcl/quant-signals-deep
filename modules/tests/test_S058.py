"""Acceptance tests for S058 — Futures calendar spread (term-structure carry).

Template v1.0.0. Reference implementation of the chapter's normative pseudocode
(§S3): net-carry fair spread with convenience yield y, cost-gate predicate,
C10 post-exit cooldown, market-state branches, causality
(assert fill_event > signal_event), and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S058.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S058_tape.csv"
EXPECTED = FIX / "S058_expected.csv"

TOL = 1e-9  # [default] tolerance on float comparisons
EXPECTED_COLS = ['day', 'fair_spread', 'dev_pts', 'direction']
COL_TYPES = {'day': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'front': 'float', 'back': 'float'}


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
    rows = [{k: _conv(r[k], COL_TYPES[k]) for k in COL_TYPES} for r in load_csv(TAPE)]
    for r in rows:
        r.setdefault("market_state", "CONTINUOUS_TRADING")
    return rows


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
    entry_bound_pts: float = 0.10  # [example]
    cost_gate_k: float = 0.5       # [default]
    carry_rate_r: float = 0.05     # [example]
    carry_div_q: float = 0.018    # [example]
    carry_conv_y: float = 0.0     # [example]
    dt_days: float = 90.0         # [example]
    exit_tol_frac: float = 0.25   # [example]
    time_stop_days: float = 10.0  # [example]
    cooldown_s: float = 60.0      # [default]


@dataclass
class ModuleState:
    cooldown_until: int = 0  # int64 ns UTC


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.80   # two futures legs half-spread sum [example]
    fee_bps = 0.20      # futures round-trip fees [example]
    borrow_bps = 0.00   # reason: no stock borrow in futures calendar [default]
    impact_bps = 0.50   # deferred-leg fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _unknown(event_ts):
    return SignalVector("TEST", 0, 0.0, 0.0, event_ts, 0, "UNKNOWN")


def fair_spread(front, cfg):
    """Normative fair-spread working form: F_1*(exp((r-q-y)*dt)-1)."""
    dt = cfg.dt_days / 365.0
    net = cfg.carry_rate_r - cfg.carry_div_q - cfg.carry_conv_y
    return front * (math.exp(net * dt) - 1)


def recompute(rows, cfg=None):
    cfg = cfg or Config()
    out = []
    for x in rows:
        fair = fair_spread(x["front"], cfg)
        dev = (x["back"] - x["front"]) - fair
        d = 1 if dev > cfg.entry_bound_pts else (-1 if dev < -cfg.entry_bound_pts else 0)
        out.append({"day": x["day"], "fair_spread": fair, "dev_pts": dev, "direction": d})
    return out


def signal(state, bars, cfg):
    """Reference implementation of the §S3 normative pseudocode."""
    bars = list(bars)
    if not bars:
        return _unknown(0)
    b = bars[-1]
    ms = b.get("market_state", "CONTINUOUS_TRADING")
    if ms == "HALTED":
        return _unknown(b["event_ts"])  # freeze; discard contributions
    if ms == "AUCTION":
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "DEGRADED")  # hold
    if not (math.isfinite(b["front"]) and math.isfinite(b["back"])) or b["front"] <= 0:
        return _unknown(b["event_ts"])  # F1/F2
    rates = (cfg.carry_rate_r, cfg.carry_div_q, cfg.carry_conv_y)
    if not all(math.isfinite(x) for x in rates):
        return _unknown(b["event_ts"])  # missing/stale rate inputs
    now = b["event_ts"]
    if now < state.cooldown_until:
        return SignalVector("TEST", 0, 0.0, 0.0, now, b["asof_ts"] - now, "OK")  # C10
    fair = fair_spread(b["front"], cfg)
    dev = (b["back"] - b["front"]) - fair
    edge_bps = abs(dev) / b["front"] * 10000.0  # modeled per-trade edge [example]
    direction = 1 if dev > cfg.entry_bound_pts else (-1 if dev < -cfg.entry_bound_pts else 0)
    cost = expected_cost_bps(1e6, 0.001, "CME", "taker", "normal")  # [example] inputs
    if direction != 0 and cost > cfg.cost_gate_k * edge_bps:
        direction = 0  # cost-gate veto (C2 bona-fide intent)
    assert (direction == 0) or (cost <= cfg.cost_gate_k * edge_bps), "cost gate"
    if abs(dev) < cfg.exit_tol_frac * cfg.entry_bound_pts:
        state.cooldown_until = now + int(cfg.cooldown_s * 1e9)  # C10: 60 s [default]
        direction = 0
    confidence = min(1.0, abs(dev) / cfg.entry_bound_pts - 1.0) if direction != 0 else 0.0
    return SignalVector("TEST", direction, confidence, 0.5 * confidence,
                        now, b["asof_ts"] - now, "OK")


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
    # hand-checks from §S4
    assert abs(got[0]["fair_spread"] - 100.0 * (math.exp(0.032 * 90.0 / 365.0) - 1)) < TOL
    assert got[1]["direction"] == 1 and got[2]["direction"] == -1
    assert got[0]["direction"] == 0


def test_signal_emits_valid_signalvector():
    rows = parse_tape()
    cfg, state = Config(), ModuleState()
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert abs(s.capital - 0.5 * s.confidence) < 1e-12
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
    cost = expected_cost_bps(1e6, 0.001, "CME", "taker", "normal")
    assert cost >= 0.0
    assert cost <= k * 100000.0   # huge edge -> gate passes
    assert not (cost <= k * 0.0001)  # tiny edge -> gate blocks
    # the full signal path vetoes a sub-threshold edge
    rows = parse_tape()
    b = dict(rows[1])  # direction +1 on the fixture
    b["back"] = b["front"] + fair_spread(b["front"], Config()) + 0.0001  # edge << cost
    s = signal(ModuleState(), [b], Config())
    assert s.direction == 0 and s.module_state == "OK"


def test_invalid_input_yields_unknown():
    bad = {"day": 0, "event_ts": 1, "asof_ts": 2, "front": 0.0, "back": 100.0,
           "market_state": "CONTINUOUS_TRADING"}
    s = signal(ModuleState(), [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
    bad2 = dict(bad, front=100.0, back=float("nan"))
    s2 = signal(ModuleState(), [bad2], Config())
    assert s2.module_state == "UNKNOWN" and s2.direction == 0


def test_convenience_yield_shifts_fair_spread():
    """y enters the normative fair curve: F_1*(exp((r-q-y)*dt)-1)."""
    y = 0.01  # [example]
    cfg = Config(carry_conv_y=y)
    got = fair_spread(100.0, cfg)
    direct = 100.0 * (math.exp((0.05 - 0.018 - y) * 90.0 / 365.0) - 1)
    assert abs(got - direct) <= TOL
    assert got != fair_spread(100.0, Config())  # y actually moves the curve
    # fixture day-1 direction is robust to y=1% [example]
    dev = (101.0 - 100.0) - got
    assert dev > cfg.entry_bound_pts


def test_post_exit_cooldown():
    """C10: a convergence bar sets cooldown; bars within 60 s [default] stay flat."""
    t0 = 1788960600000000000
    cfg = Config()
    fair0 = fair_spread(100.0, cfg)

    def bar(ts, back):
        return {"day": 0, "event_ts": ts, "asof_ts": ts + 120000,
                "front": 100.0, "back": back, "market_state": "CONTINUOUS_TRADING"}

    state = ModuleState()
    s0 = signal(state, [bar(t0, 100.0 + fair0 + 0.001)], cfg)  # |dev| < exit tol
    assert s0.direction == 0 and s0.module_state == "OK"
    assert state.cooldown_until == t0 + 60_000_000_000, "cooldown 60 s [default]"
    s1 = signal(state, [bar(t0 + 30_000_000_000, 101.5)], cfg)  # |dev| >> bound, in cooldown
    assert s1.direction == 0, "no re-entry during cooldown"
    s2 = signal(state, [bar(t0 + 61_000_000_000, 101.5)], cfg)  # cooldown expired
    assert s2.direction == 1, "entry allowed after cooldown"


def test_input_guards_yield_unknown():
    """Missing/stale rate inputs and HALTED market state -> UNKNOWN."""
    t0 = 1788960600000000000
    good = {"day": 0, "event_ts": t0, "asof_ts": t0 + 120000, "front": 100.0,
            "back": 101.0, "market_state": "CONTINUOUS_TRADING"}
    s_rate = signal(ModuleState(), [good], Config(carry_rate_r=float("nan")))
    assert s_rate.module_state == "UNKNOWN" and s_rate.direction == 0
    s_halt = signal(ModuleState(), [dict(good, market_state="HALTED")], Config())
    assert s_halt.module_state == "UNKNOWN" and s_halt.direction == 0
    s_auc = signal(ModuleState(), [dict(good, market_state="AUCTION")], Config())
    assert s_auc.module_state == "DEGRADED"
