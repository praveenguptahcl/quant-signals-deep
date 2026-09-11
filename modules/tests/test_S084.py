"""Acceptance tests for S084 — Hasbrouck (1991) trade–quote VAR.

Template v1.0.0. Reference implementation of the §S3 normative pseudocode:
loads the fixture tape, computes the trade innovation against the carried
VAR(1), prices it with the long-run impulse response (LRI), binds the
executable cost gate on direction (C2: sub-threshold innovations emit
direction 0), and asserts causality, gate veto paths, boundary conditions,
and invalid-input handling (invalid input → UNKNOWN, never interpolate).

Run: python3 -m pytest modules/tests/test_S084.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S084_tape.csv"
EXPECTED = FIX / "S084_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
NS = 1_000_000_000  # int64-ns timestamps per the §S0.4 time contract


def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def _num(v):
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
        rows.append({k: _num(v) for k, v in r.items()})
    return rows


# ---------------------------------------------------------------------------
# Reference implementation of the §S3 normative pseudocode.
# ---------------------------------------------------------------------------
CFG = {
    "A": [[0.1046, 0.0120], [0.1479, 0.5958]],  # chapter OLS estimate [documented]
    "k": 0.5,             # cost-gate multiplier [default]
    "conf_scale": 5.0,    # cents of permanent impact -> confidence 1.0 [example]
    "cadence_s": 1.0,     # per_bar (1-s) [fixed]
    "cooldown_s": 60.0,   # post-compliance-block cooldown [default]
    "ttl_mult": 3,        # staleness TTL = 3 x cadence [default] (F4)
    "seq_gap_max": 1000,  # seq gap -> DEGRADED, restart windows [default]
    "notional": 1e6,      # gate notional $ [example]
    "adv_pct": 0.01,      # participation of ADV [example]
    "venue": "XNAS",
    "side": "taker",      # [default]
    "urgency": 0.0,       # [default]
}


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model — mirrors the §S2 COST block exactly.

    4-component stack (bps, per side): spread 1.0 [example] + fees 0.3 taker /
    -0.2 maker [example] + borrow 0.0 [default: signal holds no positions;
    borrow accrues in the executing T-module's ledger] + impact/adverse-
    selection slippage 0.2 [example]. adv_pct/venue/urgency are interface-
    complete and wire to the impact term at scale-up (currently constant,
    flagged [example]).
    """
    spread_bps = 1.0   # [example] effective spread, 1c on $100
    if side == "taker":
        fee_bps = 0.3  # [example] basis: Nasdaq remove $0.0030/share [documented]
    elif side == "maker":
        fee_bps = -0.2  # [example] add rebate, tier-dependent
    elif side == "mixed":
        fee_bps = 0.05  # [example] blend
    else:
        raise ValueError(f"side must be taker|maker|mixed, got {side!r}")
    borrow_bps = 0.0   # [default] borrow_bps_per_day=0: no positions held
    impact_bps = 0.2   # [example] adverse-selection slippage on the eval trade
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _lri_cents(A):
    a, b, c, d = A[0][0], A[0][1], A[1][0], A[1][1]
    det = (1 - a) * (1 - d) - b * c
    return 100.0 * b / det  # e_m'(I-A)^{-1}e_q in cents


def _bad(x):
    return x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))


def init_state():
    return {"prev_dm": None, "prev_q": None, "last_seq": None,
            "cooldown_until": None, "last": None}


def _flat(ts, module_state, cfg, u_q=float("nan"), edge_bps=0.0, gate_pass=0):
    A = cfg["A"]
    cost = expected_cost_bps(cfg["notional"], cfg["adv_pct"], cfg["venue"],
                             cfg["side"], cfg["urgency"])
    return {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
            "module_state": module_state, "edge_bps": edge_bps, "cost_bps": cost,
            "u_q": u_q, "irf_1_cents": 100.0 * A[0][1], "lri_cents": _lri_cents(A),
            "gate_pass": gate_pass,
            "fill_event_ts": ts + int(cfg["cadence_s"] * NS) if isinstance(ts, int) else None}


