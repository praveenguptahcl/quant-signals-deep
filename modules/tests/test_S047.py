"""Acceptance tests for S047 — Bid–ask bounce / Roll spread.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of
the chapter's normative pseudocode, and pins causality, the cost gate,
hand-checked fixture arithmetic, the undefined-estimator branch, and the
estimator/veto role (11 tests).

Run: python3 -m pytest modules/tests/test_S047.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S047_tape.csv"
EXPECTED = FIX / "S047_expected.csv"

TOL = 1e-9  # [default] tolerance on float comparisons


def _num(x):
    """NaN-aware cell reader: blank expected cells encode NaN (warmup)."""
    return float("nan") if x == "" or x is None else float(x)


def _close(a, b):
    a = float(a)
    b = _num(b)
    if math.isnan(a) and math.isnan(b):
        return True
    if math.isnan(a) or math.isnan(b):
        return False
    return abs(a - b) < TOL


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


@dataclass(frozen=True)
class SignalVector:
    symbol: str
    direction: int          # +1 | -1 | 0
    confidence: float       # 0..1
    capital: float          # 0..1
    computed_at: int        # int64 ns UTC
    staleness: int          # ns
    module_state: str       # OK | DEGRADED | UNKNOWN | OFF



def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({"id": r["id"], "event_ts": int(r["event_ts"]),
                     "price": float(r["price"]), "side": r["side"]})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "price": -50.0,
            "side": "ask"}  # negative price


FEATURE_COLS = ["n", "gamma1", "roll_spread", "valid", "dir"]


def roll_stats(prices):
    """Roll (1984) spread estimator: gamma1 = cov(dp_t, dp_{t-1})."""
    dp = [prices[i + 1] - prices[i] for i in range(len(prices) - 1)]
    n = len(dp)
    m = sum(dp) / n
    gamma1 = sum(dp[i] * dp[i + 1] for i in range(n - 1)) / (n - 1) - m * m
    valid = 1 if gamma1 < 0 else 0
    spread = 2.0 * math.sqrt(-gamma1) if valid else float("nan")
    return len(prices), gamma1, spread, valid


def compute_features(rows):
    n, g1, sp, valid = roll_stats([r["price"] for r in rows])
    # estimator/veto role: direction is always 0 — the output is the spread
    # estimate itself (gross harvesting edge is bounded by the spread).
    return [{"id": "summary", "n": n, "gamma1": g1, "roll_spread": sp,
             "valid": valid, "dir": 0}]


@dataclass
class Config:
    min_trades: int = 20         # minimum trades for the estimate [default]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: bounce-harvest attempt (vetoed by the estimate)."""
    spread_bps = 2.00   # pay the full quoted spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 0.50   # concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S047 reference stub).

    Estimator/veto role: emits direction 0 always. A valid positive spread
    estimate vetoes bounce-harvesting (edge bounded by the spread); an
    undefined estimate (gamma1 >= 0) is UNKNOWN-grade missing information.
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["price"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    if len(evs) < cfg.min_trades:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    _, g1, _, valid = roll_stats([x["price"] for x in evs])
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    # edge is bounded by the spread itself -> the gate always vetoes harvest
    edge_bps = 0.5  # sub-spread edge at best [example]
    ok = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    _ = ok  # documented: harvest is uneconomic; the module is a veto
    return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")



# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    rows = tape()
    feats = compute_features(rows)
    exp = load_csv(EXPECTED)
    assert len(feats) == len(exp), (len(feats), len(exp))
    for f, w in zip(feats, exp):
        assert str(f["id"]) == str(w["id"]), (f["id"], w["id"])
        for col in FEATURE_COLS:
            assert _close(f[col], w[col]), (f["id"], col)

    f = feats[0]
    # 60-trade tape (seed 47): gamma1 negative -> valid Roll estimate
    assert f["id"] == "summary" and f["n"] == 60, f
    assert abs(f["gamma1"] - (-0.0002208)) < 1e-7, f
    assert abs(f["roll_spread"] - 0.0297) < 1e-4, f
    assert f["valid"] == 1 and f["dir"] == 0
    # undefined branch: non-negative autocovariance -> estimator undefined
    n2, g2, sp2, v2 = roll_stats([50.0] * 10)
    assert v2 == 0 and sp2 != sp2  # NaN spread
    # identity check: 2*sqrt(-gamma1) by hand
    assert abs(f["roll_spread"] - 2.0 * math.sqrt(0.0002208)) < 1e-6



def test_signal_emits_valid_signalvector():
    rows = tape()
    cfg, state = Config(), dict()
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = tape()
    cfg, state = Config(), dict()
    for i in range(len(rows) - 1):
        s = signal(state, rows[: i + 1], cfg)
        fill_event_ts = event_ts(rows[i + 1])  # earliest possible fill: next event
        assert fill_event_ts > s.computed_at, "signal-bar fill at row %d" % i


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert cost > 0
    assert cost <= k * 100.0   # huge edge -> gate passes
    assert not (cost <= k * 0.01)  # tiny edge -> gate blocks


def test_invalid_input_yields_unknown():
    s = signal(dict(), [bad_event()], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0


def test_empty_events_yields_unknown():
    """F1: no events at all -> UNKNOWN, never a fabricated signal."""
    s = signal(dict(), [], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.confidence == 0.0 and s.capital == 0.0


def test_too_few_trades_waits():
    """n < min_trades: healthy module, no information — wait, direction 0."""
    s = signal(dict(), tape()[:5], Config())
    assert s.module_state == "OK"
    assert s.direction == 0 and s.confidence == 0.0 and s.capital == 0.0


def trend_rows(n=25, start=50.0, step=0.25):
    """Synthetic constant-drift tape: zero first-order autocovariance [example].
    step is binary-exact (0.25) so drift diffs carry no float noise."""
    base = 1757000000000000000
    return [{"id": "u%d" % i, "event_ts": base + i * 1_000_000_000,
             "price": start + i * step, "side": "ask"} for i in range(n)]


def test_trending_tape_is_undefined_no_information():
    """gamma1 >= 0 (informed/trending flow): estimator undefined -> OK, dir 0."""
    rows = trend_rows()
    n, g1, sp, valid = roll_stats([r["price"] for r in rows])
    assert n == 25
    assert valid == 0 and g1 >= 0 and sp != sp  # NaN spread: undefined
    s = signal(dict(), rows, Config())
    assert s.module_state == "OK"
    assert s.direction == 0 and s.confidence == 0.0


def test_pure_alternation_identity():
    """Roll identity pinned: pure bid/ask alternation -> spread == 2*step.
    41 prices -> 40 diffs (20 up, 20 down), so the mean-adjusted covariance is
    exact: gamma1 = -0.0004, spread = 0.04."""
    px = [50.01 if i % 2 == 0 else 49.99 for i in range(41)]  # [example]
    n, g1, sp, valid = roll_stats(px)
    assert n == 41 and valid == 1
    assert abs(g1 - (-0.0004)) < 1e-12, g1  # [default] tolerance
    assert abs(sp - 0.04) < 1e-9, sp        # 2*sqrt(0.0004) == 2*0.02
    assert abs(sp - 2.0 * math.sqrt(0.0004)) < 1e-12


def test_deterministic_recompute():
    """Estimator is pure arithmetic: bit-identical across recomputations."""
    rows = tape()
    prices = [r["price"] for r in rows]
    a = roll_stats(prices)
    b = roll_stats(prices)
    assert a == b
    assert compute_features(rows) == compute_features(rows)


def test_harvest_veto_consistency():
    """Estimator/veto role: direction 0 and confidence 0 on every event,
    even when the spread estimate is valid (no harvest entries, ever)."""
    rows = tape()
    cfg = Config()
    for i in range(len(rows)):
        s = signal(dict(), rows[: i + 1], cfg)
        assert s.direction == 0, i
        assert s.confidence == 0.0 and s.capital == 0.0, i
