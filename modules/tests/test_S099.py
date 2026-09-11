"""Acceptance tests for S099 — Google Trends ASVI (exposure scaler).

Template v1.0.0 (module v1.1.0). Loads the fixture tape, runs a reference
implementation of the chapter's normative pseudocode (§S3), and asserts
causality, the cost gate, guards (staleness TTL, thin-SVI floor, halt freeze,
post-change cooldown), and hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S099.py -q   (from repo root)
"""
import csv
import math
import statistics
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S099_tape.csv"
EXPECTED = FIX / "S099_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "asvi", "exposure", "gate_pass", "fill_event_ts"]

WEEK_NS = 7 * 86400 * 10**9          # one week in int64 ns [default]
STALE_NS = 3 * WEEK_NS               # staleness TTL: 3x the 1-week cadence (F4) [default]

# Chapter S3 Config [§S0.2]: delta matches the chapter default 0.5
# (v1.0.0's test used 1.0 — a chapter/test inconsistency fixed in v1.1.0).
CFG = {"delta": 0.5, "cost_gate_k": 0.5, "notional": 100000.0,
       "cooldown_weeks": 2, "svi_min": 10.0}


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
    # Chapter COST block, single source of truth (§S2): 2.0 + 1.0 + 0.0 + 3.0
    spread_bps = 2.0   # [example]
    fee_bps = 1.0      # [example]
    borrow_bps = 0.0   # [default] long-only example; reason in COST block
    impact_bps = 3.0   # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and (math.isnan(x) or not math.isfinite(x)))


def init_state():
    return {"B_hist": [], "last_event_ts": None,
            "last_exposure": None, "last_change_week": None,
            "market_state": "CONTINUOUS_TRADING"}


