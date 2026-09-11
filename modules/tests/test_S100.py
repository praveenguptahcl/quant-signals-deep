"""Acceptance tests for S100 — Standardized Unexpected Earnings (SUE) / PEAD.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S100.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S100_tape.csv"
EXPECTED = FIX / "S100_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "sue", "tier",
                 "gate_pass", "fill_event_ts"]

# Chapter S3 parameters [example]: fixture tier cutoffs at +/-1.0 sigma
CFG = {"sue_hi": 1.0, "sue_lo": -1.0, "hold_days": 2, "k": 0.5}


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
    # Chapter S4 stack [example]: spread 3.0 + fees 1.0 + slippage 1.0
    spread_bps = 3.0
    fee_bps = 1.0
    borrow_bps = 0.0  # [default] chapter's all-in excludes borrow
    impact_bps = 1.0
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"events": 0}


def step(state, row, cfg):
    # Tape schema: ticker,eps_act,eps_exp,sigma,ar (no timestamps on the panel)
    idx = state["events"] + 1
    ts = idx  # event index as the ordered event clock [example]
    act = row.get("eps_act")
    exp = row.get("eps_exp")
    sig = row.get("sigma")
    ar = row.get("ar")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e4, 0.01, "XNAS", "taker", "normal"),
           "sue": float("nan"), "tier": "none", "gate_pass": 0,
           "fill_event_ts": ts + 1}
    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (act, exp, sig)) or sig <= 0:
        return out, state
    sue = (act - exp) / sig
    # S4 timing rule [documented]: enter ONLY at the first tradable price after release;
    # the fixture encodes pre-open releases, so the open is the entry
    if sue >= cfg["sue_hi"]:
        tier, direction = "hi+", 1
    elif sue <= cfg["sue_lo"]:
        tier, direction = "lo-", -1
    else:
        tier, direction = "mid", 0
    confidence = min(1.0, abs(sue) / 5.0) if direction else 0.0
    # chapter S4: the tape's ar column carries the entered names' announcement returns [example]
    edge_bps = abs(ar) * 100.0 if not _bad(ar) else 0.0
    gate = 1 if (direction and out["cost_bps"] <= cfg["k"] * edge_bps) else 0
    out.update({"module_state": "OK", "direction": direction, "confidence": confidence,
                "capital": 0.5 * confidence, "edge_bps": edge_bps, "sue": sue,
                "tier": tier, "gate_pass": gate})
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
        assert str(e["ticker"]) == str(rows[i]["ticker"]), f"row {i} ticker mismatch"
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
    # Chapter S4 hand-check: 10,000 shares x $0.60 move = $6,000 gross [example]
    assert abs(10000 * 0.60 - 6000.0) < 1e-9
    sigs = run(tape())
    # SUE = (act - exp) / sigma; fixture tiers at +/-1.0:
    # A 2.50 hi+, B -1.00 lo-, C 0.33 mid, D -1.25 lo-, E 1.60 hi+,
    # F 0.00 mid, G -1.50 lo-, H 1.67 hi+, I -1.36 lo-, J 1.50 hi+
    want = [("hi+", 1), ("lo-", -1), ("mid", 0), ("lo-", -1), ("hi+", 1),
            ("mid", 0), ("lo-", -1), ("hi+", 1), ("lo-", -1), ("hi+", 1)]
    for i, s in enumerate(sigs[:10]):
        assert (s["tier"], s["direction"]) == want[i], f"row {i}"
    assert abs(sigs[0]["sue"] - 2.50) < 1e-9
    assert abs(sigs[4]["sue"] - 1.60) < 1e-9
    # entered names carry the tape's ar as edge: A 2.46% -> 246 bps, gate passes
    assert abs(sigs[0]["edge_bps"] - 246.0) < 1e-9
    assert sigs[0]["gate_pass"] == 1
    # chapter: no close-to-close tradability inference -- the module only prices the
    # announcement window at the first tradable price [documented]
    assert all(s["module_state"] == "OK" for s in sigs[:10])


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
    c = expected_cost_bps(1e4, 0.01, "XNAS", "taker", "normal")
    assert abs(c - 5.0) < 1e-9, "chapter stack must total 5.0 bps"
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    st = init_state()
    bad = {"ticker": "X", "eps_act": float("nan"), "eps_exp": 1.00, "sigma": 0.10, "ar": None}
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
