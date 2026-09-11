"""Acceptance tests for S080 — PCA / statistical-factor residual reversal (eigenportfolios).

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative §S3 pseudocode (fixture scope: stated-Sigma m=1 two-asset
reduction u=(A-B)/2), and asserts causality, the cost gate, OU/borrow veto
paths, boundary behavior, cooldown, exits, and fail-safe mapping.

Run: python3 -m pytest modules/tests/test_S080.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S080_tape.csv"
EXPECTED = FIX / "S080_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
DAY_NS = 86_400_000_000_000  # one daily-bar spacing, int64 ns [default]


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


# Config mirrors §S0.2 (fixture scope: stated-Sigma m=1 reduction overrides m;
# W is unused in the reduction and carried for schema fidelity).
CFG = {"m": 1, "W": 252, "c_thresh": 2.0, "z_exit": 1.0, "sigma_u": 0.72,
       "r2_crit": 0.5, "p_max": 0.25, "cooldown_s": 300.0, "cost_gate_k": 0.5}


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Callable cost model — mirrors the §S2 COST block exactly (bps)."""
    spread_bps = 0.50   # [example] bar-close crossing assumption
    fee_bps = 0.30      # [example] taker incl. regulatory
    borrow_bps = 0.0    # [default] GC assumed; reason in COST block
    impact_bps = 0.70   # [example] flagged; calibrate per venue at scale-up
    if side == "maker":
        fee_bps = -0.20  # rebate [example]; mirrors COST block maker note
    return spread_bps + fee_bps + borrow_bps + impact_bps


def init_state():
    return {"module_state": "OK", "cooldown_until": None,
            "last_ts": None, "halted": False}


def _bad(v):
    """Module feature inputs are returns (negatives legal): only None/NaN/
    non-finite are invalid (F1). The <=0 price rule applies at ingest."""
    if v is None:
        return True
    if isinstance(v, float) and (math.isnan(v) or not math.isfinite(v)):
        return True
    return False


def step(state, row, cfg, extras=None):
    """Reference implementation of the normative §S3 pseudocode, fixture scope.

    extras: {"r2_ou": float [default 1.0], "borrow_ok": bool [default True],
             "halted": bool [default False], "locate_ok": bool [default True]}
    The fixture assumes the OU fit passed and borrow was available (documented
    in §S4); tests override extras to exercise veto paths.
    """
    ex = {"r2_ou": 1.0, "borrow_ok": True, "halted": False, "locate_ok": True}
    if extras:
        ex.update(extras)
    A = row.get("A")
    B = row.get("B")
    ts = row.get("event_ts")
    sig = dict(computed_at=ts if isinstance(ts, int) else 0, direction=0,
               confidence=0.0, capital=0.0, module_state="OK",
               edge_bps=0.0, cost_bps=1.50,
               fill_event_ts=(ts + DAY_NS) if isinstance(ts, int) else 0,
               A_hat=float("nan"), u=float("nan"), z=float("nan"),
               cost_gate_ok=False, exited=False)

    # Guards, in §S3 normative order: halt/market-state, invalid input,
    # then the cooldown gate (C10) before feature math.
    if ex["halted"]:
        sig["module_state"] = "UNKNOWN"          # C6 / §S0.5
        return sig, state
    if _bad(A) or _bad(B) or not isinstance(ts, int):
        sig["module_state"] = "UNKNOWN"          # F1, never interpolate
        return sig, state

    Ahat = (A + B) / 2.0                          # stated-Sigma m=1 reduction
    u = (A - B) / 2.0
    z = u / cfg["sigma_u"]
    if not math.isfinite(z):                      # F2: math-bounds check
        sig["module_state"] = "UNKNOWN"
        return sig, state
    edge = abs(z) * 2.0                           # [example] residual edge per s unit
    sig.update(A_hat=Ahat, u=u, z=z, edge_bps=edge)

    # t->t+1 causality pin: earliest fill is open(t+1), never the signal bar.
    assert sig["fill_event_ts"] > sig["computed_at"]

    # Exit bookkeeping (stateful): |z| < z_exit closes an open position.
    if state.get("position", 0) != 0 and abs(z) < cfg["z_exit"]:
        state["position"] = 0
        state["cooldown_until"] = ts + int(cfg["cooldown_s"] * 1e9)  # C10
        sig["exited"] = True

    cost_bps = expected_cost_bps(1e6, 0.001, "XNAS", "taker", "normal")
    sig["cost_bps"] = cost_bps
    cost_ok = cost_bps <= cfg["cost_gate_k"] * edge    # executable predicate
    sig["cost_gate_ok"] = cost_ok

    in_cooldown = (state["cooldown_until"] is not None
                   and ts < state["cooldown_until"])     # C10
    ou_ok = ex["r2_ou"] >= cfg["r2_crit"]                # OU fit-quality gate
    side_ok = (z <= 0) or (ex["borrow_ok"] and ex["locate_ok"])  # C7 locate
    entry = (abs(z) > cfg["c_thresh"]) and ou_ok and ex["borrow_ok"] \
        and side_ok and cost_ok and (not in_cooldown)

    if entry:
        sig["direction"] = -1 if z > 0 else 1
        sig["confidence"] = min(1.0, abs(z) / 4.0)
        sig["capital"] = min(cfg["p_max"], sig["confidence"] * cfg["p_max"])
        state["cooldown_until"] = ts + int(cfg["cooldown_s"] * 1e9)
        state["position"] = sig["direction"]
    return sig, state


