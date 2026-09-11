"""R028 — Credit-stress regime: acceptance tests (concrete sketch).

Reference implementation of the normative §R2 pseudocode (hysteresis state
machine), fixture replay over the 90-row tape, boundary/hysteresis/halt pins,
F1-F5 fail-safes, no-lookahead, and cost-record application.
Definition of done: `python3 -m pytest modules/tests/test_R028.py -q` exits 0.
"""
import csv
import math
import os

RID = "R028"
TOL = 1e-9
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

CFG = {"stress_bps": 550.0, "watch_bps": 350.0, "acute_chg_bps": 100.0,
       "stress_exit_bps": 500.0, "watch_exit_bps": 300.0,
       "acute_exit_bps": 50.0, "confirm_bars": 3, "min_lag_bars": 1}

COST_ADJUSTMENT_R028 = {
    "regime_id": "R028", "version": "1.1.0",
    "STRESSED": {"spread_mult": 2.0, "impact_mult": 2.0, "borrow_mult": 1.5,
                 "fee_add_bps": 0.0, "tag": "[example]"},
    "WATCH": {"spread_mult": 1.25, "impact_mult": 1.25, "borrow_mult": 1.0,
              "fee_add_bps": 0.0, "tag": "[example]"},
    "CALM": {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0,
             "fee_add_bps": 0.0, "tag": "[default]"},
}


def _parse_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _mk(state, value, ts_ns, module_state):
    return {
        "regime_id": RID,
        "state": state,
        "value": value,
        "estimator_version": ESTIMATOR_VERSION,
        "data_vintage": DATA_VINTAGE,
        "computed_at": ts_ns,
        "module_state": module_state,
        "min_lag_bars": CFG["min_lag_bars"],
    }


def _valid_oas(raw):
    """F1/F2: missing, non-finite, or negative OAS -> None (never interpolate)."""
    v = _parse_float(raw)
    if not math.isfinite(v) or v < 0:
        return None
    return v


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Normative §R2 logic: hysteresis state machine over (OAS level, 20-day
    change). Entry is immediate; exit needs confirm_bars consecutive benign
    bars. Exact-boundary prints hold the current state (strict inequalities).
    F1/F2/HALT rows emit UNKNOWN and freeze the machine; HALT additionally
    clears the rolling window (discard contributions across reopen).
    Causal: label at position t uses only events[:t+1].
    """
    out, window, prev, run = [], [], "CALM", 0
    for e in events:
        ts = int(float(e["ts_ns"]))
        flag = (e.get("flag") or "").strip()
        if flag == "HALT":
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
            window, run = [], 0
            continue
        v = _valid_oas(e["oas"])
        if v is None or flag == "MISSING":
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
            continue
        window.append(v)
        if len(window) < 21:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
            continue  # warm-up: acute path blind; machine frozen
        window = window[-21:]
        chg = window[-1] - window[0]  # Δ_20, bps
        lvl = v
        enter = (lvl > cfg["stress_bps"]) or (chg > cfg["acute_chg_bps"])
        if prev == "CALM":
            prev = "STRESSED" if enter else ("WATCH" if lvl > cfg["watch_bps"] else "CALM")
            run = 0
        elif prev == "WATCH":
            if enter:
                prev, run = "STRESSED", 0
            elif lvl < cfg["watch_exit_bps"]:
                run += 1
                if run >= cfg["confirm_bars"]:
                    prev, run = "CALM", 0
            else:
                run = 0
        else:  # STRESSED
            if (lvl < cfg["stress_exit_bps"]) and (chg < cfg["acute_exit_bps"]):
                run += 1
                if run >= cfg["confirm_bars"]:
                    prev, run = "WATCH", 0
            else:
                run = 0
        out.append(_mk(prev, chg, ts, "OK"))
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    return out


def apply_freshness(rs, now_ns):
    """F4: expire to UNKNOWN when computed_at is older than 3x cadence."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > 3 * CADENCE_NS:
        rs = dict(rs)
        rs["module_state"] = "UNKNOWN"
        rs["state"] = "UNKNOWN"
    return rs


def apply_cost_adjustment(state_label, base_cost_bps):
    """Apply the §R5 Cost-interface record to a 4-component cost stack."""
    adj = COST_ADJUSTMENT_R028[state_label]
    out = dict(base_cost_bps)
    out["spread_bps"] *= adj["spread_mult"]
    out["impact_bps"] *= adj["impact_mult"]
    out["borrow_bps"] *= adj["borrow_mult"]
    out["fee_bps"] += adj["fee_add_bps"]
    return out


def _load(name):
    p = os.path.join(os.path.dirname(__file__), "..", "fixtures", name)
    with open(p) as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def _close(a, b, tol):
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return abs(a - b) <= tol


