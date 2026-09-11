"""Acceptance tests for T039 - ETF Creation/Redemption Flow Trader.

Template v1.0.0. Reference implementation of the module's normative emit()
contract at one-bar granularity via process_bar():
    emit(state, signals, cfg) -> list[OrderTicket]
Strategies emit ORDER INTENTS ONLY (Appendix C v1.0.0); execution/broker
layers create orders.

Fixture scenario (cheap-side, MVP proxy mode, ap_access=False): S056 emits a
signed dislocation z (z > 0 = rich/premium, z < 0 = cheap/discount). The tape
carries a discount dislocation, so entries BUY the ETF leg only; the basket
short leg is phase 2 (ap_access=True). Borrow is 0.0 on the emitted long ETF
leg — creation-covered / long-leg reason documented in the COST block.

Run: python3 -m pytest modules/tests/test_T039.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, replace
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T039_tape.csv"
EXPECTED = FIX / "T039_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]


@dataclass(frozen=True)
class OrderTicket:
    symbol: str
    side: str            # BUY | SELL - intent, not a wire order
    qty: int             # shares, integer, > 0
    limit: float | None  # limit price; None = marketable intent
    tif: str             # DAY | IOC | FOK | GTC | OPG | CLS
    ticket_id: str       # module-generated idempotency key
    parent_signal: str   # "S056@<computed_at_ns>" - full provenance
    intent_ts: int       # int64 ns UTC - when the intent was emitted
    state: str           # NEW | WORKING | ... (intent-side mirror only)


@dataclass(frozen=True)
class Config:
    sid: str = "T039"
    primary_signal: str = "S056"
    trigger_bps: float = 10.0       # premium trigger [default]
    z_entry: float = 2.0          # |z| entry threshold [default]
    z_exit: float = 0.5           # |z| exit band [default]
    creation_unit: int = 50000    # shares per creation unit [default]
    creation_cost_bps: float = 2.0  # creation bound [default]
    max_hold_days: int = 5        # time stop [default]
    cost_gate_k: float = 0.5      # cost-gate multiplier [default]
    risk_R_usd: float = 250.0     # per-trade risk budget [default]
    stop_bps: float = 25.0        # stop distance [default]
    adv_cap_pct: float = 1.0      # ADV cap percent [default]
    spread_full_bps: float = 2.0  # full spread [example]
    taker_fee_bps: float = 0.3    # taker fee [example]
    maker_rebate_bps: float = -0.2  # maker rebate [example]
    borrow_bps: float = 10.0      # proxy-mode short-leg borrow [example];
                                  # fixture prices 0.0 (long ETF leg, see COST block)
    impact_k: float = 8.0         # impact coefficient [example]
    daily_loss_stop_pct: float = 1.0  # daily loss stop [default]
    venue: str = "primary"
    side_exec: str = "taker"      # taker | maker
    cooldown_s: float = 86400.0   # post-exit cooldown, 1 session [default]
    ap_access: bool = False       # basket leg emitted only when True [default]
    locate_ok: bool = True        # C7 locate for rich-side ETF shorts [default]


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


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """COST-block callable (single source of truth). 4-component stack.

    Borrow is 0.0 here: the fixture emits the cheap-side LONG ETF leg, so no
    stock-loan short exists. Rich-side proxy shorts add CFG.borrow_bps
    (10.0 [example]) as a documented adder outside this 5-arg call; the
    creation-covered AP path also prices 0.0. See the §T2 COST block.
    """
    spread_bps = CFG.spread_full_bps / 2.0
    fee_bps = CFG.maker_rebate_bps if side == "maker" else CFG.taker_fee_bps
    borrow_bps = 0.0
    impact_bps = CFG.impact_k * math.sqrt(max(adv_pct, 0.0) / 100.0)
    if urgency == "high":
        impact_bps *= 1.5
    return spread_bps + fee_bps + borrow_bps + impact_bps


def shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost):
    """shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost).

    Normative sizing (§T2): risk-scaled, ADV-capped, integer shares.
    Creation-unit quantization applies only when ap_access=True (basket leg);
    the fixture's MVP ETF leg is unquantized. `cost` is accepted for the
    contract signature; the gate already cleared before sizing.
    """
    n = risk_budget_R / max(stop_distance, 1e-9)
    n = min(n, ADV_cap)
    return max(1, int(n))


def process_bar(state, bar, cfg):
    """One bar through the strategy. Returns (ticket|None, module_state, note).

    Mirrors the §T3 normative pseudocode: validate (F1/F2) -> kill switch ->
    size -> normative cost-gate predicate -> entry/exit rules with cooldown.
    Earliest fill for a bar-t intent is bar t+1's open (t -> t+1).
    """
    ks = state["kill"]
    z = bar["signal_z"]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if (bar["close"] <= 0 or bar["market_state"] != "CONTINUOUS_TRADING"
            or bar["asof_ts"] < bar["event_ts"]
            or not math.isfinite(z) or abs(z) > 10.0):
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
                             cfg.side_exec, bar["urgency"])
    gate = cost <= cfg.cost_gate_k * bar["edge_bps"]
    pos = state.get("position", 0)
    if pos == 0:
        if abs(z) >= cfg.z_entry and gate:
            # C10 post-exit cooldown
            if bar["event_ts"] < state.get("cooldown_until", 0):
                return None, "OK", "cooldown-block"
            side = "SELL" if z > 0 else "BUY"  # rich -> short ETF; cheap -> long ETF
            if side == "SELL" and not cfg.locate_ok:
                return None, "OK", "locate-veto"  # C7
            stop_distance = bar["stop_bps"] / 1e4 * bar["close"]
            adv_cap = cfg.adv_cap_pct / 100.0 * bar["adv_shares"]
            qty = shares(cfg.risk_R_usd, stop_distance, None, adv_cap, cost)
            ticket = OrderTicket(
                symbol=bar["symbol"], side=side, qty=qty,
                limit=None,  # marketable taker intent
                tif="DAY", ticket_id="%s-%04d" % (cfg.sid, int(bar["bar"])),
                parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
                intent_ts=bar["event_ts"], state="NEW")
            state["position"] = 1 if side == "BUY" else -1
            return ticket, "OK", "entry"
        return None, "OK", "gate-block" if abs(z) >= cfg.z_entry else "flat"
    # Position open: exit on |z| through the exit band (exits never cost-gated)
    if abs(z) <= cfg.z_exit:
        exit_side = "SELL" if pos > 0 else "BUY"
        stop_distance = bar["stop_bps"] / 1e4 * bar["close"]
        adv_cap = cfg.adv_cap_pct / 100.0 * bar["adv_shares"]
        qty = shares(cfg.risk_R_usd, stop_distance, None, adv_cap, cost)
        ticket = OrderTicket(
            symbol=bar["symbol"], side=exit_side, qty=qty,
            limit=None, tif="DAY",
            ticket_id="%s-%04dx" % (cfg.sid, int(bar["bar"])),
            parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
            intent_ts=bar["event_ts"], state="NEW")
        state["position"] = 0
        state["cooldown_until"] = bar["event_ts"] + int(cfg.cooldown_s * 1e9)
        return ticket, "OK", "exit"
    return None, "OK", "hold"


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
    return {"position": 0, "kill": KillSwitch(), "cooldown_until": 0}


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
                                              CFG.side_exec, b["urgency"]),
                            rel_tol=TOL), b["bar"]
        if t is not None:
            assert t.qty > 0
            assert t.side in ("BUY", "SELL")  # valid OrderTicket sides only
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
                                 CFG.side_exec, entry["urgency"])
    edge_bps = entry["edge_bps"]
    assert cost_bps <= CFG.cost_gate_k * edge_bps  # entry edge clears the gate
    if cost_bps > 0:
        blocked = bars[7]
        cost7 = expected_cost_bps(blocked["notional"], blocked["adv_pct"], CFG.venue,
                                  CFG.side_exec, blocked["urgency"])
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


def test_post_exit_cooldown():
    """C10: no re-entry inside the post-exit cooldown window."""
    st = fresh_state()
    bars = tape()
    for b in bars[:7]:
        process_bar(st, b, CFG)
    assert st["position"] == 0  # exited at bar 6
    assert st["cooldown_until"] == bars[6]["event_ts"] + int(CFG.cooldown_s * 1e9)
    # a would-be entry inside the cooldown is suppressed even with a huge edge
    probe = dict(bars[3])
    probe["event_ts"] = bars[6]["event_ts"] + 3600 * 10**9
    probe["asof_ts"] = probe["event_ts"] + 250000
    probe["edge_bps"] = 50.0
    t, ms, note = process_bar(st, probe, CFG)
    assert t is None and note == "cooldown-block" and ms == "OK"
    # at/after cooldown expiry the same setup fires
    probe2 = dict(probe)
    probe2["event_ts"] = st["cooldown_until"]
    probe2["asof_ts"] = probe2["event_ts"] + 250000
    t2, ms2, note2 = process_bar(st, probe2, CFG)
    assert t2 is not None and note2 == "entry" and ms2 == "OK"


def test_rich_side_requires_locate():
    """C7: rich-side ETF shorts are vetoed without locate_ok."""
    bars = tape()
    rich = dict(bars[3])
    rich["signal_z"] = 2.4  # rich/premium side -> SELL the ETF leg
    rich["edge_bps"] = 12.0
    t, ms, note = process_bar(fresh_state(), rich, CFG)
    assert t is not None and t.side == "SELL" and note == "entry" and ms == "OK"
    cfg_noloc = replace(CFG, locate_ok=False)
    t2, ms2, note2 = process_bar(fresh_state(), rich, cfg_noloc)
    assert t2 is None and note2 == "locate-veto" and ms2 == "OK"
