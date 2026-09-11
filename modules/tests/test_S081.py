"""Acceptance tests for S081 — Hawkes buy/sell intensity imbalance.

Template v1.0.0. Module v1.1.0. Loads the fixture tape, runs a reference
implementation of the chapter's normative pseudocode (§S3), and asserts
causality, the cost gate, boundary behavior, veto paths (persistence /
cooldown / locate / halt), and hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S081.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S081_tape.csv"
EXPECTED = FIX / "S081_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]


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


# Config per §S0.2 (defaults; status default/example/calibrate as in the chapter).
CFG = {"mu": 0.4, "alpha_self": 0.9, "beta_self": 1.5, "alpha_cross": 0.25,
       "beta_cross": 1.0, "kappa": 2.0, "kappa_exit": 1.5, "z_window_s": 300.0,
       "m_d": 0.1458, "s_d": 1.2217, "persist_n": 3,
       "p_max": 0.25, "cooldown_s": 60.0, "cost_gate_k": 0.5,
       "locate_ok": False, "edge_per_z": 1.0}


def check_stationarity(cfg):
    """Config-load guard: fail closed if the branching matrix is not subcritical."""
    eig1 = cfg["alpha_self"] / cfg["beta_self"] + cfg["alpha_cross"] / cfg["beta_cross"]
    eig2 = cfg["alpha_self"] / cfg["beta_self"] - cfg["alpha_cross"] / cfg["beta_cross"]
    if max(eig1, eig2) >= 1.0:
        raise ValueError("stationarity violated: rho(N) >= 1")


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    # Callable cost model — mirrors the §S2 COST block exactly (taker path).
    spread_bps = 4.00   # [example]
    fee_bps = 1.40      # [example]
    borrow_bps = 0.00   # [default]; borrow_bps_per_day = 0.0
    impact_bps = 2.00   # [example]
    if side == "maker":
        fee_bps = -0.80  # [example] maker rebate
    return spread_bps + fee_bps + borrow_bps + impact_bps


def init_state():
    return {"module_state": "OK", "t_last": None, "z_prev_sgn": 0,
            "n_consec": 0, "t_last_exit": None}


def _bad(v):
    return v is None or (isinstance(v, float) and (math.isnan(v) or not math.isfinite(v)))


def step(state, row, cfg, market_state="CONTINUOUS_TRADING"):
    """Reference implementation of the §S3 normative pseudocode, fixture path.

    Fixture rows carry stated intensities (lam_b/lam_s); the O(1) recursion is
    the production path. Guards (validity, ordering, halt/auction, locate,
    cooldown, persistence, cost gate, causality) are all exercised here.
    """
    ts = row.get("event_ts")
    lb = row.get("lam_b")
    ls = row.get("lam_s")
    side = row.get("side")
    sig = dict(computed_at=ts if isinstance(ts, int) else 0, direction=0,
               confidence=0.0, capital=0.0, module_state="OK", edge_bps=0.0,
               cost_bps=7.40,
               fill_event_ts=(ts + 1_000_000) if isinstance(ts, int) else 0,
               d=float("nan"), z=float("nan"), burst=0)
    if market_state == "HALTED":
        sig["module_state"] = "UNKNOWN"
        return sig, state
    if market_state == "AUCTION":
        sig["module_state"] = "DEGRADED"
        return sig, state
    if not isinstance(ts, int) or ts <= 0 or _bad(lb) or _bad(ls) or side not in (1, -1):
        sig["module_state"] = "UNKNOWN"
        return sig, state
    if state["t_last"] is not None and ts < state["t_last"]:
        sig["module_state"] = "UNKNOWN"  # out-of-order event
        return sig, state
    dd = lb - ls
    z = (dd - cfg["m_d"]) / cfg["s_d"]
    sgn = 1 if z > 0 else (-1 if z < 0 else 0)
    if sgn == state["z_prev_sgn"] and sgn != 0:
        state["n_consec"] += 1
    else:
        state["n_consec"] = 1
    state["z_prev_sgn"] = sgn
    burst = 1 if abs(z) > cfg["kappa"] else 0  # STRICT: |z| == kappa is not a burst
    if abs(z) < cfg["kappa_exit"] or state["module_state"] != "OK":
        state["t_last_exit"] = ts  # exit starts the post-exit cooldown
    edge = abs(z) * cfg["edge_per_z"]  # [example] edge per z unit
    cost = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")
    sig.update(d=dd, z=z, burst=burst, edge_bps=edge, cost_bps=cost)
    gate = cost <= cfg["cost_gate_k"] * edge          # executable cost-gate predicate
    cooled = state["t_last_exit"] is None or (ts - state["t_last_exit"]) / 1e9 > cfg["cooldown_s"]
    located = (sgn >= 0) or cfg["locate_ok"]          # C7 locate gate
    persist_ok = state["n_consec"] >= cfg["persist_n"]
    if burst and persist_ok and gate and cooled and located:
        sig["direction"] = 1 if sgn > 0 else -1
        sig["confidence"] = min(1.0, abs(z) / 4.0)
        sig["capital"] = min(cfg["p_max"], sig["confidence"] * cfg["p_max"])
    state["t_last"] = ts
    assert sig["fill_event_ts"] > sig["computed_at"]  # t -> t+1 causality
    return sig, state


def run(rows, cfg=None, market_state="CONTINUOUS_TRADING"):
    cfg = cfg or CFG
    check_stationarity(cfg)
    st = init_state()
    out = []
    for r in rows:
        sig, st = step(st, r, cfg, market_state)
        out.append(sig)
    return out


def mkrow(ev, ts, side, lam_b, lam_s):
    return {"ev": ev, "event_ts": ts, "asof_ts": ts + 1000, "side": side,
            "lam_b": lam_b, "lam_s": lam_s}


def z_to_lams(z, cfg=CFG):
    d = z * cfg["s_d"] + cfg["m_d"]
    return 10.0, 10.0 - d


def _close(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(b))
    return a == b


# ---------------------------------------------------------------- fixtures ---

def test_fixtures_exist_and_typed():
    assert TAPE.exists(), "tape fixture missing"
    assert EXPECTED.exists(), "expected fixture missing"
    for path in (TAPE, EXPECTED):
        with open(path) as f:
            head = [next(f) for _ in range(3)]
        assert any(l.startswith("# TYPE:") for l in head), f"{path.name} missing TYPE header"
    rows = tape()
    assert len(rows) >= 5, "fixture needs >=5 hand-checkable rows"


def test_expected_matches_reference():
    rows = tape()
    sigs = run(rows)
    exp = load_csv(EXPECTED)
    assert len(exp) == len(sigs), "expected row count != tape row count"
    cols = ["computed_at", "direction", "confidence", "capital", "module_state",
            "edge_bps", "cost_bps", "fill_event_ts", "d", "z", "burst"]
    for i, (s, e) in enumerate(zip(sigs, exp)):
        assert int(e["ev"]) == int(rows[i]["ev"]), f"row {i} ev mismatch"
        for c in cols:
            got, want = s[c], _num(e[c])
            assert _close(got, want), f"row {i} col {c}: got {got} want {want}"


# ------------------------------------------------------------- signal shape ---

def test_signal_vector_valid():
    for s in run(tape()):
        assert s["direction"] in (+1, -1, 0), "direction not in {+1,-1,0}"
        assert 0.0 <= s["confidence"] <= 1.0, "confidence out of [0,1]"
        assert 0.0 <= s["capital"] <= 0.5, "capital out of [0,0.5]"
        assert s["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()):
        assert s["fill_event_ts"] > s["computed_at"]


# ------------------------------------------------------------------ costs ---

def test_cost_gate_predicate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5  # [default]
    big_edge = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 100.0
    tiny_edge = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_cost_callable_mirrors_block():
    # §S2 COST block single source of truth: taker stack sums to 7.40 bps.
    taker = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")
    assert abs(taker - 7.40) <= 1e-12, "taker callable must equal the block total"
    maker = expected_cost_bps(1e6, 0.01, "XNAS", "maker", "normal")
    assert maker < taker, "maker rebate path must reduce cost"
    assert abs(maker - (4.00 - 0.80 + 0.00 + 2.00)) <= 1e-12


# --------------------------------------------------------------- boundaries ---

def test_boundary_z_at_kappa():
    # Fixture rows 81/82: |z| just below kappa -> burst 0; just above -> burst 1.
    sigs = run(tape())
    by_ev = {int(r["ev"]): s for r, s in zip(tape(), sigs)}
    assert abs(by_ev[81]["z"]) < CFG["kappa"] and by_ev[81]["burst"] == 0
    assert abs(by_ev[82]["z"]) > CFG["kappa"] and by_ev[82]["burst"] == 1
    # Strictness holds on both sides of the threshold within 1e-6.
    for dz, want in ((-1e-6, 0), (1e-6, 1)):
        lb, ls = z_to_lams(CFG["kappa"] + dz)
        s, _ = step(init_state(), mkrow(90, 9_000_000_000, 1, lb, ls), CFG)
        assert s["burst"] == want, f"burst strictness failed at kappa{dz:+g}"


# ------------------------------------------------------------- invalid input ---

def test_invalid_input_unknown():
    rows = tape()
    bad = dict(rows[0])
    bad.update({"ev": 81, "event_ts": 7900000000, "asof_ts": 7900001000,
                "side": -1, "lam_b": float("nan"), "lam_s": 9.0})
    sig, _ = step(init_state(), bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "NaN input must map to UNKNOWN, never interpolate"
    bad2 = dict(rows[0])
    bad2.update({"ev": 82, "event_ts": 7910000000, "asof_ts": 7910001000,
                 "side": 0, "lam_b": 8.0, "lam_s": 8.0})
    sig2, _ = step(init_state(), bad2, CFG)
    assert sig2["module_state"] == "UNKNOWN", "unsigned (side=0) event must map to UNKNOWN"


def test_out_of_order_ts_unknown():
    st = init_state()
    r1 = mkrow(1, 8_000_000_000, 1, 10.0, 7.42)
    r2 = mkrow(2, 7_999_000_000, 1, 10.0, 7.42)  # earlier than r1
    step(st, r1, CFG)
    sig, _ = step(st, r2, CFG)
    assert sig["module_state"] == "UNKNOWN", "out-of-order event_ts must map to UNKNOWN"


# --------------------------------------------------------------- veto paths ---

def test_persistence_veto():
    # A lone burst (no 3 consecutive same-sign z) must not emit, even with a
    # passing cost gate; the 3rd consecutive burst may emit.
    cfg = dict(CFG, cost_gate_k=10.0)  # force the gate open [example]
    lb, ls = z_to_lams(3.0)
    rows = [mkrow(i, 8_000_000_000 + i * 1_000_000_000, 1, lb, ls) for i in range(3)]
    sigs = run(rows, cfg=cfg)
    assert all(s["burst"] == 1 for s in sigs)
    assert sigs[0]["direction"] == 0 and sigs[1]["direction"] == 0, "persistence veto failed"
    assert sigs[2]["direction"] == 1, "3rd consecutive burst should emit"
    assert abs(sigs[2]["confidence"] - 0.75) <= 1e-12
    assert abs(sigs[2]["capital"] - 0.1875) <= 1e-12


def test_cooldown_veto():
    # |z| < kappa_exit starts a 60 s [default] post-exit cooldown: no re-entry inside it.
    cfg = dict(CFG, cost_gate_k=10.0, persist_n=1)  # open gate, persistence out of the way
    lb_exit, ls_exit = z_to_lams(0.0)   # exit event
    lb, ls = z_to_lams(3.0)             # strong burst
    t0 = 8_000_000_000
    rows = [mkrow(1, t0, 1, lb_exit, ls_exit),
            mkrow(2, t0 + 1_000_000_000, 1, lb, ls),    # +1 s: inside cooldown
            mkrow(3, t0 + 61_000_000_000, 1, lb, ls)]   # +61 s: cooldown expired
    sigs = run(rows, cfg=cfg)
    assert sigs[0]["direction"] == 0
    assert sigs[1]["direction"] == 0, "cooldown veto failed"
    assert sigs[2]["direction"] == 1, "entry should re-arm after cooldown_s"


def test_locate_veto():
    # C7: SHORT direction requires locate_ok from the consumer.
    lb, ls = z_to_lams(-3.0)  # sell burst
    row = mkrow(1, 8_000_000_000, -1, lb, ls)
    cfg_closed = dict(CFG, cost_gate_k=10.0, persist_n=1, locate_ok=False)
    cfg_open = dict(CFG, cost_gate_k=10.0, persist_n=1, locate_ok=True)
    s_closed, _ = step(init_state(), row, cfg_closed)
    s_open, _ = step(init_state(), row, cfg_open)
    assert s_closed["direction"] == 0, "SHORT without locate_ok must be vetoed"
    assert s_open["direction"] == -1, "SHORT with locate_ok should emit"


def test_halt_and_auction_paths():
    row = mkrow(1, 8_000_000_000, 1, 10.0, 7.42)
    s_halt, _ = step(init_state(), row, CFG, market_state="HALTED")
    assert s_halt["module_state"] == "UNKNOWN", "HALTED must freeze to UNKNOWN"
    s_auc, _ = step(init_state(), row, CFG, market_state="AUCTION")
    assert s_auc["module_state"] == "DEGRADED", "AUCTION must hold at DEGRADED"
    assert s_auc["direction"] == 0, "no new signals in auction"


def test_stationarity_guard_rejects_supercritical():
    bad = dict(CFG, alpha_self=2.0, beta_self=1.0)  # eig1 = 2.25 >= 1
    try:
        run([mkrow(1, 8_000_000_000, 1, 10.0, 7.42)], cfg=bad)
    except ValueError:
        pass
    else:
        raise AssertionError("supercritical config must fail closed")
    check_stationarity(CFG)  # default config is subcritical: no raise
