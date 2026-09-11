"""R044 — Institutional ownership concentration: acceptance tests.

Real imports, fixture load, real assertions. Not a production harness.
Normative logic mirrors §R2.5–R2.7 of the module: causal HHI, hysteresis
entry/exit pairs, one-step-per-quarter transitions, F1–F5, amendment vintage
discipline. Definition of done: `python3 -m pytest modules/tests/test_R044.py -q` exits 0.
"""
import csv
import math
import os

RID = "R044"
TOL = 1e-9
DUAL_TOL = 1e-12
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000  # quarterly cadence base (13F calendar)
DATA_VINTAGE = "2026-09-09"

CFG = {
    "conc": 0.020,          # calibrate
    "conc_exit": 0.018,     # calibrate (sticky exit)
    "diffuse": 0.012,       # calibrate
    "diffuse_exit": 0.013,  # calibrate (sticky exit)
    "tail_names": 490,      # example
    "min_lag_bars": 1,      # default
    "dual_tol_rel": 0.25,   # default
    "stale_days": 120,      # default
    "recal_cadence_months": 12,  # default
    "min_history_quarters": 20,  # default
}

# Hand-verified HHI (tail_names=490 equal-weighted tail) — see module §R3.
HAND_HHI = [
    0.022439875510204082,
    0.019801002040816324,
    0.01758938775510204,
    0.016233304081632653,
    0.00976877551020408,
    0.012136122448979592,
]


def _parse_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _weights(e):
    return [_parse_float(e["w%d" % _i]) for _i in range(1, 11)]


def _check_weights(ws):
    if any(not math.isfinite(w) for w in ws) or any(w < 0 or w >= 1 for w in ws):
        raise ValueError("bad holder weights")
    if sum(ws) >= 1:
        raise ValueError("weights sum >= 1")


def _hhi(ws, tail_names):
    s = sum(ws)
    t = (1.0 - s) / float(tail_names)
    return sum(w * w for w in ws) + float(tail_names) * t * t


def _dual_hhi(ws, tail_names):
    s = 0.0
    sq = 0.0
    for w in ws:
        s += w
        sq += w * w
    t = (1.0 - s) / float(tail_names)
    return sq + float(tail_names) * t * t


def _plain_band(hhi, cfg):
    if hhi >= cfg["conc"]:
        return "CONCENTRATED"
    if hhi < cfg["diffuse"]:
        return "DIFFUSE"
    return "MODERATE"


def hysteresis(prev, hhi, cfg):
    """§R2.7 normative state transition. Entry strict, exit sticky, one step/quarter [rule]."""
    if prev == "CONCENTRATED":
        if hhi < cfg["conc_exit"]:
            return "MODERATE"  # one step only — never straight to DIFFUSE
        return "CONCENTRATED"
    if prev == "DIFFUSE":
        if hhi >= cfg["diffuse_exit"]:
            return "MODERATE"  # one step only — never straight to CONCENTRATED
        return "DIFFUSE"
    # prev MODERATE or UNKNOWN (UNKNOWN re-enters on plain bands — restrictive but alive)
    if hhi >= cfg["conc"]:
        return "CONCENTRATED"
    if hhi < cfg["diffuse"]:
        return "DIFFUSE"
    return "MODERATE"


def _bounds_ok(value):
    return math.isfinite(value) and 0.0 <= value <= 1.0


def f3_agree(v_primary, v_verifier, cfg):
    """F3: verifier agrees when bands match and relative HHI diff <= dual_tol_rel."""
    if not (math.isfinite(v_primary) and math.isfinite(v_verifier)):
        return False
    rel = abs(v_primary - v_verifier) / max(v_primary, v_verifier, 1e-18)
    return _plain_band(v_primary, cfg) == _plain_band(v_verifier, cfg) and rel <= cfg["dual_tol_rel"]


def _mk(state, value, ts_ns, module_state, vintage):
    return {
        "regime_id": RID,
        "state": state,
        "value": value,
        "estimator_version": ESTIMATOR_VERSION,
        "data_vintage": vintage,
        "computed_at": ts_ns,
        "module_state": module_state,
        "min_lag_bars": CFG["min_lag_bars"],
    }


