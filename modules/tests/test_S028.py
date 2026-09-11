"""Acceptance tests for S028 — Donchian breakout.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S028.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S028_tape.csv"
EXPECTED = FIX / "S028_expected.csv"

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
        rows.append({"ev": int(r["ev"]), "event_ts": int(r["event_ts"]),
                     "open": float(r["open"]), "high": float(r["high"]),
                     "low": float(r["low"]), "close": float(r["close"]),
                     "volume": int(r["volume"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"ev": -1, "event_ts": 1, "open": 100.0, "high": 99.0,
            "low": 100.0, "close": 100.0, "volume": 10}  # high < low


FEATURE_COLS = ["donch_up", "donch_lo", "mid", "brk"]


def _nz(x):
    return float(x) if x != "" else float("nan")


def compute_features(rows):
    N = Config().lookback
    out = []
    for t, r in enumerate(rows):
        if t < N:
            out.append({"id": r["ev"], "donch_up": float("nan"),
                        "donch_lo": float("nan"), "mid": float("nan"), "brk": 0})
            continue
        win = rows[t - N:t]  # completed-bar convention: bar t excluded
        up = max(x["high"] for x in win)
        lo = min(x["low"] for x in win)
        mid = (up + lo) / 2.0
        brk = 1 if r["close"] > up else (-1 if r["close"] < lo else 0)
        out.append({"id": r["ev"], "donch_up": up, "donch_lo": lo,
                    "mid": mid, "brk": brk})
    return out


@dataclass
class Config:
    lookback: int = 5            # N bars (fixture override; module default 20) [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown [default]
    max_spread_ticks: int = 3    # spread filter [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: intraday 5-min breakout, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0     # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0     # breakout chasing concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S028 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["high"] < e["low"] or e["close"] <= 0 or e["high"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    if len(evs) <= cfg.lookback:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "OK")
    win = evs[-cfg.lookback - 1:-1]
    up = max(x["high"] for x in win)
    lo = min(x["low"] for x in win)
    brk = 1 if e["close"] > up else (-1 if e["close"] < lo else 0)
    direction = brk
    confidence = 0.8 if brk else 0.0  # breakout conviction [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(e["close"] - (up + lo) / 2.0) / e["close"] * 1e4  # rail distance [example]
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
    # Hand-check bar 8 (N=5, completed-bar: window = bars 3..7):
    # up = max(101.00,101.10,101.20,101.00,100.90) = 101.20
    # lo = min(100.00,100.10,100.20,100.30,100.00) = 100.00 ; mid = 100.60
    assert abs(by_id[8]["donch_up"] - 101.20) < TOL, by_id[8]
    assert abs(by_id[8]["donch_lo"] - 100.00) < TOL, by_id[8]
    assert abs(by_id[8]["mid"] - 100.60) < TOL, by_id[8]
    assert by_id[8]["brk"] == 1  # close 102.00 > 101.20 -> bullish close-breakout
    assert by_id[7]["brk"] == 0  # bar 7 inside the channel



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
