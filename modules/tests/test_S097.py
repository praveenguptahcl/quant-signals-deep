"""Acceptance tests for S097 — Social / media sentiment, v1.1.0.

Reference implementation of the chapter's normative pseudocode (§S3): volume z
over exactly five prior days (sample SD), composite z * weighted sentiment,
HHI manipulation veto, desk gate, post-fire cooldown (C10), staleness TTL (F4),
halt/auction/closed market-state gates (C6), locate check for SHORT (C7), and
the executable cost gate (fail -> direction 0).

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
NS_PER_DAY = 86_400_000_000_000  # int64 ns per day [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "z_vol", "S", "veto", "gate_pass", "fill_event_ts"]

# Chapter S2/S3 parameters (v1.1.0): z_entry/sent_min/hhi_max are [example]/[documented]
# desk-gate values with status=calibrate; W=5 [documented] fixed; k=0.5 [default].
CFG = {"z_entry": 3.0, "sent_min": 0.10, "hhi_max": 0.25, "W": 5, "k": 0.5,
       "cooldown_days": 5, "ttl_days": 3}
EDGE_MAP = 20.0  # illustrative composite -> edge_bps mapping [example]
BORROW_SHORT_BPS_PER_DAY = 0.0  # [default] uncalibrated; must be set per-name before any short deployment


def cost_components(notional, adv_pct, venue, side, urgency):
    """Four-component decomposition mirroring the §S2 COST block exactly."""
    spread_bps = 10.0    # [documented] $50 on $50k at 2c half-spread
    fee_bps = 1.75       # [documented] $8.75 on $50k (IBKR tiered $0.0035/share x 2 legs, 1250 shares)
    borrow_bps = 0.0 if side == "long" else BORROW_SHORT_BPS_PER_DAY  # [default] reason in block
    impact_bps = 3.0     # [documented] 3 bps at the example notional
    return {"spread_bps": spread_bps, "fee_bps": fee_bps,
            "borrow_bps": borrow_bps, "impact_bps": impact_bps}


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    # Callable cost model - mirrors the COST block exactly for the reference
    # (long, XNAS, mixed, normal) trade. The short side adds the borrow term.
    return sum(cost_components(notional, adv_pct, venue, side, urgency).values())


def _bad(x):
    return x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))


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


def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def tape():
    rows = []
    for r in load_csv(TAPE):
        d = {}
        for k, v in r.items():
            d[k] = _num(v)
        rows.append(d)
    return rows


def desk_gate_ok(z, w_sent, hhi, cfg):
    """Strict-inequality desk gate (§S3 normative)."""
    return (abs(z) > cfg["z_entry"]) and (abs(w_sent) > cfg["sent_min"]) and (hhi < cfg["hhi_max"])


def veto_flag(hhi, cfg):
    return 1 if hhi > cfg["hhi_max"] else 0


def init_state():
    return {"vol_hist": [],  # exactly the five PRIOR daily buckets (never t)
            "last_fire_ts": None,   # C10 cooldown anchor
            "last_event_ts": None,  # F4 staleness anchor
            "last_sig": None,       # AUCTION hold
            "module_state": "OK"}


def _base_out(ts, cost_bps):
    return {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
            "module_state": "UNKNOWN", "edge_bps": 0.0, "cost_bps": cost_bps,
            "z_vol": float("nan"), "S": float("nan"), "veto": 0, "gate_pass": 0,
            "fill_event_ts": ts + 1 if isinstance(ts, int) else None}


def step(state, row, cfg, locate_ok=True):
    """One normative §S3 step. Returns (SignalVector-dict, state); None on CLOSED (emit nothing)."""
    ts = row.get("event_ts")
    vol = row.get("posts")
    sent = row.get("w_sent")
    hhi = row.get("hhi")  # tape stores HHI as a 0-1 fraction
    mstate = row.get("market_state", "CONTINUOUS_TRADING")
    cost_bps = expected_cost_bps(1e4, 0.01, "XNAS", "long", "normal")
    out = _base_out(ts, cost_bps)
    # F1: invalid input -> UNKNOWN, never interpolate (state untouched)
    if any(_bad(v) for v in (ts, vol, sent, hhi)) or vol < 0 \
            or not (-1.0 <= sent <= 1.0) or not (0.0 <= hhi <= 1.0):
        return out, state
    # C6 / §S0.5 market-state gates
    if mstate == "HALTED":
        state["module_state"] = "UNKNOWN"
        out["module_state"] = "UNKNOWN"
        return out, state
    if mstate == "AUCTION":
        state["module_state"] = "DEGRADED"
        held = dict(state["last_sig"]) if state["last_sig"] else out
        held = dict(held)
        held["module_state"] = "DEGRADED"
        held["computed_at"] = ts
        return held, state
    if mstate == "CLOSED":
        state["module_state"] = "OFF"
        return None, state  # emit nothing
    # F4 staleness TTL: gap > 3 x reference cadence -> UNKNOWN
    last_ts = state.get("last_event_ts")
    if last_ts is not None and (ts - last_ts) > cfg["ttl_days"] * NS_PER_DAY:
        return out, state  # UNKNOWN; anchors not advanced
    # History gate: need exactly W priors (§S3: z uses the five PRIOR days, excluding t)
    if len(state["vol_hist"]) < cfg["W"]:
        state["vol_hist"].append(vol)
        state["last_event_ts"] = ts
        return out, state  # insufficient history -> UNKNOWN
    mu = statistics.mean(state["vol_hist"])
    sd = statistics.stdev(state["vol_hist"])  # sample sd, denominator W-1
    if sd <= 0 or not math.isfinite(sd) or not math.isfinite(mu):
        return out, state  # F2: feature out of mathematical bounds
    z = (vol - mu) / sd
    if not math.isfinite(z):
        return out, state  # F2
    state["vol_hist"] = (state["vol_hist"] + [vol])[-cfg["W"]:]
    state["last_event_ts"] = ts
    # §S3: HHI > hhi_max flags campaign-dominated buckets; the veto is the product
    veto = veto_flag(hhi, cfg)
    S = z * sent  # composite: volume z times weighted signed sentiment
    gate = desk_gate_ok(z, sent, hhi, cfg)
    # C10 post-fire cooldown
    last_fire = state.get("last_fire_ts")
    cooldown = last_fire is not None and (ts - last_fire) < cfg["cooldown_days"] * NS_PER_DAY
    edge_bps = abs(S) * EDGE_MAP if gate else 0.0  # illustrative [example]
    cost_ok = cost_bps <= cfg["k"] * edge_bps      # executable predicate; fail -> direction 0
    direction = 0
    if gate and veto == 0 and not cooldown and cost_ok:
        direction = 1 if S > 0 else (-1 if S < 0 else 0)
        if direction == -1 and not locate_ok:
            direction = 0  # C7: no locate -> no SHORT
    if direction != 0:
        state["last_fire_ts"] = ts  # C10 re-arm anchor
    confidence = min(1.0, abs(z) / 10.0) if direction != 0 else 0.0  # [example]
    out.update({"module_state": "OK", "direction": direction, "confidence": confidence,
                "capital": 0.5 * confidence, "edge_bps": edge_bps, "cost_bps": cost_bps,
                "z_vol": z, "S": S, "veto": veto, "gate_pass": 1 if direction != 0 else 0,
                "fill_event_ts": ts + 1})
    assert out["fill_event_ts"] > out["computed_at"]  # causality pin
    state["last_sig"] = dict(out)
    state["module_state"] = "OK"
    return out, state


def run(rows, locate_ok=True):
    st = init_state()
    out = []
    for r in rows:
        sig, st = step(st, r, CFG, locate_ok=locate_ok)
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


def _row(day, ts, posts, w_sent, hhi, mstate="CONTINUOUS_TRADING"):
    return {"day": day, "event_ts": ts, "posts": posts, "raw_sent": w_sent,
            "w_sent": w_sent, "hhi": hhi, "market_state": mstate}


def _synth_tape(day6_posts=500.0, day6_sent=0.5, extra_days=()):
    base_ts = 1_700_000_000_000_000_000
    base_posts = [100.0, 110.0, 90.0, 105.0, 95.0]
    rows = [_row(i + 1, base_ts + i * NS_PER_DAY, p, 0.05, 0.05)
            for i, p in enumerate(base_posts)]
    rows.append(_row(6, base_ts + 5 * NS_PER_DAY, day6_posts, day6_sent, 0.05))
    for j, spec in enumerate(extra_days):
        rows.append(_row(7 + j, base_ts + (6 + j) * NS_PER_DAY, *spec))
    return rows


def test_fixtures_exist_and_typed():
    assert TAPE.exists(), "tape fixture missing"
    assert EXPECTED.exists(), "expected fixture missing"
    for path in (TAPE, EXPECTED):
        with open(path) as f:
            head = [next(f) for _ in range(3)]
        assert any(l.startswith("# TYPE:") for l in head), f"{path.name} missing TYPE header"
    rows = tape()
    assert len(rows) >= 5, "fixture needs >=5 hand-checkable rows"
    assert "market_state" in rows[0], "tape must carry the market_state column (§S0.5 gates)"


def test_expected_matches_reference():
    rows = tape()
    sigs = run(rows)
    exp = load_csv(EXPECTED)
    assert len(exp) == len(sigs), "expected row count != tape row count"
    for i, (s, e) in enumerate(zip(sigs, exp)):
        assert s is not None, f"row {i}: CLOSED must not appear in the fixture tape"
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
        assert s["computed_at"] is not None and s["fill_event_ts"] == s["computed_at"] + 1


def test_hand_checks():
    # Chapter S4 hand-check [documented]: day-6 z uses the FIVE PRIOR days
    # [123, 143, 117, 138, 132]; mean = 130.60; sd = 10.6442; z = +26.25.
    # Desk gate (v1.1.0): |z| > 3.0 [example], |w_sent| = 0.120 > 0.10 [example],
    # hhi = 0.090 < 0.25 [documented] -> fires.
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
    assert d7["gate_pass"] == 0
    # day 10: no volume trigger (|z| ~ 1.05 < 3.0) -> flat, composite still defined
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
        assert fill_event is not None and signal_event is not None
        assert fill_event > signal_event


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5  # [default]
    c = expected_cost_bps(1e4, 0.01, "XNAS", "long", "normal")
    assert abs(c - 14.75) < 1e-9, "chapter stack must total 14.75 bps"
    assert c <= k * 100.0, "cost gate should pass on a large edge"
    assert not (c <= k * 0.01), "cost gate should block on a tiny edge"


def test_cost_callable_mirrors_block():
    # The callable must mirror the §S2 COST block exactly (decomposition test).
    comp = cost_components(1e4, 0.01, "XNAS", "long", "normal")
    assert comp == {"spread_bps": 10.0, "fee_bps": 1.75,
                    "borrow_bps": 0.0, "impact_bps": 3.0}, \
        f"callable decomposition diverged from the COST block: {comp}"
    assert abs(sum(comp.values()) - 14.75) < 1e-12
    assert abs(expected_cost_bps(1e4, 0.01, "XNAS", "long", "normal") - 14.75) < 1e-12
    # short side adds the borrow term (0.0 [default] until calibrated per-name)
    comp_s = cost_components(1e4, 0.01, "XNAS", "short", "normal")
    assert comp_s["borrow_bps"] == BORROW_SHORT_BPS_PER_DAY


def test_strict_inequality_boundaries():
    # Every threshold in the desk gate is strict: exactly-at-threshold never fires.
    assert desk_gate_ok(3.0, 0.5, 0.10, CFG) is False      # |z| == z_entry
    assert desk_gate_ok(3.0000001, 0.5, 0.10, CFG) is True
    assert desk_gate_ok(-3.0000001, -0.5, 0.10, CFG) is True  # negative side symmetric
    assert desk_gate_ok(5.0, 0.10, 0.10, CFG) is False     # |w_sent| == sent_min
    assert desk_gate_ok(5.0, 0.1000001, 0.10, CFG) is True
    assert desk_gate_ok(5.0, 0.5, 0.25, CFG) is False      # hhi == hhi_max fails hhi < hhi_max
    assert desk_gate_ok(5.0, 0.5, 0.2499999, CFG) is True
    assert veto_flag(0.25, CFG) == 0
    assert veto_flag(0.2500001, CFG) == 1


def test_invalid_input_unknown():
    st = init_state()
    bad_rows = [
        {"event_ts": 1, "posts": -1.0, "w_sent": 0.5, "hhi": 0.02},          # negative volume
        {"event_ts": 2, "posts": 100.0, "w_sent": 1.5, "hhi": 0.02},         # sentiment out of [-1,1]
        {"event_ts": 3, "posts": 100.0, "w_sent": 0.5, "hhi": 1.5},          # HHI out of [0,1]
        {"event_ts": 4, "posts": float("nan"), "w_sent": 0.5, "hhi": 0.02},  # NaN
        {"event_ts": 5, "posts": 100.0, "w_sent": float("inf"), "hhi": 0.02},# non-finite
        {"event_ts": 6, "posts": 100.0, "hhi": 0.02},                       # missing field
    ]
    for bad in bad_rows:
        sig, st = step(st, bad, CFG)
        assert sig["module_state"] == "UNKNOWN", f"invalid input must map to UNKNOWN: {bad}"
        assert sig["direction"] == 0
    # invalid rows must not pollute state: the next valid row still computes
    assert len(st["vol_hist"]) == 0, "invalid input must never be interpolated into history"


def test_halt_auction_closed_staleness_paths():
    rows = _synth_tape()  # days 1-6; day 6 fires
    st = init_state()
    for r in rows:
        sig, st = step(st, r, CFG)
    assert sig["direction"] == 1 and st["last_fire_ts"] == rows[5]["event_ts"]
    base = rows[5]["event_ts"]
    # HALTED -> freeze, UNKNOWN
    sig_h, _ = step(init_state(), _row(7, base + NS_PER_DAY, 800.0, 0.5, 0.05, "HALTED"), CFG)
    assert sig_h["module_state"] == "UNKNOWN" and sig_h["direction"] == 0
    # AUCTION -> hold last vector, DEGRADED (needs history first)
    st2 = init_state()
    for r in rows:
        sig, st2 = step(st2, r, CFG)
    sig_a, st2 = step(st2, _row(7, base + NS_PER_DAY, 800.0, 0.5, 0.05, "AUCTION"), CFG)
    assert sig_a["module_state"] == "DEGRADED"
    assert sig_a["direction"] == 1, "auction must hold the last SignalVector"
    # CLOSED -> emit nothing, state OFF
    sig_c, st3 = step(init_state(), _row(7, base + NS_PER_DAY, 800.0, 0.5, 0.05, "CLOSED"), CFG)
    assert sig_c is None and st3["module_state"] == "OFF"
    # Staleness: gap > 3d TTL -> UNKNOWN (anchors not advanced)
    st4 = init_state()
    for r in rows:
        _, st4 = step(st4, r, CFG)
    stale = _row(7, base + 4 * NS_PER_DAY, 120.0, 0.05, 0.05)
    sig_s, st4 = step(st4, stale, CFG)
    assert sig_s["module_state"] == "UNKNOWN"
    assert st4["last_event_ts"] == base, "stale bucket must not advance the anchor"


def test_gate_veto_and_cost_veto_paths():
    # HHI veto path: desk gate would pass on z/sent, but hhi > hhi_max vetoes.
    rows = _synth_tape(day6_posts=500.0, day6_sent=0.5,
                       extra_days=[(980.0, 0.45, 0.3168)])  # day-7-style campaign bucket
    sigs = run(rows)
    d7 = sigs[6]
    assert d7["veto"] == 1 and d7["direction"] == 0 and d7["gate_pass"] == 0
    assert d7["module_state"] == "OK"
    # Cost-gate veto path: desk gate passes but cost > k * edge -> direction 0.
    # z ~= 3.1, w_sent = 0.11 -> edge = |3.1 * 0.11| * 20 = 6.82 bps; 0.5*6.82 < 14.75.
    sd5 = statistics.stdev([100.0, 110.0, 90.0, 105.0, 95.0])
    rows2 = _synth_tape(day6_posts=100.0 + 3.1 * sd5, day6_sent=0.11)
    sigs2 = run(rows2)
    d6 = sigs2[5]
    assert d6["module_state"] == "OK" and d6["veto"] == 0
    assert d6["direction"] == 0 and d6["gate_pass"] == 0, "cost-gate fail must veto direction"
    assert d6["edge_bps"] > 0, "edge is still logged when the cost gate vetoes"
    # Same setup with a larger edge passes the cost gate.
    rows3 = _synth_tape(day6_posts=100.0 + 3.1 * sd5, day6_sent=0.5)
    d6b = run(rows3)[5]
    assert d6b["direction"] == 1 and d6b["gate_pass"] == 1


def test_cooldown_suppresses_and_expires():
    # Day 6 fires (z=50.6). Day 7 is a desk-gate-passing candidate (z~3.46) but
    # falls inside the 5-day C10 cooldown -> suppressed, cooldown anchor unchanged.
    rows = _synth_tape(extra_days=[(800.0, 0.5, 0.05)])
    st = init_state()
    sigs = []
    for r in rows:
        sig, st = step(st, r, CFG)
        sigs.append(sig)
    d6, d7 = sigs[5], sigs[6]
    assert d6["direction"] == 1, "day 6 must fire"
    assert d7["module_state"] == "OK"
    assert d7["direction"] == 0 and d7["gate_pass"] == 0, "cooldown must suppress the re-fire"
    assert st["last_fire_ts"] == rows[5]["event_ts"], "suppressed fire must not re-arm the anchor"
    # Expiry: with the anchor 6 days back, the same candidate fires.
    st2 = init_state()
    for r in rows[:6]:
        _, st2 = step(st2, r, CFG)
    st2["last_fire_ts"] = rows[0]["event_ts"]  # 6 days before day 7
    sig7, _ = step(st2, rows[6], CFG)
    assert sig7["direction"] == 1, "cooldown expiry must allow the re-fire"


def test_locate_check_for_short():
    # Bearish catalyst: desk gate passes with S < 0 -> SHORT only with locate_ok.
    rows = _synth_tape(day6_posts=500.0, day6_sent=-0.5)
    d6_nolocate = run(rows, locate_ok=False)[5]
    assert d6_nolocate["direction"] == 0, "SHORT without locate must be suppressed (C7)"
    assert d6_nolocate["module_state"] == "OK" and d6_nolocate["gate_pass"] == 0
    d6_locate = run(rows, locate_ok=True)[5]
    assert d6_locate["direction"] == -1, "SHORT with locate asserted must emit -1"
    assert d6_locate["gate_pass"] == 1
    assert 0.0 < d6_locate["confidence"] <= 1.0
