"""Acceptance tests for T084 — Block-Trade Impact Reversion, v1.0.1.

Template v1.0.0 (strategy). Reference implementation of the chapter's
normative pseudocode (§T3): entry Boolean + cost gate + pre-trade checks
(C13/C14) + kill switch in emit(); exit Booleans (time / refill-stall /
stop-at-print / second-block) + post-exit cooldown in manage(). Asserts
causality, ticket schema, the cost gate, kill-switch behavior, halt handling,
and invalid-input handling.

Run: python3 -m pytest modules/tests/test_T084.py -q   (from repo root)
"""
import csv
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T084_tape.csv"
EXPECTED = FIX / "T084_expected.csv"

SYMBOL = 'BLK:XNAS'
PARENT_SIGNAL = 'S048'

NS = 1_000_000_000  # ns per second


# ------------------------------------------------------------ §T0.2 Config
@dataclass(frozen=True)
class Config:
    """Single Config dataclass — mirrors §T0.2 (defaults are normative)."""
    block_mult: float = 20.0
    temp_share_min: float = 0.6
    kyle_impact_cap: float = 0.02
    half_life_s: float = 90.0
    qty: int = 5000
    cost_gate_k: float = 0.5
    cooldown_s: float = 1800.0
    max_concurrent_positions: int = 3
    per_trade_R: float = 200.0
    daily_loss_stop_R: float = 5.0
    refill_stall_frac: float = 0.5
    qty_cap_frac: float = 0.10
    price_collar_frac: float = 0.10
    msg_rate_cap_per_s: float = 10.0
    max_gross_notional: float = 1_200_000.0
    adv_cap: float = 0.10


# ------------------------------------------------------------ schemas (App C)
@dataclass(frozen=True)
class OrderTicket:
    symbol: str
    side: str            # BUY | SELL | SHORT — intent, not a wire order
    qty: int             # > 0
    limit: float | None
    tif: str             # DAY | IOC | FOK | GTC | OPG | CLS
    ticket_id: str
    parent_signal: str   # "S<nnn>@<computed_at_ns>"
    intent_ts: int       # int64 ns UTC
    state: str           # NEW | WORKING | ...
    stp: bool = True     # self-trade prevention flag (C1)


