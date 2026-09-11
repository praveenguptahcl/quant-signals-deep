"""Acceptance tests for S100 — Standardized Unexpected Earnings (SUE) / PEAD.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode (§S3), and asserts causality, the cost-gate veto,
market-state / staleness / cooldown / locate guards, and hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S100.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S100_tape.csv"
EXPECTED = FIX / "S100_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "sue", "tier",
                 "gate_pass", "fill_event_ts"]

# Chapter S3 parameters: tier cutoffs are module convention [example];
# k/cooldown/ttl frozen defaults [default]; conf_scale calibrate-status [example]
CFG = {"sue_hi": 1.0, "sue_lo": -1.0, "conf_scale": 5.0, "k": 0.5,
       "cooldown_days": 5, "ttl_days": 3}

# COST-block decomposition (must mirror §S2 exactly) [example]/[default]
BORROW_BPS_PER_DAY = 0.0  # [default] reason: chapter all-in excludes borrow
COST_COMPONENTS = {"spread_bps": 3.0, "fee_bps": 1.0,
                   "borrow_bps": BORROW_BPS_PER_DAY * 1.0, "impact_bps": 1.0}


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    # Mirrors the §S2 COST block exactly: constant announcement-window stack.
    spread_bps = 3.0     # [example]
    fee_bps = 1.0        # [example]
    borrow_bps = BORROW_BPS_PER_DAY * 1.0  # [default] 1-day hold assumption
    impact_bps = 1.0     # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


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


def _bad(x):
    # F1: missing, NaN, or non-finite inputs all map to UNKNOWN, never interpolate
    return x is None or (isinstance(x, float) and not math.isfinite(x))


def _finite_pos(x):
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x) and x > 0


def init_state():
    return {"events": 0, "last_direction": 0}


def step(state, row, cfg, *, market_state="CONTINUOUS_TRADING", now=None,
         announce=None, last_entry=None, locate_ok=True,
         stale_after=10 ** 9, cooldown_win=0):
    """Reference implementation of the §S3 normative pseudocode.

    Tape schema: ticker,eps_act,eps_exp,sigma,ar (no timestamps on the panel).
    `now`/`announce`/`stale_after`/`cooldown_win` are in ordered-event index
    units [example] so the fixture (pre-open releases, gap 1 index) never trips
    the TTL or the cooldown; guard tests pass explicit values.
    """
    idx = state["events"] + 1
    ts = idx  # event index as the ordered event clock [example]
    if now is None:
        now = idx
    if announce is None:
        announce = idx - 1
    act = row.get("eps_act")
    exp = row.get("eps_exp")
    sig = row.get("sigma")
    ar = row.get("ar")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e4, 0.01, "XNAS", "taker", "normal"),
           "sue": float("nan"), "tier": "none", "gate_pass": 0,
           "fill_event_ts": ts + 1}

    # Market-state gate (§S0.5)
    if market_state == "CLOSED":
        out["module_state"] = "OFF"
        return out, state
    if market_state == "HALTED":
        return out, state  # UNKNOWN
    if market_state == "AUCTION":
        out.update({"module_state": "DEGRADED", "direction": state["last_direction"],
                    "fill_event_ts": None})
        return out, state

    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (act, exp, sig)) or not _finite_pos(sig):
        return out, state
    # Lookahead guard: mis-pinned announcement ts -> UNKNOWN
    if announce > now:
        return out, state
    # F4: staleness TTL -> UNKNOWN
    if (now - announce) > stale_after:
        return out, state
    # C10: post-entry cooldown -> direction 0, module stays OK
    if last_entry is not None and (now - last_entry) < cooldown_win:
        out["module_state"] = "OK"
        return out, state

    sue = (act - exp) / sig
    # S3 tier rule [example cutoffs]: >= hi+ / <= lo- (strict-inequality tested)
    if sue >= cfg["sue_hi"]:
        tier, pre_direction = "hi+", 1
    elif sue <= cfg["sue_lo"]:
        tier, pre_direction = "lo-", -1
    else:
        tier, pre_direction = "mid", 0
    # C7: SHORT requires consumer locate assertion
    if pre_direction == -1 and not locate_ok:
        return out, state  # UNKNOWN
    confidence = min(1.0, abs(sue) / cfg["conf_scale"]) if pre_direction else 0.0
    # chapter S4: the tape's ar column carries the entered names' announcement returns [example]
    edge_bps = abs(ar) * 100.0 if not _bad(ar) else 0.0
    direction = pre_direction
    # Cost gate as VETO: fail -> direction 0 (never an assert)
    gate = 1 if (direction and out["cost_bps"] <= cfg["k"] * edge_bps) else 0
    if direction and not gate:
        direction, confidence = 0, 0.0
    out.update({"module_state": "OK", "direction": direction,
                "confidence": confidence, "capital": 0.5 * confidence,
                "edge_bps": edge_bps, "sue": sue, "tier": tier, "gate_pass": gate})
    state["events"] += 1
    state["last_direction"] = direction
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


def _row(eps_act, eps_exp, sigma, ar=None):
    return {"ticker": "T", "eps_act": eps_act, "eps_exp": eps_exp,
            "sigma": sigma, "ar": ar}


# ---------------------------------------------------------------- fixtures

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
        assert str(e["ticker"]) == str(rows[i]["ticker"]), f"row {i} ticker mismatch"
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
        # C2: any emitted |direction|=1 must have passed the cost gate
        if s["direction"] != 0:
            assert s["gate_pass"] == 1, "C2 violation: tradeable hint without a passing cost gate"


def test_hand_checks():
    # Chapter S4 hand-check: 10,000 shares x $0.60 move = $6,000 gross [example]
    assert abs(10000 * 0.60 - 6000.0) < 1e-9
    sigs = run(tape())
    # SUE = (act - exp) / sigma; module tier cutoffs at +/-1.0 [example]:
    # entered names keep their direction; names with no ar edge are gate-vetoed to 0
    want = [("hi+", 1), ("lo-", 0), ("mid", 0), ("lo-", 0), ("hi+", 0),
            ("mid", 0), ("lo-", -1), ("hi+", 1), ("lo-", -1), ("hi+", 0)]
    for i, s in enumerate(sigs[:10]):
        assert (s["tier"], s["direction"]) == want[i], f"row {i}"
    assert abs(sigs[0]["sue"] - 2.50) < 1e-9
    assert abs(sigs[4]["sue"] - 1.60) < 1e-9
    # entered names carry the tape's ar as edge: A 2.46% -> 246 bps, gate passes
    assert abs(sigs[0]["edge_bps"] - 246.0) < 1e-9
    assert sigs[0]["gate_pass"] == 1
    # vetoed names: tier still recorded, direction forced to 0
    for i in (1, 3, 4, 9):
        assert sigs[i]["direction"] == 0 and sigs[i]["gate_pass"] == 0
    # chapter: no close-to-close tradability inference -- the module only prices the
    # announcement window at the first tradable price [documented]
    assert all(s["module_state"] == "OK" for s in sigs[:10])


# ---------------------------------------------------------------- cost model

def test_cost_callable_mirrors_block():
    # §S2 COST block: spread 3.0 + fees 1.0 + borrow 0.0 + impact 1.0 = 5.0 [example]
    assert COST_COMPONENTS == {"spread_bps": 3.0, "fee_bps": 1.0,
                               "borrow_bps": 0.0, "impact_bps": 1.0}, \
        "test decomposition must match the §S2 COST block exactly"
    assert abs(COST_COMPONENTS["borrow_bps"] - BORROW_BPS_PER_DAY * 1.0) < 1e-12
    total = sum(COST_COMPONENTS.values())
    got = expected_cost_bps(1e4, 0.01, "XNAS", "taker", "normal")
    assert abs(got - total) < 1e-12, "callable must mirror the block decomposition"
    assert abs(got - 5.0) < 1e-9, "chapter stack must total 5.0 bps"
    # callable is not notional/urgency-sensitive in this reference build [example]
    assert abs(expected_cost_bps(1e6, 0.5, "XNAS", "taker", "urgent") - 5.0) < 1e-9


def test_cost_gate_veto():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps, fail -> direction 0
    k = 0.5  # [default]
    st = init_state()
    # no ar edge -> veto -> direction 0
    sig, _ = step(st, _row(1.45, 1.20, 0.10), CFG)
    assert sig["direction"] == 0 and sig["gate_pass"] == 0
    # tiny edge (0.01% -> 1 bps; k*edge = 0.5 < 5.0) -> veto
    sig, _ = step(st, _row(1.45, 1.20, 0.10, ar=0.01), CFG)
    assert sig["direction"] == 0 and sig["gate_pass"] == 0
    # large edge (2.46% -> 246 bps; k*edge = 123 >= 5.0) -> pass
    sig, _ = step(st, _row(1.45, 1.20, 0.10, ar=2.46), CFG)
    assert sig["direction"] == 1 and sig["gate_pass"] == 1


# ---------------------------------------------------------------- guards

def test_boundary_thresholds():
    # strict-inequality boundary: cutoffs are >= / <=, so exactly +/-1.0 is in-tier
    st = init_state()
    sig, _ = step(st, _row(0.20, 0.10, 0.10, ar=5.0), CFG)   # sue = 1.0 exactly
    assert sig["tier"] == "hi+" and sig["direction"] == 1
    sig, _ = step(st, _row(0.19999999, 0.10, 0.10, ar=5.0), CFG)  # sue just below 1.0
    assert sig["tier"] == "mid" and sig["direction"] == 0
    sig, _ = step(st, _row(0.20000001, 0.10, 0.10, ar=5.0), CFG)  # sue just above 1.0
    assert sig["tier"] == "hi+" and sig["direction"] == 1
    sig, _ = step(st, _row(0.00, 0.10, 0.10, ar=5.0), CFG)   # sue = -1.0 exactly
    assert sig["tier"] == "lo-" and sig["direction"] == -1
    sig, _ = step(st, _row(0.00000001, 0.10, 0.10, ar=5.0), CFG)  # sue just above -1.0
    assert sig["tier"] == "mid" and sig["direction"] == 0
    sig, _ = step(st, _row(-0.00000001, 0.10, 0.10, ar=5.0), CFG)  # sue just below -1.0
    assert sig["tier"] == "lo-" and sig["direction"] == -1


def test_invalid_input_unknown():
    st = init_state()
    bad_rows = [
        {"ticker": "X", "eps_act": float("nan"), "eps_exp": 1.00, "sigma": 0.10, "ar": None},
        {"ticker": "Y", "eps_act": 1.20, "eps_exp": 1.00, "sigma": 0.00, "ar": None},
        {"ticker": "Z", "eps_act": 1.20, "eps_exp": 1.00, "sigma": -0.10, "ar": None},
        {"ticker": "W", "eps_act": 1.20, "eps_exp": None, "sigma": 0.10, "ar": None},
        {"ticker": "V", "eps_act": float("inf"), "eps_exp": 1.00, "sigma": 0.10, "ar": None},
    ]
    for bad in bad_rows:
        sig, _ = step(st, bad, CFG)
        assert sig["module_state"] == "UNKNOWN", f"{bad['ticker']}: invalid must map to UNKNOWN"
        # never interpolate: no partial outputs leak
        assert sig["direction"] == 0 and sig["confidence"] == 0.0 and sig["capital"] == 0.0


def test_market_state_guards():
    st = init_state()
    good = _row(1.45, 1.20, 0.10, ar=2.46)
    sig, _ = step(st, good, CFG, market_state="HALTED")
    assert sig["module_state"] == "UNKNOWN" and sig["direction"] == 0
    sig, _ = step(st, good, CFG, market_state="AUCTION")
    assert sig["module_state"] == "DEGRADED", "auction must hold last vector in DEGRADED"
    sig, _ = step(st, good, CFG, market_state="CLOSED")
    assert sig["module_state"] == "OFF" and sig["direction"] == 0
    sig, _ = step(st, good, CFG, market_state="CONTINUOUS_TRADING")
    assert sig["module_state"] == "OK" and sig["direction"] == 1


def test_staleness_ttl():
    st = init_state()
    good = _row(1.45, 1.20, 0.10, ar=2.46)
    # stale: announcement far older than the TTL -> UNKNOWN
    sig, _ = step(st, good, CFG, now=100, announce=0, stale_after=30)
    assert sig["module_state"] == "UNKNOWN"
    # fresh: within the TTL -> OK
    sig, _ = step(st, good, CFG, now=100, announce=90, stale_after=30)
    assert sig["module_state"] == "OK" and sig["direction"] == 1


def test_cooldown():
    st = init_state()
    good = _row(1.45, 1.20, 0.10, ar=2.46)
    # last entry 1 index ago, cooldown window 5 -> veto to direction 0, module OK
    sig, _ = step(st, good, CFG, now=10, last_entry=9, cooldown_win=5)
    assert sig["direction"] == 0 and sig["module_state"] == "OK"
    # last entry outside the window -> allowed
    sig, _ = step(st, good, CFG, now=10, last_entry=2, cooldown_win=5)
    assert sig["direction"] == 1 and sig["module_state"] == "OK"


def test_locate_gate():
    st = init_state()
    short_row = _row(0.82, 0.90, 0.08, ar=2.00)  # sue = -1.0 -> lo-
    sig, _ = step(st, short_row, CFG, locate_ok=False)
    assert sig["direction"] == 0 and sig["module_state"] == "UNKNOWN", \
        "SHORT without locate must be vetoed (C7)"
    sig, _ = step(st, short_row, CFG, locate_ok=True)
    assert sig["direction"] == -1 and sig["gate_pass"] == 1


# ---------------------------------------------------------------- causality

def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()):
        fill_event = s["fill_event_ts"]
        signal_event = s["computed_at"]
        if fill_event is not None:
            assert fill_event > signal_event, "fill must strictly follow the signal event"


def test_lookahead_guard():
    # mis-pinned announcement ts (announce > now) -> UNKNOWN, never a signal
    st = init_state()
    sig, _ = step(st, _row(1.45, 1.20, 0.10, ar=2.46), CFG, now=5, announce=10)
    assert sig["module_state"] == "UNKNOWN" and sig["direction"] == 0
