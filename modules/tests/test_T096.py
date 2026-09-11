"""Acceptance tests for T096 — Kalman + HMM Adaptive Trend.

Template v1.0.0 (strategy), module v1.1.0. Concrete sketch: loads the fixture
tape, runs a reference implementation of the chapter's normative pseudocode
(entry Boolean + exits + cooldown + locate check + cost gate + kill switch),
and asserts causality, ticket schema, the cost gate, kill-switch behavior,
and invalid-input handling.

Run: python3 -m pytest modules/tests/test_T096.py -q   (from repo root)
"""
import csv
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T096_tape.csv"
EXPECTED = FIX / "T096_expected.csv"

GATE_CFG = [('>=', 1.0), ('>=', 1.0), ('>=', 1.0)]   # [(op, threshold)] for g1, g2, g3
GATE_NAMES = ['hmm_trend', 'innov_ok', 'slope_ok']
COST_GATE_K = 0.5                       # [default]
PER_TRADE_R = 250        # $ risk per trade [example]
DAILY_LOSS_STOP_R = 12  # in units of R [default]
SYMBOL = 'KAL:XNAS'
PARENT_SIGNAL = 'S077'
INFRA = False  # normative emitter emits OrderTicket intents

NS_PER_MIN = 60_000_000_000


# ------------------------------------------------------------ schemas (App C/G)
@dataclass(frozen=True)
class OrderTicket:
    symbol: str
    side: str            # BUY | SELL | SHORT — intent, not a wire order
    qty: int             # > 0
    limit: float | None
    tif: str             # DAY | IOC | FOK | GTC | OPG | CLS
    ticket_id: str
    parent_signal: str   # "S<nnn>@<computed_at_ns>" (entries) or "EXIT@<ts>"
    intent_ts: int       # int64 ns UTC
    state: str           # NEW | WORKING | ...
    stp: bool = True     # self-trade prevention flag (C1)


@dataclass
class Config:
    """Single Config source — mirrors the §T0.2 table (module v1.1.0)."""
    innov_k: float = 1.5
    flatten_tol: float = 0.25
    chop_standdown_pct: float = 70.0
    chop_time_stop_bars: int = 15
    target_sigma_mult: float = 1.8
    stop_sigma_mult: float = 1.0
    cost_gate_k: float = 0.5
    risk_R_usd: float = 250.0
    equity_ref: float = 100000.0
    adv_cap_pct: float = 0.05
    max_concurrent: int = 2
    cooldown_min: int = 15
    daily_loss_stop_R: float = 12.0
    staleness_ttl_min: int = 15
    ref_notional: float = 60000.0
    vol_median: float = 0.02


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
    spread_bps = 1.5   # [example]
    fee_bps = 1.0         # [example]
    borrow_bps = 0.0   # [example] intraday; flat daily — no borrow leg
    impact_bps = 2.0   # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def size_position(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost_bps, cfg):
    """shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost)."""
    risk_usd = cfg.risk_R_usd                      # R budget in $ [example]
    cost_usd = cost_bps / 1e4 * cfg.ref_notional   # expected $ cost haircut [example]
    budget_net = max(risk_usd - cost_usd, 0.0)
    stop_leg = budget_net / max(stop_distance, 1e-12)   # shares the stop allows
    adv_leg = cfg.adv_cap_pct * ADV_cap            # 5% of ADV [example]
    if vol_estimate > 3.0 * cfg.vol_median:        # R001: halve in high vol [default]
        stop_leg *= 0.5
        adv_leg *= 0.5
    return int(max(min(stop_leg, adv_leg), 0))