def step(state, row, cfg, t_now=None):
    ts = row.get("event_ts")
    asof = row.get("asof_ts", ts)
    market = row.get("market_state", "CONTINUOUS_TRADING")
    bid, ask, mid, dm, q = (row.get("bid"), row.get("ask"), row.get("mid"),
                            row.get("dm"), row.get("q"))
    A, lri = cfg["A"], _lri_cents(cfg["A"])
    ttl_ns = cfg["ttl_mult"] * cfg["cadence_s"] * NS

    # G1: halt/auction per the §S0.5 market-state table.
    if market in ("HALTED", "CLOSED"):
        # freeze; discard contributions across reopen -> restart windows
        state["prev_dm"] = state["prev_q"] = None
        sig = _flat(ts, "UNKNOWN", cfg)
        state["last"] = sig
        return sig, state
    if market == "AUCTION":
        state["module_state_hint"] = "DEGRADED"
        sig = _flat(ts, "DEGRADED", cfg)  # no new signals; hold last
        state["last"] = sig
        return sig, state

    # G2: staleness (F4) — data older than 3x cadence at decision time.
    if t_now is None:
        t_now = ts if isinstance(ts, int) else 0
    if isinstance(ts, int) and isinstance(asof, int) and (t_now - ts) > ttl_ns:
        sig = _flat(ts, "UNKNOWN", cfg)
        state["last"] = sig
        return sig, state

    # G3: input validity (F1/F2) — invalid input -> UNKNOWN, never interpolate.
    invalid = (ts is None or _bad(bid) or _bad(ask) or _bad(mid) or _bad(dm)
               or bid <= 0 or ask <= 0 or mid <= 0 or bid >= ask  # crossed book
               or q not in (1, -1))
    if invalid:
        if isinstance(ts, int):
            state["cooldown_until"] = ts + int(cfg["cooldown_s"] * NS)  # C10
        sig = _flat(ts, "UNKNOWN", cfg)
        state["last"] = sig
        return sig, state

    # G4: post-compliance-block cooldown (C10) — no re-entry.
    if (isinstance(ts, int) and state["cooldown_until"] is not None
            and ts < state["cooldown_until"]):
        sig = _flat(ts, "DEGRADED", cfg)
        state["last"] = sig
        return sig, state

    # G5: seq gap (restart windows).
    seq = row.get("seq")
    if (seq is not None and state["last_seq"] is not None
            and seq - state["last_seq"] > cfg["seq_gap_max"]):
        state["prev_dm"] = state["prev_q"] = None
        sig = _flat(ts, "DEGRADED", cfg)
        state["last"] = sig
        state["last_seq"] = seq
        return sig, state
    if seq is not None:
        state["last_seq"] = seq

    # Warmup: no history -> no innovation -> DEGRADED, flat.
    if state["prev_dm"] is None:
        sig = _flat(ts, "DEGRADED", cfg)
        state["prev_dm"], state["prev_q"] = dm, q
        state["last"] = sig
        return sig, state

    # Core: trade innovation vs the carried VAR(1).
    exp_q = A[1][0] * state["prev_dm"] + A[1][1] * state["prev_q"]
    uq = q - exp_q
    edge_bps = abs(lri * uq) / mid * 100.0  # cents -> bps on the mid
    cost = expected_cost_bps(cfg["notional"], cfg["adv_pct"], cfg["venue"],
                             cfg["side"], cfg["urgency"])
    gate_pass = 1 if cost <= cfg["k"] * edge_bps else 0  # executable predicate

    # C2: direction binds on the gate — sub-threshold scores emit direction 0.
    if not gate_pass:
        direction, mstate = 0, "OK"
    elif uq > 0:
        direction, mstate = 1, "OK"
    elif uq < 0:
        # C7: SHORT requires the consumer to assert locate; Reg-SHO
        # threshold securities force direction 0.
        if not row.get("locate_ok", True):
            direction, mstate = 0, "DEGRADED"
        else:
            direction, mstate = -1, "OK"
    else:
        direction, mstate = 0, "OK"

    confidence = 0.0 if direction == 0 else min(1.0, abs(lri * uq) / cfg["conf_scale"])
    sig = _flat(ts, mstate, cfg, u_q=uq, edge_bps=edge_bps, gate_pass=gate_pass)
    sig["direction"] = direction
    sig["confidence"] = confidence
    sig["capital"] = 0.5 * confidence  # §S2 sizing reference [default]
    state["prev_dm"], state["prev_q"] = dm, q
    state["last"] = sig
    return sig, state


