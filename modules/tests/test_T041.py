"""Acceptance tests for T041 - HAR Vol-Timing Overlay.

Template v1.0.0. Loads the fixture tape, runs the module's reference emit()
(normative pseudocode via process_bar), and asserts the TYPE header,
fixture-vs-expected agreement, causality (no-signal-bar fills), the cost-gate
predicate (vacuous for a zero-cost overlay), kill-switch trip/re-arm, the
rebalance threshold, and invalid-input handling (UNKNOWN, never interpolate).

Strategies emit ORDER INTENTS ONLY (Appendix C v1.0.0); the broker layer
creates orders. The overlay scales the base book's target positions; it holds
no positions of its own.

Run: python3 -m pytest modules/tests/test_T041.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "T041_tape.csv"
EXPECTED = FIX / "T041_expected.csv"

TOL = 1e-9  # tolerance on float comparisons


# ------------------------------------------------------- reference contract
@dataclass(frozen=True)
class OrderTicket:
    symbol: str
    side: str            # base book side, scaled - intent, not a wire order
    qty: int             # shares, integer, > 0
    limit: float | None  # None = marketable intent (base book fill model applies)
    tif: str             # DAY | IOC | FOK | GTC | OPG | CLS
    ticket_id: str       # module-generated idempotency key
    parent_signal: str   # "S066@<asof_ts_ns>" - full provenance
    intent_ts: int       # int64 ns UTC - when the intent was emitted
    state: str           # NEW | WORKING | ... (intent-side mirror only)


@dataclass(frozen=True)
class Config:
    """Mirrors the §T0.2 Config table of modules/strategies/T041.md."""
    sid: str = "T041"
    primary_signal: str = "S066"
    target_vol: float = 0.15        # annualized vol target [default]
    scale_cap: float = 2.0          # [default]
    scale_floor: float = 0.25       # [default]
    rebalance_tol: float = 0.01     # abs scale change that emits an intent [default]
    rv_lags: tuple = (1, 5, 22)     # HAR(d,w,m) lookbacks [documented]
    cost_gate_k: float = 0.5        # [default]
    daily_loss_stop_pct: float = 1.0  # [default]


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


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """COST-block callable. The overlay itself costs nothing; it only scales
    the base book's intents, whose costs live in the base book's module."""
    spread = 0.0
    fee = 0.0
    borrow = 0.0          # direction-agnostic; borrow sits in the base book
    impact = 0.0          # no independent impact
    return spread + fee + borrow + impact


def clipped_scale(har, cfg):
    """Vol-target scaling rule: scale = target_vol / har, clipped."""
    raw = cfg.target_vol / max(har, 1e-9)
    scale = min(max(raw, cfg.scale_floor), cfg.scale_cap)
    return raw, scale


def process_bar(state, bar, cfg):
    """One bar through the overlay. Returns (ticket|None, module_state, note,
    scale). Mirrors the §T3 normative pseudocode: validate (F1/F2) -> kill
    switch -> scale -> rebalance threshold -> normative cost-gate predicate.
    Earliest fill for a bar-t intent is bar t+1's open (t -> t+1)."""
    ks = state["kill"]
    har = bar["har"]
    # F1/F2: invalid input -> UNKNOWN, never interpolate; scale frozen.
    if (bar["close"] <= 0 or bar["market_state"] != "CONTINUOUS_TRADING"
            or bar["asof_ts"] < bar["event_ts"]
            or not (har is not None and math.isfinite(har) and har > 0)):
        return None, "UNKNOWN", "invalid-input", state["scale"]
    # Kill switch: TRIPPED blocks everything; breach trips it.
    if ks.state != "ARMED":
        return None, "OFF", "kill-" + ks.state.lower(), state["scale"]
    if bar["daily_pnl_pct"] <= -cfg.daily_loss_stop_pct:
        ks.trip(bar["event_ts"], "daily-loss-stop")
        return None, "OFF", "kill-trip", state["scale"]
    # Vol-target scale from the S066 HAR forecast.
    raw, scale_new = clipped_scale(har, cfg)
    # Normative cost-gate predicate (vacuous: zero-cost overlay).
    cost = expected_cost_bps(bar["notional"], bar["adv_pct"], "primary",
                             "mixed", bar["urgency"])
    gate = cost <= cfg.cost_gate_k * bar["edge_bps"]
    prev = state["scale"]
    delta = abs(scale_new - prev)
    state["scale"] = scale_new  # overlay always tracks the target scale
    if delta > cfg.rebalance_tol and gate:
        qty = int(math.floor(bar["base_qty"] * scale_new + 0.5))
        note = "scale-up" if scale_new > prev else "scale-down"
        if raw >= cfg.scale_cap:
            note += "-cap"
        elif raw <= cfg.scale_floor:
            note += "-floor"
        ticket = OrderTicket(
            symbol=bar["symbol"], side=bar["base_side"], qty=qty,
            limit=None, tif="DAY", ticket_id="%s-%04d" % (cfg.sid, int(bar["bar"])),
            parent_signal="%s@%d" % (cfg.primary_signal, bar["asof_ts"]),
            intent_ts=bar["event_ts"], state="NEW")
        return ticket, "OK", note, scale_new
    note = "hold" + ("-cap" if raw >= cfg.scale_cap else
                     "-floor" if raw <= cfg.scale_floor else "")
    return None, "OK", note, scale_new


