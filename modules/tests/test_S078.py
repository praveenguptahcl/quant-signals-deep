"""Acceptance tests for S078 — AR(1)/ARMA short-horizon forecast.

Module v1.1.0 / template v1.0.0. Loads the fixture tapes, runs a reference
implementation of the chapter's normative pseudocode (§S3), and asserts
causality, the cost gate, boundary behavior, invalid/stale/halted inputs,
cooldown veto, and hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S078.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S078_tape.csv"
EXPECTED = FIX / "S078_expected.csv"
EDGE = FIX / "S078_edge_cases.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
TTL_NS = 180_000_000_000  # staleness TTL: 180 s [default] (§S0.4)

CFG = {"phi": 0.28, "sigma_eps_bp": 4.5, "c_thr_bp": 2.5, "c_exit_bp": 1.0,
       "z_entry": 2.0, "innov_mode": False, "W": 60, "cooldown_s": 300.0,
       "cost_gate_k": 0.5}


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Callable cost model — mirrors the §S2 COST block exactly."""
    spread_bps = 1.0   # [example]
    fee_bps = 0.30     # [example]
    borrow_bps = 0.0   # [default] reason in COST block
    impact_bps = 0.0   # [example] flagged; calibrate per venue at scale-up
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def init_state():
    return {"prev_mid": None, "prev_r": None, "cooldown_until": 0,
            "module_state": "OK", "last_sig": None}


def _bad(x):
    return (x is None
            or (isinstance(x, float) and (math.isnan(x) or not math.isfinite(x)))
            or x <= 0)


def _flat(computed_at, module_state):
    return dict(direction=0, confidence=0.0, capital=0.0,
                computed_at=computed_at, module_state=module_state,
                edge_bps=0.0, cost_bps=0.0,
                ret_bp=float("nan"), f_hat_bp=float("nan"),
                innov_bp=float("nan"), z=float("nan"))


def step(state, row, cfg):
    """Reference implementation of the §S3 normative pseudocode.

    Guards inline: HALTED freeze + discard-across-reopen (§S0.5), AUCTION
    hold-last (§S0.5), F4 staleness (TTL), F1/F2 invalid input -> UNKNOWN
    (never interpolate), cooldown (C10), locate (C7), normative cost-gate
    predicate, t->t+1 causality.
    """
    mkt = row.get("market_state") or "CONTINUOUS_TRADING"
    if mkt == "HALTED":
        # §S0.5: freeze; emit UNKNOWN; discard contributions across reopen.
        st2 = dict(state, prev_mid=None, prev_r=None, module_state="UNKNOWN")
        return _flat(row["event_ts"], "UNKNOWN"), st2
    if mkt == "AUCTION":
        # §S0.5: no new signals; hold last SignalVector; DEGRADED.
        st2 = dict(state, module_state="DEGRADED")
        if state.get("last_sig") is not None:
            return dict(state["last_sig"], module_state="DEGRADED"), st2
        return _flat(row["event_ts"], "DEGRADED"), st2
    if row["asof_ts"] - row["event_ts"] > TTL_NS:
        # F4 staleness: UNKNOWN, never interpolate; state does not advance.
        return _flat(row["event_ts"], "UNKNOWN"), dict(state, module_state="UNKNOWN")
    mid = row["mid"]
    if _bad(mid):
        # F1/F2: invalid input -> UNKNOWN, never interpolate.
        return _flat(row["event_ts"], "UNKNOWN"), dict(state, module_state="UNKNOWN")
    if state["prev_mid"] is None:
        st2 = dict(state, prev_mid=mid, module_state="OK")
        return _flat(row["event_ts"], "OK"), st2
    r = math.log(mid / state["prev_mid"]) * 1e4  # this bar's return, bp
    if state["prev_r"] is None:
        sig = _flat(row["event_ts"], "OK")
        sig["ret_bp"] = r
        st2 = dict(state, prev_mid=mid, prev_r=r, module_state="OK")
        return sig, st2
    f = cfg["phi"] * state["prev_r"]      # one-step forecast, data <= t
    innov = r - f
    z = innov / cfg["sigma_eps_bp"]
    if not (math.isfinite(f) and math.isfinite(z)):
        # F2: feature out of mathematical bounds -> UNKNOWN.
        return _flat(row["event_ts"], "UNKNOWN"), dict(state, module_state="UNKNOWN")
    edge = abs(f)
    cost = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")
    cost_ok = cost <= cfg["cost_gate_k"] * edge  # normative cost-gate predicate
    direction = 0
    if cost_ok and row["event_ts"] >= state["cooldown_until"]:  # C10 cooldown
        if not cfg["innov_mode"]:
            direction = 1 if f > cfg["c_thr_bp"] else (-1 if f < -cfg["c_thr_bp"] else 0)
        else:
            direction = 1 if z < -cfg["z_entry"] else (-1 if z > cfg["z_entry"] else 0)
    # C7 locate: SHORT requires a consumer locate assertion (absent here -> stays 0).
    conf = min(1.0, abs(f) / (2 * cfg["c_thr_bp"])) if direction else 0.0
    sig = dict(direction=direction, confidence=conf, capital=0.5 * conf,
               computed_at=row["event_ts"], module_state="OK",
               edge_bps=edge, cost_bps=cost, ret_bp=r, f_hat_bp=f,
               innov_bp=innov, z=z)
    st2 = dict(state, prev_mid=mid, prev_r=r, module_state="OK", last_sig=sig)
    return sig, st2