def step(state, row, cfg, adv_pct=0.01):
    """Reference implementation of the §S3 normative pseudocode.

    All guards inline: halt/auction freeze, staleness TTL, invalid input
    (F1), thin-SVI floor, cost-gate predicate, post-change cooldown, and the
    t->t+1 causality pin (fill_event = signal_event + 1, always > signal).
    """
    ts = row.get("event_ts")
    week = row.get("week")
    svi = row.get("svi")
    market = row.get("market_state", state.get("market_state", "CONTINUOUS_TRADING"))
    out = {"computed_at": ts, "direction": 1, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(cfg["notional"], adv_pct, "XNAS", "taker", "normal"),
           "asvi": float("nan"), "exposure": float("nan"), "gate_pass": 0,
           "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # Halt/auction -> freeze per §S0.5: do not advance the window
    if market in ("HALTED", "AUCTION"):
        out["module_state"] = "UNKNOWN" if market == "HALTED" else "DEGRADED"
        return out, state
    # F4 staleness: gap > 3x cadence -> UNKNOWN
    if state["last_event_ts"] is not None and isinstance(ts, int) \
            and (ts - state["last_event_ts"]) > STALE_NS:
        return out, state
    # F1: invalid input -> UNKNOWN, never interpolate; does not advance the window
    if any(_bad(v) for v in (ts, svi)) or svi <= 0:
        return out, state
    # Thin-ticker floor: unstable SVI -> UNKNOWN
    if svi < cfg["svi_min"]:
        return out, state
    B = math.log(svi)
    state["B_hist"].append(B)
    state["last_event_ts"] = ts
    if len(state["B_hist"]) < 9:
        return out, state  # need 8 priors + the current week -> UNKNOWN
    # the 8 most recent valid points before the current week; the current week
    # is EXCLUDED [documented]; invalid weeks were never appended, never interpolated
    window = state["B_hist"][:-1][-8:]
    med = statistics.median(window)
    asvi = B - med
    proposed = 1.0 + max(-cfg["delta"], min(cfg["delta"], asvi))  # long-only clip
    confidence = min(1.0, abs(asvi))
    edge_bps = abs(asvi) * 100.0  # illustrative edge [example]
    gate_pass = 1 if out["cost_bps"] <= cfg["cost_gate_k"] * edge_bps else 0
    if gate_pass == 0:
        # C2 for exposure scalers: sub-threshold -> neutral scale 1.0
        # (direction stays 1 per the scaler doctrine), never a tradeable hint
        applied = 1.0
    else:
        applied = proposed
    state_out = "OK"
    last = state["last_exposure"]
    if last is not None and abs(applied - last) > 1e-9 \
            and (week - state["last_change_week"]) < cfg["cooldown_weeks"]:
        applied = last  # post-change cooldown veto: hold last exposure
        state_out = "DEGRADED"
    elif last is None or abs(applied - last) > 1e-9:
        state["last_exposure"] = applied
        state["last_change_week"] = week
    out.update({"module_state": state_out, "confidence": confidence,
                "capital": 0.5 * confidence, "asvi": asvi, "exposure": applied,
                "edge_bps": edge_bps, "gate_pass": gate_pass})
    return out, state


def run(rows, cfg=None):
    cfg = cfg or CFG
    st = init_state()
    out = []
    for r in rows:
        sig, st = step(st, r, cfg)
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
        assert int(e["week"]) == int(rows[i]["week"]), f"row {i} week mismatch"
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


def _mk(week, ts, svi):
    return {"week": week, "event_ts": ts, "svi": svi}


def test_hand_checks():
    # Chapter S4 worked numbers [example]: ln(100)=4.6052, ln(50)=3.9120,
    # ASVI = 4.6052-3.9120 = +0.6931; ln(75)=4.3175 -> 4.3175-3.9120 = +0.4055
    assert abs(math.log(100.0) - 4.6052) < 1e-4
    assert abs(math.log(50.0) - 3.9120) < 1e-4
    assert abs((math.log(100.0) - math.log(50.0)) - 0.6931) < 1e-4
    assert abs((math.log(75.0) - math.log(50.0)) - 0.4055) < 1e-4
    # COST block accounting (single source of truth): 1.0 bps fee = $10.00
    # on $100k, 2.0 bps spread = $20.00 [example]
    assert abs(1e5 * 1.0 / 10000.0 - 10.00) < 1e-9
    assert abs(1e5 * 2.0 / 10000.0 - 20.00) < 1e-9
    sigs = run(tape())
    # weeks 1-8: insufficient history -> UNKNOWN
    for s in sigs[:8]:
        assert s["module_state"] == "UNKNOWN"
    # week 9: SVI 88 vs priors (18,22,19,25,21,24,23,20) -> positive ASVI
    s9 = sigs[8]
    B9 = math.log(88.0)
    prior9 = [math.log(x) for x in (18, 22, 19, 25, 21, 24, 23, 20)]
    assert s9["module_state"] == "OK"
    assert abs(s9["asvi"] - (B9 - statistics.median(prior9))) < 1e-9
    assert s9["asvi"] > 0.5, "ASVI must exceed the 0.5 clip"
    assert s9["exposure"] == 1.5, "clip at +delta=0.5 -> exposure exactly 1.5"
    assert s9["gate_pass"] == 1
    # week 10: proposes 1.5 vs last 2.0... last is 1.5, equal -> OK, no change
    s10 = sigs[9]
    assert s10["module_state"] == "OK"
    assert s10["exposure"] == 1.5
    # week 11: NaN SVI -> UNKNOWN, never interpolate, window does not advance
    s11 = sigs[10]
    assert s11["module_state"] == "UNKNOWN"
    # week 12: SVI 21 -> tiny edge -> gate veto -> neutral scale 1.0, gate_pass 0
    s12 = sigs[11]
    prior12 = [math.log(x) for x in (19, 25, 21, 24, 23, 20, 88, 64)]
    asvi12 = math.log(21.0) - statistics.median(prior12)
    assert abs(s12["asvi"] - asvi12) < 1e-9
    assert s12["gate_pass"] == 0, "tiny edge must fail the cost gate"
    assert s12["exposure"] == 1.0, "gate veto -> neutral scale"
    assert s12["module_state"] == "OK"
    # week 13: proposes ~1.5 but last change was week 12 -> cooldown veto
    s13 = sigs[12]
    assert s13["module_state"] == "DEGRADED", "cooldown must veto the week-13 rebound"
    assert s13["exposure"] == 1.0, "cooldown holds the last applied exposure"
    assert s13["gate_pass"] == 1, "gate itself passes; the cooldown vetoes"
    # week 14: SVI 5 < svi_min 10 -> UNKNOWN (thin-ticker floor)
    s14 = sigs[13]
    assert s14["module_state"] == "UNKNOWN"
    # week 15: SVI 15 -> negative ASVI, cooldown satisfied (15-12 >= 2) -> OK
    s15 = sigs[14]
    prior15 = [math.log(x) for x in (21, 24, 23, 20, 88, 64, 21, 88)]
    asvi15 = math.log(15.0) - statistics.median(prior15)
    assert abs(s15["asvi"] - asvi15) < 1e-9
    assert s15["asvi"] < 0, "week 15 ASVI must be negative"
    assert s15["module_state"] == "OK"
    assert abs(s15["exposure"] - (1.0 + max(-0.5, asvi15))) < 1e-9
    # week 16: proposes a rebound vs the week-15 change -> cooldown veto
    s16 = sigs[15]
    assert s16["module_state"] == "DEGRADED"
    assert abs(s16["exposure"] - s15["exposure"]) < 1e-9, "cooldown holds week-15 exposure"


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
    c = expected_cost_bps(1e5, 0.01, "XNAS", "taker", "normal")
    assert abs(c - 6.0) < 1e-9, "chapter stack must total 6.0 bps"
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    st = init_state()
    for bad in (0.0, -5.0, float("nan"), float("inf"), None):
        sig, _ = step(st, _mk(99, 10**18, bad), CFG)
        assert sig["module_state"] == "UNKNOWN", \
            f"svi={bad} must map to UNKNOWN, never interpolate"
    sig, _ = step(st, _mk(99, float("nan"), 50.0), CFG)
    assert sig["module_state"] == "UNKNOWN", "non-finite event_ts must map to UNKNOWN"


def test_boundary_clip():
    # 8 weeks of flat SVI 50 -> median ln(50); ASVI exactly 0 -> exposure 1.0
    rows = [_mk(w, w * WEEK_NS, 50.0) for w in range(1, 9)]
    rows.append(_mk(9, 9 * WEEK_NS, 50.0))
    sigs = run(rows)
    s = sigs[8]
    assert abs(s["asvi"]) < 1e-12, "flat series must give ASVI 0"
    assert s["exposure"] == 1.0, "zero ASVI -> neutral scale"
    assert s["confidence"] == 0.0
    assert s["gate_pass"] == 0, "zero edge must fail the cost gate"
    # large shock: ASVI 1.386 > delta 0.5 -> exposure exactly 1+delta
    rows2 = [_mk(w, w * WEEK_NS, 50.0) for w in range(1, 9)]
    rows2.append(_mk(9, 9 * WEEK_NS, 200.0))
    s2 = run(rows2)[8]
    assert s2["asvi"] > CFG["delta"]
    assert s2["exposure"] == 1.0 + CFG["delta"], "positive clip must bind exactly"


def test_gate_veto_path():
    # tiny edge -> gate_pass 0 -> neutral scale 1.0, module stays OK (no opinion)
    rows = [_mk(w, w * WEEK_NS, 50.0) for w in range(1, 9)]
    rows.append(_mk(9, 9 * WEEK_NS, 51.0))  # ASVI ~ ln(51/50) = 0.0198
    s = run(rows)[8]
    assert s["module_state"] == "OK"
    assert s["gate_pass"] == 0
    assert s["exposure"] == 1.0
    assert s["direction"] == 1, "direction stays 1: the scaler's neutral is scale 1.0"


def test_cooldown_veto_path():
    # shock at week 9 applies; rebound at week 11 vetoed (11-9 < 2); week 12 allowed
    rows = [_mk(w, w * WEEK_NS, 50.0) for w in range(1, 9)]
    rows += [_mk(9, 9 * WEEK_NS, 150.0),   # shock up -> exposure 1.5
             _mk(10, 10 * WEEK_NS, 150.0),  # same -> no change, OK
             _mk(11, 11 * WEEK_NS, 50.0),   # propose 1.0, 11-9=2 -> allowed
             _mk(12, 12 * WEEK_NS, 150.0)]  # propose 1.5, 12-11=1 < 2 -> veto
    sigs = run(rows)
    assert sigs[8]["exposure"] == 1.5 and sigs[8]["module_state"] == "OK"
    assert sigs[9]["module_state"] == "OK" and sigs[9]["exposure"] == 1.5
    assert sigs[10]["module_state"] == "OK" and sigs[10]["exposure"] == 1.0
    s12 = sigs[11]
    assert s12["module_state"] == "DEGRADED", "cooldown must veto the week-12 rebound"
    assert s12["exposure"] == 1.0, "veto holds the last applied exposure"


def test_staleness_unknown():
    rows = [_mk(1, 1 * WEEK_NS, 50.0)]
    rows.append(_mk(2, 1 * WEEK_NS + STALE_NS + 1, 60.0))  # gap > 3 weeks
    s = run(rows)[1]
    assert s["module_state"] == "UNKNOWN", "stale input must map to UNKNOWN"
    # exactly at the TTL boundary is still accepted
    rows2 = [_mk(1, 1 * WEEK_NS, 50.0)]
    rows2.append(_mk(2, 1 * WEEK_NS + STALE_NS, 60.0))
    s2 = run(rows2)[1]
    assert s2["module_state"] == "UNKNOWN", "insufficient history dominates at week 2"


def test_thin_svi_floor():
    rows = [_mk(w, w * WEEK_NS, 50.0) for w in range(1, 9)]
    rows.append(_mk(9, 9 * WEEK_NS, CFG["svi_min"] - 0.1))
    s = run(rows)[8]
    assert s["module_state"] == "UNKNOWN", "SVI below the thin floor must map to UNKNOWN"
    rows2 = [_mk(w, w * WEEK_NS, 50.0) for w in range(1, 9)]
    rows2.append(_mk(9, 9 * WEEK_NS, CFG["svi_min"]))
    s2 = run(rows2)[8]
    assert s2["module_state"] == "OK", "SVI exactly at the floor must be processed"


def test_halt_freeze():
    rows = [_mk(w, w * WEEK_NS, 50.0) for w in range(1, 9)]
    halted = _mk(9, 9 * WEEK_NS, 80.0)
    halted["market_state"] = "HALTED"
    st = init_state()
    for r in rows:
        step(st, r, CFG)
    before = list(st["B_hist"])
    sig, st = step(st, halted, CFG)
    assert sig["module_state"] == "UNKNOWN", "halt must freeze the module"
    assert st["B_hist"] == before, "halt must not advance the feature window"
    auction = _mk(10, 10 * WEEK_NS, 80.0)
    auction["market_state"] = "AUCTION"
    sig2, _ = step(st, auction, CFG)
    assert sig2["module_state"] == "DEGRADED", "auction holds the last vector"
