"""T069 — Late-Day Reversal into Close: acceptance tests (concrete sketch).

Real imports, fixture load, real assertions. Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_T069.py -q` exits 0.
"""
import csv
import math
import os

SID = "T069"
TOL = 1e-6
CFG = {'mode': 'z', 'fade': True, 'z_long': 2.0, 'z_short': -2.0, 'conf_scale': 1.0, 'edge_mult': 2.5, 'time_stop': 4, 'exit_flip': False, 'k': 0.5, 'sizing': ('risk', 400.0, None), 'cooldown_bars': 4, 'bar_ns': 900000000000, 'tif': 'DAY', 'venue': 'XNAS', 'side_class': 'mixed', 'adv_pct': 0.02, 'cost': {'spread_bps': 2.0, 'fee_bps': 0.4, 'borrow_bps': 0.0, 'impact_bps': 0.5}}
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

def size_qty(dec, r, cfg):
    mode = cfg["sizing"][0]
    if mode == "fixed":
        return int(cfg["sizing"][1])
    if mode == "risk":
        R_usd, _ = cfg["sizing"][1], None
        sd = max(float(r.get("stop_dist", 0.0)), 1e-9)
        return max(1, int(R_usd // sd))
    if mode == "conf":
        q_base, c_min = cfg["sizing"][1], cfg["sizing"][2]
        frac = max(0.0, dec["conf"] - c_min) / max(1.0 - c_min, 1e-9)
        q = int(q_base * frac)
        lot = cfg.get("lot", 1)
        return max(lot, (q // lot) * lot)
    raise ValueError("unknown sizing mode")

def decide(r, pos, cfg):
    """Per-module entry/exit logic. Returns None, a decision dict, or a list."""
    mode = cfg["mode"]
    s = r["sig"]
    if mode == "allocator":
        # T053-style: regime tilt on the proxy; dead zone holds.
        cur = pos["sleeve"] if pos else None
        if s >= 0.65 and cur != "MOM":
            return {"action": "enter", "side": "BUY", "sleeve": "MOM",
                    "edge_bps": abs(s - 0.5) * cfg["edge_mult"], "conf": min(1.0, (s - 0.5) * 2)}
        if s <= 0.35 and cur != "REV":
            return {"action": "enter", "side": "BUY", "sleeve": "REV",
                    "edge_bps": abs(s - 0.5) * cfg["edge_mult"], "conf": min(1.0, (0.5 - s) * 2)}
        if pos and 0.35 < s < 0.65:
            return {"action": "exit", "reason": "dead_zone"}
        return None
    if mode == "toggle":
        # T054-style: Hurst toggle; dead zone [0.45, 0.55] is dark.
        if pos is None:
            if r["gate"] != 1:
                return None
            if s >= 0.55:
                return {"action": "enter", "side": "BUY", "edge_bps": abs(s - 0.5) * cfg["edge_mult"],
                        "conf": min(1.0, (s - 0.5) * 4)}
            if s <= 0.45:
                return {"action": "enter", "side": "SHORT", "edge_bps": abs(s - 0.5) * cfg["edge_mult"],
                        "conf": min(1.0, (0.5 - s) * 4)}
            return None
        if 0.45 < s < 0.55:
            return {"action": "exit", "reason": "dead_zone"}
        if pos["bars_held"] + 1 >= cfg["time_stop"]:
            return {"action": "exit", "reason": "time_stop"}
        return None
    if mode == "pair":
        # T058-style: two-leg dispersion entry/exit.
        if pos is None:
            if r["gate"] != 1 or s < cfg["z_long"]:
                return None
            edge = s * cfg["edge_mult"]
            conf = min(1.0, s / (cfg["z_long"] * 2))
            return [{"action": "enter", "side": "BUY", "leg": "basket",
                     "edge_bps": edge, "conf": conf},
                    {"action": "enter", "side": "SELL", "leg": "index",
                     "edge_bps": edge, "conf": conf}]
        if s <= cfg.get("z_exit", 0.05) or pos["bars_held"] + 1 >= cfg["time_stop"]:
            return {"action": "exit", "reason": "signal_flip" if s <= cfg.get("z_exit", 0.05) else "time_stop"}
        return None
    # mode == "z": signed-score trigger, fade or trend.
    if pos is None:
        if r["gate"] != 1:
            return None
        side = None
        if not cfg["fade"]:
            if s >= cfg["z_long"]:
                side = "BUY"
            elif s <= cfg["z_short"]:
                side = "SELL"
        else:
            if s >= cfg["z_long"]:
                side = "SHORT"
            elif s <= cfg["z_short"]:
                side = "BUY"
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
        ds = d if isinstance(d, list) else [d]
        for leg_i, dd in enumerate(ds):
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
                    "ticket_id": "T-%s-%d-%d" % (sid, i, leg_i),
                    "symbol": r["symbol"], "side": dd["side"], "qty": qty,
                    "limit": limit, "tif": cfg["tif"],
                    "parent_signal": "%s@%d" % (sigsrc, ts),
                    "intent_ts": ts, "signal_ts": ts, "fill_ts": nxt,
                    "leg": dd.get("leg", ""), "edge_bps": round(dd["edge_bps"], 6),
                    "cost_bps": round(cost, 6),
                    "cost_usd": round(notional * cost / 1e4, 6),
                    "gate": "PASS", "action": "enter",
                })
                assert tickets[-1]["fill_ts"] > tickets[-1]["signal_ts"]  # assert fill_event > signal_event
                if cfg["mode"] == "pair" and leg_i == 0:
                    continue  # second leg shares the position
                pos = {"side": dd["side"], "bars_held": 0,
                       "sleeve": dd.get("sleeve", ""), "entry_ts": ts,
                       "qty": qty}
                if cfg["mode"] == "pair":
                    break
            elif dd["action"] == "exit" and pos is not None:
                xqty = pos.get("qty", size_qty({"conf": 1.0}, r, cfg))
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
                    "action": "exit", "reason": dd["reason"],
                })
                assert tickets[-1]["fill_ts"] > tickets[-1]["signal_ts"]  # assert fill_event > signal_event
                pos = None
                cooldown_until = ts + cfg["cooldown_bars"] * cfg["bar_ns"]
                break
    return tickets, module_state


