"""Acceptance tests for S083 — Imbalance/tick/volume/dollar bars.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S083.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S083_tape.csv"
EXPECTED = FIX / "S083_expected.csv"

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
CFG = {"tick_n": 5, "vol_shares": 3000, "imb_theta": 1500.0}  # [example] fixture scale
def expected_cost_bps(notional, spread_bps, venue, side, regime):
    # The sampler executes no trades: all four cost components are zero. [documented]
    return 0.0
def init_state():
    def _nb():
        return {"id": 0, "acc": 0.0, "o": None, "h": None, "l": None, "c": None}
    return {"tick": _nb(), "vol": _nb(), "imb": _nb()}
def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))
def _out(ts, ok):
    return {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
            "module_state": "OK" if ok else "UNKNOWN", "edge_bps": 0.0, "cost_bps": 0.0,
            "fill_event_ts": ts + 1 if isinstance(ts, int) else None,
            "tick_id": 0, "tick_done": 0, "tick_o": float("nan"), "tick_h": float("nan"),
            "tick_l": float("nan"), "tick_c": float("nan"),
            "vol_id": 0, "vol_done": 0, "vol_o": float("nan"), "vol_h": float("nan"),
            "vol_l": float("nan"), "vol_c": float("nan"),
            "imb_id": 0, "imb_done": 0, "imb_o": float("nan"), "imb_h": float("nan"),
            "imb_l": float("nan"), "imb_c": float("nan"), "theta": float("nan")}
def _upd(nb, px, w, thresh, absolute):
    if nb["o"] is None:
        nb["o"] = nb["h"] = nb["l"] = nb["c"] = px
    else:
        nb["h"] = max(nb["h"], px); nb["l"] = min(nb["l"], px); nb["c"] = px
    nb["acc"] += w
    hit = abs(nb["acc"]) >= thresh if absolute else nb["acc"] >= thresh
    if hit:
        snap = (nb["id"], nb["o"], nb["h"], nb["l"], nb["c"], nb["acc"])
        nb["id"] += 1; nb["acc"] = 0.0
        nb["o"] = nb["h"] = nb["l"] = nb["c"] = None
        return snap
    return None
def step(state, row, cfg):
    ts = row.get("event_ts"); px = row.get("price"); sz = row.get("size"); sg = row.get("sign")
    if ts is None or _bad(px) or _bad(sz) or sg not in (1, -1):
        return _out(ts, False), state  # invalid input -> UNKNOWN; never interpolate
    t = _upd(state["tick"], px, 1, cfg["tick_n"], False)
    v = _upd(state["vol"], px, sz, cfg["vol_shares"], False)
    m = _upd(state["imb"], px, sg * sz, cfg["imb_theta"], True)
    o = _out(ts, True)
    for key, snap, prefix in (("tick", t, "tick"), ("vol", v, "vol"), ("imb", m, "imb")):
        nb = state[key]
        o[prefix + "_id"] = snap[0] if snap else nb["id"]
        o[prefix + "_done"] = 1 if snap else 0
        src = snap[1:5] if snap else (nb["o"], nb["h"], nb["l"], nb["c"])
        o[prefix + "_o"], o[prefix + "_h"], o[prefix + "_l"], o[prefix + "_c"] = src
    o["theta"] = m[5] if m else state["imb"]["acc"]
    return o, state
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
    cols = ["computed_at", "direction", "confidence", "capital", "module_state", "edge_bps", "cost_bps", "tick_id", "tick_done", "tick_o", "tick_h", "tick_l", "tick_c", "vol_id", "vol_done", "vol_o", "vol_h", "vol_l", "vol_c", "imb_id", "imb_done", "imb_o", "imb_h", "imb_l", "imb_c", "theta"]
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
