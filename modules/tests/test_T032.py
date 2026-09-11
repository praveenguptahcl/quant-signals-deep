"""Acceptance tests for T032 - Copula Tail-Dependence Pairs (v1.1.0).

Template v1.0.0. Loads the fixture tape, runs the module's reference
emit() (normative pseudocode via process_bar), and asserts the TYPE
header, fixture-vs-expected agreement, causality (no-signal-bar fills),
the cost-gate predicate, kill-switch trip/re-arm, invalid-input handling,
the canonical sizing function, the pair-leg mirror invariant, the
borrow-day convention, and the post-exit cooldown.

The fixture tape is a SINGLE-LEG synthetic tape: expected.csv records the
primary (long) leg ticket only. Production emits the mirrored pair via
pair_tickets(); the mirror invariant is tested in
test_pair_mirror_legs.

Run: python3 -m pytest modules/tests/test_T032.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, replace
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T032_tape.csv"
EXPECTED = FIX / "T032_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
ONE_SESSION_NS = 86_400_000_000_000  # 1 session = 1 day (C10 cooldown) [default]


"""Reference implementation for T-module acceptance tests (shared sketch).

Implements the module's normative emit() contract:
    emit(state, signals, cfg) -> list[OrderTicket]
at one-bar granularity via process_bar(). Strategies emit ORDER INTENTS
ONLY (Appendix C v1.0.0); execution/broker layers create orders.
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class OrderTicket:
    symbol: str
    side: str            # BUY | SELL | SHORT | LONG - intent, not a wire order
    qty: int             # shares, integer, > 0
    limit: float | None  # limit price; None = marketable intent
    tif: str             # DAY | IOC | FOK | GTC | OPG | CLS
    ticket_id: str       # module-generated idempotency key
    parent_signal: str   # "S<nnn>@<computed_at_ns>" - full provenance
    intent_ts: int       # int64 ns UTC - when the intent was emitted
    state: str           # NEW | WORKING | ... (intent-side mirror only)


@dataclass
class Config:
    sid: str = "T000"
    primary_signal: str = "S000"
    z_entry: float = 2.0
    z_exit: float = 0.5
    cost_gate_k: float = 0.5
    risk_R_usd: float = 1000.0
    stop_bps: float = 100.0
    adv_cap_pct: float = 10.0
    spread_full_bps: float = 10.0
    taker_fee_bps: float = 0.3
    maker_rebate_bps: float = 0.2
    side_exec: str = "taker"        # taker | maker
    borrow_bps: float = 0.0         # folded round-trip short-leg charge [example]
    borrow_bps_per_day: float = 5.0  # convention: borrow_bps = per_day x hold_days [example]
    expected_hold_days: float = 10.0  # expected pair holding period [example]
    impact_k: float = 0.5
    daily_loss_stop_pct: float = -2.0
    venue: str = "XNAS"
    default_side: str = "BUY"      # BUY | SHORT


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
    """4-component cost stack (COST-block callable). Per-leg cost.

    borrow_bps is the FOLDED round-trip short-leg charge; the convention
    borrow_bps == borrow_bps_per_day * expected_hold_days is asserted in
    test_borrow_convention (the callable keeps the mandated 5-arg signature
    and reads the folded value from cfg).
    """
    spread_bps = cfg.spread_full_bps / 2.0
    fee_bps = cfg.maker_rebate_bps if side == "maker" else cfg.taker_fee_bps
    borrow_bps = cfg.borrow_bps if cfg.default_side == "SHORT" else 0.0
    impact_bps = cfg.impact_k * math.sqrt(max(adv_pct, 0.0) / 100.0)
    if urgency == "high":
        impact_bps *= 1.5
    return spread_bps + fee_bps + borrow_bps + impact_bps


def size_copula(risk_budget_R, stop_distance_bps, vol_estimate, px,
                adv_cap_pct, adv_shares, cost_gate_ok):
    """Canonical position sizing: shares = f(risk_budget_R, stop_distance,
    vol_estimate, ADV_cap, cost). vol_estimate is carried for the typed
    contract but unused in the reference build [default]; the cost term
    enters as the cost-gate predicate (False -> no position), per the §T3
    normative pseudocode.
    """
    del vol_estimate  # retained for the typed contract only
    raw_qty = risk_budget_R / max(stop_distance_bps / 1e4 * px, 1e-9)
    cap_qty = int(adv_cap_pct / 100.0 * adv_shares)
    qty = max(1, min(int(raw_qty), cap_qty))
    return qty if cost_gate_ok else 0


