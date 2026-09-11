"""Acceptance tests for S098 — Short interest / borrow fee / days-to-cover.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode, and asserts causality, the cost gate, and
hand-checked arithmetic. The chapter specifies no canonical combined formula;
the crowding score here is the chapter's OWN illustrative §S3 example —
the sum of cross-sectional z-scores of SI/float, days-to-cover, and fee
(desk-specific example, not an institutional standard).

v1.1.0 deep-review additions: threshold-boundary tests (strict > semantics),
invalid-input -> UNKNOWN coverage, gate-veto path semantics
(gate_pass == hard or squeeze, direction always 0), empty-panel UNKNOWN.

Run: python3 -m pytest modules/tests/test_S098.py -q   (from repo root)
"""
import csv
import math
import statistics
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S098_tape.csv"
EXPECTED = FIX / "S098_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["computed_at", "direction", "confidence", "capital", "module_state",
                 "edge_bps", "cost_bps", "crowd_score", "hard_flag", "squeeze_flag",
                 "gate_pass", "fill_event_ts"]

# Chapter S3 parameters [example]
CFG = {"k": 0.5, "hard_fee_bps": 100.0, "sqz_crowd": 0.60, "sqz_dtc": 5.0,
       "sqz_fee_bps": 500.0, "sqz_util": 90.0}


def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def _num(v):
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        pass
    try:
        return float(v)
    except (ValueError, TypeError):
        return v


def tape():
    rows = []
    for r in load_csv(TAPE):
        d = {}
        for k, v in r.items():
            d[k] = _num(v)
        rows.append(d)
    return rows


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    # Shorts must clear borrow fees and recall risk [example]: spread 3.0 + fees 1.0 + impact 3.0
    spread_bps = 3.0
    fee_bps = 1.0
    borrow_bps = 0.0  # [default] baseline; add the name's fee from the fixture when hard
    impact_bps = 3.0
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _bad(x):
    # F1 invalid-input class: missing, NaN, or non-finite -> UNKNOWN, never interpolate
    return x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))


def _clip01(x):
    return max(0.0, min(1.0, x))


def init_state():
    return {"rows": 0, "xstats": None}  # xstats = cross-sectional (mean, sd) per feature


def _xstats(rows):
    # chapter S4 [documented]: cross-sectional z-scores over the panel, sample sd
    good = [r for r in rows
            if not any(_bad(v) for v in (r.get("si_m"), r.get("float_m"), r.get("adv_m"),
                                         r.get("fee_ann"), r.get("util")))
            and r["float_m"] > 0 and r["adv_m"] > 0 and r["si_m"] >= 0]
    si = [r["si_m"] / r["float_m"] * 100.0 for r in good]  # SI/float, %
    dtc = [r["si_m"] / r["adv_m"] for r in good]           # days-to-cover
    fee = [float(r["fee_ann"]) for r in good]              # borrow fee, %/ann
    if len(good) < 2:
        return None
    return {"si": (statistics.mean(si), statistics.stdev(si)),
            "dtc": (statistics.mean(dtc), statistics.stdev(dtc)),
            "fee": (statistics.mean(fee), statistics.stdev(fee))}


def _z(x, ms):
    m, s = ms
    return (x - m) / s if s > 0 else 0.0


