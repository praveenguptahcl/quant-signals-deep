"""Acceptance tests for S027 — End-of-day momentum / last-hour drift.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S027.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S027_tape.csv"
EXPECTED = FIX / "S027_expected.csv"

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
                     "p930": float(r["p930"]), "p1530": float(r["p1530"]),
                     "pclose": float(r["pclose"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "p930": -1.0, "p1530": 100.0, "pclose": 100.0}


FEATURE_COLS = ["r_first", "r_last", "s"]


def compute_features(rows):
    out = []
    for r in rows:
        rf = r["p1530"] / r["p930"] - 1.0
        rl = r["pclose"] / r["p1530"] - 1.0
        s = 1 if rf > 0 else (-1 if rf < 0 else 0)
        out.append({"id": r["id"], "r_first": rf, "r_last": rl, "s": s})
    return out


@dataclass
class Config:
    entry_time: str = "15:30"        # entry anchor (ET) [example]
    min_adv_shares: float = 1e6      # ADV filter [example]
    cost_gate_k: float = 0.5         # cost-gate multiplier [default]
    cooldown_s: float = 0.0          # one signal per day; no intraday re-entry [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: EOD drift on SPY-class ETF (chapter S4 cost walk)."""
    spread_bps = 0.50   # half-spread ~0.5 bp/leg -> ~1 bp round trip [example]
    fee_bps = 0.20      # ~$0.001/share per side [example]
    borrow_bps = 0.0     # long-biased reference; reason: no overnight borrow [default]
    impact_bps = 2.0     # entry leans into auction buildup [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S027 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["p930"] <= 0 or e["p1530"] <= 0 or e["pclose"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    rf = e["p1530"] / e["p930"] - 1.0
    direction = 1 if rf > 0 else (-1 if rf < 0 else 0)
    confidence = min(1.0, abs(rf) / 0.02) if direction else 0.0  # 2% = full conviction [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(rf) * 1e4 * 0.1  # 10% of the formation move persists [example]
    gate = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    if not gate:
        direction, confidence, capital = 0, 0.0, 0.0
    return SignalVector("TEST:XNAS", direction, confidence, capital,
                        e["event_ts"], 0, "OK")



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

    by_id = {f["id"]: f for f in feats}
    # Chapter S4 hand-checks: day 1 r_first=+1.40%, r_last=+0.49%; day 2 r_first=-0.79%, r_last=-0.50%
    assert abs(by_id["d1"]["r_first"] - 0.0140) < 1e-4, by_id["d1"]
    assert abs(by_id["d1"]["r_last"] - 0.004931) < 1e-5, by_id["d1"]
    assert by_id["d1"]["s"] == 1
    assert abs(by_id["d2"]["r_first"] - (-0.007889)) < 1e-5, by_id["d2"]
    assert abs(by_id["d2"]["r_last"] - (-0.004970)) < 1e-5, by_id["d2"]
    assert by_id["d2"]["s"] == -1
    assert by_id["d6"]["s"] == 1  # the honest loser: mild-up morning, faded close



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
