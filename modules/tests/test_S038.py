"""Acceptance tests for S038 — Sub-hour microstructure reversal.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S038.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S038_tape.csv"
EXPECTED = FIX / "S038_expected.csv"

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
                     "side": r["side"], "price": float(r["price"]),
                     "mid": float(r["mid"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "side": "ask",
            "price": 100.0, "mid": -1.0}  # negative midpoint


FEATURE_COLS = ["r_mid_0", "r_trade_0"]


def formation_stats(rows):
    """(trade formation ret, mid formation ret, trade reversal ret, mid reversal ret)."""
    m = [r["mid"] for r in rows]
    p = [r["price"] for r in rows]
    return (p[5] / p[0] - 1.0, m[5] / m[0] - 1.0,
            p[11] / p[5] - 1.0, m[11] / m[5] - 1.0)


def compute_features(rows):
    m0, p0 = rows[0]["mid"], rows[0]["price"]
    return [{"id": r["id"], "r_mid_0": r["mid"] / m0 - 1.0,
             "r_trade_0": r["price"] / p0 - 1.0} for r in rows]


@dataclass
class Config:
    form_bars: int = 6            # formation window (events) [example]
    mid_thresh: float = 0.0003   # 3 bps midpoint-move trigger [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 300.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: sub-hour reversal, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0    # reversal-chasing concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S038 reference stub).

    Generates on the MIDPOINT move, never on the bounce-contaminated trade
    move: the trigger is |mid formation return| >= mid_thresh.
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["mid"] <= 0 or e["price"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    n = cfg.form_bars
    if len(evs) < n:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    win = evs[-n:]
    rm = win[-1]["mid"] / win[0]["mid"] - 1.0  # midpoint formation return
    direction = 0
    if abs(rm) >= cfg.mid_thresh:
        direction = -1 if rm > 0 else 1  # fade the midpoint move
    confidence = min(1.0, abs(rm) / 0.001) if direction else 0.0  # 10bps=full [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(rm) * 1e4 * 0.5  # half the midpoint move reverts [example]
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

    rt_f, rm_f, rt_r, rm_r = formation_stats(rows)
    # Chapter S4 hand-checks: trade -0.0650% vs mid -0.0450% (formation);
    # trade +0.0330% vs mid +0.0130% (reversal) — the 2bp gap is the bounce.
    assert abs(rt_f - (-0.000650)) < 1e-6, (rt_f, rm_f)
    assert abs(rm_f - (-0.000450)) < 1e-6, (rt_f, rm_f)
    assert abs(rt_r - 0.000330) < 1e-6, (rt_r, rm_r)
    assert abs(rm_r - 0.000130) < 1e-6, (rt_r, rm_r)
    assert abs(abs(rt_f) - abs(rm_f) - 0.0002) < 1e-6  # bounce contamination = 2bps
    # at e5 the midpoint trigger is met (|mid| = 4.5bps >= 3bps) -> fade long,
    # but the reference cost gate blocks under default k = 0.5:
    # cost 1.8bps > 0.5 * edge 2.25bps (half the 4.5bps move reverts)
    s5 = signal(dict(), rows[:6], Config())
    assert s5.direction == 0 and s5.module_state == "OK", s5  # gate-blocked
    cfg_loose = Config(); cfg_loose.cost_gate_k = 2.0
    assert signal(dict(), rows[:6], cfg_loose).direction == 1  # trigger logic
    s4 = signal(dict(), rows[:5], Config())
    assert s4.direction == 0  # formation window not complete



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
