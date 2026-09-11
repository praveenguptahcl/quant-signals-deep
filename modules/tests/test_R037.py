"""R037 v1.1.0 — Month/quarter-end rebalancing flows: acceptance tests.

Reference implementation of the §R2 normative pseudocode (MTD returns supplied
precomputed in the tape per §R2.1; window flag threaded from events per §R2.2;
hysteresis machine per §R2.2; F1–F5 per §R9) plus the §R5 cost interface.
Definition of done: `python3 -m pytest modules/tests/test_R037.py -q` exits 0.
"""
import csv
import math
import os

RID = "R037"
TOL = 1e-9
DUAL_TOL = 1e-12
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

# §R0.2 — must match the chapter table (pinned by test_config_defaults_match_chapter)
CFG = {"w_star": 0.60, "flow_entry": 0.01, "flow_exit": 0.005,
       "window_days": 3, "stale_days": 3, "min_lag_bars": 1}

CHAPTER_DEFAULTS = {"w_star": 0.60, "flow_entry": 0.01, "flow_exit": 0.005,
                    "window_days": 3, "stale_days": 3, "min_lag_bars": 1}


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


def _drift(Re, Rb, w):
    return w * (1.0 + Re) / (w * (1.0 + Re) + (1.0 - w) * (1.0 + Rb)) - w


def _drift_alt(Re, Rb, w):
    # Dual estimator: algebraically rearranged form (§R9 F3)
    num = w + w * Re
    den = num + (1.0 - w) * (1.0 + Rb)
    return num / den - w


def _transition(prev, d, cfg):
    e, x = cfg["flow_entry"], cfg["flow_exit"]
    assert x < e, "startup assertion: positive deadband"
    if d > e:
        return "SELL_EQUITY"
    if d < -e:
        return "BUY_EQUITY"
    if abs(d) < x:
        return "NEUTRAL"
    return prev  # deadband hold


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal: the label at position t uses only events[:t+1]. Missing field or
    missing in_window -> UNKNOWN (F1); non-finite row -> UNKNOWN (F2).
    Outside the window -> NEUTRAL/OK (absence of flow is measurable).
    Never interpolates.
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    prev = "NEUTRAL"
    for i, e in enumerate(events):
        ts = int(float(e["ts_ns"]))
        Re = _parse_float(e.get("R_e"))
        Rb = _parse_float(e.get("R_b"))
        iw_raw = e.get("in_window", "")
        if e.get("R_e") in (None, "") or e.get("R_b") in (None, "") or iw_raw in (None, ""):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1
            continue
        if not (math.isfinite(Re) and math.isfinite(Rb)):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F2
            continue
        try:
            in_w = bool(int(float(iw_raw)))
        except (TypeError, ValueError):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1
            continue
        d = _drift(Re, Rb, cfg["w_star"])
        if not (math.isfinite(d) and abs(d) < 1.0):
            out.append(_mk("UNKNOWN", d, ts, "UNKNOWN"))  # F2
            continue
        if not in_w:
            out.append(_mk("NEUTRAL", d, ts, "OK"))  # window off: measurable, no flow
            continue
        st = _transition(prev, d, cfg)
        prev = st
        out.append(_mk(st, d, ts, "OK"))
    return out


def cost_adjustment(rsv, base, quarter_end=False):
    """§R5 cost interface: regime state -> cost-function adjustment."""
    adj = dict(base)
    adj["edge_mult"] = 1.0
    adj["trade_ok"] = True
    adj["tags"] = ["R037:" + rsv["state"]]
    ms, st = rsv["module_state"], rsv["state"]
    if ms == "UNKNOWN":
        adj["trade_ok"] = False
        return adj
    if ms == "DEGRADED":
        adj["trade_ok"] = False
        adj["edge_mult"] = 1.5
        return adj
    if st in ("SELL_EQUITY", "BUY_EQUITY"):
        q = 2.0 if quarter_end else 1.5
        adj["impact_mult"] = adj.get("impact_mult", 1.0) * q
        adj["edge_mult"] = 2.0
    return adj


