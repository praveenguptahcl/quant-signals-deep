"""Acceptance tests for T050 - GEX Pin / Dealer-Positioning Fade (v1.1.0).

Template v1.0.0. The reference harness below implements the module's
normative emit() on the module's own terms: pin-distance entry rule
(dist_bps >= pin_dist_bps, days_to_expiry <= expiry_days, gex_stable),
the canonical fenced sizing shares() x pin-distance conviction scalar,
the COST-block callable expected_cost_bps (side-driven borrow), exits
never cost-gated, and t -> t+1 causality. Strategies emit ORDER INTENTS
ONLY (Appendix C v1.0.0); execution/broker layers create orders.

Run: python3 -m pytest modules/tests/test_T050.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T050_tape.csv"
EXPECTED = FIX / "T050_expected.csv"

TOL = 1e-9  # tolerance on float comparisons


@dataclass(frozen=True)
class OrderTicket:
    symbol: str
    side: str            # BUY | SELL | SHORT - intent, not a wire order
    qty: int             # shares, integer, > 0
    limit: float | None  # limit price; None = marketable intent
    tif: str             # DAY | IOC | FOK | GTC | OPG | CLS
    ticket_id: str       # module-generated idempotency key
    parent_signal: str   # "S<nnn>@<computed_at_ns>" - full provenance
    intent_ts: int       # int64 ns UTC - when the intent was emitted
    state: str           # NEW | WORKING | ... (intent-side mirror only)


@dataclass
class Config:
    sid: str = "T050"
    primary_signal: str = "S074"
    gex_window_d: int = 5
    pin_dist_bps: float = 30.0
    pin_reached_bps: float = 5.0
    dist_conviction_cap: float = 1.5
    expiry_days: int = 3
    gex_stable_bars: int = 3
    cost_gate_k: float = 0.5
    risk_R_usd: float = 250.0
    stop_bps: float = 25.0
    adv_cap_pct: float = 1.0
    spread_full_bps: float = 3.0
    taker_fee_bps: float = 0.30
    maker_rebate_bps: float = 0.20
    borrow_bps_per_day: float = 30.0
    expected_hold_days: int = 1
    impact_k: float = 20.0
    daily_loss_stop_pct: float = 2.0
    max_gross_mult: float = 4.0
    cooldown_sessions: int = 1
    venue: str = "primary-lit"
    default_side: str = "BUY"


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


def expected_cost_bps(notional, adv_pct, venue, side, urgency, cfg,
                     intent_side="BUY"):
    """COST-block callable: 4-component stack. `side` is the execution side
    (taker|maker|mixed per the COST block); borrow accrues on SHORT fades
    only (borrow_bps_per_day x expected_hold_days); LONG fades pay no borrow."""
    spread_bps = cfg.spread_full_bps / 2.0
    fee_bps = -cfg.maker_rebate_bps if side == "maker" else cfg.taker_fee_bps
    borrow_bps = (cfg.borrow_bps_per_day * cfg.expected_hold_days
                  if intent_side in ("SELL", "SHORT") else 0.0)
    impact_bps = cfg.impact_k * math.sqrt(max(adv_pct, 0.0) / 100.0)
    if urgency == "high":
        impact_bps *= 1.5
    return spread_bps + fee_bps + borrow_bps + impact_bps


def shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost):
    """Canonical fenced sizing: shares = f(risk_budget_R, stop_distance,
    vol_estimate, ADV_cap, cost). The cost gate is the §T3 predicate; sizing
    stays cost-aware through the stop distance."""
    per_share_risk = max(stop_distance * vol_estimate, 1e-12)
    return max(0, min(int(risk_budget_R / per_share_risk), int(ADV_cap)))


def size_pin_fade(bar, cfg):
    """Module sizing: canonical shares() x pin-distance conviction scalar."""
    base = shares(cfg.risk_R_usd, bar["stop_bps"] / 1e4, bar["close"],
                  cfg.adv_cap_pct / 100.0 * bar["adv_shares"], None)
    mult = min(bar["dist_bps"] / cfg.pin_dist_bps, cfg.dist_conviction_cap)
    return max(1, int(base * mult))


def process_bar(state, bar, cfg):
    """One bar through the strategy. Returns (ticket|None, module_state, note).

    Mirrors the §T3 normative pseudocode: validate (F1/F2) -> market state
    (§T0.5) -> kill switch -> exit rule -> normative cost-gate predicate ->
    pin-distance entry rule. Earliest fill for a bar-t intent is bar t+1's
    open (t -> t+1).
    """
    ks = state["kill"]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if (bar["close"] <= 0 or bar["market_state"] != "CONTINUOUS_TRADING"
            or bar["asof_ts"] < bar["event_ts"]
            or bar["dist_bps"] < 0 or bar["days_to_expiry"] < 0):
        state["position"] = 0
        state["qty"] = 0
        return None, "UNKNOWN", "invalid-input"
    # Kill switch: TRIPPED blocks everything; breach trips it
    if ks.state != "ARMED":
        return None, "OFF", "kill-" + ks.state.lower()
    if bar["daily_pnl_pct"] <= -cfg.daily_loss_stop_pct:
        ks.trip(bar["event_ts"], "daily-loss-stop")
        state["position"] = 0
        state["qty"] = 0
        return None, "OFF", "kill-trip"
    pos = state.get("position", 0)
    if pos != 0:
        # Exit rule: pin reached | GEX flipped | expiry today. Exits are
        # never cost-gated.
        if (bar["dist_bps"] < cfg.pin_reached_bps or not bar["gex_stable"]
                or bar["days_to_expiry"] == 0):
            exit_side = "SELL" if pos > 0 else "BUY"
            qty = max(1, int(state.get("qty", 0)))
            ticket = OrderTicket(
                symbol=bar["symbol"], side=exit_side, qty=qty, limit=None,
                tif="DAY", ticket_id="%s-%04dx" % (cfg.sid, int(bar["bar"])),
                parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
                intent_ts=bar["event_ts"], state="NEW")
            state["position"] = 0
            state["qty"] = 0
            return ticket, "OK", "exit"
        return None, "OK", "hold"
    # Entry rule (Boolean): pin-distance + expiry window + stable GEX
    if (bar["dist_bps"] >= cfg.pin_dist_bps
            and bar["days_to_expiry"] <= cfg.expiry_days
            and bar["gex_stable"]):
        side = "SELL" if bar["spot_above_pin"] else "BUY"  # fade toward pin
        cost = expected_cost_bps(bar["notional"], bar["adv_pct"], cfg.venue,
                                 "taker", bar["urgency"], cfg,
                                 intent_side=side)
        # Normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
        if cost <= cfg.cost_gate_k * bar["edge_bps"]:
            qty = size_pin_fade(bar, cfg)
            ticket = OrderTicket(
                symbol=bar["symbol"], side=side, qty=qty, limit=None,
                tif="DAY", ticket_id="%s-%04d" % (cfg.sid, int(bar["bar"])),
                parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
                intent_ts=bar["event_ts"], state="NEW")
            state["position"] = 1 if side == "BUY" else -1
            state["qty"] = qty
            return ticket, "OK", "entry"
        return None, "OK", "gate-block"
    return None, "OK", "flat"


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
            "close": float(r["close"]), "dist_bps": float(r["dist_bps"]),
            "days_to_expiry": int(r["days_to_expiry"]),
            "gex_stable": bool(int(r["gex_stable"])),
            "spot_above_pin": bool(int(r["spot_above_pin"])),
            "edge_bps": float(r["edge_bps"]), "notional": float(r["notional"]),
            "adv_pct": float(r["adv_pct"]), "adv_shares": float(r["adv_shares"]),
            "stop_bps": float(r["stop_bps"]), "urgency": r["urgency"],
            "market_state": r["market_state"],
            "daily_pnl_pct": float(r["daily_pnl_pct"]),
        })
    return rows


def expected():
    return load_csv(EXPECTED)


def fresh_state():
    return {"position": 0, "qty": 0, "kill": KillSwitch()}


def run_tape():
    st = fresh_state()
    out = []
    for b in tape():
        t, ms, note = process_bar(st, b, CFG)
        out.append((b, t, ms, note))
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
    assert {"event_ts", "asof_ts", "close", "dist_bps", "days_to_expiry",
            "gex_stable", "spot_above_pin", "market_state"} <= tcols
    assert {"intent_ts", "action", "qty", "cost_call_bps",
            "gate_pass", "module_state"} <= ecols
    assert len(load_csv(TAPE)) == len(load_csv(EXPECTED)) == 12


def test_fixture_recomputes_to_expected():
    """Reference process_bar reproduces the expected CSV row by row."""
    exp = {int(r["bar"]): r for r in expected()}
    for b, t, ms, note in run_tape():
        w = exp[b["bar"]]
        want_action = t.side if t else "HOLD"
        assert w["action"] == want_action, b["bar"]
        assert int(w["qty"]) == (t.qty if t else 0), b["bar"]
        assert w["module_state"] == ms, b["bar"]
        assert w["note"] == note, b["bar"]
        entry_side = "SELL" if b["spot_above_pin"] else "BUY"
        # cost_call_bps: COST-block reference (taker, LONG fade); gate_pass
        # uses the actual intent-side cost.
        ref_cost = expected_cost_bps(b["notional"], b["adv_pct"], CFG.venue,
                                     "taker", b["urgency"], CFG)
        side_cost = expected_cost_bps(b["notional"], b["adv_pct"], CFG.venue,
                                      "taker", b["urgency"], CFG,
                                      intent_side=entry_side)
        assert w["gate_pass"] == str(side_cost <= CFG.cost_gate_k * b["edge_bps"]), b["bar"]
        assert math.isclose(float(w["cost_call_bps"]), ref_cost,
                            rel_tol=TOL), b["bar"]
        if t is not None:
            assert t.qty > 0
            assert t.side in ("BUY", "SELL", "SHORT")
            assert t.intent_ts == b["event_ts"]
            assert t.ticket_id.startswith(CFG.sid)
            assert t.parent_signal == "%s@%d" % (CFG.primary_signal, b["event_ts"])


def test_entry_exit_sides_and_dist_sizing():
    """Entry fades toward the pin (spot below pin -> BUY); the exit of a
    LONG is a SELL; sizing carries the pin-distance conviction scalar."""
    st = fresh_state()
    bars = tape()
    t3, ms3, note3 = process_bar(st, bars[3], CFG)
    assert t3 is not None and t3.side == "BUY" and ms3 == "OK" and note3 == "entry"
    # dist multiplier: base = 250 / (25/1e4 * 99.55) = 1004; x min(42/30, 1.5) = 1405
    base = int(250 / (25 / 1e4 * 99.55))
    assert t3.qty == max(1, int(base * min(42.0 / 30.0, 1.5))) == 1405
    # position held through bars 4-5, exited at bar 6 (pin reached, dist < 5 bps)
    for b in bars[4:6]:
        t, ms, note = process_bar(st, b, CFG)
        assert t is None and note == "hold", b["bar"]
    t6, ms6, note6 = process_bar(st, bars[6], CFG)
    assert t6 is not None and t6.side == "SELL" and t6.qty == 1405
    assert ms6 == "OK" and note6 == "exit"


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    bars = tape()
    exp = {int(r["bar"]): r for r in expected()}
    for i, b in enumerate(bars):
        r = exp[b["bar"]]
        if r["intent_ts"]:
            signal_event = int(r["intent_ts"])
            fill_event = bars[i + 1]["event_ts"]  # earliest fill: next bar's open
            assert fill_event > signal_event, "signal-bar fill at bar %d" % i


def test_cost_gate_predicate():
    """Normative predicate: expected_cost_bps(...) <= k * edge_bps."""
    bars = tape()
    entry = bars[3]
    cost_bps = expected_cost_bps(entry["notional"], entry["adv_pct"], CFG.venue,
                                 "taker", entry["urgency"], CFG,
                                 intent_side="BUY")
    edge_bps = entry["edge_bps"]
    assert cost_bps <= CFG.cost_gate_k * edge_bps  # entry edge clears the gate
    blocked = bars[7]
    cost7 = expected_cost_bps(blocked["notional"], blocked["adv_pct"], CFG.venue,
                              "taker", blocked["urgency"], CFG,
                              intent_side="SELL")
    # bar 7 would be a SHORT fade: borrow accrues, tiny edge blocks it
    assert not (cost7 <= CFG.cost_gate_k * blocked["edge_bps"])


def test_short_side_borrow_in_cost():
    """COST-block: SHORT fades carry borrow_bps_per_day x expected_hold_days;
    LONG fades carry no borrow."""
    long_cost = expected_cost_bps(100000, 0.5, CFG.venue, "taker", "normal",
                                  CFG, intent_side="BUY")
    short_cost = expected_cost_bps(100000, 0.5, CFG.venue, "taker", "normal",
                                   CFG, intent_side="SELL")
    assert math.isclose(short_cost - long_cost,
                        CFG.borrow_bps_per_day * CFG.expected_hold_days,
                        rel_tol=TOL)
    assert math.isclose(short_cost, 1.5 + 0.3 + 30.0 + 1.4142135623730951,
                        rel_tol=TOL)


def test_kill_switch_trip_and_rearm():
    """ARMED -> TRIPPED blocks intents; checklist re-arm restores ARMED."""
    st = fresh_state()
    bars = tape()
    for b in bars[:9]:
        t, ms, note = process_bar(st, b, CFG)
    assert st["kill"].state == "ARMED", "kill must not trip before bar 9"
    b9 = bars[9]
    t9, ms9, note9 = process_bar(st, b9, CFG)
    assert t9 is None and ms9 == "OFF" and note9 == "kill-trip"
    assert st["kill"].state == "TRIPPED"
    # still tripped on the next bar: no intents while TRIPPED
    t10, ms10, note10 = process_bar(st, bars[10], CFG)
    assert t10 is None and ms10 == "OFF" and note10 == "kill-tripped"
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
    assert t8 is None and ms8 == "UNKNOWN" and note8 == "invalid-input"
    bad = dict(bars[3])
    bad["close"] = -1.0  # invalid price
    t, ms, _ = process_bar(fresh_state(), bad, CFG)
    assert t is None and ms == "UNKNOWN"
    bad2 = dict(bars[3])
    bad2["dist_bps"] = -5.0  # invalid indicator
    t2, ms2, _ = process_bar(fresh_state(), bad2, CFG)
    assert t2 is None and ms2 == "UNKNOWN"
