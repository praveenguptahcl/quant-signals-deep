"""T070 — MOC Auction-Pin Trader: acceptance tests (concrete sketch).

Real imports, fixture load, real assertions. Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_T070.py -q` exits 0.

Deep-review v1.1.0 changes vs v1.0.0:
- entries gated on the lean window [session_close - lean_min, session_close] ET
  (the v1.0.0 sketch never enforced "in lean window" from the entry rule);
- exit priority is explicit: imbalance flip -> stop -> time_stop(auction print) -> exit_signal;
- exit_flip defaults True (a flipped imbalance exits immediately, per T9 row 1);
- sizing is shares=f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost)
  with ADV participation cap + cost-budget veto + stop/vol floor;
- fixture clock shifted to the 15:45-15:56 ET lean window (19:45-19:56 UTC,
  2026-09-09); exit ticket is now T-T070-7-X (reason sig_flip) and the
  one-pin-per-day cooldown blocks the i=8 short entry.
"""
import csv
import math
import os

SID = "T070"
TOL = 1e-6
SESSION_CLOSE_NS = 1788984000000000000  # 2026-09-09 20:00:00 UTC = 16:00 ET
CFG = {
    'mode': 'z', 'fade': False,
    'z_long': 5.0, 'z_short': -5.0,          # imbalance thresholds, $M [example]
    'conf_scale': 1.0, 'edge_mult': 1.5,     # edge_bps = |I_t| * edge_mult [default]
    'exit_flip': True,                        # flipped imbalance exits immediately [default]
    'time_stop': 9,                           # bars -> auction-print/time stop [example]
    'stop_mult': 0.5,                         # stop = stop_mult * ATR$ [default]
    'k': 0.5,                                 # cost-gate k [default]
    'R_usd': 500.0,                           # per-trade dollar risk [example]
    'participation_cap': 0.02,                # <= 2% of ADV shares [default]
    'cost_budget_frac': 0.5,                  # veto if est. cost > 50% of R [default]
    'vol_floor_mult': 0.25,                   # stop never tighter than 0.25 * vol [default]
    'lean_min': 15,                           # lean window minutes before close [example]
    'session_close_ns': SESSION_CLOSE_NS,
    'cooldown_bars': 390,                     # one pin per day [default]
    'bar_ns': 60000000000, 'tif': 'DAY',
    'venue': 'XNAS', 'side_class': 'taker', 'adv_pct': 0.02,
    'cost': {'spread_bps': 2.0, 'fee_bps': 0.4, 'borrow_bps': 0.0, 'impact_bps': 0.5},
}
K = 0.5
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fixtures")


class KillSwitch:
    """Kill-switch state machine: ARMED -> TRIPPED -> RECOVERY -> ARMED."""
    def __init__(self, daily_loss_stop):
        self.state = "ARMED"
        self.daily_loss_stop = daily_loss_stop
        self.transitions = []

    def _go(self, to, reason):
        self.transitions.append((self.state, to, reason))
        self.state = to

    def on_pnl(self, day_pnl):
        if self.state == "ARMED" and day_pnl <= -abs(self.daily_loss_stop):
            self._go("TRIPPED", "daily_loss_stop breached")
        return self.state

    def on_condition(self, tripped, reason):
        if self.state == "ARMED" and tripped:
            self._go("TRIPPED", reason)
        return self.state

    def rearm(self, checklist):
        """Re-arm checklist: all items must be True. TRIPPED -> RECOVERY -> ARMED."""
        assert self.state == "TRIPPED", "re-arm only from TRIPPED"
        if all(checklist.values()):
            self._go("RECOVERY", "checklist green")
            self._go("ARMED", "recovery verified")
        return self.state


def expected_cost_bps(notional, adv_pct, venue, side, urgency, comp):
    """Callable cost model - 4-component stack (single source of truth: COST block)."""
    spread = comp["spread_bps"]
    fee = comp["fee_bps"]
    if side == "maker":
        fee = -abs(fee) * 0.5  # rebate proxy [example]
    borrow = comp["borrow_bps"]
    impact = comp["impact_bps"]
    return spread + fee + borrow + impact

