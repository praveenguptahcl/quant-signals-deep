"""R041 — Overnight gap vs intraday variance decomposition: acceptance tests.

Real imports, fixture load, real assertions. The in-test `detect` mirrors the
normative pseudocode in module §R2: rolling ddof=1 variance decomposition,
hysteresis state machine, edge-case guards (missing/non-finite rows, halts,
unadjusted corporate actions), freeze semantics. Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_R041.py -q` exits 0.
"""
import csv
import math
import os
import re
import statistics

RID = "R041"
TOL = 1e-9
DUAL_TOL = 1e-9
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

CFG = {
    "on_hi": 0.60,        # [example] default; calibrate per §R6.1
    "on_lo": 0.40,        # [example] default; calibrate per §R6.1
    "hyst": 0.05,         # [default] hysteresis half-band
    "window_days": 60,    # [default] rolling estimation window (bars)
    "min_lag_bars": 1,    # [default] Lag contract
    "return_type": "log", # [default]
}

COST_ADJUSTMENT_R041 = {
    "regime_id": RID,
    "version": "1.1.0",
    # which cost component scales, by how much, in which regime state (§R5 Cost interface)
    "ON_DOMINANT": {"spread_mult": 1.0, "impact_mult": 1.2, "borrow_mult": 1.0,
                    "fee_add_bps": 0.0, "tag": "[example]"},
    "ID_DOMINANT": {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0,
                    "fee_add_bps": 0.0, "tag": "[default]"},
    "BALANCED": {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0,
                 "fee_add_bps": 0.0, "tag": "[default]"},
}

_FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures")


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
        "min_lag_bars": CFG.get("min_lag_bars", 1),
    }


def _decompose(pairs):
    """Normative variance decomposition: s = vo / (vo + vi + 2*cov), ddof=1."""
    os_ = [p[0] for p in pairs]
    is_ = [p[1] for p in pairs]
    vo = statistics.variance(os_)
    vi = statistics.variance(is_)
    cv = statistics.covariance(os_, is_)
    vcc = vo + vi + 2 * cv
    if not (math.isfinite(vcc) and vcc > 0):
        return float("nan")  # F2: degenerate variance
    return vo / vcc


def _transition(prev, s, cfg):
    """Normative hysteresis state machine (§R2 pseudocode)."""
    hi, lo, h = cfg["on_hi"], cfg["on_lo"], cfg["hyst"]
    if prev == "ON_DOMINANT":
        if s <= lo:
            return "ID_DOMINANT"          # direct flip across the dead band
        if s < hi - h:
            return "BALANCED"             # exit strictly below hi-h
        return "ON_DOMINANT"              # hold inside the hysteresis band
    if prev == "ID_DOMINANT":
        if s >= hi:
            return "ON_DOMINANT"
        if s > lo + h:
            return "BALANCED"             # exit strictly above lo+h
        return "ID_DOMINANT"
    if s >= hi:                           # cold entry
        return "ON_DOMINANT"
    if s <= lo:
        return "ID_DOMINANT"
    return "BALANCED"


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState]. Normative per §R2.

    Causal: the label at position t uses only events[:t+1]. Missing /
    non-finite rows yield UNKNOWN and are excluded from the rolling window
    (F1/F2, never interpolate); HALTED events freeze (UNKNOWN, excluded);
    SPLIT_UNADJUSTED events are Gate-rejected (UNKNOWN, excluded, no fake gap).
    Hysteresis keeps the label sticky inside the entry/exit dead band.
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    window = []
    prev_label = "UNKNOWN"
    prev_ts = None
    for e in events:
        ts = int(float(e["ts_ns"]))
        etype = (e.get("event_type") or "BAR").strip().upper()
        if prev_ts is not None and ts <= prev_ts:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1
            continue
        prev_ts = ts
        if etype == "HALTED":
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # freeze
            continue
        if etype == "SPLIT_UNADJUSTED":
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # Gate
            continue
        o = _parse_float(e.get("r_on"))
        i = _parse_float(e.get("r_id"))
        if not (math.isfinite(o) and math.isfinite(i)):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1/F2
            continue
        window.append((o, i))
        window = window[-cfg["window_days"]:]  # rolling window
        if len(window) < 2:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
            continue
        value = _decompose(window)
        if not math.isfinite(value):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F2
            continue
        prev_label = _transition(prev_label, value, cfg)
        out.append(_mk(prev_label, value, ts, "OK"))
    return out


