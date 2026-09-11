"""T073 — ASVI Attention Reversal: acceptance tests (concrete sketch).

Real imports, fixture load, real assertions. Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_T073.py -q` exits 0.
"""
import csv
import math
import os

SID = "T073"
TOL = 1e-6
# CFG mirrors the §T2 Config dataclass. Fee-component tags per the tag law:
# per_share_comm/min_order_comm [documented — IBKR-style fixed pricing],
# sec_bps_blended/taf_per_share [documented — SEC FY2026 advisory / FINRA TAF],
# spread_bps [example], borrow_bps [default], impact_bps [example],
# press_up/press_down/part_cap [default], ref_price [example].
CFG = {
    'mode': 'z', 'fade': True, 'z_long': 2.5, 'z_short': -2.5,
    'press_up': 1.5, 'press_down': -1.5, 'conf_scale': 1.0,
    'edge_mult': 2.0, 'time_stop': 5, 'exit_flip': False,
    'k': 0.5, 'sizing': ('risk', 600.0, None), 'part_cap': 0.05,
    'borrow_bps_per_day': 0.0, 'cooldown_bars': 5, 'bar_ns': 86400000000000,
    'tif': 'DAY', 'venue': 'XNAS', 'side_class': 'mixed', 'adv_pct': 0.02,
    'cost': {
        'per_share_comm': 0.005, 'min_order_comm': 1.00, 'ref_price': 250.0,
        'sec_bps_blended': 0.103, 'taf_per_share': 0.000090,
        'spread_bps': 1.5, 'borrow_bps': 0.0, 'impact_bps': 0.0,
    },
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


"""Concrete sketch of the <SID> emit harness (module contract sketch)."""
import math


def expected_cost_bps(notional, adv_pct, venue, side, urgency, comp):
    """Callable cost model - 4-component stack (single source of truth: §T2 COST block).

    Fee basis: retail fixed-pricing commission ($0.005/share, min $1.00/order)
    [documented]; SEC Section 31 FY2026 $20.60/M on sell legs, blended per side
    [documented]; FINRA TAF $0.000090/share, max $4.50/trade, blended per side
    [documented]; $250 reference price is an [example] scaling assumption.
    """
    shares = notional / comp["ref_price"]
    comm_bps = max(comp["min_order_comm"],
                   comp["per_share_comm"] * shares) / notional * 1e4
    sec_bps = comp["sec_bps_blended"]
    taf_bps = comp["taf_per_share"] * shares / notional * 1e4
    fee_bps = comm_bps + sec_bps + taf_bps
    if side == "maker":
        fee_bps = -abs(fee_bps) * 0.5  # rebate proxy [example]
    return comp["spread_bps"] + fee_bps + comp["borrow_bps"] + comp["impact_bps"]


def cost_gate_pass(cost_bps, k, edge_bps):
    """Normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps."""
    return cost_bps <= k * edge_bps


def validate_row(r, prev_ts):
    """F1/F2: invalid input -> UNKNOWN, never interpolate."""
    for f in ("open", "high", "low", "close", "volume", "sig", "gate",
              "pressure", "stop_dist", "adv_shares"):
        v = r.get(f)
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            return False
    if r["close"] <= 0 or r["open"] <= 0 or r["high"] < r["low"]:
        return False
    if r["stop_dist"] <= 0 or r["adv_shares"] <= 0:
        return False
    if r["event_ts"] <= prev_ts:
        return False
    return True


def size_qty(dec, r, cfg):
    """shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost).

    Dollar-risk quantity, capped by the ADV participation cap; the cost
    component enters through the C2 cost-gate veto (not through qty).
    """
    mode = cfg["sizing"][0]
    if mode == "risk":
        R_usd = cfg["sizing"][1]
        sd = max(float(r.get("stop_dist", 0.0)), 1e-9)
        n_risk = int(R_usd // sd)
        n_adv = int(cfg["part_cap"] * float(r.get("adv_shares", 0.0)))
        return max(1, min(n_risk, n_adv))
    raise ValueError("unknown sizing mode")


def decide(r, pos, cfg):
    """Per-module entry/exit logic. Returns None or a decision dict."""
    s = r["sig"]
    p = r["pressure"]
    # mode == "z": signed-score trigger, fade or trend, with the S045
    # pressure confirmation gate (§T2 entry rule, Boolean).
    if pos is None:
        if r["gate"] != 1:
            return None
        side = None
        if cfg["fade"]:
            if s >= cfg["z_long"] and p >= cfg["press_up"]:
                side = "SHORT"
            elif s <= cfg["z_short"] and p <= cfg["press_down"]:
                side = "BUY"
        else:
            if s >= cfg["z_long"]:
                side = "BUY"
            elif s <= cfg["z_short"]:
                side = "SELL"
        if side is None:
            return None
        conf = min(1.0, abs(s) / cfg["conf_scale"])
        return {"action": "enter", "side": side,
                "edge_bps": abs(s) * cfg["edge_mult"], "conf": conf}
    if pos["bars_held"] + 1 >= cfg["time_stop"]:
        return {"action": "exit", "reason": "time_stop"}
    if cfg["exit_flip"]:
        if pos["side"] == "BUY" and s < 0:
            return {"action": "exit", "reason": "sig_flip"}
        if pos["side"] in ("SELL", "SHORT") and s > 0:
            return {"action": "exit", "reason": "sig_flip"}
    if abs(s) < 0.1 * cfg["z_long"]:
        return {"action": "exit", "reason": "exit_signal"}
    return None


def emit_intents(rows, cfg, sid, sigsrc):
    """emit(state, signals, cfg) -> list[OrderTicket intent dicts]. Sketch."""
    if not rows:
        return [], "UNKNOWN"  # F1: empty signals -> UNKNOWN
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
        dd = d
        if dd["action"] == "enter" and pos is None and ts >= cooldown_until:
            qty = size_qty(dd, r, cfg)
            notional = qty * r["close"]
            cost = expected_cost_bps(notional, cfg["adv_pct"], cfg["venue"],
                                     cfg["side_class"], "normal", comp)
            # normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
            if not cost_gate_pass(cost, cfg["k"], dd["edge_bps"]):
                continue  # C2 bona-fide intent: sub-threshold -> no ticket
            limit = None
            if cfg["side_class"] in ("maker", "mixed"):
                half = r["close"] * comp["spread_bps"] / 2 / 1e4
                limit = round(r["close"] - half if dd["side"] in ("BUY",) else r["close"] + half, 4)
            tickets.append({
                "ticket_id": "T-%s-%d-%d" % (sid, i, 0),
                "symbol": r["symbol"], "side": dd["side"], "qty": qty,
                "limit": limit, "tif": cfg["tif"],
                "parent_signal": "%s@%d" % (sigsrc, ts),
                "intent_ts": ts, "signal_ts": ts, "fill_ts": nxt,
                "leg": "", "edge_bps": round(dd["edge_bps"], 6),
                "cost_bps": round(cost, 6),
                "cost_usd": round(notional * cost / 1e4, 6),
                "borrow_usd": 0.0,
                "gate": "PASS", "action": "enter", "reason": "",
            })
            assert tickets[-1]["fill_ts"] > tickets[-1]["signal_ts"]  # assert fill_event > signal_event
            pos = {"side": dd["side"], "bars_held": 0,
                   "entry_ts": ts, "qty": qty}
        elif dd["action"] == "exit" and pos is not None:
            xqty = pos.get("qty", size_qty({"conf": 1.0}, r, cfg))
            xnot = xqty * r["close"]
            xcost = expected_cost_bps(xnot, cfg["adv_pct"], cfg["venue"],
                                      cfg["side_class"], "normal", comp)
            days_held = pos["bars_held"] + 1  # entry bar -> exit bar, calendar days
            borrow_usd = cfg["borrow_bps_per_day"] * days_held * xnot / 1e4
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
                "cost_usd": round(xnot * xcost / 1e4, 6),
                "borrow_usd": round(borrow_usd, 6),
                "gate": "N/A", "action": "exit", "reason": dd["reason"],
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
            for k in ("open", "high", "low", "close", "sig",
                      "pressure", "stop_dist"):
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
    return rows, emit_intents(rows, CFG, SID, "S099")


def _close(a, b, tol=TOL):
    return abs(a - b) <= tol


def test_1_fixture_replays_to_expected():
    rows, (tickets, mstate) = _replay()
    exp = _load_expected()
    assert mstate == "OK"
    assert len(tickets) == len(exp), (len(tickets), len(exp))
    for t, e in zip(tickets, exp):
        for k in ("ticket_id", "symbol", "side", "tif", "parent_signal",
                  "leg", "gate", "action", "reason"):
            assert str(t.get(k, "")) == e[k], (k, t.get(k, ""), e[k])
        assert int(t["qty"]) == int(e["qty"])
        for k in ("intent_ts", "signal_ts", "fill_ts"):
            assert int(t[k]) == int(e[k])
        if t.get("limit") in (None, ""):
            assert e["limit"] == ""
        else:
            assert _close(float(t["limit"]), float(e["limit"]))
        for k in ("edge_bps", "cost_bps", "cost_usd", "borrow_usd"):
            assert _close(float(t[k]), float(e[k])), (k, t[k], e[k])


def test_2_cost_gate_blocks_tiny_edge():
    rows, (tickets, mstate) = _replay()
    assert tickets, "fixture must emit at least one ticket"
    for t in tickets:
        if t["action"] == "enter":
            assert t["cost_bps"] <= K * t["edge_bps"] + 1e-9, t
            assert t["gate"] == "PASS"
    # counter-case: a tiny edge must fail the normative predicate
    assert not cost_gate_pass(1.81, K, 0.1)
    # the documented-basis fee stack is material: entry ticket cost is
    # commission+SEC+TAF based, not the old 2.7 bps plug
    t = tickets[0]
    assert 1.5 < float(t["cost_bps"]) < 3.0, t


def test_3_causality_no_signal_bar_fills():
    rows, (tickets, mstate) = _replay()
    for t in tickets:
        assert t["fill_ts"] > t["signal_ts"], t  # assert fill_event > signal_event
    gated_off = {r["event_ts"] for r in rows if r["gate"] != 1}
    for t in tickets:
        sig_ts = int(t["parent_signal"].split("@")[1])
        assert sig_ts not in gated_off, ("ticket on a gated-off bar", t)


def test_4_kill_switch_trip_and_rearm():
    ks = KillSwitch(1800.0)
    assert ks.state == "ARMED"
    ks.on_pnl(-1800.0 - 1.0)
    assert ks.state == "TRIPPED"
    ks_fresh = KillSwitch(1800.0)
    try:
        ks_fresh.rearm({"a": True})
        raise SystemExit("re-arm only from TRIPPED")
    except AssertionError:
        pass
    ks2 = KillSwitch(1800.0)
    ks2.on_condition(True, "manual trip")
    assert ks2.state == "TRIPPED"
    assert ks2.rearm({"a": True, "b": False}) == "TRIPPED"  # partial checklist: stays TRIPPED
    assert ks2.rearm({"a": True, "b": True}) == "ARMED"     # ARMED -> TRIPPED -> RECOVERY -> ARMED
    assert [s for s, _, _ in ks2.transitions] == ["ARMED", "TRIPPED", "RECOVERY"]


def test_5_invalid_input_yields_unknown():
    rows = _load(SID + "_tape.csv")
    bad = [dict(r) for r in rows]
    bad[3]["sig"] = float("nan")
    _, mstate = emit_intents(bad, CFG, SID, "S099")
    assert mstate == "UNKNOWN"
    bad2 = [dict(r) for r in rows]
    bad2[4]["close"] = -1.0
    _, mstate2 = emit_intents(bad2, CFG, SID, "S099")
    assert mstate2 == "UNKNOWN"
    bad3 = [dict(r) for r in rows]
    bad3[5]["event_ts"] = bad3[4]["event_ts"]  # non-monotonic: not a later event
    _, mstate3 = emit_intents(bad3, CFG, SID, "S099")
    assert mstate3 == "UNKNOWN"
    bad4 = [dict(r) for r in rows]
    bad4[6]["pressure"] = float("inf")  # non-finite feature -> UNKNOWN
    _, mstate4 = emit_intents(bad4, CFG, SID, "S099")
    assert mstate4 == "UNKNOWN"
    t0, ms0 = emit_intents([], CFG, SID, "S099")
    assert t0 == [] and ms0 == "UNKNOWN"  # F1: empty signals -> UNKNOWN


def test_6_handcheck_literals():
    rows, (tickets, mstate) = _replay()
    t = tickets[0]
    assert t["ticket_id"] == "T-T073-2-0"
    assert int(t["qty"]) == 240
    assert _close(float(t["cost_bps"]), 1.80659, tol=1e-4)
    # cost_usd = notional * cost_bps / 1e4, notional = 240 * 250.0572
    notional = 240 * 250.0572
    assert _close(float(t["cost_usd"]), notional * float(t["cost_bps"]) / 1e4, tol=1e-4)
    assert _close(float(t["edge_bps"]), 5.6)
    # exit ticket carries the borrow-accrual mechanism (0.0 at the [default] rate)
    x = [tt for tt in tickets if tt["action"] == "exit"][0]
    assert x["ticket_id"] == "T-T073-7-X"
    assert _close(float(x["borrow_usd"]), 0.0)


def test_7_pressure_veto_blocks_entry():
    # fixture bar 12: z=2.9 >= 2.5 but pressure 0.8 < 1.5 -> no entry (§T2 entry rule)
    rows, (tickets, mstate) = _replay()
    ids = [t["ticket_id"] for t in tickets]
    assert "T-T073-12-0" not in ids
    # synthetic: panic bar with pressure confirmation DOES enter the long fade
    rows2 = _load(SID + "_tape.csv")
    syn = [dict(rows2[0])]
    syn[0]["event_ts"] = 1790000000000000000
    syn[0]["sig"] = -3.0
    syn[0]["pressure"] = -2.0
    tickets2, ms2 = emit_intents(syn, CFG, SID, "S099")
    assert ms2 == "OK"
    assert len(tickets2) == 1 and tickets2[0]["side"] == "BUY", tickets2


def test_8_adv_participation_cap():
    rows, (tickets, mstate) = _replay()
    assert int(tickets[0]["qty"]) == 240  # risk qty binds; ADV cap does not
    # synthetic: thin name -> ADV cap binds
    rows2 = _load(SID + "_tape.csv")
    thin = [dict(rows2[2])]
    thin[0]["adv_shares"] = 2000  # 5% of 2000 = 100 shares
    tickets2, ms2 = emit_intents(thin, CFG, SID, "S099")
    assert ms2 == "OK"
    assert int(tickets2[0]["qty"]) == 100, tickets2


def test_9_borrow_accrual_on_exit():
    cfg2 = dict(CFG)
    cfg2["borrow_bps_per_day"] = 50.0  # [example] stress rate
    rows = _load(SID + "_tape.csv")
    tickets2, ms2 = emit_intents(rows, cfg2, SID, "S099")
    x = [t for t in tickets2 if t["action"] == "exit"][0]
    days_held = 5  # entry bar 2 -> exit bar 7
    xnot = int(x["qty"]) * rows[7]["close"]
    assert _close(float(x["borrow_usd"]), 50.0 * days_held * xnot / 1e4, tol=1e-4)
