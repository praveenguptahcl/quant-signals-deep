"""Acceptance tests for S087 — Fractional differentiation (memory-retaining stationarization).

Template v1.0.0 (module v1.1.0). Loads the fixture tape, runs a reference
implementation of the chapter's normative pseudocode (§S3), and asserts
causality, the cost gate, the ADF veto path, staleness handling, boundary
conditions, and hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S087.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S087_tape.csv"
EXPECTED = FIX / "S087_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]

CFG = {
    "d": 0.4,                    # [example] fit-time d* in production
    "L": 5,                      # [example] fixed-width fixture mode
    "tau": 1e-3,                 # [example] fixture/hand-check tolerance
    "adf_p": 0.0267,             # [example] ADF p-value of the fitted d* (< 0.05 gate)
    "cadence_ns": 86_400_000_000_000,  # daily bars [example]
    "ttl_mult": 3,               # [default] staleness TTL = 3 x cadence (F4)
    "k": 0.5,                    # [default] cost-gate k
    "cooldown_s": 0,             # [default] no active cooldown in the fixture
}


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


def _weights(d, tau=1e-3, L=None):
    # §S3 ffd_weights: binomial weights of (1-L)^d, w_0 = 1. [documented]
    assert 0.0 <= d <= 1.0, "d outside [0,1]"
    if L is not None:  # fixed-width mode (hand-check / fixture)
        assert L >= 1, "fixed width needs L >= 1"
        w = [1.0]
        for k in range(1, L):
            w.append(-w[-1] * (d - k + 1) / k)
        return w
    w, k = [1.0], 1  # tau-truncation mode (production)
    while True:
        w_k = -w[-1] * (d - k + 1) / k
        if abs(w_k) < tau:
            break
        w.append(w_k)
        k += 1
        assert k < 100_000, "weight series failed to converge"
    return w


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    # Callable cost model — mirrors the §S2 COST block exactly: all four
    # components are zero because the transform executes no trades. [documented]
    spread_bps = 0.0  # [documented] no trades executed
    fee_bps = 0.0     # [documented] no orders emitted (no maker rebate possible)
    borrow_bps = 0.0  # [documented] no positions held; see borrow_bps_per_day
    impact_bps = 0.0  # [documented] no fills
    return spread_bps + fee_bps + borrow_bps + impact_bps


def init_state():
    return {"hist": [], "seq": 0, "cooldown_until_ns": 0,
            "module_state": "UNKNOWN", "last_vector": None}


def _bad(x):
    if x is None:
        return True
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return True
    return isinstance(x, (int, float)) and x <= 0


def step(state, row, cfg):
    # Reference implementation of the §S3 normative pseudocode.
    ts = row.get("event_ts")
    px = row.get("price")
    mkt = row.get("market_state", "CONTINUOUS_TRADING")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0, "cost_bps": 0.0,
           "ffd": float("nan"), "d": cfg["d"], "L": cfg["L"],
           "signal_event": ts, "fill_event_ts": None}
    # F1: invalid input -> UNKNOWN, never interpolate
    if ts is None or _bad(px):
        state["module_state"] = "UNKNOWN"
        return out, state
    out["fill_event_ts"] = ts + 1  # earliest reaction is t+1
    # F4: staleness — gap wider than TTL masks the window (no interpolation)
    if state["hist"] and (ts - state["hist"][-1]["event_ts"]) > cfg["ttl_mult"] * cfg["cadence_ns"]:
        state["hist"] = []
        state["module_state"] = "UNKNOWN"
        return out, state
    # Market-state gates (§S0.5)
    if mkt == "HALTED":
        state["module_state"] = "UNKNOWN"
        return out, state
    if mkt == "AUCTION":
        state["module_state"] = "DEGRADED"
        out["module_state"] = "DEGRADED"
        return out, state
    if mkt == "CLOSED":
        state["module_state"] = "OFF"
        out["module_state"] = "OFF"
        out["fill_event_ts"] = None
        return out, state
    # C10: post-exit / post-block cooldown
    if ts < state.get("cooldown_until_ns", 0):
        state["module_state"] = "DEGRADED"
        out["module_state"] = "DEGRADED"
        return out, state
    # Stationarity gate (veto path): ADF p >= 0.05 -> features gated out
    if cfg.get("adf_p", 0.0) >= 0.05:
        state["module_state"] = "UNKNOWN"
        return out, state
    # C7: locate — S087 never emits SHORT (direction is always 0)
    direction = 0
    # Warmup: the first L-1 bars are DEGRADED (no ffd emitted)
    state["hist"].append({"event_ts": ts, "price": px})
    state["seq"] += 1
    if len(state["hist"]) < cfg["L"]:
        state["module_state"] = "DEGRADED"
        out["module_state"] = "DEGRADED"
        return out, state
    w = _weights(cfg["d"], cfg["tau"], L=cfg["L"])
    xs = [h["price"] for h in state["hist"][-cfg["L"]:]]  # chronological, oldest first
    out["ffd"] = sum(wk * xk for wk, xk in zip(w, xs))    # w_0 on EARLIEST bar (§S4)
    out["direction"] = direction
    out["module_state"] = "OK"
    state["module_state"] = "OK"
    state["last_vector"] = out
    return out, state


def run(rows, cfg=None):
    cfg = cfg or CFG
    st = init_state()
    out = []
    for r in rows:
        sig, st = step(st, r, cfg)
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
            "edge_bps", "cost_bps", "ffd", "d", "L"]
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
        signal_event = s["signal_event"]
        if fill_event is not None:
            assert fill_event > signal_event


def test_causality_prefix_invariance():
    # Future data cannot leak into earlier outputs: the first n outputs of a
    # run on the full tape are identical to a run on the n-bar prefix.
    rows = tape()
    full = run(rows)
    prefix = run(rows[:5])
    for i in range(5):
        assert _close(full[i]["ffd"], prefix[i]["ffd"]), \
            f"row {i}: output changed when future data was present"
        assert full[i]["module_state"] == prefix[i]["module_state"]


def test_warmup_degraded_explicit():
    # The first L-1 bars are warmup: DEGRADED, no ffd emitted. [documented]
    sigs = run(tape())
    for s in sigs[:CFG["L"] - 1]:
        assert s["module_state"] == "DEGRADED", "warmup bars must be DEGRADED"
        assert math.isnan(s["ffd"]), "warmup bars must emit no ffd"
    first = sigs[CFG["L"] - 1]
    assert first["module_state"] == "OK" and not math.isnan(first["ffd"])


def test_weights_boundary_cases():
    # d=0 (tau mode) -> identity weights; d=1 -> (1,-1). [documented]
    assert _weights(0.0, 1e-5) == [1.0]
    w1 = _weights(1.0, 1e-5)
    assert len(w1) == 2 and _close(w1[0], 1.0) and _close(w1[1], -1.0)
    # fixed-width d=0.4, L=5 matches the §S4 hand-check weights. [documented]
    for got, want in zip(_weights(0.4, 1e-3, L=5), [1.0, -0.4, -0.12, -0.064, -0.0416]):
        assert _close(got, want)


def test_d0_identity_and_d1_negated_difference():
    # Window-order convention (w_0 on the earliest bar): tau-mode d=0 is the
    # identity; d=1 with L=2 is the negated one-bar difference. [documented]
    prices = [100.0, 102.0, 101.0, 105.0]
    cfg0 = dict(CFG, d=0.0, tau=1e-5, L=1)
    outs = [step(init_state(), {"event_ts": i, "price": p}, cfg0)[0]
            for i, p in enumerate(prices)]
    for o, p in zip(outs, prices):
        assert o["module_state"] == "OK" and _close(o["ffd"], p), \
            "d=0 must return the input unchanged"
    cfg1 = dict(CFG, d=1.0, tau=1e-5, L=2)
    st = init_state()
    outs = []
    for i, p in enumerate(prices):
        o, st = step(st, {"event_ts": i, "price": p}, cfg1)
        outs.append(o)
    assert outs[0]["module_state"] == "DEGRADED"  # warmup
    for o, p_prev, p in zip(outs[1:], prices[:-1], prices[1:]):
        assert o["module_state"] == "OK" and _close(o["ffd"], p_prev - p), \
            "d=1, L=2 must give x_{t-1} - x_t"


def test_invalid_inputs_unknown():
    # F1: invalid input -> UNKNOWN, never interpolate. Covers NaN, non-positive,
    # non-finite, and missing prices. [documented]
    rows = tape()
    for bad_price in (float("nan"), 0.0, -3.25, float("inf"), float("-inf"), None):
        bad = dict(rows[0])
        bad["price"] = bad_price
        sig, st = step(init_state(), bad, CFG)
        assert sig["module_state"] == "UNKNOWN", f"price={bad_price} must map to UNKNOWN"
        assert st["hist"] == [], "invalid input must not enter the history window"


def test_staleness_gap_masks_and_restarts():
    # F4: a gap wider than 3x cadence masks the window (no interpolation) and
    # restarts history; the next valid bar is warmup, not an emission.
    rows = tape()
    st = init_state()
    sigs = []
    for r in rows[:6]:
        s, st = step(st, r, CFG)
        sigs.append(s)
    assert sigs[5]["module_state"] == "OK"
    gap_row = dict(rows[6])
    gap_row["event_ts"] = rows[5]["event_ts"] + 4 * CFG["cadence_ns"]  # > 3x TTL
    s, st = step(st, gap_row, CFG)
    assert s["module_state"] == "UNKNOWN", "gap > TTL must mask, never interpolate"
    assert math.isnan(s["ffd"]), "masked bar must emit no ffd"
    assert st["hist"] == [], "stale window must be cleared"
    nxt = dict(rows[7])
    nxt["event_ts"] = gap_row["event_ts"] + CFG["cadence_ns"]
    s2, _ = step(st, nxt, CFG)
    assert s2["module_state"] == "DEGRADED", "post-gap restart must warm up, not emit"


def test_adf_gate_veto():
    # Stationarity gate: ADF p >= 0.05 gates every emission (veto path). [documented]
    veto_cfg = dict(CFG, adf_p=0.10)  # [example] above the 0.05 gate [default]
    for r in tape():
        s, _ = step(init_state(), r, veto_cfg)
        assert s["module_state"] == "UNKNOWN", "ADF veto must gate every emission"
        assert math.isnan(s["ffd"]), "gated features must emit no ffd"


def test_halt_freezes_and_auction_holds():
    # §S0.5 market-state table: HALTED -> freeze/UNKNOWN; AUCTION -> hold/DEGRADED.
    rows = tape()
    st = init_state()
    for r in rows[:6]:
        step(st, r, CFG)
    halt = dict(rows[6])
    halt["market_state"] = "HALTED"
    s, _ = step(st, halt, CFG)
    assert s["module_state"] == "UNKNOWN", "HALTED must freeze and emit UNKNOWN"
    assert len(st["hist"]) == 6, "halt must not consume the bar"
    auc = dict(rows[6])
    auc["market_state"] = "AUCTION"
    s, _ = step(st, auc, CFG)
    assert s["module_state"] == "DEGRADED", "AUCTION must hold the last vector"


def test_cost_gate():
    # Executable predicate: expected_cost_bps(...) <= k * edge_bps, k=0.5 [default].
    k = CFG["k"]
    c = expected_cost_bps(1e6, 0.01, "XNAS", "taker", 0.5)
    assert c == 0.0, "infrastructure module: executes no trades [documented]"
    assert c <= k * 100.0, "cost gate should pass on a large edge"
    for s in run(tape()):
        assert expected_cost_bps(0.0, 0.0, "none", "taker", 0.0) <= k * s["edge_bps"], \
            "cost gate must hold on every fixture row"


def test_cost_callable_mirrors_block():
    # The callable mirrors the §S2 COST block exactly: all four components are
    # zero for every side and urgency — no maker rebate is possible without
    # orders. [documented]
    for side in ("taker", "maker", "mixed"):
        for urgency in (0.0, 0.5, 1.0):
            assert expected_cost_bps(1e6, 0.01, "XNAS", side, urgency) == 0.0, \
                f"side={side} urgency={urgency}: cost must be exactly 0.0"