CFG = Config()


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def tape():
    rows = []
    for r in load_csv(TAPE):
        har = r["har"].strip()
        rows.append({
            "bar": int(r["bar"]), "event_ts": int(r["event_ts"]),
            "asof_ts": int(r["asof_ts"]), "symbol": r["symbol"],
            "close": float(r["close"]), "har": float(har) if har else None,
            "base_qty": int(r["base_qty"]), "base_side": r["base_side"],
            "edge_bps": float(r["edge_bps"]), "notional": float(r["notional"]),
            "adv_pct": float(r["adv_pct"]), "urgency": r["urgency"],
            "market_state": r["market_state"],
            "daily_pnl_pct": float(r["daily_pnl_pct"]),
        })
    return rows


def expected():
    return load_csv(EXPECTED)


def fresh_state():
    return {"scale": 1.0, "kill": KillSwitch()}


def run_tape():
    st = fresh_state()
    out = []
    for b in tape():
        t, ms, note, scale = process_bar(st, b, CFG)
        out.append((b, t, ms, note, scale))
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
    assert {"event_ts", "asof_ts", "close", "har", "base_qty",
            "market_state"} <= tcols
    assert {"intent_ts", "action", "qty", "cost_call_bps", "cost_call_usd",
            "gate_pass", "module_state", "scale"} <= ecols
    assert len(load_csv(TAPE)) == len(load_csv(EXPECTED)) == 12


def test_fixture_recomputes_to_expected():
    """Reference process_bar reproduces the expected CSV row by row."""
    exp = {int(r["bar"]): r for r in expected()}
    for b, t, ms, note, scale in run_tape():
        w = exp[b["bar"]]
        want_action = t.side if t else "HOLD"
        assert w["action"] == want_action, b["bar"]
        assert int(w["qty"]) == (t.qty if t else 0), b["bar"]
        assert w["module_state"] == ms, b["bar"]
        assert w["note"] == note, b["bar"]
        assert math.isclose(float(w["scale"]), scale, abs_tol=1e-6), b["bar"]  # 6-dp CSV
        want_gate = expected_cost_bps(b["notional"], b["adv_pct"], "primary",
                                      "mixed", b["urgency"]) <= CFG.cost_gate_k * b["edge_bps"]
        assert w["gate_pass"] == str(want_gate), b["bar"]
        assert math.isclose(float(w["cost_call_bps"]),
                            expected_cost_bps(b["notional"], b["adv_pct"], "primary",
                                              "mixed", b["urgency"]),
                            rel_tol=TOL), b["bar"]
        assert math.isclose(float(w["cost_call_usd"]),
                            float(w["cost_call_bps"]) / 1e4 * b["notional"],
                            rel_tol=TOL), b["bar"]
        if t is not None:
            assert t.qty > 0
            assert t.side == b["base_side"]  # overlay never flips the base side
            assert t.intent_ts == b["event_ts"]
            assert t.ticket_id.startswith(CFG.sid)
            assert t.parent_signal == "%s@%d" % (CFG.primary_signal, b["asof_ts"])


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


def test_cost_gate_predicate_vacuous():
    """Normative predicate: expected_cost_bps(...) <= k * edge_bps.

    The overlay's own cost is 0.0 bps, so the predicate holds for every bar;
    the gate can only bind through the base book's own cost function."""
    for b in tape():
        cost_bps = expected_cost_bps(b["notional"], b["adv_pct"], "primary",
                                     "mixed", b["urgency"])
        assert cost_bps == 0.0
        assert cost_bps <= CFG.cost_gate_k * b["edge_bps"]


def test_rebalance_threshold():
    """Sub-threshold scale moves update state silently; no intent emitted."""
    st = fresh_state()
    bars = tape()
    for b in bars[:6]:
        process_bar(st, b, CFG)
    # bar 6: |0.2679 - 0.2727| < 0.01 -> HOLD, but scale tracks the target
    t6, ms6, note6, s6 = process_bar(st, bars[6], CFG)
    assert t6 is None and ms6 == "OK" and note6 == "hold"
    assert math.isclose(s6, CFG.target_vol / bars[6]["har"], rel_tol=TOL)
    # bar 7: cap hit -> intent carries the -cap note
    t7, ms7, note7, s7 = process_bar(st, bars[7], CFG)
    assert t7 is not None and t7.qty == 2000 and note7 == "scale-up-cap"
    assert s7 == CFG.scale_cap


def test_kill_switch_trip_and_rearm():
    """ARMED -> TRIPPED blocks intents; checklist re-arm restores ARMED."""
    st = fresh_state()
    bars = tape()
    for b in bars[:9]:
        t, ms, note, _ = process_bar(st, b, CFG)
    assert st["kill"].state == "ARMED", "kill must not trip before bar 9"
    b9 = bars[9]
    t9, ms9, note9, _ = process_bar(st, b9, CFG)
    assert t9 is None and ms9 == "OFF" and note9 == "kill-trip"
    assert st["kill"].state == "TRIPPED"
    # still tripped on the next bar: no intents while TRIPPED
    t10, ms10, note10, _ = process_bar(st, bars[10], CFG)
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
    """F1/F2: halted, invalid-price, or bad-HAR bars -> UNKNOWN, never interpolate."""
    st = fresh_state()
    bars = tape()
    t8, ms8, note8, _ = process_bar(st, bars[8], CFG)  # HALTED bar
    assert t8 is None and ms8 == "UNKNOWN" and note8 == "invalid-input"
    bad = dict(bars[3])
    bad["close"] = -1.0  # invalid price
    t, ms, _, _ = process_bar(fresh_state(), bad, CFG)
    assert t is None and ms == "UNKNOWN"
    bad_har = dict(bars[3])
    for bad_val in (0.0, -0.2, float("nan")):  # non-positive / NaN HAR forecast
        bad_har["har"] = bad_val
        t, ms, _, _ = process_bar(fresh_state(), bad_har, CFG)
        assert t is None and ms == "UNKNOWN", bad_val
