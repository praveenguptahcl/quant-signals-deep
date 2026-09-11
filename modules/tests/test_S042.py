"""Acceptance tests for S042 — SOTM: settle-to-open momentum (monthly vol).

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S042.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S042_tape.csv"
EXPECTED = FIX / "S042_expected.csv"

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



REALIZED_VOL = 0.112   # trailing realized vol [example]
TRADING_DAYS = 252.0


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({"id": r["id"], "event_ts": int(r["event_ts"]),
                     "leg": r["leg"], "close": float(r["close"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "leg": "prior",
            "close": 0.0}  # non-positive close


FEATURE_COLS = ["logret", "sqret"]


def compute_features(rows):
    out = []
    for i, r in enumerate(rows):
        if i == 0:
            out.append({"id": r["id"], "logret": float("nan"),
                        "sqret": float("nan")})
            continue
        lr = math.log(r["close"] / rows[i - 1]["close"])
        out.append({"id": r["id"], "logret": lr, "sqret": lr * lr})
    return out


def sotm_vol(rows):
    """SOTM vol = (fwd_var / T - realized_var) / (2 * realized_vol)."""
    feats = compute_features(rows)
    sq = [f["sqret"] for f in feats[1:]]
    if not sq:
        return 0.0  # fewer than 2 rows -> no returns yet -> no signal
    fwd_var = sum(sq)
    T = len(sq) / TRADING_DAYS
    rv = REALIZED_VOL ** 2
    return (fwd_var / T - rv) / (2 * REALIZED_VOL)


@dataclass
class Config:
    realized_vol: float = 0.112    # trailing realized vol [example]
    cost_gate_k: float = 0.5       # cost-gate multiplier [default]
    cooldown_s: float = 86_400.0   # post-settle cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: monthly settle-cycle options positioning."""
    spread_bps = 1.00   # half-spread, options [example]
    fee_bps = 0.65      # OCC + exchange + brokerage [example]
    borrow_bps = 0.0     # long-biased reference; reason: no borrow [default]
    impact_bps = 1.00    # monthly-turn concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S042 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["close"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    sv = sotm_vol(evs)
    direction = 1 if sv >= 0.015 else (-1 if sv <= -0.015 else 0)
    confidence = min(abs(sv) * 20.0, 1.0)  # scales with |SOTM| [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(sv) * 1e4
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

    sv = sotm_vol(rows)
    # Tape calibrated (seed 42) so the chapter's +1.5% hand-check reproduces:
    assert abs(sv - 0.015) < 1e-9, sv
    feats = compute_features(rows)
    sq = [f["sqret"] for f in feats[1:]]
    assert len(sq) == 23  # 24 closes -> 23 log returns
    assert abs(sum(sq) - (23 / 252.0) * (0.112 ** 2 + 0.015 * 2 * 0.112)) < 1e-12
    legs = [r["leg"] for r in rows]
    assert legs[:12] == ["prior"] * 12 and legs[12:] == ["scenario"] * 12



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