def apply_freshness(rs, now_ns):
    """F4: expire to UNKNOWN when computed_at is older than 3x cadence."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > 3 * CADENCE_NS:
        rs = dict(rs)
        rs["module_state"] = "UNKNOWN"
        rs["state"] = "UNKNOWN"
    return rs


def apply_cost_adjustment(regime_state, components):
    """Apply the §R5 cost-interface record to a 4-component cost stack.

    components: {spread_bps, fee_bps, borrow_bps, impact_bps} from the
    strategy's expected_cost_bps inputs. Multipliers scale the named component;
    fee_add_bps adds. Returns a new dict; the regime record is versioned and
    every application is decision-logged (Appendix g v1.0.0).
    """
    rec = COST_ADJUSTMENT_R041[regime_state]
    out = dict(components)
    out["spread_bps"] = components["spread_bps"] * rec["spread_mult"]
    out["impact_bps"] = components["impact_bps"] * rec["impact_mult"]
    out["borrow_bps"] = components["borrow_bps"] * rec["borrow_mult"]
    out["fee_bps"] = components["fee_bps"] + rec["fee_add_bps"]
    return out


def _load(name):
    p = os.path.join(_FIX, name)
    with open(p) as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def _tape_header(name, key):
    with open(os.path.join(_FIX, name)) as f:
        for ln in f:
            if ln.startswith("#") and key in ln:
                return ln
    return ""


def _close(a, b, tol):
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return abs(a - b) <= tol


def _check_replay(tape_name, exp_name, cfg):
    tape = _load(tape_name)
    exp = _load(exp_name)
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(_FIX, tape_name)).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, cfg)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)


def test_fixture_replay_original():
    _check_replay("R041_tape.csv", "R041_expected.csv", CFG)


def test_fixture_replay_hysteresis():
    hdr = _tape_header("R041_hysteresis_tape.csv", "WINDOW_BARS")
    assert "4" in hdr, "hysteresis scenario documents its window accelerator"
    _check_replay("R041_hysteresis_tape.csv", "R041_hysteresis_expected.csv",
                  dict(CFG, window_days=4))


def test_fixture_replay_edge():
    _check_replay("R041_edge_tape.csv", "R041_edge_expected.csv", CFG)


def test_hysteresis_entry_and_sticky_exit():
    """Pins: entry at row5 (s=0.7233 >= 0.60); row7 holds ON despite s=0.5975
    below the entry threshold; row8 exits BALANCED once s < 0.60-0.05."""
    got = detect(None, _load("R041_hysteresis_tape.csv"),
                 dict(CFG, window_days=4))
    labels = [g["state"] for g in got]
    assert labels[4] == "ON_DOMINANT", labels   # entry pin
    assert got[4]["value"] >= CFG["on_hi"]
    assert labels[6] == "ON_DOMINANT", labels   # hysteresis pin: 0.5975 < 0.60
    assert got[6]["value"] < CFG["on_hi"]
    assert got[6]["value"] >= CFG["on_hi"] - CFG["hyst"]
    assert labels[7] == "BALANCED", labels      # exit pin
    # a threshold-only rule (no hysteresis) would flip row7 to BALANCED:
    assert got[6]["value"] < CFG["on_hi"], "scenario must sit inside the dead band"


def test_hysteresis_id_side():
    """Pins: ID entry at row9 (s=0.2749 <= 0.40); row10 holds ID at s=0.4198
    (inside (0.40, 0.45]); row11 exits BALANCED at s=0.4680 > 0.45."""
    got = detect(None, _load("R041_hysteresis_tape.csv"),
                 dict(CFG, window_days=4))
    labels = [g["state"] for g in got]
    assert labels[8] == "ID_DOMINANT", labels
    assert labels[9] == "ID_DOMINANT", labels   # hysteresis pin
    assert CFG["on_lo"] < got[9]["value"] <= CFG["on_lo"] + CFG["hyst"]
    assert labels[10] == "BALANCED", labels


def test_boundary_transitions():
    """Exact threshold boundaries: >= on_hi enters ON, <= on_lo enters ID."""
    assert _transition("BALANCED", 0.60, CFG) == "ON_DOMINANT"
    assert _transition("BALANCED", 0.40, CFG) == "ID_DOMINANT"
    assert _transition("BALANCED", 0.59999, CFG) == "BALANCED"
    assert _transition("BALANCED", 0.40001, CFG) == "BALANCED"
    # hold inside the dead band at the exact float exit edges
    assert _transition("ON_DOMINANT", 0.60 - 0.05, CFG) == "ON_DOMINANT"
    assert _transition("ID_DOMINANT", 0.40 + 0.05, CFG) == "ID_DOMINANT"


def test_direct_flip_across_dead_band():
    """A single bar can jump straight from ON_DOMINANT to ID_DOMINANT."""
    assert _transition("ON_DOMINANT", 0.10, CFG) == "ID_DOMINANT"
    assert _transition("ID_DOMINANT", 0.90, CFG) == "ON_DOMINANT"


def test_edge_missing_nonfinite_halt_split_unknown():
    """Rows 3-6 of the edge tape: missing, non-finite, HALTED, unadjusted
    split all emit UNKNOWN and contribute nothing to the window."""
    got = detect(None, _load("R041_edge_tape.csv"), CFG)
    labels = [g["state"] for g in got]
    states = [g["module_state"] for g in got]
    assert labels[2] == "UNKNOWN" and states[2] == "UNKNOWN"   # missing F1
    assert labels[3] == "UNKNOWN" and states[3] == "UNKNOWN"   # nan F1/F2
    assert labels[4] == "UNKNOWN" and states[4] == "UNKNOWN"   # halt freeze
    assert labels[5] == "UNKNOWN" and states[5] == "UNKNOWN"   # split Gate
    # recovery: row7 recomputed from valid rows {1,2,7} only — the -0.75
    # unadjusted split must NOT leak into the variance
    assert labels[6] == "BALANCED" and states[6] == "OK", got[6]
    assert _close(got[6]["value"], 0.4642857142857143, TOL), got[6]["value"]
    indep = _decompose([(0.004, 0.003), (0.001, 0.002), (0.005, 0.004)])
    assert _close(got[6]["value"], indep, TOL)


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    for name, cfg in [("R041_tape.csv", CFG),
                      ("R041_hysteresis_tape.csv", dict(CFG, window_days=4)),
                      ("R041_edge_tape.csv", CFG)]:
        tape = _load(name)
        full = detect(None, tape, cfg)
        for k in range(1, len(tape) + 1):
            prefix = detect(None, tape[:k], cfg)
            assert len(prefix) == k
            for a, b in zip(prefix, full[:k]):
                assert a["state"] == b["state"], (name, k, a, b)
                assert a["module_state"] == b["module_state"]
                assert _close(a["value"], b["value"], TOL), (name, k)


def test_f1_missing_input_unknown():
    got = detect(None, [], CFG)
    assert len(got) == 1
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"


def test_f2_bounds_violation_unknown():
    tape = _load("R041_tape.csv")
    bad = [dict(r) for r in tape]
    bad[2]["r_on"] = "nan"
    got = detect(None, bad, CFG)
    assert got[2]["module_state"] == "UNKNOWN", got[2]


def test_f3_dual_estimator_agreement():
    # On the clean tapes every row is valid, so prefix alignment holds.
    for name, cfg in [("R041_tape.csv", CFG),
                      ("R041_hysteresis_tape.csv", dict(CFG, window_days=4))]:
        tape = _load(name)
        got = detect(None, tape, cfg)
        w = cfg["window_days"]
        for i in range(len(tape)):
            g = got[i]
            if g["module_state"] != "OK":
                continue
            sub = [(_parse_float(e["r_on"]), _parse_float(e["r_id"]))
                   for e in tape[max(0, i + 1 - w):i + 1]]
            if len(sub) < 2:
                continue
            os_ = [p[0] for p in sub]
            is_ = [p[1] for p in sub]
            vo = statistics.variance(os_)
            vi = statistics.variance(is_)
            cv = statistics.covariance(os_, is_)
            vcc = vo + vi + 2 * cv
            v2 = vo / vcc if vcc > 0 else float("nan")
            assert _close(g["value"], v2, DUAL_TOL), (name, i)
    # On the edge tape, the final valid window must be exactly {1,2,7} —
    # missing/halted/split rows contribute nothing to either estimator.
    tape = _load("R041_edge_tape.csv")
    got = detect(None, tape, CFG)
    sub = [(0.004, 0.003), (0.001, 0.002), (0.005, 0.004)]
    os_ = [p[0] for p in sub]
    is_ = [p[1] for p in sub]
    vo = statistics.variance(os_)
    vi = statistics.variance(is_)
    cv = statistics.covariance(os_, is_)
    v2 = vo / (vo + vi + 2 * cv)
    assert _close(got[-1]["value"], v2, DUAL_TOL)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R041_tape.csv")
    rs = detect(None, tape, CFG)[-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R041_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3)."""
    tape = _load("R041_tape.csv")
    got = detect(None, tape, CFG)
    assert abs(got[4]["value"] - 0.5203) <= 1e-4, got[4]["value"]
    assert got[4]["state"] == "BALANCED"
    assert got[0]["state"] == "UNKNOWN"  # <2 rows


