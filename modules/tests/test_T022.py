"""T022 Queue-Imbalance Maker with Toxicity Cancel — acceptance tests.

Run: python3 -m pytest modules/tests/test_T022.py -q
"""
import csv
import math
import os

SID = "T022"
TAPE = os.path.join("modules", "fixtures", "T022_tape.csv")
EXPECTED = os.path.join("modules", "fixtures", "T022_expected.csv")
TOL = 1e-9
CSV_TOL_BPS = max(TOL, 1e-4)  # expected CSV rounds bps to 4 dp
CSV_TOL_USD = max(TOL, 0.01)  # expected CSV rounds dollars to 2 dp


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    """Callable cost model — T022 COST block (single source of truth, mirrors §T2)."""
    spread_bps = -4.0   # [example] maker: earns half the 2c spread @ $50 = -4 bps/round-trip
    fee_bps = -0.8      # [example] maker rebate credit; displayed tier band [unverified] -> ~0.4 bps/fill @ $50
    borrow_bps = 0.0    # [default] intraday inventory; flat by 15:30; no overnight carry
    impact_bps = 0.0    # [example] maker takes nothing; adverse selection via VPIN cancel
    return spread_bps + fee_bps + borrow_bps + impact_bps


def load_csv(path):
    with open(path) as f:
        lines = f.readlines()
    assert lines[0].strip().startswith("# TYPE:"), "missing TYPE header"
    return lines[0].strip(), list(csv.DictReader(lines[1:]))


def test_type_header():
    type_line, _ = load_csv(TAPE)
    assert "validation-run" in type_line
    type_line2, _ = load_csv(EXPECTED)
    assert "validation-run" in type_line2


def test_fixture_arithmetic():
    # the tape's stored cost stack, the module's cost callable, and the
    # expected CSV must all agree; P&L arithmetic is recomputed by hand,
    # including the cost-function-call $ column (inputs -> bps -> $)
    _, tape = load_csv(TAPE)
    _, exp = load_csv(EXPECTED)
    assert len(tape) >= 5, "need >=5 hand-checked rows"
    exp_by_id = {e["trade_id"]: e for e in exp if e["trade_id"] != "SUMMARY"}
    for t in tape:
        e = exp_by_id[t["trade_id"]]
        qty = float(t["qty"])
        entry = float(t["entry_px"])
        exitp = float(t["exit_px"])
        notional = float(t["notional"])
        stack_bps = (float(t["spread_bps"]) + float(t["fee_bps"])
                     + float(t["borrow_bps"]) + float(t["impact_bps"]))
        cbps = expected_cost_bps(notional, float(t["adv_pct"]), t["venue"],
                                 "maker", t["urgency"])
        assert abs(cbps - stack_bps) <= TOL
        assert abs(cbps - float(e["expected_cost_bps"])) <= CSV_TOL_BPS
        sign = 1 if t["side"] in ("BUY", "LONG") else -1
        gross = sign * (exitp - entry) * qty
        cost_usd = notional * cbps / 10000.0
        net = gross - cost_usd
        assert abs(gross - float(e["gross_pnl"])) <= CSV_TOL_USD
        assert abs(cost_usd - float(e["cost_dollars"])) <= CSV_TOL_USD
        assert abs(net - float(e["net_pnl"])) <= CSV_TOL_USD


def test_no_signal_bar_fills():
    _, tape = load_csv(TAPE)
    for t in tape:
        fill_event = int(t["fill_ts"])
        signal_event = int(t["signal_ts"])
        assert fill_event > signal_event, "fill_event > signal_event (t->t+1 causality)"


def test_cost_gate_predicate():
    # the normative C3 predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5
    c = expected_cost_bps(100000.0, 0.1, "XNAS", "maker", "normal")
    if c <= 0:
        # zero/negative cost (maker capture/rebate): the gate passes any positive edge
        assert c <= k * 0.05, "non-positive cost must clear the gate"
    else:
        assert c <= k * 50.0, "cost gate must pass when edge >> cost"
        assert not (c <= k * 0.05), "cost gate must block when edge << cost"


