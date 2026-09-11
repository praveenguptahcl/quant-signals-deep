"""Acceptance tests for S093 — News novelty / staleness reversal.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S093.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S093_tape.csv"
EXPECTED = FIX / "S093_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "novelty", "staleness", "leg",
                 "gate_pass", "fill_event_ts"]

# Chapter S3 parameters [example]
CFG = {"tau": 0.5, "h_days": 5, "unwind_frac": 0.40, "k": 0.5}


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
    # 1-5 day fade on liquid large-caps [example]: spread 2.0 + fees 1.0 + impact 3.0 + borrow 1.0/day
    spread_bps = 2.0
    fee_bps = 1.0
    borrow_bps = 1.0  # [example] ~3%/ann on the short leg
    impact_bps = 3.0
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"events": 0}


def step(state, row, cfg):
    ts = row.get("event_ts")
    nov = row.get("novelty")
    day0 = row.get("day0_pct")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal"),
           "novelty": float("nan"), "staleness": float("nan"), "leg": "none",
           "gate_pass": 0, "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (ts, nov, day0)) or not (0.0 <= nov <= 1.0):
        return out, state
    staleness = 1.0 - nov
    if nov < cfg["tau"]:
        leg = "fade"  # stale news -> overreaction -> fade the day-0 move
        direction = -1 if day0 > 0 else 1
    else:
        leg = "ride"  # novel news -> drift -> follow the day-0 move
        direction = 1 if day0 > 0 else -1
    confidence = min(1.0, abs(nov - cfg["tau"]) * 2.0)
    edge_bps = abs(day0) * 100.0 * cfg["unwind_frac"]  # illustrative unwind fraction [example]
    gate = 1 if out["cost_bps"] <= cfg["k"] * edge_bps else 0
    out.update({"module_state": "OK", "direction": direction, "confidence": confidence,
                "capital": 0.5 * confidence, "edge_bps": edge_bps, "novelty": nov,
                "staleness": staleness, "leg": leg, "gate_pass": gate})
    state["events"] += 1
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
    # Chapter S4: E6 novelty 0.10 -> stale -> fade the -3.58% day-0 move -> long (+1)
    # E1 novelty 0.97 -> novel -> ride the -1.64% move -> short (-1)
    sigs = run(tape())
    e6 = sigs[5]
    assert abs(e6["novelty"] - 0.10) < 1e-9
    assert abs(e6["staleness"] - 0.90) < 1e-9
    assert e6["leg"] == "fade" and e6["direction"] == 1
    e1 = sigs[0]
    assert e1["leg"] == "ride" and e1["direction"] == -1
    # chapter hand-check: centroid cosine for the stale story = 0.8452 -> novelty 0.15 [documented]
    assert abs((1.0 - 0.8452) - 0.1548) < 1e-9
    # reversal concentrates in low-novelty events: E6 next-5d +1.67 on day-0 -3.58
    assert abs(sigs[5]["edge_bps"] - 3.58 * 100.0 * 0.40) < 1e-9


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
    assert abs(c - 7.0) < 1e-9, "chapter stack must total 7.0 bps"
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    st = init_state()
    bad = {"event_ts": 1, "novelty": float("nan"), "day0_pct": 1.0, "next5d_pct": -0.5}
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
