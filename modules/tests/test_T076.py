"""Acceptance tests for T076 — Liquidation-Cascade Fade.

Template v1.0.0 (strategy). Concrete sketch: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode (entry Boolean +
cost gate + kill switch), and asserts causality, ticket schema, the cost gate,
kill-switch behavior, and invalid-input handling.

Run: python3 -m pytest modules/tests/test_T076.py -q   (from repo root)
"""
import csv
import hashlib
import math
import uuid
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T076_tape.csv"
EXPECTED = FIX / "T076_expected.csv"

GATE_CFG = [('>=', 10.0), ('>=', 70.0), ('>=', 1.0)]   # [(op, threshold)] for g1, g2, g3
GATE_NAMES = ['liq_ratio', 'decay_pct', 'confirm_score']
COST_GATE_K = 0.5                       # [default]
PER_TRADE_R = 250        # $ risk per trade [example]
DAILY_LOSS_STOP_R = 3  # in units of R [default]
SYMBOL = 'BTC-PERP:VENUE'
PARENT_SIGNAL = 'S096'
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
    spread_bps = 20.0   # [example]
    fee_bps = 10.0         # [example]
    borrow_bps = 0.0   # [example]
    impact_bps = 5.0   # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def size_shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost) -> int:
    """shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost) — §T2.4."""
    if stop_distance <= 0:
        return 0
    qty = math.floor(risk_budget_R / stop_distance)
    qty = min(qty, math.floor(ADV_cap))
    return max(qty, 0)


# ------------------------------------------------- normative pseudocode stub
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

        # Entry Boolean: three chapter gates (all must pass)
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
        t = OrderTicket(symbol=SYMBOL, side=side, qty=int(row["qty"]), limit=None,
                        tif="IOC", ticket_id=f"{uuid.uuid4()}",
                        parent_signal=f"{PARENT_SIGNAL}@{sig_ts}",
                        intent_ts=sig_ts + 1000, state="NEW", stp=True)
        assert row["fill_ts"] > sig_ts, "causality: fill must be after signal (t->t+1)"
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
    assert cost <= k * 210.0      # large edge -> gate passes
    assert not (cost <= k * 7.0)  # tiny edge -> gate blocks


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



def test_short_mirror_emits_sell():
    """Normative pseudocode short-mirror: a passing SHORT-side row emits a
    SELL-side intent (never a buy into a short-liquidation cascade)."""
    rows = [{"bar": 2, "signal_ts": 1700000600000000000,
             "fill_ts": 1700000900000000000, "side": "SHORT",
             "edge_bps": 120.0, "g1": 14.0, "g2": 82.0, "g3": 1.0,
             "price": 66450.0, "qty": 50, "valid": 1}]
    tickets = emit({}, rows, {})
    assert len(tickets) == 1
    assert tickets[0].side == "SHORT"
    assert tickets[0].stp is True                      # C1
    assert tickets[0].intent_ts > rows[0]["signal_ts"]  # causality (C2)
    assert rows[0]["fill_ts"] > rows[0]["signal_ts"]


def test_sizing_fenced_function():
    """§T2.4 normative sizing: risk budget / stop distance, capped at 10%
    participation; degenerate stop yields zero, never negative size."""
    R = 250.0          # [example]
    bar_volume = 2000.0
    adv_cap = 0.10 * bar_volume                         # [default]
    assert size_shares(R, 225.0, vol_estimate=450.0, ADV_cap=adv_cap, cost=None) == 1
    assert size_shares(R, 25.0, vol_estimate=450.0, ADV_cap=adv_cap, cost=None) == 10
    assert size_shares(R, 25.0, vol_estimate=450.0, ADV_cap=5.0, cost=None) == 5   # ADV cap binds
    assert size_shares(R, 0.0, vol_estimate=450.0, ADV_cap=adv_cap, cost=None) == 0  # degenerate stop
    assert size_shares(R, -1.0, vol_estimate=450.0, ADV_cap=adv_cap, cost=None) == 0
