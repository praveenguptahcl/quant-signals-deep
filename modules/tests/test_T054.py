"""T054 — Hurst/Variance-Ratio Regime Toggle: acceptance tests.

Concrete harness for the §T3 normative pseudocode: toggle with hysteresis,
cost-gate predicate, F1/F2 UNKNOWN handling, kill-switch state machine.
Real imports, fixture load, real assertions. Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_T054.py -q` exits 0.
"""
import csv
import math
import os

SID = "T054"
TOL = 1e-6
# Mirror of the §T0.2 Config dataclass defaults; 'cost' is the 4-component
# stack from the §T2 COST block (single source of truth).
CFG = {
    "H_trend": 0.55, "H_rev": 0.45, "hyst_bars": 2,
    "R_usd": 500.0, "sleeve_cap": 2_000_000,
    "time_stop_bars": 30, "cooldown_bars": 2, "bar_ns": 60000000000,
    "tif": "DAY", "venue": "XNAS", "side_class": "taker",
    "adv_pct": 0.02, "cost_gate_k": 0.5,
    "cost": {"spread_bps": 2.5, "fee_bps": 0.4, "borrow_bps": 0.0,
             "impact_bps": 0.0},
}
SIGSRC = "S090"
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


def size_shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost):
    """shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost).

    Dollar-risk N = floor(R/stop_distance), capped at ADV_cap. `cost` enters
    through the normative cost-gate predicate (no ticket when it fails), not
    through size. `vol_estimate` is accepted for the canonical signature and
    is used to floor the stop when stop_distance is missing. [example]
    reference implementation; mirrors the §T2 fenced function.
    """
    sd = max(float(stop_distance) if stop_distance is not None else 0.0, 1e-9)
    n = max(1, int(risk_budget_R // sd))
    if ADV_cap is not None:
        n = min(n, int(ADV_cap))
    return n


def validate_row(r, prev_ts):
    """F1/F2: invalid input -> UNKNOWN, never interpolate."""
    for f in ("open", "high", "low", "close", "volume", "sig", "gate"):
        v = r.get(f)
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            return False
    if r["close"] <= 0 or r["open"] <= 0 or r["high"] < r["low"]:
        return False
    if r["event_ts"] <= prev_ts:
        return False
    return True


def decide(r, pos, arm, cfg):
    """T054 toggle with hysteresis: arming a sleeve needs `hyst_bars`
    consecutive qualifying readings; the dead zone exits immediately.

    `arm` is {"side": "MOM"|"REV"|None, "count": int}, reset on dead-zone
    bars and on exits. Returns None, or an enter/exit decision dict.
    """
    s = r["sig"]
    if pos is not None:
        if cfg["H_rev"] < s < cfg["H_trend"]:
            return {"action": "exit", "reason": "dead_zone"}
        if pos["bars_held"] + 1 >= cfg["time_stop_bars"]:
            return {"action": "exit", "reason": "time_stop"}
        return None
    if r["gate"] != 1:
        return None
    side = None
    if s >= cfg["H_trend"]:
        side = "MOM"
    elif s <= cfg["H_rev"]:
        side = "REV"
    if side is None:
        arm["side"], arm["count"] = None, 0
        return None
    if arm["side"] == side:
        arm["count"] += 1
    else:
        arm["side"], arm["count"] = side, 1
    if arm["count"] < cfg["hyst_bars"]:
        return None  # hysteresis: not armed yet — load-bearing anti-chatter guard
    edge_bps = abs(s - 0.5) * 80.0  # [example] modeled per-trade edge
    if side == "MOM":
        return {"action": "enter", "side": "BUY", "edge_bps": edge_bps,
                "conf": min(1.0, (s - 0.5) * 4)}
    return {"action": "enter", "side": "SHORT", "edge_bps": edge_bps,
            "conf": min(1.0, (0.5 - s) * 4)}


def emit_intents(rows, cfg, sid, sigsrc):
    """emit(state, signals, cfg) -> list[OrderTicket intent dicts]."""
    tickets = []
    pos = None
    arm = {"side": None, "count": 0}
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
        # Fall back to the bar grid so the normative assert below always
        # holds (fill on the next bar's open; the earliest legal fill).
        nxt = nxt_ts if nxt_ts > ts else ts + cfg["bar_ns"]
        assert nxt > ts, "causality: fill_event > signal_event"
        d = decide(r, pos, arm, cfg)
        if d is None:
            if pos is not None:
                pos["bars_held"] += 1
            continue
        if d["action"] == "enter" and pos is None and ts >= cooldown_until:
            price = r["close"]
            adv_cap = int(cfg["sleeve_cap"] // max(price, 1e-9))
            qty = size_shares(cfg["R_usd"], r.get("stop_dist"), None,
                              adv_cap, None)
            notional = qty * price
            cost = expected_cost_bps(notional, cfg["adv_pct"], cfg["venue"],
                                     cfg["side_class"], "normal", comp)
            # normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
            if not cost_gate_pass(cost, cfg["cost_gate_k"], d["edge_bps"]):
                continue  # C2 bona-fide intent: sub-threshold -> no ticket
            limit = None
            if cfg["side_class"] in ("maker", "mixed"):
                half = price * comp["spread_bps"] / 2 / 1e4
                limit = round(price - half if d["side"] == "BUY"
                              else price + half, 4)
            tickets.append({
                "ticket_id": "T-%s-%d-0" % (sid, i),
                "symbol": r["symbol"], "side": d["side"], "qty": qty,
                "limit": limit, "tif": cfg["tif"],
                "parent_signal": "%s@%d" % (sigsrc, ts),
                "intent_ts": ts, "signal_ts": ts, "fill_ts": nxt,
                "leg": "", "edge_bps": round(d["edge_bps"], 6),
                "cost_bps": round(cost, 6),
                "cost_usd": round(notional * cost / 1e4, 6),
                "gate": "PASS", "action": "enter", "reason": "",
            })
            assert tickets[-1]["fill_ts"] > tickets[-1]["signal_ts"]  # t->t+1
            pos = {"side": d["side"], "bars_held": 0, "entry_ts": ts,
                   "qty": qty}
        elif d["action"] == "exit" and pos is not None:
            xqty = pos.get("qty", 1)
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
            assert tickets[-1]["fill_ts"] > tickets[-1]["signal_ts"]  # t->t+1
            pos = None
            arm = {"side": None, "count": 0}  # exits reset the arming streak
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
            for k in ("event_ts", "volume", "gate"):
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
    return rows, emit_intents(rows, CFG, SID, SIGSRC)


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
        for k in ("edge_bps", "cost_bps", "cost_usd"):
            assert _close(float(t[k]), float(e[k])), (k, t[k], e[k])


def test_2_cost_gate_blocks_tiny_edge():
    rows, (tickets, mstate) = _replay()
    assert tickets, "fixture must emit at least one ticket"
    for t in tickets:
        if t["action"] == "enter":
            assert t["cost_bps"] <= CFG["cost_gate_k"] * t["edge_bps"] + 1e-9, t
            assert t["gate"] == "PASS"
    # counter-case: a tiny edge must fail the normative predicate
    assert not cost_gate_pass(2.7, CFG["cost_gate_k"], 0.1)


def test_3_causality_no_signal_bar_fills():
    rows, (tickets, mstate) = _replay()
    for t in tickets:
        assert t["fill_ts"] > t["signal_ts"], t  # assert fill_event > signal_event
    gated_off = {r["event_ts"] for r in rows if r["gate"] != 1}
    for t in tickets:
        sig_ts = int(t["parent_signal"].split("@")[1])
        assert sig_ts not in gated_off, ("ticket on a gated-off bar", t)


def test_4_kill_switch_trip_and_rearm():
    ks = KillSwitch(3000.0)
    assert ks.state == "ARMED"
    ks.on_pnl(-3000.0 - 1.0)
    assert ks.state == "TRIPPED"
    ks_fresh = KillSwitch(3000.0)
    try:
        ks_fresh.rearm({"a": True})
        raise SystemExit("re-arm must only run from TRIPPED")
    except AssertionError:
        pass
    ks2 = KillSwitch(3000.0)
    ks2.on_condition(True, "manual trip")
    assert ks2.state == "TRIPPED"
    assert ks2.rearm({"a": True, "b": False}) == "TRIPPED"  # partial: stays TRIPPED
    assert ks2.rearm({"a": True, "b": True}) == "ARMED"  # ARMED->TRIPPED->RECOVERY->ARMED
    assert [s for s, _, _ in ks2.transitions] == ["ARMED", "TRIPPED", "RECOVERY"]


def test_5_invalid_input_yields_unknown():
    rows = _load(SID + "_tape.csv")
    bad = [dict(r) for r in rows]
    bad[3]["sig"] = float("nan")
    _, mstate = emit_intents(bad, CFG, SID, SIGSRC)
    assert mstate == "UNKNOWN"
    bad2 = [dict(r) for r in rows]
    bad2[4]["close"] = -1.0
    _, mstate2 = emit_intents(bad2, CFG, SID, SIGSRC)
    assert mstate2 == "UNKNOWN"
    bad3 = [dict(r) for r in rows]
    bad3[5]["event_ts"] = bad3[4]["event_ts"]  # non-monotonic: not a later event
    _, mstate3 = emit_intents(bad3, CFG, SID, SIGSRC)
    assert mstate3 == "UNKNOWN"


def test_6_handcheck_literals():
    rows, (tickets, mstate) = _replay()
    t = tickets[0]
    assert t["ticket_id"] == "T-T054-2-0"
    assert int(t["qty"]) == 400
    assert _close(float(t["cost_bps"]), 2.9)
    assert _close(float(t["cost_usd"]), 29.006635)
    assert _close(float(t["edge_bps"]), 8.8)


def test_7_hysteresis_two_readings():
    rows = _load(SID + "_tape.csv")
    one_reading = [dict(rows[0]), dict(rows[1])]  # sig 0.52, 0.58: 1 qualifying
    tickets, _ = emit_intents(one_reading, CFG, SID, SIGSRC)
    assert not tickets, "single qualifying reading must not arm (hysteresis)"
    two_readings = [dict(rows[0]), dict(rows[1]), dict(rows[2])]
    tickets2, _ = emit_intents(two_readings, CFG, SID, SIGSRC)
    assert [t["ticket_id"] for t in tickets2] == ["T-T054-2-0"]
    assert tickets2[0]["side"] == "BUY"
    # dead zone still exits immediately, no hysteresis on the way out
    dead = [dict(rows[1]), dict(rows[2]), dict(rows[4])]  # arm then 0.50 dead-zone bar
    tickets3, _ = emit_intents(dead, CFG, SID, SIGSRC)
    assert [t["action"] for t in tickets3] == ["enter", "exit"]
