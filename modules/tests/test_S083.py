"""Acceptance tests for S083 — Imbalance/tick/volume/dollar bars.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode (§S3), and asserts causality, the cost gate, and
hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S083.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S083_tape.csv"
EXPECTED = FIX / "S083_expected.csv"

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


# --- Reference implementation of the §S3 normative pseudocode ---

CFG = {  # fixture-scale thresholds [example]
    "tick_n": 5,
    "vol_shares": 3000,
    "imb_theta": 1500.0,
    "theta_lambda": 0.05,       # EWMA smoothing for E_0[T]*E_0[|theta|] [default]
    "tick_rule": "carry_forward",  # [default]
    "ttl_mult": 3,              # staleness TTL = 3x median bar cadence [default]
    "cost_k": 0.5,              # cost-gate multiplier [default]
}


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    # Callable cost model - mirrors the §S2 COST block exactly.
    # The sampler executes no trades: all four cost components are zero. [documented]
    spread_bps = 0.0            # [documented]
    fee_bps = 0.0               # [documented]
    borrow_bps_per_day = 0.0    # [documented] reason: no positions taken, nothing borrowed
    impact_bps = 0.0            # [documented]
    _ = (notional, adv_pct, venue, side, urgency)  # signature fixed by v1.0.0; args unused
    return spread_bps + fee_bps + borrow_bps_per_day + impact_bps


def cost_gate_passes(cost_bps, edge_bps, k=0.5) -> bool:
    # Executable cost-gate predicate from §S3: expected_cost_bps(...) <= k * edge_bps
    return cost_bps <= k * edge_bps


def init_state():
    def _nb():
        return {"id": 0, "acc": 0.0, "o": None, "h": None, "l": None, "c": None}
    return {"tick": _nb(), "vol": _nb(), "imb": _nb(),
            "last_event_ts": None, "last_out": None, "market_state": "CONTINUOUS_TRADING"}


def _out(ts, ok):
    return {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
            "module_state": "OK" if ok else "UNKNOWN", "edge_bps": 0.0, "cost_bps": 0.0,
            "fill_event_ts": ts + 1 if isinstance(ts, int) else None,
            "tick_id": 0, "tick_done": 0, "tick_o": float("nan"), "tick_h": float("nan"),
            "tick_l": float("nan"), "tick_c": float("nan"),
            "vol_id": 0, "vol_done": 0, "vol_o": float("nan"), "vol_h": float("nan"),
            "vol_l": float("nan"), "vol_c": float("nan"),
            "imb_id": 0, "imb_done": 0, "imb_o": float("nan"), "imb_h": float("nan"),
            "imb_l": float("nan"), "imb_c": float("nan"), "theta": float("nan")}


def _valid(row):
    # F1: invalid input -> UNKNOWN, never interpolate. All guards bound here.
    ts = row.get("event_ts")
    px = row.get("price")
    sz = row.get("size")
    sg = row.get("sign")
    if ts is None:
        return False
    for x in (px, sz):
        if x is None or not (isinstance(x, (int, float)) and math.isfinite(x)):
            return False
    if not (px > 0) or not (sz > 0):
        return False
    if sg not in (1, -1):
        return False
    return True


def _upd(nb, px, w, thresh, absolute):
    if nb["o"] is None:
        nb["o"] = nb["h"] = nb["l"] = nb["c"] = px
    else:
        nb["h"] = max(nb["h"], px); nb["l"] = min(nb["l"], px); nb["c"] = px
    nb["acc"] += w
    hit = abs(nb["acc"]) >= thresh if absolute else nb["acc"] >= thresh
    if hit:
        snap = (nb["id"], nb["o"], nb["h"], nb["l"], nb["c"], nb["acc"])
        nb["id"] += 1; nb["acc"] = 0.0
        nb["o"] = nb["h"] = nb["l"] = nb["c"] = None
        return snap
    return None


def step(state, row, cfg):
    # §S3 normative pseudocode, guards inline. Returns (signal_vector, state).
    ts = row.get("event_ts")
    ms = row.get("market_state", "CONTINUOUS_TRADING")

    # G1 halt guard: freeze state, emit UNKNOWN, discard contributions across reopen.
    if ms == "HALTED":
        return _out(ts, False), state
    # G2 auction guard: no new signals; hold last vector; state DEGRADED.
    if ms == "AUCTION":
        lo = dict(state["last_out"]) if state["last_out"] is not None else _out(ts, False)
        lo["module_state"] = "DEGRADED"
        return lo, state
    # G3 monotonicity guard: ts must be strictly increasing (causality pin 1).
    if ts is not None and state["last_event_ts"] is not None and ts <= state["last_event_ts"]:
        return _out(ts, False), state
    # G4 input validity (F1): invalid -> UNKNOWN, never interpolate.
    if not _valid(row):
        return _out(ts, False), state

    px = row.get("price"); sz = row.get("size"); sg = row.get("sign")
    t = _upd(state["tick"], px, 1, cfg["tick_n"], False)
    v = _upd(state["vol"], px, sz, cfg["vol_shares"], False)
    m = _upd(state["imb"], px, sg * sz, cfg["imb_theta"], True)
    o = _out(ts, True)
    for key, snap, prefix in (("tick", t, "tick"), ("vol", v, "vol"), ("imb", m, "imb")):
        nb = state[key]
        o[prefix + "_id"] = snap[0] if snap else nb["id"]
        o[prefix + "_done"] = 1 if snap else 0
        src = snap[1:5] if snap else (nb["o"], nb["h"], nb["l"], nb["c"])
        o[prefix + "_o"], o[prefix + "_h"], o[prefix + "_l"], o[prefix + "_c"] = src
    o["theta"] = m[5] if m else state["imb"]["acc"]

    # G5 cost gate (executable predicate): constant-zero stack, edge 0.0 -> 0 <= k*0 passes vacuously.
    cost = expected_cost_bps(0.0, 0.0, "n/a", "n/a", 0.0)
    assert cost_gate_passes(cost, 0.0, cfg["cost_k"]), "cost gate failed"
    # G6 causality pin: earliest fill strictly after the signal event (t -> t+1).
    assert o["fill_event_ts"] > o["computed_at"], "fill_event must be > signal_event"

    state["last_event_ts"] = ts
    state["last_out"] = o
    return o, state


def signal_batch(state, events, cfg):
    # §S0.1 contract: empty events -> UNKNOWN.
    if not events:
        return _out(None, False), state
    return step(state, events[-1], cfg)


def run(rows):
    st = init_state(); out = []
    for r in rows:
        sig, st = step(st, r, CFG)
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
    cols = ["computed_at", "direction", "confidence", "capital", "module_state", "edge_bps", "cost_bps", "tick_id", "tick_done", "tick_o", "tick_h", "tick_l", "tick_c", "vol_id", "vol_done", "vol_o", "vol_h", "vol_l", "vol_c", "imb_id", "imb_done", "imb_o", "imb_h", "imb_l", "imb_c", "theta"]
    for i, (s, e) in enumerate(zip(sigs, exp)):
        assert int(e["ev"]) == int(rows[i]["ev"]), f"row {i} ev mismatch"
        for c in cols:
            got = s[c]
            want = _num(e[c])
            assert _close(got, want), f"row {i} col {c}: got {got} want {want}"


def test_boundary_exact_threshold_close():
    # Pins the >= comparison at the exact threshold: ev9 volume acc == 3000 == V*,
    # ev12 imbalance |theta| == 1500.0 == imb_theta. Both must close the bar. [example]
    sigs = run(tape())
    ev9 = sigs[8]
    assert ev9["vol_done"] == 1 and ev9["vol_id"] == 1, "exact V* hit must close volume bar"
    assert ev9["vol_c"] == 98.87, "volume bar 1 close price hand-check"
    ev12 = sigs[11]
    assert ev12["imb_done"] == 1 and ev12["imb_id"] == 1, "exact |theta|* hit must close imbalance bar"
    assert abs(ev12["theta"] - 1500.0) <= TOL, "closing theta must equal +1500.0"
    # Just below the threshold must NOT close: ev7 theta=1400 < 1500.
    assert sigs[6]["imb_done"] == 0 and abs(sigs[6]["theta"] - 1400.0) <= TOL


def test_corrupt_row_freezes_and_unknown():
    # ev16: NaN price -> F1 UNKNOWN; accumulator state must not advance on the bad row.
    sigs = run(tape())
    assert sigs[15]["module_state"] == "UNKNOWN", "corrupt row must emit UNKNOWN"
    assert sigs[14]["module_state"] == "OK"
    # theta reported at ev16 is NaN, not carried forward: never interpolate.
    assert math.isnan(sigs[15]["theta"])


def test_halt_freezes_state():
    # ev17: HALTED -> UNKNOWN, state frozen; a 100000-share buy that would have
    # closed every bar must contribute nothing.
    rows = tape()
    st = init_state()
    for r in rows[:16]:
        _, st = step(st, r, CFG)
    frozen = {"tick_id": st["tick"]["id"], "vol_id": st["vol"]["id"],
              "imb_id": st["imb"]["id"], "imb_acc": st["imb"]["acc"]}
    sig17, st = step(st, rows[16], CFG)
    assert sig17["module_state"] == "UNKNOWN", "halt must emit UNKNOWN"
    assert st["tick"]["id"] == frozen["tick_id"]
    assert st["vol"]["id"] == frozen["vol_id"]
    assert st["imb"]["id"] == frozen["imb_id"]
    assert st["imb"]["acc"] == frozen["imb_acc"] == 1100.0, "theta frozen at ev15 value"


def test_auction_degraded_hold():
    # AUCTION: no new signals; hold last vector; state DEGRADED.
    rows = tape()
    st = init_state()
    for r in rows[:5]:
        _, st = step(st, r, CFG)
    auc = dict(rows[5])
    auc["market_state"] = "AUCTION"
    auc["event_ts"] = rows[5]["event_ts"]
    sig, st2 = step(st, auc, CFG)
    assert sig["module_state"] == "DEGRADED"
    # held vector = last emission at ev5: tick bar 0 closed, vol bar 1 open.
    assert sig["tick_id"] == 0 and sig["tick_done"] == 1, "held vector must be the ev5 emission"
    assert sig["vol_id"] == 1 and sig["vol_done"] == 0
    assert st2["tick"]["id"] == 1 and st2["vol"]["id"] == 1, "auction must not advance state"


def test_ts_not_monotonic_unknown():
    # Causality pin 1: non-increasing event_ts -> UNKNOWN, never interpolated.
    rows = tape()
    st = init_state()
    _, st = step(st, rows[0], CFG)
    dup = dict(rows[1])
    dup["event_ts"] = rows[0]["event_ts"]  # duplicate ts
    sig, _ = step(st, dup, CFG)
    assert sig["module_state"] == "UNKNOWN", "duplicate ts must emit UNKNOWN"


def test_empty_events_unknown():
    # §S0.1 contract: empty events -> UNKNOWN.
    sig, _ = signal_batch(init_state(), [], CFG)
    assert sig["module_state"] == "UNKNOWN"


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
    # Normative predicate: expected_cost_bps(...) <= k * edge_bps, k = 0.5 [default].
    # The sampler executes no trades: cost is the constant-zero stack [documented].
    c = expected_cost_bps(0.0, 0.0, "n/a", "n/a", 0.0)
    assert c == 0.0
    assert cost_gate_passes(c, 0.0, 0.5), "vacuous pass: 0.0 <= 0.5 * 0.0"
    # Veto path of the predicate itself, exercised on a hypothetical nonzero cost:
    assert not cost_gate_passes(1.0, 0.0, 0.5), "nonzero cost on zero edge must veto"


def test_invalid_input_unknown():
    rows = tape()
    st = init_state()
    bad_price = dict(rows[0]); bad_price["price"] = float("nan")
    sig, _ = step(st, bad_price, CFG)
    assert sig["module_state"] == "UNKNOWN", "NaN price must map to UNKNOWN"
    bad_size = dict(rows[0]); bad_size["size"] = float("nan")
    sig, _ = step(st, bad_size, CFG)
    assert sig["module_state"] == "UNKNOWN", "NaN size must map to UNKNOWN"
    bad_sign = dict(rows[0]); bad_sign["sign"] = 0
    sig, _ = step(st, bad_sign, CFG)
    assert sig["module_state"] == "UNKNOWN", "sign not in {+1,-1} must map to UNKNOWN"
    zero_price = dict(rows[0]); zero_price["price"] = 0.0
    sig, _ = step(st, zero_price, CFG)
    assert sig["module_state"] == "UNKNOWN", "non-positive price must map to UNKNOWN"
    neg_size = dict(rows[0]); neg_size["size"] = -100
    sig, _ = step(st, neg_size, CFG)
    assert sig["module_state"] == "UNKNOWN", "non-positive size must map to UNKNOWN"


def test_expected_cost_bps_signature():
    # The callable must keep the v1.0.0 signature (notional, adv_pct, venue, side, urgency).
    import inspect
    params = list(inspect.signature(expected_cost_bps).parameters)
    assert params == ["notional", "adv_pct", "venue", "side", "urgency"]
    assert expected_cost_bps(1e6, 0.01, "XNAS", "taker", 1) == 0.0
