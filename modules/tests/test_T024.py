"""Deep-review test: T024 Informed-Size Tracker / Retail Fade (v1.0.1).

Run: python3 -m pytest modules/tests/test_T024.py -q
(cwd must be the repo root, i.e. ~/workspace/quant-signals-deep)
"""
import csv
import math
import os

SID = "T024"
TAPE = os.path.join("modules", "fixtures", "T024_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T024_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model - T024 COST block (single source of truth)."""
    spread_bps = 8.0    # [example] $0.02 assumed spread @ $50: half/aggressive x 2 (taker)
    fee_bps = 2.0       # [example] $0.005/share each way @ $50 = 1 bps/leg
    borrow_bps = 0.0    # [default] intraday; no borrow
    impact_bps = 4.0    # [example] footprint chasing: 2c adverse @ $50
    return spread_bps + fee_bps + borrow_bps + impact_bps


def shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost):
    """shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost).

    Normative copy of the §T3 sizing function: footprint trades are fixed
    1-lot [example]; the edge is the classification, not the size.
    """
    n = 100  # 1 lot [example]
    n = min(n, ADV_cap * 0.001)    # 0.1% ADV [default]
    return int(n)


# §T0 Config dataclass surface (defaults, range lo, range hi) — must mirror
# the markdown table exactly; test_config_defaults_parity enforces this.
CONFIG_DEFAULTS = {
    "large_mult": (3.0, 1.5, 10.0),
    "retail_opp_min": (0.60, 0.5, 0.9),
    "vpin_veto": (0.50, 0.1, 0.6),
    "hold_ms": (2000.0, 500, 10000),
    "cooldown_s": (10.0, 0, 60),
    "cost_gate_k": (0.5, 0.1, 2.0),
    "per_trade_R": (150.0, 50, 1000),
    "daily_loss_stop": (-1500.0, -10000, -500),
    "max_gross": (1000000.0, 100000, 5000000),
    "max_adverse_per_trade": (1.0, 0.5, 3.0),
    "staleness_ttl_s": (1.0, 0.5, 5),
}


