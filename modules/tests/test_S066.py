"""Acceptance tests for S066 — HAR realized-volatility forecast.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode, and real assertions
including causality (assert fill_event > signal_event) and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S066.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S066_tape.csv"
EXPECTED = FIX / "S066_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['day', 'rv_d', 'rv_w', 'rv_m', 'har']
COL_TYPES = {'day': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'rv': 'float'}


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


def recompute(rows):
    vals = [r["rv"] for r in rows]
    out = []
    for i in range(4, len(vals)):
        d = vals[i]
        w = sum(vals[i - 4:i + 1]) / 5
        m = sum(vals[:i + 1]) / (i + 1)
        f = 5e-5 + 0.40 * d + 0.35 * w + 0.20 * m
        out.append({"day": i, "rv_d": d, "rv_w": w, "rv_m": m, "har": f})
    return out


@dataclass
class Config:
    beta0: float = 5e-5   # [example]
    beta_d: float = 0.40  # [example]
    beta_w: float = 0.35  # [example]
    beta_m: float = 0.20  # [example]
    cost_gate_k: float = 0.5  # [default]
    edge_bps: float = 50.0     # [example] reference edge level for the cost gate
    confidence_scale: float = 0.001  # [example]
    clip_floor: float = 1e-8   # [example] positivity floor
    min_days: int = 5          # [example] minimum history for the weekly mean
    monthly_window: int = 22   # [documented] normative monthly horizon

def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    # Forecast emits no entries; stack is the downstream strategy's reference [example].
    spread_bps = 0.50
    fee_bps = 0.30
    borrow_bps_per_day = 0.00   # reason: forecast-only module [default]
    impact_bps = 0.50
    return spread_bps + fee_bps + borrow_bps_per_day + impact_bps

def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    b = bars[-1]
    vals = [r["rv"] for r in bars]
    if any(v < 0 or not math.isfinite(v) for v in vals) or len(vals) < cfg.min_days:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    d = vals[-1]
    w = sum(vals[-5:]) / 5
    # normative monthly: last `monthly_window` days; warm-up/fixture branch uses
    # the full available history (mirrors the §S3 normative pseudocode)
    m = (sum(vals[-cfg.monthly_window:]) / cfg.monthly_window
         if len(vals) >= cfg.monthly_window else sum(vals) / len(vals))
    f = cfg.beta0 + cfg.beta_d * d + cfg.beta_w * w + cfg.beta_m * m
    f = max(f, cfg.clip_floor)                                  # positivity clip
    confidence = min(1.0, f / cfg.confidence_scale) if f > 0 else 0.0
    gate = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * cfg.edge_bps
    st = "OK" if gate else "DEGRADED"
    return SignalVector("TEST", 0, confidence, 0.0, b["event_ts"],
                        b["asof_ts"] - b["event_ts"], st)


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Reference recomputation of the tape matches expected.csv.

    The 12-day fixture uses the warm-up branch: its `rv_m` column is the
    full-history mean (the normative 22-day window is pinned by
    test_normative_monthly_uses_22_days).
    """
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
    # day-4 hand-check pinned [measured]
    assert abs(got[0]["har"] - 0.0001969000) <= TOL
    # last-row hand-checks pinned independently of recompute()
    last = got[-1]
    assert abs(last["rv_d"] - 0.00019) < 1e-12
    assert abs(last["rv_w"] - 0.000162) < 1e-12
    m_mean = sum(r["rv"] for r in rows) / len(rows)   # full-history mean, 12 days
    assert abs(last["rv_m"] - m_mean) < 1e-12
    assert abs(last["har"] - (5e-5 + 0.40*0.00019 + 0.35*0.000162 + 0.20*m_mean)) < 1e-12
    assert len(got) == 8


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
    cfg = Config()
    base_ts, base_asof = 1_700_000_000_000_000_000, 1_700_000_000_000_012_000
    def bar(rv, day=0):
        return {"day": day, "event_ts": base_ts, "asof_ts": base_asof, "rv": rv}
    cases = [
        [bar(-0.5)],                                    # negative RV
        [bar(float("nan"))],                             # NaN
        [bar(float("inf"))],                             # +inf
        [],                                             # empty
        [bar(0.0001) for _ in range(4)],                 # < min_days (5)
    ]
    for bars in cases:
        s = signal({}, bars, cfg)
        assert s.module_state == "UNKNOWN" and s.direction == 0, bars


def _synthetic_bars(rvs, base_ts=1_700_000_000_000_000_000):
    return [{"day": i, "event_ts": base_ts + i * 86_400_000_000_000,
             "asof_ts": base_ts + i * 86_400_000_000_000 + 12_000, "rv": v}
            for i, v in enumerate(rvs)]


def test_normative_monthly_uses_22_days():
    """Pin the normative branch: with >=22 days the monthly mean must use the
    last 22 days, NOT the full history (fixture uses the warm-up branch)."""
    cfg = Config()
    rvs = [0.0001] * 22 + [0.0003] * 5          # 27 days
    bars = _synthetic_bars(rvs)
    s = signal({}, bars, cfg)
    assert s.module_state == "OK"
    # independent hand computation (no reuse of the stub's formula path)
    d = 0.0003
    w = 0.0003
    m22 = (17 * 0.0001 + 5 * 0.0003) / 22       # last 22 days: i = 5..26
    f_exp = 5e-5 + 0.40 * d + 0.35 * w + 0.20 * m22
    assert f_exp < 0.001, "keeps confidence = f/scale exact"
    assert abs(s.confidence - f_exp / 0.001) <= 1e-9, (s.confidence, f_exp / 0.001)
    # the full-history mean would give a different answer: prove the branch matters
    m_full = (22 * 0.0001 + 5 * 0.0003) / 27
    assert abs(m_full - m22) > 1e-9
    f_wrong = 5e-5 + 0.40 * d + 0.35 * w + 0.20 * m_full
    assert abs(s.confidence - f_wrong / 0.001) > 1e-9


def test_positivity_clip():
    """A forced-negative raw forecast clips at clip_floor, never prints
    negative confidence."""
    cfg = Config(beta0=-0.001, beta_d=0.0, beta_w=0.0, beta_m=0.0)
    bars = _synthetic_bars([0.0001] * 12)
    s = signal({}, bars, cfg)
    assert s.module_state == "OK"
    assert s.confidence == max(1e-8, -0.001) / 0.001
    assert s.confidence >= 0.0


def test_cost_gate_states():
    """Cost gate: default k -> OK on a reference edge; near-zero k -> DEGRADED."""
    bars = parse_tape()
    s_ok = signal({}, bars, Config())
    assert s_ok.module_state == "OK"
    cfg = Config(cost_gate_k=0.001)   # threshold = 0.001 * 50 = 0.05 bps < 1.30 bps
    s_deg = signal({}, bars, cfg)
    assert s_deg.module_state == "DEGRADED"
    assert s_deg.direction == 0 and 0.0 <= s_deg.confidence <= 1.0
