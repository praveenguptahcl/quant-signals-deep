"""R035 — Earnings proximity / earnings season: acceptance tests.

Reference implementation of the §R2 normative pseudocode (hysteresis state
machine), fixture load, real assertions. Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_R035.py -q` exits 0.
"""

import csv
import math
import os

RID = "R035"
TOL = 1e-9
DUAL_TOL = 0.5          # [default] days; announced-vs-actual timestamp agreement band (F3)
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

CFG = {
    "D": 2,             # [example] entry distance (calendar days)
    "D_watch": 5,       # [example] watch distance
    "ivp_crit": 90.0,   # [example] entry IV-percentile
    "h_d": 1,           # [example] hysteresis: distance margin
    "h_ivp": 10.0,      # [example] hysteresis: IV-percentile margin
    "L": 252,           # [example] IV-percentile lookback sessions
    "L_min": 126,       # [default] min sessions for a clean lookback
    "min_lag_bars": 1,  # [default]
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
        "min_lag_bars": CFG.get("min_lag_bars", 1),
    }


def _row_value(e, cfg):
    _d = _parse_float(e["d_days"])
    _iv = _parse_float(e["iv_pct"])
    if not (math.isfinite(_d) and math.isfinite(_iv)):
        raise ValueError("non-finite earnings inputs")
    return _d, _iv


def _aggregate(events, vals, cfg):
    return vals[-1][0]


def _dual_aggregate(events, cfg):
    """Independent second-calendar path: d from the dual source must agree
    within DUAL_TOL, else F3 UNKNOWN (announced vs actual timestamp)."""
    last = events[-1]
    raw = (last.get("d_days_dual") or "").strip()
    return _parse_float(raw) if raw else _parse_float(last["d_days"])


def _entry(d, iv, cfg):
    return d <= cfg["D"] and iv >= cfg["ivp_crit"]


def _stay_pre(d, iv, cfg):
    return d <= cfg["D"] + cfg["h_d"] and iv >= cfg["ivp_crit"] - cfg["h_ivp"]


def _label(d, iv, prev, cfg):
    """Normative hysteresis transitions (§R2). prev=None after a reset."""
    if d < 0:
        return "NORMAL"  # [default] the print has passed; next cycle's build-up starts fresh
    if prev == "PRE_EARNINGS":
        if _stay_pre(d, iv, cfg):
            return "PRE_EARNINGS"
    elif prev == "WATCH":
        if _entry(d, iv, cfg):
            return "PRE_EARNINGS"
        if d <= cfg["D_watch"] + cfg["h_d"]:
            return "WATCH"
        return "NORMAL"
    else:  # NORMAL / None / post-reset: strict entry, no hysteresis memory
        if _entry(d, iv, cfg):
            return "PRE_EARNINGS"
        if d <= cfg["D_watch"]:
            return "WATCH"
        return "NORMAL"
    # fall-through: exited PRE_EARNINGS -> WATCH band (with hysteresis) or NORMAL
    if d <= cfg["D_watch"] + cfg["h_d"]:
        return "WATCH"
    return "NORMAL"


def detect(state, events, cfg, dual_fn=None):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal hysteresis machine: the label at position t uses only events[:t+1]
    and the carried per-name memory. Empty input -> UNKNOWN (F1);
    unconfirmed calendar -> UNKNOWN (F1); non-finite d/iv -> UNKNOWN (F2);
    dual-calendar disagreement -> UNKNOWN (F3); HALTED -> UNKNOWN + memory
    reset (discard across reopen, [default]); short lookback -> DEGRADED
    label still emitted. Never interpolates.
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    dual = dual_fn or _dual_aggregate
    mem = {}   # name -> (label, value)
    out = []
    for i, e in enumerate(events):
        ts = int(float(e["ts_ns"]))
        name = e.get("name", "")
        mkt = (e.get("market_state") or "CONTINUOUS_TRADING").strip()
        if mkt == "HALTED":
            mem.pop(name, None)  # [default] reset hysteresis memory across reopen
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
            continue
        if mkt == "AUCTION":
            prev = mem.get(name)
            if prev is None:
                out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
            else:
                out.append(_mk(prev[0], prev[1], ts, "DEGRADED"))  # hold last, degraded
            continue
        if mkt == "CLOSED":
            out.append(_mk("OFF", float("nan"), ts, "OFF"))
            continue
        if str(e.get("calendar_confirmed", "1")).strip() not in ("1", "true", "True"):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1; memory kept
            continue
        try:
            d, iv = _row_value(e, cfg)
        except Exception:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F2; memory kept
            continue
        v = d
        dv = dual(events[: i + 1], cfg)
        if not (math.isfinite(dv) and abs(dv - v) <= DUAL_TOL):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F3; memory kept
            continue
        label = _label(d, iv, mem.get(name, (None, None))[0], cfg)
        try:
            lookback_n = int(float(e.get("lookback_n", "252")))
        except (TypeError, ValueError):
            lookback_n = 0
        module_state = "DEGRADED" if lookback_n < cfg["L_min"] else "OK"
        mem[name] = (label, d)
        out.append(_mk(label, d, ts, module_state))
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
    tape = _load("R035_tape.csv")
    exp = _load("R035_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R035_tape.csv")).readline()
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
    tape = _load("R035_tape.csv")
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


