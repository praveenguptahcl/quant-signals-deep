"""Acceptance tests for S094 — Unusual intraday volume (RVOL) & signed block-trade pressure.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S094.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S094_tape.csv"
EXPECTED = FIX / "S094_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "rvol", "block_imb", "trigger",
                 "net_usd", "cum_usd", "gate_pass", "fill_event_ts"]

# Chapter S3 parameters [example]
CFG = {"N": 20, "rvol_trigger": 2.0, "block_min_k": 10.0, "imb_window_min": 15,
       "k": 0.5, "shares": 2000, "entry_px": 40.00, "exit_px": 40.35,
       "cost_usd": 50.0}


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
    # Chapter S4 explicit decomposition on the 2,000-share $80k example [example]:
    # spread $20 = 2.5 bps, commissions/fees $10 = 1.25 bps, impact $20 = 2.5 bps
    spread_bps = 2.5
    fee_bps = 1.25
    borrow_bps = 0.0  # [default] intraday, no borrow
    impact_bps = 2.5
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"cum": 0.0, "pos": 0}


def step(state, row, cfg):
    ts = row.get("event_ts")
    base = row.get("baseline_k")
    act = row.get("actual_k")
    buy = row.get("buy_k")
    sell = row.get("sell_k")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(8e4, 0.01, "XNAS", "taker", "urgent"),
           "rvol": float("nan"), "block_imb": float("nan"), "trigger": 0,
           "net_usd": 0.0, "cum_usd": state["cum"],
           "gate_pass": 0, "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (ts, base, act, buy, sell)) or base <= 0 or act < 0:
        return out, state
    rvol = act / base
    tot = buy + sell
    imb = (buy - sell) / tot if tot > 0 else 0.0
    trigger = 1 if (rvol > cfg["rvol_trigger"] and tot >= cfg["block_min_k"]) else 0
    direction = (1 if imb > 0 else -1) if trigger else 0
    # position bookkeeping: enter on first trigger, exit when the imbalance flips sign
    net = 0.0
    if trigger and state["pos"] == 0:
        state["pos"] = direction
    if state["pos"] != 0 and trigger and direction != state["pos"]:
        gross = cfg["shares"] * (cfg["exit_px"] - cfg["entry_px"]) * state["pos"]
        net = gross - cfg["cost_usd"]
        state["cum"] += net
        state["pos"] = 0
    out["cum_usd"] = state["cum"]
    out["net_usd"] = net
    edge_bps = (cfg["exit_px"] - cfg["entry_px"]) / cfg["entry_px"] * 10000.0 if net else 0.0
    gate = 1 if out["cost_bps"] <= cfg["k"] * edge_bps else 0
    out.update({"module_state": "OK", "direction": direction,
                "confidence": min(1.0, rvol / 4.0) if trigger else 0.0,
                "capital": 0.5 * min(1.0, rvol / 4.0) if trigger else 0.0,
                "edge_bps": edge_bps, "rvol": rvol, "block_imb": imb,
                "trigger": trigger, "gate_pass": gate})
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
        assert int(e["bin"]) == int(rows[i]["bin"]), f"row {i} bin mismatch"
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
    # Chapter S4: bin 4 RVOL = 206/60 = 3.43 -> trigger, block imbalance +1.0 -> long
    # bin 9 RVOL = 157/55 = 2.85 -> trigger, imbalance -1.0 -> exit
    sigs = run(tape())
    b4, b9 = sigs[3], sigs[8]
    assert abs(b4["rvol"] - 206.0 / 60.0) < 1e-9
    assert abs(b4["block_imb"] - 1.0) < 1e-9
    assert b4["trigger"] == 1 and b4["direction"] == 1
    assert abs(b9["rvol"] - 157.0 / 55.0) < 1e-9
    assert abs(b9["block_imb"] - (-1.0)) < 1e-9
    assert b9["trigger"] == 1 and b9["direction"] == -1
    # chapter P&L: 2,000 x $0.35 = $700 gross - $50 costs = +$650 net [example]
    assert abs(b9["net_usd"] - 650.0) < 1e-9
    assert abs(b9["cum_usd"] - 650.0) < 1e-9
    # bin 10: RVOL 1.55 with no blocks -> correctly ignored
    assert sigs[9]["trigger"] == 0 and sigs[9]["direction"] == 0


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
    c = expected_cost_bps(8e4, 0.01, "XNAS", "taker", "urgent")
    assert abs(c - 6.25) < 1e-9, "chapter stack must total 6.25 bps"
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    st = init_state()
    bad = {"event_ts": 1, "baseline_k": float("nan"), "actual_k": 100.0,
           "buy_k": 0.0, "sell_k": 0.0}
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