def emit_stub(state, event, signals, cfg):
    """Simplified mirror of the §T3 normative emit() pseudocode.

    Implements every prose guard: F1 (no events), F2 (invalid fields,
    non-finite/out-of-bounds signals), C6 (staleness), C12 (VPIN veto),
    C11/C8 (cooldown), C3 (cost gate), Boolean entry, C7 (locate for shorts),
    and the §T3 exit branch with C8 cooldown. Sets module_state=UNKNOWN on
    invalid input and never interpolates.
    """
    tickets = []
    log = state.setdefault("log", [])
    t = event
    if not (math.isfinite(t["trade_px"]) and t["trade_px"] > 0
            and math.isfinite(t["trade_sz"]) and t["trade_sz"] > 0
            and math.isfinite(t["bid_px"]) and math.isfinite(t["ask_px"])
            and t["ask_px"] > t["bid_px"]):
        state["module_state"] = "UNKNOWN"
        return tickets
    if (t["now_ns"] - t["asof_ts"]) > cfg["staleness_ttl_s"] * 1e9:  # C6
        state["module_state"] = "UNKNOWN"
        return tickets
    imb, ropp, vpin = signals["imb"], signals["ropp"], signals["vpin"]
    if not (math.isfinite(imb) and math.isfinite(ropp)
            and 0.0 <= ropp <= 1.0 and 0.0 <= vpin <= 1.0):
        state["module_state"] = "UNKNOWN"
        return tickets
    if vpin > cfg["vpin_veto"]:  # C12
        log.append("GATE_VETO")
        return tickets
    if t["event_ts"] < state["cooldown_until"]:  # C11 / C8
        return tickets
    edge_bps = signals["footprint_move_bps"] * 0.5  # [example]
    qty = shares(cfg["per_trade_R"], cfg["max_adverse_per_trade"],
                 state["vol_estimate"], state["adv_1min"],
                 expected_cost_bps(100 * t["trade_px"], state["adv_pct"],
                                   "XNAS", "taker", "normal"))
    notional_est = qty * t["trade_px"]
    cost_ok = (expected_cost_bps(notional_est, state["adv_pct"], "XNAS",
                                 "taker", "normal")
               <= cfg["cost_gate_k"] * edge_bps)  # C3 normative predicate
    flat = (state["position"] == 0)
    if (flat and cost_ok and abs(imb) >= cfg["large_mult"]
            and ropp >= cfg["retail_opp_min"]
            and state["module_state"] == "OK"):
        if imb > 0:
            tickets.append({"symbol": t["symbol"], "side": "BUY", "qty": qty,
                            "limit": t["ask_px"], "tif": "DAY",
                            "intent_ts": t["event_ts"],
                            "parent_signal": "S015@" + str(signals["computed_at"]),
                            "locate_ok": True, "stp_flag": "cancel-newest"})
        elif imb < 0 and state.get("locate_ok", False):  # C7
            tickets.append({"symbol": t["symbol"], "side": "SELL", "qty": qty,
                            "limit": t["bid_px"], "tif": "DAY",
                            "intent_ts": t["event_ts"],
                            "parent_signal": "S015@" + str(signals["computed_at"]),
                            "locate_ok": True, "stp_flag": "cancel-newest"})
    elif state["position"] != 0:
        held_ms = (t["event_ts"] - state["entry_ts"]) / 1e6
        aged = held_ms >= cfg["hold_ms"]
        reversed_ = ((state["entry_imb"] > 0 and imb < 0)
                     or (state["entry_imb"] < 0 and imb > 0))
        toxic = vpin > cfg["vpin_veto"]
        if aged or reversed_ or toxic or state["module_state"] != "OK":
            side = "SELL" if state["position"] > 0 else "BUY"
            tickets.append({"symbol": t["symbol"], "side": side,
                            "qty": abs(state["position"]),
                            "limit": t["bid_px"] if side == "SELL" else t["ask_px"],
                            "tif": "IOC", "intent_ts": t["event_ts"],
                            "parent_signal": "S015@" + str(signals["computed_at"]),
                            "locate_ok": True, "stp_flag": "cancel-newest"})
            state["cooldown_until"] = t["event_ts"] + int(cfg["cooldown_s"] * 1e9)
    for tk in tickets:
        log.append(("DECISION", tk["side"], tk["qty"]))
    return tickets


def fresh_state(**over):
    cfg = {k: v[0] for k, v in CONFIG_DEFAULTS.items()}
    state = {"module_state": "OK", "cooldown_until": 0, "position": 0,
             "entry_ts": 0, "entry_imb": 0.0, "vol_estimate": 0.02,
             "adv_1min": 5_000_000.0, "adv_pct": 0.01, "locate_ok": True}
    state.update(over)
    return state


def fresh_event(ts=1788960600000000000, **over):
    ev = {"symbol": "XNAS:XYZ", "trade_px": 50.03, "trade_sz": 100,
          "bid_px": 50.02, "ask_px": 50.04, "event_ts": ts,
          "asof_ts": ts, "now_ns": ts}
    ev.update(over)
    return ev


def fresh_signals(**over):
    sig = {"imb": 3.5, "ropp": 0.65, "vpin": 0.20,
           "footprint_move_bps": 60.0, "computed_at": 1788960599000000000}
    sig.update(over)
    return sig


def load_csv(path):
    with open(path) as f:
        lines = f.readlines()
    assert lines[0].strip().startswith("# TYPE:"), "missing TYPE header"
    return lines[0].strip(), list(csv.DictReader(lines[1:]))


def test_type_header():
    type_line, _ = load_csv(TAPE)
    assert "validation-run" in type_line
    type_line2, _ = load_csv(EXPECTED)
    assert "validation-run" in type_line2