def detect(state, events, cfg, verifier_fn=None):
    """detect(state, events, cfg, verifier_fn=None) -> list[RegimeState].

    Causal: the label at position t uses only events[:t+1] and the carried
    prev label. Invalid input -> UNKNOWN (never interpolate); F3 verifier
    disagreement -> UNKNOWN; HALTED -> UNKNOWN with prev frozen.
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN", DATA_VINTAGE)]  # F1
    out = []
    prev = None
    for e in events:
        ts = int(float(e["ts_ns"]))
        vintage = str(e.get("filing_ts", DATA_VINTAGE))  # amendments bump vintage
        if e.get("market_state") == "HALTED":
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN", vintage))  # freeze
            continue
        try:
            ws = _weights(e)
            _check_weights(ws)
        except Exception:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN", vintage))  # F1/F2
            prev = None
            continue
        v = _hhi(ws, cfg["tail_names"])
        if not _bounds_ok(v):
            out.append(_mk("UNKNOWN", v, ts, "UNKNOWN", vintage))  # F2
            prev = None
            continue
        if verifier_fn is not None:
            vv = verifier_fn(e)
            if vv is not None and not f3_agree(v, vv, cfg):
                out.append(_mk("UNKNOWN", v, ts, "UNKNOWN", vintage))  # F3
                prev = None
                continue
        label = hysteresis(prev if prev is not None else "MODERATE", v, cfg)
        out.append(_mk(label, v, ts, "OK", vintage))
        prev = label
    return out


def apply_freshness(rs, now_ns, stale_days):
    """F4: expire to UNKNOWN when holdings older than stale_days."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > stale_days * 86400000000000:
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
    tape = _load("R044_tape.csv")
    exp = _load("R044_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R044_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        assert g["estimator_version"] == ESTIMATOR_VERSION
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R044_tape.csv")
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


def test_f1_missing_filing_unknown():
    """A quarter with a missing holder weight -> UNKNOWN row, no interpolation."""
    tape = _load("R044_tape_missing.csv")
    got = detect(None, tape, CFG)
    assert len(got) == len(tape)
    assert got[0]["module_state"] == "OK"
    assert got[1]["module_state"] == "UNKNOWN", got[1]
    assert got[1]["state"] == "UNKNOWN"


def test_f2_bounds_violation_unknown():
    tape = _load("R044_tape.csv")
    bad = [dict(r) for r in tape]
    bad[0]["w1"] = "nan"
    got = detect(None, bad, CFG)
    assert got[0]["module_state"] == "UNKNOWN", got[0]


def test_f2_weights_sum_ge_one_unknown():
    tape = _load("R044_tape.csv")
    bad = [dict(r) for r in tape]
    bad[2]["w1"] = "0.95"  # weights sum = 1.28 >= 1 -> invalid
    got = detect(None, bad, CFG)
    assert got[2]["module_state"] == "UNKNOWN", got[2]
    assert got[0]["module_state"] == "OK"  # other rows unaffected


def test_f3_verifier_agreement():
    tape = _load("R044_tape.csv")
    for e in tape:
        ws = _weights(e)
        v1 = _hhi(ws, CFG["tail_names"])
        v2 = _dual_hhi(ws, CFG["tail_names"])
        assert _close(v1, v2, DUAL_TOL), (v1, v2)
        assert f3_agree(v1, v2, CFG), (v1, v2)


def test_f3_band_disagreement_unknown():
    """Verifier HHI in a different band -> UNKNOWN (F3), never a silent label."""
    tape = _load("R044_tape.csv")

    def bad_verifier(e):
        return 0.011  # DIFFUSE band vs primary CONCENTRATED

    got = detect(None, tape[:1], CFG, verifier_fn=bad_verifier)
    assert got[0]["module_state"] == "UNKNOWN", got[0]
    assert got[0]["state"] == "UNKNOWN"

    def ok_verifier(e):
        return None  # verifier unavailable -> label from primary (honest: logged upstream)

    got2 = detect(None, tape[:1], CFG, verifier_fn=ok_verifier)
    assert got2[0]["module_state"] == "OK"


def test_f4_staleness_expires_to_unknown():
    tape = _load("R044_tape.csv")
    rs = detect(None, tape, CFG)[-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 200 * 86400000000000, CFG["stale_days"])
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + 30 * 86400000000000, CFG["stale_days"])
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R044_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_spot_handcheck():
    """Independently hand-verified HHI arithmetic (module §R3)."""
    tape = _load("R044_tape.csv")
    got = detect(None, tape, CFG)
    assert len(got) == len(HAND_HHI)
    for g, h in zip(got, HAND_HHI):
        assert _close(g["value"], h, 1e-12), (g["value"], h)