@dataclass
class KillSwitch:
    """ARMED -> TRIPPED -> RECOVERY -> ARMED (§T0.7/§T0.8)."""
    state: str = "ARMED"
    trip_reason: str = ""
    day_loss_R: float = 0.0

    def note_loss(self, loss_R: float) -> None:
        self.day_loss_R += loss_R
        if self.day_loss_R <= -self.stop_R() and self.state == "ARMED":
            self.state = "TRIPPED"
            self.trip_reason = f"daily loss stop: {self.day_loss_R:.2f}R"

    @staticmethod
    def stop_R() -> float:
        return Config().daily_loss_stop_R

    def begin_recovery(self) -> None:
        assert self.state == "TRIPPED", "recovery only from TRIPPED"
        self.state = "RECOVERY"

    def rearm(self, checklist: dict) -> bool:
        ok = (self.state == "RECOVERY" and all(checklist.values())
              and self.day_loss_R > -self.stop_R())
        if ok:
            self.state, self.trip_reason = "ARMED", ""
        return ok


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model — reference constant stack (§T2 COST block)."""
    spread_bps = 0.5   # [example]
    fee_bps = 2.5         # [example]
    borrow_bps = 0.0   # [example] — long-leg reference
    impact_bps = 1.0   # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


# --------------------------------------------- normative pseudocode (§T3)
def size_shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost, cfg,
                refilling_depth=1e12):
    """shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost)."""
    qty_risk = risk_budget_R / max(stop_distance, 1e-9)
    qty_adv = ADV_cap * vol_estimate
    qty_refill = cfg.qty_cap_frac * refilling_depth
    return int(max(min(qty_risk, qty_adv, qty_refill, cfg.qty), 0))


def pretrade_ok(ticket, ref_px, recent_intents, cfg) -> bool:
    """Pre-trade trio + message-rate cap (C13, C14)."""
    if ticket.limit is not None:
        if abs(ticket.limit - ref_px) / ref_px > cfg.price_collar_frac:
            return False
    if ticket.qty * ref_px > cfg.max_gross_notional:
        return False
    if len(recent_intents) >= cfg.msg_rate_cap_per_s * 60:
        return False
    return True


def _chain(log, action, reason, payload, before, after):
    prev = log[-1]["hash"] if log else "genesis"
    h = hashlib.sha256((prev + payload).encode()).hexdigest()[:16]
    log.append({"action": action, "reason": reason,
                "state_before": before, "state_after": after,
                "prev_hash": prev, "hash": h})


def emit(state: dict, rows: list[dict], cfg: "Config | None" = None) -> list[OrderTicket]:
    """emit(state, signals, cfg) -> list[OrderTicket] — reference stub.

    Intents only (Appendix c v1.0.0): never places orders. Invalid input ->
    module_state UNKNOWN, never interpolated (F1/F2). Halt -> OFF (C15).
    """
    cfg = cfg or Config()
    tickets = []
    kill = state.setdefault("kill", KillSwitch())
    state.setdefault("module_state", "OK")
    state.setdefault("cooldown_until", 0)
    state.setdefault("positions", {})
    state.setdefault("recent_intents", [])
    log = state.setdefault("decision_log", [])

    if not rows:
        state["module_state"] = "UNKNOWN"
        _chain(log, "NO_SIGNAL", "empty-input", "empty", "OK", "UNKNOWN")
        return []

    for row in rows:
        sig_ts = row["signal_ts"]
        before = state["module_state"]
        # Halt latches OFF for the rest of the batch (C15).
        if state.get("halted"):
            state["module_state"] = "OFF"
            continue
        # Kill switch dominates (C4): TRIPPED/RECOVERY reports OFF, never UNKNOWN.
        if kill.state != "ARMED":
            state["module_state"] = "OFF"
            continue
        # Halt -> OFF (C15), before any input validation.
        if row.get("halt"):
            state["module_state"] = "OFF"
            state["halted"] = True
            _chain(log, "HALT", "halt-flag", f"halt@{sig_ts}", before, "OFF")
            continue
        # F1/F2: invalid input -> UNKNOWN
        if (not row["valid"] or row["price"] <= 0 or row["qty"] <= 0
                or row["side"] not in ("LONG", "SHORT", "BUY", "SELL")):
            state["module_state"] = "UNKNOWN"
            _chain(log, "COMPLIANCE_BLOCK", "invalid-input",
                   f"bad-input@{sig_ts}", before, "UNKNOWN")
            continue

        # Entry Boolean: three chapter gates (all must pass), fixed order (C7)
        gates = [row["g1"] >= cfg.block_mult,
                 row["g2"] >= cfg.temp_share_min,
                 row["g3"] >= 1.0]
        if not all(gates):
            _chain(log, "GATE_VETO", "entry-boolean", f"veto@{sig_ts}", before, before)
            continue
        # Post-exit cooldown (C10)
        if row.get("now", sig_ts) < state["cooldown_until"]:
            _chain(log, "GATE_VETO", "cooldown", f"cooldown@{sig_ts}", before, before)
            continue
        # Normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps (C6)
        cost = expected_cost_bps(row["qty"] * row["price"],
                                 row.get("adv_pct", 0.001), "XNAS", "taker", "normal")
        if not (cost <= cfg.cost_gate_k * row["edge_bps"]):
            _chain(log, "GATE_VETO", "cost-gate", f"cost-veto@{sig_ts}", before, before)
            continue
        side = {'LONG': 'BUY', 'SHORT': 'SHORT', 'BUY': 'BUY', 'SELL': 'SELL'}[row["side"]]
        # C16: cheapest build is long-only (locate_ok=False default)
        if side == "SHORT" and not row.get("locate_ok", False):
            _chain(log, "COMPLIANCE_BLOCK", "locate", f"locate-veto@{sig_ts}",
                   before, before)
            continue
        t = OrderTicket(symbol=SYMBOL, side=side, qty=int(row["qty"]), limit=None,
                        tif="IOC", ticket_id=f"{uuid.uuid4()}",
                        parent_signal=f"{PARENT_SIGNAL}@{sig_ts}",
                        intent_ts=sig_ts + 1000, state="NEW", stp=True)
        # Pre-trade trio + message-rate (C13, C14)
        if not pretrade_ok(t, row["price"], state["recent_intents"], cfg):
            _chain(log, "COMPLIANCE_BLOCK", "pretrade", f"pretrade-veto@{sig_ts}",
                   before, before)
            continue
        assert row["fill_ts"] > sig_ts, "causality: fill must be after signal (t->t+1)"
        tickets.append(t)
        state["recent_intents"].append(t.intent_ts)
        state["positions"][SYMBOL] = {
            "side": t.side, "qty": t.qty, "entry_ts": sig_ts,
            "block_side": row.get("aggressor_side", "sell"),
            "baseline_depth": row.get("refill_depth", 1e9)}
        _chain(log, "EMIT_INTENT", "emit",
               t.ticket_id + t.parent_signal + str(t.intent_ts), before,
               state["module_state"])

    return tickets


def manage(state: dict, events: list[dict], cfg: "Config | None" = None) -> list[OrderTicket]:
    """manage(state, events, cfg) -> list[OrderTicket] — exit intents (§T3).

    Exit triggers (§T2.3): second-block (C12), stop-at-print, refill-stall,
    time. Every exit sets the post-exit cooldown (C10).
    """
    cfg = cfg or Config()
    exits = []
    kill = state.setdefault("kill", KillSwitch())
    state.setdefault("module_state", "OK")
    state.setdefault("cooldown_until", 0)
    state.setdefault("positions", {})
    state.setdefault("recent_intents", [])
    log = state.setdefault("decision_log", [])

    if kill.state != "ARMED":
        state["module_state"] = "OFF"
        return []

    for e in events:
        pos = state["positions"].get(e["symbol"])
        if pos is None:
            continue
        before = state["module_state"]
        reason = None
        if (e.get("kind") == "block"
                and e.get("aggressor_side") == pos["block_side"]
                and e["event_ts"] - pos["entry_ts"] <= 1800 * NS):   # 30 min [default]
            reason = "second-block"                                  # C12
        elif e.get("through_print"):
            reason = "stop-at-print"
        elif e.get("refill_depth", 1e18) < cfg.refill_stall_frac * pos["baseline_depth"]:
            reason = "refill-stall"
        elif e["event_ts"] >= pos["entry_ts"] + cfg.half_life_s * NS:
            reason = "time"
        if reason is None:
            continue
        flip = {"BUY": "SELL", "SELL": "BUY", "SHORT": "BUY"}[pos["side"]]
        x = OrderTicket(symbol=e["symbol"], side=flip, qty=pos["qty"], limit=None,
                        tif="IOC", ticket_id=f"{uuid.uuid4()}",
                        parent_signal=f"T084-exit@{e['event_ts']}",
                        intent_ts=e["event_ts"] + 1000, state="NEW", stp=True)
        fill_ts = e["event_ts"] + 300 * NS          # modeled next-print fill
        assert fill_ts > x.intent_ts, "causality: exit fill after exit intent"
        if not pretrade_ok(x, e.get("px", 1.0), state["recent_intents"], cfg):
            _chain(log, "COMPLIANCE_BLOCK", "pretrade-exit",
                   f"pretrade-veto@{e['event_ts']}", before, before)
            continue
        exits.append(x)
        state["recent_intents"].append(x.intent_ts)
        state["cooldown_until"] = e["event_ts"] + cfg.cooldown_s * NS   # C10
        del state["positions"][e["symbol"]]
        _chain(log, "EMIT_INTENT", f"exit-{reason}",
               x.ticket_id + x.parent_signal + str(x.intent_ts), before,
               state["module_state"])
    return exits


# ------------------------------------------------------------------- helpers
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def tape_rows():
    rows = []
    for r in load_csv(TAPE):
        rows.append({"bar": int(r["bar"]), "signal_ts": int(r["signal_ts"]),
                      "fill_ts": int(r["fill_ts"]), "side": r["side"],
                      "edge_bps": float(r["edge_bps"]),
                      "g1": float(r["g1"]), "g2": float(r["g2"]), "g3": float(r["g3"]),
                      "price": float(r["price"]), "qty": int(r["qty"]),
                      "valid": int(r["valid"]) == 1})
    return rows


def open_position(entry_ts=None):
    """Seed a single open long position (as emit() would record it)."""
    t = entry_ts if entry_ts is not None else 1_700_000_000_000_000_000
    return {SYMBOL: {"side": "BUY", "qty": 5000, "entry_ts": t,
                     "block_side": "sell", "baseline_depth": 100_000}}


# -------------------------------------------------------------------- tests
def test_size_shares_caps():
    """shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost): the
    tightest of risk / ADV / refill / cfg.qty caps wins."""
    cfg = Config()
    # risk cap binds: 200 / 0.10 = 2000
    assert size_shares(200.0, 0.10, 1e9, 0.10, 4.0, cfg, 1e9) == 2000
    # ADV cap binds: 0.10 * 10000 = 1000
    assert size_shares(200.0, 0.01, 10000, 0.10, 4.0, cfg, 1e9) == 1000
    # refill cap binds: 0.10 * 20000 = 2000 < cfg.qty 5000
    assert size_shares(1e6, 0.01, 1e9, 0.10, 4.0, cfg, 20000) == 2000
    # cfg.qty binds
    assert size_shares(1e6, 0.01, 1e9, 0.10, 4.0, cfg, 1e9) == 5000


def test_fixture_recomputes_to_expected():
    """Reference stub reproduces the expected ticket set from the raw tape."""
    rows = tape_rows()
    tickets = emit({}, rows)
    exp = load_csv(EXPECTED)
    assert len(tickets) == len(exp), (len(tickets), len(exp))
    for t, e in zip(tickets, exp):
        assert t.side == e["side"], e["ticket_idx"]
        assert t.qty == int(e["qty"]), e["ticket_idx"]
        assert t.intent_ts == int(e["intent_ts"]), e["ticket_idx"]
        assert t.tif == e["tif"], e["ticket_idx"]
        assert t.symbol == e["symbol"], e["ticket_idx"]


def test_no_signal_bar_fills():
    """Causality: every fill/boundary event is strictly after its signal event."""
    rows = tape_rows()
    for r in rows:
        assert r["fill_ts"] > r["signal_ts"], f"signal-bar fill at bar {r['bar']}"
    exp = {int(x["intent_ts"]): int(x["fill_ts"]) for x in load_csv(EXPECTED)}
    for t in emit({}, rows):
        signal_ts = int(t.parent_signal.split("@")[1])
        assert exp[t.intent_ts] > signal_ts


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates intents."""
    k = Config().cost_gate_k  # [default]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert cost > 0
    assert cost <= k * 100.0      # large edge -> gate passes
    assert not (cost <= k * 0.8)  # tiny edge -> gate blocks


