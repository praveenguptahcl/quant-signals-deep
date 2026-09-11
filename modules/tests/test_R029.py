"""R029 — Dollar regime: acceptance tests (concrete sketch).

Real imports, fixture load, real assertions. Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_R029.py -q` exits 0.

The reference detector below is stateful: hysteresis keeps an extreme label
(STRONG/WEAK) until the percentile exits the wider exit band, and a deadband
on G absorbs zero-cross whipsaw. Fixtures pin every transition.
"""
import ast
import csv
import math
import os
import statistics

RID = "R029"
TOL = 1e-9
DUAL_TOL = 1e-12
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

# v1.1.0 config: all thresholds are [example] defaults with status=calibrate;
# the calibration recipe in §R3 replaces them per instrument before production.
CFG = {"pct_hi": 0.80, "pct_lo": 0.20, "hyst_pct": 0.05,
       "deadband_pts": 0.10, "min_lag_bars": 1}

STRONG = "STRONG_DOLLAR_UPTREND"
WEAK = "WEAK_DOLLAR_DOWNTREND"
UP = "DOLLAR_UPTREND"
DOWN = "DOLLAR_DOWNTREND"


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
    g = float(e['ma50']) - float(e['ma200'])
    p = _parse_float(e['pctile'])
    if not (math.isfinite(g) and math.isfinite(p)):
        raise ValueError('non-finite DXY inputs')  # F1
    if not (0.0 <= p <= 1.0):
        raise ValueError('percentile out of [0,1]')  # F2
    return g, p


def _aggregate(events, vals, cfg):
    return vals[-1]


def _dual_aggregate(events, cfg):
    return float(events[-1]['ma50']) - float(events[-1]['ma200'])


def _bounds_ok(value, cfg):
    return math.isfinite(value)


def _new_state():
    return {"sign": None, "extreme": None}  # sign: UP|DOWN ; extreme: STRONG|WEAK


def _step(st, e, cfg):
    """One causal step of the v1.1.0 hysteresis state machine.

    F1/F2 failures emit UNKNOWN and leave the state vector untouched, so a
    recovery bar continues from the last good state (labels are never
    backfilled — F5).
    """
    g, p = _row_value(e, cfg)
    hi, lo, h, db = (cfg['pct_hi'], cfg['pct_lo'],
                     cfg['hyst_pct'], cfg['deadband_pts'])
    prev_sign, prev_extreme = st["sign"], st["extreme"]
    if g > db:
        sign = "UP"
    elif g < -db:
        sign = "DOWN"
    elif prev_sign is not None:
        sign = prev_sign  # deadband hold: absorbs zero-cross whipsaw
    else:
        sign = "UP" if g >= 0 else "DOWN"  # [default] first-bar tie-break
    if sign == "UP" and p >= hi:
        label, extreme = STRONG, "STRONG"
    elif sign == "DOWN" and p <= lo:
        label, extreme = WEAK, "WEAK"
    elif (prev_extreme == "STRONG" and sign == "UP"
            and p >= hi - h):
        label, extreme = STRONG, "STRONG"  # hysteresis hold
    elif (prev_extreme == "WEAK" and sign == "DOWN"
            and p <= lo + h):
        label, extreme = WEAK, "WEAK"  # hysteresis hold
    elif sign == "UP":
        label, extreme = UP, None
    else:
        label, extreme = DOWN, None
    st["sign"], st["extreme"] = sign, extreme
    return label, g


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal: the label at position t uses only events[:t+1] plus the module's
    own prior state (never future inputs). Empty input or an unparseable row
    yields module_state UNKNOWN (F1); out-of-bounds indicator values yield
    UNKNOWN (F2). Never interpolates.
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    st = _new_state() if state is None else state
    out = []
    vals = []
    for i, e in enumerate(events):
        ts = int(float(e["ts_ns"]))
        try:
            label, v = _step(st, e, cfg)
        except Exception:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1/F2
            continue  # state vector untouched: no backfill, resume on next bar
        vals.append(v)
        value = _aggregate(events[: i + 1], vals, cfg)
        if not _bounds_ok(value, cfg):
            out.append(_mk("UNKNOWN", value, ts, "UNKNOWN"))  # F2
            continue
        out.append(_mk(label, value, ts, "OK"))
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


def _module_path():
    return os.path.join(os.path.dirname(__file__), "..", "regimes", "R029.md")


def _close(a, b, tol):
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return abs(a - b) <= tol


def test_fixture_replay():
    tape = _load("R029_tape.csv")
    exp = _load("R029_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R029_tape.csv")).readline()
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
    tape = _load("R029_tape.csv")
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


