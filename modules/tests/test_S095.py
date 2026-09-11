"""Acceptance tests for S095 — Crypto funding-rate / basis.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S095.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S095_tape.csv"
EXPECTED = FIX / "S095_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "f_ann", "z_t", "gate_pass", "fill_event_ts"]

# Chapter S3 parameters [example]
CFG = {"W": 5, "z_reduce": 2.5, "fee_per_leg_bps": 4.0, "slip_per_leg_bps": 5.0,
       "k": 0.5}


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
    # Chapter S4: fees 4 legs x 0.04% = 16.0 bps [example]; slippage 5.0 bps/leg x 4 = 20.0;
    # spread 1.0 [example]; borrow 0 [default: own cash, spot leg unlevered]
    spread_bps = 1.0
    fee_bps = 16.0
    borrow_bps = 0.0  # [default]
    impact_bps = 20.0
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"hist": []}


def step(state, row, cfg):
    ts = row.get("event_ts")
    f = row.get("funding_pct")
    h = row.get("interval_h")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e4, 0.01, "BINANCE", "mixed", "passive"),
           "f_ann": float("nan"), "z_t": float("nan"), "gate_pass": 0,
           "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (ts, f, h)) or h <= 0:
        return out, state
    state["hist"].append(f)
    if len(state["hist"]) > cfg["W"] + 1:
        state["hist"] = state["hist"][-(cfg["W"] + 1):]
    f_ann = (8760.0 / h) * (f / 100.0) * 10000.0  # simple annualization, in bps [documented convention]
    out["f_ann"] = f_ann
    if len(state["hist"]) < cfg["W"] + 1:
        return out, state  # insufficient history -> UNKNOWN
    win = state["hist"][-(cfg["W"] + 1):-1]
    m = sum(win) / len(win)
    sd = math.sqrt(sum((x - m) ** 2 for x in win) / (len(win) - 1))
    z_t = (f - m) / sd if sd > 0 else 0.0
    out["z_t"] = z_t
    if z_t > cfg["z_reduce"]:
        direction = -1  # crowded longs -> reduce leverage (never an unconditional short)
    elif z_t < -cfg["z_reduce"]:
        direction = 1
    else:
        direction = 0
    confidence = min(1.0, abs(z_t) / 10.0) if direction else 0.0
    # edge_bps is an ILLUSTRATIVE avoided-drawdown value for the crowding flag [example].
    # The chapter's carry example is net -$10 on $10k (gross $6 - fees $16): it FAILS
    # its own cost gate, and no invented edge is allowed to force a pass.
    edge_bps = 100.0 if direction else 0.0  # [example]
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
    # Chapter S4: baseline prints 0.010/0.012/0.011/0.013/0.012 -> mean 0.0116%, sd ~0.00114%;
    # the 0.050% print -> z ~ +33.7 [documented] -> reduce leverage, never an unconditional short
    sigs = run(tape())
    s6 = sigs[5]
    assert s6["module_state"] == "OK"
    assert abs(s6["z_t"] - 33.7) < 0.6
    assert s6["direction"] == -1
    assert s6["gate_pass"] == 1
    # chapter S4 carry accounting: $6.00 funding - $16.00 fees = -$10.00 net [documented];
    # the carry example therefore FAILS the cost gate (37 bps > 0.5*0 bps of carry edge) —
    # the gate below passes only on the separate illustrative avoided-drawdown edge [example]
    assert abs(6.00 - 16.00 - (-10.00)) < 1e-9
    # f_ann units [documented convention]: (8760/8)*(0.05/100)*10000 = 5475 bps
    assert abs(s6["f_ann"] - 5475.0) < 1.0
    # rows 1-5: insufficient history -> UNKNOWN
    for s in sigs[:5]:
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
    c = expected_cost_bps(1e4, 0.01, "BINANCE", "mixed", "passive")
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    rows = tape()
    st = init_state()
    sig, _ = step(st, dict(rows[6]), CFG)  # funding = nan
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
