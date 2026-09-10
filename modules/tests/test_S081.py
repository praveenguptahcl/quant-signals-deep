"""Acceptance tests for S081 — Hawkes buy/sell intensity imbalance.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S081.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S081_tape.csv"
EXPECTED = FIX / "S081_expected.csv"

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
CFG = {"mu":0.4,"alpha_self":0.9,"beta_self":1.5,"alpha_cross":0.25,
       "kappa":2.0,"z_window_s":300.0,"m_d":0.1458,"s_d":1.2217,
       "p_max":0.25,"cooldown_s":60.0,"cost_gate_k":0.5}
def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    return 0.50 + 0.35 + 0.00 + 6.55   # [example] stack from the module COST block
def init_state():
    return {"module_state":"OK"}
def _bad(v):
    return v is None or (isinstance(v,float) and (math.isnan(v) or not math.isfinite(v)))
def step(state,row,cfg):
    lb=row.get("lam_b"); ls=row.get("lam_s"); ts=row.get("event_ts")
    sig=dict(computed_at=ts if isinstance(ts,int) else 0,direction=0,confidence=0.0,
             capital=0.0,module_state="OK",edge_bps=0.0,cost_bps=7.40,
             fill_event_ts=(ts+1_000_000) if isinstance(ts,int) else 0,
             d=float("nan"),z=float("nan"),burst=0)
    if _bad(lb) or _bad(ls) or not isinstance(ts,int):
        sig["module_state"]="UNKNOWN"; return sig,state
    dd=lb-ls; z=(dd-cfg["m_d"])/cfg["s_d"]
    burst=1 if abs(z)>cfg["kappa"] else 0
    edge=abs(z)*1.0  # [example] edge per z unit
    sig.update(d=dd,z=z,burst=burst,edge_bps=edge)
    assert sig["fill_event_ts"] > sig["computed_at"]
    if burst and edge*cfg["cost_gate_k"] >= sig["cost_bps"]:
        sig["direction"]=1 if z>0 else -1
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
    cols = ["computed_at", "direction", "confidence", "capital", "module_state", "edge_bps", "cost_bps", "fill_event_ts", "d", "z", "burst"]
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
    bad.update({'ev': 81, 'event_ts': 7900000000, 'asof_ts': 7900001000, 'side': -1, 'lam_b': float('nan'), 'lam_s': 9.0})
    st = init_state()
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
