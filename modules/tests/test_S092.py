"""Acceptance tests for S092 — Identified-news vs no-news drift decomposition.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S092.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S092_tape.csv"
EXPECTED = FIX / "S092_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "jump_z", "identified_news", "net_usd",
                 "gate_pass", "fill_event_ts"]

# Chapter S3 parameters [example]
CFG = {"c": 3.5, "w_min": 15, "h_min": 60, "min_jump_pct": 1.5, "k": 0.5,
       "notional": 10000.0, "all_in_bps": 5.0}


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
    # Chapter S4 explicit 5-bps all-in stack [example]: spread 2.0 + fees 1.0 + slippage 2.0
    spread_bps = 2.0
    fee_bps = 1.0
    borrow_bps = 0.0  # [default] chapter's all-in excludes borrow; add ~1.0 bps/day on short legs [example]
    impact_bps = 2.0
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"cum": 0.0}


def step(state, row, cfg):
    ts = row.get("event_ts")
    jump = row.get("jump_pct")
    z = row.get("jump_z")
    news = row.get("news_flag")
    nxt = row.get("next60_pct")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e4, 0.01, "XNAS", "taker", "urgent"),
           "jump_z": float("nan"), "identified_news": 0, "net_usd": 0.0,
           "gate_pass": 0, "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (ts, jump, z, news, nxt)) or news not in (0, 1):
        return out, state
    is_jump = abs(z) > cfg["c"] and abs(jump) >= cfg["min_jump_pct"]
    identified = 1 if (is_jump and news == 1) else 0
    if is_jump and news == 1:
        direction = 1 if jump > 0 else -1  # follow news-backed jumps
    elif is_jump:
        direction = -1 if jump > 0 else 1  # fade no-news jumps
    else:
        direction = 0
    cost_usd = cfg["notional"] * cfg["all_in_bps"] / 10000.0
    net = direction * (nxt / 100.0) * cfg["notional"] - cost_usd if direction else 0.0
    state["cum"] += net
    edge_bps = abs(nxt) * 100.0
    gate = 1 if out["cost_bps"] <= cfg["k"] * edge_bps else 0
    out.update({"module_state": "OK", "direction": direction,
                "confidence": min(1.0, abs(z) / 5.0) if direction else 0.0,
                "capital": 0.5 * min(1.0, abs(z) / 5.0) if direction else 0.0,
                "edge_bps": edge_bps, "jump_z": z, "identified_news": identified,
                "net_usd": net, "gate_pass": gate})
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
    # Chapter S4 hand-checked nets on $10,000 at 5 bps all-in ($5/event) [example]:
    # ev1 +$55, ev2 +$85, ev3 -$25, ev4 +$105, ev5 -$35, ev6 +$65 -> total +$250
    sigs = run(tape())
    want_dirs = [1, 1, 1, -1, -1, -1]
    want_nets = [55.0, 85.0, -25.0, 105.0, -35.0, 65.0]
    for i, s in enumerate(sigs):
        assert s["direction"] == want_dirs[i], f"row {i} direction"
        assert abs(s["net_usd"] - want_nets[i]) < 1e-9, f"row {i} net"
    assert abs(sum(want_nets) - 250.0) < 1e-9
    # ev1 label: news-backed -> identified=1, follow
    assert sigs[0]["identified_news"] == 1
    # ev4: no-news spike -> identified=0, fade short
    assert sigs[3]["identified_news"] == 0
    assert sigs[3]["direction"] == -1


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
    c = expected_cost_bps(1e4, 0.01, "XNAS", "taker", "urgent")
    assert abs(c - 5.0) < 1e-9, "chapter stack must total 5.0 bps"
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    st = init_state()
    bad = {"event_ts": 1, "jump_pct": float("nan"), "jump_z": 4.0,
           "news_flag": 1, "next60_pct": 0.5}
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