def step(state, row, cfg):
    # Tape schema: ticker,si_m,float_m,adv_m,fee_ann,util,dix (no timestamps on the panel)
    idx = state["rows"] + 1
    ts = idx  # event index as the ordered event clock [example]
    si_m = row.get("si_m")
    float_m = row.get("float_m")
    adv_m = row.get("adv_m")
    fee_ann = row.get("fee_ann")
    util = row.get("util")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0,
           "cost_bps": expected_cost_bps(1e4, 0.01, "XNAS", "short", "normal"),
           "crowd_score": float("nan"), "hard_flag": 0, "squeeze_flag": 0,
           "gate_pass": 0, "fill_event_ts": ts + 1}
    # F1: invalid input -> UNKNOWN, never interpolate
    if any(_bad(v) for v in (si_m, float_m, adv_m, fee_ann, util)) \
            or float_m <= 0 or adv_m <= 0 or si_m < 0:
        return out, state
    si_float = si_m / float_m
    fee_bps = fee_ann * 100.0
    dtc = si_m / adv_m
    # chapter S3/S4 [documented] illustrative example: sum of cross-sectional z-scores
    # of SI/float, days-to-cover, and fee — desk-specific, NOT an institutional standard
    xs = state.get("xstats")
    if xs is None:
        return out, state  # panel too small for cross-sectional z -> UNKNOWN
    crowd = (_z(si_float * 100.0, xs["si"]) + _z(dtc, xs["dtc"])
             + _z(float(fee_ann), xs["fee"]))
    hard = 1 if fee_bps > cfg["hard_fee_bps"] else 0
    squeeze = 1 if (crowd > cfg["sqz_crowd"] and dtc > cfg["sqz_dtc"]
                   and fee_bps > cfg["sqz_fee_bps"] and util > cfg["sqz_util"]) else 0
    # doctrine: crowded + hard-to-borrow names are NO-SHORT and NO-LONG (exclusion);
    # squeeze is a 3-5 day anti-short window on the *trigger* day
    out.update({"module_state": "OK", "direction": 0, "confidence": 0.0,
                "capital": 0.0, "edge_bps": 0.0, "crowd_score": crowd,
                "hard_flag": hard, "squeeze_flag": squeeze,
                "gate_pass": 1 if (hard or squeeze) else 0})
    state["rows"] += 1
    return out, state


def run(rows):
    st = init_state()
    st["xstats"] = _xstats(rows)  # cross-sectional stats need the whole panel
    out = []
    for r in rows:
        sig, st = step(st, r, CFG)
        out.append(sig)
    return out


def _close(a, b):
    if a is None and b is None:
        return True
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(b))
    return a == b


def test_fixtures_exist_and_typed():
    assert TAPE.exists(), "tape fixture missing"
    assert EXPECTED.exists(), "expected fixture missing"
    with open(TAPE) as f:
        head = [next(f) for _ in range(3)]
    assert any(l.startswith("# TYPE:") for l in head), "tape missing TYPE header"
    with open(EXPECTED) as f:
        head = [next(f) for _ in range(3)]
    assert any(l.startswith("# TYPE:") for l in head), "expected missing TYPE header"
    rows = tape()
    assert len(rows) >= 5, "fixture needs >=5 hand-checkable rows"


def test_expected_matches_reference():
    rows = tape()
    sigs = run(rows)
    exp = load_csv(EXPECTED)
    assert len(exp) == len(sigs), "expected row count != tape row count"
    for i, (s, e) in enumerate(zip(sigs, exp)):
        assert str(e["ticker"]) == str(rows[i]["ticker"]), f"row {i} ticker mismatch"
        for c in EXPECTED_COLS:
            got = s[c]
            want = _num(e[c])
            assert _close(got, want), f"row {i} col {c}: got {got} want {want}"


