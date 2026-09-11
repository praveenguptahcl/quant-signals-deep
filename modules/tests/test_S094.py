"""Acceptance tests for S094 — Unusual intraday volume (RVOL) & signed block-trade pressure.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode (§S3), and asserts causality, the cost gate,
hand-checked arithmetic, boundary triggers, invalid→UNKNOWN paths, the halt
path, the gate-veto path, the post-exit cooldown, the locate veto, and the
Lee–Ready signing rules.

Fixture note: bins 1–12 are the synthetic 12-bin morning tape (seed 94094);
bins 13–17 are hand-built boundary/robustness rows (RVOL exactly at the
trigger, block volume exactly at the threshold, invalid baseline, NaN volume,
HALTED market state). buy_k/sell_k are PRE-SIGNED block aggregates in
thousands of shares — production signs per-trade via Lee–Ready (§S3); the
fixture validates the aggregated decision logic. See test_lee_ready_* for the
signing rules themselves.

Run: python3 -m pytest modules/tests/test_S094.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S094_tape.csv"
EXPECTED = FIX / "S094_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
BIN_NS = 300_000_000_000  # 5-min bin in ns [example]; earliest fill = open(t+1)
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "rvol", "block_imb", "trigger",
                 "net_usd", "cum_usd", "gate_pass", "fill_event_ts"]

# Chapter S3 parameters (status per §S0.2: calibrate/default/example)
CFG = {"N": 20, "bin_min": 5, "rvol_trigger": 2.0, "block_shares": 10000,
       "imb_window_min": 15, "k": 0.5, "expected_drift_bps": 15.0,
       "cooldown_min": 30, "staleness_ttl_s": 900, "locate_ok": True,
       "shares": 2000, "entry_px": 40.00, "exit_px": 40.35, "cost_usd": 50.0}

KNOWN_MARKET_STATES = ("CONTINUOUS_TRADING", "HALTED", "AUCTION", "CLOSED")


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
    # Chapter S4 explicit decomposition on the 2,000-share $80k example [example]:
    # spread $20 = 2.5 bps, commissions/fees $10 = 1.25 bps, impact $20 = 2.5 bps
    spread_bps = 2.5
    fee_bps = 1.25
    borrow_bps = 0.0  # [default] borrow_bps_per_day = 0: intraday, no borrow
    impact_bps = 2.5
    return spread_bps + fee_bps + borrow_bps + impact_bps


def lee_ready(price, lagged_mid, prev_price, prev_sign):
    """Normative Lee–Ready (1991) signing [documented].

    Quote test first vs the 5-s-lagged midquote; the tick test resolves
    midquote prints against the previous trade price; a zero tick inherits
    the previous classification.
    """
    if price > lagged_mid:
        return +1
    if price < lagged_mid:
        return -1
    if price > prev_price:
        return +1
    if price < prev_price:
        return -1
    return prev_sign


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"cum": 0.0, "pos": 0, "cooldown_until": None, "last_sig": None}


def _blank_out(ts):
    return {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
            "module_state": "UNKNOWN", "edge_bps": 0.0,
            "cost_bps": expected_cost_bps(8e4, 0.01, "XNAS", "taker", "urgent"),
            "rvol": float("nan"), "block_imb": float("nan"), "trigger": 0,
            "net_usd": 0.0, "cum_usd": 0.0,
            "gate_pass": 0,
            "fill_event_ts": ts + BIN_NS if isinstance(ts, int) else None}


def step(state, row, cfg):
    ts = row.get("event_ts")
    base = row.get("baseline_k")
    act = row.get("actual_k")
    buy = row.get("buy_k")
    sell = row.get("sell_k")
    ms = row.get("market_state") or "CONTINUOUS_TRADING"
    out = _blank_out(ts)
    out["cum_usd"] = state["cum"]
    # F1: invalid input -> UNKNOWN, never interpolate (also unknown market state)
    if (any(_bad(v) for v in (ts, base, act, buy, sell))
            or ms not in KNOWN_MARKET_STATES
            or base <= 0 or act < 0 or buy < 0 or sell < 0):
        state["last_sig"] = dict(out)
        return out, state
    # Market-state table (§S0.5)
    if ms == "HALTED":
        state["last_sig"] = dict(out)  # freeze; UNKNOWN; contributions discarded
        return out, state
    if ms == "AUCTION":
        last = state.get("last_sig")
        if last is None:
            return out, state
        held = dict(last)
        held.update({"computed_at": ts, "module_state": "DEGRADED"})
        state["last_sig"] = held
        return held, state
    if ms == "CLOSED":
        out["module_state"] = "OFF"
        state["last_sig"] = dict(out)
        return out, state
    # --- features: data <= event_ts only; baseline excludes today (§S2) ---
    rvol = act / base
    tot_k = buy + sell                      # k shares (fixture unit)
    tot_shares = tot_k * 1000.0
    imb = (buy - sell) / tot_k if tot_k > 0 else None  # undefined with no blocks
    # --- guards: cooldown, trigger ---
    cd = state.get("cooldown_until")
    cooldown_ok = cd is None or (isinstance(ts, int) and ts >= cd)
    trigger = 1 if (rvol > cfg["rvol_trigger"] and tot_shares >= cfg["block_shares"]
                    and imb is not None and cooldown_ok) else 0
    direction = (1 if imb > 0 else -1) if (trigger and imb != 0) else 0
    # C7: SHORT requires consumer locate_ok (Reg-SHO); else direction 0
    if direction == -1 and not cfg.get("locate_ok", True):
        direction = 0
    # --- cost gate (entry only): expected_cost_bps(...) <= k * expected_drift_bps ---
    gate_pass = 1 if (trigger and out["cost_bps"] <= cfg["k"] * cfg["expected_drift_bps"]) else 0
    if trigger and direction != 0 and not gate_pass:
        direction = 0  # veto: sub-threshold scores emit direction 0 (C2)
    # --- position bookkeeping: enter on first gated trigger; exit on sign flip ---
    net = 0.0
    if trigger and direction != 0 and state["pos"] == 0:
        state["pos"] = direction
    if state["pos"] != 0 and trigger and direction != 0 and direction != state["pos"]:
        gross = cfg["shares"] * (cfg["exit_px"] - cfg["entry_px"]) * state["pos"]
        net = gross - cfg["cost_usd"]
        state["cum"] += net
        state["pos"] = 0
        if isinstance(ts, int):
            state["cooldown_until"] = ts + cfg["cooldown_min"] * 60 * 1_000_000_000
    out["cum_usd"] = state["cum"]
    out["net_usd"] = net
    live = trigger and direction != 0
    edge_bps = cfg["expected_drift_bps"] if live else 0.0  # ex-ante edge the gate uses [example]
    out.update({"module_state": "OK", "direction": direction,
                "confidence": min(1.0, rvol / 4.0) if live else 0.0,   # [default] scaling
                "capital": 0.5 * min(1.0, rvol / 4.0) if live else 0.0,  # [default]
                "edge_bps": edge_bps, "rvol": rvol,
                "block_imb": imb if imb is not None else 0.0,
                "trigger": trigger, "gate_pass": gate_pass})
    state["last_sig"] = dict(out)
    return out, state


def run(rows, cfg=None):
    cfg = cfg or dict(CFG)
    st = init_state()
    out = []
    for r in rows:
        sig, st = step(st, r, cfg)
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
    assert len(rows) >= 5, "fixture needs >=5 hand-checkable rows"


def test_expected_matches_reference():
    rows = tape()
    sigs = run(rows)
    exp = load_csv(EXPECTED)
    assert len(exp) == len(sigs), "expected row count != tape row count"
    for i, (s, e) in enumerate(zip(sigs, exp)):
        assert int(e["bin"]) == int(rows[i]["bin"]), f"row {i} bin mismatch"
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
    # Chapter S4: bin 4 RVOL = 206/60 = 3.43 -> trigger, block imbalance +1.0 -> long
    # bin 9 RVOL = 157/55 = 2.85 -> trigger, imbalance -1.0 -> exit
    sigs = run(tape())
    b4, b9 = sigs[3], sigs[8]
    assert abs(b4["rvol"] - 206.0 / 60.0) < 1e-9
    assert abs(b4["block_imb"] - 1.0) < 1e-9
    assert b4["trigger"] == 1 and b4["direction"] == 1
    assert abs(b9["rvol"] - 157.0 / 55.0) < 1e-9
    assert abs(b9["block_imb"] - (-1.0)) < 1e-9
    assert b9["trigger"] == 1 and b9["direction"] == -1
    # chapter P&L: 2,000 x $0.35 = $700 gross - $50 costs = +$650 net [example]
    assert abs(b9["net_usd"] - 650.0) < 1e-9
    assert abs(b9["cum_usd"] - 650.0) < 1e-9
    # bin 10: RVOL 1.55 with no blocks -> correctly ignored
    assert sigs[9]["trigger"] == 0 and sigs[9]["direction"] == 0
    # cost gate now evaluates on the bound expected drift: 6.25 <= 0.5 * 15 = 7.5
    assert b4["gate_pass"] == 1


def test_trigger_boundary():
    # RVOL exactly at the trigger (2.0) must NOT fire: the rule is strict >
    sigs = run(tape())
    b13, b14 = sigs[12], sigs[13]
    assert abs(b13["rvol"] - 2.0) < 1e-9
    assert b13["trigger"] == 0 and b13["direction"] == 0, "rvol == trigger must not fire"
    # RVOL just above (2.01) with block volume exactly at the 10k-share threshold fires
    assert abs(b14["rvol"] - 2.01) < 1e-9
    assert b14["trigger"] == 1 and b14["direction"] == 1
    assert abs(b14["confidence"] - 2.01 / 4.0) < 1e-9
    assert b14["gate_pass"] == 1


def test_invalid_and_halt_rows_unknown():
    sigs = run(tape())
    b15, b16, b17 = sigs[14], sigs[15], sigs[16]
    assert b15["module_state"] == "UNKNOWN", "zero baseline must map to UNKNOWN"
    assert b16["module_state"] == "UNKNOWN", "NaN volume must map to UNKNOWN"
    assert b17["module_state"] == "UNKNOWN", "HALTED market state must map to UNKNOWN"
    for b in (b15, b16, b17):
        assert b["direction"] == 0 and b["trigger"] == 0, "UNKNOWN rows emit no direction"
        assert b["confidence"] == 0.0 and b["capital"] == 0.0


def test_no_signal_bar_fills():
    # t -> t+1 causality: the fill event is pinned to the next bin's open,
    # strictly after the signal event on every row.
    for s in run(tape()):
        fill_event = s["fill_event_ts"]
        signal_event = s["computed_at"]
        if fill_event is not None:
            assert fill_event > signal_event
    sigs = run(tape())
    for i, s in enumerate(sigs):
        if isinstance(s["computed_at"], int):
            assert s["fill_event_ts"] == s["computed_at"] + BIN_NS, \
                f"row {i}: fill must be pinned to open(t+1)"


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k * expected_drift_bps
    k = 0.5  # [default]
    drift = 15.0  # [example] bound ex-ante edge
    c = expected_cost_bps(8e4, 0.01, "XNAS", "taker", "urgent")
    assert abs(c - 6.25) < 1e-9, "chapter stack must total 6.25 bps"
    assert c <= k * drift, "gate should pass on the bound expected drift"
    assert not (c <= k * 0.01), "gate should block on a tiny edge"


def test_gate_veto_path():
    # A trigger whose cost fails the gate must emit direction 0 (C2), never a hint.
    cfg = dict(CFG, k=0.01)  # threshold 0.15 bps << 6.25 bps cost
    st = init_state()
    row4 = dict(tape()[3])
    sig, _ = step(st, row4, cfg)
    assert sig["trigger"] == 1, "trigger conditions still met"
    assert sig["gate_pass"] == 0, "gate must fail under the tiny k"
    assert sig["direction"] == 0, "failed gate vetoes the direction"
    assert sig["confidence"] == 0.0 and sig["capital"] == 0.0


def test_locate_veto_short():
    # C7: SHORT without a consumer locate assertion emits direction 0.
    cfg = dict(CFG, locate_ok=False)
    st = init_state()
    row9 = dict(tape()[8])
    sig, _ = step(st, row9, cfg)
    assert sig["trigger"] == 1
    assert sig["direction"] == 0, "SHORT without locate_ok must be vetoed"


def test_cooldown_suppresses_reentry():
    # §S2 exits: 30-min post-exit cooldown. A trigger 5 min after the bin-9
    # exit must be suppressed even though RVOL/block conditions are met.
    st = init_state()
    cfg = dict(CFG)
    r4, r9 = dict(tape()[3]), dict(tape()[8])
    step(st, r4, cfg)   # entry
    step(st, r9, cfg)   # exit -> cooldown_until = t9 + 30 min
    r4b = dict(r4)
    r4b["event_ts"] = r9["event_ts"] + 5 * 60 * 1_000_000_000
    sig, _ = step(st, r4b, cfg)
    assert sig["trigger"] == 0, "cooldown must suppress re-entry"
    assert sig["direction"] == 0


def test_lee_ready_quote_and_tick():
    # Normative Lee–Ready (1991) signing rules [documented].
    assert lee_ready(40.02, 40.00, 40.01, +1) == +1   # quote test: above lagged mid
    assert lee_ready(39.98, 40.00, 39.99, -1) == -1   # quote test: below lagged mid
    assert lee_ready(40.00, 40.00, 39.99, -1) == +1   # midquote print, uptick
    assert lee_ready(40.00, 40.00, 40.01, +1) == -1   # midquote print, downtick
    assert lee_ready(40.00, 40.00, 40.00, +1) == +1   # zero tick inherits previous
    assert lee_ready(40.00, 40.00, 40.00, -1) == -1


def test_auction_degraded_hold_last():
    st = init_state()
    cfg = dict(CFG)
    r4 = dict(tape()[3])
    sig4, _ = step(st, r4, cfg)
    rauc = dict(r4)
    rauc["event_ts"] = r4["event_ts"] + BIN_NS
    rauc["market_state"] = "AUCTION"
    held, _ = step(st, rauc, cfg)
    assert held["module_state"] == "DEGRADED"
    assert held["direction"] == sig4["direction"], "auction holds the last vector"


def test_invalid_input_unknown():
    st = init_state()
    bad = {"event_ts": 1, "baseline_k": float("nan"), "actual_k": 100.0,
           "buy_k": 0.0, "sell_k": 0.0, "market_state": "CONTINUOUS_TRADING"}
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"
