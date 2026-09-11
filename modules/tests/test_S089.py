"""Acceptance tests for S089 — Avellaneda–Stoikov inventory-skew market making.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S089.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S089_tape.csv"
EXPECTED = FIX / "S089_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "r", "bid", "ask", "spread_bps",
                 "lambda_a", "lambda_b", "skew_bps", "gate_pass", "fill_event_ts"]

# Chapter S4 parameters (synthetic, seed 89) [example]
CFG = {"gamma": 0.1, "kappa": 1.5, "A": 140.0, "k": 0.5}


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
    # Maker quoting stack (chapter's blind spot made explicit) [example]:
    # spread 0.0 (captures, not pays) + maker rebate -0.20 + adverse fill +0.50 + latency 0.10
    spread_bps = 0.0
    fee_bps = -0.20 if side == "maker" else 0.30  # [example]
    borrow_bps = 0.0  # [default] signal emits quotes only; overnight carry is the consumer's
    impact_bps = 0.50  # adverse selection on the fill [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"updates": 0}


def step(state, row, cfg):
    ts = row.get("event_ts")
    s = row.get("s")
    q = row.get("q")
    sig = row.get("sigma")
    Tt = row.get("Tt")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e6, 0.01, "XNAS", "maker", "passive"),
           "r": float("nan"), "bid": float("nan"), "ask": float("nan"),
           "spread_bps": float("nan"), "lambda_a": float("nan"),
           "lambda_b": float("nan"), "skew_bps": 0.0, "gate_pass": 0,
           "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # F1: invalid input -> UNKNOWN, never interpolate
    if _bad(ts) or _bad(s) or _bad(q) or _bad(sig) or _bad(Tt) or sig <= 0 or Tt <= 0:
        return out, state
    g, kappa, A = cfg["gamma"], cfg["kappa"], cfg["A"]
    r = s - q * g * sig ** 2 * Tt
    dstar = 0.5 * (g * sig ** 2 * Tt + (2.0 / g) * math.log(1.0 + g / kappa))
    bid, ask = r - dstar, r + dstar
    lam_a = A * math.exp(-kappa * (ask - s))
    lam_b = A * math.exp(-kappa * (s - bid))
    skew_bps = (r - s) / s * 10000.0
    direction = 0 if q == 0 else (-1 if q > 0 else 1)
    confidence = min(1.0, abs(q) * g * sig ** 2 * Tt / dstar)
    edge_bps = 2.0 * dstar / s * 10000.0  # half-spread captured per round trip [example]
    cost_bps = out["cost_bps"]
    gate = 1 if cost_bps <= cfg["k"] * edge_bps else 0
    out.update({"module_state": "OK", "direction": direction, "confidence": confidence,
                "capital": 0.25 * confidence, "edge_bps": edge_bps, "r": r, "bid": bid,
                "ask": ask, "spread_bps": 2.0 * dstar / s * 10000.0,
                "lambda_a": lam_a, "lambda_b": lam_b, "skew_bps": skew_bps,
                "gate_pass": gate})
    state["updates"] += 1
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
    # Chapter S4 hand-checks (rounded in the chapter; tolerance here is exact):
    # q=+20 -> r=99.82, bid=99.1701, ask=100.4699, lambda_a=69.19, lambda_b=40.32 [example]
    sigs = run(tape())
    q20 = sigs[4]
    assert abs(q20["r"] - 99.82) < 1e-9
    assert abs(q20["bid"] - 99.1701148) < 1e-4
    assert abs(q20["ask"] - 100.4698852) < 1e-4
    assert abs(q20["lambda_a"] - 69.19) < 0.05
    assert abs(q20["lambda_b"] - 40.32) < 0.05
    assert abs(q20["spread_bps"] - 129.977) < 0.01
    # symmetry: lambda_a(q) == lambda_b(-q)
    qneg = sigs[0]
    assert abs(qneg["lambda_a"] - q20["lambda_b"]) / q20["lambda_b"] < 1e-9
    assert abs(qneg["lambda_b"] - q20["lambda_a"]) / q20["lambda_a"] < 1e-9
    # q=0: quotes symmetric around the mid, no lean
    q0 = sigs[2]
    assert q0["direction"] == 0
    assert abs(q0["bid"] - (100.0 - 0.6498852)) < 1e-4


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
    c = expected_cost_bps(1e6, 0.01, "XNAS", "maker", "passive")
    big_edge = c <= k * 200.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    rows = tape()
    st = init_state()
    sig, _ = step(st, dict(rows[5]), CFG)  # q = nan
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
    sig, _ = step(st, dict(rows[6]), CFG)  # s = nan
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
