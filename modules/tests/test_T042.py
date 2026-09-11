"""Acceptance tests for T042 - Jump-Robust Vol Spike Trader (v1.1.0).

Template v1.0.0. Concrete sketch: loads the fixture tape, runs the module's
reference emit() (normative pseudocode via process_bar), and asserts the
TYPE header, fixture-vs-expected agreement, causality (no-signal-bar fills),
the cost-gate predicate, kill-switch trip/re-arm, invalid-input handling,
jump/proxy stand-downs, the post-exit cooldown, jump and adverse-stop exits,
and the cost-aware position sizer.

Run: python3 -m pytest modules/tests/test_T042.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, replace
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T042_tape.csv"
EXPECTED = FIX / "T042_expected.csv"

TOL = 1e-9  # tolerance on float comparisons



"""Reference implementation for T-module acceptance tests (shared sketch).

Implements the module's normative emit() contract:
    emit(state, signals, cfg) -> list[OrderTicket]
at one-bar granularity via process_bar(). Strategies emit ORDER INTENTS
ONLY (Appendix C v1.0.0); execution/broker layers create orders.
"""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class OrderTicket:
    symbol: str
    side: str            # BUY | SELL | SHORT - intent, not a wire order
    qty: int             # shares, integer, > 0
    limit: float | None  # limit price; None = marketable intent
    tif: str             # DAY | IOC | FOK | GTC | OPG | CLS
    ticket_id: str       # module-generated idempotency key
    parent_signal: str   # "S<nnn>@<computed_at_ns>" - full provenance
    intent_ts: int       # int64 ns UTC - when the intent was emitted
    state: str           # NEW | WORKING | ... (intent-side mirror only)


@dataclass
class Config:
    sid: str = "T000"
    primary_signal: str = "S000"
    bv_window_min: int = 5
    jump_pvalue: float = 0.01
    z_entry: float = 2.0
    z_exit: float = 0.5
    cost_gate_k: float = 0.5
    risk_R_usd: float = 1000.0
    stop_bps: float = 100.0
    adv_cap_pct: float = 10.0
    spread_full_bps: float = 10.0
    taker_fee_bps: float = 0.30
    maker_rebate_bps: float = 0.20
    side_exec: str = "taker"        # taker | maker
    borrow_bps: float = 0.0         # per-round-trip example borrow charge (SHORT)
    impact_k: float = 0.5
    daily_loss_stop_pct: float = -2.0
    venue: str = "XNAS"
    default_side: str = "BUY"      # BUY | SHORT
    cooldown_bars: int = 78         # post-exit cooldown, bars (C10)


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


def expected_cost_bps(notional, adv_pct, venue, side, urgency, cfg):
    """4-component cost stack (COST-block callable). Example values."""
    spread_bps = cfg.spread_full_bps / 2.0
    fee_bps = cfg.maker_rebate_bps if side == "maker" else cfg.taker_fee_bps
    borrow_bps = cfg.borrow_bps if cfg.default_side == "SHORT" else 0.0
    impact_bps = cfg.impact_k * math.sqrt(max(adv_pct, 0.0) / 100.0)
    if urgency == "high":
        impact_bps *= 1.5
    return spread_bps + fee_bps + borrow_bps + impact_bps


def size_vol(risk_R_usd, stop_bps, px, adv_shares, adv_pct, notional,
             venue, urgency, edge_bps, cfg, apply_gate=True):
    """shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost).

    Entry path (apply_gate=True): an unaffordable size returns 0 and emit()
    vetoes via the normative cost-gate predicate. Exit path: exits are never
    cost-gated, so the gate is bypassed.
    """
    raw = risk_R_usd / max(stop_bps / 1e4 * px, 1e-9)
    qty = min(raw, cfg.adv_cap_pct / 100 * adv_shares)
    if apply_gate:
        cost = expected_cost_bps(notional, adv_pct, venue, cfg.side_exec,
                                 urgency, cfg)
        if cost > cfg.cost_gate_k * edge_bps:
            return 0
    return max(1, int(qty))


def stopped(state, bar, cfg):
    """Adverse stop: long-vol position moved against entry by >= stop_bps."""
    ep = state.get("entry_px")
    return bool(state.get("position", 0) > 0 and ep
                and (ep - bar["close"]) / ep * 1e4 >= cfg.stop_bps)


def process_bar(state, bar, cfg):
    """One bar through the strategy. Returns (ticket|None, module_state, note).

    Mirrors the module's normative pseudocode: validate (F1/F2) -> kill
    switch -> exit logic (band / jump arrival / adverse stop) -> jump and
    proxy stand-downs -> post-exit cooldown (C10) -> normative cost-gate
    predicate -> entry. Earliest fill for a bar-t intent is bar t+1's open
    (t -> t+1).
    """
    ks = state["kill"]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if (bar["close"] <= 0 or bar["market_state"] != "CONTINUOUS_TRADING"
            or bar["asof_ts"] < bar["event_ts"]):
        state["position"] = 0
        state["entry_px"] = None
        return None, "UNKNOWN", "invalid-input"
    # Kill switch: TRIPPED blocks everything; breach trips it
    if ks.state != "ARMED":
        return None, "OFF", "kill-" + ks.state.lower()
    if bar["daily_pnl_pct"] <= -cfg.daily_loss_stop_pct:
        ks.trip(bar["event_ts"], "daily-loss-stop")
        state["position"] = 0
        state["entry_px"] = None
        return None, "OFF", "kill-trip"
    z = bar["signal_z"]
    pos = state.get("position", 0)
    if pos != 0:
        # Exits are never cost-gated: mean-reversion band, jump arrival,
        # or adverse stop.
        reason = None
        if abs(z) <= cfg.z_exit:
            reason = "exit"
        elif bar.get("is_jump", 0):
            reason = "jump-exit"
        elif stopped(state, bar, cfg):
            reason = "stop-exit"
        if reason:
            qty = size_vol(cfg.risk_R_usd, bar["stop_bps"], bar["close"],
                           bar["adv_shares"], bar["adv_pct"], bar["notional"],
                           cfg.venue, bar["urgency"], bar["edge_bps"], cfg,
                           apply_gate=False)
            exit_side = "SELL" if pos > 0 else "BUY"
            ticket = OrderTicket(
                symbol=bar["symbol"], side=exit_side, qty=qty,
                limit=(round(bar["close"], 2) if cfg.side_exec == "maker" else None),
                tif="DAY", ticket_id="%s-%04dx" % (cfg.sid, int(bar["bar"])),
                parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
                intent_ts=bar["event_ts"], state="NEW")
            state["position"] = 0
            state["entry_px"] = None
            state["cooldown_until"] = int(bar["bar"]) + cfg.cooldown_bars
            return ticket, "OK", reason
        return None, "OK", "hold"
    # Flat: entry path.
    if bar.get("is_jump", 0):
        return None, "OK", "jump-stand-down"   # pure-jump spike: stand down
    if not bar.get("proxy_ok", 1):
        return None, "OK", "proxy-stand-down"  # proxy basis breach: stand down
    if int(bar["bar"]) < state.get("cooldown_until", -1):
        return None, "OK", "cooldown"          # C10 post-exit cooldown
    if abs(z) >= cfg.z_entry:
        qty = size_vol(cfg.risk_R_usd, bar["stop_bps"], bar["close"],
                       bar["adv_shares"], bar["adv_pct"], bar["notional"],
                       cfg.venue, bar["urgency"], bar["edge_bps"], cfg,
                       apply_gate=True)
        # Normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
        cost = expected_cost_bps(bar["notional"], bar["adv_pct"], cfg.venue,
                                 cfg.side_exec, bar["urgency"], cfg)
        gate = cost <= cfg.cost_gate_k * bar["edge_bps"]
        if qty > 0 and gate:
            ticket = OrderTicket(
                symbol=bar["symbol"], side=cfg.default_side, qty=qty,
                limit=(round(bar["close"], 2) if cfg.side_exec == "maker" else None),
                tif="DAY", ticket_id="%s-%04d" % (cfg.sid, int(bar["bar"])),
                parent_signal="%s@%d" % (cfg.primary_signal, bar["event_ts"]),
                intent_ts=bar["event_ts"], state="NEW")
            state["position"] = 1 if cfg.default_side == "BUY" else -1
            state["entry_px"] = bar["close"]
            return ticket, "OK", "entry"
        return None, "OK", "gate-block"
    return None, "OK", "flat"


CFG = Config(
    sid="T042", primary_signal="S064",
    bv_window_min=5, jump_pvalue=0.01,
    z_entry=2.5, z_exit=1.0, cost_gate_k=0.5,
    risk_R_usd=250, stop_bps=25, adv_cap_pct=1.0,
    spread_full_bps=6.0, taker_fee_bps=0.5,
    maker_rebate_bps=-0.2, side_exec="taker",
    borrow_bps=0.0, impact_k=25.0,
    daily_loss_stop_pct=1.0, venue="primary",
    default_side="BUY", cooldown_bars=78)


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
            "is_jump": int(r["is_jump"]), "proxy_ok": int(r["proxy_ok"]),
        })
    return rows


def expected():
    return load_csv(EXPECTED)


def fresh_state():
    return {"position": 0, "entry_px": None, "cooldown_until": -1,
            "kill": KillSwitch()}


def mkbar(bar=0, close=100.0, z=0.0, edge=2.0, is_jump=0, proxy_ok=1,
          market_state="CONTINUOUS_TRADING", daily_pnl_pct=0.05):
    """Synthetic single bar for path-specific tests."""
    ts = 1789045200000000000 + bar * 300_000_000_000
    return {"bar": bar, "event_ts": ts, "asof_ts": ts + 25000000,
            "symbol": "XYZ", "close": close, "signal_z": z,
            "edge_bps": edge, "notional": 100000.0, "adv_pct": 0.5,
            "adv_shares": 2000000.0, "stop_bps": 25.0, "urgency": "normal",
            "market_state": market_state, "daily_pnl_pct": daily_pnl_pct,
            "is_jump": is_jump, "proxy_ok": proxy_ok}


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
    assert {"event_ts", "asof_ts", "close", "signal_z", "market_state",
            "is_jump", "proxy_ok"} <= tcols
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
                                              CFG.side_exec, b["urgency"], CFG),
                            rel_tol=TOL), b["bar"]
        if t is not None:
            assert t.qty > 0
            assert t.side in ("BUY", "SELL", "SHORT")
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
    cost = expected_cost_bps(100000.0, 0.5, CFG.venue, CFG.side_exec,
                             "normal", CFG)
    assert math.isclose(cost, 5.267766952966369, rel_tol=TOL)  # pins the stack
    assert cost <= CFG.cost_gate_k * 21.071067811865476  # bar-3 style edge passes
    assert not (cost <= CFG.cost_gate_k * 0.05)          # tiny edge blocked


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


def test_jump_stand_down():
    """Pure-jump spike -> stand down, no intent, state stays OK."""
    st = fresh_state()
    b = mkbar(bar=0, z=3.25, edge=21.0, is_jump=1)
    t, ms, note = process_bar(st, b, CFG)
    assert t is None and ms == "OK" and note == "jump-stand-down"
    # the fixture exercises the same path on tape bar 7
    exp = {int(r["bar"]): r for r in expected()}
    assert exp[7]["note"] == "jump-stand-down"
    assert exp[7]["module_state"] == "OK"


def test_proxy_stand_down():
    """Proxy basis breach (proxy_ok=0) -> stand down, no intent."""
    st = fresh_state()
    b = mkbar(bar=0, z=3.0, edge=21.0, proxy_ok=0)
    t, ms, note = process_bar(st, b, CFG)
    assert t is None and ms == "OK" and note == "proxy-stand-down"


def test_post_exit_cooldown():
    """C10: no re-entry until cooldown_until elapses after an exit."""
    cfg2 = replace(CFG, cooldown_bars=2)
    st = fresh_state()
    t0, _, n0 = process_bar(st, mkbar(bar=0, z=3.0, edge=21.0), cfg2)
    assert t0 is not None and n0 == "entry"
    t1, ms1, n1 = process_bar(st, mkbar(bar=1, z=0.5, edge=21.0,
                                       close=100.5), cfg2)
    assert t1 is not None and t1.side == "SELL" and n1 == "exit"
    assert ms1 == "OK"
    # bar 2 < cooldown_until (= 1 + 2): suppressed
    t2, ms2, n2 = process_bar(st, mkbar(bar=2, z=3.0, edge=21.0), cfg2)
    assert t2 is None and ms2 == "OK" and n2 == "cooldown"
    # bar 3 >= cooldown_until: re-entry allowed
    t3, _, n3 = process_bar(st, mkbar(bar=3, z=3.0, edge=21.0), cfg2)
    assert t3 is not None and n3 == "entry"


def test_jump_exit_while_long():
    """Jump arrival while long -> flatten immediately (thesis broken)."""
    st = fresh_state()
    t0, _, _ = process_bar(st, mkbar(bar=0, z=3.0, edge=21.0), CFG)
    assert t0 is not None
    t1, ms1, n1 = process_bar(st, mkbar(bar=1, z=2.5, edge=21.0, is_jump=1,
                                       close=100.5), CFG)
    assert t1 is not None and t1.side == "SELL" and n1 == "jump-exit"
    assert ms1 == "OK" and st["position"] == 0


def test_stop_exit():
    """Adverse move >= stop_bps while long -> stop exit (never cost-gated)."""
    st = fresh_state()
    t0, _, _ = process_bar(st, mkbar(bar=0, z=3.0, edge=21.0,
                                     close=100.0), CFG)
    assert t0 is not None
    # (100.0 - 99.70) / 100.0 * 1e4 = 30 bps >= stop_bps 25
    t1, ms1, n1 = process_bar(st, mkbar(bar=1, z=2.0, edge=21.0,
                                       close=99.70), CFG)
    assert t1 is not None and t1.side == "SELL" and n1 == "stop-exit"
    assert ms1 == "OK" and st["position"] == 0


def test_size_vol_cost_gate():
    """size_vol: entry returns 0 when the gate fails; exits bypass the gate."""
    kw = dict(risk_R_usd=250.0, stop_bps=25.0, px=100.44, adv_shares=2000000.0,
              adv_pct=0.5, notional=100000.0, venue="primary",
              urgency="normal", cfg=CFG)
    # bar-3 style edge: gate passes -> 995 shares
    assert size_vol(edge_bps=21.071067811865476, apply_gate=True, **kw) == 995
    # tiny edge: gate fails -> unaffordable entry size is 0
    assert size_vol(edge_bps=0.05, apply_gate=True, **kw) == 0
    # exits never cost-gated: same tiny edge still sizes normally
    assert size_vol(edge_bps=0.05, apply_gate=False, **kw) == 995
