"""Acceptance tests for S030 — Bollinger bandwidth squeeze → expansion.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S030.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S030_tape.csv"
EXPECTED = FIX / "S030_expected.csv"

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
                     "bw": float(r["bw"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "bw": -0.5}  # negative bandwidth


FEATURE_COLS = ["pct", "squeeze"]


def compute_features(rows):
    R, p = Config().pct_window, Config().squeeze_pct
    out = []
    for t, r in enumerate(rows):
        if t < R:
            out.append({"id": r["id"], "pct": float("nan"), "squeeze": 0})
            continue
        prior = [x["bw"] for x in rows[t - R:t]]
        pct = 100.0 * sum(1 for x in prior if x <= r["bw"]) / R
        out.append({"id": r["id"], "pct": pct,
                    "squeeze": 1 if pct <= p else 0})
    return out


@dataclass
class Config:
    bb_lookback: int = 20         # Bollinger N [example]
    bb_mult: float = 2.0          # Bollinger k [example]
    pct_window: int = 20          # percentile window R (fixture override; module default 125) [example]
    squeeze_pct: float = 20.0     # squeeze threshold p [example]
    cost_gate_k: float = 0.5      # cost-gate multiplier [default]
    cooldown_s: float = 600.0     # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: squeeze-breakout entry, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0     # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0     # expansion-chasing concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S030 reference stub).

    The squeeze is direction-neutral: it ARMS the system (squeeze=1) and the
    direction comes from the confirmed band break (S029 leg). The stub emits
    direction 0 with OK state; consumers read the squeeze feature.
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["bw"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    feats = compute_features(evs)
    f = feats[-1]
    armed = bool(f["squeeze"]) and not (f["pct"] != f["pct"])  # nan-safe
    confidence = 0.6 if armed else 0.0  # volatility-timing conviction [example]
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = 8.0  # expected expansion move [example]
    gate = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    if not gate:
        armed, confidence = False, 0.0
    return SignalVector("TEST:XNAS", 0, confidence, 0.5 * confidence,
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
    # Hand-checks: bar 23 (bw=0.90): prior 20 = bars 3..22, min 0.96 -> 0% -> squeeze ON
    assert abs(by_id["b23"]["pct"] - 0.0) < TOL, by_id["b23"]
    assert by_id["b23"]["squeeze"] == 1
    # bar 26 (bw=1.564): all 20 priors <= 1.564 -> 100% -> expansion, NOT a squeeze
    assert abs(by_id["b26"]["pct"] - 100.0) < TOL, by_id["b26"]
    assert by_id["b26"]["squeeze"] == 0
    # bar 21 (bw=1.30): priors bars 1..20, values <=1.30 are 0.90..1.29 -> 14/20 = 70%
    assert abs(by_id["b21"]["pct"] - 70.0) < TOL, by_id["b21"]
    assert by_id["b21"]["squeeze"] == 0



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