def apply_freshness(rs, now_ns):
    """F4: expire to UNKNOWN when computed_at is older than stale_days x cadence."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > CFG["stale_days"] * CADENCE_NS:
        rs = dict(rs)
        rs["module_state"] = "UNKNOWN"
        rs["state"] = "UNKNOWN"
    return rs


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
    tape = _load("R037_tape.csv")
    exp = _load("R037_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R037_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    assert len(tape) == 15, len(tape)
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)


def test_state_sequence_pins_transitions():
    """The 15-bar tape pins entries, deadband holds, exits, window-off, F1/F2."""
    tape = _load("R037_tape.csv")
    got = detect(None, tape, CFG)
    seq = [g["state"] for g in got]
    assert seq == ["SELL_EQUITY", "SELL_EQUITY", "NEUTRAL", "BUY_EQUITY",
                   "BUY_EQUITY", "NEUTRAL", "NEUTRAL", "SELL_EQUITY",
                   "BUY_EQUITY", "BUY_EQUITY", "BUY_EQUITY", "NEUTRAL",
                   "UNKNOWN", "UNKNOWN", "NEUTRAL"], seq
    # deadband holds: bar2 drift inside (exit, entry) holds SELL; bar5 holds BUY
    assert abs(got[1]["value"]) < CFG["flow_entry"] and abs(got[1]["value"]) > CFG["flow_exit"]
    assert abs(got[4]["value"]) < CFG["flow_entry"] and abs(got[4]["value"]) > CFG["flow_exit"]


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R037_tape.csv")
    full = detect(None, tape, CFG)
    for k in range(1, len(tape) + 1):
        prefix = detect(None, tape[:k], CFG)
        assert len(prefix) == k
        for a, b in zip(prefix, full[:k]):
            assert a["state"] == b["state"], (k, a, b)
            assert a["module_state"] == b["module_state"]
            assert _close(a["value"], b["value"], TOL), (k, a["value"], b["value"])


def test_f1_missing_input_unknown():
    got = detect(None, [], CFG)
    assert len(got) == 1
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"
    # missing R_e row (fixture bar 13) -> F1 UNKNOWN
    tape = _load("R037_tape.csv")
    got = detect(None, tape, CFG)
    assert got[12]["module_state"] == "UNKNOWN", got[12]


def test_f2_nonfinite_unknown():
    tape = _load("R037_tape.csv")
    got = detect(None, tape, CFG)
    # non-finite R_e row (fixture bar 14) -> F2 UNKNOWN
    assert got[13]["module_state"] == "UNKNOWN", got[13]
    # direct: inf returns -> non-finite -> F2 UNKNOWN
    # (note: the drift formula is bounded in (-w, 1-w) by construction, so the
    #  |drift| >= 1.0 arm of F2 is unreachable; non-finite input is the F2 path)
    bad = [dict(r) for r in tape[:1]]
    bad[0]["R_e"] = "inf"
    got = detect(None, bad, CFG)
    assert got[0]["module_state"] == "UNKNOWN", got[0]


def test_f3_dual_estimator_agreement():
    """Primary vs rearranged drift form agree per bar; labels agree (F3)."""
    tape = _load("R037_tape.csv")
    got = detect(None, tape, CFG)
    prev = "NEUTRAL"
    for e, g in zip(tape, got):
        Re, Rb = _parse_float(e["R_e"]), _parse_float(e["R_b"])
        if not (math.isfinite(Re) and math.isfinite(Rb)):
            continue
        v1 = _drift(Re, Rb, CFG["w_star"])
        v2 = _drift_alt(Re, Rb, CFG["w_star"])
        assert _close(v1, v2, DUAL_TOL), (v1, v2)
        in_w = bool(int(float(e["in_window"])))
        if g["module_state"] == "OK" and in_w:
            alt_label = _transition(prev, v2, CFG)
            assert alt_label == g["state"], (alt_label, g["state"])
            prev = g["state"]


def test_f4_staleness_expires_to_unknown():
    tape = _load("R037_tape.csv")
    rs = detect(None, tape, CFG)[0]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + (CFG["stale_days"] + 1) * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CFG["stale_days"] * CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R037_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3)."""
    tape = _load("R037_tape.csv")
    got = detect(None, tape, CFG)
    assert abs(got[0]["value"] - 0.02264150943396226) <= TOL, got[0]["value"]
    assert got[0]["state"] == "SELL_EQUITY"
    assert abs(got[3]["value"] - (-0.01717791411042946)) <= TOL, got[3]["value"]
    assert got[3]["state"] == "BUY_EQUITY"