def test_kill_switch_trip():
    """Daily loss beyond the stop trips the switch; emit goes OFF until re-armed."""
    kill = KillSwitch()
    assert kill.state == "ARMED"
    stop = Config().daily_loss_stop_R
    kill.note_loss(-stop * 0.5)
    assert kill.state == "ARMED"          # half the stop: still armed
    kill.note_loss(-stop * 0.6)
    assert kill.state == "TRIPPED"
    assert kill.trip_reason
    state = {"kill": kill}
    assert emit(state, tape_rows()) == []   # tripped: no intents
    assert state["module_state"] == "OFF"
    kill.begin_recovery()
    assert kill.state == "RECOVERY"
    kill.day_loss_R = 0.0  # loss reset after review
    checklist = {"losses_reconciled": True, "feeds_healthy": True,
                  "risk_limits_reviewed": True, "decision_log_intact": True}
    assert kill.rearm(checklist)
    assert kill.state == "ARMED"


def test_invalid_input_yields_unknown():
    state = {}
    bad = [{"bar": 0, "signal_ts": 1, "fill_ts": 2, "side": "LONG",
             "edge_bps": 50.0, "g1": 99.0, "g2": 99.0, "g3": 99.0,
             "price": -1.0, "qty": 100, "valid": 1}]  # negative price
    assert emit(state, bad) == []
    assert state["module_state"] == "UNKNOWN"
    state2 = {}
    bad2 = [{"bar": 0, "signal_ts": 1, "fill_ts": 2, "side": "LONG",
              "edge_bps": 50.0, "g1": 99.0, "g2": 99.0, "g3": 99.0,
              "price": 100.0, "qty": 100, "valid": 0}]  # valid flag false
    assert emit(state2, bad2) == []
    assert state2["module_state"] == "UNKNOWN"


