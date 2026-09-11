"""Acceptance tests for T046 - Straddle-Implied Move Fade.

Template v1.0.0. Loads the fixture tape, runs the module's reference emit()
(normative pseudocode via process_bar), and asserts the TYPE header,
fixture-vs-expected agreement (per ticket: two-leg straddle entries/exits),
causality (no-signal-bar fills), the cost-gate predicate, kill-switch
trip/re-arm, invalid-input handling, and the delta-hedge rule.

Run: python3 -m pytest modules/tests/test_T046.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T046_tape.csv"
EXPECTED = FIX / "T046_expected.csv"

TOL = 1e-9  # tolerance on float comparisons


@dataclass(frozen=True)
class OrderTicket:
    """OrderTicket intents only (Appendix C v1.0.0); never wire orders."""
    symbol: str
    side: str            # BUY | SELL | SHORT - intent, not a wire order
    qty: int             # contracts for options legs, shares for stock hedge legs
    limit: float | None  # limit price; None = marketable intent
    tif: str             # DAY | IOC | FOK | GTC | OPG | CLS
    ticket_id: str       # module-generated idempotency key (leg encoded: -C/-P/-H)
    parent_signal: str   # "S<nnn>@<computed_at_ns>" - full provenance
    intent_ts: int       # int64 ns UTC - when the intent was emitted
    state: str           # NEW | WORKING | ... (intent-side mirror only)


@dataclass
class Config:
    sid: str = "T046"
    implied_mult: float = 1.5
    event_window_d: int = 3
    max_tenor_d: int = 14
    cost_gate_k: float = 0.5
    daily_loss_stop_pct: float = 2.0
    risk_R_usd: float = 250.0
    stop_premium_frac: float = 0.50
    adv_cap_pct: float = 1.0
    hedge_delta_tol: float = 0.10
    hedge_min_shares: int = 50
    spread_full_bps: float = 10.0
    taker_fee_bps: float = 1.0
    maker_rebate_bps: float = -0.2
    borrow_bps: float = 0.0
    impact_k: float = 20.0
    venue: str = "primary"
    default_side: str = "SHORT"


class KillSwitch:
    """Kill-switch state machine: ARMED -> TRIPPED -> RECOVERY -> ARMED."""

    def __init__(self):
        self.state = "ARMED"
        self.trips = []

    def trip(self, ts, reason):
        if self.state == "ARMED":
            self.state = "TRIPPED"
            self.trips.append((int(ts), str(reason)))

    def begin_recovery(self):
        if self.state == "TRIPPED":
            self.state = "RECOVERY"

    def rearm(self, checklist_ok):
        """Re-arm only from RECOVERY with every checklist item True."""
        if self.state == "RECOVERY" and all(checklist_ok):
            self.state = "ARMED"
            return True
        return False


def expected_cost_bps(notional, adv_pct, venue, side, urgency, cfg):
    """4-component cost stack (COST-block callable)."""
    spread_bps = cfg.spread_full_bps / 2.0
    fee_bps = cfg.maker_rebate_bps if side == "maker" else cfg.taker_fee_bps
    borrow_bps = cfg.borrow_bps  # 0.0: no stock borrow in steady state (C7 vetoes HTB)
    impact_bps = cfg.impact_k * math.sqrt(max(adv_pct, 0.0) / 100.0)
    if urgency == "high":
        impact_bps *= 1.5
    return spread_bps + fee_bps + borrow_bps + impact_bps


def size_straddle(risk_R_usd, stop_premium_frac, straddle_px, vol_est_move,
                  adv_contracts, cost_usd_est, cfg):
    """contracts = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost)."""
    premium_at_risk = stop_premium_frac * straddle_px * 100.0  # USD per straddle
    eff_R = max(risk_R_usd - cost_usd_est, 0.0)
    raw = eff_R / max(premium_at_risk, 1e-9)
    return max(1, min(int(raw), int(cfg.adv_cap_pct / 100.0 * adv_contracts)))


def process_bar(state, bar, cfg):
    """One bar through the strategy. Returns (tickets, module_state, note).

    Mirrors the module's normative pseudocode: F1/F2 validation -> kill
    switch -> exit/stop/hedge on open position -> entry rule with cost gate.
    Earliest fill for a bar-t intent is bar t+1's open (t -> t+1).
    """
    ks = state["kill"]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if (bar["close"] <= 0 or bar["straddle_px"] <= 0
            or bar["market_state"] != "CONTINUOUS_TRADING"
            or bar["asof_ts"] < bar["event_ts"]):
        state["position"] = 0
        state["contracts"] = 0
        return [], "UNKNOWN", "invalid-input"
    # Kill switch: TRIPPED/RECOVERY blocks everything; breach trips it
    if ks.state != "ARMED":
        return [], "OFF", "kill-" + ks.state.lower()
    if bar["daily_pnl_pct"] <= -cfg.daily_loss_stop_pct:
        ks.trip(bar["event_ts"], "daily-loss-stop")
        state["position"] = 0
        state["contracts"] = 0
        return [], "OFF", "kill-trip"
    pos = state.get("position", 0)
    if pos != 0:
        # Exits first: event passed, stop (thesis broken), or DTE guard;
        # exits never cost-gated
        if (bar["event_passed"] == 1 or bar["move_realized"] >= state["entry_implied"]
                or bar["dte"] <= 2):
            tickets = [
                OrderTicket(symbol=bar["symbol"], side="BUY", qty=state["contracts"],
                            limit=None, tif="DAY",
                            ticket_id="%s-%04dx-%s" % (cfg.sid, int(bar["bar"]), leg),
                            parent_signal="S070@%d" % bar["event_ts"],
                            intent_ts=bar["event_ts"], state="NEW")
                for leg in ("C", "P")]
            state["position"] = 0
            state["contracts"] = 0
            return tickets, "OK", "exit"
        # Delta hedge: re-center when net delta breaches tolerance
        dn = bar["delta_net"]
        hs = round(abs(dn) * state["contracts"] * 100)
        if abs(dn) > cfg.hedge_delta_tol and hs >= cfg.hedge_min_shares:
            ht = OrderTicket(symbol=bar["symbol"],
                             side="SHORT" if dn > 0 else "BUY", qty=hs,
                             limit=None, tif="DAY",
                             ticket_id="%s-%04d-H" % (cfg.sid, int(bar["bar"])),
                             parent_signal="S070@%d" % bar["event_ts"],
                             intent_ts=bar["event_ts"], state="NEW")
            return [ht], "OK", "hedge"
        return [], "OK", "hold"
    # Flat: entry rule as Boolean expression over the consumed SignalVectors
    in_window = bar["event_active"] == 1
    ratio_ok = bar["implied_move"] >= cfg.implied_mult * bar["har_move"]
    if ratio_ok and in_window and bar["informed_flag"] == 0 and bar["ts_gate_ok"] == 1:
        qty0 = size_straddle(cfg.risk_R_usd, cfg.stop_premium_frac,
                             bar["straddle_px"], bar["implied_move"],
                             bar["adv_contracts"], 0.0, cfg)
        notional = qty0 * bar["straddle_px"] * 100.0
        cost = expected_cost_bps(notional, bar["adv_pct"], cfg.venue,
                                 "taker", bar["urgency"], cfg)
        # Normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
        if cost <= cfg.cost_gate_k * bar["edge_bps"]:
            cost_usd = cost * notional / 1e4
            qty = size_straddle(cfg.risk_R_usd, cfg.stop_premium_frac,
                                bar["straddle_px"], bar["implied_move"],
                                bar["adv_contracts"], cost_usd, cfg)
            tickets = [
                OrderTicket(symbol=bar["symbol"], side="SHORT", qty=qty,
                            limit=None, tif="DAY",
                            ticket_id="%s-%04d-%s" % (cfg.sid, int(bar["bar"]), leg),
                            parent_signal="S070@%d" % bar["event_ts"],
                            intent_ts=bar["event_ts"], state="NEW")
                for leg in ("C", "P")]
            state["position"] = -1
            state["contracts"] = qty
            state["entry_implied"] = bar["implied_move"]
            return tickets, "OK", "entry"
        return [], "OK", "gate-block"
    return [], "OK", "flat"


CFG = Config()


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({
            "bar": int(r["bar"]), "event_ts": int(r["event_ts"]),
            "asof_ts": int(r["asof_ts"]), "symbol": r["symbol"],
            "close": float(r["close"]), "straddle_px": float(r["straddle_px"]),
            "implied_move": float(r["implied_move"]), "har_move": float(r["har_move"]),
            "event_active": int(r["event_active"]), "event_passed": int(r["event_passed"]),
            "informed_flag": int(r["informed_flag"]),
            "move_realized": float(r["move_realized"]),
            "ts_gate_ok": int(r["ts_gate_ok"]), "delta_net": float(r["delta_net"]),
            "edge_bps": float(r["edge_bps"]), "adv_pct": float(r["adv_pct"]),
            "adv_contracts": float(r["adv_contracts"]), "urgency": r["urgency"],
            "market_state": r["market_state"],
            "daily_pnl_pct": float(r["daily_pnl_pct"]),
            "dte": int(r["dte"]),
        })
    return rows


def expected():
    return load_csv(EXPECTED)


def fresh_state():
    return {"position": 0, "contracts": 0, "entry_implied": 0.0, "kill": KillSwitch()}


def run_tape():
    st = fresh_state()
    out = []
    for b in tape():
        tickets, ms, note = process_bar(st, b, CFG)
        out.append((b, tickets, ms, note))
    return out


# ------------------------------------------------------------------- tests
def test_type_header_and_columns():
    """Fixture files carry the TYPE header and the expected columns."""
    for path in (TAPE, EXPECTED):
        with open(path) as f:
            first = f.readline().strip()
        assert first.startswith("# TYPE:"), path
    tcols = set(load_csv(TAPE)[0].keys())
    ecols = set(load_csv(EXPECTED)[0].keys())
    assert {"event_ts", "asof_ts", "close", "implied_move", "har_move",
            "event_active", "event_passed", "informed_flag",
            "market_state"} <= tcols
    assert {"intent_ts", "action", "qty", "leg", "cost_call_bps",
            "gate_pass", "module_state"} <= ecols
    assert len(load_csv(TAPE)) == 12
    assert len(load_csv(EXPECTED)) == 14  # 12 bars + 2 extra leg rows


def _row_key(t, tickets, ms, note):
    """Expected-row key: (bar, leg) where leg comes from the ticket id."""
    rows = []
    if tickets:
        suffix_to_leg = {"C": "call", "P": "put", "H": "hedge"}
        for t in tickets:
            leg = suffix_to_leg[t.ticket_id.rsplit("-", 1)[-1]]
            rows.append((t, leg))
    else:
        rows.append((None, ""))
    return rows


def test_fixture_recomputes_to_expected():
    """Reference process_bar reproduces the expected CSV row by row, per ticket."""
    exp = {(int(r["bar"]), r["leg"]): r for r in expected()}
    for b, tickets, ms, note in run_tape():
        keyed = _row_key(b, tickets, ms, note)
        assert len(keyed) == len([1 for k in exp if k[0] == b["bar"]]), b["bar"]
        for t, leg in keyed:
            w = exp[(b["bar"], leg)]
            want_action = t.side if t else "HOLD"
            assert w["action"] == want_action, (b["bar"], leg)
            assert int(w["qty"]) == (t.qty if t else 0), (b["bar"], leg)
            assert w["module_state"] == ms, (b["bar"], leg)
            assert w["note"] == note, (b["bar"], leg)
            # cost call evaluated on the planned (cost_est=0) size at this bar
            qty0 = size_straddle(CFG.risk_R_usd, CFG.stop_premium_frac,
                                 b["straddle_px"], b["implied_move"],
                                 b["adv_contracts"], 0.0, CFG)
            cost = expected_cost_bps(qty0 * b["straddle_px"] * 100.0,
                                     b["adv_pct"], CFG.venue, "taker",
                                     b["urgency"], CFG)
            assert math.isclose(float(w["cost_call_bps"]), cost, rel_tol=TOL)
            assert w["gate_pass"] == str(cost <= CFG.cost_gate_k * b["edge_bps"])
            if t is not None:
                assert t.qty > 0
                assert t.side in ("BUY", "SELL", "SHORT")
                assert t.intent_ts == b["event_ts"]
                assert t.ticket_id.startswith(CFG.sid)
                assert t.parent_signal == "S070@%d" % b["event_ts"]


def test_two_leg_entry_and_exit():
    """A straddle entry emits both legs; an exit closes both legs at state qty."""
    st = fresh_state()
    bars = tape()
    t3, ms3, n3 = process_bar(st, bars[3], CFG)
    assert n3 == "entry" and ms3 == "OK"
    assert len(t3) == 2 and {t.side for t in t3} == {"SHORT"}
    assert [t.qty for t in t3] == [1, 1]
    assert {t.ticket_id.rsplit("-", 1)[-1] for t in t3} == {"C", "P"}
    assert st["contracts"] == 1 and st["position"] == -1
    t4, _, n4 = process_bar(st, bars[4], CFG)
    assert t4 == [] and n4 == "hold"  # position open, no exit yet
    t6, ms6, n6 = process_bar(st, bars[6], CFG)
    assert n6 == "exit" and ms6 == "OK"
    assert len(t6) == 2 and {t.side for t in t6} == {"BUY"}
    assert [t.qty for t in t6] == [1, 1]
    assert st["position"] == 0 and st["contracts"] == 0


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    bars = tape()
    exp = [r for r in expected() if r["intent_ts"]]
    for r in exp:
        i = int(r["bar"])
        signal_event = int(r["intent_ts"])
        fill_event = bars[i + 1]["event_ts"]  # earliest fill: next bar's open
        assert fill_event > signal_event, "signal-bar fill at bar %d" % i


def test_cost_gate_predicate():
    """Normative predicate: expected_cost_bps(...) <= k * edge_bps."""
    bars = tape()
    entry = bars[3]
    qty0 = size_straddle(CFG.risk_R_usd, CFG.stop_premium_frac,
                         entry["straddle_px"], entry["implied_move"],
                         entry["adv_contracts"], 0.0, CFG)
    cost_bps = expected_cost_bps(qty0 * entry["straddle_px"] * 100.0,
                                 entry["adv_pct"], CFG.venue, "taker",
                                 entry["urgency"], CFG)
    assert cost_bps <= CFG.cost_gate_k * entry["edge_bps"]  # entry clears
    blocked = bars[7]
    cost7 = expected_cost_bps(qty0 * blocked["straddle_px"] * 100.0,
                              blocked["adv_pct"], CFG.venue, "taker",
                              blocked["urgency"], CFG)
    assert not (cost7 <= CFG.cost_gate_k * blocked["edge_bps"])  # tiny edge blocks
    assert blocked["implied_move"] < CFG.implied_mult * blocked["har_move"]  # ratio also blocks


def test_kill_switch_trip_and_rearm():
    """ARMED -> TRIPPED blocks intents; checklist re-arm restores ARMED."""
    st = fresh_state()
    bars = tape()
    for b in bars[:9]:
        tickets, ms, note = process_bar(st, b, CFG)
    assert st["kill"].state == "ARMED", "kill must not trip before bar 9"
    b9 = bars[9]
    t9, ms9, note9 = process_bar(st, b9, CFG)
    assert t9 == [] and ms9 == "OFF" and note9 == "kill-trip"
    assert st["kill"].state == "TRIPPED"
    # still tripped on the next bar: no intents while TRIPPED
    t10, ms10, note10 = process_bar(st, bars[10], CFG)
    assert t10 == [] and ms10 == "OFF" and note10 == "kill-tripped"
    # re-arm checklist: RECOVERY + all-true checklist -> ARMED
    st["kill"].begin_recovery()
    assert st["kill"].state == "RECOVERY"
    assert st["kill"].rearm([True, True, True, True, True]) is True
    assert st["kill"].state == "ARMED"
    # and a partial checklist must NOT re-arm
    st["kill"].trip(b9["event_ts"], "retest")
    st["kill"].begin_recovery()
    assert st["kill"].rearm([True, True, False, True, True]) is False
    assert st["kill"].state == "RECOVERY"


def test_invalid_input_unknown():
    """F1/F2: halted or invalid bars -> UNKNOWN, never interpolate."""
    st = fresh_state()
    bars = tape()
    t8, ms8, note8 = process_bar(st, bars[8], CFG)  # HALTED bar
    assert t8 == [] and ms8 == "UNKNOWN" and note8 == "invalid-input"
    bad = dict(bars[3])
    bad["close"] = -1.0  # invalid price
    t, ms, _ = process_bar(fresh_state(), bad, CFG)
    assert t == [] and ms == "UNKNOWN"
    stale = dict(bars[3])
    stale["asof_ts"] = stale["event_ts"] - 1  # asof before event: F1 violation
    t, ms, _ = process_bar(fresh_state(), stale, CFG)
    assert t == [] and ms == "UNKNOWN"


def test_delta_hedge_rule():
    """Breach of hedge_delta_tol emits a correctly sized stock hedge intent."""
    bars = tape()
    st = fresh_state()
    process_bar(st, bars[3], CFG)  # open the short straddle
    assert st["contracts"] == 1
    # synthetic: delta breach with 10 contracts -> 150 shares >= hedge_min_shares
    st["contracts"] = 10
    hedge_bar = dict(bars[4])
    hedge_bar["delta_net"] = 0.15
    hedge_bar["move_realized"] = 0.002  # below the stop
    tickets, ms, note = process_bar(st, hedge_bar, CFG)
    assert note == "hedge" and ms == "OK"
    assert len(tickets) == 1
    ht = tickets[0]
    assert ht.side == "SHORT" and ht.qty == 150 and ht.limit is None
    # negative delta -> BUY hedge
    hedge_bar["delta_net"] = -0.15
    tickets, _, _ = process_bar(st, hedge_bar, CFG)
    assert tickets[0].side == "BUY" and tickets[0].qty == 150
    # below min shares -> no hedge, hold
    st["contracts"] = 1
    hedge_bar["delta_net"] = 0.15
    tickets, ms, note = process_bar(st, hedge_bar, CFG)
    assert tickets == [] and note == "hold"
