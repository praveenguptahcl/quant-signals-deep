"""Acceptance tests for S079 — HMM regime switching.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode (§S3), and asserts causality, the cost gate,
boundary conditions, invalid-input handling, and hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S079.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S079_tape.csv"
EXPECTED = FIX / "S079_expected.csv"
GATES = FIX / "S079_gates.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
STALENESS_TTL_S = 900.0  # [default] §S0.4 (3x the 5-min bar cadence per F4)


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
# Reference implementation of the §S3 normative pseudocode (v1.1.0).
# Mirrors the module exactly: guards inline, all variables bound.
# ---------------------------------------------------------------------------
CFG = {"A": [[0.97, 0.03], [0.08, 0.92]], "mu": [3.0, -5.0], "sigma": [40.0, 120.0],
       "p_halve": 0.7, "p_suspend": 0.8, "cooldown_s": 300.0, "cost_gate_k": 0.5,
       "ref_notional_usd": 1e6, "ref_adv_pct": 0.01, "venue": "XNAS",
       "side": "taker", "locate_asserted": True}


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    # Mirrors the §S2 COST block exactly (v1.1.0):
    # 1.00 spread [example] + 0.30 venue taker [documented]
    # + 2.06 SEC Section 31 [documented] + 0.0 borrow [default]
    # + 0.0 impact [example] = 3.36 bps.
    spread_bps = 1.00
    venue_fee_bps = 0.30
    sec_fee_bps = 2.06
    borrow_bps = 0.0
    impact_bps = 0.0
    fee_bps = venue_fee_bps + sec_fee_bps
    if side == "maker":
        fee_bps = -0.30 + sec_fee_bps  # maker credit ~$0.0030/share [documented]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _g(x, mu, sig):
    return math.exp(-0.5 * ((x - mu) / sig) ** 2) / (sig * math.sqrt(2 * math.pi))


def init_state():
    return {"alpha": [0.7273, 0.2727], "cooldown_until": 0, "module_state": "OK"}  # stationary [example]


def _unknown(row, state, reason):
    sig = dict(direction=0, confidence=0.0, capital=0.0,
               computed_at=row.get("event_ts"), module_state="UNKNOWN",
               edge_bps=0.0, cost_bps=0.0, p_vol=float("nan"),
               gate="UNKNOWN", veto_reason=reason)
    return sig, dict(state, module_state="UNKNOWN")


def decide_gate(p_vol, cost_ok, in_cooldown, locate_ok, cfg):
    """Pure gate mapping per the §S2 Boolean rules. Mirrors §S3 pseudocode."""
    if p_vol < cfg["p_halve"]:
        gate, direction = "FULL", 1
    elif p_vol < cfg["p_suspend"]:
        gate, direction = "HALVE", 0
    else:
        gate, direction = "SUSPEND", -1
    if not cost_ok:
        gate += "|COST"
        direction = 0
    if in_cooldown:
        gate += "|COOLDOWN"
        direction = 0
    if direction == -1 and not locate_ok:
        gate += "|LOCATE"  # C7: no SHORT without locate
        direction = 0
    return gate, direction


def step(state, row, cfg, edge_bps=2.0):
    """One normative §S3 iteration on a single bar row."""
    if row.get("halted"):
        return _unknown(row, state, "C6: halted")  # §S0.5 market-state table
    ev_ts = row.get("event_ts")
    asof_ts = row.get("asof_ts")
    if ev_ts is not None and asof_ts is not None:
        if (asof_ts - ev_ts) / 1e9 > STALENESS_TTL_S:
            return _unknown(row, state, "F4: stale input")  # staleness guard
    r = row.get("ret_bp")
    if r is None or (isinstance(r, float) and (math.isnan(r) or not math.isfinite(r))):
        return _unknown(row, state, "F1/F2: non-finite ret_bp")  # never interpolate
    if not (cfg["sigma"][0] > 0 and cfg["sigma"][1] > 0):
        return _unknown(row, state, "F2: sigma out of bounds")
    # forward filter ONLY — the smoother is banned in live code (C11)
    pred = [sum(state["alpha"][i] * cfg["A"][i][j] for i in (0, 1)) for j in (0, 1)]
    like = [_g(r, cfg["mu"][j], cfg["sigma"][j]) for j in (0, 1)]
    num = [pred[j] * like[j] for j in (0, 1)]
    tot = sum(num)
    if not (tot > 0 and all(math.isfinite(v) for v in num)):
        return _unknown(row, state, "F2: degenerate filter")
    alpha = [num[0] / tot, num[1] / tot]
    p_vol = alpha[1]
    # normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
    cost = expected_cost_bps(cfg["ref_notional_usd"], cfg["ref_adv_pct"],
                             cfg["venue"], cfg["side"], "normal")
    cost_ok = cost <= cfg["cost_gate_k"] * edge_bps
    in_cooldown = ev_ts is not None and ev_ts < state["cooldown_until"]
    gate, direction = decide_gate(p_vol, cost_ok, in_cooldown,
                                  cfg.get("locate_asserted", True), cfg)
    conf = abs(p_vol - 0.5) * 2  # [example]
    sig = dict(direction=direction, confidence=conf, capital=0.5 * conf,
               computed_at=ev_ts, module_state="OK",
               edge_bps=edge_bps, cost_bps=cost, p_vol=p_vol, gate=gate,
               veto_reason=None)
    return sig, {"alpha": alpha, "cooldown_until": state["cooldown_until"],
                 "module_state": "OK"}


def step_events(state, events, cfg, edge_bps=2.0):
    """Event-list entry point; empty events -> UNKNOWN (F1)."""
    if not events:
        return _unknown({}, state, "F1: empty events")
    return step(state, events[-1], cfg, edge_bps)


def run(rows, cfg=None, edge_bps=2.0):
    st = init_state()
    out = []
    cfg = cfg or CFG
    for i, r in enumerate(rows):
        sig, st = step(st, r, cfg, edge_bps)
        sig = dict(sig)
        sig["fill_event_ts"] = rows[i + 1]["event_ts"] if i + 1 < len(rows) else None
        out.append(sig)
    return out


def _close(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(b))
    return a == b


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_fixtures_exist_and_typed():
    for path, name in ((TAPE, "tape"), (EXPECTED, "expected"), (GATES, "gates")):
        assert path.exists(), f"{name} fixture missing"
        with open(path) as f:
            head = [next(f) for _ in range(3)]
        assert any(l.startswith("# TYPE:") for l in head), f"{name} missing TYPE header"
    assert len(tape()) >= 5, "tape fixture needs >=5 hand-checkable rows"
    assert len(load_csv(GATES)) >= 10, "gates fixture needs >=10 boundary rows"


def test_expected_matches_reference():
    rows = tape()
    sigs = run(rows)
    exp = load_csv(EXPECTED)
    assert len(exp) == len(sigs), "expected row count != tape row count"
    cols = ["computed_at", "direction", "confidence", "capital", "module_state",
            "edge_bps", "cost_bps", "p_vol", "gate"]
    for i, (s, e) in enumerate(zip(sigs, exp)):
        assert int(e["ev"]) == int(rows[i]["ev"]), f"row {i} ev mismatch"
        for c in cols:
            got, want = s[c], _num(e[c])
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
        fill_event, signal_event = s["fill_event_ts"], s["computed_at"]
        if fill_event is not None:
            assert fill_event > signal_event  # assert fill_event > signal_event


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps ; k = 0.5 [default]
    k = 0.5
    cost = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")
    assert abs(cost - 3.36) <= 1e-9, "callable must mirror the COST block exactly"
    assert cost <= k * 100.0, "cost gate should pass on a large edge"
    assert not (cost <= k * 0.01), "cost gate should block on a tiny edge"
    assert not (cost <= k * 2.0), "demo edge 2.0 bps [example] is vetoed: 3.36 > 1.0"


def test_invalid_input_unknown():
    rows = tape()
    st = init_state()
    for bad_val, label in ((float("nan"), "NaN"), (float("inf"), "+inf"),
                           (float("-inf"), "-inf"), (None, "missing")):
        bad = dict(rows[0])
        if bad_val is None:
            del bad["ret_bp"]
        else:
            bad["ret_bp"] = bad_val
        sig, _ = step(st, bad, CFG)
        assert sig["module_state"] == "UNKNOWN", f"{label} must map to UNKNOWN, never interpolate"


def test_empty_events_unknown():
    sig, _ = step_events(init_state(), [], CFG)
    assert sig["module_state"] == "UNKNOWN", "empty events must map to UNKNOWN (F1)"


def test_staleness_unknown():
    rows = tape()
    stale = dict(rows[0])
    stale["asof_ts"] = stale["event_ts"] + int(1000 * 1e9)  # 1000 s > 900 s TTL [default]
    sig, _ = step(init_state(), stale, CFG)
    assert sig["module_state"] == "UNKNOWN", "stale input must map to UNKNOWN (F4)"


def test_halt_unknown():
    rows = tape()
    halted = dict(rows[0])
    halted["halted"] = 1
    sig, _ = step(init_state(), halted, CFG)
    assert sig["module_state"] == "UNKNOWN", "halted bar must map to UNKNOWN (C6/§S0.5)"


def test_gate_boundaries():
    # Decision-table fixture pins every §S2 Boolean boundary incl. veto suffixes.
    for i, row in enumerate(load_csv(GATES)):
        gate, direction = decide_gate(float(row["p_vol"]),
                                      row["cost_ok"] == "1",
                                      row["in_cooldown"] == "1",
                                      row["locate_ok"] == "1", CFG)
        assert gate == row["gate"], f"gates row {i}: gate {gate} != {row['gate']}"
        assert direction == int(row["direction"]), \
            f"gates row {i}: direction {direction} != {row['direction']}"


def test_gate_veto_path():
    # With the demo edge (2.0 bps [example]) the cost gate fails everywhere:
    # every row is cost-vetoed (direction forced 0), none tradeable.
    for s in run(tape()):
        assert s["gate"].endswith("|COST"), f"veto suffix missing: {s['gate']}"
        assert s["direction"] == 0, "cost-vetoed row must emit direction 0"
        assert s["cost_bps"] > CFG["cost_gate_k"] * s["edge_bps"]


def test_gate_pass_path():
    # Large edge (100 bps [example]) opens the gate: regime decides direction.
    sigs = run(tape(), edge_bps=100.0)
    calm = [s for s in sigs if s["p_vol"] < 0.7]
    vol = [s for s in sigs if s["p_vol"] >= 0.8]
    assert calm, "fixture must contain calm bars"
    assert vol, "fixture must contain volatile bars"
    for s in calm:
        assert (s["gate"], s["direction"]) == ("FULL", 1), f"calm bar: {s['gate']}"
    for s in vol:
        assert (s["gate"], s["direction"]) == ("SUSPEND", -1), f"vol bar: {s['gate']}"


def test_cooldown_veto():
    rows = tape()
    st = init_state()
    st["cooldown_until"] = rows[2]["event_ts"] + 10_000_000_000  # inside cooldown
    sig, _ = step(st, rows[2], CFG, edge_bps=100.0)  # edge open so only cooldown bites
    assert sig["direction"] == 0, "cooldown must force direction 0 (C10)"
    assert sig["gate"].endswith("|COOLDOWN"), f"cooldown suffix missing: {sig['gate']}"


def test_sigma_relabel_invariant():
    # §S10 failure 2: relabel by estimated sigma ascending after every fit.
    assert CFG["sigma"][0] <= CFG["sigma"][1], "sigma[0] <= sigma[1] (calm first)"
    assert CFG["mu"][0] > CFG["mu"][1], "mu ordering consistent with calm/vol labels"