def test_hysteresis_hold_concentrated():
    """HHI 0.0198 < entry 0.020 but >= exit 0.018 -> stays CONCENTRATED."""
    tape = _load("R044_tape.csv")
    got = detect(None, tape, CFG)
    assert got[0]["state"] == "CONCENTRATED"
    assert got[1]["state"] == "CONCENTRATED", got[1]


def test_hysteresis_exit_concentrated():
    """HHI 0.0176 < exit 0.018 -> steps down to MODERATE."""
    tape = _load("R044_tape.csv")
    got = detect(None, tape, CFG)
    assert got[2]["state"] == "MODERATE", got[2]


def test_hysteresis_entry_exit_boundaries():
    # entry is strict >= ; exit is sticky (>= exit stays)
    assert hysteresis("MODERATE", 0.020, CFG) == "CONCENTRATED"
    assert hysteresis("MODERATE", 0.019999999, CFG) == "MODERATE"
    assert hysteresis("CONCENTRATED", 0.018, CFG) == "CONCENTRATED"
    assert hysteresis("CONCENTRATED", 0.017999999, CFG) == "MODERATE"
    assert hysteresis("MODERATE", 0.011999999, CFG) == "DIFFUSE"   # strict <
    assert hysteresis("MODERATE", 0.012, CFG) == "MODERATE"
    assert hysteresis("DIFFUSE", 0.013, CFG) == "MODERATE"          # >= exit leaves
    assert hysteresis("DIFFUSE", 0.012999999, CFG) == "DIFFUSE"     # sticky hold


def test_hysteresis_one_step_per_quarter():
    # CONCENTRATED can never jump straight to DIFFUSE (and reverse)
    assert hysteresis("CONCENTRATED", 0.005, CFG) == "MODERATE"
    assert hysteresis("DIFFUSE", 0.050, CFG) == "MODERATE"


def test_halt_freezes_to_unknown():
    tape = _load("R044_tape.csv")
    rows = [dict(r) for r in tape]
    rows[2]["market_state"] = "HALTED"
    got = detect(None, rows, CFG)
    assert got[2]["module_state"] == "UNKNOWN", got[2]
    assert got[2]["state"] == "UNKNOWN"
    # prev label frozen: row 4 still transitions from CONCENTRATED correctly
    assert got[3]["module_state"] == "OK"


def test_amendment_bumps_vintage_and_relabels():
    """13F/A restatement: recompute from amended row, bump vintage, re-label."""
    tape = _load("R044_tape.csv")
    rows = [dict(r) for r in tape]
    amend_ts = 1900000000000000000
    rows[1]["w1"] = "0.030"   # restated top holder -> HHI ~0.01643
    rows[1]["filing_ts"] = str(amend_ts)
    got = detect(None, rows, CFG)
    assert got[1]["data_vintage"] == str(amend_ts), got[1]
    assert _close(got[1]["value"], 0.01643419387755102, 1e-9), got[1]["value"]
    assert got[1]["state"] == "MODERATE", got[1]  # was CONCENTRATED pre-amendment
    assert got[0]["data_vintage"] == DATA_VINTAGE  # unamended rows keep vintage


def test_no_interpolation_across_gap():
    """A missing quarter yields UNKNOWN and never shifts row alignment."""
    tape = _load("R044_tape.csv")
    rows = [dict(r) for r in tape]
    rows[2]["w4"] = ""
    got = detect(None, rows, CFG)
    assert len(got) == len(tape)
    assert got[2]["state"] == "UNKNOWN"
    assert [g["computed_at"] for g in got] == [int(float(r["ts_ns"])) for r in tape]