def run(rows, cfg=None, extras=None):
    cfg = cfg or CFG
    st = init_state()
    st["position"] = 0
    out = []
    for r in rows:
        sig, st = step(st, r, cfg, extras)
        sig["position"] = st["position"]
        out.append(sig)
    return out


def _close(a, b):
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
    cols = ["computed_at", "direction", "confidence", "capital", "module_state",
            "edge_bps", "cost_bps", "fill_event_ts", "A_hat", "u", "z"]
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
    big_edge = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 100.0
    tiny_edge = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"
    # maker path mirrors the COST block maker-rebate note exactly
    assert _close(expected_cost_bps(1e6, 0.01, "XNAS", "maker", "normal"), 1.0)


def test_invalid_input_unknown():
    rows = tape()
    base = dict(rows[0])
    cases = [
        {"A": float("nan"), "label": "NaN return"},
        {"A": float("inf"), "label": "+inf return"},
        {"B": float("-inf"), "label": "-inf return"},
        {"event_ts": "not-an-int", "label": "non-int timestamp"},
    ]
    for c in cases:
        bad = dict(base)
        label = c.pop("label")
        bad.update(c)
        bad.update({'ev': 11, 'event_ts': bad.get('event_ts', 1000864000000000),
                    'asof_ts': 1000864000001000})
        sig, _ = step(init_state(), bad, CFG)
        assert sig["module_state"] == "UNKNOWN", \
            f"invalid input must map to UNKNOWN, never interpolate ({label})"


def test_boundary_at_threshold():
    # Entry is strict: |z| == c_thresh is NOT a signal (boundary pin).
    row = {'ev': 11, 'event_ts': 2000086400000000, 'asof_ts': 2000086400001000}
    on = dict(row, A=1.44, B=-1.44)    # u = 1.44 -> z = 2.0 exactly
    sig, _ = step(init_state(), on, CFG)
    assert _close(sig["z"], 2.0), f"boundary setup wrong: z={sig['z']}"
    assert sig["direction"] == 0, "z == c_thresh must not enter"
    just_over = dict(row, A=1.45, B=-1.44)  # u = 1.445 -> z = 2.0069...
    sig2, _ = step(init_state(), just_over, CFG)
    assert sig2["z"] > 2.0
    assert sig2["direction"] == -1, "z > c_thresh with gate passing must enter"


def test_gate_veto_paths():
    # Same stretched row; each veto independently blocks entry.
    row = {'ev': 11, 'event_ts': 2000086400000000, 'asof_ts': 2000086400001000,
           'A': 1.8, 'B': -1.8}   # z = 2.5 > c_thresh
    sig_base, _ = step(init_state(), row, CFG)
    assert sig_base["direction"] == -1, "baseline row should enter"
    sig_r2, _ = step(init_state(), row, CFG, {"r2_ou": 0.2})
    assert sig_r2["direction"] == 0, "R2_OU below r2_crit must veto"
    sig_bor, _ = step(init_state(), row, CFG, {"borrow_ok": False})
    assert sig_bor["direction"] == 0, "borrow_ok False must veto"
    sig_loc, _ = step(init_state(), row, CFG, {"locate_ok": False})
    assert sig_loc["direction"] == 0, "missing locate must veto the short leg (C7)"
    tight = dict(CFG, cost_gate_k=0.01)  # gate ~ cost 1.5 > 0.01*5.0
    sig_cost, _ = step(init_state(), row, tight)
    assert sig_cost["direction"] == 0, "failed cost gate must veto"
    assert sig_cost["cost_gate_ok"] is False


def test_cooldown_blocks_reentry():
    # After an entry, a stretched row inside cooldown_s is suppressed (C10).
    st = init_state()
    day6 = {'ev': 6, 'event_ts': 1000432000000000, 'asof_ts': 1000432000001000,
            'A': 2.553, 'B': -0.51}          # fixture day 6: z = 2.127 -> SHORT
    sig6, st = step(st, day6, CFG)
    assert sig6["direction"] == -1
    soon = {'ev': 7, 'event_ts': 1000432000000000 + 60_000_000_000,  # +60 s
            'asof_ts': 1000432000001000 + 60_000_000_000,
            'A': 2.6, 'B': -0.5}             # z still > c_thresh
    sig7, _ = step(st, soon, CFG)
    assert sig7["direction"] == 0, "cooldown must block re-entry inside 300 s"
    assert sig7["module_state"] == "OK"


def test_halt_freeze():
    row = dict(tape()[0])
    sig, _ = step(init_state(), row, CFG, {"halted": True})
    assert sig["module_state"] == "UNKNOWN", "halted events freeze per §S0.5"
    assert sig["direction"] == 0


def test_exit_on_z_exit_crossover():
    # Stateful run: fixture day 6 opens SHORT; day 7 |z| < z_exit exits.
    sigs = run(tape())
    after6 = sigs[5]
    after7 = sigs[6]
    assert after6["position"] == -1, f"day 6 should open short, got {after6['position']}"
    assert abs(after7["z"]) < CFG["z_exit"], "day 7 z must be under z_exit"
    assert after7["position"] == 0, "z_exit crossover must flatten the position"
    assert after7["exited"] is True
    # no other day opens a position
    assert all(s["position"] == 0 for i, s in enumerate(sigs) if i not in (5, 6))
