"""Acceptance tests for S089 — Avellaneda–Stoikov inventory-skew market making.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode (v1.1.0: full half-spread
delta* = gamma*sigma^2*tau/2 + (1/gamma)*ln(1+gamma/k); k_gate is the
cost-gate multiplier, distinct from book-depth k), and asserts causality,
the cost gate, guards (staleness/halt/inventory/locate/cooldown), and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S089.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S089_tape.csv"
EXPECTED = FIX / "S089_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "r", "bid", "ask", "spread_bps",
                 "lambda_a", "lambda_b", "skew_bps", "gate_pass", "fill_event_ts"]

# Chapter S4/S0.2 parameters (synthetic, seed 89) [example]
CFG = {"gamma": 0.1, "k": 1.5, "A": 140.0, "k_gate": 0.5,
       "max_abs_q": 20, "staleness_ttl_s": 3.0, "cooldown_s": 60.0,
       "notional": 1e6, "adv_pct": 0.01, "venue": "XNAS"}


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
    # Callable cost model - S089 maker stack. Mirrors the chapter COST block exactly.
    if side != "maker":
        raise ValueError("S089 is maker-only; taker quotes are out of scope")
    spread_bps = 0.0    # [default] maker captures the spread; it is the edge, not a cost
    fee_bps = -0.25     # [example] $0.0025/share Nasdaq displayed adding-liquidity credit [documented] at $100 example price
    borrow_bps = 0.0    # [default] borrow_bps_per_day = 0.0; carry lives in the consumer's ledger
    impact_bps = 0.5    # [example] adverse-selection leakage at the example notional
    return spread_bps + fee_bps + borrow_bps + impact_bps  # = 0.25 [example]


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def _pull(ts, state, module_state):
    return {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
            "module_state": module_state, "edge_bps": 0.0,
            "cost_bps": expected_cost_bps(1e6, 0.01, "XNAS", "maker", "passive"),
            "r": float("nan"), "bid": float("nan"), "ask": float("nan"),
            "spread_bps": float("nan"), "lambda_a": float("nan"),
            "lambda_b": float("nan"), "skew_bps": 0.0, "gate_pass": 0,
            "fill_event_ts": ts + 1 if isinstance(ts, int) else None}


def init_state():
    return {"updates": 0, "pull_ts_ns": None}


def _sign(x):
    return 0 if x == 0 else (1 if x > 0 else -1)


def step(state, row, cfg):
    ts = row.get("event_ts")
    s = row.get("s")
    q = row.get("q")
    sig = row.get("sigma")
    Tt = row.get("Tt")
    # per-row overrides (empty CSV cells -> cfg defaults)
    g = cfg["gamma"] if _bad(row.get("gamma")) else row["gamma"]
    k = cfg["k"]
    A = cfg["A"]
    k_gate = cfg["k_gate"] if _bad(row.get("k_gate")) else row["k_gate"]
    max_abs_q = cfg["max_abs_q"]
    ttl_s = cfg["staleness_ttl_s"]
    cooldown_s = cfg["cooldown_s"]
    market = row.get("market_state") or "CONTINUOUS_TRADING"
    asof = row.get("asof_ts")
    asof = ts if _bad(asof) else asof
    locate_ok = row.get("locate_ok")
    locate_ok = True if _bad(locate_ok) else bool(locate_ok)

    # Guards, in normative order (F1/F4/market-state/inventory/cooldown)
    if market == "HALTED":
        return _pull(ts, state, "UNKNOWN"), state
    if market == "AUCTION":
        return _pull(ts, state, "DEGRADED"), state
    if market == "CLOSED":
        out = _pull(ts, state, "OFF")
        return out, state
    if _bad(ts) or _bad(s) or _bad(q) or _bad(sig) or _bad(Tt) or _bad(g) or _bad(k_gate):
        return _pull(ts, state, "UNKNOWN"), state
    if min(s, sig, Tt, g, k, A) <= 0:
        return _pull(ts, state, "UNKNOWN"), state
    if (asof - ts) / 1e9 > ttl_s:
        return _pull(ts, state, "UNKNOWN"), state  # F4 staleness
    if abs(q) > max_abs_q:
        state["pull_ts_ns"] = ts  # inventory breach -> pull + start cooldown
        return _pull(ts, state, "DEGRADED"), state
    if state["pull_ts_ns"] is not None and (ts - state["pull_ts_ns"]) / 1e9 < cooldown_s:
        return _pull(ts, state, "DEGRADED"), state  # C10 cooldown still active

    # Core: data <= t only
    r = s - q * g * sig ** 2 * Tt
    dstar = 0.5 * g * sig ** 2 * Tt + (1.0 / g) * math.log(1.0 + g / k)
    bid, ask = r - dstar, r + dstar
    if ask <= bid or bid <= 0 or ask <= 0:
        return _pull(ts, state, "UNKNOWN"), state  # F2 bounds
    lam_a = A * math.exp(-k * (ask - s))
    lam_b = A * math.exp(-k * (s - bid))
    edge_bps = (ask - bid) / s * 10000.0
    cost_bps = expected_cost_bps(cfg["notional"], cfg["adv_pct"], cfg["venue"],
                                 "maker", "passive")
    out = _pull(ts, state, "OK")
    out.update({"edge_bps": edge_bps, "cost_bps": cost_bps, "r": r, "bid": bid,
                "ask": ask, "spread_bps": edge_bps, "lambda_a": lam_a,
                "lambda_b": lam_b, "skew_bps": (r - s) / s * 10000.0})
    # Cost gate: executable predicate; veto -> pull quotes (C2 bona-fide intent)
    if not (cost_bps <= k_gate * edge_bps):
        out["module_state"] = "DEGRADED"  # quotes pulled; no sub-threshold hints
        out.update({"r": float("nan"), "bid": float("nan"), "ask": float("nan"),
                    "spread_bps": float("nan"), "lambda_a": float("nan"),
                    "lambda_b": float("nan"), "skew_bps": 0.0})
        return out, state  # gate_pass=0, direction 0, quotes NaN, edge kept for audit
    out["gate_pass"] = 1
    # Direction + locate check (C7)
    direction = -_sign(q)
    if direction == -1 and not locate_ok:
        out["module_state"] = "DEGRADED"  # quotes pulled; no locate -> no SHORT lean
        out.update({"r": float("nan"), "bid": float("nan"), "ask": float("nan"),
                    "spread_bps": float("nan"), "lambda_a": float("nan"),
                    "lambda_b": float("nan"), "skew_bps": 0.0})
        return out, state
    confidence = min(1.0, abs(q) * g * sig ** 2 * Tt / dstar)
    out.update({"module_state": "OK", "direction": direction,
                "confidence": confidence, "capital": 0.5 * confidence})
    # Causality: earliest fill strictly after the signal event
    assert out["fill_event_ts"] > out["computed_at"]
    state["updates"] += 1
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
    assert len(rows) >= 15, "fixture needs >=15 rows (sweep + guard paths)"


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
    # Chapter S4 hand-checks (rounded in the chapter; tolerance here is exact):
    # q=+20 -> r=99.82, bid=99.1701, ask=100.4699, lambda_a=69.19, lambda_b=40.32 [example]
    sigs = run(tape())
    q20 = sigs[4]
    assert abs(q20["r"] - 99.82) < 1e-9
    assert abs(q20["bid"] - 99.1701148) < 1e-4
    assert abs(q20["ask"] - 100.4698852) < 1e-4
    assert abs(q20["lambda_a"] - 69.19) < 0.05
    assert abs(q20["lambda_b"] - 40.32) < 0.05
    assert abs(q20["spread_bps"] - 129.977) < 0.01
    # symmetry: lambda_a(q) == lambda_b(-q)
    qneg = sigs[0]
    assert abs(qneg["lambda_a"] - q20["lambda_b"]) / q20["lambda_b"] < 1e-9
    assert abs(qneg["lambda_b"] - q20["lambda_a"]) / q20["lambda_a"] < 1e-9
    # q=0: quotes symmetric around the mid, no lean
    q0 = sigs[2]
    assert q0["direction"] == 0
    assert abs(q0["bid"] - (100.0 - 0.6498852)) < 1e-4


def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()):
        fill_event = s["fill_event_ts"]
        signal_event = s["computed_at"]
        if fill_event is not None:
            assert fill_event > signal_event


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k_gate * edge_bps
    c = expected_cost_bps(1e6, 0.01, "XNAS", "maker", "passive")
    assert abs(c - 0.25) < 1e-12, "callable must mirror the COST block (0.25 bps)"
    big_edge = c <= CFG["k_gate"] * 200.0
    tiny_edge = c <= CFG["k_gate"] * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"
    try:
        expected_cost_bps(1e6, 0.01, "XNAS", "taker", "passive")
    except ValueError:
        pass
    else:
        raise AssertionError("maker-only callable must reject side='taker'")


def test_invalid_input_unknown():
    rows = tape()
    st = init_state()
    sig, _ = step(st, dict(rows[5]), CFG)  # q = nan
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
    sig, _ = step(st, dict(rows[6]), CFG)  # s = nan
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"


def test_gate_veto_pulls_quotes():
    # row 8: k_gate=1e-4 -> 0.25 > 1e-4 * 129.98 -> gate fails -> pull (C2)
    rows = tape()
    st = init_state()
    sig, _ = step(st, dict(rows[7]), CFG)
    assert sig["module_state"] == "DEGRADED", "gate veto must pull quotes (DEGRADED)"
    assert sig["direction"] == 0, "vetoed signal must emit direction 0, never a hint"
    assert sig["gate_pass"] == 0
    assert sig["edge_bps"] > 0, "veto row records the computed edge for audit"
    assert math.isnan(sig["bid"]), "vetoed quotes are pulled (NaN), not emitted"


def test_inventory_breach_and_cooldown():
    # rows 9-11: q=21 breaches max_abs_q=20 -> DEGRADED pull; +30s still in
    # 60s cooldown -> DEGRADED; +90s cooldown expired -> OK
    rows = tape()
    st = init_state()
    sig, st = step(st, dict(rows[8]), CFG)
    assert sig["module_state"] == "DEGRADED" and sig["direction"] == 0
    assert st["pull_ts_ns"] == rows[8]["event_ts"], "breach must arm the cooldown timer"
    sig, st = step(st, dict(rows[9]), CFG)  # +30s
    assert sig["module_state"] == "DEGRADED", "cooldown must hold the pull for 60s"
    assert sig["direction"] == 0
    sig, st = step(st, dict(rows[10]), CFG)  # +90s
    assert sig["module_state"] == "OK", "quotes must resume once the cooldown expires"
    assert sig["direction"] == -1, "q=5 long book -> direction -1"


def test_boundary_max_abs_q():
    # boundary: |q| == max_abs_q is OK; |q| == max_abs_q + 1 pulls
    base = {"event_ts": 1788946200000000000, "s": 100.0, "sigma": 0.3, "Tt": 1.0}
    st = init_state()
    sig, _ = step(st, dict(base, q=20), CFG)
    assert sig["module_state"] == "OK", "q at the cap must still quote"
    st = init_state()
    sig, _ = step(st, dict(base, q=21), CFG)
    assert sig["module_state"] == "DEGRADED", "q past the cap must pull"
    st = init_state()
    sig, _ = step(st, dict(base, q=-21), CFG)
    assert sig["module_state"] == "DEGRADED", "short side breach must pull too"


def test_halt_freeze():
    # row 12: HALTED -> UNKNOWN per the market-state table
    rows = tape()
    st = init_state()
    sig, _ = step(st, dict(rows[11]), CFG)
    assert sig["module_state"] == "UNKNOWN", "halt must freeze to UNKNOWN"
    assert sig["direction"] == 0 and math.isnan(sig["bid"])


def test_staleness_unknown():
    # row 14: asof_ts - event_ts = 5s > 3s TTL -> UNKNOWN (F4)
    rows = tape()
    st = init_state()
    sig, _ = step(st, dict(rows[13]), CFG)
    assert sig["module_state"] == "UNKNOWN", "stale input must map to UNKNOWN, never interpolate"


def test_locate_veto_for_short():
    # row 15: q=10 -> direction -1 but locate_ok=0 -> direction 0, DEGRADED (C7)
    rows = tape()
    st = init_state()
    sig, _ = step(st, dict(rows[14]), CFG)
    assert sig["module_state"] == "DEGRADED"
    assert sig["direction"] == 0, "no locate -> no SHORT lean"
    assert sig["gate_pass"] == 1, "gate passed; the veto is the locate check"
    # long-book direction with locate_ok=1 (row 4) still emits -1
    st = init_state()
    sig, _ = step(st, dict(rows[3]), CFG)
    assert sig["direction"] == -1 and sig["module_state"] == "OK"