def run(rows, **kw):
    st = init_state()
    return [step(st, r, CFG, **kw)[0] for r in rows]


def _close(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(b))
    return a == b


COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
        "edge_bps", "cost_bps", "u_q", "irf_1_cents", "lri_cents", "gate_pass"]


def test_fixtures_exist_and_typed():
    assert TAPE.exists(), "tape fixture missing"
    assert EXPECTED.exists(), "expected fixture missing"
    for path in (TAPE, EXPECTED):
        with open(path) as f:
            head = [next(f) for _ in range(3)]
        assert any(l.startswith("# TYPE:") for l in head), f"{path.name} missing TYPE header"
    assert len(tape()) >= 5, "fixture needs >=5 hand-checkable rows"


def test_expected_matches_reference():
    rows = tape()
    sigs = run(rows)
    exp = load_csv(EXPECTED)
    assert len(exp) == len(sigs), "expected row count != tape row count"
    for i, (s, e) in enumerate(zip(sigs, exp)):
        assert int(e["ev"]) == int(rows[i]["ev"]), f"row {i} ev mismatch"
        for c in COLS:
            got, want = s[c], _num(e[c])
            assert _close(got, want), f"row {i} col {c}: got {got} want {want}"


def test_signal_vector_valid():
    for s in run(tape()):
        assert s["direction"] in (+1, -1, 0), "direction not in {+1,-1,0}"
        assert 0.0 <= s["confidence"] <= 1.0, "confidence out of [0,1]"
        assert 0.0 <= s["capital"] <= 0.5, "capital out of [0,0.5]"
        assert s["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")
        assert s["capital"] == 0.5 * s["confidence"], "capital must equal 0.5*confidence"


def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()):
        fill_event, signal_event = s["fill_event_ts"], s["computed_at"]
        if fill_event is not None:
            assert fill_event > signal_event, "causality violated: fill <= signal"


def test_cost_callable_mirrors_block():
    # §S2 4-component stack: spread 1.0 + fees + borrow 0.0 + impact 0.2.
    taker = expected_cost_bps(1e6, 0.01, "XNAS", "taker", 0.0)
    maker = expected_cost_bps(1e6, 0.01, "XNAS", "maker", 0.0)
    mixed = expected_cost_bps(1e6, 0.01, "XNAS", "mixed", 0.0)
    assert taker == 1.0 + 0.3 + 0.0 + 0.2 == 1.5
    assert maker == 1.0 + (-0.2) + 0.0 + 0.2 == 1.0
    assert mixed == 1.0 + 0.05 + 0.0 + 0.2 == 1.25
    try:
        expected_cost_bps(1e6, 0.01, "XNAS", "midpoint", 0.0)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown side must raise (caller maps to UNKNOWN)")


def test_cost_gate_predicate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps
    k = CFG["k"]
    c = expected_cost_bps(1e6, 0.01, "XNAS", "taker", 0.0)
    assert c <= k * 100.0, "gate should pass on a large edge"
    assert not (c <= k * 0.01), "gate should block on a tiny edge"
    assert c <= k * (c / k), "gate passes exactly at the boundary (<=)"


def test_gate_veto_path():
    # rows 2-5: |LRI*u_q| ~1.34 bps of edge < 2x cost 1.5 -> vetoed to direction 0;
    # row 6: 5.33 bps of edge -> passes.
    sigs = run(tape())
    for i in (1, 2, 3, 4):
        assert sigs[i]["gate_pass"] == 0, f"row {i} should be gate-vetoed"
        assert sigs[i]["direction"] == 0, f"row {i} veto must emit direction 0 (C2)"
        assert sigs[i]["confidence"] == 0.0 and sigs[i]["capital"] == 0.0
        assert sigs[i]["module_state"] == "OK", "veto is a measurement, not an error"
    assert sigs[5]["gate_pass"] == 1
    assert sigs[5]["direction"] == -1


def test_confidence_cap_boundary():
    # row 6: |LRI*u_q| = 5.33c > conf_scale 5.0 -> capped at exactly 1.0.
    sigs = run(tape())
    assert sigs[5]["confidence"] == 1.0
    assert sigs[5]["capital"] == 0.5


