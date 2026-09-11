"""R030 — Central-bank event proximity: acceptance tests.

Tests the normative detector (hysteresis state machine, trading-day tau,
market-state freeze, F1-F5 fail-safes) against the validation-run fixture.
Definition of done: `python3 -m pytest modules/tests/test_R030.py -q` exits 0.
"""
import csv
import math
import os
import datetime as _dt

RID = "R030"
TOL = 1e-9
DUAL_TOL = 1e-9
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

CFG = {"drift_lo": 2.0, "drift_hi": 25.0, "pre_lo": 0.5,
       "shock_exit": -0.02, "h": 0.5, "min_lag_bars": 1}


def _parse_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _trading_days(d0, d1):
    """Weekdays in (d0, d1]. Fixture-local: weekends excluded, holidays ignored."""
    n, d = 0, d0 + _dt.timedelta(days=1)
    while d <= d1:
        if d.weekday() < 5:
            n += 1
        d += _dt.timedelta(days=1)
    return float(n)


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


def _row_tau(e, cfg):
    """tau: explicit override (synthetic intraday pin) else trading-day count.

    Raises ValueError on unparseable input (F1/F2).
    """
    ovr = (e.get("tau_override") or "").strip()
    if ovr:
        v = float(ovr)
        if not math.isfinite(v):
            raise ValueError("non-finite tau override")
        return v
    try:
        d0 = _dt.date.fromisoformat(e["asof"])
        d1 = _dt.date.fromisoformat(e["event_date"])
    except Exception:
        raise ValueError("bad event date")  # F1
    if not d1 >= d0:
        raise ValueError("event_date before asof")  # F2
    return _trading_days(d0, d1)


def _transition(prev, tau, cfg):
    """Hysteresis state machine (normative; mirrors module §R2 pseudocode)."""
    HI, LO, PLO, SX, H = (cfg["drift_hi"], cfg["drift_lo"], cfg["pre_lo"],
                          cfg["shock_exit"], cfg["h"])
    if prev in ("EVENT_DAY", "POST_DIGEST") and tau > HI + H:
        return "FAR"  # calendar rolled to a far next event
    if prev == "FAR":
        return "DRIFT" if tau <= HI else "FAR"
    if prev == "DRIFT":
        if tau > HI + H:
            return "FAR"
        if tau <= LO:
            return "PRE_EVENT"
        return "DRIFT"
    if prev == "PRE_EVENT":
        if tau > LO + H:
            return "DRIFT"
        if tau <= PLO:
            return "EVENT_DAY"
        return "PRE_EVENT"
    if prev == "EVENT_DAY":
        if tau <= SX:
            return "POST_DIGEST"
        if tau > PLO + H:
            return "PRE_EVENT"  # calendar shifted
        return "EVENT_DAY"
    if prev == "POST_DIGEST":
        if tau > HI + H:
            return "FAR"
        if tau > LO + H:
            return "DRIFT"
        if tau > PLO + H:
            return "PRE_EVENT"
        return "POST_DIGEST"
    return "UNKNOWN"


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal: label at position t uses only events[:t+1] plus prior label.
    state is a mutable dict carrying 'prev' across rows; None -> {'prev': 'FAR'}.
    Empty input or unparseable row -> module_state UNKNOWN (F1); non-finite tau
    or inverted dates -> UNKNOWN (F2). HALTED freezes and emits UNKNOWN;
    AUCTION holds last label and emits DEGRADED. Never interpolates.
    """
    if state is None:
        state = {"prev": "FAR"}
    prev = state.get("prev", "FAR")
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    for i, e in enumerate(events):
        ts = int(float(e["ts_ns"]))
        market = (e.get("market") or "").strip().upper()
        if market == "HALTED":
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # freeze; prev kept
            continue
        if market == "AUCTION":
            out.append(_mk(prev if prev != "FAR" else "UNKNOWN", float("nan"), ts, "DEGRADED"))
            continue
        try:
            tau = _row_tau(e, cfg)
        except Exception:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1/F2
            continue  # prev frozen
        if not math.isfinite(tau):
            out.append(_mk("UNKNOWN", tau, ts, "UNKNOWN"))  # F2
            continue
        label = _transition(prev, tau, cfg)
        out.append(_mk(label, tau, ts, "OK"))
        prev = label
    state["prev"] = prev
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


def _ev(asof, event_date, tau_override="", market="", ts_ns=1789070400000000000):
    return {"ts_ns": str(ts_ns), "asof": asof, "event_date": event_date,
            "tau_override": tau_override, "market": market}


def test_fixture_replay():
    tape = _load("R030_tape.csv")
    exp = _load("R030_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R030_tape.csv")).readline()
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
    tape = _load("R030_tape.csv")
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
    tape = _load("R030_tape.csv")
    bad = [dict(r) for r in tape]
    bad[1]["event_date"] = "not-a-date"
    got = detect(None, bad, CFG)
    assert got[1]["module_state"] == "UNKNOWN", got[1]


def test_f3_dual_estimator_agreement():
    tape = _load("R030_tape.csv")[:5]  # date-derived rows only
    for e in tape:
        d0 = _dt.date.fromisoformat(e["asof"])
        d1 = _dt.date.fromisoformat(e["event_date"])
        v1 = _row_tau(e, CFG)  # day-by-day count
        total = (d1 - d0).days
        weeks, rem = divmod(total, 7)  # arithmetic decomposition (independent impl)
        v2 = weeks * 5 + sum(1 for i in range(1, rem + 1)
                             if (d0 + _dt.timedelta(days=weeks * 7 + i)).weekday() < 5)
        assert _close(v1, v2, DUAL_TOL), (v1, v2)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R030_tape.csv")
    rs = detect(None, tape, CFG)[0]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R030_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3)."""
    tape = _load("R030_tape.csv")
    got = detect(None, tape, CFG)
    assert got[0]["value"] == 4.0, got[0]["value"]   # trading days (Sep 10, Sep 16]
    assert got[0]["state"] == "DRIFT"
    assert got[1]["state"] == "PRE_EVENT"
    assert got[2]["state"] == "EVENT_DAY"
    assert got[3]["state"] == "FAR"                  # calendar rolled to 2026-10-28


