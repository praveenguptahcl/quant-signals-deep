"""Acceptance tests for T082 — Information-Share Venue Router (v1.0.1).

Template v1.0.0 (strategy). Concrete sketch: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode (§T2.2 entry
Boolean + §T2.3 exits + §T2.4 fenced sizing + §T2.7 cost gate + §T0 kill
switch), and asserts causality, ticket schema, the cost gate, kill-switch
behavior, reroute cancel-replace semantics, and invalid-input handling.

Run: python3 -m pytest modules/tests/test_T082.py -q   (from repo root)
"""
import csv
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T082_tape.csv"
EXPECTED = FIX / "T082_expected.csv"

GATE_CFG = [('>=', 0.05), ('>=', 1.0), ('>=', 1.0)]   # [(op, threshold)] for g1, g2, g3
GATE_NAMES = ['is_margin', 'tox_ok', 'spread_ok']
COST_GATE_K = 0.5                       # [default]
REROUTE_GAP = 0.10                      # [default]
PER_TRADE_R = 115.0      # $ risk per trade [example]
DAILY_LOSS_STOP_R = 5.0  # in units of R [default]
CHILD_MAX_SHARES = 1000  # [default]
SYMBOL = 'LGX:XNAS'
PARENT_SIGNAL = 'S016'
INFRA = False  # normative emitter emits OrderTicket intents


# ------------------------------------------------------------ schemas (App c)
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
    stp: bool = True     # self-trade prevention flag (R1)


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
    """Callable cost model — reference constant stack (§T2.6 COST block)."""
    spread_bps = 1.2   # [example]
    fee_bps = 1.0      # [example]
    borrow_bps = 0.0    # [example]
    impact_bps = 1.5    # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


# ------------------------------------------------- normative pseudocode stub
def emit(state: dict, rows: list[dict], cfg: dict) -> list[OrderTicket]:
    """emit(state, signals, cfg) -> list[OrderTicket] — reference stub.

    Intents only (Appendix c v1.0.0): never places orders. Invalid input ->
    module_state UNKNOWN, never interpolated (F1/F2). A working ticket is held
    (max_concurrent_positions = 1 [default]) until rerouted or expired; a
    reroute emits a cancel + a NEW ticket with the replaces link in the
    decision log (Appendix g v1.0.0).
    """
    tickets = []
    kill = state.setdefault("kill", KillSwitch())
    state.setdefault("module_state", "OK")
    state.setdefault("working", None)   # held intent: one at a time [default]
    log = state.setdefault("decision_log", [])

    def chain_hash(prev, payload):
        return hashlib.sha256((prev + payload).encode()).hexdigest()[:16]

    def append(action, reason, payload, before, after):
        prev = log[-1]["hash"] if log else "genesis"
        log.append({"action": action, "reason": reason, "outcome": payload,
                     "state_before": before, "state_after": after,
                     "prev_hash": prev, "hash": chain_hash(prev, payload)})

    for row in rows:
        sig_ts = row["signal_ts"]
        before = state["module_state"]
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

        # Reroute branch (§T2.2 / §T3): chosen venue score dropped below
        # second-best minus the reroute gap -> cancel + new ticket intent.
        working = state["working"]
        if working is not None and row.get("rank1_is") is not None:
            if row["rank1_is"] < row["rank2_is"] - REROUTE_GAP:
                old_id = working["ticket_id"]
                append("CANCEL", "reroute", f"cancel@{old_id}", before, before)
                nt = OrderTicket(symbol=working["symbol"], side=working["side"],
                                 qty=working["qty"], limit=None, tif="IOC",
                                 ticket_id=f"{uuid.uuid4()}",
                                 parent_signal=f"{PARENT_SIGNAL}@{sig_ts}",
                                 intent_ts=sig_ts + 1000, state="NEW", stp=True)
                assert nt.intent_ts > sig_ts, "causality on reroute intents"
                tickets.append(nt)
                append("EMIT_INTENT", "reroute", nt.ticket_id + f"|replaces:{old_id}",
                       before, state["module_state"])
                state["working"] = {"ticket_id": nt.ticket_id, "symbol": nt.symbol,
                                    "side": nt.side, "qty": nt.qty}
                continue
            # Working intent held; no reroute -> hold, emit nothing new.
            continue

        # Entry Boolean: three chapter gates (all must pass), fixed order
        gates = []
        for (op, th), v in zip(GATE_CFG, (row["g1"], row["g2"], row["g3"])):
            gates.append(v >= th if op == ">=" else (v <= th if op == "<=" else (v > th if op == ">" else v < th)))
        if not all(gates):
            append("GATE_VETO", "entry-boolean", f"veto@{sig_ts}", before, before)
            continue
        # Normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
        cost = expected_cost_bps(row["qty"] * row["price"], 0.001, "venue", "taker", "normal")
        if not (cost <= COST_GATE_K * row["edge_bps"]):
            append("GATE_VETO", "cost-gate", f"cost-veto@{sig_ts}", before, before)
            continue
        side = {'LONG': 'BUY', 'SHORT': 'SHORT', 'BUY': 'BUY', 'SELL': 'SELL'}[row["side"]]
        qty = min(int(row["qty"]), CHILD_MAX_SHARES)   # fenced sizing cap (§T2.4)
        t = OrderTicket(symbol=SYMBOL, side=side, qty=qty, limit=None,
                        tif="IOC", ticket_id=f"{uuid.uuid4()}",
                        parent_signal=f"{PARENT_SIGNAL}@{sig_ts}",
                        intent_ts=sig_ts + 1000, state="NEW", stp=True)
        assert row["fill_ts"] > sig_ts, "causality: fill must be after signal (t->t+1)"
        tickets.append(t)
        append("EMIT_INTENT", "emit", t.ticket_id + t.parent_signal + str(t.intent_ts),
               before, state["module_state"])
        state["working"] = {"ticket_id": t.ticket_id, "symbol": t.symbol,
                            "side": t.side, "qty": t.qty}

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


