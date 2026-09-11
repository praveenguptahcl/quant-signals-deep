"""Acceptance tests for S099 — Google Trends ASVI.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S099.py -q   (from repo root)
"""
import csv
import math
import statistics
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S099_tape.csv"
EXPECTED = FIX / "S099_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "asvi", "exposure", "gate_pass", "fill_event_ts"]

# Chapter S3 parameters [example]
CFG = {"delta": 1.0, "k": 0.5, "notional": 100000.0, "fee_rate_bps": 1.0}


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
    # Chapter S4 stack [example]: commissions/fees 1.0 + spread 2.0 + impact 3.0
    spread_bps = 2.0
    fee_bps = 1.0
    borrow_bps = 0.0  # [default] chapter example is long-only on the ASVI screen
    impact_bps = 3.0
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"B_hist": []}


def step(state, row, cfg):
    ts = row.get("event_ts")
    svi = row.get("svi")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e5, 0.01, "XNAS", "taker", "normal"),
           "asvi": float("nan"), "exposure": float("nan"), "gate_pass": 0,
           "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (ts, svi)) or svi <= 0:
        return out, state
    B = math.log(svi)
    state["B_hist"].append(B)
    # separate-download warning: the prior 8-week median must come from a download
    # that strictly precedes the current week (no renormalization on fresh data)
    if len(state["B_hist"]) < 9:
        return out, state  # insufficient history -> UNKNOWN
    window = state["B_hist"][-9:-1]
    med = statistics.median(window)
    asvi = B - med
    clipped = max(-cfg["delta"], min(cfg["delta"], asvi))
    exposure = 1.0 + clipped  # long-only scale around full exposure [example]
    out["asvi"] = asvi
    out["exposure"] = exposure
    direction = 1  # exposure scaler, not a direction signal
    confidence = min(1.0, abs(asvi))
    # chapter S4 hand-check: fee drag 0.75 + spread 1.50 = 2.25 bps/event [example]
    cost = cfg["notional"] * (cfg["fee_rate_bps"] / 10000.0)
    edge_bps = abs(asvi) * 100.0
    gate = 1 if out["cost_bps"] <= cfg["k"] * edge_bps else 0
    out.update({"module_state": "OK", "direction": direction, "confidence": confidence,
                "capital": 0.5 * confidence, "edge_bps": edge_bps, "gate_pass": gate})
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
        assert int(e["week"]) == int(rows[i]["week"]), f"row {i} week mismatch"
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
    # Chapter S4 worked numbers [example]: ln(100)=4.6052, ln(50)=3.9120,
    # ASVI = 4.6052-3.9120 = +0.6931; ln(75)=4.3175 -> 4.3175-3.9120 = +0.4055
    assert abs(math.log(100.0) - 4.6052) < 1e-4
    assert abs(math.log(50.0) - 3.9120) < 1e-4
    assert abs((math.log(100.0) - math.log(50.0)) - 0.6931) < 1e-4
    assert abs((math.log(75.0) - math.log(50.0)) - 0.4055) < 1e-4
    # chapter cost accounting: 0.75 bps fee = $7.50 on $100k, spread 1.50 bps = $15.00 [example]
    assert abs(1e5 * 0.75 / 10000.0 - 7.50) < 1e-9
    assert abs(1e5 * 1.50 / 10000.0 - 15.00) < 1e-9
    sigs = run(tape())
    # weeks 1-8: insufficient history -> UNKNOWN
    for s in sigs[:8]:
        assert s["module_state"] == "UNKNOWN"
    s9 = sigs[8]
    assert s9["module_state"] == "OK"
    # week 9: prior 8-week median of ln(svi) for weeks 1-8 (18,22,19,25,21,24,23,20)
    B9 = math.log(88.0)
    prior = [math.log(x) for x in (18, 22, 19, 25, 21, 24, 23, 20)]
    assert abs(s9["asvi"] - (B9 - statistics.median(prior))) < 1e-9
    assert s9["exposure"] > 1.0, "positive ASVI must scale exposure above 1x"
    assert s9["gate_pass"] == 1


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
    c = expected_cost_bps(1e5, 0.01, "XNAS", "taker", "normal")
    assert abs(c - 6.0) < 1e-9, "chapter stack must total 6.0 bps"
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    st = init_state()
    bad = {"event_ts": 1, "week": 99, "svi": 0.0}
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