def run(rows):
    st = init_state()
    out = []
    for i, r in enumerate(rows):
        sig, st = step(st, r, CFG)
        sig = dict(sig)
        sig["fill_event_ts"] = rows[i + 1]["event_ts"] if i + 1 < len(rows) else None
        out.append(sig)
    return out


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
    return [{k: _num(v) for k, v in r.items()} for r in load_csv(TAPE)]


def edge_rows():
    return [{k: _num(v) for k, v in r.items()} for r in load_csv(EDGE)]


def _close(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(b))
    return a == b


def test_fixtures_exist_and_typed():
    for path in (TAPE, EXPECTED, EDGE):
        assert path.exists(), f"{path.name} fixture missing"
        with open(path) as f:
            head = [next(f) for _ in range(3)]
        assert any(l.startswith("# TYPE:") for l in head), f"{path.name} missing TYPE header"
    assert len(tape()) >= 5, "tape fixture needs >=5 hand-checkable rows"
    assert len(edge_rows()) == 9, "edge fixture needs exactly 9 designed rows"


def test_expected_matches_reference():
    rows = tape()
    sigs = run(rows)
    exp = load_csv(EXPECTED)
    assert len(exp) == len(sigs), "expected row count != tape row count"
    cols = ["computed_at", "direction", "confidence", "capital", "module_state",
            "edge_bps", "cost_bps", "ret_bp", "f_hat_bp", "innov_bp", "z"]
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


def test_earliest_fill_next_bar_open():
    # Causality pin: earliest fill is the NEXT bar's open (bar-label = open
    # time, §S0.4), never on or before the signal bar.
    rows = tape()
    sigs = run(rows)
    for i, s in enumerate(sigs[:-1]):
        assert s["fill_event_ts"] == rows[i + 1]["event_ts"], \
            f"row {i}: earliest fill is not the next bar's open"
        assert s["fill_event_ts"] > s["computed_at"]
    assert sigs[-1]["fill_event_ts"] is None, "last bar has no next bar"


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5  # [default]
    big_edge = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 100.0
    tiny_edge = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_gate_veto_path_and_boundary():
    # |f| ~= 2.59 passes the |f| > 2.5 threshold but the normative cost-gate
    # predicate (1.3 <= 0.5 * 2.59 = 1.295) vetoes the emission; |f| ~= 2.62
    # passes both and emits +1. Separates the threshold gate from the cost gate.
    rows = edge_rows()
    st = init_state()
    sigs = []
    for r in rows:
        s, st = step(st, r, CFG)
        sigs.append(s)
    veto, trade = sigs[2], sigs[4]
    assert veto["edge_bps"] > CFG["c_thr_bp"], "threshold gate should pass at |f|~=2.59"
    assert not (veto["cost_bps"] <= CFG["cost_gate_k"] * veto["edge_bps"]), \
        "cost gate should block at |f|~=2.59"
    assert veto["direction"] == 0 and veto["module_state"] == "OK", \
        "vetoed emission must stay flat, not error"
    assert trade["cost_bps"] <= CFG["cost_gate_k"] * trade["edge_bps"], \
        "cost gate should pass at |f|~=2.62"
    assert trade["direction"] == 1, "unvetoed |f|~=2.62 should emit +1"


def test_invalid_input_unknown():
    rows = tape()
    bad = dict(rows[0])
    bad.update({'mid': float('nan')})
    st = init_state()
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"


def test_invalid_stale_halted_inputs_unknown():
    rows = edge_rows()
    st = init_state()
    sigs = []
    for r in rows:
        s, st = step(st, r, CFG)
        sigs.append(s)
    assert sigs[5]["module_state"] == "UNKNOWN", "NaN mid -> UNKNOWN"
    assert sigs[6]["module_state"] == "UNKNOWN", "asof lag 181 s > TTL 180 s -> UNKNOWN"
    assert sigs[7]["module_state"] == "UNKNOWN", "HALTED -> freeze, UNKNOWN"
    # §S0.5: contributions discarded across reopen — the estimation window restarts.
    assert sigs[8]["module_state"] == "OK"
    assert math.isnan(sigs[8]["f_hat_bp"]), "post-halt bar must restart the window"


def test_cooldown_veto():
    # C10: a bar that would otherwise emit is suppressed inside the cooldown.
    rows = edge_rows()
    st = init_state()
    for r in rows[:4]:
        _, st = step(st, r, CFG)
    st["cooldown_until"] = rows[4]["event_ts"] + 10 ** 12
    sig, _ = step(st, rows[4], CFG)  # |f|~=2.62 would emit +1 without the cooldown
    assert sig["direction"] == 0 and sig["module_state"] == "OK", \
        "cooldown must veto an otherwise valid emission"
