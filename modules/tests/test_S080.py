"""Acceptance tests for S080 — PCA / statistical-factor residual reversal (eigenportfolios).

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S080.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S080_tape.csv"
EXPECTED = FIX / "S080_expected.csv"

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
CFG = {"m":1,"c_thresh":2.0,"sigma_u":0.72,"r2_crit":0.5,"p_max":0.25,
       "cooldown_s":300.0,"cost_gate_k":0.5}
def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    return 0.50 + 0.30 + 0.00 + 0.70   # [example] stack from the module COST block
def init_state():
    return {"module_state":"OK"}
def _bad(v):
    return v is None or (isinstance(v,float) and (math.isnan(v) or not math.isfinite(v)))
def step(state,row,cfg):
    A=row.get("A"); B=row.get("B"); ts=row.get("event_ts")
    sig=dict(computed_at=ts if isinstance(ts,int) else 0,direction=0,confidence=0.0,
             capital=0.0,module_state="OK",edge_bps=0.0,cost_bps=1.50,
             fill_event_ts=(ts+86_400_000_000_000) if isinstance(ts,int) else 0,
             A_hat=float("nan"),u=float("nan"),z=float("nan"))
    if _bad(A) or _bad(B) or not isinstance(ts,int):
        sig["module_state"]="UNKNOWN"; return sig,state
    Ahat=(A+B)/2.0; u=(A-B)/2.0; z=u/cfg["sigma_u"]
    edge=abs(z)*2.0  # [example] residual edge per z unit
    sig.update(A_hat=Ahat,u=u,z=z,edge_bps=edge)
    assert sig["fill_event_ts"] > sig["computed_at"]
    if abs(z) > cfg["c_thresh"] and edge*cfg["cost_gate_k"] >= sig["cost_bps"]:
        sig["direction"]=-1 if z>0 else 1
        sig["confidence"]=min(1.0,abs(z)/4.0)
        sig["capital"]=min(cfg["p_max"],sig["confidence"]*cfg["p_max"])
    return sig,state
def run(rows):
    st=init_state(); out=[]
    for r in rows:
        sig,st=step(st,r,CFG); out.append(sig)
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
    cols = ["computed_at", "direction", "confidence", "capital", "module_state", "edge_bps", "cost_bps", "fill_event_ts", "A_hat", "u", "z"]
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
    big_edge = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 100.0
    tiny_edge = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    rows = tape()
    bad = dict(rows[0])
    bad.update({'ev': 11, 'event_ts': 1000864000000000, 'asof_ts': 1000864000001000, 'A': float('nan'), 'B': 0.0})
    st = init_state()
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