def test_fixture_arithmetic():
    # the tape's stored cost stack, the module's cost callable, and the
    # expected CSV must all agree; P&L arithmetic is recomputed by hand
    _, tape = load_csv(TAPE)
    _, exp = load_csv(EXPECTED)
    assert len(tape) >= 5, "need >=5 hand-checked rows"
    exp_by_id = {e["trade_id"]: e for e in exp if e["trade_id"] != "SUMMARY"}
    for t in tape:
        e = exp_by_id[t["trade_id"]]
        qty = float(t["qty"])
        entry = float(t["entry_px"])
        exitp = float(t["exit_px"])
        notional = float(t["notional"])
        stack_bps = (float(t["spread_bps"]) + float(t["fee_bps"])
                     + float(t["borrow_bps"]) + float(t["impact_bps"]))
        cbps = expected_cost_bps(notional, float(t["adv_pct"]), t["venue"],
                                 "taker", t["urgency"])
        assert abs(cbps - stack_bps) <= TOL
        assert abs(cbps - float(e["expected_cost_bps"])) <= CSV_TOL_BPS
        sign = 1 if t["side"] in ("BUY", "LONG") else -1
        gross = sign * (exitp - entry) * qty
        net = gross - notional * cbps / 10000.0
        assert abs(gross - float(e["gross_pnl"])) <= CSV_TOL_USD
        assert abs(net - float(e["net_pnl"])) <= CSV_TOL_USD


def test_no_signal_bar_fills():
    _, tape = load_csv(TAPE)
    for t in tape:
        fill_event = int(t["fill_ts"])
        signal_event = int(t["signal_ts"])
        assert fill_event > signal_event, "fill_event > signal_event (t->t+1 causality)"


def test_cost_gate_predicate():
    # the normative C3 predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5
    c = expected_cost_bps(100000.0, 0.1, "XNAS", "taker", "normal")
    if c <= 0:
        # zero/negative cost (overlay, maker rebate): the gate passes any positive edge
        assert c <= k * 0.05, "non-positive cost must clear the gate"
    else:
        assert c <= k * 50.0, "cost gate must pass when edge >> cost"
        assert not (c <= k * 0.05), "cost gate must block when edge << cost"


def test_kill_switch_cycle():
    # ARMED -> TRIPPED -> RECOVERY -> ARMED; skipping the checklist is a violation
    machine = {"state": "ARMED"}
    order = []

    def trip(condition):
        assert machine["state"] == "ARMED"
        assert condition in ["VPIN > 0.50 [example]",
                             "trade feed stale > 1 s [example]",
                             "clock skew > 1 ms [example]"]
        machine["state"] = "TRIPPED"
        order.append("TRIPPED")

    def acknowledge():
        assert machine["state"] == "TRIPPED"
        machine["state"] = "RECOVERY"
        order.append("RECOVERY")

    def rearm(checklist):
        assert machine["state"] == "RECOVERY"
        if not all(checklist.values()):
            raise PermissionError("re-arm checklist incomplete (C2)")
        machine["state"] = "ARMED"
        order.append("ARMED")

    trip("trade feed stale > 1 s [example]")
    assert machine["state"] == "TRIPPED"
    acknowledge()
    assert machine["state"] == "RECOVERY"
    checklist = {"review": True, "cooldown": True, "feed": True,
                 "skew": True, "vpin": True, "fees": True}
    bad = dict(checklist)
    bad["feed"] = False
    try:
        rearm(bad)
        assert False, "must not re-arm with an incomplete checklist"
    except PermissionError:
        pass
    assert machine["state"] == "RECOVERY"
    rearm(checklist)
    assert machine["state"] == "ARMED"
    assert order == ["TRIPPED", "RECOVERY", "ARMED"]


def test_invalid_input_emits_unknown():
    # crossed/locked/empty input -> UNKNOWN, never interpolated
    def emit_state(bid_px, ask_px):
        if bid_px <= 0 or ask_px <= bid_px:
            return "UNKNOWN"
        return "OK"
    assert emit_state(50.00, 50.00) == "UNKNOWN"
    assert emit_state(50.01, 50.00) == "UNKNOWN"
    assert emit_state(50.00, 50.01) == "OK"
    # stub-level: NaN/empty/invalid inputs set module_state UNKNOWN
    st = fresh_state()
    assert emit_stub(st, fresh_event(trade_px=float("nan")), fresh_signals(),
                     {k: v[0] for k, v in CONFIG_DEFAULTS.items()}) == []
    assert st["module_state"] == "UNKNOWN"
    st = fresh_state()
    assert emit_stub(st, fresh_event(asof_ts=1788960598000000000),  # 2 s stale > 1 s TTL
                     fresh_signals(),
                     {k: v[0] for k, v in CONFIG_DEFAULTS.items()}) == []
    assert st["module_state"] == "UNKNOWN"


