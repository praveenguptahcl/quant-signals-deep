"""Acceptance tests for S043 — SOTM regime: IV-RV spread sign.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of
the chapter's normative pseudocode (§S3), and pins causality, the cost gate,
threshold-boundary semantics, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S043.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S043_tape.csv"
EXPECTED = FIX / "S043_expected.csv"

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


def fixture_type_header(path):
    """Return the '# TYPE:' header value, or None if absent."""
    with open(path) as f:
        for ln in f:
            if ln.startswith("# TYPE:"):
                return ln.split(":", 1)[1].strip()
    return None


@dataclass(frozen=True)
class SignalVector:
    symbol: str
    direction: int          # +1 | -1 | 0
    confidence: float       # 0..1
    capital: float          # 0..1
    computed_at: int        # int64 ns UTC
    staleness: int          # ns
    module_state: str       # OK | DEGRADED | UNKNOWN | OFF


SPREAD_THRESHOLD = 0.5  # vol points [example]
CONFIDENCE_SCALE = 2.0  # vol points [example]; confidence = min(|spread|/2, 1)


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({"id": r["id"], "event_ts": int(r["event_ts"]),
                     "dte_start": int(r["dte_start"]),
                     "dte_end": int(r["dte_end"]),
                     "realized_vol": float(r["realized_vol"]),
                     "iv_avg": float(r["iv_avg"]),
                     "spot": float(r["spot"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "dte_start": 30, "dte_end": 2,
            "realized_vol": -3.0, "iv_avg": 12.0,
            "spot": 4000.0}  # negative realized vol


def tiny_edge_event():
    """Spread +0.02 vol points: edge 2 bps, cost gate must veto."""
    return {"id": "tiny", "event_ts": 2, "dte_start": 30, "dte_end": 2,
            "realized_vol": 12.0, "iv_avg": 12.02,
            "spot": 4100.0}


FEATURE_COLS = ["spread", "direction"]


def compute_features(rows):
    out = []
    for r in rows:
        sp = r["iv_avg"] - r["realized_vol"]
        d = 1 if sp >= SPREAD_THRESHOLD else (-1 if sp <= -SPREAD_THRESHOLD else 0)
        out.append({"id": r["id"], "spread": sp, "direction": d})
    return out


@dataclass
class Config:
    spread_threshold: float = 0.5  # vol points [example]
    dte_start: int = 30            # measurement window start [example]
    dte_end: int = 2               # measurement window end [example]
    cost_gate_k: float = 0.5       # cost-gate multiplier [default]
    cooldown_s: float = 2_592_000.0  # post-exit cooldown (30d) [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model — mirrors the §S2 COST block exactly."""
    spread_bps = 0.50  # half-spread, liquid large-cap [example]
    fee_bps = 0.30     # taker incl. regulatory [example]
    borrow_bps = 0.0   # long-biased reference; reason in COST block [default]
    impact_bps = 1.00  # flagged; calibrate per venue at scale-up [example]
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S043 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["realized_vol"] <= 0 or e["iv_avg"] <= 0 or e["spot"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    feats = compute_features(evs)
    direction = feats[-1]["direction"]
    confidence = min(abs(feats[-1]["spread"]) / CONFIDENCE_SCALE, 1.0)
    capital = 0.5 * confidence
    # normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(feats[-1]["spread"]) * 100.0  # vol-point to bps [example]
    gate = (expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
            <= cfg.cost_gate_k * edge_bps)
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
    m = by_id["2026-05"]  # chapter hand-check month
    assert abs(m["spread"] - 1.313102) < 1e-6, m
    assert m["direction"] == 1  # spread +1.31 >= 0.5 -> long gamma
    n_long = sum(1 for f in feats if f["direction"] == 1)
    n_short = sum(1 for f in feats if f["direction"] == -1)
    assert n_long > 0 and n_short > 0  # both regimes present in the tape


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
    assert abs(cost - 1.80) < 1e-12  # pins the §S2 reference stack [example]
    assert cost <= k * 100.0   # huge edge -> gate passes
    assert not (cost <= k * 0.01)  # tiny edge -> gate blocks


def test_invalid_input_yields_unknown():
    s = signal(dict(), [bad_event()], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0


def test_threshold_boundary_inclusive():
    """Boundary semantics: spread exactly ±0.5 -> ±1 (>= / <=, not strict)."""
    by_id = {f["id"]: f for f in compute_features(tape())}
    b = by_id["2026-06"]  # fixture pins the boundary: spread = +0.50 exactly
    assert abs(b["spread"] - 0.5) < 1e-9, b
    assert b["direction"] == 1  # >= +0.5 -> long gamma
    # mirrored boundary computed directly
    rows = [{"id": "m", "event_ts": 3, "dte_start": 30, "dte_end": 2,
             "realized_vol": 13.0, "iv_avg": 12.5, "spot": 4000.0}]
    assert compute_features(rows)[0]["direction"] == -1  # <= -0.5 -> short gamma


def test_cost_gate_zeroes_subthreshold_signal():
    """signal() must zero direction/confidence when the cost gate fails."""
    cfg = Config()
    s = signal(dict(), [tiny_edge_event()], cfg)
    # spread +0.02 -> edge 2 bps; cost 1.80 > 0.5 * 2 -> vetoed, direction 0
    assert s.direction == 0
    assert s.confidence == 0.0 and s.capital == 0.0
    assert s.module_state == "OK"  # veto is a gate decision, not a fault


def test_fixture_schema_and_type_header():
    """Fixture hygiene: TYPE header + pinned DTE-window columns on every row."""
    assert fixture_type_header(TAPE) == "validation-run"
    assert fixture_type_header(EXPECTED) == "validation-run"
    for r in tape():
        assert r["dte_start"] == 30 and r["dte_end"] == 2  # DTE window [example]
        assert r["event_ts"] > 0
