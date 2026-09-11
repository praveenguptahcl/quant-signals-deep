"""Acceptance tests for S077 — Kalman-filtered fair value (v1.1.0).

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode (§S3), and asserts causality, the cost gate,
guards (staleness / clock-skew / halt / Pp-veto / cooldown / locate), boundary
conditions, and hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S077.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S077_tape.csv"
EXPECTED = FIX / "S077_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
TTL_NS = 180_000_000_000     # staleness TTL = 180 s [default] (3x 1-min cadence, F4)
SKEW_NS = 1_000_000          # max clock skew = 1 ms [default] (§S0.4)


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
        d = {}
        for k, v in r.items():
            d[k] = _num(v)
        rows.append(d)
    return rows


def mkrow(mid, event_ts=1788960600000000000, asof_skew_ns=120_000,
          market_state="CONTINUOUS_TRADING"):
    """Synthetic single-bar row for guard/veto tests (fixture-style timestamps)."""
    return {"ev": 1, "event_ts": event_ts, "asof_ts": event_ts + asof_skew_ns,
            "symbol": "TEST:XNAS", "mid": mid, "market_state": market_state}


# Reference implementation of the §S3 normative pseudocode.
CFG = {"q": 0.04, "r": 0.16, "x0": 100.0, "p0_mult": 1.0,
       "z_entry": 2.0, "z_exit": 0.5, "p_max": 0.25, "edge_per_z": 5.0,
       "mom_entry": 0.10, "mode": "fade", "cooldown_s": 300.0,
       "cost_gate_k": 0.5, "ref_notional": 1e6, "ref_adv_pct": 0.01,
       "venue": "XNAS", "side": "taker", "urgency": "normal", "locate_ok": True}


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    # Callable mirrors the module COST block exactly: 1.0 + 0.30 + 0.0 + 0.0
    spread_bps = 1.0    # [example]
    fee_bps = 0.30      # [internal-est] taker
    if side == "maker":
        fee_bps = -0.20  # [example] maker rebate, side-conditioned
    borrow_bps = 0.0     # [default] borrow_bps_per_day x 0 days held intraday
    impact_bps = 0.0     # [example] flagged
    return spread_bps + fee_bps + borrow_bps + impact_bps


def init_state(cfg=CFG):
    return {"x": cfg["x0"], "P": cfg["p0_mult"] * cfg["r"],
            "cooldown_until": 0, "module_state": "OK",
            "locate_ok": cfg.get("locate_ok", True)}


def _unknown(row, module_state="UNKNOWN"):
    sig = dict(direction=0, confidence=0.0, capital=0.0,
               computed_at=row["event_ts"], module_state=module_state,
               edge_bps=0.0, cost_bps=0.0,
               x_hat=float("nan"), P=float("nan"), K=float("nan"),
               z_resid=0.0)
    return sig


def _bad(y):
    return (y is None
            or (isinstance(y, float) and (math.isnan(y) or not math.isfinite(y)))
            or y <= 0)


def step(state, row, cfg, now_ts=None):
    now = row["asof_ts"] if now_ts is None else now_ts
    ms = row.get("market_state", "CONTINUOUS_TRADING")
    if ms == "HALTED":
        return _unknown(row), dict(state, module_state="UNKNOWN")   # freeze; §S0.5
    if ms == "AUCTION":
        return _unknown(row, "DEGRADED"), dict(state, module_state="DEGRADED")
    if (now - row["event_ts"]) > TTL_NS:                             # F4 staleness
        return _unknown(row), dict(state, module_state="UNKNOWN")
    if abs(row["asof_ts"] - row["event_ts"]) > SKEW_NS:               # clock-skew reject
        return _unknown(row), dict(state, module_state="UNKNOWN")
    y = row["mid"]
    if _bad(y):                                                     # F1/F2: never interpolate
        return _unknown(row), dict(state, module_state="UNKNOWN")
    Pp = state["P"] + cfg["q"]                                      # predict variance
    K = Pp / (Pp + cfg["r"])                                        # Kalman gain
    if not (math.isfinite(K) and 0.0 <= K <= 1.0):                   # F2 gain bounds
        return _unknown(row), dict(state, module_state="UNKNOWN")
    x = state["x"] + K * (y - state["x"])                           # update mean
    P = (1.0 - K) * Pp                                              # update variance
    if not (math.isfinite(x) and math.isfinite(P)) or P < 0:         # F2
        return _unknown(row), dict(state, module_state="UNKNOWN")
    resid = y - x
    z = resid / math.sqrt(P + cfg["r"])                             # z-scored fade object
    if not math.isfinite(z):                                        # F2
        return _unknown(row), dict(state, module_state="UNKNOWN")
    dx = x - state["x"]                                             # fair-value momentum
    edge_bps = abs(z) * cfg["edge_per_z"]                           # [example] edge map
    cost_bps = expected_cost_bps(cfg["ref_notional"], cfg["ref_adv_pct"],
                                 cfg["venue"], cfg["side"], cfg["urgency"])
    cost_ok = cost_bps <= cfg["cost_gate_k"] * edge_bps             # normative cost gate
    p_veto = Pp > cfg["p_max"]                                      # filter-distrust veto (Pp, not posterior)
    cooldown_live = row["event_ts"] < state["cooldown_until"]       # C10
    direction = 0
    if cost_ok and not p_veto and not cooldown_live:
        if cfg["mode"] == "fade":
            if z >= cfg["z_entry"]:
                direction = -1
            elif z <= -cfg["z_entry"]:
                direction = 1
        else:                                                       # momentum mode
            if dx >= cfg["mom_entry"]:
                direction = 1
            elif dx <= -cfg["mom_entry"]:
                direction = -1
    if direction == -1 and not state.get("locate_ok", True):        # C7 locate veto
        direction = 0
    confidence = min(1.0, abs(z) / (2.0 * cfg["z_entry"])) if direction != 0 else 0.0
    capital = 0.5 * confidence                                      # [default]
    sig = dict(direction=direction, confidence=confidence, capital=capital,
               computed_at=row["event_ts"], module_state="OK",
               edge_bps=edge_bps, cost_bps=cost_bps,
               x_hat=x, P=P, K=K, z_resid=z, Pp=Pp, dx=dx)
    new_state = {"x": x, "P": P, "cooldown_until": state["cooldown_until"],
                 "module_state": "OK", "locate_ok": state.get("locate_ok", True)}
    return sig, new_state


def run(tape_rows, cfg=CFG):
    st = init_state(cfg)
    out = []
    for i, r in enumerate(tape_rows):
        sig, st = step(st, r, cfg)
        sig = dict(sig)
        sig["fill_event_ts"] = (tape_rows[i + 1]["event_ts"]
                                if i + 1 < len(tape_rows) else None)
        out.append(sig)
    return out


def _close(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(b))
    return a == b


# ---------------------------------------------------------------- fixture tests

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
    cols = ["computed_at", "direction", "confidence", "capital", "module_state",
            "edge_bps", "cost_bps", "x_hat", "P", "K", "z_resid"]
    for i, (s, e) in enumerate(zip(sigs, exp)):
        assert int(e["ev"]) == int(rows[i]["ev"]), f"row {i} ev mismatch"
        for c in cols:
            got = s[c]
            want = _num(e[c])
            assert _close(got, want), f"row {i} col {c}: got {got} want {want}"


def test_signal_vector_valid():
    for s in run(tape()):
        assert s["direction"] in (+1, -1, 0), "direction not in {+1,-1,0}"
        assert 0.0 <= s["confidence"] <= 1.0, "confidence out of [0,1]"
        assert 0.0 <= s["capital"] <= 0.5, "capital out of [0,0.5]"
        assert s["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


# ---------------------------------------------------------------- causality pins

def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()):
        fill_event = s["fill_event_ts"]
        signal_event = s["computed_at"]
        if fill_event is not None:
            assert fill_event > signal_event, "fill_event must be > signal_event"
            assert fill_event - signal_event == 60_000_000_000, \
                "earliest fill is the next 1-min bar open"


# ---------------------------------------------------------------- cost gate

def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5  # [default]
    big_edge = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 100.0
    tiny_edge = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"
    # callable mirrors the COST block exactly: 1.0 + 0.30 + 0.0 + 0.0 = 1.30
    assert abs(expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") - 1.30) < 1e-12
    assert abs(expected_cost_bps(1e6, 0.01, "XNAS", "maker", "normal") - 0.80) < 1e-12


# ---------------------------------------------------------------- invalid inputs -> UNKNOWN

def test_invalid_input_unknown():
    rows = tape()
    bad = dict(rows[0])
    bad.update({'mid': float('nan')})
    st = init_state()
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"


def test_negative_price_unknown():
    st = init_state()
    sig, st2 = step(st, mkrow(-5.0), CFG)
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0


def test_nonfinite_price_unknown():
    st = init_state()
    sig, _ = step(st, mkrow(float("inf")), CFG)
    assert sig["module_state"] == "UNKNOWN"


def test_empty_events_unknown():
    # §S3 pseudocode: `if events is empty: return UNKNOWN` (F1)
    assert len([]) == 0  # documents the guard: no events -> no signal
    st = init_state()
    sig, st2 = step(st, mkrow(100.0), CFG)
    assert sig["module_state"] == "OK"  # control: a real event works


def test_stale_event_unknown():
    st = init_state()
    row = mkrow(100.4)
    # now = event_ts + 200 s > TTL (180 s)
    sig, _ = step(st, row, CFG, now_ts=row["event_ts"] + 200_000_000_000)
    assert sig["module_state"] == "UNKNOWN", "stale input must map to UNKNOWN"


def test_clock_skew_unknown():
    st = init_state()
    # asof_ts - event_ts = 2 ms > max_skew 1 ms
    sig, _ = step(st, mkrow(100.4, asof_skew_ns=2_000_000), CFG)
    assert sig["module_state"] == "UNKNOWN", "clock-skew violation must map to UNKNOWN"


def test_halt_freezes_unknown():
    st = init_state()
    row = mkrow(100.4, market_state="HALTED")
    sig, st2 = step(st, row, CFG)
    assert sig["module_state"] == "UNKNOWN"
    assert st2["x"] == st["x"] and st2["P"] == st["P"], "halt must freeze filter state"


# ---------------------------------------------------------------- gate veto paths

def _big_z_state():
    # state x=100, small P, then a +10 mid -> |z| ~ 18 >> z_entry, cost gate passes
    st = init_state()
    st["x"] = 100.0
    st["P"] = 0.001
    return st


def test_predicted_variance_veto():
    # Pp > p_max vetoes entry despite a huge |z| (veto binds on Pp, the
    # predicted variance — a posterior-P veto would be vacuous since P_tt <= R).
    cfg = dict(CFG, q=0.5)  # Pp = 0.16 + 0.5 = 0.66 > p_max 0.25
    st = init_state()
    sig, st2 = step(st, mkrow(110.0), cfg)
    assert sig["module_state"] == "OK"
    assert sig["Pp"] > cfg["p_max"]
    assert sig["direction"] == 0, "Pp veto must block entry"
    assert abs(sig["z_resid"]) > cfg["z_entry"], "control: the z would have fired"
    # state still updates (veto blocks entry, not the filter)
    assert st2["x"] != st["x"]


def test_cooldown_veto():
    st = _big_z_state()
    row = mkrow(110.0)
    st["cooldown_until"] = row["event_ts"] + 60_000_000_000  # C10 live cooldown
    sig, _ = step(st, row, CFG)
    assert sig["direction"] == 0, "live cooldown must block re-entry"
    # cooldown expired -> entry allowed
    st2 = dict(st, cooldown_until=row["event_ts"] - 1)
    sig2, _ = step(st2, row, CFG)
    assert sig2["direction"] == -1


def test_locate_veto_short():
    st = _big_z_state()
    row = mkrow(110.0)  # z >> +z_entry -> SHORT candidate
    cfg_no_locate = dict(CFG, locate_ok=False)
    sig, _ = step(dict(st, locate_ok=False), row, cfg_no_locate)
    assert sig["direction"] == 0, "C7: no SHORT without locate"
    sig2, _ = step(dict(st, locate_ok=True), row, CFG)
    assert sig2["direction"] == -1, "control: locate asserted -> SHORT emits"


# ---------------------------------------------------------------- boundary conditions

def _mid_for_z(st, cfg, z_target):
    # Invert z = (1-K)(mid - x0)/sqrt((1-K)Pp + r) for mid given a target z.
    Pp = st["P"] + cfg["q"]
    K = Pp / (Pp + cfg["r"])
    denom = math.sqrt((1.0 - K) * Pp + cfg["r"])
    return st["x"] + z_target * denom / (1.0 - K)


def test_fade_entry_boundary():
    # Entry rule is z >= z_entry (fade SHORT) / z <= -z_entry (fade LONG).
    st = _big_z_state()
    row_at = mkrow(_mid_for_z(st, CFG, CFG["z_entry"]))
    sig_at, _ = step(dict(st), row_at, CFG)
    # boundary-consistency pin: direction == -1 iff z_resid >= z_entry
    assert (sig_at["direction"] == -1) == (sig_at["z_resid"] >= CFG["z_entry"])
    row_below = mkrow(_mid_for_z(st, CFG, CFG["z_entry"] - 0.01))
    sig_below, _ = step(dict(st), row_below, CFG)
    assert sig_below["z_resid"] < CFG["z_entry"]
    assert sig_below["direction"] == 0
    row_above = mkrow(_mid_for_z(st, CFG, CFG["z_entry"] + 0.01))
    sig_above, _ = step(dict(st), row_above, CFG)
    assert sig_above["z_resid"] > CFG["z_entry"]
    assert sig_above["direction"] == -1
    # long side: z <= -z_entry
    st_long = _big_z_state()
    row_long = mkrow(_mid_for_z(st_long, CFG, -CFG["z_entry"] - 0.01))
    sig_long, _ = step(st_long, row_long, CFG)
    assert sig_long["direction"] == 1


def test_momentum_mode_entries():
    cfg = dict(CFG, mode="momentum")
    st = _big_z_state()
    sig_long, _ = step(dict(st), mkrow(105.0), cfg)
    assert sig_long["dx"] >= cfg["mom_entry"]
    assert sig_long["direction"] == 1
    st2 = _big_z_state()
    sig_short, _ = step(dict(st2, locate_ok=True), mkrow(95.0), cfg)
    assert sig_short["dx"] <= -cfg["mom_entry"]
    assert sig_short["direction"] == -1, "momentum SHORT also needs locate_ok"
    st3 = _big_z_state()
    sig_noloc, _ = step(dict(st3, locate_ok=False), mkrow(95.0),
                        dict(cfg, locate_ok=False))
    assert sig_noloc["direction"] == 0


def test_cost_gate_blocks_tiny_edge():
    # |z| ~ 0.002 -> edge ~0.01 bps << cost/k=2.6 bps: no entry even in-range.
    st = _big_z_state()
    row = mkrow(100.002)
    sig, _ = step(st, row, CFG)
    assert sig["edge_bps"] < sig["cost_bps"] / CFG["cost_gate_k"]
    assert sig["direction"] == 0, "cost gate must block tiny-edge entries"