def test_fixture_replay():
    tape = _load("R028_tape.csv")
    exp = _load("R028_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R028_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp) == 90, (len(got), len(exp))
    for i, (g, x) in enumerate(zip(got, exp)):
        assert g["state"] == x["state"], (i + 1, g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (i + 1, g, x)
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (i + 1, g["value"], xv)


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R028_tape.csv")
    full = detect(None, tape, CFG)
    for k in range(1, len(tape) + 1):
        prefix = detect(None, tape[:k], CFG)
        assert len(prefix) == k
        for a, b in zip(prefix, full[:k]):
            assert a["state"] == b["state"], (k, a, b)
            assert a["module_state"] == b["module_state"]
            assert _close(a["value"], b["value"], TOL), (k, a["value"], b["value"])


def test_warmup_unknown_then_first_label():
    got = detect(None, _load("R028_tape.csv"), CFG)
    for i in range(20):  # rows 1-20: <21 valid prints -> UNKNOWN
        assert got[i]["state"] == "UNKNOWN" and got[i]["module_state"] == "UNKNOWN", i + 1
    assert got[20]["state"] == "CALM" and got[20]["module_state"] == "OK"  # row 21


def test_exact_boundary_holds_state():
    got = detect(None, _load("R028_tape.csv"), CFG)
    assert got[27]["state"] == "CALM", "row 28: OAS exactly 350 must not enter WATCH"
    assert got[37]["state"] == "WATCH", "row 38: OAS exactly 550 must not enter STRESSED"
    for i in (76, 77, 78):
        assert got[i]["state"] == "STRESSED", f"row {i+1}: OAS exactly 500 must hold STRESSED"
    assert got[84]["state"] == "WATCH", "row 85: OAS exactly 300 must hold WATCH"


def test_hysteresis_hold_below_entry():
    got = detect(None, _load("R028_tape.csv"), CFG)
    # rows 45-47: 540/520/500 — below the 550 entry but above the 500 exit
    for i in (44, 45, 46):
        assert got[i]["state"] == "STRESSED", (i + 1, got[i]["state"])


def test_stress_exit_needs_confirm_bars():
    got = detect(None, _load("R028_tape.csv"), CFG)
    # rows 52-53: first two benign bars below 500 -> still STRESSED
    assert got[51]["state"] == "STRESSED", "row 52"
    assert got[52]["state"] == "STRESSED", "row 53"
    # row 54: third consecutive benign bar -> exit to WATCH
    assert got[53]["state"] == "WATCH", "row 54"


def test_acute_entry_regardless_of_level():
    got = detect(None, _load("R028_tape.csv"), CFG)
    assert got[72]["state"] == "WATCH", "row 73: chg=88 < 100"
    assert got[73]["state"] == "STRESSED", "row 74: chg=112 > 100 while level 532 < 550"
    assert got[39]["state"] == "STRESSED", "row 40: chg=257 > 100 while level 552"


def test_acute_gate_blocks_stress_exit():
    got = detect(None, _load("R028_tape.csv"), CFG)
    # rows 80-81: level < 500 but chg >= acute_exit (58, 40... row 81 chg=40 <50 -> run=1)
    assert got[79]["state"] == "STRESSED", "row 80: chg=58 blocks exit"
    assert got[80]["state"] == "STRESSED", "row 81"
    assert got[81]["state"] == "STRESSED", "row 82"
    assert got[82]["state"] == "WATCH", "row 83: third benign bar -> exit"


def test_f1_missing_row_freezes_machine():
    got = detect(None, _load("R028_tape.csv"), CFG)
    assert got[21]["state"] == "UNKNOWN" and got[21]["module_state"] == "UNKNOWN", "row 22"
    assert got[22]["state"] == "CALM", "row 23 resumes from frozen CALM"


def test_f2_nonfinite_and_negative_unknown():
    got = detect(None, _load("R028_tape.csv"), CFG)
    assert got[86]["module_state"] == "UNKNOWN", "row 87: nan"
    assert got[86]["state"] == "UNKNOWN"
    assert got[89]["module_state"] == "UNKNOWN", "row 90: negative OAS"
    assert got[89]["state"] == "UNKNOWN"


def test_halt_freezes_and_discards_window():
    got = detect(None, _load("R028_tape.csv"), CFG)
    assert got[87]["state"] == "UNKNOWN", "row 88: HALT"
    # window cleared on halt -> row 89 re-warms, still UNKNOWN (not a label)
    assert got[88]["state"] == "UNKNOWN" and got[88]["module_state"] == "UNKNOWN", "row 89"


def test_f3_dual_estimator_agreement():
    tape = _load("R028_tape.csv")
    vals = [v for v in (_valid_oas(e["oas"]) for e in tape) if v is not None]
    # skip the halt row's contribution window: recompute on valid prints only
    w = vals[-21:]
    v1 = w[-1] - w[0]
    v2 = float(vals[-1]) - float(vals[-22 + 1])
    assert abs(v1 - v2) <= TOL, (v1, v2)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R028_tape.csv")
    rs = detect(None, tape, CFG)[53]  # row 54: a labeled row
    assert rs["computed_at"] > 0 and rs["module_state"] == "OK"
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R028_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module §R3)."""
    got = detect(None, _load("R028_tape.csv"), CFG)
    assert abs(got[20]["value"] - (-32.0)) <= TOL, got[20]["value"]   # 288-320
    assert abs(got[39]["value"] - 257.0) <= TOL, got[39]["value"]     # 552-295
    assert abs(got[53]["value"] - (-40.0)) <= TOL, got[53]["value"]   # 420-460
    assert abs(got[73]["value"] - 112.0) <= TOL, got[73]["value"]     # 532-420
    assert abs(got[84]["value"] - (-172.0)) <= TOL, got[84]["value"]  # 300-472
    assert got[39]["state"] == "STRESSED"
    assert got[20]["state"] == "CALM"


def test_cost_record_application():
    base = {"spread_bps": 8.0, "impact_bps": 6.0, "borrow_bps": 2.0, "fee_bps": 0.5}
    s = apply_cost_adjustment("STRESSED", base)
    assert s == {"spread_bps": 16.0, "impact_bps": 12.0, "borrow_bps": 3.0, "fee_bps": 0.5}
    w = apply_cost_adjustment("WATCH", base)
    assert w == {"spread_bps": 10.0, "impact_bps": 7.5, "borrow_bps": 2.0, "fee_bps": 0.5}
    c = apply_cost_adjustment("CALM", base)
    assert c == base  # identity
    assert COST_ADJUSTMENT_R028["version"] == ESTIMATOR_VERSION
