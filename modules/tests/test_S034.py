"""Acceptance tests for S034 — Scheduled macro-announcement drift.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S034.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S034_tape.csv"
EXPECTED = FIX / "S034_expected.csv"

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
                     "p_pre": float(r["p_pre"]), "p_ann": float(r["p_ann"]),
                     "p_j1": float(r["p_j1"]), "p_j2": float(r["p_j2"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "p_pre": 6000.0, "p_ann": 0.0,
            "p_j1": 6000.0, "p_j2": 6000.0}  # non-positive announce price


FEATURE_COLS = ["R_pre_bp", "R_jump_bp", "dir"]


def _bp(a, b):
    return math.log(b / a) * 1e4


def compute_features(rows):
    th = Config().jump_thresh_bp
    out = []
    for r in rows:
        rp = _bp(r["p_pre"], r["p_ann"])
        rj = _bp(r["p_ann"], r["p_j2"])
        d = 0
        if abs(rj) >= th:
            d = 1 if rj > 0 else -1
        out.append({"id": r["id"], "R_pre_bp": rp, "R_jump_bp": rj, "dir": d})
    return out


@dataclass
class Config:
    jump_thresh_bp: float = 10.0   # diurnal-vol jump threshold [default]
    cost_gate_k: float = 0.5       # cost-gate multiplier [default]
    cooldown_s: float = 3600.0     # one signal per announcement [default]
    max_hold_min: float = 30.0     # flat by tau+30min [example]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: announcement-window futures/ETF, liquid."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0    # fast-window concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S034 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if min(e["p_pre"], e["p_ann"], e["p_j1"], e["p_j2"]) <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    rj = math.log(e["p_j2"] / e["p_ann"]) * 1e4
    direction = 0
    if abs(rj) >= cfg.jump_thresh_bp:
        direction = 1 if rj > 0 else -1
    confidence = min(1.0, abs(rj) / 50.0) if direction else 0.0  # 50bp = full [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(rj) * 0.5  # half the jump persists [example]
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
    e1 = by_id["e1"]
    # Chapter S4 hand-checks: R_pre = +15.8bp, R_jump = -29.8bp -> short
    assert abs(e1["R_pre_bp"] - 15.77) < 0.02, e1
    assert abs(e1["R_jump_bp"] - (-29.80)) < 0.02, e1
    assert e1["dir"] == -1
    # e2: positive jump clears the threshold -> long; e3: -5.4bp under it -> flat
    assert by_id["e2"]["dir"] == 1
    assert by_id["e3"]["dir"] == 0
    assert abs(by_id["e3"]["R_jump_bp"] - (-5.40)) < 0.02



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
