"""Acceptance tests for S035 — Short-term reversal.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S035.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S035_tape.csv"
EXPECTED = FIX / "S035_expected.csv"

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
                     "symbol": r["symbol"], "r_form": float(r["r_form"]),
                     "r_hold": float(r["r_hold"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "symbol": "BAD",
            "r_form": float("nan"), "r_hold": 0.0}  # NaN formation return


FEATURE_COLS = ["rank", "leg"]


def _legs(rows):
    order = sorted(range(len(rows)), key=lambda i: rows[i]["r_form"])
    leg = [0] * len(rows)
    for i in order[:3]:
        leg[i] = 1
    for i in order[-3:]:
        leg[i] = -1
    return leg, order


def compute_features(rows):
    leg, order = _legs(rows)
    rank = [0] * len(rows)
    for r, i in enumerate(order):
        rank[i] = r + 1  # 1 = worst formation return
    return [{"id": rows[i]["id"], "rank": rank[i], "leg": leg[i]}
            for i in range(len(rows))]


def portfolio_stats(rows):
    """(formation/holding correlation, long-leg hold, short-leg hold, spread)."""
    leg, _ = _legs(rows)
    rf = [r["r_form"] for r in rows]
    rh = [r["r_hold"] for r in rows]
    n = len(rows)
    mx, my = sum(rf) / n, sum(rh) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rf, rh))
    den = (sum((a - mx) ** 2 for a in rf) * sum((b - my) ** 2 for b in rh)) ** 0.5
    corr = cov / den if den else float("nan")
    lr = [rh[i] for i in range(n) if leg[i] == 1]
    sr = [rh[i] for i in range(n) if leg[i] == -1]
    lret, sret = sum(lr) / len(lr), sum(sr) / len(sr)
    return corr, lret, sret, lret - sret


@dataclass
class Config:
    n_long: int = 3              # losers bought [example]
    n_short: int = 3             # winners shorted [example]
    min_names: int = 6           # minimum cross-section [default]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 86_400.0 # weekly rebalance [example]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: weekly cross-sectional reversal, large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 1.00   # short-leg borrow [example]; reason: 3-name short leg
    impact_bps = 1.00   # weekly-turn concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S035 reference stub).

    Portfolio-level stub: the reversal book is active when the cross-section
    is wide enough; per-name legs come from compute_features.
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["r_form"] != e["r_form"]:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    direction = 0
    confidence = 0.0
    if len(evs) >= cfg.min_names:
        rf = [x["r_form"] for x in evs]
        width = max(rf) - min(rf)
        direction = 1  # reversal spread is on
        confidence = min(1.0, width / 20.0)  # 20pp wide = full [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = 250.0  # weekly reversal spread [example]
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

    by_sym = {r["symbol"]: f["leg"] for r, f in zip(rows, feats)}
    # Chapter S4 hand-checks: long GGG/AAA/HHH, short EEE/CCC/BBB
    assert sorted(s for s, l in by_sym.items() if l == 1) == ["AAA", "GGG", "HHH"], by_sym
    assert sorted(s for s, l in by_sym.items() if l == -1) == ["BBB", "CCC", "EEE"], by_sym
    corr, lret, sret, spread = portfolio_stats(rows)
    assert abs(corr - (-0.302)) < 0.005, corr          # formation/holding correlation
    assert abs(spread - 2.497) < 0.01, spread          # long-leg minus short-leg hold



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
