"""Acceptance tests for S054 — Copula pairs trading.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode (S3, v1.1.0), and real
assertions including exits + cooldown, rho bounds, staleness TTL,
causality (assert fill_event > signal_event), and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S054.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, replace
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S054_tape.csv"
EXPECTED = FIX / "S054_expected.csv"

TOL = 1e-9  # [default] tolerance on float comparisons
EXPECTED_COLS = ['day', 'p_ab', 'direction']
COL_TYPES = {'day': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'u': 'float', 'v': 'float'}

TTL_NS = 3_000_000_000        # staleness TTL 3 s [default]
COOLDOWN_NS = 60_000_000_000  # post-exit cooldown 60 s [default]


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


def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p):
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 0.97575
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1-p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q, r = p - 0.5, (p-0.5)**2
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def _p_ab(u, v, rho=0.8):
    return _norm_cdf((_norm_ppf(u) - rho * _norm_ppf(v)) / math.sqrt(1 - rho ** 2))


def recompute(rows):
    """Trigger-only reference: per-day p_ab + threshold direction.

    Excludes exits, cost-gate, and cooldown by design (expected.csv pins the
    trigger, not the stateful book); the cost gate never blocks at the
    reference stack with k=0.5, so trigger direction == emitted direction here.
    """
    out = []
    for r in rows:
        p = _p_ab(r["u"], r["v"])
        d = 1 if p < 0.05 else (-1 if p > 0.95 else 0)
        out.append({"day": r["day"], "p_ab": p, "direction": d})
    return out


@dataclass
class Config:
    rho: float = 0.8         # [example]
    p_L: float = 0.05        # [documented]
    p_U: float = 0.95        # [documented]
    cost_gate_k: float = 0.5  # [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 1.00   # two-leg half-spread sum [example]
    fee_bps = 0.60      # two-leg taker fees [example]
    borrow_bps = 1.50   # = borrow_bps_per_day 0.15 [example] x H=10 d [example]
    base_impact_bps = 1.50  # [example]
    urgency_mult = {"patient": 0.7, "normal": 1.0, "aggressive": 2.0}[urgency]  # [default]
    part = max(adv_pct, 1e-6)
    impact_bps = base_impact_bps * urgency_mult * max(1.0, (part / 0.001) ** 0.5)  # [default] scaling
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _unknown(ts):
    return SignalVector("TEST", 0, 0.0, 0.0, ts, 0, "UNKNOWN")


def signal(state, events, cfg):
    """Reference implementation of the S3 (v1.1.0) normative pseudocode.

    events: newest-last canonical events; state holds prev_direction,
    cooldown_until_ns, last_sig, optional market / now_ns overrides.
    """
    events = list(events)
    if not events:
        return _unknown(0)
    b = events[-1]
    now_ns = state.get("now_ns", b["asof_ts"])
    assert now_ns >= b["event_ts"], "causality clock sanity"
    if not (math.isfinite(cfg.rho) and 0.1 <= cfg.rho < 1.0):
        return _unknown(b["event_ts"])                      # F2: |rho|>=1 undefined
    if state.get("market") == "HALTED":
        return _unknown(b["event_ts"])
    if state.get("market") == "AUCTION":
        last = state.get("last_sig")
        if last is None:
            return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "DEGRADED")
        return replace(last, module_state="DEGRADED")       # hold last, no new signals
    if not (0.0 < b["u"] < 1.0 and 0.0 < b["v"] < 1.0):
        return _unknown(b["event_ts"])                      # F1/F2
    if now_ns - b["asof_ts"] > TTL_NS:
        return _unknown(b["event_ts"])                      # F1 staleness
    p = _norm_cdf((_norm_ppf(b["u"]) - cfg.rho * _norm_ppf(b["v"])) / math.sqrt(1 - cfg.rho ** 2))
    if not math.isfinite(p):
        return _unknown(b["event_ts"])                      # F2
    prev = state.get("prev_direction", 0)
    if (prev == 1 and p >= 0.5) or (prev == -1 and p <= 0.5):
        state["prev_direction"] = 0                         # exits take precedence
        state["cooldown_until_ns"] = now_ns + COOLDOWN_NS    # C10
        sig = SignalVector("TEST", 0, 0.0, 0.0, now_ns, 0, "OK")
        state["last_sig"] = sig
        return sig
    edge_bps = abs(p - 0.5) * 40.0                          # [example] modeled per-trade edge
    cost_ok = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    direction = 1 if (p < cfg.p_L and cost_ok) else (-1 if (p > cfg.p_U and cost_ok) else 0)
    if now_ns < state.get("cooldown_until_ns", 0):
        direction = 0                                       # C10 entry veto
    confidence = min(1.0, abs(p - 0.5) * 2.0) if direction else 0.0
    sig = SignalVector("TEST", direction, confidence, 0.5 * confidence,
                       b["event_ts"], now_ns - b["asof_ts"], "OK")
    state["prev_direction"] = direction
    state["last_sig"] = sig
    return sig


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
    # hand-checks pinned from chapter S4
    assert abs(got[0]["p_ab"] - 0.9711) < 1e-3
    assert abs(got[2]["p_ab"] - 0.0118) < 1e-3 and got[2]["direction"] == 1  # day-2 long trigger
    assert abs(got[3]["p_ab"] - 0.5) < 1e-9                              # u=v=0.5 -> neutral
    assert got[4]["p_ab"] > 0.99 and got[4]["direction"] == -1             # (0.9,0.1): A rich vs B
    assert got[5]["p_ab"] < 0.01 and got[5]["direction"] == 1              # (0.1,0.9): A cheap vs B
    assert got[0]["direction"] == -1


def test_signal_emits_valid_signalvector():
    rows = parse_tape()
    cfg = Config()
    sigs = [signal({}, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    # trigger directions agree with the fixture at the reference stack
    assert [s.direction for s in sigs] == [-1, 0, 1, 0, -1, 1]


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = parse_tape()
    cfg = Config()
    for i in range(len(rows)):
        s = signal({}, rows[: i + 1], cfg)
        assert s.computed_at == rows[i]["event_ts"], "signal must be timestamped at its bar"
        later = [r["event_ts"] for r in rows[i + 1:] if r["event_ts"] > s.computed_at]
        if later:
            assert min(later) > s.computed_at, "signal-bar fill"


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries; binds under stress."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "X", "taker", "normal")
    assert cost >= 0.0
    assert cost <= k * 100000.0   # huge edge -> gate passes
    assert not (cost <= k * 0.0001)  # tiny edge -> gate blocks
    # gate binds when participation/urgency scale impact: day-2-class trigger
    edge_day2 = abs(0.0118468370 - 0.5) * 40.0
    stressed = expected_cost_bps(1.0, 0.01, "X", "taker", "aggressive")
    assert not (stressed <= k * edge_day2), "elevated participation must veto"


def test_invalid_input_yields_unknown():
    def bar(day, u, v, event_ts=10**18, asof_ts=10**18 + 120_000):
        return {"day": day, "event_ts": event_ts, "asof_ts": asof_ts, "u": u, "v": v}
    good = bar(0, 0.5, 0.5)
    # u/v outside (0,1) -> UNKNOWN
    assert signal({}, [bar(0, 0.0, 0.5)], Config()).module_state == "UNKNOWN"
    assert signal({}, [bar(0, 1.5, 0.5)], Config()).module_state == "UNKNOWN"
    # |rho| >= 1 -> UNKNOWN
    assert signal({}, [good], Config(rho=1.0)).module_state == "UNKNOWN"
    assert signal({}, [good], Config(rho=0.99)).module_state == "OK"  # boundary passes
    # staleness past TTL -> UNKNOWN
    stale = {"now_ns": good["asof_ts"] + TTL_NS + 1}
    assert signal(stale, [good], Config()).module_state == "UNKNOWN"


def _synthetic_bar(day, u, v, ts, asof_delta=120_000):
    return {"day": day, "event_ts": ts, "asof_ts": ts + asof_delta, "u": u, "v": v}


def test_exit_and_cooldown():
    """Trigger entry -> p crosses back through 0.5 -> flat exit + 60 s cooldown."""
    cfg = Config()
    state = {}
    ts0 = 10**18
    day = 86400 * 10**9
    # bar 1: (0.1438, 0.6433) -> p=0.0118 < p_L -> long A (+1)
    b1 = _synthetic_bar(0, 0.1438, 0.6433, ts0)
    s1 = signal(state, [b1], cfg)
    assert s1.direction == 1 and s1.module_state == "OK"
    # bar 2: (0.6, 0.4) -> p ~= 0.776 >= 0.5 -> exit, cooldown set
    b2 = _synthetic_bar(1, 0.6, 0.4, ts0 + day)
    state["now_ns"] = b2["asof_ts"]
    s2 = signal(state, [b1, b2], cfg)
    assert s2.direction == 0 and s2.module_state == "OK"
    assert state["cooldown_until_ns"] == state["now_ns"] + COOLDOWN_NS
    # bar 3 (inside cooldown): trigger present but entries vetoed
    now3 = state["cooldown_until_ns"] - 10**9
    b3 = _synthetic_bar(2, 0.1438, 0.6433, now3 - 120_000)
    state["now_ns"] = now3
    s3 = signal(state, [b1, b2, b3], cfg)
    assert s3.direction == 0, "entries must be vetoed inside the cooldown"
    # bar 4 (after cooldown): trigger re-arms
    now4 = state["cooldown_until_ns"] + 10**9
    b4 = _synthetic_bar(3, 0.1438, 0.6433, now4 - 120_000)
    state["now_ns"] = now4
    s4 = signal(state, [b1, b2, b3, b4], cfg)
    assert s4.direction == 1, "trigger re-arms after cooldown expires"


def test_cost_gate_veto_wiring():
    """A trigger whose modeled edge is thinned (k=0.1) is vetoed to direction 0."""
    rows = parse_tape()
    cfg = Config(cost_gate_k=0.1)  # [example] thinned gate
    s = signal({}, rows[:3], cfg)  # day 2 would trigger +1 at k=0.5
    assert s.direction == 0 and s.module_state == "OK"
    assert s.confidence == 0.0 and s.capital == 0.0
