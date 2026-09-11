"""T059 — News-Sentiment First-Minute Momentum: acceptance tests (deep review, v1.0.1).

Concrete harness mirroring the §T3 normative pseudocode: Boolean entry guards
(S092 identified-news gate, novelty, scheduled-macro veto, story-age veto,
sentiment threshold, locate for shorts, post-exit cooldown, cost gate),
managed exits (time stop / adverse stop / story-update sign flip), the
mandated sizing function shares=f(risk_budget_R, stop_distance, vol_estimate,
ADV_cap, cost), and the kill-switch state machine ARMED -> TRIPPED ->
RECOVERY -> ARMED. Strategies emit OrderTicket intents only; the harness fills
strictly after the signal bar (fill_event > signal_event, t->t+1 causality).

Definition of done: `python3 -m pytest modules/tests/test_T059.py -q` exits 0.
"""
import csv
import math
import os

SID = "T059"
TOL = 1e-6
CFG = {
    "sent_min": 0.60, "novel_min": 0.70, "hold_secs": 60, "fixed_qty": 1000,
    "stop_cents": 15.0, "cooldown_bars": 10, "cost_gate_k": 0.5,
    "bar_ns": 1_000_000_000, "tif": "IOC", "venue": "XNAS", "side_class": "taker",
    "adv_pct": 0.05, "edge_mult": 12.0, "story_age_max_s": 60, "locate_ok": True,
    "per_trade_R": 150.0, "daily_loss_stop": -1500.0, "max_gross": 1_000_000.0,
    "cost": {"spread_bps": 2.5, "fee_bps": 0.4, "borrow_bps": 0.0, "impact_bps": 1.0},
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
    """Callable cost model - 4-component stack (single source of truth: §T2 COST block)."""
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
    """shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost) [mandated]."""
    n = risk_budget_R / max(stop_distance, 1e-9)   # R-based base [default]
    n = min(n, ADV_cap * 0.05)                      # 5% ADV participation cap [default]
    return int(n)


def validate_row(r, prev_ts):
    """F1/F2: invalid input -> UNKNOWN, never interpolate."""
    for f in ("open", "high", "low", "close", "volume", "sig", "gate",
              "novelty", "macro", "story_age_s", "stop_dist"):
        v = r.get(f)
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            return False
    if r["close"] <= 0 or r["open"] <= 0 or r["high"] < r["low"]:
        return False
    if r["event_ts"] <= prev_ts:
        return False
    return True


def decide_entry(r, cfg, cooldown_ok):
    """Boolean entry rule (§T2). Returns (side, edge_bps) or None."""
    if r["gate"] != 1:                                  # S092 identified-news flag
        return None
    if r["macro"] != 0:                                 # scheduled macro veto
        return None
    if r["novelty"] < cfg["novel_min"]:                 # duplicate-story veto
        return None
    if r["story_age_s"] > cfg["story_age_max_s"]:       # C11 stale-news veto
        return None
    if not cooldown_ok:                                 # C10 post-exit cooldown
        return None
    s = r["sig"]
    if abs(s) < cfg["sent_min"]:
        return None
    side = "BUY" if s > 0 else "SELL"
    if side == "SELL" and not cfg["locate_ok"]:         # C7 locate check
        return None
    return side, abs(s) * cfg["edge_mult"]


def decide_exit(r, pos, cfg):
    """Exit rule (§T2). Returns reason or None."""
    held_ns = r["event_ts"] - pos["entry_ts"]
    if pos["side"] == "BUY":
        adverse_c = (pos["entry_px"] - r["close"]) * 100.0
    else:
        adverse_c = (r["close"] - pos["entry_px"]) * 100.0
    if held_ns >= cfg["hold_secs"] * 1e9:
        return "time_stop"
    if adverse_c > cfg["stop_cents"]:
        return "stop_loss"
    if r["gate"] == 1 and ((r["sig"] > 0) != (pos["entry_s"] > 0)):
        return "sig_flip"   # sentiment sign flips on a story update
    return None


def emit_intents(rows, cfg, sid, sigsrc):
    """emit(state, signals, cfg) -> list[OrderTicket intent dicts]. Normative sketch."""
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
        # fill strictly after the signal bar (t->t+1 causality, C4)
        nxt = rows[i + 1]["event_ts"] if i + 1 < len(rows) else ts + cfg["bar_ns"]
        nxt = nxt if nxt > ts else ts + cfg["bar_ns"]
        assert nxt > ts, "causality: fill_event > signal_event"
        if pos is not None:
            reason = decide_exit(r, pos, cfg)
            if reason is not None:
                xnot = pos["qty"] * r["close"]
                xcost = expected_cost_bps(xnot, cfg["adv_pct"], cfg["venue"],
                                          cfg["side_class"], "normal", comp)
                tickets.append({
                    "ticket_id": "T-%s-%d-X" % (sid, i),
                    "symbol": r["symbol"],
                    "side": "SELL" if pos["side"] == "BUY" else "BUY",
                    "qty": pos["qty"],
                    "limit": "", "tif": "DAY",
                    "parent_signal": "%s@%d" % (sigsrc, ts),
                    "intent_ts": ts, "signal_ts": ts, "fill_ts": nxt,
                    "leg": "", "edge_bps": 0.0,
                    "cost_bps": round(xcost, 6),
                    "cost_usd": round(xnot * xcost / 1e4, 6),
                    "gate": "N/A", "action": "exit", "reason": reason,
                })
                assert tickets[-1]["fill_ts"] > tickets[-1]["signal_ts"]
                pos = None
                cooldown_until = ts + cfg["cooldown_bars"] * cfg["bar_ns"]  # C10
            continue  # exit has priority; no same-bar re-entry; held bars pass
        d = decide_entry(r, cfg, ts >= cooldown_until)
        if d is None:
            continue
        side, edge = d
        qty = size_shares(cfg["per_trade_R"], cfg["stop_cents"] / 100.0,
                          None, 1_000_000, None)
        notional = qty * r["close"]
        cost = expected_cost_bps(notional, cfg["adv_pct"], cfg["venue"],
                                 cfg["side_class"], "normal", comp)
        if not cost_gate_pass(cost, cfg["cost_gate_k"], edge):
            continue  # C2 bona-fide intent: sub-threshold edge -> no ticket
        tickets.append({
            "ticket_id": "T-%s-%d-0" % (sid, i),
            "symbol": r["symbol"], "side": side, "qty": qty,
            "limit": "", "tif": cfg["tif"],
            "parent_signal": "%s@%d" % (sigsrc, ts),
            "intent_ts": ts, "signal_ts": ts, "fill_ts": nxt,
            "leg": "", "edge_bps": round(edge, 6),
            "cost_bps": round(cost, 6),
            "cost_usd": round(notional * cost / 1e4, 6),
            "gate": "PASS", "action": "enter", "reason": "",
        })
        assert tickets[-1]["fill_ts"] > tickets[-1]["signal_ts"]  # C4
        pos = {"side": side, "qty": qty, "entry_ts": ts,
               "entry_px": r["close"], "entry_s": r["sig"]}
    return tickets, module_state


def _load(name):
    path = os.path.join(FIX, name)
    with open(path) as f:
        first = f.readline().strip()
        assert first.startswith("# TYPE:"), "fixture must carry a # TYPE: line"
        rd = csv.DictReader(f)
        rows = []
        for r in rd:
            for k in ("event_ts", "volume", "gate", "macro"):
                r[k] = int(float(r[k]))
            for k in ("open", "high", "low", "close", "sig", "novelty",
                      "story_age_s", "stop_dist"):
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
    return rows, emit_intents(rows, CFG, SID, "S091")


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


def test_2_cost_gate_predicate():
    rows, (tickets, mstate) = _replay()
    assert tickets, "fixture must emit at least one ticket"
    for t in tickets:
        if t["action"] == "enter":
            assert t["cost_bps"] <= K * t["edge_bps"] + 1e-9, t
            assert t["gate"] == "PASS"
    # normative counter-case: tiny edge must fail the predicate
    assert not cost_gate_pass(3.9, K, 0.61 * 12.0)  # 0.5*7.32=3.66 < 3.9
    # vetoed story: |s|=0.61 passes sent_min but fails the cost gate -> no ticket
    rows2 = _load(SID + "_tape.csv")
    r = dict(rows2[5])
    r["sig"] = 0.61
    ts = [dict(x) for x in rows2]
    ts[5] = r
    tk2, _ = emit_intents(ts, CFG, SID, "S091")
    assert not any(t["ticket_id"] == "T-T059-5-0" for t in tk2), tk2


def test_3_causality_guards_and_stale_news_veto():
    rows, (tickets, mstate) = _replay()
    for t in tickets:
        assert t["fill_ts"] > t["signal_ts"], t  # assert fill_event > signal_event
    # no tickets on non-story bars (gate==0) and no re-entry inside the cooldown
    story_ts = {r["event_ts"] for r in rows if r["gate"] == 1}
    for t in tickets:
        if t["action"] == "enter":
            assert int(t["signal_ts"]) in story_ts, ("entry on non-story bar", t)
    enter_ts = [int(t["signal_ts"]) for t in tickets if t["action"] == "enter"]
    exit_ts = [int(t["signal_ts"]) for t in tickets if t["action"] == "exit"]
    assert all(enter_ts[i] < exit_ts[i] for i in range(min(len(enter_ts), len(exit_ts))))
    # C11: a 120 s-old story is vetoed even with a strong signal
    rows2 = [dict(x) for x in rows]
    rows2[5]["story_age_s"] = 120.0
    tk2, _ = emit_intents(rows2, CFG, SID, "S091")
    assert not any(t["ticket_id"] == "T-T059-5-0" for t in tk2)


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
    ks2.on_condition(True, "feed latency > 5 s vs exchange")
    assert ks2.state == "TRIPPED"
    assert ks2.rearm({"a": True, "b": False}) == "TRIPPED"  # partial checklist: stays TRIPPED
    assert ks2.rearm({"a": True, "b": True}) == "ARMED"     # ARMED -> TRIPPED -> RECOVERY -> ARMED
    assert [s for s, _, _ in ks2.transitions] == ["ARMED", "TRIPPED", "RECOVERY"]


def test_5_invalid_input_yields_unknown():
    rows = _load(SID + "_tape.csv")
    bad = [dict(r) for r in rows]
    bad[3]["sig"] = float("nan")
    _, mstate = emit_intents(bad, CFG, SID, "S091")
    assert mstate == "UNKNOWN"
    bad2 = [dict(r) for r in rows]
    bad2[4]["close"] = -1.0
    _, mstate2 = emit_intents(bad2, CFG, SID, "S091")
    assert mstate2 == "UNKNOWN"
    bad3 = [dict(r) for r in rows]
    bad3[5]["event_ts"] = bad3[4]["event_ts"]  # non-monotonic: not a later event
    _, mstate3 = emit_intents(bad3, CFG, SID, "S091")
    assert mstate3 == "UNKNOWN"
    bad4 = [dict(r) for r in rows]
    bad4[5]["novelty"] = float("nan")  # story metadata corrupt -> UNKNOWN
    _, mstate4 = emit_intents(bad4, CFG, SID, "S091")
    assert mstate4 == "UNKNOWN"


def test_6_handcheck_literals():
    rows, (tickets, mstate) = _replay()
    by_id = {t["ticket_id"]: t for t in tickets}
    assert len(tickets) == 5
    e1 = by_id["T-T059-5-0"]
    assert e1["side"] == "BUY" and int(e1["qty"]) == 1000
    assert _close(float(e1["cost_bps"]), 3.9)
    assert _close(float(e1["cost_usd"]), 97.5234)
    assert _close(float(e1["edge_bps"]), 8.64)          # 0.72 * 12.0
    x1 = by_id["T-T059-13-X"]
    assert x1["side"] == "SELL" and x1["reason"] == "stop_loss"
    assert _close(float(x1["cost_usd"]), 97.461)        # 1000 * 249.9000 * 3.9/1e4
    e2 = by_id["T-T059-25-0"]
    assert e2["side"] == "SELL" and _close(float(e2["edge_bps"]), 9.0)
    assert e2["gate"] == "PASS"                          # 3.9 <= 0.5 * 9.0
    x2 = by_id["T-T059-30-X"]
    assert x2["side"] == "BUY" and x2["reason"] == "sig_flip"
    e3 = by_id["T-T059-42-0"]
    assert e3["side"] == "BUY" and _close(float(e3["edge_bps"]), 8.16)
    assert e3["gate"] == "PASS"                          # 3.9 <= 0.5 * 8.16


def test_7_sizing_and_cooldown():
    # mandated sizing honors per-trade R (150 / 0.15 -> 1000) [example]
    assert size_shares(150.0, 0.15, None, 1_000_000, None) == 1000
    # ADV cap binds: 5% of a 2,000-share ADV -> 100 shares
    assert size_shares(150.0, 0.15, None, 2000, None) == 100
    # the bar-33 story (strong, novel) fires nothing: 10-bar post-exit cooldown
    rows, (tickets, _) = _replay()
    enter_ids = {t["ticket_id"] for t in tickets if t["action"] == "enter"}
    assert "T-T059-33-0" not in enter_ids
    # the duplicate (novelty 0.45), scheduled-macro, and sub-threshold stories
    # also fire nothing
    assert "T-T059-15-0" not in enter_ids
    assert "T-T059-18-0" not in enter_ids
    assert "T-T059-20-0" not in enter_ids
    # CFG mirrors the §T0 Config dataclass defaults (do-not-regress)
    for k, v in {"sent_min": 0.60, "novel_min": 0.70, "hold_secs": 60,
                 "fixed_qty": 1000, "stop_cents": 15.0, "cooldown_bars": 10,
                 "cost_gate_k": 0.5}.items():
        assert CFG[k] == v, (k, CFG[k], v)
