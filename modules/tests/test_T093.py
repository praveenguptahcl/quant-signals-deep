"""Acceptance tests for T093 — Options-to-Equity Lead Trader.

Template v1.0.0 (strategy). Concrete sketch: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode (entry Boolean +
cost gate + kill switch + earnings blackout + exit trigger + sizing), and
asserts causality, ticket schema, the cost gate, kill-switch behavior,
invalid-input handling, and the S_B composite.

Run: python3 -m pytest modules/tests/test_T093.py -q   (from repo root)
"""
import csv
import hashlib
import math
import uuid
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T093_tape.csv"
EXPECTED = FIX / "T093_expected.csv"

GATE_CFG = [('>=', 1.25), ('>=', 3.0), ('<=', 10.0)]   # [(op, threshold)] for g1, g2, g3
GATE_NAMES = ['S_B', 'call_ratio', 'spread_ok']
COST_GATE_K = 0.5                       # [default]
PER_TRADE_R = 400        # $ risk per trade [example]
DAILY_LOSS_STOP_R = 8  # in units of R [default]
BLACKOUT_SESSIONS = 2  # earnings blackout [default]
MAX_GROSS_NOTIONAL = 5_000_000  # $ [example]
SYMBOL = 'OPT:XNAS'
PARENT_SIGNAL = 'S071'
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
    fee_bps = 1.0         # [example]
    borrow_bps = 0.0   # [default] borrow_bps_per_day=0.0: long-only reference build
    impact_bps = 2.0   # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def composite_SB(z_skew25, z_flow, z_leadlag) -> float:
    """S_B = 0.45*z_skew25 + 0.35*z_flow + 0.20*z_leadlag [example]."""
    return 0.45 * z_skew25 + 0.35 * z_flow + 0.20 * z_leadlag


def size(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost) -> int:
    """Normative sizing: shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost)."""
    q = risk_budget_R / max(stop_distance, 1e-9)
    q = min(q, ADV_cap)
    return int(q)


def exit_trigger(d: dict, pos: dict, cfg: dict) -> bool:
    """Normative exit rule (§T3): skew revert | stop | target | time stop."""
    skew_reverted = abs(d["skew_25d"] - d["skew_25d_mean20"]) <= cfg["skew_revert_tol"]
    stopped = d["last_price"] <= pos["entry_px"] - cfg["stop_mult"] * d["sigma_20d"]
    targeted = d["last_price"] >= pos["entry_px"] + cfg["target_mult"] * d["sigma_20d"]
    timed_out = d["sessions_held"] >= cfg["time_stop_d"]
    return skew_reverted or stopped or targeted or timed_out


# ------------------------------------------------- normative pseudocode stub
def emit(state: dict, rows: list[dict], cfg: dict) -> list[OrderTicket]:
    """emit(state, signals, cfg) -> list[OrderTicket] — reference stub.

    Intents only (Appendix C v1.0.0): never places orders. Invalid input ->
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
        # C11: earnings blackout veto (logged, module stays OK)
        if row["sessions_to_earnings"] <= BLACKOUT_SESSIONS:
            append("GATE_VETO", "earnings-blackout", f"blackout@{sig_ts}", before, before)
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
        # C14: pre-trade fat-finger trio
        notional = row["qty"] * row["price"]
        if not (row["qty"] > 0 and notional <= MAX_GROSS_NOTIONAL):
            append("COMPLIANCE_BLOCK", "fat-finger", f"size-block@{sig_ts}", before, before)
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
                      "valid": int(r["valid"]) == 1,
                      "sessions_to_earnings": int(r["sessions_to_earnings"])})
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
        assert abs(float(e["cost_bps"]) - expected_cost_bps(
            t.qty * 150.0, 0.001, "OPT:XNAS", "taker", "normal")) <= 1e-4, e["ticket_idx"]


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
    assert not (cost <= k * 1.0)  # tiny edge -> gate blocks


def test_cost_stack_single_source():
    """The callable sums to the §T2 COST block reference total (5.00 bps [example])."""
    assert abs(expected_cost_bps(39900.0, 0.001, "OPT:XNAS", "taker", "normal") - 5.0) < 1e-9


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
             "price": -1.0, "qty": 100, "valid": 1, "sessions_to_earnings": 10}]  # negative price
    assert emit(state, bad, {}) == []
    assert state["module_state"] == "UNKNOWN"
    state2 = {}
    bad2 = [{"bar": 0, "signal_ts": 1, "fill_ts": 2, "side": "LONG",
              "edge_bps": 50.0, "g1": 99.0, "g2": 99.0, "g3": 99.0,
              "price": 100.0, "qty": 100, "valid": 0, "sessions_to_earnings": 10}]  # valid flag false
    assert emit(state2, bad2, {}) == []
    assert state2["module_state"] == "UNKNOWN"


def test_earnings_blackout_veto():
    """C11: sessions_to_earnings <= 2 vetoes the entry; module stays OK."""
    rows = tape_rows()
    blackout = [r for r in rows if r["bar"] == 6]
    assert len(blackout) == 1
    state = {}
    assert emit(state, blackout, {}) == []
    assert state["module_state"] == "OK"
    assert any(r["action"] == "GATE_VETO" and r["reason"] == "earnings-blackout"
               for r in state["decision_log"])


def test_composite_SB_weights():
    """S_B = 0.45*z_skew25 + 0.35*z_flow + 0.20*z_leadlag [example]; weights sum to 1.0."""
    assert math.isclose(composite_SB(1.0, 1.0, 1.0), 1.0, rel_tol=1e-12)
    assert math.isclose(composite_SB(2.0, 1.0, 0.0), 0.45 * 2.0 + 0.35 * 1.0, rel_tol=1e-12)


def test_sizing_and_exit_trigger():
    """Normative size() and exit_trigger() behave per §T3."""
    q = size(risk_budget_R=0.0040 * 1_000_000, stop_distance=1.1 * 2.0,
             vol_estimate=2.0, ADV_cap=0.05 * 10_000_000, cost=5.0)
    assert q == int(min(0.0040 * 1_000_000 / (1.1 * 2.0), 0.05 * 10_000_000))
    cfg = {"skew_revert_tol": 0.5, "stop_mult": 1.1, "target_mult": 2.2, "time_stop_d": 8}
    base = {"skew_25d": 3.0, "skew_25d_mean20": 3.0, "last_price": 150.0,
            "sigma_20d": 2.0, "sessions_held": 3}
    pos = {"entry_px": 150.0}
    assert exit_trigger(base, pos, cfg) is True      # skew reverted to mean
    d2 = dict(base, skew_25d=5.0)
    assert exit_trigger(d2, pos, cfg) is False        # nothing fires
    d3 = dict(d2, last_price=150.0 - 1.1 * 2.0 - 0.01)
    assert exit_trigger(d3, pos, cfg) is True         # hard stop
    d4 = dict(d2, sessions_held=8)
    assert exit_trigger(d4, pos, cfg) is True         # time stop


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