def test_hand_checked_arithmetic():
    # pins the §S4 hand-checks: IRF(1)=1.20c, LRI=3.33c, row innovations.
    sigs = run(tape())
    assert sigs[0]["irf_1_cents"] == 1.2
    assert abs(sigs[0]["lri_cents"] - 3.3319831397210486) <= TOL
    assert sigs[1]["u_q"] == 0.40446622
    assert sigs[5]["u_q"] == -1.59917212
    assert math.isnan(sigs[0]["u_q"]), "warmup row has no innovation"


def test_warmup_degraded():
    sigs = run(tape())
    assert sigs[0]["module_state"] == "DEGRADED"
    assert sigs[0]["direction"] == 0


def _fab(**over):
    r = dict(tape()[5])  # strong-signal row as a base
    r.update(over)
    return r


def _primed():
    """State with one valid warmup bar consumed (past the DEGRADED warmup)."""
    st = init_state()
    step(st, dict(tape()[0]), CFG)
    return st


def test_invalid_input_unknown():
    cases = [
        {"mid": float("nan")}, {"mid": -1.0}, {"bid": float("inf")},
        {"dm": float("nan")}, {"q": 0}, {"q": 2},
        {"bid": 100.05, "ask": 100.04},  # crossed book
    ]
    for kw in cases:
        sig, _ = step(init_state(), _fab(**kw), CFG)
        assert sig["module_state"] == "UNKNOWN", f"{kw} must map to UNKNOWN"
        assert sig["direction"] == 0, "UNKNOWN emits no direction"


def test_halt_auction_freeze():
    st = init_state()
    sig, st = step(st, _fab(market_state="HALTED"), CFG)
    assert sig["module_state"] == "UNKNOWN", "halt -> UNKNOWN, freeze"
    # contributions across reopen discarded -> next continuous row is warmup
    sig2, _ = step(st, _fab(market_state="CONTINUOUS_TRADING"), CFG)
    assert sig2["module_state"] == "DEGRADED", "windows restart across reopen"
    sig3, _ = step(init_state(), _fab(market_state="AUCTION"), CFG)
    assert sig3["module_state"] == "DEGRADED", "auction -> DEGRADED, no new signals"
    assert sig3["direction"] == 0


def test_staleness_ttl():
    ts = tape()[5]["event_ts"]
    stale = _fab(asof_ts=ts)  # replay: decision time 4s after the event
    sig, _ = step(_primed(), stale, CFG, t_now=ts + 4 * NS)
    assert sig["module_state"] == "UNKNOWN", "data older than 3x cadence -> UNKNOWN"
    fresh = _fab(asof_ts=ts)
    sig2, _ = step(_primed(), fresh, CFG, t_now=ts + 2 * NS)
    assert sig2["module_state"] == "OK"


def test_locate_guard_short():
    blocked, _ = step(_primed(), _fab(locate_ok=False), CFG)
    assert blocked["direction"] == 0, "SHORT without locate_ok must not emit"
    assert blocked["module_state"] == "DEGRADED"
    ok, _ = step(_primed(), _fab(locate_ok=True), CFG)
    assert ok["direction"] == -1


def test_cooldown_blocks_reentry():
    st = _primed()
    ts = tape()[5]["event_ts"]
    bad, st = step(st, _fab(event_ts=ts, mid=float("nan")), CFG)
    assert bad["module_state"] == "UNKNOWN"
    blocked, st = step(st, _fab(event_ts=ts + 30 * NS), CFG)  # inside 60s cooldown
    assert blocked["module_state"] == "DEGRADED"
    assert blocked["direction"] == 0, "no re-entry during C10 cooldown"
    sig, _ = step(st, _fab(event_ts=ts + 61 * NS), CFG)  # after cooldown
    assert sig["module_state"] == "OK"


def test_seq_gap_degraded():
    st = init_state()
    s1, st = step(st, _fab(seq=100), CFG)
    s2, st = step(st, _fab(seq=100 + 2000, event_ts=tape()[5]["event_ts"] + NS), CFG)
    assert s2["module_state"] == "DEGRADED", "seq gap > 1000 restarts windows"
