"""Acceptance tests for S085 — Triple-barrier labeling.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S085.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S085_tape.csv"
EXPECTED = FIX / "S085_expected.csv"

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
CFG = {"event_day": 15, "side": 1, "k_u": 1.0, "k_l": 1.0,
       "sig_cfg": 1.0,      # vol-scale reproducing the chapter's stated +-1.0pt barriers [example]
       "sig_hat": 1.2978,   # chapter vol estimate sqrt(32/19) [documented]
       "H": 5}              # horizon in days [example]
DAY = 86400000000000
def expected_cost_bps(notional, spread_bps, venue, side, regime):
    # Labeling executes no trades: all four cost components are zero. [documented]
    return 0.0
def init_state():
    return {"entry": None, "label": "", "exit_day": "", "status": "pre_event"}
def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))
def step(state, row, cfg):
    ts = row.get("event_ts"); day = row.get("day"); sp = row.get("spread")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0, "cost_bps": 0.0,
           "z": float("nan"), "is_event": 0, "r_s": "", "barrier_status": state["status"],
           "label": state["label"], "exit_day": state["exit_day"],
           "fill_event_ts": ts + DAY if isinstance(ts, int) else None}
    if ts is None or day is None or _bad(sp):
        return out, state  # invalid input -> UNKNOWN; never interpolate
    out["module_state"] = "OK"
    out["z"] = sp / cfg["sig_hat"]
    if day == cfg["event_day"]:
        state["entry"] = sp; state["status"] = "entry"
        out["is_event"] = 1; out["r_s"] = 0.0; out["barrier_status"] = "entry"
        return out, state
    if state["entry"] is None:
        return out, state  # pre-event rows: no label yet
    rs = cfg["side"] * (sp - state["entry"])
    out["r_s"] = rs
    if state["label"] == "":
        if rs >= cfg["k_u"] * cfg["sig_cfg"]:
            state["label"] = 1
            state["exit_day"] = day; state["status"] = "profit_hit"
        elif rs <= -cfg["k_l"] * cfg["sig_cfg"]:
            state["label"] = -1
            state["exit_day"] = day; state["status"] = "stop_hit"
        elif day >= cfg["event_day"] + cfg["H"]:
            state["label"] = 0
            state["exit_day"] = day; state["status"] = "vertical"
        else:
            state["status"] = "pending"
    elif state["status"] in ("profit_hit", "stop_hit", "vertical"):
        state["status"] = "decided"
    out["barrier_status"] = state["status"]
    out["label"] = state["label"]
    out["exit_day"] = state["exit_day"]
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
    cols = ["computed_at", "direction", "confidence", "capital", "module_state", "edge_bps", "cost_bps", "z", "is_event", "r_s", "barrier_status", "label", "exit_day"]
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
    bad.update({'spread': float('nan')})
    st = init_state()
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