def test_cost_interface_scales_named_components():
    """§R5: ON_DOMINANT scales impact 1.2x; everything else identity; no
    component may scale without an explicit record entry."""
    comps = {"spread_bps": 2.0, "fee_bps": 0.3, "borrow_bps": 1.0,
             "impact_bps": 5.0}  # [example]
    on = apply_cost_adjustment("ON_DOMINANT", comps)
    assert _close(on["impact_bps"], 6.0, TOL), on
    assert _close(on["spread_bps"], 2.0, TOL), on
    assert _close(on["borrow_bps"], 1.0, TOL), on
    assert _close(on["fee_bps"], 0.3, TOL), on
    bal = apply_cost_adjustment("BALANCED", comps)
    for k in comps:
        assert _close(bal[k], comps[k], TOL), (k, bal)
    for state, rec in COST_ADJUSTMENT_R041.items():
        if state in ("regime_id", "version"):
            continue
        assert set(rec) == {"spread_mult", "impact_mult", "borrow_mult",
                            "fee_add_bps", "tag"}, (state, rec)
        assert rec["tag"] in ("[example]", "[default]", "[documented]")
    assert COST_ADJUSTMENT_R041["version"] == ESTIMATOR_VERSION


def test_config_pinned_to_calibrated_defaults():
    """Drift pin: the calibrated defaults in §R0.2 must match the harness."""
    assert CFG["on_hi"] == 0.60
    assert CFG["on_lo"] == 0.40
    assert CFG["hyst"] == 0.05
    assert CFG["window_days"] == 60
    assert CFG["min_lag_bars"] == 1
    assert CFG["return_type"] == "log"


def test_module_version_pinned():
    """§0 front-matter version must be 1.1.0 (deep-review edition)."""
    p = os.path.join(os.path.dirname(__file__), "..", "regimes", "R041.md")
    text = open(p).read()
    m = re.search(r"^version:\s*(\S+)\s*$", text, re.M)
    assert m and m.group(1) == "1.1.0", m.group(1) if m else None