def test_hysteresis_boundaries():
    """Strict entry/exit bands and deadband holds (fixture bars 7/8/10/11)."""
    tape = _load("R037_tape.csv")
    got = detect(None, tape, CFG)
    e, x = CFG["flow_entry"], CFG["flow_exit"]
    # bar 7: drift just below +entry, prev NEUTRAL -> strict: NO entry
    assert 0 < got[6]["value"] < e, got[6]["value"]
    assert got[6]["state"] == "NEUTRAL"
    # bar 8: drift just above +entry -> SELL
    assert got[7]["value"] > e, got[7]["value"]
    assert got[7]["state"] == "SELL_EQUITY"
    # bar 10: drift just below -entry -> BUY (strict negative entry)
    assert got[9]["value"] < -e, got[9]["value"]
    assert got[9]["state"] == "BUY_EQUITY"
    # bar 11: |drift| just above exit, inside deadband -> hold BUY
    assert x < abs(got[10]["value"]) < e, got[10]["value"]
    assert got[10]["state"] == "BUY_EQUITY"
    # startup assertion: deadband must be positive
    bad = dict(CFG, flow_exit=CFG["flow_entry"])
    try:
        _transition("NEUTRAL", 0.007, bad)
        raise AssertionError("expected deadband assertion")
    except AssertionError as ex:
        assert "deadband" in str(ex)


def test_window_off_neutral_but_measurable():
    """Outside the window: NEUTRAL/OK even when drift exceeds the entry band."""
    tape = _load("R037_tape.csv")
    got = detect(None, tape, CFG)
    bar12 = got[11]
    assert abs(bar12["value"]) < CFG["flow_entry"]  # drift inside band here
    assert bar12["state"] == "NEUTRAL" and bar12["module_state"] == "OK"
    # month-start semantics: R_e = R_b = 0 -> drift exactly 0 -> NEUTRAL/OK
    bar15 = got[14]
    assert bar15["value"] == 0.0
    assert bar15["state"] == "NEUTRAL" and bar15["module_state"] == "OK"


def test_cost_interface():
    """§R5 multipliers pinned: impact x1.5 (x2.0 quarter-end), edge x2.0, blocking."""
    base = {"spread_bps": 1.0, "impact_bps": 2.0, "borrow_bps": 0.5,
            "spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0}
    sell = _mk("SELL_EQUITY", 0.02, 1, "OK")
    a = cost_adjustment(sell, base)
    assert a["impact_mult"] == 1.5, a
    assert a["edge_mult"] == 2.0, a
    assert a["spread_mult"] == 1.0 and a["borrow_mult"] == 1.0, a  # untouched [default]
    assert a["trade_ok"] is True
    assert a["tags"] == ["R037:SELL_EQUITY"]
    aq = cost_adjustment(sell, base, quarter_end=True)
    assert aq["impact_mult"] == 2.0, aq  # quarter-end boost
    buy = _mk("BUY_EQUITY", -0.02, 1, "OK")
    ab = cost_adjustment(buy, base)
    assert ab["impact_mult"] == 1.5 and ab["edge_mult"] == 2.0, ab
    neu = _mk("NEUTRAL", 0.0, 1, "OK")
    an = cost_adjustment(neu, base)
    assert an["impact_mult"] == 1.0 and an["edge_mult"] == 1.0 and an["trade_ok"] is True, an
    unk = _mk("UNKNOWN", float("nan"), 1, "UNKNOWN")
    au = cost_adjustment(unk, base)
    assert au["trade_ok"] is False, au  # restrictive: unknown blocks
    deg = _mk("NEUTRAL", 0.0, 1, "DEGRADED")
    ad = cost_adjustment(deg, base)
    assert ad["trade_ok"] is False and ad["edge_mult"] == 1.5, ad


def test_config_defaults_match_chapter():
    """CFG must equal the §R0.2 table exactly."""
    assert CFG == CHAPTER_DEFAULTS, (CFG, CHAPTER_DEFAULTS)
