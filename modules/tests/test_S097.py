"""Acceptance tests for S097 — Social / media sentiment.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic. The module is a feature/gate, not a standalone
direction source.

Run: python3 -m pytest modules/tests/test_S097.py -q   (from repo root)
"""
import csv
import math
import statistics
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S097_tape.csv"
EXPECTED = FIX / "S097_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "z_vol", "S", "veto", "gate_pass", "fill_event_ts"]

# Chapter S3 parameters [example]
CFG = {"z_entry": 1.96, "W": 5, "k": 0.5}


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
    # Small-cap long/short holding 2-5 days [example]: spread 5.0 + fees 1.0 + impact 4.0 + borrow 5.0
    spread_bps = 5.0
    fee_bps = 1.0
    borrow_bps = 5.0  # [example] hard-to-borrow short leg
    impact_bps = 4.0
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"vol_hist": []}  # raw post counts of the five PRIOR days (t-W:t-1), never t


def step(state, row, cfg):
    ts = row.get("event_ts")
    vol = row.get("posts")
    sent = row.get("w_sent")
    hhi = row.get("hhi")  # tape stores HHI as a 0-1 fraction
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e4, 0.01, "XNAS", "mixed", "normal"),
           "z_vol": float("nan"), "S": float("nan"), "veto": 0, "gate_pass": 0,
           "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (ts, vol, sent, hhi)) or vol < 0 or not (-1.0 <= sent <= 1.0) \
            or not (0.0 <= hhi <= 1.0):
        return out, state
    # chapter S3 [documented]: z uses the five PRIOR days, excluding the current observation
    if len(state["vol_hist"]) < cfg["W"]:
        state["vol_hist"].append(vol)
        return out, state  # insufficient history -> UNKNOWN
    m = statistics.mean(state["vol_hist"])
    sd = statistics.stdev(state["vol_hist"])  # sample sd, denominator W-1
    z = (vol - m) / sd if sd > 0 else 0.0
    state["vol_hist"] = (state["vol_hist"] + [vol])[-cfg["W"]:]  # exactly the five prior days
    # chapter S3/S4 [documented]: HHI > 0.25 flags campaign-dominated buckets;
    # the manipulation diagnostic VETOES the sentiment leg
    veto = 1 if hhi > 0.25 else 0  # 0.25 threshold is an [example] desk gate
    S = z * sent  # composite: volume z times weighted signed sentiment [example]
    gate = 1 if (abs(z) > cfg["z_entry"] and not veto) else 0
    if gate:
        direction = 1 if S > 0 else (-1 if S < 0 else 0)
    else:
        direction = 0
    confidence = min(1.0, abs(z) / 10.0) if gate else 0.0
    edge_bps = abs(S) * 20.0 if gate else 0.0  # illustrative [example]
    cost_gate = 1 if out["cost_bps"] <= cfg["k"] * edge_bps else 0
    out.update({"module_state": "OK", "direction": direction, "confidence": confidence,
                "capital": 0.5 * confidence, "edge_bps": edge_bps, "z_vol": z, "S": S,
                "veto": veto, "gate_pass": cost_gate if gate else 0})
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
        assert int(e["day"]) == int(rows[i]["day"]), f"row {i} day mismatch"
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
    # Chapter S4 hand-check [documented]: day-6 z uses the FIVE PRIOR days
    # [123, 143, 117, 138, 132]; mean = 130.60; sd = 10.6442; z = +26.25
    sigs = run(tape())
    d6 = sigs[5]
    assert d6["module_state"] == "OK"
    assert abs(d6["z_vol"] - 26.25) < 0.02
    assert d6["veto"] == 0
    assert d6["direction"] == 1  # volume shock with positive weighted sentiment
    assert abs(d6["S"] - 26.25 * 0.120) < 0.05  # composite = z * w_sent
    assert d6["gate_pass"] == 1
    # day 7: z ~ +6.36 but HHI 0.3168 > 0.25 -> campaign-dominated -> vetoed, no trade
    d7 = sigs[6]
    assert d7["module_state"] == "OK"
    assert abs(d7["z_vol"] - 6.36) < 0.02
    assert d7["veto"] == 1
    assert d7["direction"] == 0  # the veto is the signal's most valuable output
    # day 10: no volume trigger (|z| ~ 1.05 < 1.96) -> flat, composite still defined
    d10 = sigs[9]
    assert d10["module_state"] == "OK"
    assert d10["direction"] == 0
    assert abs(d10["z_vol"] - (-1.05)) < 0.02
    # days 1-5: insufficient history (fewer than five prior days) -> UNKNOWN
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
    c = expected_cost_bps(1e4, 0.01, "XNAS", "mixed", "normal")
    assert abs(c - 15.0) < 1e-9, "chapter stack must total 15.0 bps"
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    st = init_state()
    bad = {"event_ts": 1, "posts": -1.0, "raw_sent": 0.5, "w_sent": 0.5, "hhi": 0.02}
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