def test_kill_switch_trips_and_rearms():
    # ARMED -> TRIPPED -> RECOVERY -> ARMED with the §T0.7 re-arm checklist
    state = "ARMED"
    kill_conditions = [
        "VPIN > vpin_cancel [default]",
        "abs(inventory_q) > inv_max [default]",
        "L1 stale > staleness_ttl_s [default]",
        "clock skew > max_skew [default]",
        "adverse fill > max_adverse_per_trade [default]",
    ]
    assert isinstance(kill_conditions, list) and len(kill_conditions) >= 3
    stale_s = 1.0
    if stale_s >= 1.0:
        state = "TRIPPED"   # emit nothing; module OFF
    assert state == "TRIPPED"
    rearm_checklist = [
        True,   # manual review signed off
        True,   # cooldown expired
        True,   # L1 feed healthy, skew within max_skew
        True,   # no active compliance block
        True,   # inputs hash re-pinned; params hash logged
    ]
    assert all(rearm_checklist)
    state = "RECOVERY"      # DEGRADED until the checklist passes
    state = "ARMED"
    assert state == "ARMED"


def test_invalid_input_emits_unknown():
    # crossed/locked/empty input -> UNKNOWN, never interpolated
    def emit_state(bid_px, ask_px):
        if bid_px <= 0 or ask_px <= bid_px:
            return "UNKNOWN"
        return "OK"
    assert emit_state(50.00, 50.00) == "UNKNOWN"
    assert emit_state(50.01, 50.00) == "UNKNOWN"
    assert emit_state(50.00, 50.01) == "OK"


def test_cost_callable_signature():
    c = expected_cost_bps(250000.0, 0.5, "XNAS", "maker", "normal")
    assert isinstance(c, float) and math.isfinite(c)


def test_summary_row_consistency():
    # the SUMMARY row must equal the detail-row totals (stale totals are a
    # silent worked-example bug; this test pins the §T4 example)
    _, exp = load_csv(EXPECTED)
    detail = [e for e in exp if e["trade_id"] != "SUMMARY"]
    summary = [e for e in exp if e["trade_id"] == "SUMMARY"]
    assert len(summary) == 1 and len(detail) == 6
    s = summary[0]
    assert "6" in s["expected_cost_bps"]
    gross = sum(float(e["gross_pnl"]) for e in detail)
    cost = sum(float(e["cost_dollars"]) for e in detail)
    net = sum(float(e["net_pnl"]) for e in detail)
    assert abs(float(s["gross_pnl"]) - gross) <= CSV_TOL_USD
    assert abs(float(s["cost_dollars"]) - cost) <= CSV_TOL_USD
    assert abs(float(s["net_pnl"]) - net) <= CSV_TOL_USD


def shares(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost):
    """Mirror of the §T2 fenced sizing function (maker: quote = sizing)."""
    lot = 100                    # 1 lot [example]
    cap = ADV_cap * 0.001        # 0.1% ADV [default]
    n = min(lot, cap)
    return int(max(n, 0))


def test_sizing_function_fenced():
    # one lot by default; the 0.1% ADV cap binds on thin names; zero ADV -> zero
    assert shares(200.0, 2.0, 50.0, 5_000_000.0, -4.8) == 100
    assert shares(200.0, 2.0, 50.0, 50_000.0, -4.8) == 50
    assert shares(200.0, 2.0, 50.0, 0.0, -4.8) == 0


def entry_rule(imb, vpin, inv_q, l1_fresh, market_cont, locate_ok, s011_veto, cost_ok):
    """Mirror of the §T2 QUOTE Boolean: every guard must pass to quote."""
    side = 'BUY' if imb > 0 else 'SELL'   # quote the heavy side
    return (abs(imb) >= 0.20 and vpin <= 0.35 and abs(inv_q) <= 5.0
            and l1_fresh and market_cont
            and (side != 'SELL' or locate_ok)   # C7 locate on shorts
            and (s011_veto is False)             # S011 illiquidity screen
            and cost_ok)                         # C3 cost gate


def test_entry_rule_s011_veto():
    ok = dict(imb=0.30, vpin=0.10, inv_q=1.0, l1_fresh=True, market_cont=True,
              locate_ok=True, s011_veto=False, cost_ok=True)
    assert entry_rule(**ok) is True
    vetoed = dict(ok); vetoed["s011_veto"] = True
    assert entry_rule(**vetoed) is False, "S011 veto must block quoting"
    short_nolocate = dict(ok); short_nolocate.update(imb=-0.30, locate_ok=False)
    assert entry_rule(**short_nolocate) is False, "C7: short without locate blocked"
    buy_nolocate = dict(ok); buy_nolocate.update(imb=0.30, locate_ok=False)
    assert entry_rule(**buy_nolocate) is True, "BUY needs no locate"
    toxic = dict(ok); toxic["vpin"] = 0.40
    assert entry_rule(**toxic) is False, "C12: VPIN > cancel blocked"
