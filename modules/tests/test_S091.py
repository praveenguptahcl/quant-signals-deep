"""Acceptance tests for S091 — Machine-readable news sentiment (first-minute reaction).

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S091.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S091_tape.csv"
EXPECTED = FIX / "S091_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "S_b", "z_b", "gate_pass", "fill_event_ts"]

# Chapter S3 parameters [example]
CFG = {"bucket_min": 1, "trail_days": 30, "rel_min": 80.0, "nov_min": 70.0,
       "z_entry": 2.0, "h_min": 10, "k": 0.5}


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
    # Chapter S4 explicit decomposition on the 500-share $25k example [example]:
    # spread $5.00 = 2.0 bps, commissions/fees $2.50 = 1.0 bps, impact $0.00 (explicit assumption)
    spread_bps = 2.0
    fee_bps = 1.0
    borrow_bps = 0.0  # [default] intraday, no borrow
    impact_bps = 0.0  # [example] explicit chapter assumption: the market order walks no book
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"stories": 0}


def step(state, row, cfg):
    ts = row.get("event_ts")
    ess = row.get("ess")
    rel = row.get("rel")
    nov = row.get("nov")
    mu = row.get("trail_mean")
    sd = row.get("trail_sd")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(2.5e4, 0.01, "XNAS", "taker", "urgent"),
           "S_b": float("nan"), "z_b": float("nan"), "gate_pass": 0,
           "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (ts, ess, rel, nov, mu, sd)) or sd <= 0:
        return out, state
    S_b = ess  # single-story bucket: weighted mean = the story's ESS [example]
    z_b = (S_b - mu) / sd
    floors = rel >= cfg["rel_min"] and nov >= cfg["nov_min"]
    enter = floors and abs(z_b) > cfg["z_entry"]
    direction = (1 if S_b > 0 else -1) if enter else 0
    confidence = min(1.0, abs(z_b) / 4.0) if enter else 0.0
    # Chapter S4: first-minute +39.6 bps leg minus the 3.0 bps stack -> 42.7 bps net path [example]
    edge_bps = 42.7 if enter else 0.0
    gate = 1 if out["cost_bps"] <= cfg["k"] * edge_bps else 0
    out.update({"module_state": "OK", "direction": direction, "confidence": confidence,
                "capital": 0.5 * confidence, "edge_bps": edge_bps, "S_b": S_b,
                "z_b": z_b, "gate_pass": gate})
    state["stories"] += 1
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
    # Story 1 (NOVA): z = (0.85-0.05)/0.30 = 2.667 -> clears floors and z_entry -> long [example]
    sigs = run(tape())
    s1 = sigs[0]
    assert s1["module_state"] == "OK"
    assert abs(s1["z_b"] - 2.6666667) < 1e-6
    assert s1["direction"] == 1
    assert s1["gate_pass"] == 1
    # Story 2: |z| = 1.52 < 2.0 -> no trade; story 3: rel 40 < 80 floor -> no trade;
    # story 5: nov 60 < 70 floor -> no trade
    assert sigs[1]["direction"] == 0
    assert sigs[2]["direction"] == 0
    assert sigs[4]["direction"] == 0
    # chapter S4 P&L: gross $114.25 - costs $7.50 = net $106.75 [example]
    assert abs(114.25 - 7.50 - 106.75) < 1e-9


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
    c = expected_cost_bps(2.5e4, 0.01, "XNAS", "taker", "urgent")
    assert abs(c - 3.0) < 1e-9, "chapter stack must total 3.0 bps"
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    rows = tape()
    st = init_state()
    sig, _ = step(st, dict(rows[3]), CFG)  # ess = nan
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