# ------------------------------------------------- normative pseudocode stub
def emit(state: dict, rows: list[dict], cfg) -> list[OrderTicket]:
    """emit(state, signals, cfg) -> list[OrderTicket] — reference stub.

    Intents only (Appendix c v1.0.0): never places orders. Invalid input ->
    module_state UNKNOWN, never interpolated (F1/F2). Infra publishers (T081)
    publish bar boundaries downstream and never emit OrderTickets.
    """
    if isinstance(cfg, dict):
        cfg = Config(**{k: v for k, v in cfg.items() if hasattr(Config, k)})
    tickets = []
    kill = state.setdefault("kill", KillSwitch())
    state.setdefault("module_state", "OK")
    state.setdefault("position", 0)        # +1 long / -1 short / 0 flat (intent-side)
    state.setdefault("position_qty", 0)
    state.setdefault("cooldown_until", 0)  # int64 ns UTC; C10
    log = state.setdefault("decision_log", [])

    def chain_hash(prev, payload):
        return hashlib.sha256((prev + payload).encode()).hexdigest()[:16]

    def append(action, reason, payload, before, after):
        prev = log[-1]["hash"] if log else "genesis"
        log.append({"action": action, "reason": reason,
                     "state_before": before, "state_after": after,
                     "prev_hash": prev, "hash": chain_hash(prev, payload)})

    def exit_trigger(row):
        if row.get("flattened"):
            return "flatten"
        if row.get("chop_stop"):
            return "chop-stop"
        pnl = row.get("pnl_usd", 0.0)
        sig = row.get("sigma20_usd", 1.0)
        if pnl <= -cfg.stop_sigma_mult * sig:
            return "stop"
        if pnl >= cfg.target_sigma_mult * sig:
            return "target"
        return None

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

        # --- exits first: existing position; exits are never cost-gated ---
        if state["position"] != 0:
            trig = exit_trigger(row)
            if trig is not None:
                side = "SELL" if state["position"] > 0 else "BUY"
                t = OrderTicket(symbol=SYMBOL, side=side, qty=int(state["position_qty"]),
                                limit=None, tif="IOC", ticket_id=f"{uuid.uuid4()}",
                                parent_signal=f"EXIT@{sig_ts}",
                                intent_ts=sig_ts + 1000, state="NEW", stp=True)
                assert row["fill_ts"] > sig_ts, "causality: fill must be after signal (t->t+1)"
                tickets.append(t)
                append("EMIT_INTENT", f"exit:{trig}", t.ticket_id + t.parent_signal,
                       before, state["module_state"])
                state["position"], state["position_qty"] = 0, 0
                state["cooldown_until"] = sig_ts + cfg.cooldown_min * NS_PER_MIN  # C10
            continue  # no entries while a position is open

        # Entry Boolean: three chapter gates (all must pass)
        gates = []
        for (op, th), v in zip(GATE_CFG, (row["g1"], row["g2"], row["g3"])):
            gates.append(v >= th if op == ">=" else (v <= th if op == "<=" else (v > th if op == ">" else v < th)))
        if not all(gates):
            append("GATE_VETO", "entry-boolean", f"veto@{sig_ts}", before, before)
            continue
        # C10: post-exit cooldown suppresses re-entry
        if sig_ts < state["cooldown_until"]:
            append("GATE_VETO", "cooldown", f"cooldown-veto@{sig_ts}", before, before)
            continue
        # Normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
        cost = expected_cost_bps(row["qty"] * row["price"], 0.001, "venue", "taker", "normal")
        if not (cost <= cfg.cost_gate_k * row["edge_bps"]):
            append("GATE_VETO", "cost-gate", f"cost-veto@{sig_ts}", before, before)
            continue
        if row["side"] == "SHORT" and not row.get("locate_ok", False):
            append("GATE_VETO", "locate", f"C7-veto@{sig_ts}", before, before)  # C7
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


def good_row(**kw):
    """A gate-passing entry row; override fields as needed."""
    base = {"bar": 0, "signal_ts": 1700000000000000000, "fill_ts": 1700000300000000000,
            "side": "LONG", "edge_bps": 22.0, "g1": 1.0, "g2": 1.0, "g3": 1.0,
            "price": 75.0, "qty": 800, "valid": True}
    base.update(kw)
    return base


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
    assert not (cost <= k * 0.9)  # tiny edge -> gate blocks


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