def pair_tickets(primary):
    """Mirror the primary leg ticket into the production pair.

    leg-B = same qty, opposite side (LONG <-> SHORT), fresh ticket id, same
    provenance/parent signal/intent_ts. Short leg requires locate_ok (C7);
    both legs must fill or neither does (leg-risk, §T8 #3).
    """
    opposite = {"LONG": "SHORT", "SHORT": "LONG",
                "BUY": "SELL", "SELL": "BUY"}[primary.side]
    leg_b = OrderTicket(
        symbol=primary.symbol, side=opposite, qty=primary.qty,
        limit=primary.limit, tif=primary.tif,
        ticket_id=primary.ticket_id + "-B",
        parent_signal=primary.parent_signal,
        intent_ts=primary.intent_ts, state="NEW")
    return primary, leg_b


def process_bar(state, bar, cfg):
    """One bar through the strategy. Returns (ticket|None, module_state, note).

    Mirrors the module's normative pseudocode: validate (F1/F2) -> kill
    switch -> size via size_copula -> normative cost-gate predicate ->
    entry/exit rules -> C10 post-exit cooldown. Earliest fill for a bar-t
    intent is bar t+1's open (t -> t+1).
    """
    ks = state["kill"]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if (bar["close"] <= 0 or bar["market_state"] != "CONTINUOUS_TRADING"
            or bar["asof_ts"] < bar["event_ts"]):
        state["position"] = 0
        return None, "UNKNOWN", "invalid-input"
    # Kill switch: TRIPPED blocks everything; breach trips it
    if ks.state != "ARMED":
        return None, "OFF", "kill-" + ks.state.lower()
    if bar["daily_pnl_pct"] <= -cfg.daily_loss_stop_pct:
        ks.trip(bar["event_ts"], "daily-loss-stop")
        state["position"] = 0
        return None, "OFF", "kill-trip"
    # Normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
    cost = expected_cost_bps(bar["notional"], bar["adv_pct"], cfg.venue,
                             cfg.side_exec, bar["urgency"], cfg)
    gate = cost <= cfg.cost_gate_k * bar["edge_bps"]
    # Position sizing (canonical): shares = f(risk_budget_R, stop_distance,
    # vol_estimate, ADV_cap, cost). The cost term vetoes ENTRY via the gate
    # predicate; exits are never cost-gated, so size them with cost_ok=True.
    qty = size_copula(cfg.risk_R_usd, bar["stop_bps"], 0.0, bar["close"],
                     cfg.adv_cap_pct, bar["adv_shares"], True)
    z = bar["signal_z"]
    pos = state.get("position", 0)
    if pos == 0:
        # C10 post-exit cooldown: suppress re-entry until it elapses
        if bar["event_ts"] < state.get("cooldown_until", 0):
            return None, "OK", "cooldown"
        if abs(z) >= cfg.z_entry and gate:
            side = cfg.default_side
            ticket = OrderTicket(
                symbol=bar["symbol"], side=side, qty=qty,
                limit=(round(bar["close"], 2) if cfg.side_exec == "maker" else None),
                tif="DAY", ticket_id="%s-%04d" % (cfg.sid, int(bar["bar"])),
                parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
                intent_ts=bar["event_ts"], state="NEW")
            state["position"] = 1 if side == "BUY" else -1
            return ticket, "OK", "entry"
        return None, "OK", "gate-block" if abs(z) >= cfg.z_entry else "flat"
    # Position open: exit on z through the exit band (exits never cost-gated)
    if abs(z) <= cfg.z_exit:
        exit_side = "SELL" if pos > 0 else "BUY"
        ticket = OrderTicket(
            symbol=bar["symbol"], side=exit_side, qty=qty,
            limit=(round(bar["close"], 2) if cfg.side_exec == "maker" else None),
            tif="DAY", ticket_id="%s-%04dx" % (cfg.sid, int(bar["bar"])),
            parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
            intent_ts=bar["event_ts"], state="NEW")
        state["position"] = 0
        state["cooldown_until"] = bar["event_ts"] + ONE_SESSION_NS
        return ticket, "OK", "exit"
    return None, "OK", "hold"