def test_signal_vector_valid():
    for s in run(tape()):
        assert s["direction"] in (+1, -1, 0), "direction not in {+1,-1,0}"
        assert 0.0 <= s["confidence"] <= 1.0, "confidence out of [0,1]"
        assert 0.0 <= s["capital"] <= 0.5, "capital out of [0,0.5]"
        assert s["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_hand_checks():
    # Chapter S4 table [documented]: illustrative crowding z-sums (sample-sd cross-sectional)
    # MEMEQ +4.72 (squeeze-risk corner); PWRS +1.51 (crowded but exits); KLVR +0.12
    # (illiquidity, not crowding); ZQTA -2.54, NORD -1.90, DLTA -1.91 (control group)
    sigs = run(tape())
    zqta, klvr, nord, memeq, pwrs, dlta = sigs
    assert abs(memeq["crowd_score"] - 4.72) < 0.02
    assert abs(pwrs["crowd_score"] - 1.51) < 0.02
    assert abs(klvr["crowd_score"] - 0.12) < 0.02
    assert abs(zqta["crowd_score"] - (-2.54)) < 0.02
    assert abs(nord["crowd_score"] - (-1.90)) < 0.02
    assert abs(dlta["crowd_score"] - (-1.91)) < 0.02
    # MEMEQ hand-checks [documented]: SI/float = 42/150 = 28.0%; DTC = 42/4.5 = 9.33 days;
    # 30-day borrow drag on a $1M short = 42*30/365 = 3.45%
    assert abs(42.0 / 150.0 - 0.28) < 1e-12
    assert abs(42.0 / 4.5 - 9.33) < 0.01
    assert abs(42.0 * 30.0 / 365.0 - 3.45) < 0.01
    # squeeze-risk corner [example thresholds]: MEMEQ hard + squeeze; PWRS hard, no squeeze
    assert memeq["hard_flag"] == 1 and memeq["squeeze_flag"] == 1
    assert pwrs["hard_flag"] == 1 and pwrs["squeeze_flag"] == 0
    assert zqta["hard_flag"] == 0 and zqta["squeeze_flag"] == 0
    # exclusion doctrine: direction is always 0 (module gates, never initiates)
    assert all(s["direction"] == 0 for s in sigs)
    # KLVR borrow 850 bps > 100 bps hard threshold; ZQTA 40 bps is not hard [example]
    assert klvr["hard_flag"] == 1
    assert zqta["hard_flag"] == 0


def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()):
        fill_event = s["fill_event_ts"]
        signal_event = s["computed_at"]
        if fill_event is not None:
            assert fill_event > signal_event


def test_cost_gate():
    # normative predicate: expected_cost_bps(...) <= k * edge_bps
    k = 0.5  # [default]
    c = expected_cost_bps(1e4, 0.01, "XNAS", "short", "normal")
    assert abs(c - 7.0) < 1e-9, "chapter stack must total 7.0 bps"
    big_edge = c <= k * 100.0
    tiny_edge = c <= k * 0.01
    assert big_edge, "cost gate should pass on a large edge"
    assert not tiny_edge, "cost gate should block on a tiny edge"


def test_invalid_input_unknown():
    st = init_state()
    bad = {"ticker": "BAD", "si_m": -5.0, "float_m": 100.0, "adv_m": 10.0,
           "fee_ann": 1.0, "util": 10.0, "dix": 8.0}
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"


def _panel_state():
    # state with the real tape's cross-sectional stats, for synthetic-row tests
    st = init_state()
    st["xstats"] = _xstats(tape())
    return st


def _row(**kw):
    base = {"ticker": "SYN", "si_m": 42.0, "float_m": 150.0, "adv_m": 4.5,
            "fee_ann": 42.0, "util": 97.0, "dix": 16.0}
    base.update(kw)
    return base


def test_boundary_fee_exactly_at_threshold():
    # fee_bps == hard_fee_bps is NOT hard (strict >); chapter S3 guard semantics
    st = _panel_state()
    sig, _ = step(st, _row(fee_ann=1.0), CFG)  # 1.0 %/ann == 100 bps exactly
    assert sig["module_state"] == "OK"
    assert sig["hard_flag"] == 0, "fee exactly at threshold must not flag hard"
    assert sig["squeeze_flag"] == 0
    assert sig["gate_pass"] == 0
    assert sig["direction"] == 0


