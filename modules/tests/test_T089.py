"""Acceptance tests for T089 — Quote-Matcher (SIP-vs-Direct).

Template v1.0.0 (strategy). Concrete sketch: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode (entry Boolean +
cost gate + kill switch), and asserts causality, ticket schema, the cost gate,
kill-switch behavior, and invalid-input handling.

Run: python3 -m pytest modules/tests/test_T089.py -q   (from repo root)
"""
import csv
import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pytest

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T089_tape.csv"
EXPECTED = FIX / "T089_expected.csv"

GATE_CFG = [('>=', 0.9), ('>=', 1.0), ('<=', 5.0)]   # [(op, threshold)] for g1, g2, g3
GATE_NAMES = ['disloc_cents', 'futures_ok', 'not_news']
COST_GATE_K = 0.5                       # [default]
PER_TRADE_R = 25        # $ risk per trade [example]
DAILY_LOSS_STOP_R = 12  # in units of R [default]
ADV_CAP_SHARES = 600    # participation cap per event [default]
MAX_GROSS_NOTIONAL = 120_000  # $ [example]
SYMBOL = 'LGX:XNAS'
PARENT_SIGNAL = 'S016'
INFRA = False  # normative emitter emits OrderTicket intents


@dataclass(frozen=True)
class Config:
    """§T0 T0.1 Config dataclass — single source of module parameters."""
    gate_cents: float = 0.9
    abort_cents: float = 5.0
    feed_gap_max_ms: float = 5.0
    max_events_day: int = 8
    qty_default: int = 400          # [example]
    adv_cap_shares: int = 600       # [default]
    cost_gate_k: float = 0.5        # [default]
    per_trade_R: float = 25.0       # [example]
    daily_loss_stop_R: float = 12.0  # [default]
    cooldown_s: float = 1.0         # [default]


def size_shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost) -> int:
    """§T2.3b normative sizing: shares = f(risk_budget_R, stop_distance,
    vol_estimate, ADV_cap, cost). cost gates entry upstream; it does not
    resize here. Reference: size_shares(25.0, 0.05, 200.0, 600, 2.3) == 500."""
    risk_shares = risk_budget_R / max(stop_distance, 1e-9)  # 1e-9 floor [default]
    return max(0, int(min(risk_shares, ADV_cap)))

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
    spread_bps = 1.2   # [example]
    fee_bps = 0.6         # [example]
    borrow_bps = 0.0   # [example]
    impact_bps = 0.5   # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


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
    state.setdefault("cooldown_until", 0)   # CR-10 post-exit cooldown (int64 ns)
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
        # CR-10: post-exit cooldown
        if sig_ts < state["cooldown_until"]:
            append("GATE_VETO", "cooldown", f"cooldown@{sig_ts}", before, before)
            continue
        # CR-04: pre-trade fat-finger trio (validation run: qty is a measured case input)
        qty = int(row["qty"])
        assert 0 < qty <= ADV_CAP_SHARES, "CR-04 size check"
        assert row["price"] * qty <= MAX_GROSS_NOTIONAL, "CR-04 value check"
        side = {'LONG': 'BUY', 'SHORT': 'SHORT', 'BUY': 'BUY', 'SELL': 'SELL'}[row["side"]]
        t = OrderTicket(symbol=SYMBOL, side=side, qty=qty, limit=None,
                        tif="IOC", ticket_id=f"{uuid.uuid4()}",
                        parent_signal=f"{PARENT_SIGNAL}@{sig_ts}",
                        intent_ts=sig_ts + 1000, state="NEW", stp=True)
        assert row["fill_ts"] > sig_ts, "causality: fill must be after signal (t->t+1)"
        tickets.append(t)
        state["cooldown_until"] = sig_ts + int(1.0 * 1e9)  # CR-10: 1 s [default]
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
    assert cost == pytest.approx(2.30, abs=1e-4)   # §T4 tolerance on cost_bps
    assert cost > 0
    assert cost <= k * 100.0      # large edge -> gate passes
    assert not (cost <= k * 0.45999999999999996)  # tiny edge -> gate blocks


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


def test_config_defaults():
    """§T0 T0.1: the Config dataclass defaults match the documented contract."""
    cfg = Config()
    assert cfg.gate_cents == 0.9
    assert cfg.abort_cents == 5.0
    assert cfg.feed_gap_max_ms == 5.0
    assert cfg.max_events_day == 8
    assert cfg.qty_default == 400
    assert cfg.adv_cap_shares == 600
    assert cfg.cost_gate_k == 0.5
    assert cfg.per_trade_R == 25.0
    assert cfg.daily_loss_stop_R == 12.0
    assert cfg.cooldown_s == 1.0


def test_size_shares_contract():
    """§T2.3b: shares = min(risk_budget_R / stop_distance, ADV_cap), floored at 0."""
    assert size_shares(25.0, 0.05, 200.0, 600, 2.3) == 500   # reference: fixture bar-1 qty
    assert size_shares(25.0, 0.01, 200.0, 600, 2.3) == 600    # ADV cap binds
    assert size_shares(50.0, 0.05, 200.0, 10_000, 2.3) == 1000  # risk budget scales
    assert size_shares(25.0, 0.0, 200.0, 600, 2.3) == 600     # degenerate stop -> cap
    assert size_shares(25.0, -1.0, 200.0, 600, 2.3) == 600    # negative stop -> cap
    assert isinstance(size_shares(25.0, 0.05, 200.0, 600, 2.3), int)


def test_regime_record_schema():
    """§T9: regime gates are machine records with the mandated keys and enums."""
    rec = {"regime_id": "R001", "direction": "degrades",
           "mechanism": "vol spike -> dislocations are news, not staleness -> abort",
           "condition": "disloc_cents > 5", "action": "veto",
           "min_lag": "1 event", "unknown_behavior": "veto"}
    assert set(rec) == {"regime_id", "direction", "mechanism", "condition",
                        "action", "min_lag", "unknown_behavior"}
    assert rec["direction"] in ("amplifies", "degrades", "inverts")
    assert rec["action"] in ("veto", "halve", "double", "widen_stops", "pause_entry")


def test_timing_box_ordering():
    """§T2 timing box: signal_ts < intent_ts < fill_ts on every emitted ticket."""
    rows = tape_rows()
    tickets = emit({}, rows, {})
    exp_fill = {int(x["intent_ts"]): int(x["fill_ts"]) for x in load_csv(EXPECTED)}
    assert tickets, "fixture must produce at least one intent"
    for t in tickets:
        signal_ts = int(t.parent_signal.split("@")[1])
        assert t.intent_ts > signal_ts, "intent must be after signal"
        assert exp_fill[t.intent_ts] > t.intent_ts, "fill must be after intent"