def passing_row(sig_ts, fill_ts, rank1=None, rank2=None):
    """A fully-passing router row, optionally carrying venue ranks."""
    r = {"bar": 0, "signal_ts": sig_ts, "fill_ts": fill_ts, "side": "BUY",
         "edge_bps": 14.7, "g1": 0.12, "g2": 1.0, "g3": 1.0,
         "price": 150.0, "qty": 1000, "valid": True}
    if rank1 is not None:
        r["rank1_is"], r["rank2_is"] = rank1, rank2
    return r


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
        assert abs(float(e["cost_bps"]) - 3.7) <= 1e-9, e["ticket_idx"]


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
    assert not (cost <= k * 0.7400000000000001)  # tiny edge -> gate blocks


def test_cost_stack_exact_value():
    """§T2.6 reference stack is exact: 3.7 bps -> $55.50 on the §T4 case."""
    cost = expected_cost_bps(150000.00, 0.001, "LGX:XNAS", "taker", "normal")
    assert abs(cost - 3.7) <= 1e-9
    dollars = 150000.00 * cost / 10_000
    assert abs(dollars - 55.50) <= 1e-6


def test_cost_gate_boundary():
    """Boundary of the executable predicate: 3.7 <= 0.5 * edge."""
    cost = expected_cost_bps(1.0, 0.001, "v", "taker", "normal")
    assert cost <= COST_GATE_K * 7.4     # equality: gate passes
    assert not (cost <= COST_GATE_K * 7.39)  # just below: gate blocks


def test_reroute_emits_cancel_replace():
    """Score drop below second-best minus the reroute gap cancels and re-issues."""
    base = 1700000000000000000
    r0 = passing_row(base, base + 300_000_000_000, rank1=0.60, rank2=0.50)
    r1 = passing_row(base + 300_000_000_000, base + 600_000_000_000,
                     rank1=0.30, rank2=0.55)  # 0.30 < 0.55 - 0.10 -> reroute
    state = {}
    tickets = emit(state, [r0, r1], {})
    assert len(tickets) == 2
    t0, t1 = tickets
    assert t0.ticket_id != t1.ticket_id           # cancel-replace: NEW ticket_id
    assert t1.intent_ts > r1["signal_ts"]          # causality preserved on replace
    log = state["decision_log"]
    cancels = [r for r in log if r["action"] == "CANCEL"]
    assert len(cancels) == 1
    replaces = [r for r in log if r["action"] == "EMIT_INTENT"
                and f"replaces:{t0.ticket_id}" in r["outcome"]]
    assert replaces, "replaces link must be in the decision log (Appendix g)"


def test_no_reroute_without_score_drop():
    """A passing second row without a score drop holds the working intent."""
    base = 1700000000000000000
    r0 = passing_row(base, base + 300_000_000_000, rank1=0.60, rank2=0.50)
    r1 = passing_row(base + 300_000_000_000, base + 600_000_000_000,
                     rank1=0.58, rank2=0.50)  # drop but within the 0.10 gap
    tickets = emit({}, [r0, r1], {})
    assert len(tickets) == 1  # held, not re-emitted


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
    """Appendix c schema fields + R1 self-trade prevention + R5 decision log."""
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
        assert t.stp is True                      # R1 self-trade prevention
        assert "@" in t.parent_signal              # provenance
    log = state["decision_log"]
    assert any(r["action"] == "EMIT_INTENT" for r in log)
    for prev, rec in zip([{"hash": "genesis"}] + log, log):
        assert rec["prev_hash"] == prev["hash"]    # hash chain intact (R5)
        assert rec["hash"]