def cost_gate_pass(cost_bps, k, edge_bps):
    """Normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps."""
    return cost_bps <= k * edge_bps

def in_lean_window(ts, cfg):
    """Lean window = [session_close - lean_min, session_close] (ET session clock)."""
    lo = cfg["session_close_ns"] - cfg["lean_min"] * 60_000_000_000
    return lo <= ts <= cfg["session_close_ns"]

def validate_row(r, prev_ts):
    """F1/F2: invalid input -> UNKNOWN, never interpolate."""
    for f in ("open", "high", "low", "close", "volume", "sig", "gate",
              "stop_dist", "adv_shares"):
        v = r.get(f)
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            return False
    if r["close"] <= 0 or r["open"] <= 0 or r["high"] < r["low"]:
        return False
    if r["stop_dist"] < 0 or r["adv_shares"] <= 0:
        return False
    if r["event_ts"] <= prev_ts:
        return False
    return True

def size_shares(risk_budget_R, stop_distance, vol_estimate, adv_shares, cost_bps,
                price, participation_cap, cost_budget_frac, vol_floor_mult):
    """shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost).

    risk-limited, ADV participation-capped, cost-budget vetoed, vol-floored.
    Returns 0 when the cost budget vetoes (caller emits no ticket).
    """
    stop_distance = max(stop_distance, vol_floor_mult * vol_estimate)  # never tighter than noise
    q_risk = int(risk_budget_R // max(stop_distance, 1e-9))
    q_adv = int(participation_cap * adv_shares)                         # ADV_cap
    cost_per_share = price * cost_bps / 1e4
    q_cost = int((cost_budget_frac * risk_budget_R) // max(cost_per_share, 1e-12))
    if q_cost < 1:
        return 0  # C2: cost budget veto
    return max(1, min(q_risk, q_adv, q_cost))

def decide(r, pos, cfg):
    """Per-module entry/exit logic. Returns None or a decision dict.

    Exit priority (normative): imbalance flip -> stop -> time_stop -> exit_signal.
    """
    s = r["sig"]  # signed MOC imbalance, $M [example]
    if pos is None:
        if r["gate"] != 1:
            return None
        if not in_lean_window(r["event_ts"], cfg):
            return None  # C2: outside the lean window -> no intent
        side = None
        if s >= cfg["z_long"]:
            side = "BUY"
        elif s <= cfg["z_short"]:
            side = "SHORT"
        if side is None:
            return None
        conf = min(1.0, abs(s) / cfg["conf_scale"])
        return {"action": "enter", "side": side,
                "edge_bps": abs(s) * cfg["edge_mult"], "conf": conf}
    # exits, in priority order
    if cfg["exit_flip"]:
        if pos["side"] == "BUY" and s < 0:
            return {"action": "exit", "reason": "sig_flip"}
        if pos["side"] in ("SELL", "SHORT") and s > 0:
            return {"action": "exit", "reason": "sig_flip"}
    stop_dist = cfg["stop_mult"] * pos["stop_dist"]
    if pos["side"] == "BUY" and r["close"] <= pos["entry_price"] - stop_dist:
        return {"action": "exit", "reason": "stop"}
    if pos["side"] in ("SELL", "SHORT") and r["close"] >= pos["entry_price"] + stop_dist:
        return {"action": "exit", "reason": "stop"}
    if pos["bars_held"] + 1 >= cfg["time_stop"]:
        return {"action": "exit", "reason": "time_stop"}
    if abs(s) < 0.1 * cfg["z_long"]:
        return {"action": "exit", "reason": "exit_signal"}
    return None

def emit_intents(rows, cfg, sid, sigsrc):
    """emit(state, signals, cfg) -> list[OrderTicket intent dicts]. Sketch."""
    tickets = []
    pos = None
    cooldown_until = -1
    prev_ts = -1
    module_state = "OK"
    comp = cfg["cost"]
    for i, r in enumerate(rows):
        ts = r["event_ts"]
        if not validate_row(r, prev_ts):
            module_state = "UNKNOWN"  # F1/F2: never interpolate
            prev_ts = ts
            continue
        prev_ts = ts
        nxt_ts = rows[i + 1]["event_ts"] if i + 1 < len(rows) else -1
        # F1/F2: a corrupt later row must not break causality on this row;
        # fall back to the bar grid so the normative assert below always holds.
        nxt = nxt_ts if nxt_ts > ts else ts + cfg["bar_ns"]
        assert nxt > ts, "causality: fill_event > signal_event"
        d = decide(r, pos, cfg)
        if d is None:
            if pos is not None:
                pos["bars_held"] += 1
            continue
        if d["action"] == "enter" and pos is None and ts >= cooldown_until:
            qty = size_shares(cfg["R_usd"], r["stop_dist"], r["stop_dist"],
                              r["adv_shares"], comp["spread_bps"] + comp["fee_bps"]
                              + comp["borrow_bps"] + comp["impact_bps"],
                              r["close"], cfg["participation_cap"],
                              cfg["cost_budget_frac"], cfg["vol_floor_mult"])
            if qty < 1:
                continue  # C2: cost-budget veto -> no ticket
            notional = qty * r["close"]
            cost = expected_cost_bps(notional, cfg["adv_pct"], cfg["venue"],
                                     cfg["side_class"], "normal", comp)
            # normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
            if not cost_gate_pass(cost, cfg["k"], d["edge_bps"]):
                continue  # C2 bona-fide intent: sub-threshold -> no ticket
            limit = None
            if cfg["side_class"] in ("maker", "mixed"):
                half = r["close"] * comp["spread_bps"] / 2 / 1e4
                limit = round(r["close"] - half if d["side"] == "BUY" else r["close"] + half, 4)
            tickets.append({
                "ticket_id": "T-%s-%d-%d" % (sid, i, 0),
                "symbol": r["symbol"], "side": d["side"], "qty": qty,
                "limit": limit, "tif": cfg["tif"],
                "parent_signal": "%s@%d" % (sigsrc, ts),
                "intent_ts": ts, "signal_ts": ts, "fill_ts": nxt,
                "leg": "", "edge_bps": round(d["edge_bps"], 6),
                "cost_bps": round(cost, 6),
                "cost_usd": round(notional * cost / 1e4, 6),
                "gate": "PASS", "action": "enter",
            })
            assert tickets[-1]["fill_ts"] > tickets[-1]["signal_ts"]  # assert fill_event > signal_event
            pos = {"side": d["side"], "bars_held": 0,
                   "entry_price": r["close"], "stop_dist": r["stop_dist"],
                   "entry_ts": ts, "qty": qty}
        elif d["action"] == "exit" and pos is not None:
            xqty = pos["qty"]
            xnot = xqty * r["close"]
            xcost = expected_cost_bps(xnot, cfg["adv_pct"], cfg["venue"],
                                      cfg["side_class"], "normal", comp)
            tickets.append({
                "ticket_id": "T-%s-%d-X" % (sid, i),
                "symbol": r["symbol"],
                "side": "SELL" if pos["side"] == "BUY" else "BUY",
                "qty": xqty,
                "limit": None, "tif": "DAY",
                "parent_signal": "%s@%d" % (sigsrc, ts),
                "intent_ts": ts, "signal_ts": ts, "fill_ts": nxt,
                "leg": "", "edge_bps": 0.0,
                "cost_bps": round(xcost, 6),
                "cost_usd": round(xnot * xcost / 1e4, 6), "gate": "N/A",
                "action": "exit", "reason": d["reason"],
            })
            assert tickets[-1]["fill_ts"] > tickets[-1]["signal_ts"]  # assert fill_event > signal_event
            pos = None
            cooldown_until = ts + cfg["cooldown_bars"] * cfg["bar_ns"]
    return tickets, module_state


def _load(name):
    path = os.path.join(FIX, name)
    with open(path) as f:
        first = f.readline().strip()
        assert first.startswith("# TYPE:"), "fixture must carry a # TYPE: line"
        rd = csv.DictReader(f)
        rows = []
        for r in rd:
            for k in ("event_ts", "volume", "gate", "adv_shares"):
                r[k] = int(float(r[k]))
            for k in ("open", "high", "low", "close", "sig", "stop_dist"):
                r[k] = float(r[k])
            rows.append(r)
    return rows

def _load_expected():
    path = os.path.join(FIX, SID + "_expected.csv")
    with open(path) as f:
        first = f.readline().strip()
        assert first.startswith("# TYPE:"), "expected must carry a # TYPE: line"
        return list(csv.DictReader(f))

def _replay():
    rows = _load(SID + "_tape.csv")
    return rows, emit_intents(rows, CFG, SID, "S033")

def _close(a, b, tol=TOL):
    return abs(a - b) <= tol

def _mkrow(ts, sig, close=250.0, gate=1, stop_dist=1.0, adv=5_000_000):
    return {"event_ts": ts, "symbol": "AAA", "open": close, "high": close + 0.2,
            "low": close - 0.2, "close": close, "volume": 100000, "sig": sig,
            "gate": gate, "stop_dist": stop_dist, "adv_shares": adv}

def _in_window_ts(offset_min=5):
    return SESSION_CLOSE_NS - offset_min * 60_000_000_000

def test_1_fixture_replays_to_expected():
    rows, (tickets, mstate) = _replay()
    exp = _load_expected()
    assert mstate == "OK"
    assert len(tickets) == len(exp), (len(tickets), len(exp))
    for t, e in zip(tickets, exp):
        for k in ("ticket_id", "symbol", "side", "tif", "parent_signal", "leg", "gate", "action", "reason"):
            assert str(t.get(k, "")) == e[k], (k, t.get(k, ""), e[k])
        assert int(t["qty"]) == int(e["qty"])
        for k in ("intent_ts", "signal_ts", "fill_ts"):
            assert int(t[k]) == int(e[k])
        if t.get("limit") in (None, ""):
            assert e["limit"] == ""
        else:
            assert _close(float(t["limit"]), float(e["limit"]))
        for k in ("edge_bps", "cost_bps", "cost_usd"):
            assert _close(float(t[k]), float(e[k])), (k, t[k], e[k])

def test_2_cost_gate_and_short_mirror():
    rows, (tickets, mstate) = _replay()
    assert tickets, "fixture must emit at least one ticket"
    for t in tickets:
        if t["action"] == "enter":
            assert t["cost_bps"] <= K * t["edge_bps"] + 1e-9, t
            assert t["gate"] == "PASS"
    # counter-case: a tiny edge must fail the normative predicate
    assert not cost_gate_pass(2.7, K, 0.1)
    # mirror branch: a large SELL imbalance enters SHORT in the lean window
    ts0 = _in_window_ts(10)
    rws = [_mkrow(ts0, -6.0), _mkrow(ts0 + 60_000_000_000, -6.5)]
    tkts, ms = emit_intents(rws, CFG, SID, "S033")
    assert ms == "OK"
    assert len(tkts) == 1 and tkts[0]["side"] == "SHORT" and tkts[0]["action"] == "enter"

def test_3_causality_no_signal_bar_fills():
    rows, (tickets, mstate) = _replay()
    for t in tickets:
        assert t["fill_ts"] > t["signal_ts"], t  # assert fill_event > signal_event
    gated_off = {r["event_ts"] for r in rows if r["gate"] != 1}
    for t in tickets:
        sig_ts = int(t["parent_signal"].split("@")[1])
        assert sig_ts not in gated_off, ("ticket on a gated-off bar", t)

def test_4_kill_switch_trip_and_rearm():
    ks = KillSwitch(1500.0)
    assert ks.state == "ARMED"
    ks.on_pnl(-1500.0 - 1.0)
    assert ks.state == "TRIPPED"
    ks_fresh = KillSwitch(1500.0)
    try:
        ks_fresh.rearm({"a": True})
        raise SystemExit("re-arm only from TRIPPED")
    except AssertionError:
        pass
    ks2 = KillSwitch(1500.0)
    ks2.on_condition(True, "manual trip")
    assert ks2.state == "TRIPPED"
    assert ks2.rearm({"a": True, "b": False}) == "TRIPPED"  # partial checklist: stays TRIPPED
    assert ks2.rearm({"a": True, "b": True}) == "ARMED"     # ARMED -> TRIPPED -> RECOVERY -> ARMED
    assert [s for s, _, _ in ks2.transitions] == ["ARMED", "TRIPPED", "RECOVERY"]

def test_5_invalid_input_yields_unknown():
    rows = _load(SID + "_tape.csv")
    bad = [dict(r) for r in rows]
    bad[3]["sig"] = float("nan")
    _, mstate = emit_intents(bad, CFG, SID, "S033")
    assert mstate == "UNKNOWN"
    bad2 = [dict(r) for r in rows]
    bad2[4]["close"] = -1.0
    _, mstate2 = emit_intents(bad2, CFG, SID, "S033")
    assert mstate2 == "UNKNOWN"
    bad3 = [dict(r) for r in rows]
    bad3[5]["event_ts"] = bad3[4]["event_ts"]  # non-monotonic: not a later event
    _, mstate3 = emit_intents(bad3, CFG, SID, "S033")
    assert mstate3 == "UNKNOWN"

def test_6_handcheck_literals():
    rows, (tickets, mstate) = _replay()
    t = tickets[0]
    assert t["ticket_id"] == "T-T070-2-0"
    assert int(t["qty"]) == 500
    assert _close(float(t["cost_bps"]), 2.9)
    assert _close(float(t["cost_usd"]), 36.258294)
    assert _close(float(t["edge_bps"]), 9.75)
    x = tickets[1]
    assert x["ticket_id"] == "T-T070-7-X"
    assert x["side"] == "SELL" and x["action"] == "exit"
    assert x["reason"] == "sig_flip"
    assert _close(float(x["cost_usd"]), 36.241851)
    assert _close(float(x["edge_bps"]), 0.0)

def test_7_lean_window_veto_and_one_pin_per_day():
    # a large imbalance OUTSIDE the lean window must not emit (entry rule)
    ts_out = SESSION_CLOSE_NS - 30 * 60_000_000_000  # 15:30 ET, before the window
    tkts, ms = emit_intents([_mkrow(ts_out, 8.0),
                             _mkrow(ts_out + 60_000_000_000, 8.0)], CFG, SID, "S033")
    assert ms == "OK" and tkts == [], "no entries outside the lean window"
    # one pin per day: after the fixture's sig_flip exit, the i=8 short is blocked
    rows, (tickets, mstate) = _replay()
    sig_ts = {int(t["parent_signal"].split("@")[1]) for t in tickets}
    assert base_ts(8) not in sig_ts, "post-exit cooldown must block the i=8 entry"

def base_ts(i):
    return 1788983100000000000 + i * 60_000_000_000

def test_8_stop_exit():
    ts0 = _in_window_ts(10)
    rws = [_mkrow(ts0, 6.0, close=250.0),
           _mkrow(ts0 + 60_000_000_000, 6.5, close=249.4)]  # 0.6 adverse > 0.5 stop
    tkts, ms = emit_intents(rws, CFG, SID, "S033")
    assert ms == "OK"
    assert len(tkts) == 2, tkts
    assert tkts[1]["action"] == "exit" and tkts[1]["reason"] == "stop"
