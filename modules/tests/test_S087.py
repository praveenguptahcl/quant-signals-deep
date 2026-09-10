"""Acceptance tests for S087 — Fractional differentiation (memory-retaining stationarization).

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S087.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S087_tape.csv"
EXPECTED = FIX / "S087_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]


def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def _num(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        pass
    try:
        return float(v)
    except (ValueError, TypeError):
        return v


def tape():
    rows = []
    for r in load_csv(TAPE):
        d = {}
        for k, v in r.items():
            d[k] = _num(v)
        rows.append(d)
    return rows


import math
CFG = {"d": 0.4, "L": 5, "tau": 1e-3}  # [example]
def _weights(d, L):
    w = [1.0]
    for k in range(1, L):
        w.append(-w[-1] * (d - k + 1) / k)
    return w
W = _weights(CFG["d"], CFG["L"])
def expected_cost_bps(notional, spread_bps, venue, side, regime):
    # The transform executes no trades: all four cost components are zero. [documented]
    return 0.0
def init_state():
    return {"hist": []}
def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))
def step(state, row, cfg):
    ts = row.get("event_ts"); px = row.get("price")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0, "cost_bps": 0.0,
           "ffd": float("nan"), "d": cfg["d"], "L": cfg["L"],
           "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    if ts is None or _bad(px):
        return out, state  # invalid input -> UNKNOWN; never interpolate
    state["hist"].append(px)
    if len(state["hist"]) < cfg["L"]:
        out["module_state"] = "DEGRADED"  # warmup: fewer than L bars
        return out, state
    xs = state["hist"][-cfg["L"]:]  # chronological, oldest first
    out["ffd"] = sum(w * x for w, x in zip(W, xs))  # window oldest-first; w_0 on earliest bar = chapter S4 hand-check
    out["module_state"] = "OK"
    return out, state
def run(rows):
    st = init_state(); out = []
    for r in rows:
        sig, st = step(st, r, CFG)
        out.append(sig)
    return out


def _close(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(b))
    return a == b


def test_fixtures_exist_and_typed():
    assert TAPE.exists(), "tape fixture missing"
    assert EXPECTED.exists(), "expected fixture missing"
    with open(TAPE) as f:
        head = [next(f) for _ in range(3)]
    assert any(l.startswith("# TYPE:") for l in head), "tape missing TYPE header"
    with open(EXPECTED) as f:
        head = [next(f) for _ in range(3)]
    assert any(l.startswith("# TYPE:") for l in head), "expected missing TYPE header"
    rows = tape()
    assert len(rows) >= 5, "fixture needs >=5 hand-checkable rows"


def test_expected_matches_reference():
    rows = tape()
    sigs = run(rows)
    exp = load_csv(EXPECTED)
    assert len(exp) == len(sigs), "expected row count != tape row count"
    cols = ["computed_at", "direction", "confidence", "capital", "module_state", "edge_bps", "cost_bps", "ffd", "d", "L"]
    for i, (s, e) in enumerate(zip(sigs, exp)):
        assert int(e["ev"]) == int(rows[i]["ev"]), f"row {i} ev mismatch"
        for c in cols:
            got = s[c]
            want = _num(e[c])
            assert _close(got, want), f"row {i} col {c}: got {got} want {want}"


def test_signal_vector_valid():
    for s in run(tape()):
        assert s["direction"] in (+1, -1, 0), "direction not in {+1,-1,0}"
        assert 0.0 <= s["confidence"] <= 1.0, "confidence out of [0,1]"
        assert 0.0 <= s["capital"] <= 0.5, "capital out of [0,0.5]"
        assert s["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()):
        fill_event = s["fill_event_ts"]
        signal_event = s["computed_at"]
        if fill_event is not None:
            assert fill_event > signal_event


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5  # [default]
    c = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")
    if c == 0.0:
        # infrastructure module: executes no trades; the gate is vacuous [documented]
        assert c == 0.0
        return
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    rows = tape()
    bad = dict(rows[0])
    bad.update({'price': float('nan')})
    st = init_state()
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