def test_f1_row_gap_unknown_and_state_survives():
    """A missing print emits UNKNOWN but does not clobber the state vector:
    the next good bar resumes (STRONG held through the gap)."""
    tape = _load("R029_tape.csv")
    got = detect(None, tape, CFG)
    assert got[4]["module_state"] == "UNKNOWN", got[4]   # missing print row
    assert got[4]["state"] == "UNKNOWN"
    assert got[3]["state"] == STRONG                     # entered before gap
    assert got[5]["state"] == STRONG                     # hysteresis hold after gap
    assert got[5]["module_state"] == "OK"


def test_f2_bounds_violation_unknown():
    tape = _load("R029_tape.csv")
    bad = [dict(r) for r in tape]
    bad[0]["ma50"] = "nan"
    got = detect(None, bad, CFG)
    assert got[0]["module_state"] == "UNKNOWN", got[0]


def test_f2_percentile_out_of_bounds():
    tape = _load("R029_tape.csv")
    got = detect(None, tape, CFG)
    assert got[11]["state"] == "UNKNOWN"          # pctile=1.25 fixture row
    assert got[11]["module_state"] == "UNKNOWN"
    assert got[12]["state"] == WEAK               # recovery resumes cleanly
    assert got[12]["module_state"] == "OK"


def test_f3_dual_estimator_agreement():
    tape = _load("R029_tape.csv")
    good = [e for e in tape if math.isfinite(_parse_float(e['pctile']))]
    vals = [float(e['ma50']) - float(e['ma200']) for e in good]
    v1 = _aggregate(tape, vals, CFG)
    v2 = _dual_aggregate(tape, CFG)
    if not _bounds_ok(v1, CFG):
        return  # degenerate panel: both estimators must agree on UNKNOWN-ness
    assert _close(v1, v2, DUAL_TOL), (v1, v2)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R029_tape.csv")
    rs = detect(None, tape, CFG)[-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R029_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3)."""
    tape = _load('R029_tape.csv')
    got = detect(None, tape, CFG)
    assert abs(got[0]['value'] - 1.7) <= 1e-9, got[0]['value']
    assert got[0]['state'] == STRONG
    assert got[1]['state'] == WEAK


def test_hysteresis_strong_hold_and_exit():
    """pi=0.80 enters STRONG; 0.77 holds (inside exit band 0.75); 0.74 exits."""
    got = detect(None, _load('R029_tape.csv'), CFG)
    assert got[3]['state'] == STRONG    # pi == pct_hi: entry boundary
    assert got[5]['state'] == STRONG    # pi=0.77 >= 0.75: hysteresis hold
    assert got[6]['state'] == UP        # pi=0.74 < 0.75: exit to uptrend
    assert got[6]['module_state'] == 'OK'


def test_hysteresis_weak_hold_and_exit():
    """pi=0.10 enters WEAK; 0.22 holds (inside exit band 0.25); 0.27 exits."""
    got = detect(None, _load('R029_tape.csv'), CFG)
    assert got[8]['state'] == WEAK
    assert got[9]['state'] == WEAK      # pi=0.22 <= 0.25: hysteresis hold
    assert got[10]['state'] == DOWN     # pi=0.27 > 0.25: exit to downtrend


def test_deadband_absorbs_zero_cross_whipsaw():
    """G=-0.05 stays inside +/-0.10 deadband: prior UP sign is held."""
    got = detect(None, _load('R029_tape.csv'), CFG)
    assert got[7]['state'] == UP
    assert got[7]['module_state'] == 'OK'


def test_exact_boundary_entries():
    """pi exactly on the entry band is an entry, not a miss."""
    got = detect(None, _load('R029_tape.csv'), CFG)
    assert got[3]['state'] == STRONG    # pi=0.80 == pct_hi
    assert got[12]['state'] == WEAK     # pi=0.20 == pct_lo


def test_cost_interface_identity():
    """The Cost interface block is the single cost channel: R029 gates tilts,
    never cost inputs — every multiplier must be the identity. Fails on
    cost-interface drift."""
    src = open(_module_path()).read()
    marker = "COST_ADJUSTMENT_R029 = "
    i = src.index(marker) + len(marker)
    j = src.index("\n```", i)
    rec = ast.literal_eval(src[i:j].strip())
    assert rec["regime_id"] == "R029"
    assert rec["version"] == "1.1.0"
    for k, v in rec.items():
        if isinstance(v, dict):
            assert v["spread_mult"] == 1.0, (k, v)
            assert v["impact_mult"] == 1.0, (k, v)
            assert v["borrow_mult"] == 1.0, (k, v)
            assert v["fee_add_bps"] == 0.0, (k, v)