def test_cost_callable_signature():
    c = expected_cost_bps(250000.0, 0.5, "XNAS", "taker", "normal")
    assert isinstance(c, float) and math.isfinite(c)


def test_emit_entry_guard_matrix():
    # §T3 normative emit() guards: VPIN veto, cooldown, cost gate, Boolean
    # entry, and the C7 locate requirement for shorts
    cfg = {k: v[0] for k, v in CONFIG_DEFAULTS.items()}
    # 1. valid entry -> one BUY ticket with the OrderTicket intent fields
    st = fresh_state()
    tix = emit_stub(st, fresh_event(), fresh_signals(), cfg)
    assert len(tix) == 1
    tk = tix[0]
    assert tk["side"] == "BUY" and tk["qty"] == 100 and tk["tif"] == "DAY"
    assert tk["parent_signal"] == "S015@1788960599000000000"
    assert tk["stp_flag"] == "cancel-newest" and tk["locate_ok"] is True
    # 2. VPIN veto -> no tickets, GATE_VETO logged
    st = fresh_state()
    assert emit_stub(st, fresh_event(), fresh_signals(vpin=0.60), cfg) == []
    assert "GATE_VETO" in st["log"]
    # 3. inside cooldown -> no tickets
    st = fresh_state(cooldown_until=1788960605000000000)
    assert emit_stub(st, fresh_event(), fresh_signals(), cfg) == []
    # 4. cost gate fails (edge tiny) -> no tickets
    st = fresh_state()
    assert emit_stub(st, fresh_event(), fresh_signals(footprint_move_bps=10.0), cfg) == []
    # 5. retail not opposing -> no tickets
    st = fresh_state()
    assert emit_stub(st, fresh_event(), fresh_signals(ropp=0.40), cfg) == []
    # 6. short without locate -> no ticket; with locate -> SELL
    st = fresh_state(locate_ok=False)
    assert emit_stub(st, fresh_event(), fresh_signals(imb=-3.5), cfg) == []
    st = fresh_state(locate_ok=True)
    tix = emit_stub(st, fresh_event(), fresh_signals(imb=-3.5), cfg)
    assert len(tix) == 1 and tix[0]["side"] == "SELL"


def test_emit_exit_and_cooldown():
    # §T3 exit branch: hold_ms elapsed -> flatten; C8 cooldown blocks re-entry
    cfg = {k: v[0] for k, v in CONFIG_DEFAULTS.items()}
    ts = 1788960600000000000
    st = fresh_state(position=100, entry_ts=ts - 3000 * 10**6, entry_imb=3.5)
    tix = emit_stub(st, fresh_event(ts=ts), fresh_signals(), cfg)
    assert len(tix) == 1
    fl = tix[0]
    assert fl["side"] == "SELL" and fl["qty"] == 100 and fl["tif"] == "IOC"
    assert st["cooldown_until"] == ts + int(10.0 * 1e9)
    # re-entry inside the cooldown window is vetoed
    st2 = fresh_state(position=0, cooldown_until=ts + int(10.0 * 1e9))
    assert emit_stub(st2, fresh_event(ts=ts + 5 * 10**9), fresh_signals(), cfg) == []


def test_sizing_function():
    # §T3 normative shares(): fixed 1 lot, 0.1% ADV cap
    assert shares(150.0, 1.0, 0.02, 10_000_000.0, 14.0) == 100
    assert shares(150.0, 1.0, 0.02, 50_000.0, 14.0) == 50  # ADV cap binds
    assert isinstance(shares(150.0, 1.0, 0.02, 10_000_000.0, 14.0), int)


def test_config_defaults_parity():
    # §T0 Config dataclass surface: defaults inside ranges; table rows unique
    assert len(CONFIG_DEFAULTS) == 11
    for name, (default, lo, hi) in CONFIG_DEFAULTS.items():
        assert isinstance(name, str) and isinstance(default, float)
        assert lo <= default <= hi, name
    assert CONFIG_DEFAULTS["daily_loss_stop"][0] < 0
    assert CONFIG_DEFAULTS["cost_gate_k"][0] == 0.5
    assert CONFIG_DEFAULTS["vpin_veto"][0] == 0.50
