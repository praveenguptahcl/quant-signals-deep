"""Acceptance tests for S092 — Identified-news vs no-news drift decomposition.

Module v1.1.0, template v1.0.0. Runs a reference implementation of the
chapter's normative pseudocode (§S3) over two tapes:

  * S092_tape.csv        — 6 synthetic jump events (validation-run)
  * S092_edge.csv        — 5 edge cases: boundary |z|==threshold, cost-gate veto,
                           invalid input -> UNKNOWN, halt -> UNKNOWN,
                           no-news down-jump -> fade long

and asserts causality, the cost gate (as entry condition), invalid-input ->
UNKNOWN, locate/cooldown/staleness/halt guards, and hand-checked arithmetic.

CFG below mirrors the §S0.2 Config defaults. The reference uses the fixture's
illustrative per-event edge (|next60_pct| x 100) [example] as documented in
§S3/§S4; the production path uses the calibrated cfg.edge_bps_identified /
cfg.edge_bps_nonews defaults (60/70 [default]), asserted in
test_production_edge_defaults.

Run: python3 -m pytest modules/tests/test_S092.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S092_tape.csv"
EXPECTED = FIX / "S092_expected.csv"
EDGE_TAPE = FIX / "S092_edge.csv"
EDGE_EXPECTED = FIX / "S092_edge_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "jump_z", "identified_news", "net_usd",
                 "gate_pass", "fill_event_ts"]
EDGE_COLS = EXPECTED_COLS + ["note"]

# Chapter S0.2 Config defaults. Statuses: calibrate for jump_z, news_window_min,
# drift_horizon_min, z_lookback_bars, edge_bps_identified, edge_bps_nonews,
# cooldown_min; default for k; example for notional/all_in_bps.
CFG = {"jump_z": 3.0, "min_jump_pct": 1.5, "news_window_min": 15.0,
       "drift_horizon_min": 60.0, "z_lookback_bars": 78,
       "edge_bps_identified": 60.0, "edge_bps_nonews": 70.0,
       "k": 0.5, "notional": 10000.0, "all_in_bps": 5.0, "z_scale": 5.0,
       "staleness_ttl_s": 3, "cooldown_min": 60}


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


def tape(path=TAPE):
    rows = []
    for r in load_csv(path):
        d = {}
        for k, v in r.items():
            d[k] = _num(v)
        rows.append(d)
    return rows


def cost_components():
    # Chapter S2 COST block, mirrored exactly [example]; borrow_bps_per_day = 0.0
    # [default] with reason in the table (no overnight borrow in the fixture legs).
    return {"spread_bps": 2.5, "fee_bps": 0.5, "borrow_bps": 0.0, "impact_bps": 2.0}


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    c = cost_components()
    return c["spread_bps"] + c["fee_bps"] + c["borrow_bps"] + c["impact_bps"]


def cost_gate_pass(cost_bps, edge_bps, k):
    # Normative predicate (§S3): expected_cost_bps(...) <= k * edge_bps
    return cost_bps <= k * edge_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"cum": 0.0, "last": None}


def step(state, row, cfg):
    """Reference implementation of the §S3 normative pseudocode.

    Fixture path: edge_bps is the tape's illustrative per-event
    |next60_pct| x 100 [example] (see §S4). Production path: calibrated
    cfg.edge_bps_identified / cfg.edge_bps_nonews.
    """
    ts = row.get("event_ts")
    jump = row.get("jump_pct")          # percent
    z = row.get("jump_z")
    news = row.get("news_flag")
    nxt = row.get("next60_pct")         # percent; fixture accounting only [example]
    now_ts = row.get("now_ts", ts)
    asof_ts = row.get("asof_ts", ts)
    market_state = row.get("market_state", "CONTINUOUS_TRADING")
    if row.get("halt_flag") == 1:       # edge-tape halt simulation (§S0.5)
        market_state = "HALTED"
    locate_ok = row.get("locate_ok", True)
    ev = row.get("event_id", row.get("ev"))

    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e4, 0.01, "XNAS", "taker", "urgent"),
           "jump_z": z, "identified_news": 0, "net_usd": 0.0,
           "gate_pass": 0, "fill_event_ts": None, "note": None}

    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (ts, now_ts, asof_ts, jump, z, nxt)) \
            or news not in (0, 1) or not isinstance(ev, int):
        out["note"] = "invalid input -> UNKNOWN"
        return out, state
    # F4: staleness -> UNKNOWN
    if (now_ts - asof_ts) > cfg["staleness_ttl_s"] * 1e9:
        out["note"] = "stale input -> UNKNOWN"
        return out, state
    # Market-state table (§S0.5)
    if market_state == "HALTED":
        out["note"] = "HALT freeze -> UNKNOWN"
        return out, state
    if market_state == "AUCTION":
        out["module_state"] = "DEGRADED"
        out["note"] = "AUCTION -> DEGRADED"
        return out, state
    if market_state == "CLOSED":
        out["module_state"] = "OFF"
        out["note"] = "CLOSED -> OFF"
        return out, state

    out["module_state"] = "OK"
    is_jump = abs(z) > cfg["jump_z"] and abs(jump) >= cfg["min_jump_pct"]
    identified = 1 if (is_jump and news == 1) else 0
    out["identified_news"] = identified

    leg = 0
    if is_jump:
        leg = (1 if z > 0 else -1) if identified else (-1 if z > 0 else 1)
    # C10: post-emission cooldown — no re-signal of the same jump event id
    last = state.get("last")
    if leg != 0 and last is not None and last["ev"] == ev \
            and (now_ts - last["ts"]) <= cfg["cooldown_min"] * 60e9:
        leg = 0
        out["note"] = "cooldown: same jump re-signaled"
    # C7: locate veto on short legs
    if leg < 0 and not locate_ok:
        leg = 0
        out["note"] = "locate missing -> direction 0"

    cost_bps = out["cost_bps"]
    edge_bps = abs(nxt) * 100.0 if is_jump else 0.0  # fixture edge [example]
    out["edge_bps"] = edge_bps
    gate = 1 if (leg != 0 and cost_gate_pass(cost_bps, edge_bps, cfg["k"])) else 0
    out["gate_pass"] = gate
    if leg != 0 and not gate:
        leg = 0  # C2 bona-fide-intent veto -> direction 0, state stays OK
        out["note"] = "cost gate veto -> direction 0"
    if leg == 0 and out["note"] is None and not is_jump:
        out["note"] = "no jump (|z| <= threshold)"

    confidence = min(1.0, abs(z) / cfg["z_scale"]) if leg else 0.0
    capital = 0.5 * confidence if leg else 0.0
    net = leg * (nxt / 100.0) * cfg["notional"] \
        - cfg["notional"] * cfg["all_in_bps"] / 10000.0 if leg else 0.0
    state["cum"] += net
    out.update({"direction": leg, "confidence": confidence, "capital": capital,
                "net_usd": net})
    if leg != 0:
        out["fill_event_ts"] = ts + 1  # next bar's first honest quote; pin causality
        assert out["fill_event_ts"] > out["computed_at"]  # no signal-bar fills
        state["last"] = {"ev": ev, "ts": now_ts}
    return out, state


def run(rows):
    st = init_state()
    out = []
    for r in rows:
        sig, st = step(st, r, CFG)
        out.append(sig)
    return out


def ev_row(ev, jump_z, jump_pct, news_flag, next60_pct, **kw):
    """Synthetic event row (not from a tape) for guard/boundary tests."""
    r = {"ev": ev, "event_ts": 1789000000000000000 + ev * 10,
         "jump_pct": jump_pct, "jump_z": jump_z, "news_flag": news_flag,
         "next60_pct": next60_pct}
    r.update(kw)
    return r


def _close(a, b):
    if a is None and b is None:
        return True
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(b))
    return a == b


def _assert_rows(sigs, exp_rows, tape_rows, cols, label):
    assert len(exp_rows) == len(sigs), f"{label}: expected row count != tape row count"
    for i, (s, e) in enumerate(zip(sigs, exp_rows)):
        assert int(e["ev"]) == int(tape_rows[i]["ev"]), f"{label} row {i} ev mismatch"
        for c in cols:
            got = s[c]
            want = _num(e[c])
            assert _close(got, want), f"{label} row {i} col {c}: got {got!r} want {want!r}"


def test_fixtures_exist_and_typed():
    for path in (TAPE, EXPECTED, EDGE_TAPE, EDGE_EXPECTED):
        assert path.exists(), f"{path.name} missing"
        with open(path) as f:
            head = [next(f) for _ in range(3)]
        assert any(l.startswith("# TYPE:") for l in head), f"{path.name} missing TYPE header"
    assert len(tape()) >= 5, "main tape needs >=5 hand-checkable rows"
    assert len(tape(EDGE_TAPE)) >= 3, "edge tape needs >=3 rows"


def test_expected_matches_reference():
    rows = tape()
    _assert_rows(run(rows), load_csv(EXPECTED), rows, EXPECTED_COLS, "main tape")


def test_edge_tape_matches_reference():
    rows = tape(EDGE_TAPE)
    _assert_rows(run(rows), load_csv(EDGE_EXPECTED), rows, EDGE_COLS, "edge tape")


def test_signal_vector_valid():
    for s in run(tape()) + run(tape(EDGE_TAPE)):
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
    # edge tape ev11: no-news down-jump -> fade long, +$35 [example]
    edge = run(tape(EDGE_TAPE))
    assert edge[4]["direction"] == 1
    assert abs(edge[4]["net_usd"] - 35.0) < 1e-9


def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()) + run(tape(EDGE_TAPE)):
        fill_event = s["fill_event_ts"]
        signal_event = s["computed_at"]
        if fill_event is not None:
            assert fill_event > signal_event


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5  # [default]
    c = expected_cost_bps(1e4, 0.01, "XNAS", "taker", "urgent")
    assert abs(c - 5.0) < 1e-9, "chapter stack must total 5.0 bps"
    assert cost_gate_pass(c, 100.0, k), "gate should pass on a large edge"
    assert not cost_gate_pass(c, 0.01, k), "gate should block on a tiny edge"


def test_cost_block_mirror():
    # The callable must mirror the §S2 COST block component-by-component.
    c = cost_components()
    assert abs(c["spread_bps"] - 2.5) < 1e-12   # [example]
    assert abs(c["fee_bps"] - 0.5) < 1e-12      # [example]
    assert abs(c["borrow_bps"] - 0.0) < 1e-12   # [default] borrow_bps_per_day = 0.0
    assert abs(c["impact_bps"] - 2.0) < 1e-12   # [example]
    assert abs(sum(c.values()) - 5.0) < 1e-12


def test_production_edge_defaults():
    # §S0.2 production edge estimator defaults: the gate passes on them for both legs.
    assert abs(CFG["edge_bps_identified"] - 60.0) < 1e-12  # [default]
    assert abs(CFG["edge_bps_nonews"] - 70.0) < 1e-12     # [default]
    c = expected_cost_bps(1e4, 0.01, "XNAS", "taker", "urgent")
    assert cost_gate_pass(c, CFG["edge_bps_identified"], CFG["k"])
    assert cost_gate_pass(c, CFG["edge_bps_nonews"], CFG["k"])


def test_boundary_at_threshold():
    # |jump_z| == cfg.jump_z is NOT a jump (strict >); no signal, state OK.
    st = init_state()
    sig, _ = step(st, ev_row(101, 3.0, 1.6, 1, 0.5), CFG)
    assert sig["module_state"] == "OK"
    assert sig["direction"] == 0
    assert sig["gate_pass"] == 0
    assert sig["fill_event_ts"] is None
    # just above the threshold with news -> follow long
    sig2, _ = step(init_state(), ev_row(102, 3.01, 1.6, 1, 0.5), CFG)
    assert sig2["direction"] == 1
    assert sig2["gate_pass"] == 1


def test_gate_veto_emits_direction_zero():
    # Tiny edge fails the gate -> bona-fide-intent veto: direction 0, state OK.
    st = init_state()
    sig, _ = step(st, ev_row(103, 4.0, 2.0, 1, 0.01), CFG)  # edge = 1 bps
    assert sig["module_state"] == "OK"
    assert sig["gate_pass"] == 0
    assert sig["direction"] == 0
    assert sig["confidence"] == 0.0
    assert sig["capital"] == 0.0
    assert sig["net_usd"] == 0.0
    assert sig["fill_event_ts"] is None


def test_invalid_input_unknown():
    st = init_state()
    bad = {"event_ts": 1, "jump_pct": float("nan"), "jump_z": 4.0,
           "news_flag": 1, "next60_pct": 0.5}
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
    assert sig["direction"] == 0
    # bad news_flag value -> UNKNOWN
    sig2, _ = step(init_state(), ev_row(104, 4.0, 2.0, 2, 0.5), CFG)
    assert sig2["module_state"] == "UNKNOWN"
    # missing price -> UNKNOWN
    sig3, _ = step(init_state(), ev_row(105, 4.0, None, 1, 0.5), CFG)
    assert sig3["module_state"] == "UNKNOWN"


def test_locate_veto_on_short_leg():
    # No-news positive jump -> fade short; locate_ok=False vetoes to direction 0.
    st = init_state()
    row = ev_row(106, 4.2, 2.1, 0, -0.9, locate_ok=False)
    sig, _ = step(st, row, CFG)
    assert sig["module_state"] == "OK"
    assert sig["direction"] == 0, "short leg without locate must be vetoed (C7)"
    # with locate asserted the same row emits the fade short
    sig2, _ = step(init_state(), ev_row(106, 4.2, 2.1, 0, -0.9, locate_ok=True), CFG)
    assert sig2["direction"] == -1


def test_market_state_table():
    st = init_state()
    sig, _ = step(st, ev_row(107, 4.0, 2.0, 1, 0.5, market_state="HALTED"), CFG)
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0
    sig2, _ = step(init_state(), ev_row(107, 4.0, 2.0, 1, 0.5, market_state="AUCTION"), CFG)
    assert sig2["module_state"] == "DEGRADED"
    sig3, _ = step(init_state(), ev_row(107, 4.0, 2.0, 1, 0.5, market_state="CLOSED"), CFG)
    assert sig3["module_state"] == "OFF"


def test_staleness_unknown():
    st = init_state()
    ts = 1789000000000000000
    row = ev_row(108, 4.0, 2.0, 1, 0.5)
    row["asof_ts"] = ts - 4_000_000_000  # 4 s old > 3 s TTL [default]
    row["now_ts"] = ts
    sig, _ = step(st, row, CFG)
    assert sig["module_state"] == "UNKNOWN", "stale input must map to UNKNOWN"
    # fresh as-of passes
    row2 = ev_row(108, 4.0, 2.0, 1, 0.5)
    row2["asof_ts"] = row2["now_ts"] = row2["event_ts"]
    sig2, _ = step(init_state(), row2, CFG)
    assert sig2["module_state"] == "OK"


def test_cooldown_same_jump():
    # Re-signaling the same jump event id within cooldown -> direction 0 (C10).
    st = init_state()
    row = ev_row(109, 4.0, 2.0, 1, 0.5)
    sig1, st = step(st, row, CFG)
    assert sig1["direction"] == 1
    sig2, _ = step(st, row, CFG)
    assert sig2["direction"] == 0, "same jump re-signaled inside cooldown"
    assert sig2["module_state"] == "OK"
    # a different jump event still signals
    sig3, _ = step(st, ev_row(110, 4.2, 2.1, 1, 0.6), CFG)
    assert sig3["direction"] == 1
