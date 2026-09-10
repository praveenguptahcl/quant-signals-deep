"""Acceptance tests for S078 — AR(1)/ARMA short-horizon forecast.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S078.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S078_tape.csv"
EXPECTED = FIX / "S078_expected.csv"

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
CFG = {"phi":0.28,"sigma_eps_bp":4.5,"c_thr_bp":2.5,"c_exit_bp":1.0,"z_entry":2.0,
       "innov_mode":False,"W":60,"cooldown_s":300.0,"cost_gate_k":0.5}
def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    return 1.0 + 0.30 + 0.0 + 0.0   # [example] stack from the module COST block
def init_state():
    return {"prev_mid":None,"prev_r":None,"cooldown_until":0,"module_state":"OK"}
def _bad(x):
    return x is None or (isinstance(x,float) and (math.isnan(x) or not math.isfinite(x))) or x <= 0
def step(state,row,cfg):
    mid = row["mid"]
    if _bad(mid):
        sig = dict(direction=0,confidence=0.0,capital=0.0,computed_at=row["event_ts"],
                   module_state="UNKNOWN",edge_bps=0.0,cost_bps=0.0,
                   ret_bp=float("nan"),f_hat_bp=float("nan"),innov_bp=float("nan"),z=float("nan"))
        return sig, dict(state, module_state="UNKNOWN")
    if state["prev_mid"] is None:
        return (dict(direction=0,confidence=0.0,capital=0.0,computed_at=row["event_ts"],
                     module_state="OK",edge_bps=0.0,cost_bps=0.0,
                     ret_bp=float("nan"),f_hat_bp=float("nan"),innov_bp=float("nan"),z=float("nan")),
                {"prev_mid":mid,"prev_r":None,"cooldown_until":0,"module_state":"OK"})
    r = math.log(mid/state["prev_mid"])*1e4
    if state["prev_r"] is None:
        sig = dict(direction=0,confidence=0.0,capital=0.0,computed_at=row["event_ts"],
                   module_state="OK",edge_bps=0.0,cost_bps=0.0,
                   ret_bp=r,f_hat_bp=float("nan"),innov_bp=float("nan"),z=float("nan"))
        return sig, {"prev_mid":mid,"prev_r":r,"cooldown_until":state["cooldown_until"],"module_state":"OK"}
    f = cfg["phi"]*state["prev_r"]; innov = r-f; z = innov/cfg["sigma_eps_bp"]
    if not (math.isfinite(f) and math.isfinite(z)):
        sig = dict(direction=0,confidence=0.0,capital=0.0,computed_at=row["event_ts"],
                   module_state="UNKNOWN",edge_bps=0.0,cost_bps=0.0,
                   ret_bp=r,f_hat_bp=float("nan"),innov_bp=float("nan"),z=float("nan"))
        return sig, dict(state, module_state="UNKNOWN")
    edge = abs(f); cost = expected_cost_bps(1e6,0.01,"XNAS","taker","normal")
    cost_ok = cost <= cfg["cost_gate_k"]*edge
    direction = 0
    if cost_ok and row["event_ts"] >= state["cooldown_until"]:
        if not cfg["innov_mode"]:
            direction = 1 if f > cfg["c_thr_bp"] else (-1 if f < -cfg["c_thr_bp"] else 0)
        else:
            direction = 1 if z < -cfg["z_entry"] else (-1 if z > cfg["z_entry"] else 0)
    conf = min(1.0,abs(f)/(2*cfg["c_thr_bp"])) if direction else 0.0
    sig = dict(direction=direction,confidence=conf,capital=0.5*conf,
               computed_at=row["event_ts"],module_state="OK",
               edge_bps=edge,cost_bps=cost,ret_bp=r,f_hat_bp=f,innov_bp=innov,z=z)
    return sig, {"prev_mid":mid,"prev_r":r,"cooldown_until":state["cooldown_until"],"module_state":"OK"}
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
    cols = ["computed_at", "direction", "confidence", "capital", "module_state", "edge_bps", "cost_bps", "ret_bp", "f_hat_bp", "innov_bp", "z"]
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
    bad.update({'mid': float('nan')})
    st = init_state()
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