def test_ticket_schema_and_compliance():
    """Appendix c schema fields + C1 self-trade prevention + C5 decision log."""
    state = {}
    tickets = emit(state, tape_rows())
    assert tickets, "fixture must produce at least one intent"
    seen = set()
    for t in tickets:
        assert t.side in ("BUY", "SELL", "SHORT")
        assert t.qty > 0
        assert t.tif in ("DAY", "IOC", "FOK", "GTC", "OPG", "CLS")
        assert t.limit is None or t.limit > 0
        assert t.ticket_id not in seen; seen.add(t.ticket_id)
        assert t.stp is True                      # C1 self-trade prevention
        assert "@" in t.parent_signal              # provenance
    log = state["decision_log"]
    assert any(r["action"] == "EMIT_INTENT" for r in log)
    for prev, rec in zip([{"hash": "genesis"}] + log, log):
        assert rec["prev_hash"] == prev["hash"]    # hash chain intact (C5)
        assert rec["hash"]


def test_config_defaults():
    """§T0.2 Config defaults are normative and pinned."""
    c = Config()
    assert (c.block_mult, c.temp_share_min, c.kyle_impact_cap) == (20.0, 0.6, 0.02)
    assert (c.half_life_s, c.qty, c.cost_gate_k) == (90.0, 5000, 0.5)
    assert (c.cooldown_s, c.max_concurrent_positions) == (1800.0, 3)
    assert (c.per_trade_R, c.daily_loss_stop_R) == (200.0, 5.0)
    assert (c.refill_stall_frac, c.qty_cap_frac, c.price_collar_frac) == (0.5, 0.10, 0.10)
    assert (c.msg_rate_cap_per_s, c.max_gross_notional) == (10.0, 1_200_000.0)


