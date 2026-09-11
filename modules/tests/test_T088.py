"""Acceptance tests for T088 — Full-Stack Signal Ensemble.

Template v1.0.0 (strategy). Concrete sketch: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode (entry Boolean +
cost gate + kill switch), and asserts causality, ticket schema, the cost gate,
kill-switch behavior, and invalid-input handling.

Run: python3 -m pytest modules/tests/test_T088.py -q   (from repo root)
"""
import csv
import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T088_tape.csv"
EXPECTED = FIX / "T088_expected.csv"

GATE_CFG = [('>=', 0.55), ('>=', 1.0), ('>=', 1.0)]   # [(op, threshold)] for g1, g2, g3
GATE_NAMES = ['stacker_p', 'meta_ok', 'family_ok']
COST_GATE_K = 0.5                       # [default]
PER_TRADE_R = 100        # $ risk per trade [example]
DAILY_LOSS_STOP_R = 15  # in units of R [default]
MAX_BETS = 20            # [example]
MAX_MSGS_PER_BAR = 3     # C13: 1 intent + 2 cancel-replaces per symbol per bar [default]
MAX_GROSS_NOTIONAL = 500_000  # C14 notional cap [example]
META_SCALE_LO, META_SCALE_HI = 0.5, 1.5  # [example]
PARTICIPATION_CAP = 0.10  # [default]
SYMBOL = 'ENS:XNAS'
PARENT_SIGNAL = 'S086'
INFRA = False  # normative emitter emits OrderTicket intents

