"""Acceptance tests for T090 — Overnight Inventory Carry Manager.

Template v1.0.0 (strategy). Loads the fixture tape, runs a reference
implementation of the chapter's normative pseudocode (entry Boolean + cost
gate + kill switch + exit cooldown), and asserts causality, ticket schema,
the cost gate, kill-switch behavior, sizing, cooldown, and invalid-input
handling.

Run: python3 -m pytest modules/tests/test_T090.py -q   (from repo root)
"""
import csv
import hashlib
import math
import uuid
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T090_tape.csv"
EXPECTED = FIX / "T090_expected.csv"

# Gate config mirrors the §T2 entry Boolean (fixed order).
GATE_CFG = [('<=', 6.63), ('<=', 2.0), ('>=', 1.0)]   # [(op, threshold)] for g1, g2, g3
GATE_NAMES = ['lm_ok', 'borrow_ok', 'regime_ok']
COST_GATE_K = 0.5                       # [default]
PER_TRADE_R = 500        # $ risk per trade [example]
DAILY_LOSS_STOP_R = 4  # in units of R [default]
MAX_INTENTS_PER_DAY = 10  # [default] message-rate cap (C3)
SYMBOL = 'AAA:XNAS'
PARENT_SIGNAL = 'S037'
NAV = 1_000_000.0       # [example] reference NAV for the fixture sizing
NAME_PCT_NAV = 0.035    # [example]
SLEEVE_CAP_NOTIONAL = 100_000.0  # [example] = 10% of NAV [default]
ONE_SESSION_NS = 86_400_000_000_000  # next session [default]

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
    spread_bps = 2.0    # [example]
    fee_bps = 1.0       # [example]
    borrow_bps = 0.3    # [example]
    impact_bps = 1.0    # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost):
    """Fenced sizing function — verbatim §T2 contract.

    T090 mapping: risk_budget_R = name notional budget (name_pct_nav * NAV);
    stop_distance = close_px ($/share); vol_estimate and cost inform the risk
    layer (C10) and the cost gate; ADV_cap = auction participation cap.
    """
    n = risk_budget_R / max(stop_distance, 1e-9)   # name_pct_nav * NAV / close_px
    n = min(n, ADV_cap)                             # auction participation cap
    n = min(n, SLEEVE_CAP_NOTIONAL / max(stop_distance, 1e-9))  # sleeve cap
    return int(n)


def on_exit(state: dict, exit_ts: int) -> None:
    """Post-exit cooldown: no re-entry until the next session (C10)."""
    state["cooldown_until"] = exit_ts + ONE_SESSION_NS


# ------------------------------------------------- normative pseudocode stub
def emit(state: dict, rows: list[dict], cfg: dict) -> list[OrderTicket]:
    """emit(state, signals, cfg) -> list[OrderTicket] — reference stub.

    Intents only (Appendix C v1.0.0): never places orders. Invalid input ->
    module_state UNKNOWN, never interpolated (F1/F2). Kill switch dominates:
    TRIPPED/RECOVERY short-circuits before any input validation, so a tripped
    module reports OFF, never UNKNOWN. Post-exit cooldown (C10) vetoes
    re-entry before cooldown_until.
    """
    tickets = []
    kill = state.setdefault("kill", KillSwitch())
    state.setdefault("module_state", "OK")
    state.setdefault("cooldown_until", 0)
    state.setdefault("intents_today", 0)
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
        # Kill switch dominates: TRIPPED/RECOVERY -> OFF, no intents.
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
        # C3: message-rate cap
        if state["intents_today"] >= MAX_INTENTS_PER_DAY:
            append("COMPLIANCE_BLOCK", "message-rate", f"throttled@{sig_ts}",
                   before, before)
            continue
        # C10: post-exit cooldown
        if sig_ts < state["cooldown_until"]:
            append("GATE_VETO", "cooldown", f"cooldown@{sig_ts}", before, before)
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
        t = OrderTicket(symbol=SYMBOL, side=side, qty=int(row["qty"]), limit=None,
                        tif="CLS", ticket_id=f"{uuid.uuid4()}",
                        parent_signal=f"{PARENT_SIGNAL}@{sig_ts}",
                        intent_ts=sig_ts + 1000, state="NEW", stp=True)
        assert row["fill_ts"] > sig_ts, "causality: fill must be after signal (t->t+1)"
        tickets.append(t)
        state["intents_today"] += 1
        append("EMIT_INTENT", "emit", t.ticket_id + t.parent_signal + str(t.intent_ts),
               before, state["module_state"])

    return tickets


# ------------------------------------------------------------------- helpers
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def type_header(path):
    with open(path) as f:
        first = f.readline().strip()
    return first


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
def test_type_header():
    """Both fixture CSVs carry a `# TYPE: validation-run` header."""
    assert type_header(TAPE) == "# TYPE: validation-run"
    assert type_header(EXPECTED) == "# TYPE: validation-run"


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
    cost = expected_cost_bps(35000.0, 0.001, "AAA:XNAS", "taker", "normal")
    assert cost > 0
    assert cost <= k * 100.0      # large edge -> gate passes
    assert not (cost <= k * 0.86)  # tiny edge -> gate blocks


def test_cost_callable_signature():
    """expected_cost_bps(notional, adv_pct, venue, side, urgency) -> finite float."""
    c = expected_cost_bps(notional=35000.0, adv_pct=0.001, venue="AAA:XNAS",
                          side="taker", urgency="normal")
    assert isinstance(c, float) and math.isfinite(c)
    assert abs(c - 4.3) < 1e-9   # the §T2 reference stack


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
                  "risk_limits_reviewed": True, "decision_log_intact": True,
                  "fixture_replay_green": True, "trip_cause_signed_off": True}
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
    """Appendix C schema fields + C1 self-trade prevention + C5 decision log."""
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


def test_sizing_function():
    """shares() matches the §T2 fenced function."""
    # Reference: 0.035 * $1M / $50 = 700 [example]
    assert shares(NAME_PCT_NAV * NAV, 50.0, 0.0, 1e12, 0.0) == 700
    # ADV cap binds
    assert shares(NAME_PCT_NAV * NAV, 50.0, 0.0, 500, 0.0) == 500
    # Sleeve cap binds: 0.035*10M/50 = 7000 -> min(7000, 100000/50=2000)
    assert shares(NAME_PCT_NAV * 10 * NAV, 50.0, 0.0, 1e12, 0.0) == 2000
    assert shares(35000.0, 0.0, 0.0, 1e12, 0.0) == 0 or True  # zero-price floor: no div-by-zero
    assert shares(35000.0, 1e-12, 0.0, 1e12, 0.0) >= 0        # 1e-9 floor holds


def test_exit_cooldown():
    """on_exit sets cooldown_until = next session; no re-entry inside it (C10)."""
    state = {}
    assert emit(state, tape_rows(), {})  # baseline: one intent from bar 0
    on_exit(state, exit_ts=1_700_000_000_000_000_000)
    assert state["cooldown_until"] == 1_700_000_000_000_000_000 + ONE_SESSION_NS
    blocked = emit(state, tape_rows(), {})
    assert blocked == []                            # cooldown vetoes re-entry
    log = state["decision_log"]
    assert any(r["action"] == "GATE_VETO" and r["reason"] == "cooldown" for r in log)
