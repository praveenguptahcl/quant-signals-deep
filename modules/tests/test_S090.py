"""Acceptance tests for S090 — Hurst / variance-ratio regime label (v1.1.0).

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode (S3), and asserts causality, the cost gate
(including the veto path), boundary label semantics, F1/F2/F4 fail-safes,
market-state guards, cooldown spacing, and hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S090.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S090_tape.csv"
EXPECTED = FIX / "S090_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
NS_PER_DAY = 86_400_000_000_000
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "vr2", "h2", "vr4", "h4", "label",
                 "gate_pass", "fill_event_ts"]

# Chapter S3/S4: the fixture harness runs window W=9 [example] so the 31-row tape
# stays hand-checkable. The production minimum window is 60 bars [example]
# (S2 risk limits). Horizons {2,4}, bands [example].
CFG = {"W": 9, "k_fast": 2, "k_slow": 4, "vr_hi": 1.10, "vr_lo": 0.90,
       "cost_gate_k": 0.5, "cooldown": 1, "ttl_days": 3}


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
    # Mirrors the S2 COST block exactly [example]: the label places no trades of
    # its own, so this is the consumer-execution reference stack.
    spread_bps = 1.0    # [example]
    fee_bps = 0.5       # [example]
    borrow_bps = 0.0     # [default] borrow_bps_per_day = 0.0: label only, no short leg
    impact_bps = 0.5    # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def _svar(xs):
    n = len(xs)
    m = sum(xs) / n
    return sum((x - m) ** 2 for x in xs) / (n - 1)


def _vr_h(r, k):
    rk = [sum(r[i:i + k]) for i in range(len(r) - k + 1)]
    vr = _svar(rk) / (k * _svar(r))
    h = 0.5 * (1.0 + math.log(vr) / math.log(k))
    return vr, h


def _sgn(x, eps=1e-12):
    # tolerance-banded sign: |x| <= eps counts as exactly 1.0 [default]
    if x > eps:
        return 1
    if x < -eps:
        return -1
    return 0


def label_of(vr_fast, vr_slow, cfg=CFG):
    """Chapter S3 label precedence: horizon contradiction is surfaced first,
    never averaged away; thresholds are strict inequalities."""
    if _sgn(vr_fast - 1.0) != _sgn(vr_slow - 1.0):
        return "mixed"
    if vr_fast > cfg["vr_hi"]:
        return "persist"
    if vr_fast < cfg["vr_lo"]:
        return "revert"
    return "random_walk"


def confidence_of(label, vr_fast, vr_slow):
    # all mappings [example]
    if label == "persist":
        return min(1.0, 2.0 * (vr_fast - 1.0))
    if label == "revert":
        return min(1.0, 2.0 * (1.0 - vr_fast))
    if label == "mixed":
        return min(1.0, abs(vr_fast - 1.0) + abs(vr_slow - 1.0))
    if label == "random_walk":
        return 1.0 - min(1.0, 2.0 * abs(vr_fast - 1.0))
    return 0.0


def init_state():
    return {"win": [], "max_ts": None, "prev_label": "insufficient", "since_flip": 0}


def _unknown_out(ts, label):
    return {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
            "module_state": "UNKNOWN", "edge_bps": 0.0,
            "cost_bps": expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal"),
            "vr2": float("nan"), "h2": float("nan"), "vr4": float("nan"),
            "h4": float("nan"), "label": label, "gate_pass": 0,
            "fill_event_ts": ts + 1 if isinstance(ts, int) else None}


def step(state, row, cfg, market_state="CONTINUOUS_TRADING", cost_fn=expected_cost_bps):
    ts = row.get("event_ts")
    r = row.get("r")
    # S0.5 market-state guards: halt/auction/closed never compute on bad state
    if market_state == "HALTED":
        return _unknown_out(ts, state["prev_label"]), state  # frozen: win untouched
    if market_state == "AUCTION":
        out = _unknown_out(ts, state["prev_label"])
        out["module_state"] = "DEGRADED"  # hold last vector, no new signal
        return out, state
    if market_state == "CLOSED":
        out = _unknown_out(ts, state["prev_label"])
        out["module_state"] = "OFF"
        return out, state
    # F4 staleness: event older than TTL vs the newest seen -> UNKNOWN, freeze
    # (never backfill); harness clock = max event_ts seen so far [example]
    ttl_ns = cfg["ttl_days"] * NS_PER_DAY
    if (state["max_ts"] is not None and isinstance(ts, int)
            and ts < state["max_ts"] - ttl_ns):
        return _unknown_out(ts, state["prev_label"]), state
    # F1: invalid input -> UNKNOWN, reset window, never interpolate
    if (not isinstance(ts, int) or not isinstance(r, (int, float))
            or not math.isfinite(float(r))):
        state.update({"win": [], "max_ts": None,
                      "prev_label": "insufficient", "since_flip": 0})
        return _unknown_out(ts, "insufficient"), state
    state["win"].append(float(r))
    if len(state["win"]) > cfg["W"]:
        state["win"] = state["win"][-cfg["W"]:]
    state["max_ts"] = ts if state["max_ts"] is None else max(state["max_ts"], ts)
    if len(state["win"]) < cfg["W"]:
        return _unknown_out(ts, "insufficient"), state
    w = state["win"]
    # F2: degenerate window or undefined log -> UNKNOWN, never a label
    if _svar(w) == 0.0:
        return _unknown_out(ts, "insufficient"), state
    vr2, h2 = _vr_h(w, cfg["k_fast"])
    vr4, h4 = _vr_h(w, cfg["k_slow"])
    if not (vr2 > 0.0 and vr4 > 0.0 and math.isfinite(vr2) and math.isfinite(vr4)):
        return _unknown_out(ts, "insufficient"), state
    cand = label_of(vr2, vr4, cfg)
    # cooldown: minimum `cooldown` bars between accepted label flips; the first
    # label after a reset/insufficient stretch is always accepted
    if cand != state["prev_label"]:
        if state["prev_label"] == "insufficient" or state["since_flip"] >= cfg["cooldown"]:
            state["prev_label"] = cand
            state["since_flip"] = 0
        label = state["prev_label"]
    else:
        label = cand
    state["since_flip"] += 1
    # direction: +1 on persist only; this module never emits -1 (C7 locate guard)
    direction = 1 if label == "persist" else 0
    conf = confidence_of(label, vr2, vr4)
    edge_bps = 8.0 if direction == 1 else 0.0  # illustrative regime-timing edge [example]
    cost = cost_fn(1e6, 0.01, "XNAS", "taker", "normal")
    # normative cost gate: gate_pass=0 means a tradeable hint was vetoed (C2)
    gate_ok = (direction == 0) or (cost <= cfg["cost_gate_k"] * edge_bps)
    if not gate_ok:
        direction, conf = 0, 0.0
    capital = 0.25 * conf if direction != 0 else 0.0  # [default] 0.25 factor
    out = {"computed_at": ts, "direction": direction, "confidence": conf,
           "capital": capital, "module_state": "OK", "edge_bps": edge_bps,
           "cost_bps": cost, "vr2": vr2, "h2": h2, "vr4": vr4, "h4": h4,
           "label": label, "gate_pass": 1 if gate_ok else 0,
           "fill_event_ts": ts + 1}
    return out, state


def run(rows, **kw):
    st = init_state()
    out = []
    for r in rows:
        sig, st = step(st, r, CFG, **kw)
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


def _sigs_equal(a, b):
    return all(_close(a[c], b[c]) for c in EXPECTED_COLS)


def test_fixtures_exist_and_typed():
    assert TAPE.exists(), "tape fixture missing"
    assert EXPECTED.exists(), "expected fixture missing"
    with open(TAPE) as f:
        head = [next(f) for _ in range(4)]
    assert any(l.startswith("# TYPE:") for l in head), "tape missing TYPE header"
    with open(EXPECTED) as f:
        head = [next(f) for _ in range(4)]
    assert any(l.startswith("# TYPE:") for l in head), "expected missing TYPE header"
    rows = tape()
    assert len(rows) >= 25, "fixture needs the full 31-row tape"


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
        assert s["direction"] in (+1, 0), "this module emits +1/0 only, never -1 (C7)"
        assert 0.0 <= s["confidence"] <= 1.0, "confidence out of [0,1]"
        assert 0.0 <= s["capital"] <= 0.5, "capital out of [0,0.5]"
        assert s["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")
        assert s["label"] in ("persist", "revert", "mixed", "random_walk", "insufficient")


def test_hand_checks():
    # Chapter S4 hand tape (operator-verified arithmetic) [measured]
    sigs = run(tape())
    # row 9: full window on rows 1-9 -> horizon contradiction -> mixed (not persist)
    m = sigs[8]
    assert m["module_state"] == "OK"
    assert abs(m["vr2"] - 1.5714) < 1e-3
    assert abs(m["h2"] - 0.826) < 1e-3
    assert abs(m["vr4"] - 0.8000) < 1e-3
    assert abs(m["h4"] - 0.4195) < 1e-3
    assert m["label"] == "mixed"
    assert m["direction"] == 0  # contradiction -> no tradeable hint
    assert abs(m["confidence"] - 0.7714) < 1e-3
    # rows 1-8: insufficient window -> UNKNOWN
    for s in sigs[:8]:
        assert s["module_state"] == "UNKNOWN"
        assert s["label"] == "insufficient"
    # row 10: r=nan -> F1 UNKNOWN + window reset
    assert sigs[9]["module_state"] == "UNKNOWN"
    # row 19: full window on rows 11-19 -> clean persist at both horizons
    p = sigs[18]
    assert p["label"] == "persist" and p["direction"] == 1
    assert abs(p["vr2"] - 1.8033) < 1e-3
    assert abs(p["vr4"] - 2.4410) < 1e-3
    assert p["gate_pass"] == 1 and p["edge_bps"] == 8.0
    assert abs(p["capital"] - 0.25) < 1e-9
    # row 20: r=nan -> F1 UNKNOWN + window reset
    assert sigs[19]["module_state"] == "UNKNOWN"
    # row 29: full window on rows 21-29 -> clean revert at both horizons
    v = sigs[28]
    assert v["label"] == "revert" and v["direction"] == 0
    assert abs(v["vr2"] - 0.0882) < 1e-3
    assert abs(v["vr4"] - 0.0713) < 1e-3
    # row 30: stale event_ts (4d before max, TTL 3d) -> F4 UNKNOWN, label frozen
    st = sigs[29]
    assert st["module_state"] == "UNKNOWN"
    assert st["label"] == "revert"
    # row 31: r=inf -> F1 UNKNOWN
    assert sigs[30]["module_state"] == "UNKNOWN"


def test_label_boundaries():
    # thresholds are strict inequalities; contradiction check is tolerance-banded
    assert label_of(1.10, 1.05) == "random_walk"      # vr_hi is strict >
    assert label_of(0.90, 0.95) == "random_walk"      # vr_lo is strict <
    assert label_of(1.1000001, 1.05) == "persist"
    assert label_of(0.8999999, 0.95) == "revert"
    assert label_of(1.0, 1.0) == "random_walk"
    assert label_of(1.2, 0.8) == "mixed"
    assert label_of(0.8, 1.2) == "mixed"
    assert label_of(1.0 + 1e-13, 1.0 - 1e-13) == "random_walk"  # inside sgn eps


def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()):
        fill_event = s["fill_event_ts"]
        signal_event = s["computed_at"]
        if fill_event is not None and signal_event is not None:
            assert fill_event > signal_event


def test_no_lookahead():
    # a signal at bar i must not depend on bars after i: prefixes are invariant
    rows = tape()
    full = run(rows)
    for n in (9, 19, 29):
        prefix = run(rows[:n])
        for i, (a, b) in enumerate(zip(prefix, full[:n])):
            assert _sigs_equal(a, b), f"row {i}: output changed when later bars exist"


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5  # [default]
    c = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")
    assert c == 2.0, "callable must mirror the S2 COST block exactly (1.0+0.5+0.0+0.5)"
    assert c <= k * 100.0, "cost gate should pass on a large edge"
    assert not (c <= k * 0.01), "cost gate should block on a tiny edge"


def test_gate_veto_path():
    # C2: a tradeable hint that fails the cost gate is vetoed to direction 0,
    # confidence 0, gate_pass 0 -- the label itself is retained.
    rows = tape()
    st = init_state()
    for r in rows[:18]:
        step(st, r, CFG)
    vetoed, _ = step(st, rows[18], CFG, cost_fn=lambda *a: 100.0)
    assert vetoed["label"] == "persist"
    assert vetoed["gate_pass"] == 0
    assert vetoed["direction"] == 0
    assert vetoed["confidence"] == 0.0
    assert vetoed["capital"] == 0.0
    assert vetoed["module_state"] == "OK"  # label computed; only the hint vetoed
    # control: the same row passes the gate under the reference cost stack
    st2 = init_state()
    for r in rows[:18]:
        step(st2, r, CFG)
    clean, _ = step(st2, rows[18], CFG)
    assert clean["gate_pass"] == 1 and clean["direction"] == 1


def test_invalid_input_unknown():
    rows = tape()
    st = init_state()
    sig, _ = step(st, dict(rows[9]), CFG)  # row 10: r = nan
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
    st = init_state()
    sig, _ = step(st, dict(rows[30]), CFG)  # row 31: r = inf
    assert sig["module_state"] == "UNKNOWN"
    # F1 resets the window: a fresh window must refill before any label
    st = init_state()
    for r in rows[:9]:
        step(st, r, CFG)
    assert len(st["win"]) == 9
    step(st, dict(rows[9]), CFG)
    assert st["win"] == [], "F1 must reset the window, never interpolate across the gap"


def test_stale_event_freezes_window():
    # F4: an event older than TTL vs the newest seen -> UNKNOWN; the window is
    # frozen (not appended, not reset).
    rows = tape()
    st = init_state()
    for r in rows[:29]:
        step(st, r, CFG)
    before = list(st["win"])
    assert len(before) == 9
    sig, st2 = step(st, rows[29], CFG)  # row 30: ts 4d before max, TTL 3d
    assert sig["module_state"] == "UNKNOWN"
    assert st2["win"] == before, "stale event must not enter the window"
    assert st2["max_ts"] == st["max_ts"], "stale event must not move the clock"


def test_zero_variance_unknown():
    # F2: a degenerate constant window has undefined VR -> UNKNOWN, never a label
    st = init_state()
    base = 1788946200000000000
    last = None
    for i in range(9):
        last, st = step(st, {"ev": i + 1, "event_ts": base + i * 600_000_000_000,
                             "r": 0.0}, CFG)
    assert last["module_state"] == "UNKNOWN"
    assert last["label"] == "insufficient"


def test_market_state_guards():
    rows = tape()
    st = init_state()
    for r in rows[:9]:
        step(st, r, CFG)
    assert len(st["win"]) == 9
    sig, st = step(st, rows[9], CFG, market_state="HALTED")
    assert sig["module_state"] == "UNKNOWN"
    assert len(st["win"]) == 9, "HALTED must freeze the window"
    sig, st = step(st, rows[9], CFG, market_state="AUCTION")
    assert sig["module_state"] == "DEGRADED"
    assert len(st["win"]) == 9, "AUCTION must not consume the event"
    sig, _ = step(st, rows[9], CFG, market_state="CLOSED")
    assert sig["module_state"] == "OFF"


def test_cooldown_min_spacing():
    # mechanism pin: accepted label flips are spaced >= cooldown bars apart
    cfg = dict(CFG)
    cfg["cooldown"] = 3
    trend = [1.0, 0.9, 1.1, 0.8, 1.2]
    rev = [1.0, -0.9, 1.1, -1.0, 0.9]
    stream = (trend + rev) * 8  # 80 bars, deterministic, no RNG
    base = 1788946200000000000
    rows = [{"ev": i + 1, "event_ts": base + i * 600_000_000_000, "r": v}
            for i, v in enumerate(stream)]
    st = init_state()
    outs = [step(st, r, cfg)[0] for r in rows]
    labels = [o["label"] for o in outs if o["module_state"] == "OK"]
    flips = [i for i in range(1, len(labels)) if labels[i] != labels[i - 1]]
    assert len(flips) >= 1, "stream must actually flip or the test is vacuous"
    gaps = [b - a for a, b in zip(flips, flips[1:])]
    assert all(g >= 3 for g in gaps), f"cooldown violated: gaps {gaps}"
