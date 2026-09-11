"""Acceptance tests for S091 — News sentiment z-score (ESS).

Template v1.0.0, module v1.1.0. Loads the fixture tape, runs a reference
implementation of the chapter's normative pseudocode (S3), and asserts
causality, the cost-gate veto, boundary conditions, invalid-input -> UNKNOWN,
halt freeze, cooldown, and hand-checked arithmetic.

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

# Chapter S3 config [calibrate] per S0.2a, except k and age cutoff [default]
CFG = {"z_entry": 2.0, "rel_floor": 80.0, "nov_floor": 70.0, "trail_n": 30,
       "k": 0.5, "age_cutoff_min": 120}


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
    """Callable cost model — mirrors the chapter COST block exactly (S2).
    News-reaction stack (taker): spread 1.5 + fees 0.5 + borrow 0.0 + impact 1.0 [example]."""
    spread_bps = 1.5   # [example] news-reaction spread at the example notional
    fee_bps = 0.5      # [example] venue schedule
    borrow_bps = 0.0   # [default] long leg in the chapter's sketch; intraday
    impact_bps = 1.0   # [example] chasing the first-minute move
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))


def init_state():
    return {"cooldown_stories": set()}


def step(state, row, cfg, t_now=None, locate_ok=True):
    """Reference implementation of the S3 normative pseudocode."""
    ts = row.get("event_ts")
    ess = row.get("ess")
    rel = row.get("rel")
    nov = row.get("nov")
    mu = row.get("trail_mean")
    sd = row.get("trail_sd")
    mstate = row.get("market_state")
    illust_edge = row.get("illust_edge_bps")
    story_id = row.get("story_id") or ""
    t_now = ts if t_now is None else t_now
    s_b_out = ess if isinstance(ess, float) else float("nan")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": illust_edge if not _bad(illust_edge) else 0.0,
           "cost_bps": expected_cost_bps(2.5e4, 0.01, "XNAS", "taker", "urgent"),  # [example] ref args
           "S_b": s_b_out, "z_b": float("nan"), "gate_pass": 0,
           "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # F1: invalid / non-finite input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (ts, t_now, ess, rel, nov, mu, sd, illust_edge)):
        return out, state
    if mstate not in ("CONTINUOUS_TRADING", "HALTED", "AUCTION", "CLOSED"):
        return out, state
    # Market-state table (S0.5): non-continuous -> freeze, no new signal
    if mstate != "CONTINUOUS_TRADING":
        out["module_state"] = {"HALTED": "UNKNOWN", "AUCTION": "DEGRADED",
                               "CLOSED": "OFF"}[mstate]
        return out, state
    # F2: mathematical bounds
    if not (-1.0 <= ess <= 1.0) or not (0.0 <= rel <= 100.0) \
            or not (0.0 <= nov <= 100.0) or sd <= 0:
        return out, state
    # Staleness: story age cutoff (mask, state stays OK)
    if (t_now - ts) > cfg["age_cutoff_min"] * 60 * 1_000_000_000:  # [default] 120 min
        out["module_state"] = "OK"
        return out, state
    # Cooldown: no re-entry on the same story_id (C10)
    if story_id and story_id in state["cooldown_stories"]:
        out["module_state"] = "OK"
        return out, state
    S_b = ess
    z_b = (S_b - mu) / sd
    out["z_b"] = z_b
    floors_ok = rel >= cfg["rel_floor"] and nov >= cfg["nov_floor"]
    enter = floors_ok and abs(z_b) > cfg["z_entry"]  # strict >
    # Cost gate: executable predicate -> veto (C2), never a tradeable hint
    gate = out["cost_bps"] <= cfg["k"] * illust_edge
    out["gate_pass"] = 1 if gate else 0
    if not gate:
        enter = False
    if enter and S_b > 0.0:
        direction = 1
    elif enter and S_b < 0.0:
        direction = -1 if locate_ok else 0  # C7 Reg-SHO locate
    else:
        direction = 0  # includes S_b == 0: zero sentiment never trades
    confidence = min(1.0, abs(z_b) / 4.0) if direction != 0 else 0.0  # [default]
    capital = 0.5 * confidence if direction != 0 else 0.0  # [default]
    out.update({"module_state": "OK", "direction": direction,
                "confidence": confidence, "capital": capital})
    if direction != 0 and story_id:
        state["cooldown_stories"].add(story_id)
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


def _row(**kw):
    base = {"ev": 0, "event_ts": 1788946203000000000, "ess": 0.0, "rel": 90.0,
            "nov": 90.0, "trail_mean": 0.0, "trail_sd": 0.3,
            "market_state": "CONTINUOUS_TRADING", "illust_edge_bps": 0.0,
            "story_id": "SYN"}
    base.update(kw)
    return base


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
    assert len(rows) >= 9, "fixture needs >=9 rows (tradable, veto, boundary, invalid, halt)"


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
    # normative predicate: expected_cost_bps(...) <= k * edge_bps; veto on failure (C2)
    k = 0.5  # [default]
    c = expected_cost_bps(2.5e4, 0.01, "XNAS", "taker", "urgent")  # [example] ref args
    assert abs(c - (1.5 + 0.5 + 0.0 + 1.0)) < 1e-9, "callable must mirror the COST block"
    assert abs(c - 3.0) < 1e-9, "chapter stack must total 3.0 bps"
    assert c <= k * 100.0, "cost gate should pass on a large edge"
    assert not (c <= k * 0.01), "cost gate should block on a tiny edge"


def test_cost_gate_veto():
    # Story 6: z=3.0 and floors pass, but 3.0 bps > 0.5*4.0 bps -> vetoed, direction 0 [example]
    s6 = run(tape())[5]
    assert s6["module_state"] == "OK"
    assert s6["gate_pass"] == 0, "gate must fail on a sub-threshold edge"
    assert s6["direction"] == 0, "vetoed stories emit no tradeable hint (C2)"
    assert s6["confidence"] == 0.0 and s6["capital"] == 0.0


def test_boundary_z_equals_entry():
    # Story 7: |z| == 2.0 exactly -> strict > fails -> no trade (boundary pin) [example]
    s7 = run(tape())[6]
    assert s7["z_b"] == 2.0
    assert s7["direction"] == 0


def test_invalid_input_unknown():
    rows = tape()
    st = init_state()
    sig, _ = step(st, dict(rows[3]), CFG)  # ess = nan
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"


def test_out_of_bounds_unknown():
    # Story 8: ess = 1.5 outside [-1,1] -> UNKNOWN (F2), never interpolate
    s8 = run(tape())[7]
    assert s8["module_state"] == "UNKNOWN"
    assert s8["direction"] == 0


def test_halt_freeze():
    # Story 9: HALTED -> freeze, UNKNOWN, no new signal
    s9 = run(tape())[8]
    assert s9["module_state"] == "UNKNOWN"
    assert s9["direction"] == 0


def test_cooldown_no_repeat():
    # Same story_id emitted twice -> second emission vetoed (C10)
    rows = tape()
    st = init_state()
    first, st = step(st, dict(rows[0]), CFG)
    assert first["direction"] == 1
    second, _ = step(st, dict(rows[0]), CFG)
    assert second["direction"] == 0, "no re-entry on the same story_id"
    assert second["module_state"] == "OK"


def test_short_locate_veto():
    # Bearish high-|z| story: SHORT needs locate_ok (C7)
    row = _row(ess=-0.95, trail_mean=0.05, illust_edge_bps=42.7, story_id="SHORT-1")
    st = init_state()
    blocked, _ = step(st, dict(row), CFG, locate_ok=False)
    assert blocked["direction"] == 0, "SHORT without locate must be blocked"
    assert blocked["module_state"] == "OK"
    allowed, _ = step(init_state(), dict(row), CFG, locate_ok=True)
    assert allowed["direction"] == -1


def test_zero_sentiment_no_trade():
    # ess = 0.0 with |z| > 2.0 -> enter logic true but S_b == 0 -> direction 0, no capital
    row = _row(ess=0.0, trail_mean=-0.603, illust_edge_bps=42.7, story_id="ZERO-1")
    st = init_state()
    sig, _ = step(st, row, CFG)
    assert sig["module_state"] == "OK"
    assert sig["direction"] == 0
    assert sig["confidence"] == 0.0 and sig["capital"] == 0.0


def test_stale_story_masked():
    # Story older than age_cutoff_min -> masked (state OK, no signal)
    rows = tape()
    st = init_state()
    old_now = rows[0]["event_ts"] + 121 * 60 * 1_000_000_000  # 121 min later [default] cutoff
    sig, _ = step(st, dict(rows[0]), CFG, t_now=old_now)
    assert sig["direction"] == 0
    assert sig["module_state"] == "OK"