def test_post_exit_cooldown_blocks_reentry():
    """C10: after an exit, re-entry is vetoed until cooldown_until elapses."""
    state = {"position": 1, "position_qty": 800}
    t0 = 1700000000000000000
    exit_row = good_row(signal_ts=t0, fill_ts=t0 + 300_000_000_000, flattened=True)
    outs = emit(state, [exit_row], {})
    assert len(outs) == 1 and outs[0].side == "SELL"
    cd = state["cooldown_until"]
    assert cd == t0 + 15 * NS_PER_MIN            # 15 min [default]
    # Re-entry one minute later: vetoed even though every gate passes.
    soon = good_row(signal_ts=t0 + NS_PER_MIN, fill_ts=t0 + 2 * NS_PER_MIN)
    assert emit(state, [soon], {}) == []
    assert any(r["reason"] == "cooldown" for r in state["decision_log"])
    # After the cooldown: entry passes again.
    later = good_row(signal_ts=t0 + 16 * NS_PER_MIN, fill_ts=t0 + 17 * NS_PER_MIN)
    assert len(emit(state, [later], {})) == 1


def test_short_requires_locate():
    """C7: SHORT without locate_ok is vetoed; with locate_ok it passes gates."""
    no_locate = good_row(side="SHORT", locate_ok=False)
    state = {}
    assert emit(state, [no_locate], {}) == []
    assert any(r["reason"] == "locate" for r in state["decision_log"])
    state2 = {}
    ok_locate = good_row(side="SHORT", locate_ok=True,
                         signal_ts=1700000600000000000, fill_ts=1700000900000000000)
    outs = emit(state2, [ok_locate], {})
    assert len(outs) == 1 and outs[0].side == "SHORT"


def test_exits_never_cost_gated():
    """Exits fire on flatten/stop/target/chop-stop even when the cost gate would block entry."""
    cfg = Config()
    t0 = 1700000000000000000
    for trig, kw in [("flatten", {"flattened": True}),
                     ("stop", {"pnl_usd": -200.0, "sigma20_usd": 100.0}),
                     ("target", {"pnl_usd": 300.0, "sigma20_usd": 100.0}),
                     ("chop-stop", {"chop_stop": True})]:
        state = {"position": 1, "position_qty": 800}
        row = good_row(signal_ts=t0, fill_ts=t0 + 300_000_000_000,
                       edge_bps=0.01, **kw)  # edge so tiny the entry cost gate blocks
        outs = emit(state, [row], cfg)
        assert len(outs) == 1, trig
        assert outs[0].side == "SELL", trig
        assert state["position"] == 0, trig
        assert state["cooldown_until"] == t0 + cfg.cooldown_min * NS_PER_MIN, trig


def test_sizing_legs_and_r001_halve():
    """size_position: stop leg binds; ADV leg binds; cost haircut; R001 halve."""
    cfg = Config()
    # Stop leg binds: ($250 - $27 cost haircut) / $2.50 stop = 89 sh; ADV leg huge.
    q = size_position(250.0, 2.50, 0.01, 1_000_000, 4.5, cfg)
    assert q == int((250.0 - 4.5 / 1e4 * 60000.0) / 2.50)  # cost haircut then stop leg
    # ADV leg binds: 5% of 1,000 sh = 50.
    assert size_position(250.0, 0.01, 0.01, 1_000, 0.0, cfg) == 50
    # R001: vol > 3x median halves both legs.
    q_hi = size_position(250.0, 2.50, 0.10, 1_000_000, 0.0, cfg)
    q_lo = size_position(250.0, 2.50, 0.01, 1_000_000, 0.0, cfg)
    assert q_hi * 2 == q_lo