def test_trading_day_tau_not_calendar_days():
    """§R3 is trading-day distance: a weekend must not advance tau."""
    got = detect(None, [_ev("2026-09-11", "2026-09-14")], CFG)  # Fri -> Mon
    assert got[0]["value"] == 1.0, got[0]["value"]


def test_hysteresis_exact_boundaries():
    """Exit boundary is strict (>); entry is inclusive (<=)."""
    seq = [
        (_ev("2026-10-05", "2026-10-28", "20.0"), "DRIFT"),
        (_ev("2026-10-05", "2026-10-28", "25.5"), "DRIFT"),   # exact exit: holds
        (_ev("2026-10-05", "2026-10-28", "25.51"), "FAR"),    # exit
        (_ev("2026-10-05", "2026-10-28", "25.0"), "DRIFT"),   # exact entry: re-enters
    ]
    got = detect(None, [e for e, _ in seq], CFG)
    assert [g["state"] for g in got] == [s for _, s in seq], got
    st = {"prev": "DRIFT"}
    got = detect(st, [_ev("2026-10-05", "2026-10-28", "2.5")], CFG)
    assert got[0]["state"] == "DRIFT"  # 2.5 > drift_lo: no PRE entry
    st = {"prev": "DRIFT"}
    got = detect(st, [_ev("2026-10-05", "2026-10-28", "2.0")], CFG)
    assert got[0]["state"] == "PRE_EVENT"  # exact entry


def test_hysteresis_prevents_flipflop():
    """Same tau=0.5 classifies differently by prior state — hysteresis, not bug."""
    st1 = {"prev": "DRIFT"}
    a = detect(st1, [_ev("2026-10-05", "2026-10-28", "0.5")], CFG)[0]
    assert a["state"] == "PRE_EVENT"
    st2 = {"prev": "PRE_EVENT"}
    b = detect(st2, [_ev("2026-10-05", "2026-10-28", "0.5")], CFG)[0]
    assert b["state"] == "EVENT_DAY"


