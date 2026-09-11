"""Acceptance tests for S090 — Variance-ratio / Hurst regime toggle.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S090.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S090_tape.csv"
EXPECTED = FIX / "S090_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "vr2", "h2", "vr4", "h4", "label",
                 "gate_pass", "fill_event_ts"]

# Chapter S3/S4: rolling window W=9, horizons {2,4}, bands [example]
CFG = {"W": 9, "k_set": (2, 4), "vr_hi": 1.10, "vr_lo": 0.90, "k": 0.5}


def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def _num(v):
    if v is None or v == "":
        return None
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


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    # The toggled book's own stack (the label places no trades of its own) [example]
    return 2.0


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def _svar(xs):
    n = len(xs)
    m = sum(xs) / n
    return sum((x - m) ** 2 for x in xs) / (n - 1)


def _vr_h(r, k):
    rk = [sum(r[i:i + k]) for i in range(len(r) - k + 1)]
    vr = _svar(rk) / (k * _svar(r))
    h = 0.5 * (1.0 + math.log(vr) / math.log(k))
    return vr, h


def init_state():
    return {"win": []}


def step(state, row, cfg):
    ts = row.get("event_ts")
    r = row.get("r")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal"),
           "vr2": float("nan"), "h2": float("nan"), "vr4": float("nan"),
           "h4": float("nan"), "label": "insufficient", "gate_pass": 0,
           "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # F1: invalid input -> UNKNOWN, never interpolate
    if _bad(ts) or _bad(r) or not math.isfinite(r):
        state["win"] = []  # invalid return breaks the window; never interpolate
        return out, state
    state["win"].append(r)
    if len(state["win"]) > cfg["W"]:
        state["win"] = state["win"][-cfg["W"]:]
    if len(state["win"]) < cfg["W"]:
        return out, state  # insufficient window -> UNKNOWN
    w = state["win"]
    vr2, h2 = _vr_h(w, 2)
    vr4, h4 = _vr_h(w, 4)
    out.update({"module_state": "OK", "vr2": vr2, "h2": h2, "vr4": vr4, "h4": h4})
    if vr2 > cfg["vr_hi"]:
        label, direction, conf = "persist", 1, min(1.0, (vr2 - 1.0) * 2.0)
    elif vr2 < cfg["vr_lo"]:
        label, direction, conf = "revert", -1, min(1.0, (1.0 - vr2) * 2.0)
    else:
        label, direction, conf = "random_walk", 0, 0.0
    edge_bps = 8.0 if direction != 0 else 0.0  # illustrative regime-timing value [example]
    gate = 1 if out["cost_bps"] <= cfg["k"] * edge_bps else 0
    out.update({"label": label, "direction": direction, "confidence": conf,
                "capital": 0.25 * conf, "edge_bps": edge_bps, "gate_pass": gate})
    return out, state


def run(rows):
    st = init_state()
    out = []
    for r in rows:
        sig, st = step(st, r, CFG)
        out.append(sig)
    return out


def _close(a, b):
    if a is None and b is None:
        return True
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
    for i, (s, e) in enumerate(zip(sigs, exp)):
        assert int(e["ev"]) == int(rows[i]["ev"]), f"row {i} ev mismatch"
        for c in EXPECTED_COLS:
            got = s[c]
            want = _num(e[c])
            assert _close(got, want), f"row {i} col {c}: got {got} want {want}"


def test_signal_vector_valid():
    for s in run(tape()):
        assert s["direction"] in (+1, -1, 0), "direction not in {+1,-1,0}"
        assert 0.0 <= s["confidence"] <= 1.0, "confidence out of [0,1]"
        assert 0.0 <= s["capital"] <= 0.5, "capital out of [0,0.5]"
        assert s["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_hand_checks():
    # Chapter S4 corrected arithmetic (operator-verified): k=2 -> VR=1.5714, H=0.826;
    # k=4 -> VR=0.8000, H=0.4195 [documented]
    sigs = run(tape())
    full = sigs[8]
    assert full["module_state"] == "OK"
    assert abs(full["vr2"] - 1.5714) < 1e-3
    assert abs(full["h2"] - 0.826) < 1e-3
    assert abs(full["vr4"] - 0.8000) < 1e-3
    assert abs(full["h4"] - 0.4195) < 1e-3
    assert full["label"] == "persist"
    assert full["direction"] == 1
    # horizon contradiction: same tape says revert at k=4
    assert full["vr4"] < 0.90
    # rows 1-8: insufficient window -> UNKNOWN
    for s in sigs[:8]:
        assert s["module_state"] == "UNKNOWN"


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
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    rows = tape()
    st = init_state()
    sig, _ = step(st, dict(rows[9]), CFG)  # r = nan
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