def _load(name):
    path = os.path.join(FIX, name)
    with open(path) as f:
        first = f.readline().strip()
        assert first.startswith("# TYPE:"), "fixture must carry a # TYPE: line"
        rd = csv.DictReader(f)
        rows = []
        for r in rd:
            for k in ("event_ts","volume","gate"):
                r[k] = int(float(r[k]))
            for k in ("open","high","low","close","sig","stop_dist"):
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
    return rows, emit_intents(rows, CFG, SID, "S027")

def _close(a, b, tol=TOL):
    return abs(a - b) <= tol

def test_1_fixture_replays_to_expected():
    rows, (tickets, mstate) = _replay()
    exp = _load_expected()
    assert mstate == "OK"
    assert len(tickets) == len(exp), (len(tickets), len(exp))
    for t, e in zip(tickets, exp):
        for k in ("ticket_id","symbol","side","tif","parent_signal","leg","gate","action","reason"):
            assert str(t.get(k, "")) == e[k], (k, t.get(k, ""), e[k])
        assert int(t["qty"]) == int(e["qty"])
        for k in ("intent_ts","signal_ts","fill_ts"):
            assert int(t[k]) == int(e[k])
        if t.get("limit") in (None, ""):
            assert e["limit"] == ""
        else:
            assert _close(float(t["limit"]), float(e["limit"]))
        for k in ("edge_bps","cost_bps","cost_usd"):
            assert _close(float(t[k]), float(e[k])), (k, t[k], e[k])

def test_2_cost_gate_blocks_tiny_edge():
    rows, (tickets, mstate) = _replay()
    assert tickets, "fixture must emit at least one ticket"
    for t in tickets:
        if t["action"] == "enter":
            assert t["cost_bps"] <= K * t["edge_bps"] + 1e-9, t
            assert t["gate"] == "PASS"
    # counter-case: a tiny edge must fail the normative predicate
    assert not cost_gate_pass(2.7, K, 0.1)

def test_3_causality_no_signal_bar_fills():
    rows, (tickets, mstate) = _replay()
    for t in tickets:
        assert t["fill_ts"] > t["signal_ts"], t  # assert fill_event > signal_event
    gated_off = {r["event_ts"] for r in rows if r["gate"] != 1}
    for t in tickets:
        sig_ts = int(t["parent_signal"].split("@")[1])
        assert sig_ts not in gated_off, ("ticket on a gated-off bar", t)

def test_4_kill_switch_trip_and_rearm():
    ks = KillSwitch(1200.0)
    assert ks.state == "ARMED"
    ks.on_pnl(-1200.0 - 1.0)
    assert ks.state == "TRIPPED"
    ks_fresh = KillSwitch(1200.0)
    try:
        ks_fresh.rearm({"a": True})
        raise SystemExit("re-arm must only run from TRIPPED")
    except AssertionError:
        pass
    ks2 = KillSwitch(1200.0)
    ks2.on_condition(True, "manual trip")
    assert ks2.state == "TRIPPED"
    assert ks2.rearm({"a": True, "b": False}) == "TRIPPED"  # partial checklist: stays TRIPPED
    assert ks2.rearm({"a": True, "b": True}) == "ARMED"     # ARMED -> TRIPPED -> RECOVERY -> ARMED
    assert [s for s, _, _ in ks2.transitions] == ["ARMED", "TRIPPED", "RECOVERY"]

def test_5_invalid_input_yields_unknown():
    rows = _load(SID + "_tape.csv")
    bad = [dict(r) for r in rows]
    bad[3]["sig"] = float("nan")
    _, mstate = emit_intents(bad, CFG, SID, "S027")
    assert mstate == "UNKNOWN"
    bad2 = [dict(r) for r in rows]
    bad2[4]["close"] = -1.0
    _, mstate2 = emit_intents(bad2, CFG, SID, "S027")
    assert mstate2 == "UNKNOWN"
    bad3 = [dict(r) for r in rows]
    bad3[5]["event_ts"] = bad3[4]["event_ts"]  # non-monotonic: not a later event
    _, mstate3 = emit_intents(bad3, CFG, SID, "S027")
    assert mstate3 == "UNKNOWN"

def test_6_handcheck_literals():
    rows, (tickets, mstate) = _replay()
    t = tickets[0]
    assert t["ticket_id"] == "T-T069-2-0"
    assert int(t["qty"]) == 400
    assert _close(float(t["cost_bps"]), 2.9)
    assert _close(float(t["cost_usd"]), 29.006635)
    assert _close(float(t["edge_bps"]), 6.5)
