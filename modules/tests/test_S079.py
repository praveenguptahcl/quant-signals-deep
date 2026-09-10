"""Acceptance tests for S079 — HMM regime switching.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S079.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S079_tape.csv"
EXPECTED = FIX / "S079_expected.csv"

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
CFG = {"A":[[0.97,0.03],[0.08,0.92]],"mu":[3.0,-5.0],"sigma":[40.0,120.0],
       "p_halve":0.7,"p_suspend":0.8,"cooldown_s":300.0,"cost_gate_k":0.5}
def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    return 1.0 + 0.30 + 0.0 + 0.0   # [example] stack from the module COST block
def _g(x,mu,sig):
    return math.exp(-0.5*((x-mu)/sig)**2)/(sig*math.sqrt(2*math.pi))
def init_state():
    return {"alpha":[0.7273,0.2727],"cooldown_until":0,"module_state":"OK"}  # stationary [example]
def step(state,row,cfg):
    r = row["ret_bp"]
    if r is None or (isinstance(r,float) and (math.isnan(r) or not math.isfinite(r))):
        sig = dict(direction=0,confidence=0.0,capital=0.0,computed_at=row["event_ts"],
                   module_state="UNKNOWN",edge_bps=0.0,cost_bps=0.0,p_vol=float("nan"),gate="UNKNOWN")
        return sig, dict(state, module_state="UNKNOWN")
    pred = [sum(state["alpha"][i]*cfg["A"][i][j] for i in (0,1)) for j in (0,1)]
    like = [_g(r,cfg["mu"][j],cfg["sigma"][j]) for j in (0,1)]
    num = [pred[j]*like[j] for j in (0,1)]; tot = sum(num)
    if not (tot > 0 and all(math.isfinite(v) for v in num)):
        sig = dict(direction=0,confidence=0.0,capital=0.0,computed_at=row["event_ts"],
                   module_state="UNKNOWN",edge_bps=0.0,cost_bps=0.0,p_vol=float("nan"),gate="UNKNOWN")
        return sig, dict(state, module_state="UNKNOWN")
    alpha = [num[0]/tot,num[1]/tot]; p_vol = alpha[1]
    edge = 2.0; cost = expected_cost_bps(1e6,0.01,"XNAS","taker","normal")
    cost_ok = cost <= cfg["cost_gate_k"]*edge
    if p_vol < cfg["p_halve"]: gate="FULL"; direction=1
    elif p_vol < cfg["p_suspend"]: gate="HALVE"; direction=0
    else: gate="SUSPEND"; direction=-1
    if not cost_ok or row["event_ts"] < state["cooldown_until"]:
        direction = 0; gate = gate+"|COST" if not cost_ok else gate
    conf = abs(p_vol-0.5)*2
    sig = dict(direction=direction,confidence=conf,capital=0.5*conf,
               computed_at=row["event_ts"],module_state="OK",
               edge_bps=edge,cost_bps=cost,p_vol=p_vol,gate=gate)
    return sig, {"alpha":alpha,"cooldown_until":state["cooldown_until"],"module_state":"OK"}
def run(tape):
    st = init_state(); out = []
    for i,r in enumerate(tape):
        sig,st = step(st,r,CFG)
        sig = dict(sig); sig["fill_event_ts"] = tape[i+1]["event_ts"] if i+1 < len(tape) else None
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
    cols = ["computed_at", "direction", "confidence", "capital", "module_state", "edge_bps", "cost_bps", "p_vol", "gate"]
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
    bad.update({'ret_bp': float('nan')})
    st = init_state()
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