def test_event_day_exit_to_post_digest():
    st = {"prev": "EVENT_DAY"}
    a = detect(st, [_ev("2026-10-05", "2026-10-28", "-0.01")], CFG)[0]
    assert a["state"] == "EVENT_DAY"  # -0.01 > shock_exit: window still open
    st = {"prev": "EVENT_DAY"}
    b = detect(st, [_ev("2026-10-05", "2026-10-28", "-0.02")], CFG)[0]
    assert b["state"] == "POST_DIGEST"  # exact exit edge
    assert st["prev"] == "POST_DIGEST"


def test_rollover_far_after_event():
    st = {"prev": "EVENT_DAY"}
    got = detect(st, [_ev("2026-09-18", "2026-10-28")], CFG)[0]
    assert got["state"] == "FAR"  # tau=28 vs next event


def test_unknown_freezes_prev():
    st = {"prev": "POST_DIGEST"}
    rows = [_ev("2026-10-05", "", ""),              # missing date -> UNKNOWN
            _ev("2026-10-05", "2026-10-28", "1.2")]
    got = detect(st, rows, CFG)
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[1]["state"] == "PRE_EVENT"  # prev survived the UNKNOWN row


def test_halt_freezes_and_emits_unknown():
    st = {"prev": "DRIFT"}
    rows = [_ev("2026-10-05", "2026-10-28", "1.0", market="HALTED"),
            _ev("2026-10-06", "2026-10-28", "1.0")]
    got = detect(st, rows, CFG)
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[1]["state"] == "PRE_EVENT"  # resume from frozen prev


def test_auction_holds_last_state_degraded():
    st = {"prev": "DRIFT"}
    got = detect(st, [_ev("2026-10-05", "2026-10-28", "20.0", market="AUCTION")], CFG)
    assert got[0]["module_state"] == "DEGRADED"
    assert got[0]["state"] == "DRIFT"


def test_corporate_action_fields_ignored():
    """Splits/dividends do not touch calendar-based tau: extra columns are no-ops."""
    base = _ev("2026-09-10", "2026-09-16")
    corp = dict(base, split_ratio="4:1", dividend_cash="2.50", adj_factor="0.25")
    a = detect(None, [base], CFG)[0]
    b = detect(None, [corp], CFG)[0]
    assert a["state"] == b["state"] == "DRIFT"
    assert a["value"] == b["value"]


def test_missing_bar_gap_does_not_interpolate():
    """A dropped daily bar must not shift the next label: calendar time, not bars."""
    full = [_ev("2026-09-10", "2026-09-16"), _ev("2026-09-11", "2026-09-16"),
            _ev("2026-09-14", "2026-09-16")]
    gapped = [full[0], full[2]]
    a = detect(None, full, CFG)
    b = detect(None, gapped, CFG)
    assert b[-1]["state"] == a[-1]["state"] == "PRE_EVENT"
    assert b[-1]["value"] == a[-1]["value"] == 2.0  # Fri + Mon


def test_cost_adjustment_record_matches_md():
    """The md's COST_ADJUSTMENT_R030 must parse, cover all live states, and
    version-match: fails on cost-interface logic drift."""
    import ast
    md = os.path.join(os.path.dirname(__file__), "..", "regimes", "R030.md")
    src = open(md).read()
    line = next(l for l in src.splitlines()
                if l.startswith("COST_ADJUSTMENT_R030 ="))
    adj = ast.literal_eval(line.split("=", 1)[1].strip())
    assert adj["version"] == ESTIMATOR_VERSION, adj["version"]
    assert adj["regime_id"] == RID
    for st in ("EVENT_DAY", "PRE_EVENT", "OTHER"):
        rec = adj[st]
        for k in ("spread_mult", "impact_mult", "borrow_mult", "fee_add_bps"):
            assert rec[k] >= 0, (st, k, rec[k])
    assert adj["OTHER"]["spread_mult"] == 1.0  # identity default
    assert adj["EVENT_DAY"]["spread_mult"] >= adj["PRE_EVENT"]["spread_mult"] >= 1.0
