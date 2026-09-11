"""Acceptance tests for S086 — Meta-labeling (v1.1.0).

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic.

The reference `step()` covers the normative subset enforceable on the fixture:
fail-closed guards (invalid input -> UNKNOWN; HALTED -> UNKNOWN; AUCTION ->
DEGRADED), the strict tau gate, the executable cost-gate predicate
`expected_cost_bps(...) <= k * edge_bps`, and t->t+1 causality. Staleness
(requires the ingest clock), locate (requires broker locate state), and
cooldown (requires session state) are integration-level guards owned by the
harness per §S0.7, not by this unit.

Run: python3 -m pytest modules/tests/test_S086.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

import pytest

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S086_tape.csv"
EXPECTED = FIX / "S086_expected.csv"

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
        d = {}
        for k, v in r.items():
            d[k] = _num(v)
        rows.append(d)
    return rows


CFG = {"tau": 0.55, "win_net": 16.0, "loss_net": -16.0,
       "cost_gate_k": 0.5}  # chapter starting points [example]; see §S2 calibration recipe
WIN_NET_REF_BPS = 16.0  # [example] win_net at the $10k reference notional, in bps


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    # Mirrors the §S2 COST block exactly: 1.0 + 0.5 + 0.0 + 0.5 = 2.0 bps. [example]
    return 2.0


def init_state():
    return {"cum": 0.0, "wins": 0, "n": 0, "tw": 0, "tn": 0}


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def step(state, row, cfg):
    ts = row.get("event_ts"); s = row.get("side"); p = row.get("p_hat"); b = row.get("barrier")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0, "cost_bps": expected_cost_bps(1e4, 0.0001, "XNAS", "taker", "normal"),
           "p_hat": float("nan"), "decision": 0, "pnl": 0.0, "cum_pnl": state["cum"],
           "raw_precision": float("nan"), "filt_precision": float("nan"),
           "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # market-state guards (§S0.5)
    ms = row.get("market_state", "CONTINUOUS_TRADING")
    if ms == "HALTED":
        return out, state  # freeze; contributions across reopen discarded
    if ms == "AUCTION":
        out["module_state"] = "DEGRADED"  # no new signals; hold last
        return out, state
    # fail-closed input guards (F1/F2): invalid input -> UNKNOWN, never interpolate
    if ts is None or s not in (1, -1) or _bad(p) or b not in ("win", "loss"):
        return out, state
    out["module_state"] = "OK"; out["p_hat"] = p
    # gates: strict tau gate AND executable cost-gate predicate
    take_raw = 1 if p > cfg["tau"] else 0
    edge_bps = (2.0 * p - 1.0) * WIN_NET_REF_BPS  # E[net $/bet] at $10k = bps [example]
    gate_pass = out["cost_bps"] <= cfg["cost_gate_k"] * edge_bps
    take = 1 if (take_raw and gate_pass) else 0
    out["decision"] = take
    pnl = (cfg["win_net"] if b == "win" else cfg["loss_net"]) * take
    state["cum"] += pnl
    out["pnl"] = pnl; out["cum_pnl"] = state["cum"]
    out["direction"] = s * take
    out["confidence"] = p
    out["capital"] = min(0.5, p - cfg["tau"]) if take else 0.0
    out["edge_bps"] = edge_bps * take
    state["n"] += 1; state["wins"] += 1 if b == "win" else 0
    state["tn"] += take; state["tw"] += take * (1 if b == "win" else 0)
    return out, state


def run(rows):
    st = init_state(); out = []
    for r in rows:
        sig, st = step(st, r, CFG)
        out.append(sig)
    rp = st["wins"] / st["n"] if st["n"] else float("nan")
    fp = st["tw"] / st["tn"] if st["tn"] else float("nan")
    for sig in out:
        if sig["module_state"] == "OK":
            sig["raw_precision"] = rp; sig["filt_precision"] = fp
    return out


def _close(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(b))
    return a == b


def _mkrow(**kw):
    row = {"ev": 0, "event_ts": 1788946200000000000, "side": 1,
           "rvol_z": 0.0, "sprd_z": 0.0, "barrier": "win", "p_hat": 0.9}
    row.update(kw)
    return row


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
    cols = ["computed_at", "direction", "confidence", "capital", "module_state", "edge_bps", "cost_bps", "p_hat", "decision", "pnl", "cum_pnl", "raw_precision", "filt_precision"]
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


def test_causality_pin():
    # the module's causal invariant, pinned both directions
    def invariant(fill_event, signal_event):
        assert fill_event > signal_event, "no signal-bar fills"
    for s in run(tape()):
        invariant(s["fill_event_ts"], s["computed_at"])
    with pytest.raises(AssertionError):
        invariant(100, 100)   # a fill on its own signal bar must fail the invariant
    with pytest.raises(AssertionError):
        invariant(99, 100)    # a fill before its signal bar must fail the invariant


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps
    k = CFG["cost_gate_k"]  # 0.5 [default]
    c = expected_cost_bps(1e4, 0.0001, "XNAS", "taker", "normal")
    assert c == 2.0, "callable must mirror the §S2 COST block exactly (2.0 bps)"
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_tau_boundary():
    # strict inequality: p_hat == tau -> SKIP; just below -> SKIP
    st = init_state()
    sig, _ = step(st, _mkrow(p_hat=CFG["tau"]), CFG)
    assert sig["decision"] == 0 and sig["direction"] == 0, "p_hat == tau must SKIP"
    st = init_state()
    sig, _ = step(st, _mkrow(p_hat=CFG["tau"] - 1e-9), CFG)
    assert sig["decision"] == 0 and sig["direction"] == 0, "p_hat just below tau must SKIP"


def test_cost_gate_veto_path():
    # clears tau (0.56 > 0.55) but fails the gate: edge=1.92 bps, k*edge=0.96 < 2.0 cost
    st = init_state()
    sig, _ = step(st, _mkrow(p_hat=0.56), CFG)
    assert sig["module_state"] == "OK", "gate veto is a clean skip, not an error"
    assert sig["decision"] == 0 and sig["direction"] == 0, "gate must veto the bet"
    assert sig["capital"] == 0.0 and sig["pnl"] == 0.0, "vetoed bet carries no capital or pnl"
    # and a bet clearing both gates is taken
    st = init_state()
    sig, _ = step(st, _mkrow(p_hat=0.70), CFG)
    assert sig["decision"] == 1 and sig["direction"] == 1, "bet clearing both gates must be taken"


def test_invalid_inputs_unknown():
    bad_rows = [
        _mkrow(p_hat=float("nan")),          # NaN probability
        _mkrow(side=0),                       # side outside {-1,+1}
        _mkrow(side="x"),                    # non-numeric side
        _mkrow(side=None),                   # missing side
        _mkrow(barrier="bogus"),             # unknown barrier outcome
        _mkrow(event_ts=None),               # missing timestamp
        {},                                  # empty event
    ]
    for row in bad_rows:
        st = init_state()
        sig, _ = step(st, row, CFG)
        assert sig["module_state"] == "UNKNOWN", f"invalid input must map to UNKNOWN: {row}"
        assert sig["direction"] == 0 and sig["capital"] == 0.0, "UNKNOWN emits no position"


def test_halt_and_auction():
    st = init_state()
    sig, _ = step(st, _mkrow(market_state="HALTED"), CFG)
    assert sig["module_state"] == "UNKNOWN", "HALTED must freeze to UNKNOWN"
    assert sig["direction"] == 0
    st = init_state()
    sig, _ = step(st, _mkrow(market_state="AUCTION"), CFG)
    assert sig["module_state"] == "DEGRADED", "AUCTION must hold last at DEGRADED"
    assert sig["direction"] == 0