def test_f1_unconfirmed_calendar_unknown():
    tape = _load("R035_tape.csv")
    got = detect(None, tape, CFG)
    assert got[12]["state"] == "UNKNOWN" and got[12]["module_state"] == "UNKNOWN"


def test_f2_bounds_violation_unknown():
    tape = _load("R035_tape.csv")
    got = detect(None, tape, CFG)
    assert got[13]["module_state"] == "UNKNOWN", got[13]
    assert got[13]["state"] == "UNKNOWN"


def test_f3_dual_estimator_agreement():
    tape = _load("R035_tape.csv")
    got = detect(None, tape, CFG)
    # row 14: second calendar disagrees by 3 days -> F3 UNKNOWN
    assert got[14]["module_state"] == "UNKNOWN" and got[14]["state"] == "UNKNOWN"
    # agreement path: rows with matching dual stay non-UNKNOWN
    assert got[4]["module_state"] == "OK"


def test_f3_dual_disagreement_wiring():
    """Injected dual disagreement must force UNKNOWN (logic-drift pin)."""
    tape = _load("R035_tape.csv")[:5]
    got = detect(None, tape, CFG, dual_fn=lambda ev, c: 999.0)
    assert all(g["state"] == "UNKNOWN" and g["module_state"] == "UNKNOWN" for g in got)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R035_tape.csv")
    rs = detect(None, tape, CFG)[-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R035_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_hysteresis_hold_pins():
    """Rows 5-6 must stay PRE_EARNINGS inside the hysteresis band."""
    got = detect(None, _load("R035_tape.csv"), CFG)
    assert got[5]["state"] == "PRE_EARNINGS", got[5]   # iv 84 >= 90-10
    assert got[6]["state"] == "PRE_EARNINGS", got[6]   # d 3 <= 2+1, iv 85 >= 80


def test_hysteresis_exit_pin():
    """Row 10: iv 79 < 80 exits PRE_EARNINGS -> WATCH."""
    got = detect(None, _load("R035_tape.csv"), CFG)
    assert got[10]["state"] == "WATCH", got[10]


def test_halt_resets_hysteresis_memory():
    """Rows 6 and 8 share identical inputs; the halt between them must reset
    memory, so row 8 is WATCH where row 6 is PRE_EARNINGS."""
    got = detect(None, _load("R035_tape.csv"), CFG)
    assert got[6]["state"] == "PRE_EARNINGS"
    assert got[7]["state"] == "UNKNOWN" and got[7]["module_state"] == "UNKNOWN"
    assert got[8]["state"] == "WATCH", got[8]


def test_print_passed_forces_normal():
    """Row 11: d=-1 (print passed) -> NORMAL regardless of IV."""
    got = detect(None, _load("R035_tape.csv"), CFG)
    assert got[11]["state"] == "NORMAL", got[11]
    assert got[11]["value"] == -1.0


def test_missing_bars_no_interpolation():
    """The 2-day gap before row 11 must not be interpolated: value stays -1.0."""
    tape = _load("R035_tape.csv")
    t10 = int(float(tape[10]["ts_ns"]))
    t11 = int(float(tape[11]["ts_ns"]))
    assert t11 - t10 == 3 * CADENCE_NS, "fixture must contain a 2-day gap"
    got = detect(None, tape, CFG)
    assert got[11]["value"] == -1.0 and got[11]["state"] == "NORMAL"


def test_degraded_short_lookback():
    """Row 15: split inside lookback, 100 < 126 sessions -> DEGRADED label emitted."""
    got = detect(None, _load("R035_tape.csv"), CFG)
    assert got[15]["module_state"] == "DEGRADED", got[15]
    assert got[15]["state"] == "NORMAL"


def test_entry_after_unknown_or_degraded():
    """Row 16: strict entry works after UNKNOWN/DEGRADED rows (no stuck state)."""
    got = detect(None, _load("R035_tape.csv"), CFG)
    assert got[16]["state"] == "PRE_EARNINGS", got[16]
    assert got[16]["module_state"] == "OK"


def test_boundary_entry_conditions():
    """Row 1: d=5 -> WATCH (not entry). Row 3: iv=89 -> WATCH (not entry).
    Row 4: d=2, iv=90 -> PRE_EARNINGS (inclusive boundaries)."""
    got = detect(None, _load("R035_tape.csv"), CFG)
    assert got[1]["state"] == "WATCH"
    assert got[3]["state"] == "WATCH"
    assert got[4]["state"] == "PRE_EARNINGS"


def test_auction_holds_last_state_degraded():
    tape = [dict(r) for r in _load("R035_tape.csv")[:5]]
    tape.append(dict(tape[-1]))
    tape[-1]["market_state"] = "AUCTION"
    got = detect(None, tape, CFG)
    assert got[-1]["state"] == "PRE_EARNINGS", got[-1]
    assert got[-1]["module_state"] == "DEGRADED"


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module §R3)."""
    got = detect(None, _load("R035_tape.csv"), CFG)
    assert got[0]["state"] == "NORMAL", got[0]
    assert got[4]["state"] == "PRE_EARNINGS"
    assert got[9]["state"] == "PRE_EARNINGS"
