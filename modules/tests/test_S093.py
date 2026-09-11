"""Acceptance tests for S093 — News novelty / staleness reversal.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, gate-veto
semantics, boundary conditions, invalid-input handling, and hand-checked
arithmetic.

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

# Chapter S0.2 Config (status: calibrate; defaults below are [example])
CFG = {"n_prior": 10, "stale_gate": 0.5, "h_days": 5, "unwind_frac": 0.40, "k_gate": 0.5}


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
    # Mirrors the S2 COST block exactly: 1-5-day event stack (taker entry).
    spread_bps = 2.0            # [example]
    fee_bps = 1.0               # [example]
    borrow_bps_per_day = 0.25   # [example]; reason: fade leg shorts positive day-0 moves
    h_days = CFG["h_days"]      # [example]; reversal_h_days default
    borrow_bps = borrow_bps_per_day * h_days
    impact_bps = 3.0            # [example] 1-5-day fade execution at small participation
    total = spread_bps + fee_bps + borrow_bps + impact_bps
    if side == "maker":
        total = 0.5 * spread_bps + fee_bps + borrow_bps + impact_bps  # [example] maker concession
    return total


def _bad(x):
    return x is None or (isinstance(x, float) and (math.isnan(x) or not math.isfinite(x)))


def init_state():
    return {"events": 0, "last": None, "cooldown": {}}


def step(state, row, cfg, market_state="CONTINUOUS_TRADING"):
    ts = row.get("event_ts")
    nov = row.get("novelty")
    day0 = row.get("day0_pct")
    # S3 guards: halt/closed freeze, auction holds last vector
    if market_state in ("HALTED", "CLOSED"):
        out = dict(state["last"] or {"computed_at": ts, "direction": 0, "confidence": 0.0,
                                     "capital": 0.0, "edge_bps": 0.0, "novelty": float("nan"),
                                     "staleness": float("nan"), "leg": "none", "gate_pass": 0,
                                     "fill_event_ts": None})
        out.update({"computed_at": ts, "module_state": "UNKNOWN", "fill_event_ts": None})
        return out, state
    if market_state == "AUCTION":
        out = dict(state["last"] or {"computed_at": ts, "direction": 0, "confidence": 0.0,
                                     "capital": 0.0, "edge_bps": 0.0, "novelty": float("nan"),
                                     "staleness": float("nan"), "leg": "none", "gate_pass": 0,
                                     "fill_event_ts": None})
        out.update({"module_state": "DEGRADED"})
        return out, state
    cost_bps = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": cost_bps,
           "novelty": float("nan"), "staleness": float("nan"), "leg": "none",
           "gate_pass": 0, "fill_event_ts": None}
    # F1: invalid input -> UNKNOWN, never interpolate. No signal => no fill scheduled.
    if (not isinstance(ts, int) or isinstance(ts, bool) or ts <= 0
            or _bad(nov) or _bad(day0) or not (0.0 <= nov <= 1.0) or day0 == 0.0):
        return out, state
    # F4 staleness TTL (S0.4): features older than 3 s -> UNKNOWN, never interpolate.
    if row.get("feed_age_s", 0) > 3:
        return out, state
    # F3/min-set (S2): fewer than n_prior stories -> similarity undefined -> UNKNOWN.
    if row.get("n_prior_stories", cfg["n_prior"]) < cfg["n_prior"]:
        return out, state
    staleness = 1.0 - nov
    if nov < cfg["stale_gate"]:
        leg = "fade"  # stale news -> overreaction -> fade the day-0 move
        direction = -1 if day0 > 0 else 1
    else:
        leg = "ride"  # novel news -> drift -> follow the day-0 move
        direction = 1 if day0 > 0 else -1
    # C10 story-arc cooldown: no re-fade of the same arc within 5 sessions [default].
    arc = row.get("story_arc", "ev%d" % row.get("ev", -1))
    last_ts = state["cooldown"].get(arc)
    if last_ts is not None and ts - last_ts <= 5 * 86400_000_000_000:
        direction = 0
    # C7 Reg-SHO locate: the short leg needs the consumer's locate_ok assertion.
    if direction < 0 and not row.get("locate_ok", True):
        direction = 0
    edge_bps = abs(day0) * 100.0 * cfg["unwind_frac"]  # illustrative per-event bps [example]
    gate_pass = 1 if cost_bps <= cfg["k_gate"] * edge_bps else 0
    if gate_pass and direction != 0:
        confidence = min(1.0, abs(nov - cfg["stale_gate"]) * 2.0)
        capital = 0.5 * confidence
        fill_event_ts = ts + 1  # earliest honest reaction is t+1; no signal-bar fills
    else:
        # C2 veto: sub-threshold or vetoed scores emit direction 0 — never a tradeable hint.
        direction, confidence, capital, fill_event_ts = 0, 0.0, 0.0, None
    out.update({"module_state": "OK", "direction": direction, "confidence": confidence,
                "capital": capital, "edge_bps": edge_bps, "novelty": nov,
                "staleness": staleness, "leg": leg, "gate_pass": gate_pass,
                "fill_event_ts": fill_event_ts})
    state["events"] += 1
    if direction != 0:
        state["cooldown"][arc] = ts  # C10: arm the story-arc cooldown only on live signals
    state["last"] = dict(out)
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
        if s["direction"] == 0:
            assert s["confidence"] == 0.0 and s["capital"] == 0.0, "direction 0 must carry no tradeable hint"


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
    # chapter hand-check: centroid cosine for the stale story = 0.8452 -> novelty 0.1548 [example]
    assert abs((1.0 - 0.8452) - 0.1548) < 1e-9
    # reversal concentrates in low-novelty events: E6 next-5d +1.67 on day-0 -3.58
    assert abs(e6["edge_bps"] - 3.58 * 100.0 * 0.40) < 1e-9


def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()):
        fill_event = s["fill_event_ts"]
        signal_event = s["computed_at"]
        if fill_event is not None:
            assert fill_event > signal_event


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k_gate * edge_bps
    c = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")
    assert abs(c - 7.25) < 1e-9, "chapter stack must total 7.25 bps (2.0+1.0+1.25+3.0)"
    m = expected_cost_bps(1e6, 0.01, "XNAS", "maker", "normal")
    assert abs(m - 6.25) < 1e-9, "maker variant must total 6.25 bps"
    k = 0.5  # [default]
    assert c <= k * 100.0, "cost gate should pass on a large edge"
    assert not (c <= k * 0.01), "cost gate should block on a tiny edge"


def test_cost_gate_veto():
    # E11: novelty 0.40 -> stale -> fade a +0.05% day-0 move; edge 2.0 bps;
    # 7.25 <= 0.5*2.0 fails -> veto: direction 0, no tradeable hint, no fill.
    sigs = run(tape())
    e11 = sigs[10]
    assert e11["leg"] == "fade"
    assert abs(e11["edge_bps"] - 2.0) < 1e-9
    assert e11["gate_pass"] == 0
    assert e11["direction"] == 0 and e11["confidence"] == 0.0 and e11["capital"] == 0.0
    assert e11["fill_event_ts"] is None, "vetoed signal must schedule no fill"
    assert e11["module_state"] == "OK"


def test_boundary_novelty_equals_stale_gate():
    # boundary: novelty == stale_gate is NOT fade (fade requires <). Ride leg.
    st = init_state()
    row = {"event_ts": 1788946200000000000, "novelty": 0.5, "day0_pct": 1.0, "next5d_pct": 0.0}
    sig, _ = step(st, row, CFG)
    assert sig["leg"] == "ride" and sig["direction"] == 1
    assert sig["confidence"] == 0.0, "at the gate, confidence must be 0"
    # just below the gate -> fade
    row2 = dict(row, novelty=0.499999999)
    sig2, _ = step(st, row2, CFG)
    assert sig2["leg"] == "fade"


def test_invalid_input_unknown():
    st = init_state()
    bad_rows = [
        {"event_ts": 1, "novelty": float("nan"), "day0_pct": 1.0, "next5d_pct": -0.5},  # NaN novelty
        {"event_ts": 1, "novelty": 1.5, "day0_pct": 1.0, "next5d_pct": -0.5},           # novelty out of [0,1]
        {"event_ts": 1, "novelty": -0.1, "day0_pct": 1.0, "next5d_pct": -0.5},          # novelty out of [0,1]
        {"event_ts": 1, "novelty": None, "day0_pct": 1.0, "next5d_pct": -0.5},         # missing novelty
        {"event_ts": 1, "novelty": 0.2, "day0_pct": float("inf"), "next5d_pct": -0.5}, # non-finite price
        {"event_ts": 1, "novelty": 0.2, "day0_pct": 0.0, "next5d_pct": -0.5},           # zero move
        {"novelty": 0.2, "day0_pct": 1.0},                                             # missing event_ts
    ]
    for b in bad_rows:
        sig, _ = step(st, b, CFG)
        assert sig["module_state"] == "UNKNOWN", f"invalid input must map to UNKNOWN: {b}"
        assert sig["fill_event_ts"] is None, "invalid input must schedule no fill"
        assert sig["direction"] == 0


def test_invalid_tape_row_e12():
    # E12: novelty NaN -> F1 -> UNKNOWN, never interpolated
    sigs = run(tape())
    e12 = sigs[11]
    assert e12["module_state"] == "UNKNOWN"
    assert e12["direction"] == 0 and e12["fill_event_ts"] is None


def test_empty_tape():
    assert run([]) == [], "empty events must yield no signals, not a crash"


def test_market_state_handling():
    # halt/closed freeze -> UNKNOWN, no fill; auction holds last vector as DEGRADED
    st = init_state()
    good = {"event_ts": 1788946200000000000, "novelty": 0.9, "day0_pct": -1.0, "next5d_pct": 0.0}
    sig, st = step(st, good, CFG)
    assert sig["module_state"] == "OK"
    halt, st = step(st, dict(good, event_ts=1788946260000000000), CFG, market_state="HALTED")
    assert halt["module_state"] == "UNKNOWN" and halt["fill_event_ts"] is None
    closed, st = step(st, dict(good, event_ts=1788946320000000000), CFG, market_state="CLOSED")
    assert closed["module_state"] == "UNKNOWN"
    auc, st = step(st, dict(good, event_ts=1788946380000000000), CFG, market_state="AUCTION")
    assert auc["module_state"] == "DEGRADED"
    assert (auc["direction"], auc["confidence"]) == (sig["direction"], sig["confidence"]), \
        "auction must hold the last signal vector"


def test_staleness_ttl_unknown():
    # F4: features older than the 3 s TTL -> UNKNOWN, never interpolated.
    st = init_state()
    row = {"event_ts": 1788946200000000000, "novelty": 0.9, "day0_pct": -1.0,
           "next5d_pct": 0.0, "feed_age_s": 30}
    sig, _ = step(st, row, CFG)
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0 and sig["fill_event_ts"] is None


def test_min_comparison_set_unknown():
    # F3/min-set (S2): fewer than n_prior stories -> similarity undefined -> UNKNOWN.
    st = init_state()
    row = {"event_ts": 1788946200000000000, "novelty": 0.9, "day0_pct": -1.0,
           "next5d_pct": 0.0, "n_prior_stories": 7}
    sig, _ = step(st, row, CFG)
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0 and sig["fill_event_ts"] is None


def test_locate_veto_on_short_leg():
    # C7: ride leg on a negative day-0 move -> short; without the consumer's
    # locate_ok assertion the short leg is vetoed to direction 0.
    st = init_state()
    row = {"event_ts": 1788946200000000000, "novelty": 0.9, "day0_pct": -1.0,
           "next5d_pct": 0.0, "locate_ok": False}
    sig, _ = step(st, row, CFG)
    assert sig["leg"] == "ride" and sig["gate_pass"] == 1
    assert sig["direction"] == 0 and sig["confidence"] == 0.0 and sig["capital"] == 0.0
    assert sig["fill_event_ts"] is None


def test_story_arc_cooldown_veto():
    # C10: no re-fade of the same story arc inside the 5-session cooldown.
    st = init_state()
    r1 = {"ev": 1, "event_ts": 1788946200000000000, "novelty": 0.1, "day0_pct": -3.0,
          "next5d_pct": 1.0, "story_arc": "arcA"}
    r2 = {"ev": 2, "event_ts": 1788946260000000000, "novelty": 0.1, "day0_pct": -2.0,
          "next5d_pct": 1.0, "story_arc": "arcA"}
    s1, st = step(st, r1, CFG)
    assert s1["direction"] == 1 and s1["gate_pass"] == 1
    s2, st = step(st, r2, CFG)
    assert s2["direction"] == 0 and s2["confidence"] == 0.0 and s2["capital"] == 0.0
    assert s2["fill_event_ts"] is None, "cooldown-vetoed signal must schedule no fill"
    assert s2["module_state"] == "OK"
