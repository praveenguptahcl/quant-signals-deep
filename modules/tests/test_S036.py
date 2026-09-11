"""Acceptance tests for S036 — Overnight-gap fade.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S036.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S036_tape.csv"
EXPECTED = FIX / "S036_expected.csv"

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
                     "session": r["session"],
                     "prior_close": float(r["prior_close"]) if r["prior_close"] else float("nan"),
                     "open": float(r["open"]) if r["open"] else float("nan"),
                     "close": float(r["close"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "session": "bad",
            "prior_close": 100.0, "open": -1.0, "close": 100.0}  # negative open


FEATURE_COLS = ["gap", "in_gate", "dir", "fade_ret"]


def _session_anchor(rows):
    first = rows[0]
    return first["prior_close"], first["open"]


def compute_features(rows):
    cfg = Config()
    # group row indices by session, preserving order
    sessions, order = {}, []
    for i, r in enumerate(rows):
        if r["session"] not in sessions:
            sessions[r["session"]] = []
            order.append(r["session"])
        sessions[r["session"]].append(i)
    out = [None] * len(rows)
    for s in order:
        idx = sessions[s]
        pc, op = rows[idx[0]]["prior_close"], rows[idx[0]]["open"]
        gap = op / pc - 1.0
        in_gate = 1 if (cfg.gap_min <= abs(gap) <= cfg.gap_max) else 0
        d = (-1 if gap > 0 else (1 if gap < 0 else 0)) * in_gate
        for i in idx:
            out[i] = {"id": rows[i]["id"], "gap": gap, "in_gate": in_gate,
                      "dir": d, "fade_ret": rows[i]["close"] / op - 1.0}
    return out


@dataclass
class Config:
    gap_min: float = 0.005        # minimum tradeable gap [example]
    gap_max: float = 0.05         # maximum tradeable gap [example]
    max_hold_bars: int = 10       # fade horizon [example]
    cost_gate_k: float = 0.5      # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: open fade, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0    # open-auction concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S036 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["close"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    sess = [x for x in evs if x["session"] == e["session"]]
    pc, op = sess[0]["prior_close"], sess[0]["open"]
    if not (pc == pc and op == op) or pc <= 0 or op <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    gap = op / pc - 1.0
    in_gate = cfg.gap_min <= abs(gap) <= cfg.gap_max
    direction = (-1 if gap > 0 else (1 if gap < 0 else 0)) if in_gate else 0
    confidence = min(1.0, abs(gap) / 0.03) if direction else 0.0  # 3% = full [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(gap) * 1e4 * 0.3  # 30% of the gap fills [example]
    ok = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    if not ok:
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
    s1 = by_id["s1b1"]
    # Chapter S4 hand-checks: gap = +2.00% -> fade short
    assert abs(s1["gap"] - 0.02) < 1e-12, s1
    assert s1["in_gate"] == 1 and s1["dir"] == -1
    assert abs(s1["fade_ret"] - (101.50 / 102.00 - 1.0)) < 1e-12, s1
    assert abs(by_id["s1b1"]["fade_ret"] - (-0.004902)) < 1e-5
    # s2: +0.20% gap is below the 0.50% minimum gate -> flat
    assert by_id["s2b1"]["in_gate"] == 0 and by_id["s2b1"]["dir"] == 0
    # every bar of a session shares the session gap and direction
    assert all(by_id["s1b%d" % i]["dir"] == -1 for i in range(1, 11))



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