def test_manage_exit_on_half_life():
    """manage() emits a closing intent once the half-life elapses (time exit)."""
    t0 = 1_700_000_000_000_000_000
    state = {"positions": open_position(t0)}
    ev = {"kind": "tick", "symbol": SYMBOL, "event_ts": t0 + 95 * NS,
          "aggressor_side": None, "refill_depth": 90_000, "through_print": False,
          "px": 79.95}
    exits = manage(state, [ev])
    assert len(exits) == 1
    x = exits[0]
    assert x.side == "SELL" and x.qty == 5000 and x.tif == "IOC" and x.stp
    assert x.intent_ts > ev["event_ts"]                      # causality
    assert state["cooldown_until"] == ev["event_ts"] + int(1800 * NS)  # C10
    assert SYMBOL not in state["positions"]
    assert any(r["reason"] == "exit-time" for r in state["decision_log"])


def test_second_block_veto_and_flatten():
    """C12: second block, same direction, within the hold -> flatten + stand down."""
    t0 = 1_700_000_000_000_000_000
    state = {"positions": open_position(t0)}
    ev = {"kind": "block", "symbol": SYMBOL, "event_ts": t0 + 600 * NS,  # 10 min
          "aggressor_side": "sell", "refill_depth": 80_000,
          "through_print": False, "px": 79.80}
    exits = manage(state, [ev])
    assert len(exits) == 1                                   # flattened
    assert exits[0].side == "SELL"
    assert state["cooldown_until"] > ev["event_ts"]          # stand down (C10)
    assert any(r["reason"] == "exit-second-block" for r in state["decision_log"])


def test_pretrade_fat_finger_veto():
    """C14: max-notional trio vetoes an oversized ticket; normal ticket passes."""
    cfg = Config()
    big = OrderTicket(symbol=SYMBOL, side="BUY", qty=50000, limit=None, tif="IOC",
                      ticket_id="x", parent_signal="S048@1", intent_ts=2,
                      state="NEW", stp=True)
    assert not pretrade_ok(big, 79.91, [], cfg)      # 50000*79.91 > $1.2M
    ok = OrderTicket(symbol=SYMBOL, side="BUY", qty=5000, limit=None, tif="IOC",
                     ticket_id="y", parent_signal="S048@1", intent_ts=2,
                     state="NEW", stp=True)
    assert pretrade_ok(ok, 79.91, [], cfg)
    # price collar: 20% away from reference with a limit set -> veto
    collar = OrderTicket(symbol=SYMBOL, side="BUY", qty=5000, limit=95.89,
                         tif="DAY", ticket_id="z", parent_signal="S048@1",
                         intent_ts=2, state="NEW", stp=True)
    assert not pretrade_ok(collar, 79.91, [], cfg)


def test_halt_goes_off():
    """C15: a halted print freezes the module (OFF), emitting nothing."""
    rows = tape_rows()
    rows[0]["halt"] = True
    state = {}
    assert emit(state, rows) == []
    assert state["module_state"] == "OFF"
    assert any(r["action"] == "HALT" for r in state["decision_log"])