def test_boundary_dtc_exactly_at_threshold():
    # dtc == sqz_dtc is NOT a squeeze (strict >); other corner conditions pass
    st = _panel_state()
    sig, _ = step(st, _row(si_m=45.0, adv_m=9.0), CFG)  # 45.0/9.0 == 5.0 days exactly
    assert sig["module_state"] == "OK"
    assert sig["crowd_score"] > CFG["sqz_crowd"], "test must isolate the dtc boundary"
    assert sig["squeeze_flag"] == 0, "dtc exactly at threshold must not squeeze"
    assert sig["hard_flag"] == 1  # fee 4200 bps still hard
    assert sig["gate_pass"] == 1  # hard veto path still gates
    assert sig["direction"] == 0


def test_boundary_crowd_exactly_at_threshold():
    # squeeze requires crowd STRICTLY greater than sqz_crowd
    st = _panel_state()
    row = _row()
    xs = st["xstats"]
    crowd = (_z(row["si_m"] / row["float_m"] * 100.0, xs["si"])
             + _z(row["si_m"] / row["adv_m"], xs["dtc"])
             + _z(row["fee_ann"], xs["fee"]))
    assert crowd > CFG["sqz_crowd"], "fixture corner must clear the crowd threshold"
    cfg_at = dict(CFG, sqz_crowd=crowd)  # threshold exactly at the computed crowd
    sig, _ = step(_panel_state(), row, cfg_at)
    assert sig["squeeze_flag"] == 0, "crowd exactly at threshold must not squeeze"
    sig2, _ = step(_panel_state(), row, CFG)
    assert sig2["squeeze_flag"] == 1, "corner must squeeze under default thresholds"


def test_boundary_util_exactly_at_threshold():
    # util == sqz_util (percent units) is NOT a squeeze (strict >)
    st = _panel_state()
    sig, _ = step(st, _row(util=90.0), CFG)
    assert sig["module_state"] == "OK"
    assert sig["squeeze_flag"] == 0, "util exactly at 90.0% must not squeeze"
    assert sig["hard_flag"] == 1
    assert sig["gate_pass"] == 1


def test_gate_veto_path():
    # gate_pass == hard or squeeze on every tape row; direction is always 0
    # even when the squeeze veto fires (module gates, never initiates).
    sigs = run(tape())
    rows = tape()
    for s in sigs:
        assert s["gate_pass"] == (1 if (s["hard_flag"] or s["squeeze_flag"]) else 0)
        assert s["direction"] == 0
    by_ticker = {r["ticker"]: s for r, s in zip(rows, sigs)}
    assert by_ticker["MEMEQ"]["squeeze_flag"] == 1 and by_ticker["MEMEQ"]["gate_pass"] == 1
    assert by_ticker["KLVR"]["hard_flag"] == 1 and by_ticker["KLVR"]["squeeze_flag"] == 0 \
        and by_ticker["KLVR"]["gate_pass"] == 1  # hard veto path: gated without squeeze
    assert by_ticker["ZQTA"]["gate_pass"] == 0


def test_invalid_inputs_all_map_to_unknown():
    st = _panel_state()
    bad_rows = [
        _row(si_m=float("nan")),      # NaN short interest
        _row(si_m=-5.0),              # negative short interest
        _row(float_m=0.0),            # zero float
        _row(adv_m=0.0),              # zero ADV
        _row(fee_ann=float("inf")),   # non-finite fee
        _row(util=None),              # missing utilization
    ]
    for i, bad in enumerate(bad_rows):
        sig, _ = step(_panel_state(), bad, CFG)
        assert sig["module_state"] == "UNKNOWN", f"bad row {i} must map to UNKNOWN"
        assert math.isnan(sig["crowd_score"]), f"bad row {i} must not produce a score"
        assert sig["hard_flag"] == 0 and sig["squeeze_flag"] == 0, \
            f"bad row {i} must not raise flags"


def test_empty_panel_unknown():
    # fewer than 2 valid names -> no cross-sectional stats -> UNKNOWN, never interpolate
    st = init_state()
    sig, _ = step(st, _row(), CFG)
    assert sig["module_state"] == "UNKNOWN"
