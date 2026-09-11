"""Acceptance tests for S082 — Deep learning on the LOB (DeepLOB + classical ML features).

Template v1.0.0. Two fixture tapes:
  * S082_tape.csv          — the chapter's §S4 accuracy-sweep waterfall (5 scenarios)
  * S082_gates.csv         — gate / edge-case paths (invalid, stale, halt, auction,
                             confidence boundary, locate veto, cooldown, cost-gate veto,
                             full emit, F2 bounds, LONG without locate)

The `signal()` function below is the reference implementation of the §S3
normative pseudocode: every guard named in the module is present, the cost-gate
predicate is executable, and causality is asserted inline.

Run: python3 -m pytest modules/tests/test_S082.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S082_tape.csv"
EXPECTED = FIX / "S082_expected.csv"
GATES = FIX / "S082_gates.csv"
GATES_EXPECTED = FIX / "S082_gates_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]

# ---- §S2 COST block constants (callable mirrors the block exactly) ----
REF_PRICE_P = 100.0        # [example] bps = 10000 * pence / REF_PRICE_P
SPREAD_HALF_BPS = 5.0       # [example] half-spread 0.05 p
FEE_BPS = 0.5               # [example] fees + slippage 0.005 p
BORROW_BPS_PER_DAY = 0.0    # [default] reason: intraday hold, flat at close
IMPACT_BPS = 0.0            # [example] flagged; no queue model
MAKER_REBATE_BPS = -0.20    # [example] maker-side rebate

CFG = {
    "T_snaps": 100, "L_depth": 10, "p_conf": 0.6, "alpha_bp": 1.0,
    "p_max": 0.25, "cooldown_s": 60.0, "cost_gate_k": 0.5,
    "stale_ttl_s": 3.0, "min_fill_lag_ns": 1_000_000,
}


def expected_cost_bps(notional, adv_pct, venue, side, urgency, hold_days=0.0):
    """Callable cost model — constants identical to the §S2 COST block."""
    fee_bps = MAKER_REBATE_BPS if side == "maker" else FEE_BPS
    return SPREAD_HALF_BPS + fee_bps + BORROW_BPS_PER_DAY * hold_days + IMPACT_BPS


def _bad(v):
    return v is None or (isinstance(v, float) and (math.isnan(v) or not math.isfinite(v)))


def _mk(t, state="OK", edge_bps=0.0, nc=None, nw=None, en=None, reason=""):
    return dict(
        computed_at=t,
        direction=0, confidence=0.0, capital=0.0,
        module_state=state,
        edge_bps=edge_bps,
        cost_bps=expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal"),
        fill_event_ts=t + CFG["min_fill_lag_ns"],
        net_correct=float("nan") if nc is None else nc,
        net_wrong=float("nan") if nw is None else nw,
        exp_net=float("nan") if en is None else en,
        deploy=0,
        reason=reason,
    )


def signal(state, events, cfg):
    """Reference implementation of the §S3 normative pseudocode.

    signal(state, events, cfg) -> SignalVector. `events` newest last; the
    newest event is evaluated. Returns (signal_vector, state).
    """
    evt = events[-1]
    t = evt.get("event_ts")
    now = evt.get("asof_ts")

    # F1: invalid input or stale -> UNKNOWN, never interpolate
    raw = [evt.get(f) for f in ("acc", "mu_c", "mu_w", "spread", "fees")]
    if (not isinstance(t, int) or not isinstance(now, int)
            or (now - t) > int(cfg["stale_ttl_s"] * 1e9)
            or any(_bad(v) for v in raw)):
        return _mk(t if isinstance(t, int) else 0, "UNKNOWN", reason="invalid_or_stale"), state

    # Market-state guards (§S0.5)
    ms = evt.get("market_state") or "CONTINUOUS_TRADING"
    if ms == "HALTED":
        return _mk(t, "UNKNOWN", reason="halt_freeze"), state
    if ms == "AUCTION":
        sig = _mk(t, "DEGRADED", reason="auction_hold")
        return sig, state

    # Cost arithmetic (fixture values are pence; convert at REF_PRICE_P).
    # Computed before the entry gates so flat rows still carry hand-check values.
    acc, mu_c, mu_w, sp, fe = raw
    nc = mu_c - sp - fe
    nw = mu_w - sp - fe
    en = acc * nc + (1.0 - acc) * nw
    edge_bps = 10000.0 * max(0.0, en) / REF_PRICE_P
    cost_bps = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")

    # Cooldown guard (post-exit / post-emit)
    last_emit = evt.get("last_emit_ts") or 0
    if t - last_emit < int(cfg["cooldown_s"] * 1e9):
        sig = _mk(t, edge_bps=edge_bps, nc=nc, nw=nw, en=en, reason="cooldown")
        return sig, state

    # Classifier output bounds (F2)
    max_p = evt.get("max_p")
    if max_p is None:
        max_p = 0.0
    if (not isinstance(max_p, (int, float)) or _bad(max_p)
            or not (0.0 <= max_p <= 1.0)):
        return _mk(t, "UNKNOWN", edge_bps=edge_bps, nc=nc, nw=nw, en=en,
                   reason="max_p_bounds"), state
    cstar = evt.get("cstar") or 0

    # Confidence gate (strictly greater: boundary p_conf does NOT emit)
    if max_p <= cfg["p_conf"]:
        sig = _mk(t, edge_bps=edge_bps, nc=nc, nw=nw, en=en, reason="below_confidence")
        return sig, state

    # t -> t+1 causality: earliest fill is strictly after the signal event
    fill_ts = t + cfg["min_fill_lag_ns"]
    assert fill_ts > t, "causality: fill_event must be strictly after signal_event"

    sig = _mk(t, edge_bps=edge_bps, nc=nc, nw=nw, en=en, reason="nonpositive_edge")
    if en <= 0.0:
        return sig, state

    # Normative cost gate: expected_cost_bps(...) <= k * edge_bps
    if not (cost_bps <= cfg["cost_gate_k"] * edge_bps):
        sig["reason"] = "cost_gate_veto"
        return sig, state

    # C7 locate veto: SHORT without locate collapses to flat
    if cstar == -1 and not int(evt.get("locate_ok", 1)):
        sig["reason"] = "locate_veto"
        return sig, state

    direction = 1 if cstar >= 0 else -1
    conf = min(1.0, float(max_p))
    sig.update(
        direction=direction,
        confidence=conf,
        capital=min(cfg["p_max"], conf * cfg["p_max"]),
        deploy=1,
        reason="emit",
    )
    state["last_emit_ts"] = t
    return sig, state


def init_state():
    return {"module_state": "OK", "last_emit_ts": 0}


def run(rows):
    st = init_state()
    out = []
    for r in rows:
        sig, st = signal(st, [r], CFG)
        out.append(sig)
    return out


# ---------- fixture loading ----------

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


def tape(path=TAPE):
    rows = []
    for r in load_csv(path):
        d = {}
        for k, v in r.items():
            d[k] = _num(v)
        rows.append(d)
    return rows


def _close(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(b))
    return a == b


COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
        "edge_bps", "cost_bps", "fill_event_ts",
        "net_correct", "net_wrong", "exp_net", "deploy", "reason"]


def _assert_rows_match(rows, exp_rows, label):
    assert len(exp_rows) == len(rows), f"{label}: expected row count != tape row count"
    sigs = run(rows)
    for i, (s, e) in enumerate(zip(sigs, exp_rows)):
        assert int(e["ev"]) == int(rows[i]["ev"]), f"{label} row {i}: ev mismatch"
        for c in COLS:
            got = s[c]
            want = _num(e[c])
            assert _close(got, want), f"{label} row {i} col {c}: got {got} want {want}"


# ---------- tests ----------

def test_fixtures_exist_and_typed():
    for p in (TAPE, EXPECTED, GATES, GATES_EXPECTED):
        assert p.exists(), f"fixture missing: {p}"
        with open(p) as f:
            head = [next(f) for _ in range(3)]
        assert any(l.startswith("# TYPE:") for l in head), f"fixture missing TYPE header: {p}"


def test_tape_row_count():
    rows = tape()
    assert len(rows) == 5, "accuracy sweep needs exactly the 5 hand-checkable scenarios"


def test_gates_row_count():
    rows = tape(GATES)
    assert len(rows) == 11, "gate fixture needs exactly the 11 edge-case rows"


def test_expected_matches_reference():
    _assert_rows_match(tape(), load_csv(EXPECTED), "tape")


def test_gates_expected_matches_reference():
    _assert_rows_match(tape(GATES), load_csv(GATES_EXPECTED), "gates")


def test_hand_checks_waterfall():
    """Independent hand arithmetic for tape row 2 (acc=0.55, [example] pence units)."""
    sigs = run(tape())
    s = sigs[1]
    assert _close(s["net_correct"], 0.06 - 0.05 - 0.005)
    assert _close(s["net_wrong"], -0.06 - 0.05 - 0.005)
    assert _close(s["exp_net"], 0.55 * 0.005 + 0.45 * (-0.115))
    assert s["deploy"] == 0
    assert s["reason"] == "nonpositive_edge"


def test_hand_checks_positive_emit():
    """Independent hand arithmetic for gates row 19 (the full emit path)."""
    sigs = run(tape(GATES))
    by_ev = {int(r["ev"]): s for r, s in zip(tape(GATES), sigs)}
    s = by_ev[19]
    assert _close(s["net_correct"], 0.30 - 0.05 - 0.005)          # 0.245
    assert _close(s["net_wrong"], -0.06 - 0.05 - 0.005)           # -0.115
    assert _close(s["exp_net"], 0.8 * 0.245 + 0.2 * (-0.115))     # 0.173
    assert _close(s["edge_bps"], 17.3)
    assert s["deploy"] == 1
    assert s["direction"] == 1
    assert _close(s["confidence"], 0.7)
    assert _close(s["capital"], 0.175)                            # min(0.25, 0.7*0.25)
    assert s["reason"] == "emit"
    assert s["module_state"] == "OK"


def test_signal_vector_valid():
    for s in run(tape()) + run(tape(GATES)):
        assert s["direction"] in (+1, -1, 0), "direction not in {+1,-1,0}"
        assert 0.0 <= s["confidence"] <= 1.0, "confidence out of [0,1]"
        assert 0.0 <= s["capital"] <= CFG["p_max"], "capital above p_max"
        assert s["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()) + run(tape(GATES)):
        assert s["fill_event_ts"] > s["computed_at"], "fill must be strictly after signal"


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps
    k = CFG["cost_gate_k"]
    assert expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 100.0
    assert not (expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal") <= k * 0.01)


def test_cost_callable_mirrors_block():
    # the callable must equal the §S2 4-component stack exactly
    expect = SPREAD_HALF_BPS + FEE_BPS + BORROW_BPS_PER_DAY * 3.0 + IMPACT_BPS
    assert _close(expected_cost_bps(1e6, 0.01, "LSE", "taker", "normal", hold_days=3.0), expect)
    # borrow is 0 with the intraday-hold reason, so hold_days does not move it
    assert _close(expected_cost_bps(1e6, 0.01, "LSE", "taker", "normal"), 5.5)
    # maker side earns the rebate [example]
    assert _close(expected_cost_bps(1e6, 0.01, "LSE", "maker", "normal"), 5.0 - 0.20)


def test_invalid_input_unknown():
    by_ev = {int(r["ev"]): s for r, s in zip(tape(GATES), run(tape(GATES)))}
    s = by_ev[11]  # acc missing (NaN-equivalent)
    assert s["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
    assert s["direction"] == 0 and s["capital"] == 0.0 and s["deploy"] == 0
    assert s["reason"] == "invalid_or_stale"


def test_stale_input_unknown():
    by_ev = {int(r["ev"]): s for r, s in zip(tape(GATES), run(tape(GATES)))}
    s = by_ev[12]  # asof_ts - event_ts = 5 s > TTL 3 s
    assert s["module_state"] == "UNKNOWN"
    assert s["reason"] == "invalid_or_stale"


def test_halted_unknown():
    by_ev = {int(r["ev"]): s for r, s in zip(tape(GATES), run(tape(GATES)))}
    s = by_ev[13]  # market_state=HALTED
    assert s["module_state"] == "UNKNOWN"
    assert s["reason"] == "halt_freeze"
    assert s["direction"] == 0


def test_auction_degraded_hold():
    by_ev = {int(r["ev"]): s for r, s in zip(tape(GATES), run(tape(GATES)))}
    s = by_ev[14]  # market_state=AUCTION
    assert s["module_state"] == "DEGRADED"
    assert s["direction"] == 0 and s["deploy"] == 0
    assert s["reason"] == "auction_hold"


def test_confidence_boundary_no_emit():
    by_ev = {int(r["ev"]): s for r, s in zip(tape(GATES), run(tape(GATES)))}
    s = by_ev[15]  # max_p == p_conf exactly, with a genuinely positive edge
    assert s["exp_net"] > 0, "boundary row must carry a positive edge"
    assert s["deploy"] == 0, "max_p == p_conf must NOT emit (strict > required)"
    assert s["reason"] == "below_confidence"
    assert s["direction"] == 0 and s["module_state"] == "OK"


def test_locate_veto_short():
    by_ev = {int(r["ev"]): s for r, s in zip(tape(GATES), run(tape(GATES)))}
    s = by_ev[16]  # SHORT without locate_ok
    assert s["deploy"] == 0
    assert s["reason"] == "locate_veto"
    assert s["direction"] == 0 and s["module_state"] == "OK"


def test_long_needs_no_locate():
    by_ev = {int(r["ev"]): s for r, s in zip(tape(GATES), run(tape(GATES)))}
    s = by_ev[21]  # LONG with locate_ok=0
    assert s["deploy"] == 1, "locate veto applies to SHORT only"
    assert s["direction"] == 1


def test_cooldown_blocks_reentry():
    by_ev = {int(r["ev"]): s for r, s in zip(tape(GATES), run(tape(GATES)))}
    s = by_ev[17]  # last_emit_ts 30 s ago < cooldown 60 s
    assert s["deploy"] == 0
    assert s["reason"] == "cooldown"
    assert s["module_state"] == "OK"


def test_cost_gate_veto():
    by_ev = {int(r["ev"]): s for r, s in zip(tape(GATES), run(tape(GATES)))}
    s = by_ev[18]  # exp_net=0.011 p > 0 but 5.5 bps > 0.5 * 1.1 bps
    assert s["exp_net"] > 0, "veto row must carry a positive (but sub-cost) edge"
    assert s["deploy"] == 0
    assert s["reason"] == "cost_gate_veto"
    assert s["module_state"] == "OK"


def test_max_p_bounds_unknown():
    by_ev = {int(r["ev"]): s for r, s in zip(tape(GATES), run(tape(GATES)))}
    s = by_ev[20]  # max_p=1.2 out of [0,1]
    assert s["module_state"] == "UNKNOWN", "out-of-bounds classifier output is F2"
    assert s["reason"] == "max_p_bounds"
    assert s["direction"] == 0
