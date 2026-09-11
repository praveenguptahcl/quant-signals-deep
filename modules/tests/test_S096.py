"""Acceptance tests for S096 — Crypto OI shocks & liquidation clusters.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic. All reported_* inputs are censored lower bounds.

Run: python3 -m pytest modules/tests/test_S096.py -q   (from repo root)
"""
import csv
import math
import statistics
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S096_tape.csv"
EXPECTED = FIX / "S096_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "shock_flag", "cascade_flag", "flip_flag",
                 "fade_window", "gate_pass", "fill_event_ts"]

# Chapter S3 parameters [example]
CFG = {"k_oi": 2.0, "m_liq": 5.0, "depth_drop": 0.50, "fade_h": 4, "k": 0.5}


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
    # Post-cascade fade in stressed conditions [example]: spread 3.0 + fees 8.0 + slippage 10.0
    spread_bps = 3.0
    fee_bps = 8.0
    borrow_bps = 0.0  # [default] spot-hour horizon, no borrow
    impact_bps = 10.0  # stressed slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def _sgn(x):
    return 1 if x > 0 else (-1 if x < 0 else 0)


def init_state():
    return {"liq_hist": [], "prev_f": None, "fade_left": 0,
            "prev_px": None, "prev_oi": None,
            "prev_shock": 0, "prev_disloc": 0, "bars_since_cascade": 999}


def step(state, row, cfg):
    ts = row.get("event_ts")
    px = row.get("price")
    oi = row.get("reported_oi_b")
    f = row.get("reported_funding")
    ll = row.get("reported_liq_long_m")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e4, 0.01, "BINANCE", "taker", "urgent"),
           "shock_flag": 0, "cascade_flag": 0, "flip_flag": 0, "fade_window": 0,
           "gate_pass": 0, "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (ts, px, oi, f, ll)):
        return out, state
    baseline = statistics.median(state["liq_hist"]) if state["liq_hist"] else 0.05
    state["liq_hist"].append(ll)
    shock = 1 if ll > cfg["m_liq"] * baseline else 0
    # dislocation: forced flow must meet a price/OI dislocation [example thresholds];
    # h48/h49 have elevated reported liqs (0.32/0.23) but NO dislocation, so no cascade
    px_drop = (px - state["prev_px"]) / state["prev_px"] if state["prev_px"] else 0.0
    oi_drop = (oi - state["prev_oi"]) / state["prev_oi"] if state["prev_oi"] else 0.0
    disloc = 1 if (px_drop <= -0.01 or oi_drop <= -0.03) else 0
    state["prev_px"], state["prev_oi"] = px, oi
    # cascade = sustained forced flow ADJACENT to the dislocation: shock at t AND shock
    # at t-1 AND dislocation at t-1. h50 is the shock bar; h51 is the cascade peak.
    cascade = 1 if (shock and state["prev_shock"] and state["prev_disloc"]) else 0
    state["prev_shock"], state["prev_disloc"] = shock, disloc
    state["bars_since_cascade"] = 0 if cascade else state["bars_since_cascade"] + 1
    flip = 1 if (state["prev_f"] is not None and _sgn(f) != _sgn(state["prev_f"])
                and f != 0 and state["prev_f"] != 0) else 0
    state["prev_f"] = f
    # fade rule: funding flip confirms a *recent* cascade -> fade the exhaustion move
    if flip and state["bars_since_cascade"] <= 8:
        state["fade_left"] = cfg["fade_h"]
    fade = 1 if state["fade_left"] > 0 else 0
    if fade:
        state["fade_left"] -= 1
    direction = 1 if fade else 0  # fade the washed-out long liquidation
    confidence = 0.6 if fade else 0.0  # [example] confirmed-cascade confidence
    # HONESTY: the +1.61% move (99.23 -> 100.83) happens BEFORE the h53 flip confirms;
    # the rule entering at h53 does NOT harvest it, so it is not claimed as edge.
    # edge_bps is an illustrative residual-normalization value for the h53+ window [example].
    edge_bps = 80.0 if fade else 0.0  # [example]
    gate = 1 if out["cost_bps"] <= cfg["k"] * edge_bps else 0
    out.update({"module_state": "OK", "direction": direction, "confidence": confidence,
                "capital": 0.5 * confidence, "edge_bps": edge_bps,
                "shock_flag": shock, "cascade_flag": cascade, "flip_flag": flip,
                "fade_window": fade, "gate_pass": gate})
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
        assert int(e["hour"]) == int(rows[i]["hour"]), f"row {i} hour mismatch"
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
    # Chapter S4 ordered flag sequence [documented]: h50 shock (-1.6% price, -6.1% OI),
    # h51 cascade peak (8.5M long liqs, ~40x baseline), h52 flow slows, h53 funding flips
    sigs = run(tape())
    h50, h51, h53 = sigs[5], sigs[6], sigs[8]
    assert h50["shock_flag"] == 1 and h50["cascade_flag"] == 0
    assert h51["cascade_flag"] == 1
    assert h53["flip_flag"] == 1
    assert abs((0.891 - 0.949) / 0.949 - (-0.061)) < 1e-3  # OI drop -6.1%
    assert abs((99.23 - 100.86) / 100.86 - (-0.0162)) < 1e-4  # price drop -1.62%
    # the fade fires only at/after the flip confirmation (h53), not at the h51 low
    assert sigs[6]["fade_window"] == 0  # h51: no fade without the flip
    assert h53["fade_window"] == 1 and h53["direction"] == 1
    # entering at h53 harvests h53-h57 (100.83 -> 100.42 = -0.41%), not the +1.61% bounce
    assert abs((100.42 - 100.83) / 100.83 - (-0.00407)) < 1e-4
    # the +1.61% pre-confirmation bounce is never claimed as edge: edge_bps is the
    # illustrative post-confirmation value (80 bps), not 161 bps
    assert h53["edge_bps"] == 80.0


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
    c = expected_cost_bps(1e4, 0.01, "BINANCE", "taker", "urgent")
    assert abs(c - 21.0) < 1e-9, "chapter stack must total 21.0 bps"
    big_edge = c <= k * 200.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    st = init_state()
    bad = {"event_ts": 1, "price": float("nan"), "reported_oi_b": 0.9,
           "reported_funding": 0.0, "reported_liq_long_m": 0.1,
           "reported_liq_short_m": 0.0}
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