# ------------------------------------------------------------ schemas (App C/G)
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
    """ARMED -> TRIPPED -> RECOVERY -> ARMED (App: T-module risk contract)."""
    state: str = "ARMED"
    trip_reason: str = ""
    day_loss_R: float = 0.0

    def note_loss(self, loss_R: float) -> None:
        self.day_loss_R += loss_R
        if self.day_loss_R <= -DAILY_LOSS_STOP_R and self.state == "ARMED":
            self.state = "TRIPPED"
            self.trip_reason = f"daily loss stop: {self.day_loss_R:.2f}R <= -{DAILY_LOSS_STOP_R}R"

    def begin_recovery(self) -> None:
        assert self.state == "TRIPPED", "recovery only from TRIPPED"
        self.state = "RECOVERY"

    def rearm(self, checklist: dict) -> bool:
        ok = (self.state == "RECOVERY" and all(checklist.values())
              and self.day_loss_R > -DAILY_LOSS_STOP_R)
        if ok:
            self.state, self.trip_reason = "ARMED", ""
        return ok


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model — reference constant stack (§T2 COST block)."""
    spread_bps = 2.0   # [example]
    fee_bps = 2.0         # [example]
    borrow_bps = 0.0   # [example]
    impact_bps = 2.0   # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


# ------------------------------------------------- normative pseudocode stub
def shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost,
           bet_qty=100, meta_scale=1.0, bar_volume=10**9):
    """Normative sizing: shares = f(risk_budget_R, stop_distance, vol_estimate,
    ADV_cap, cost) — §T2.7 reference implementation. Invalid input -> 0 (veto)."""
    if not (risk_budget_R > 0 and stop_distance > 0 and vol_estimate > 0
            and 0 < ADV_cap <= 1 and cost >= 0):
        return 0  # invalid input -> no intent (F2), never a guessed size
    meta_scale = min(max(meta_scale, META_SCALE_LO), META_SCALE_HI)
    qty = int(bet_qty * meta_scale)            # 100 sh/bet [example]
    return max(min(qty, int(ADV_cap * bar_volume)), 0)  # 10% participation [default]


def emit(state: dict, rows: list[dict], cfg: dict) -> list[OrderTicket]:
    """emit(state, signals, cfg) -> list[OrderTicket] — reference stub.

    Intents only (Appendix c v1.0.0): never places orders. Invalid input ->
    module_state UNKNOWN, never interpolated (F1/F2). Infra publishers (T081)
    publish bar boundaries downstream and never emit OrderTickets.
    """
    tickets = []
    kill = state.setdefault("kill", KillSwitch())
    state.setdefault("module_state", "OK")
    log = state.setdefault("decision_log", [])

    def chain_hash(prev, payload):
        return hashlib.sha256((prev + payload).encode()).hexdigest()[:16]

    def append(action, reason, payload, before, after):
        prev = log[-1]["hash"] if log else "genesis"
        log.append({"action": action, "reason": reason,
                     "state_before": before, "state_after": after,
                     "prev_hash": prev, "hash": chain_hash(prev, payload)})

    for row in rows:
        sig_ts = row["signal_ts"]
        before = state["module_state"]
        # C15: HALTED / AUCTION / CLOSED -> OFF, nothing emitted.
        if state.get("market_state", "CONTINUOUS_TRADING") != "CONTINUOUS_TRADING":
            state["module_state"] = "OFF"
            continue
        # Kill switch dominates: TRIPPED/RECOVERY short-circuits before any
        # input validation, so a tripped module reports OFF, never UNKNOWN.
        if kill.state != "ARMED":
            state["module_state"] = "OFF"
            continue
        # F1/F2: invalid input -> UNKNOWN
        if (not row["valid"] or row["price"] <= 0 or row["qty"] <= 0
                or row["side"] not in ("LONG", "SHORT", "BUY", "SELL")):
            state["module_state"] = "UNKNOWN"
            append("COMPLIANCE_BLOCK", "invalid-input", f"bad-input@{sig_ts}",
                   before, "UNKNOWN")
            continue

        # Entry Boolean: three chapter gates (all must pass) + exit cooldown (C19)
        gates = []
        for (op, th), v in zip(GATE_CFG, (row["g1"], row["g2"], row["g3"])):
            gates.append(v >= th if op == ">=" else (v <= th if op == "<=" else (v > th if op == ">" else v < th)))
        if not all(gates):
            append("GATE_VETO", "entry-boolean", f"veto@{sig_ts}", before, before)
            continue
        if sig_ts < state.get("cooldown_until", 0):
            append("GATE_VETO", "exit-cooldown", f"cooldown@{sig_ts}", before, before)
            continue
        # Normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
        cost = expected_cost_bps(row["qty"] * row["price"], 0.001, "venue", "taker", "normal")
        if not (cost <= COST_GATE_K * row["edge_bps"]):
            append("GATE_VETO", "cost-gate", f"cost-veto@{sig_ts}", before, before)
            continue
        side = {'LONG': 'BUY', 'SHORT': 'SHORT', 'BUY': 'BUY', 'SELL': 'SELL'}[row["side"]]
        # C16: SHORT requires a confirmed locate
        if side == "SHORT" and not state.get("locate", {SYMBOL: True}).get(SYMBOL, True):
            append("GATE_VETO", "locate", f"no-locate@{sig_ts}", before, before)
            continue
        # C13: message-rate cap per symbol per bar
        key = (SYMBOL, row["bar"])
        if state.setdefault("bar_counts", {}).get(key, 0) >= MAX_MSGS_PER_BAR:
            append("COMPLIANCE_BLOCK", "message-rate", f"rate-cap@{sig_ts}", before, before)
            continue
        # C14: pre-trade fat-finger trio (price collar skipped: market intent, no limit)
        if not (row["qty"] <= MAX_BETS * 100 * META_SCALE_HI
                and row["qty"] * row["price"] <= MAX_GROSS_NOTIONAL):
            append("GATE_VETO", "fat-finger", f"size-cap@{sig_ts}", before, before)
            continue
        t = OrderTicket(symbol=SYMBOL, side=side, qty=int(row["qty"]), limit=None,
                        tif="IOC", ticket_id=f"{uuid.uuid4()}",
                        parent_signal=f"{PARENT_SIGNAL}@{sig_ts}",
                        intent_ts=sig_ts + 1000, state="NEW", stp=True)
        assert row["fill_ts"] > sig_ts, "causality: fill must be after signal (t->t+1)"
        state["bar_counts"][key] = state["bar_counts"].get(key, 0) + 1
        tickets.append(t)
        append("EMIT_INTENT", "emit", t.ticket_id + t.parent_signal + str(t.intent_ts),
               before, state["module_state"])

    return tickets


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


# -------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Reference stub reproduces the expected ticket set from the raw tape."""
    rows = tape_rows()
    tickets = emit({}, rows, {})
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
    for t in emit({}, rows, {}):
        signal_ts = int(t.parent_signal.split("@")[1])
        assert exp[t.intent_ts] > signal_ts


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates intents."""
    k = COST_GATE_K  # [default]
    cost = expected_cost_bps(1.0, 0.001, "venue", "taker", "normal")
    assert cost > 0
    assert cost <= k * 100.0      # large edge -> gate passes
    assert not (cost <= k * 1.2000000000000002)  # tiny edge -> gate blocks


def test_kill_switch_trip():
    """Daily loss beyond the stop trips the switch; emit goes OFF until re-armed."""
    kill = KillSwitch()
    assert kill.state == "ARMED"
    kill.note_loss(-DAILY_LOSS_STOP_R * 0.5)
    assert kill.state == "ARMED"          # half the stop: still armed
    kill.note_loss(-DAILY_LOSS_STOP_R * 0.6)
    assert kill.state == "TRIPPED"
    assert kill.trip_reason
    state = {"kill": kill}
    assert emit(state, tape_rows(), {}) == []   # tripped: no intents
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
    assert emit(state, bad, {}) == []
    assert state["module_state"] == "UNKNOWN"
    state2 = {}
    bad2 = [{"bar": 0, "signal_ts": 1, "fill_ts": 2, "side": "LONG",
              "edge_bps": 50.0, "g1": 99.0, "g2": 99.0, "g3": 99.0,
              "price": 100.0, "qty": 100, "valid": 0}]  # valid flag false
    assert emit(state2, bad2, {}) == []
    assert state2["module_state"] == "UNKNOWN"


def test_ticket_schema_and_compliance():
    """Appendix c schema fields + C1 self-trade prevention + C5 decision log."""
    state = {}
    tickets = emit(state, tape_rows(), {})
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


def test_cost_stack_matches_expected_fixture():
    """§T4 tolerance: recomputed expected_cost_bps matches expected.csv within 1e-4 bps."""
    exp = load_csv(EXPECTED)
    rows = {r["bar"]: r for r in tape_rows()}
    for e in exp:
        row = rows[int(e["bar"])]
        cost = expected_cost_bps(row["qty"] * row["price"], 0.001,
                                 "ENS:XNAS", "taker", "normal")
        assert abs(cost - float(e["cost_bps"])) <= 1e-4, e["ticket_idx"]


def test_shares_sizing():
    """Normative shares=f(...) — meta scaling, participation cap, invalid veto."""
    kw = dict(bet_qty=100, bar_volume=10**6)
    assert shares(100.0, 1.0, 1.0, 0.10, 6.0, meta_scale=1.0, **kw) == 100
    assert shares(100.0, 1.0, 1.0, 0.10, 6.0, meta_scale=2.0, **kw) == 150  # clipped to 1.5 [example]
    assert shares(100.0, 1.0, 1.0, 0.10, 6.0, meta_scale=0.1, **kw) == 50   # clipped to 0.5 [example]
    assert shares(100.0, 1.0, 1.0, 0.10, 6.0, bet_qty=100, meta_scale=1.0,
                  bar_volume=500) == 50  # 10% participation cap binds [default]
    assert shares(100.0, -1.0, 1.0, 0.10, 6.0) == 0   # invalid input -> veto (F2)
    assert shares(100.0, 1.0, 1.0, 1.5, 6.0) == 0     # ADV_cap out of range -> veto


def test_exit_cooldown_veto():
    """C19: ON_EXIT -> cooldown_until = now + 30 min; intents blocked until expiry."""
    state = {"cooldown_until": 1700000300000000000}  # bar 0's fill_ts: cooldown active
    tickets = emit(state, tape_rows(), {})
    assert tickets == []
    assert any(r["action"] == "GATE_VETO" and r["reason"] == "exit-cooldown"
               for r in state["decision_log"])
    state2 = {"cooldown_until": 0}  # cooldown expired -> bar 0 passes again
    assert len(emit(state2, tape_rows(), {})) == 1


def test_halt_market_state_no_intents():
    """C15: HALTED -> module OFF, nothing emitted."""
    state = {"market_state": "HALTED"}
    assert emit(state, tape_rows(), {}) == []
    assert state["module_state"] == "OFF"


def test_message_rate_cap():
    """C13: at most MAX_MSGS_PER_BAR messages per symbol per bar."""
    base = tape_rows()[0]  # bar 0 passes all gates
    rows = []
    for i in range(5):
        r = dict(base)
        r["signal_ts"] = base["signal_ts"] + i
        r["fill_ts"] = r["signal_ts"] + 300_000_000_000
        rows.append(r)
    state = {}
    assert len(emit(state, rows, {})) == MAX_MSGS_PER_BAR
    assert any(r["action"] == "COMPLIANCE_BLOCK" and r["reason"] == "message-rate"
               for r in state["decision_log"])


def test_short_without_locate_veto():
    """C16: SHORT side without a confirmed locate is vetoed."""
    row = dict(tape_rows()[0])  # passes all gates
    row["side"] = "SHORT"
    state = {"locate": {SYMBOL: False}}
    assert emit(state, [row], {}) == []
    assert any(r["action"] == "GATE_VETO" and r["reason"] == "locate"
               for r in state["decision_log"])
    state2 = {"locate": {SYMBOL: True}}
    tickets = emit(state2, [row], {})
    assert len(tickets) == 1 and tickets[0].side == "SHORT"