CFG = Config(
    sid="T032", primary_signal="S054",
    z_entry=2.0, z_exit=0.5, cost_gate_k=0.5,
    risk_R_usd=250, stop_bps=25, adv_cap_pct=1.0,
    spread_full_bps=3.0, taker_fee_bps=0.3,
    maker_rebate_bps=-0.2, side_exec="taker",
    borrow_bps=50.0, borrow_bps_per_day=5.0, expected_hold_days=10.0,
    impact_k=25.0,
    daily_loss_stop_pct=1.0, venue="primary",
    default_side="LONG")


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
            "close": float(r["close"]), "signal_z": float(r["signal_z"]),
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
    return {"position": 0, "kill": KillSwitch()}


def run_tape():
    st = fresh_state()
    out = []
    for b in tape():
        t, ms, note = process_bar(st, b, CFG)
        out.append((b, t, ms, note))
    return out


def _bar(**kw):
    base = {"bar": 99, "event_ts": 1790000000000000000,
            "asof_ts": 1790000000000000000, "symbol": "XYZ", "close": 100.0,
            "signal_z": 2.4, "edge_bps": 14.0, "notional": 100000,
            "adv_pct": 0.5, "adv_shares": 2000000, "stop_bps": 25,
            "urgency": "normal", "market_state": "CONTINUOUS_TRADING",
            "daily_pnl_pct": 0.05}
    base.update(kw)
    return base


# ------------------------------------------------------------------- tests
def test_type_header_and_columns():
    """Fixture files carry the TYPE header and the expected columns."""
    for path in (TAPE, EXPECTED):
        with open(path) as f:
            first = f.readline().strip()
        assert first.startswith("# TYPE:"), path
    tcols = set(load_csv(TAPE)[0].keys())
    ecols = set(load_csv(EXPECTED)[0].keys())
    assert {"event_ts", "asof_ts", "close", "signal_z", "market_state"} <= tcols
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
        assert w["gate_pass"] == str(
            float(w["cost_call_bps"]) <= CFG.cost_gate_k * b["edge_bps"]), b["bar"]
        assert math.isclose(float(w["cost_call_bps"]),
                            expected_cost_bps(b["notional"], b["adv_pct"], CFG.venue,
                                              CFG.side_exec, b["urgency"], CFG),
                            rel_tol=TOL), b["bar"]
        if t is not None:
            assert t.qty > 0
            assert t.side in ("BUY", "SELL", "SHORT", "LONG")
            assert t.intent_ts == b["event_ts"]
            assert t.ticket_id.startswith(CFG.sid)
            assert t.parent_signal == "%s@%d" % (CFG.primary_signal, b["event_ts"])


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
                                 CFG.side_exec, entry["urgency"], CFG)
    edge_bps = entry["edge_bps"]
    assert cost_bps <= CFG.cost_gate_k * edge_bps  # entry edge clears the gate
    if cost_bps > 0:
        blocked = bars[7]
        cost7 = expected_cost_bps(blocked["notional"], blocked["adv_pct"], CFG.venue,
                                  blocked["side_exec"] if "side_exec" in blocked else CFG.side_exec,
                                  blocked["urgency"], CFG)
        assert not (cost7 <= CFG.cost_gate_k * blocked["edge_bps"])  # tiny edge blocks
    else:
        # zero-cost overlay/filter/normalizer: the predicate holds vacuously
        assert cost_bps == 0.0


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


def test_sizing_canonical():
    """§T2 canonical sizing: shares = f(risk_budget_R, stop_distance,
    vol_estimate, ADV_cap, cost). Bar-3 reference: 996 shares; ADV cap
    binds on thin books; failed cost gate -> 0."""
    assert size_copula(250, 25, 0.0, 100.33, 1.0, 2_000_000, True) == 996
    assert size_copula(250, 25, 0.0, 100.33, 1.0, 2_000_000, False) == 0
    assert size_copula(250, 25, 0.0, 100.33, 1.0, 500, True) == 5  # ADV cap binds
    assert size_copula(500, 25, 0.0, 100.33, 1.0, 2_000_000, True) == 1993  # linear in R
    assert size_copula(250, 25, 0.0, 100.33, 1.0, 2_000_000, True) >= 1


