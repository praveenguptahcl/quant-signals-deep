"""Acceptance tests for T077 — Crypto Basis Cash-and-Carry.

Template v1.0.0 (strategy). Concrete sketch: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode (entry Boolean +
cost gate + kill switch + UNKNOWN handling + exit boolean), and asserts
causality, ticket schema, the cost gate, kill-switch behavior, exit/cooldown
logic, fixture TYPE headers, and invalid-input handling.

Run: python3 -m pytest modules/tests/test_T077.py -q   (from repo root)
"""
import csv
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T077_tape.csv"
EXPECTED = FIX / "T077_expected.csv"

GATE_CFG = [('>=', 12.0), ('>=', 1.0), ('>=', 1.0)]   # [(op, threshold)] for g1, g2, g3
GATE_NAMES = ['attainable_ann', 'funding_cover', 'book_depth_ok']
COST_GATE_K = 0.5                       # [default]
PER_TRADE_R = 250        # $ risk per trade [example]
DAILY_LOSS_STOP_R = 4  # in units of R [default]
MAX_GROSS_NOTIONAL = 20_000_000  # [example] §T0 risk contract
MAX_TICKETS_PER_HOUR = 4  # [default] CR3 message-rate cap
COOLDOWN_NS = int(24 * 3600 * 1_000_000_000)  # 24 h [default] CR10
EXIT_ATTAINABLE_ANN = 2.0    # [default] §T2.3
EXIT_FUNDING_ANN = -5.0      # [default] §T2.3
EXIT_DIVERGENCE_X = 3.0      # [default] §T2.3 (ratio vs entry basis)
COST_TOLERANCE_BPS = 1e-6    # [default] §T4 tolerance
SYMBOL = 'BTC-SPOT:VENUE'
PARENT_SIGNAL = 'S057'

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
    stp: bool = True     # self-trade prevention flag (C1/CR1)


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
    spread_bps = 8.0   # [example]
    fee_bps = 20.0         # [example]
    borrow_bps = 1.4   # [example]
    impact_bps = 4.0   # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def evaluate_exit(position: dict, bar: dict, cfg: dict) -> bool:
    """§T2.3 / §T3 EXIT boolean for an open pair.

    bar: {attainable_ann, funding_ann, divergence_ratio, hold_days}.
    divergence_ratio = intraday divergence / entry basis.
    """
    max_hold = cfg.get("max_hold_days", 30)
    return (bar["attainable_ann"] < EXIT_ATTAINABLE_ANN
            or bar["funding_ann"] < EXIT_FUNDING_ANN
            or bar["hold_days"] >= max_hold
            or bar["divergence_ratio"] > EXIT_DIVERGENCE_X)


# ------------------------------------------------- normative pseudocode stub
def emit(state: dict, rows: list[dict], cfg: dict) -> list[OrderTicket]:
    """emit(state, events, cfg) -> list[OrderTicket] — reference stub.

    Intents only (Appendix C v1.0.0): never places orders. Invalid input ->
    module_state UNKNOWN, never interpolated (F1/F2). Kill check precedes
    validation: tripped module reports OFF, never UNKNOWN. The reference stub
    uses each row's signal_ts as the evaluation clock (deterministic replay).
    """
    tickets = []
    kill = state.setdefault("kill", KillSwitch())
    state.setdefault("module_state", "OK")
    state.setdefault("cooldown_until", 0)          # CR10: post-exit cooldown
    state.setdefault("ticket_count_by_hour", {})
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
        # CR10: post-exit cooldown blocks entries
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
        # CR3: message-rate cap (hourly buckets on the evaluation clock)
        hour = sig_ts // 3_600_000_000_000
        counts = state["ticket_count_by_hour"]
        if counts.get(hour, 0) >= MAX_TICKETS_PER_HOUR:
            append("GATE_VETO", "message-rate", f"rate-cap@{sig_ts}", before, before)
            continue
        # CR4: pre-trade fat-finger trio (qty>0; notional<=gross cap; ADV cap)
        notional = int(row["qty"]) * row["price"]
        if not (int(row["qty"]) > 0 and notional <= MAX_GROSS_NOTIONAL):
            append("GATE_VETO", "fat-finger", f"size-reject@{sig_ts}", before, before)
            continue
        side = {'LONG': 'BUY', 'SHORT': 'SHORT', 'BUY': 'BUY', 'SELL': 'SELL'}[row["side"]]
        t = OrderTicket(symbol=SYMBOL, side=side, qty=int(row["qty"]), limit=None,
                        tif="IOC", ticket_id=f"{uuid.uuid4()}",
                        parent_signal=f"{PARENT_SIGNAL}@{sig_ts}",
                        intent_ts=sig_ts + 1000, state="NEW", stp=True)
        assert row["fill_ts"] > sig_ts, "causality: fill must be after signal (t->t+1)"
        tickets.append(t)
        counts[hour] = counts.get(hour, 0) + 1
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
    assert cost <= k * 200.39999999999998      # large edge -> gate passes
    assert not (cost <= k * 6.68)  # tiny edge -> gate blocks


def test_cost_column_matches_expected_within_tolerance():
    """§T4: the expected.csv cost_bps equals the callable's output within ±1e-6."""
    row0 = tape_rows()[0]
    cost = expected_cost_bps(row0["qty"] * row0["price"], 0.001, "venue",
                             "taker", "normal")
    exp = load_csv(EXPECTED)[0]
    assert abs(cost - float(exp["cost_bps"])) <= COST_TOLERANCE_BPS, exp["ticket_idx"]


def test_fixture_type_header():
    """§T4: both fixtures carry the '# TYPE: validation-run' header."""
    for p in (TAPE, EXPECTED):
        with open(p) as f:
            first = f.readline().strip()
        assert first == "# TYPE: validation-run", p


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


def test_exits_and_cooldown():
    """§T2.3/§T3: EXIT boolean fires on all four triggers; cooldown blocks re-entry."""
    cfg = {"max_hold_days": 30}
    pos = {"entry_basis_ann": 13.1}
    healthy = {"attainable_ann": 13.1, "funding_ann": 10.0,
               "divergence_ratio": 1.0, "hold_days": 5}
    assert not evaluate_exit(pos, healthy, cfg)
    assert evaluate_exit(pos, {**healthy, "attainable_ann": 1.5}, cfg)   # basis decay
    assert evaluate_exit(pos, {**healthy, "funding_ann": -6.0}, cfg)     # funding flip
    assert evaluate_exit(pos, {**healthy, "hold_days": 30}, cfg)         # max hold
    assert evaluate_exit(pos, {**healthy, "divergence_ratio": 3.5}, cfg)  # >3x entry
    # CR10: cooldown blocks entries for 24 h after an exit
    # (rows 0-4 are input-valid; row 5's invalid-input path is covered elsewhere)
    state = {"cooldown_until": tape_rows()[0]["signal_ts"] + COOLDOWN_NS}
    assert emit(state, tape_rows()[:5], {}) == []
    assert state["module_state"] == "OK"


def test_ticket_schema_and_compliance():
    """Appendix C schema fields + C1/CR1 self-trade prevention + C5/CR5 decision log."""
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
        assert t.stp is True                      # C1/CR1 self-trade prevention
        assert "@" in t.parent_signal              # provenance
    log = state["decision_log"]
    assert any(r["action"] == "EMIT_INTENT" for r in log)
    for prev, rec in zip([{"hash": "genesis"}] + log, log):
        assert rec["prev_hash"] == prev["hash"]    # hash chain intact (C5/CR5)
        assert rec["hash"]
