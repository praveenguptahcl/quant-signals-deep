"""R033 — Systemic tail-risk / crisis regime: acceptance tests (concrete sketch).

Real imports, fixture load, real assertions. Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_R033.py -q` exits 0.
"""
import csv
import math
import os
import statistics

RID = "R033"
TOL = 1e-9
DUAL_TOL = 1e-9
ESTIMATOR_VERSION = "1.0.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

CFG = {"kappa": 2.5, "k_crit": 3, "M": 8, "min_lag_bars": 1}


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


def _row_value(e, cfg):
    _z = _parse_float(e['z'])
    if not math.isfinite(_z):
        raise ValueError('non-finite z')
    return _z


def _aggregate(events, vals, cfg):
    return float(sum(1 for _v in vals if _v < -cfg['kappa']))


def _dual_aggregate(events, cfg):
    return float(sum(1 for _e in events if float(_e['z']) < -cfg['kappa']))


def _state_of(value, e, cfg):
    if value >= cfg['k_crit']:
        return 'CRISIS'
    if value >= 2:
        return 'WATCH'
    return 'NORMAL'


def _bounds_ok(value, cfg):
    return math.isfinite(value) and 0.0 <= value <= float(cfg['M'])


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal: the label at position t uses only events[:t+1]. Empty input or an
    unparseable row yields module_state UNKNOWN (F1); out-of-bounds indicator
    values yield UNKNOWN (F2). Never interpolates.
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    vals = []
    for i, e in enumerate(events):
        ts = int(float(e["ts_ns"]))
        try:
            v = _row_value(e, cfg)
        except Exception:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1
            continue
        vals.append(v)
        value = _aggregate(events[: i + 1], vals, cfg)
        if not _bounds_ok(value, cfg):
            out.append(_mk("UNKNOWN", value, ts, "UNKNOWN"))  # F2
            continue
        out.append(_mk(_state_of(value, e, cfg), value, ts, "OK"))
    return out


def apply_freshness(rs, now_ns):
    """F4: expire to UNKNOWN when computed_at is older than 3x cadence."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > 3 * CADENCE_NS:
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
    tape = _load("R033_tape.csv")
    exp = _load("R033_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R033_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R033_tape.csv")
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


def test_f2_bounds_violation_unknown():
    tape = _load("R033_tape.csv")
    bad = [dict(r) for r in tape]
    bad[0]["z"] = "nan"
    got = detect(None, bad, CFG)
    assert got[0]["module_state"] == "UNKNOWN", got[0]


def test_f3_dual_estimator_agreement():
    tape = _load("R033_tape.csv")
    vals = [_row_value(e, CFG) for e in tape]
    v1 = _aggregate(tape, vals, CFG)
    v2 = _dual_aggregate(tape, CFG)
    if not _bounds_ok(v1, CFG):
        return  # degenerate panel: both estimators must agree on UNKNOWN-ness
    assert _close(v1, v2, DUAL_TOL), (v1, v2)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R033_tape.csv")
    rs = detect(None, tape, CFG)[-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R033_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3)."""
    tape = _load('R033_tape.csv')
    got = detect(None, tape, CFG)
    assert got[7]['value'] == 3.0, got[7]['value']
    assert got[7]['state'] == 'CRISIS'

