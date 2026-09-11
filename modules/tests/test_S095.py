"""Acceptance tests for S095 — Funding-rate / basis z-score (perpetuals).

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode (S095.md §S3), and asserts causality, the cost
gate, the guards (halt/auction, staleness, cooldown, locate), and hand-checked
arithmetic.

Run: python3 -m pytest modules/tests/test_S095.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S095_tape.csv"
EXPECTED = FIX / "S095_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "f_ann", "z_t", "gate_pass", "fill_event_ts"]

# Chapter §S0.2 Config defaults. z_cut/trail_n are [example] (status: calibrate);
# k/cooldown_h/ttl_h are [default].
CFG = {"trail_n": 5, "z_cut": 2.5, "k": 0.5, "cooldown_h": 8.0, "ttl_h": 24.0}

H8_NS = 8 * 3600 * 10 ** 9  # one funding interval in ns [documented]


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
    # Mirrors the §S2 COST block exactly: perp interval stack, side = taker.
    spread_bps = 15.0   # [example]
    fee_bps = 12.0      # [example]
    borrow_bps = 0.0    # [default] reason: perps have funding, not borrow
    impact_bps = 10.0   # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"hist": [], "last_print_ts": None, "last_governor_ts": None}


def step(state, row, cfg):
    """Reference implementation of the §S3 normative pseudocode."""
    ts = row.get("event_ts")
    f = row.get("funding_pct")
    h = row.get("interval_h")
    market = row.get("market", "CONTINUOUS_TRADING")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e4, 0.01, "BINANCE", "taker", "passive"),
           "f_ann": float("nan"), "z_t": float("nan"), "gate_pass": 0,
           "fill_event_ts": ts + 1 if isinstance(ts, int) else None}
    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (ts, f, h)) or not isinstance(h, (int, float)) or h <= 0:
        return out, state
    # Halt/auction guard (§S0.5): freeze state, no new signals across reopen
    if market == "HALTED":
        return out, state
    if market == "AUCTION":
        out["module_state"] = "DEGRADED"
        return out, state
    # Staleness guard: gap > TTL -> UNKNOWN; mask the print (no interpolation),
    # but advance last_print_ts so the next regular print can recover.
    ttl_ns = int(cfg["ttl_h"] * 3600 * 1e9)
    if state["last_print_ts"] is not None and ts - state["last_print_ts"] > ttl_ns:
        state["last_print_ts"] = ts
        return out, state
    # Valid print: append, advance clock, keep a bounded window
    state["hist"].append(f)
    state["last_print_ts"] = ts
    if len(state["hist"]) > cfg["trail_n"] + 1:
        state["hist"] = state["hist"][-(cfg["trail_n"] + 1):]
    f_ann = (8760.0 / h) * (f / 100.0) * 10000.0  # bps annualization [documented]
    out["f_ann"] = f_ann
    if len(state["hist"]) < cfg["trail_n"] + 1:
        return out, state  # insufficient history -> UNKNOWN
    win = state["hist"][-(cfg["trail_n"] + 1):-1]
    m = sum(win) / len(win)
    var = sum((x - m) ** 2 for x in win) / (len(win) - 1)
    sd = math.sqrt(var) if var > 0 else 0.0
    z_t = (f - m) / sd if sd > 0 else 0.0  # sd == 0 -> z = 0.0 (no crowding signal)
    out["z_t"] = z_t
    # Locate guard: direction -1 is a leverage-reduction intent, never a new short
    # sale; the module never emits SHORT, so locate is n/a here. A consumer that
    # shorts on this signal must assert locate_ok itself (C7).
    # Cooldown guard: no re-entry inside one funding interval after a governor.
    cd_ns = int(cfg["cooldown_h"] * 3600 * 1e9)
    if state["last_governor_ts"] is not None and ts - state["last_governor_ts"] < cd_ns:
        out["module_state"] = "OK"  # valid print, governor suppressed
        return out, state
    if z_t > cfg["z_cut"]:
        direction = -1  # crowded longs -> reduce leverage (never an unconditional short)
    elif z_t < -cfg["z_cut"]:
        direction = 1   # crowded shorts -> fade the other way
    else:
        direction = 0
    # edge_bps is an ILLUSTRATIVE avoided-drawdown value [example], not a
    # documented edge. The chapter's carry example is net -$10 on $10k
    # (funding $6 - fees $16): it FAILS its own cost gate by construction, and no
    # invented edge is allowed to force a pass.
    edge_bps = 100.0 if direction else 0.0  # [example]
    cost_bps = expected_cost_bps(1e4, 0.01, "BINANCE", "taker", "passive")
    gate_pass = 1 if cost_bps <= cfg["k"] * edge_bps else 0
    # C2: gate fail -> veto to direction 0 (never a tradeable hint)
    if direction != 0 and not gate_pass:
        direction = 0
    confidence = min(1.0, abs(z_t) / 10.0) if direction else 0.0
    if direction != 0:
        state["last_governor_ts"] = ts
    out.update({"module_state": "OK", "direction": direction, "confidence": confidence,
                "capital": 0.5 * confidence, "edge_bps": edge_bps,
                "cost_bps": cost_bps, "gate_pass": gate_pass})
    return out, state


def run(rows, cfg=None):
    st = init_state()
    out = []
    for r in rows:
        sig, st = step(st, r, cfg or CFG)
        out.append(sig)
    return out


def mkrow(ts, f, h=8, market="CONTINUOUS_TRADING"):
    return {"event_ts": ts, "funding_pct": f, "interval_h": h, "market": market}


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
    assert len(rows) >= 5, "fixture needs >=5 hand-checkable rows"


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
    # Chapter S4: baseline prints 0.010/0.012/0.011/0.013/0.012 -> mean 0.0116%, sd ~0.00114%;
    # the 0.050% print -> z ~ +33.7 [documented] -> reduce leverage, never an unconditional short
    sigs = run(tape())
    s6 = sigs[5]
    assert s6["module_state"] == "OK"
    assert abs(s6["z_t"] - 33.7) < 0.6
    assert s6["direction"] == -1
    assert s6["gate_pass"] == 1
    # chapter S4 carry accounting: $6.00 funding - $16.00 fees = -$10.00 net [documented];
    # the carry example therefore FAILS the cost gate (37 bps > 0.5*0 bps of carry edge) —
    # the gate below passes only on the separate illustrative avoided-drawdown edge [example]
    assert abs(6.00 - 16.00 - (-10.00)) < 1e-9
    # f_ann units [documented]: (8760/8)*(0.05/100)*10000 = 5475 bps
    assert abs(s6["f_ann"] - 5475.0) < 1.0
    # rows 1-5: insufficient history -> UNKNOWN
    for s in sigs[:5]:
        assert s["module_state"] == "UNKNOWN"
    # row 8: intra-interval extreme (0.200%, z >> z_cut) 4h after the governor ->
    # cooldown suppresses the re-entry: direction 0, state OK
    s8 = sigs[7]
    assert s8["z_t"] > CFG["z_cut"], "row 8 must genuinely exceed the cutoff"
    assert s8["module_state"] == "OK"
    assert s8["direction"] == 0
    assert s8["gate_pass"] == 0
    # row 9: 44h gap (> 24h TTL) -> staleness UNKNOWN
    s9 = sigs[8]
    assert s9["module_state"] == "UNKNOWN"


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
    c = expected_cost_bps(1e4, 0.01, "BINANCE", "taker", "passive")
    assert abs(c - 37.0) < 1e-9, "callable must mirror the §S2 COST block total exactly"
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    rows = tape()
    st = init_state()
    sig, _ = step(st, dict(rows[6]), CFG)  # funding = nan
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"


def test_invalid_interval_zero():
    st = init_state()
    sig, _ = step(st, mkrow(1789008000000000000, 0.050, h=0), CFG)
    assert sig["module_state"] == "UNKNOWN", "interval_h = 0 must map to UNKNOWN"


def test_boundary_z_cut_strict():
    # win = [1,2,3,4,5] -> mean 3.0, sd = sqrt(2.5); probe just below/above z_cut.
    ts = 1789008000000000000
    mu, sd = 3.0, math.sqrt(2.5)
    f_below = mu + (CFG["z_cut"] - 1e-6) * sd
    f_above = mu + (CFG["z_cut"] + 1e-6) * sd
    f_neg = mu - (CFG["z_cut"] + 1e-6) * sd
    for f, want in ((f_below, 0), (f_above, -1), (f_neg, 1)):
        st = {"hist": [1.0, 2.0, 3.0, 4.0, 5.0],
              "last_print_ts": ts - H8_NS, "last_governor_ts": None}
        sig, _ = step(st, mkrow(ts, f), CFG)
        assert sig["module_state"] == "OK"
        assert sig["direction"] == want, f"f={f}: want direction {want}, got {sig['direction']}"


def test_sd_zero_guard():
    # constant prints -> sd = 0 -> z = 0.0, no governor, state OK
    ts = 1789008000000000000
    st = {"hist": [0.01] * 5, "last_print_ts": ts - H8_NS, "last_governor_ts": None}
    sig, _ = step(st, mkrow(ts, 0.01), CFG)
    assert sig["module_state"] == "OK"
    assert sig["z_t"] == 0.0
    assert sig["direction"] == 0


def test_gate_veto_path():
    # tiny k makes the gate fail on the genuine extreme -> C2 veto to direction 0
    rows = tape()
    st = init_state()
    for r in rows[:5]:
        step(st, r, CFG)
    cfg2 = dict(CFG, k=0.01)
    sig, _ = step(st, dict(rows[5]), cfg2)
    assert sig["module_state"] == "OK"
    assert sig["gate_pass"] == 0
    assert sig["direction"] == 0, "gate fail must veto to direction 0 (never a tradeable hint)"
    assert sig["confidence"] == 0.0
    assert sig["capital"] == 0.0
    assert sig["edge_bps"] == 100.0  # the illustrative edge is recorded; the veto is the decision


def test_cooldown_suppression():
    # a fresh extreme inside the cooldown window is suppressed, not re-emitted
    ts = 1789008000000000000
    st = {"hist": [0.010, 0.012, 0.011, 0.013, 0.012],
          "last_print_ts": ts, "last_governor_ts": ts}
    sig, st2 = step(st, mkrow(ts + 4 * 3600 * 10 ** 9, 0.200), CFG)
    assert sig["z_t"] > CFG["z_cut"]
    assert sig["module_state"] == "OK"
    assert sig["direction"] == 0, "cooldown must suppress the re-entry"
    assert st2["last_governor_ts"] == ts, "suppressed print must not re-arm the cooldown"


def test_staleness_guard():
    # 25h gap (> 24h TTL) -> UNKNOWN; the print is masked, clock advances for recovery
    ts = 1789008000000000000
    st = {"hist": [0.010, 0.012, 0.011, 0.013, 0.012],
          "last_print_ts": ts, "last_governor_ts": None}
    sig, st2 = step(st, mkrow(ts + 25 * 3600 * 10 ** 9, 0.050), CFG)
    assert sig["module_state"] == "UNKNOWN"
    assert len(st2["hist"]) == 5, "stale print must be masked (not appended)"
    assert st2["last_print_ts"] == ts + 25 * 3600 * 10 ** 9


def test_halt_freezes_state():
    ts = 1789008000000000000
    st = {"hist": [0.010, 0.012, 0.011, 0.013, 0.012],
          "last_print_ts": ts - H8_NS, "last_governor_ts": None}
    sig, st2 = step(st, mkrow(ts, 0.200, market="HALTED"), CFG)
    assert sig["module_state"] == "UNKNOWN"
    assert st2["hist"] == [0.010, 0.012, 0.011, 0.013, 0.012], "halt must freeze state"
    sig2, _ = step(st, mkrow(ts, 0.200, market="AUCTION"), CFG)
    assert sig2["module_state"] == "DEGRADED"
