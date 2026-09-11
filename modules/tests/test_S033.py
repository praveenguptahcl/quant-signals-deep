"""Acceptance tests for S033 — Open-auction imbalance continuation.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S033.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S033_tape.csv"
EXPECTED = FIX / "S033_expected.csv"

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
                     "ref": float(r["ref"]), "ind": float(r["ind"]),
                     "paired": int(r["paired"]), "imb": int(r["imb"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "ref": 149.80, "ind": 150.00,
            "paired": 0, "imb": 100}  # zero paired shares


FEATURE_COLS = ["rho", "d_bps", "gate", "dir"]


def compute_features(rows):
    cfg = Config()
    out = []
    for r in rows:
        rho = abs(r["imb"]) / r["paired"]
        d_bps = (r["ind"] - r["ref"]) / r["ref"] * 1e4
        gate = 1 if (rho >= cfg.rho_min and abs(d_bps) >= cfg.d_min_bps) else 0
        s = 1 if r["imb"] > 0 else (-1 if r["imb"] < 0 else 0)
        out.append({"id": r["id"], "rho": rho, "d_bps": d_bps,
                    "gate": gate, "dir": s * gate})
    return out


@dataclass
class Config:
    rho_min: float = 0.15         # imbalance ratio gate [example]
    d_min_bps: float = 20.0       # displacement gate [example]
    cost_gate_k: float = 0.5      # cost-gate multiplier [default]
    cooldown_s: float = 300.0    # post-exit cooldown [default]
    max_hold_s: float = 300.0    # flat by open+5min [example]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: open-auction participation, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0    # auction-concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S033 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["paired"] <= 0 or e["ref"] <= 0 or e["ind"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    rho = abs(e["imb"]) / e["paired"]
    d_bps = (e["ind"] - e["ref"]) / e["ref"] * 1e4
    gate = rho >= cfg.rho_min and abs(d_bps) >= cfg.d_min_bps
    s = 1 if e["imb"] > 0 else (-1 if e["imb"] < 0 else 0)
    direction = s if gate else 0
    confidence = min(1.0, rho / 0.30) if direction else 0.0  # 30% = full conviction [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(d_bps) * 0.2  # one-fifth of the displacement persists [example]
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
    m8 = by_id["m8"]
    # Chapter S4 hand-checks: rho = 217180/972793 = 22.3%, d = +50.07 bps
    assert abs(m8["rho"] - 217180.0 / 972793.0) < 1e-9, m8
    assert abs(m8["d_bps"] - 50.07) < 0.01, m8
    assert m8["gate"] == 1 and m8["dir"] == 1
    # Point-in-time replay: the first message fails the displacement gate,
    # so its direction (0) differs from the final snapshot (+1) — the final
    # snapshot must never be used to explain earlier messages.
    assert by_id["m1"]["dir"] == 0
    assert by_id["m1"]["gate"] == 0  # |d| = 10.0 bps < 20 bps gate
    assert signal(dict(), rows, Config()).direction == 1  # full replay -> long



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