def test_pair_mirror_legs():
    """Production pair invariant: two legs, opposite sides, equal qty,
    shared provenance; short leg carries the locate requirement (C7)."""
    st = fresh_state()
    t3, ms3, note3 = process_bar(st, dict(tape()[3]), CFG)
    assert t3 is not None and note3 == "entry"
    leg_a, leg_b = pair_tickets(t3)
    assert leg_a.qty == leg_b.qty == 996
    assert {leg_a.side, leg_b.side} == {"LONG", "SHORT"}
    assert leg_b.ticket_id == t3.ticket_id + "-B"
    assert leg_b.parent_signal == t3.parent_signal
    assert leg_b.intent_ts == t3.intent_ts
    assert leg_b.state == "NEW"
    # the fixture records only the primary leg; the mirror is the production
    # contract tested here, not in expected.csv


def test_borrow_convention():
    """Borrow convention: folded round-trip bps == per-day x hold days."""
    assert math.isclose(CFG.borrow_bps,
                        CFG.borrow_bps_per_day * CFG.expected_hold_days,
                        rel_tol=TOL)
    # short-leg stack includes the folded borrow charge
    short_cfg = replace(CFG, default_side="SHORT")
    leg = expected_cost_bps(100000, 0.5, CFG.venue, "taker", "normal", CFG)
    short_leg = expected_cost_bps(100000, 0.5, CFG.venue, "taker", "normal",
                                  short_cfg)
    assert math.isclose(short_leg - leg, CFG.borrow_bps, rel_tol=TOL)


def test_pair_level_cost_stack():
    """Honesty test: the tape gates the recorded (long) leg only; the true
    pair stack = 2 x (spread + fee + impact) + borrow_roundtrip."""
    leg = expected_cost_bps(100000, 0.5, CFG.venue, "taker", "normal", CFG)
    short_cfg = replace(CFG, default_side="SHORT")
    short_leg = expected_cost_bps(100000, 0.5, CFG.venue, "taker", "normal",
                                  short_cfg)
    pair_one_way = leg + short_leg
    assert math.isclose(pair_one_way,
                        2 * (CFG.spread_full_bps / 2.0 + CFG.taker_fee_bps
                             + CFG.impact_k * math.sqrt(0.5 / 100.0))
                        + CFG.borrow_bps,
                        rel_tol=TOL)
    assert math.isclose(pair_one_way, 57.13553390693274, rel_tol=1e-6)
    assert math.isclose(2 * pair_one_way, 114.27106781386548, rel_tol=1e-6)  # round-trip
    # with the full pair stack the bar-3 edge would NOT clear the gate:
    # the fixture's single-leg gate is documented optimism, not production
    assert not (pair_one_way <= CFG.cost_gate_k * 14.271067811865475)


def test_exit_cooldown():
    """C10: after an exit, re-entry is suppressed for one session."""
    st = fresh_state()
    ts0 = 1790000000000000000
    entry_bar = _bar(bar=0, event_ts=ts0, asof_ts=ts0)
    t, ms, note = process_bar(st, entry_bar, CFG)
    assert t is not None and note == "entry"
    ts1 = ts0 + ONE_SESSION_NS
    exit_bar = _bar(bar=1, event_ts=ts1, asof_ts=ts1, signal_z=0.25)
    t1, ms1, note1 = process_bar(st, exit_bar, CFG)
    assert t1 is not None and note1 == "exit"
    # re-entry one session later (cooldown satisfied) is allowed
    ts2 = ts1 + ONE_SESSION_NS
    again = _bar(bar=2, event_ts=ts2, asof_ts=ts2)
    t2, ms2, note2 = process_bar(st, again, CFG)
    assert t2 is not None and note2 == "entry"
    # but an entry signal inside the cooldown window is suppressed
    st2 = fresh_state()
    process_bar(st2, entry_bar, CFG)
    process_bar(st2, exit_bar, CFG)
    mid = _bar(bar=2, event_ts=ts1 + ONE_SESSION_NS // 2,
               asof_ts=ts1 + ONE_SESSION_NS // 2)
    t3, ms3, note3 = process_bar(st2, mid, CFG)
    assert t3 is None and note3 == "cooldown" and ms3 == "OK"
