"""Acceptance tests for S096 — OI shock / liquidation cluster (cascade fade).

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode (§S3), and asserts causality, the cost gate,
boundary conditions, invalid-input handling, gate vetoes, market-state guards,
staleness, cooldown, and hand-checked arithmetic. All reported_* inputs are
censored lower bounds.

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
H_NS = 3_600_000_000_000  # one hour in int64 ns [fixed]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "shock_flag", "cascade_flag", "flip_flag",
                 "fade_window", "gate_pass", "fill_event_ts"]

# Chapter §S0.2 config. Every value mirrors the chapter exactly.
CFG = {
    "shock_px_pct": 1.0,        # [example] dislocation: dPx <= -1.0%
    "shock_oi_pct": 3.0,        # [example] dislocation: dOI <= -3.0%
    "shock_liq_mult": 5.0,      # [example] shock: liq_long > 5.0 x median baseline
    "liq_baseline_bars": 24,    # [default] trailing window for the liq baseline
    "cascade_confirm_bars": 8,  # [default] flip must follow a cascade within 8 bars
    "fade_h": 4,                # [default] fade window length in bars
    "k": 0.5,                   # [default] cost-gate multiplier
    "staleness_ttl_s": 10800,   # [default] 3h TTL = 3x the 1h reference cadence (F4)
    "cooldown_bars": 24,        # [default] post-exit cooldown in bars (C10)
}


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


def cost_stack():
    # Mirrors the §S2 COST block exactly (single source of truth).
    return {
        "spread_bps": 10.0,  # [example] cascade spread at the example notional
        "fee_bps": 6.0,      # [example] taker fees at the example tier
        "borrow_bps": 0.0,   # [default] borrow_bps_per_day = 0.0: perps have funding, not borrow
        "impact_bps": 5.0,   # [example] post-cascade execution
    }


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    # Callable cost model - post-cascade stack (taker), §S2 COST block.
    s = cost_stack()
    return s["spread_bps"] + s["fee_bps"] + s["borrow_bps"] + s["impact_bps"]


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _sgn(x):
    return 1 if x > 0 else (-1 if x < 0 else 0)


def init_state():
    return {"liq_hist": [], "prev_f": None, "fade_left": 0, "cooldown_left": 0,
            "prev_px": None, "prev_oi": None,
            "prev_shock": 0, "prev_disloc": 0, "bars_since_cascade": 10 ** 9,
            "last_ts": None, "last_vector": None, "post_halt": False}


def _row(ts, price=100.0, oi=1.0, funding=0.0002, liq_long=0.1,
         liq_short=0.0, market_state=None):
    r = {"event_ts": ts, "price": price, "reported_oi_b": oi,
         "reported_funding": funding, "reported_liq_long_m": liq_long,
         "reported_liq_short_m": liq_short}
    if market_state is not None:
        r["market_state"] = market_state
    return r


def _blank(ts):
    fill = ts + 1 if isinstance(ts, int) and not isinstance(ts, bool) else None
    return {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
            "module_state": "UNKNOWN", "edge_bps": 0.0,
            "cost_bps": expected_cost_bps(1e4, 0.01, "BINANCE", "taker", "urgent"),
            "shock_flag": 0, "cascade_flag": 0, "flip_flag": 0, "fade_window": 0,
            "gate_pass": 0, "fill_event_ts": fill}


def step(state, row, cfg):
    """Reference implementation of the §S3 normative pseudocode."""
    ts = row.get("event_ts")
    ms = row.get("market_state") or "CONTINUOUS_TRADING"
    out = _blank(ts)

    # Halt guard (§S0.5): freeze state, emit UNKNOWN, discard contributions
    # across reopen.
    if ms == "HALTED":
        state["post_halt"] = True
        return out, state  # out is already UNKNOWN with zeroed flags
    # Auction guard (§S0.5): no new signals; hold last vector; DEGRADED.
    if ms == "AUCTION":
        if state["last_vector"] is not None:
            out = dict(state["last_vector"])
            out["computed_at"] = ts
            out["fill_event_ts"] = _blank(ts)["fill_event_ts"]
        out["module_state"] = "DEGRADED"
        return out, state
    # Closed guard (§S0.5): emit nothing tradeable; OFF.
    if ms == "CLOSED":
        out["module_state"] = "OFF"
        return out, state
    if ms != "CONTINUOUS_TRADING":
        return out, state  # unmapped market state: fail closed -> UNKNOWN

    # Staleness guard (F4): gap > TTL -> UNKNOWN, mask the gap, never interpolate.
    if isinstance(ts, int) and not isinstance(ts, bool) \
            and state["last_ts"] is not None \
            and (ts - state["last_ts"]) > cfg["staleness_ttl_s"] * 1_000_000_000:
        state["last_ts"] = ts
        return out, state

    px = row.get("price")
    oi = row.get("reported_oi_b")
    f = row.get("reported_funding")
    ll = row.get("reported_liq_long_m")

    # F1: invalid input -> UNKNOWN, never interpolate.
    if not isinstance(ts, int) or isinstance(ts, bool) \
            or not _finite(px) or px <= 0 \
            or not _finite(oi) or oi < 0 \
            or not _finite(f) \
            or not _finite(ll) or ll < 0:
        return out, state

    # Post-halt reopen: discard contributions across the halt (§S0.5).
    if state["post_halt"]:
        state["liq_hist"] = []
        state["prev_px"] = None
        state["prev_oi"] = None
        state["prev_shock"] = 0
        state["prev_disloc"] = 0
        state["post_halt"] = False
    state["last_ts"] = ts

    hist = state["liq_hist"][-cfg["liq_baseline_bars"]:]
    baseline = statistics.median(hist) if hist else 0.05  # [default] cold-start
    state["liq_hist"].append(ll)

    # Shock: forced flow vs the trailing baseline. Strict >: equality at the
    # threshold is NOT a shock.
    shock = 1 if ll > cfg["shock_liq_mult"] * baseline else 0
    dpx = (px - state["prev_px"]) / state["prev_px"] if state["prev_px"] else 0.0
    doi = (oi - state["prev_oi"]) / state["prev_oi"] if state["prev_oi"] else 0.0
    # Dislocation: forced flow must meet a price/OI dislocation (inclusive boundary).
    disloc = 1 if (dpx <= -cfg["shock_px_pct"] / 100.0
                   or doi <= -cfg["shock_oi_pct"] / 100.0) else 0
    state["prev_px"], state["prev_oi"] = px, oi

    # Cascade = forced-flow shock ADJACENT to the dislocation: shock at t AND
    # shock at t-1 AND dislocation at t-1. h50 is the shock bar; h51 the cascade peak.
    cascade = 1 if (shock and state["prev_shock"] and state["prev_disloc"]) else 0
    state["prev_shock"], state["prev_disloc"] = shock, disloc
    state["bars_since_cascade"] = 0 if cascade else state["bars_since_cascade"] + 1

    # Flip: funding sign change with both legs nonzero (a 0.0 print is not a flip).
    flip = 1 if (state["prev_f"] is not None and _sgn(f) != _sgn(state["prev_f"])
                 and f != 0 and state["prev_f"] != 0) else 0
    state["prev_f"] = f

    # Fade: funding flip confirms a *recent* cascade -> fade the exhaustion move.
    # Post-exit cooldown (C10): no re-fade of the same cascade.
    if flip and state["bars_since_cascade"] <= cfg["cascade_confirm_bars"] \
            and state["cooldown_left"] == 0:
        state["fade_left"] = cfg["fade_h"]
    fade = 1 if state["fade_left"] > 0 else 0
    if fade:
        state["fade_left"] -= 1
        if state["fade_left"] == 0:
            state["cooldown_left"] = cfg["cooldown_bars"]
    elif state["cooldown_left"] > 0:
        state["cooldown_left"] -= 1

    # HONESTY: the +1.61% move (99.23 -> 100.83) happens BEFORE the h53 flip
    # confirms; the rule entering at h53 does NOT harvest it, so it is not
    # claimed as edge. edge_bps is an illustrative post-confirmation value [example].
    edge_bps = 80.0 if fade else 0.0  # [example]
    cost_bps = out["cost_bps"]
    # Executable cost-gate predicate; sub-threshold -> direction 0 (C2), never a hint.
    gate = 1 if cost_bps <= cfg["k"] * edge_bps else 0
    direction = 1 if (fade and gate) else 0  # locate n/a: SHORT (-1) is never emitted
    confidence = 0.6 if direction == 1 else 0.0  # [example] confirmed-cascade confidence
    out.update({"module_state": "OK", "direction": direction, "confidence": confidence,
                "capital": 0.5 * confidence, "edge_bps": edge_bps,
                "shock_flag": shock, "cascade_flag": cascade, "flip_flag": flip,
                "fade_window": fade, "gate_pass": gate})
    state["last_vector"] = dict(out)
    return out, state


def run(rows, cfg=CFG):
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


def test_never_emits_short():
    # S096 is a long-only fade; locate is n/a (C7 consumer contract).
    for s in run(tape()):
        assert s["direction"] != -1, "S096 must never emit SHORT"


def test_hand_checks():
    # Chapter S4 ordered flag sequence [documented]: h50 shock (-1.6% price, -6.1% OI),
    # h51 cascade peak (8.5M long liqs, ~61x the trailing median baseline),
    # h52 flow slows, h53 funding flips.
    sigs = run(tape())
    h50, h51, h53 = sigs[5], sigs[6], sigs[8]
    assert h50["shock_flag"] == 1 and h50["cascade_flag"] == 0
    assert h51["cascade_flag"] == 1
    assert h53["flip_flag"] == 1
    assert abs((0.891 - 0.949) / 0.949 - (-0.061)) < 1e-3  # OI drop -6.1%
    assert abs((99.23 - 100.86) / 100.86 - (-0.0162)) < 1e-4  # price drop -1.62%
    # 8.5M long liqs vs the trailing median baseline of the h45-h50 window
    base = statistics.median([0.02, 0.05, 0.01, 0.32, 0.23, 2.80])
    assert abs(base - 0.14) < 1e-12
    assert abs(8.50 / base - 60.714) < 0.01  # ~61x, not ~40x
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


def test_cost_stack_mirrors_chapter():
    # The callable mirrors the §S2 COST block exactly (single source of truth).
    s = cost_stack()
    assert s == {"spread_bps": 10.0, "fee_bps": 6.0,
                 "borrow_bps": 0.0, "impact_bps": 5.0}, \
        "cost stack components must match the chapter's 4-component stack"
    # borrow is explicitly zero with a stated reason: perps have funding, not borrow.
    assert s["borrow_bps"] == 0.0
    c = expected_cost_bps(1e4, 0.01, "BINANCE", "taker", "urgent")
    assert abs(c - 21.0) < 1e-9, "chapter stack must total 21.0 bps"
    # L2 constant stack: venue/side/urgency/notional do not move the total.
    assert expected_cost_bps(1e6, 0.5, "OTHER", "maker", "patient") == c


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5  # [default]
    c = expected_cost_bps(1e4, 0.01, "BINANCE", "taker", "urgent")
    assert abs(c - 21.0) < 1e-9, "chapter stack must total 21.0 bps"
    big_edge = c <= k * 200.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_gate_veto_path():
    # With the gate multiplier at zero the fade is still detected, but the gate
    # vetoes it: C2 emits direction 0, never a tradeable hint.
    veto_cfg = dict(CFG, k=0.0)
    st = init_state()
    outs = []
    for r in tape():
        sig, st = step(st, r, veto_cfg)
        outs.append(sig)
    h53 = outs[8]
    assert h53["fade_window"] == 1, "the fade is still detected"
    assert h53["gate_pass"] == 0
    assert h53["direction"] == 0
    assert h53["confidence"] == 0.0 and h53["capital"] == 0.0
    # with the chapter default the same row passes the gate and fires
    st = init_state()
    outs = []
    for r in tape():
        sig, st = step(st, r, CFG)
        outs.append(sig)
    assert outs[8]["gate_pass"] == 1 and outs[8]["direction"] == 1


def test_shock_boundary_strict_inequality():
    # liq exactly == shock_liq_mult x baseline is NOT a shock (strict >).
    st = init_state()
    base = 1_000_000_000_000
    for i in range(6):
        sig, st = step(st, _row(base + i * H_NS, liq_long=0.1), CFG)
    assert sig["module_state"] == "OK"
    # baseline median = 0.1 -> threshold = 5.0 x 0.1 = 0.5
    sig, st = step(st, _row(base + 6 * H_NS, liq_long=0.5), CFG)
    assert sig["shock_flag"] == 0, "equality at the threshold must not flag a shock"
    sig, st = step(st, _row(base + 7 * H_NS, liq_long=0.5000001), CFG)
    assert sig["shock_flag"] == 1


def test_disloc_boundary_inclusive():
    # dPx exactly -shock_px_pct% IS a dislocation (inclusive <=), observed via
    # cascade formation: shock at t-1 + dislocation at t-1 + shock at t.
    def cascade_at(dpx_price):
        st = init_state()
        base = 2_000_000_000_000
        for i in range(5):
            step(st, _row(base + i * H_NS, price=100.0, liq_long=0.1), CFG)
        # bar 5: shock (2.0 > 5x0.1) with the candidate dislocation
        step(st, _row(base + 5 * H_NS, price=dpx_price, liq_long=2.0), CFG)
        # bar 6: shock again -> cascade iff bar 5 was a dislocation
        sig, _ = step(st, _row(base + 6 * H_NS, price=dpx_price, liq_long=2.0), CFG)
        return sig["cascade_flag"]

    assert cascade_at(99.0) == 1, "exactly -1.0% must count as a dislocation"
    assert cascade_at(99.01) == 0, "-0.99% must not count as a dislocation"


def test_flip_ignores_zero_funding():
    base = 3_000_000_000_000
    st = init_state()
    for i in range(3):
        step(st, _row(base + i * H_NS, funding=0.0002), CFG)
    sig, st = step(st, _row(base + 3 * H_NS, funding=0.0), CFG)
    assert sig["flip_flag"] == 0, "a flip into exactly-zero funding is not a flip"
    sig, st = step(st, _row(base + 4 * H_NS, funding=-0.0002), CFG)
    assert sig["flip_flag"] == 0, "a flip out of exactly-zero funding is not a flip"
    # genuine sign change with both legs nonzero
    st = init_state()
    for i in range(3):
        step(st, _row(base + i * H_NS, funding=0.0002), CFG)
    sig, _ = step(st, _row(base + 3 * H_NS, funding=-0.0002), CFG)
    assert sig["flip_flag"] == 1


def test_invalid_inputs_unknown():
    cases = [
        {"price": float("nan")},
        {"price": 0.0},
        {"price": -5.0},
        {"price": float("inf")},
        {"reported_oi_b": float("nan")},
        {"reported_oi_b": -0.5},
        {"reported_funding": None},
        {"reported_liq_long_m": float("nan")},
        {"reported_liq_long_m": -1.0},
        {"event_ts": None},
        {"event_ts": "not-an-int"},
    ]
    for bad in cases:
        st = init_state()
        r = _row(4_000_000_000_000)
        r.update(bad)
        sig, _ = step(st, r, CFG)
        assert sig["module_state"] == "UNKNOWN", f"{bad} must map to UNKNOWN, never interpolate"
        assert sig["direction"] == 0
        assert sig["shock_flag"] == 0 and sig["cascade_flag"] == 0


def test_staleness_guard():
    # Gap beyond the 3h TTL -> UNKNOWN (F4); the gap is masked, never interpolated.
    st = init_state()
    base = 5_000_000_000_000
    sig, st = step(st, _row(base), CFG)
    assert sig["module_state"] == "OK"
    sig, st = step(st, _row(base + 10801 * 1_000_000_000), CFG)  # 10801s > 10800s TTL
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0
    # exactly at the TTL boundary is still OK
    st = init_state()
    step(st, _row(base), CFG)
    sig, _ = step(st, _row(base + 10800 * 1_000_000_000), CFG)
    assert sig["module_state"] == "OK"


def test_market_state_guards():
    base = 6_000_000_000_000
    st = init_state()
    for i in range(4):
        sig, st = step(st, _row(base + i * H_NS, liq_long=0.1), CFG)
    assert sig["module_state"] == "OK" and sig["direction"] == 0
    # HALTED: freeze, UNKNOWN, no flags computed on the halt bar
    sig, st = step(st, _row(base + 4 * H_NS, liq_long=100.0, market_state="HALTED"), CFG)
    assert sig["module_state"] == "UNKNOWN"
    assert sig["shock_flag"] == 0
    # reopen: the halt bar's flow is discarded, not part of the baseline
    sig, st = step(st, _row(base + 5 * H_NS, liq_long=0.1), CFG)
    assert sig["module_state"] == "OK"
    assert sig["shock_flag"] == 0, "halt-bar flow must not enter the baseline"
    # AUCTION: hold the last vector, DEGRADED
    sig, st = step(st, _row(base + 6 * H_NS, market_state="AUCTION"), CFG)
    assert sig["module_state"] == "DEGRADED"
    assert sig["direction"] == 0  # last emitted direction was 0
    assert sig["fill_event_ts"] > sig["computed_at"]
    # CLOSED: OFF
    sig, st = step(st, _row(base + 7 * H_NS, market_state="CLOSED"), CFG)
    assert sig["module_state"] == "OFF"
    assert sig["direction"] == 0


def test_auction_holds_live_fade():
    # An auction during a live fade holds the fade vector (DEGRADED), not a reset.
    st = init_state()
    for r in tape():
        sig, st = step(st, r, CFG)
    assert sig["direction"] == 1 and sig["fade_window"] == 1  # h56 live fade
    auc, _ = step(st, _row(sig["computed_at"] + H_NS, market_state="AUCTION"), CFG)
    assert auc["module_state"] == "DEGRADED"
    assert auc["direction"] == 1 and auc["fade_window"] == 1, \
        "auction must hold the last vector"
    assert auc["fill_event_ts"] > auc["computed_at"]


def test_post_exit_cooldown_blocks_refade():
    # Cascade at bar 6, flip at bar 7 -> 4-bar fade (bars 7-10). A second flip at
    # bar 11 is inside the 8-bar confirmation window, but the post-exit cooldown
    # (C10) blocks re-fading the same cascade.
    base = 7_000_000_000_000
    st = init_state()
    rows = [_row(base + i * H_NS, liq_long=0.1, funding=0.0002) for i in range(5)]
    rows.append(_row(base + 5 * H_NS, price=98.0, liq_long=2.0, funding=0.0002))
    rows.append(_row(base + 6 * H_NS, price=98.0, liq_long=8.0, funding=0.0002))
    rows.append(_row(base + 7 * H_NS, price=98.5, liq_long=0.1, funding=-0.0002))
    rows += [_row(base + i * H_NS, price=98.5, liq_long=0.1, funding=-0.0002)
             for i in (8, 9, 10)]
    outs = []
    for r in rows:
        sig, st = step(st, r, CFG)
        outs.append(sig)
    assert outs[6]["cascade_flag"] == 1
    assert [o["fade_window"] for o in outs[7:11]] == [1, 1, 1, 1]
    assert outs[10]["direction"] == 1
    sig, _ = step(st, _row(base + 11 * H_NS, price=98.5, liq_long=0.1,
                           funding=0.0002), CFG)
    assert sig["flip_flag"] == 1
    assert sig["fade_window"] == 0 and sig["direction"] == 0, \
        "cooldown must block re-fading the same cascade"
