"""Acceptance tests for S084 — Hasbrouck (1991) trade–quote VAR.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S084.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S084_tape.csv"
EXPECTED = FIX / "S084_expected.csv"

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
CFG = {"A": [[0.1046, 0.0120], [0.1479, 0.5958]],  # chapter OLS estimate [documented]
       "conf_scale": 5.0,   # cents of permanent impact -> confidence 1.0 [example]
       "fee_bps": 0.3}      # per-side fee [example]
def expected_cost_bps(notional, spread_bps, venue, side, regime):
    # Measurement module: acting on the signal pays the effective spread + fees. [example]
    return spread_bps + CFG["fee_bps"]
def _lri_cents(A):
    a, b, c, d = A[0][0], A[0][1], A[1][0], A[1][1]
    det = (1 - a) * (1 - d) - b * c
    return 100.0 * b / det  # e_m'(I-A)^{-1}e_q in cents
def init_state():
    return {"prev_dm": None, "prev_q": None}
def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))
def step(state, row, cfg):
    ts = row.get("event_ts"); md = row.get("mid"); dm = row.get("dm"); q = row.get("q")
    A = cfg["A"]; lri = _lri_cents(A); irf1 = 100.0 * A[0][1]
    base = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
            "module_state": "UNKNOWN", "edge_bps": lri, "cost_bps": expected_cost_bps(1e6, 1.0, "XNAS", "taker", "normal"),
            "u_q": float("nan"), "irf_1_cents": irf1, "lri_cents": lri,
            "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    if ts is None or _bad(md) or _bad(dm) or q not in (1, -1):
        return base, state  # invalid input -> UNKNOWN; never interpolate
    if state["prev_dm"] is None:
        base["module_state"] = "DEGRADED"  # warmup: no history, no innovation
        state["prev_dm"] = dm; state["prev_q"] = q
        return base, state
    exp_q = A[1][0] * state["prev_dm"] + A[1][1] * state["prev_q"]
    uq = q - exp_q
    base["module_state"] = "OK"
    base["u_q"] = uq
    base["direction"] = 1 if uq > 0 else (-1 if uq < 0 else 0)
    base["confidence"] = min(1.0, abs(lri * uq) / cfg["conf_scale"])
    state["prev_dm"] = dm; state["prev_q"] = q
    return base, state
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
    cols = ["computed_at", "direction", "confidence", "capital", "module_state", "edge_bps", "cost_bps", "u_q", "irf_1_cents", "lri_cents"]
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
    bad.update({'mid': float('nan')})
    st = init_state()
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
