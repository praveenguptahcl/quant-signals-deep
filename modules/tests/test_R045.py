"""R045 — Cross-sectional volatility regime: acceptance tests.

Reference implementation of detect() per the module's normative pseudocode
(SR2.6) plus hysteresis transitions (SR2.7). Real imports, fixture load, real
assertions. Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_R045.py -q` exits 0.
"""
import csv
import math
import os
import statistics

RID = "R045"
TOL = 1e-9
CADENCE_NS = 86400000000000
ESTIMATOR_VERSION = "1.1.0"
DATA_VINTAGE = "2026-09-09"

CFG = {
    "window_days": 20,        # [example] per-name realized-vol window (days)
    "wide_entry": 0.50,       # [example] XS % entry
    "wide_exit": 0.40,        # [example] XS % exit (< wide_entry [rule])
    "narrow_entry": 0.25,     # [example] XS % entry
    "narrow_exit": 0.30,      # [example] XS % exit (> narrow_entry [rule])
    "min_coverage_frac": 0.75,  # [default]
    "ca_jump_tol": 5.0,       # [default] per-name vol vs trailing median
    "gap_mult": 3,            # [default] staleness multiple of cadence
    "N": 8,                   # [example] universe size in fixtures
    "min_lag_bars": 1,        # [default]
}


def _parse_float(x):
    try:
        s = str(x).strip()
        if s == "":
            return None
        return float(s)
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


def _band(xs, cfg):
    if xs >= cfg["wide_entry"]:
        return "WIDE"
    if xs <= cfg["narrow_entry"]:
        return "NARROW"
    return "NORMAL"


def _hysteresis(prev, xs, cfg):
    """Normative state transitions (module SR2.7). Entry is strict; exit is
    sticky. A value crossing the far band from any state takes that state."""
    we, wx = cfg["wide_entry"], cfg["wide_exit"]
    ne, nx = cfg["narrow_entry"], cfg["narrow_exit"]
    assert wx < we and nx > ne, "hysteresis width must be > 0"
    if xs >= we:
        return "WIDE"
    if xs <= ne:
        return "NARROW"
    if prev == "WIDE":
        return "WIDE" if xs >= wx else "NORMAL"
    if prev == "NARROW":
        return "NARROW" if xs <= nx else "NORMAL"
    return "NORMAL"


def _xs_of(vols):
    if len(vols) < 2:
        return float("nan")
    return statistics.stdev(vols)


def _new_state():
    return {"prev": "NORMAL", "hist": [], "last_ts": None, "last": None}


def _step(state, e, cfg):
    """One causal step. Returns (record, state). Never interpolates."""
    n = cfg["N"]
    names = ["v%d" % i for i in range(1, n + 1)]
    ts = int(float(e["ts_ns"]))
    ms = str(e.get("market_state", "CONTINUOUS_TRADING") or
             "CONTINUOUS_TRADING").strip().upper()

    # Market-state machine (module R0.6)
    if ms == "CLOSED":
        return _mk("OFF", float("nan"), ts, "OFF"), state
    if ms == "AUCTION":
        last = state["last"]
        if last is None:
            return _mk("UNKNOWN", float("nan"), ts, "UNKNOWN"), state
        rs = dict(last)
        rs["module_state"] = "DEGRADED"  # hold last label; no new labels
        return rs, state
    if ms == "HALTED":
        last = state["last"]
        val = last["value"] if last else float("nan")
        return _mk("UNKNOWN", val, ts, "UNKNOWN"), state  # frozen, no update

    # Gap policy (F4): > gap_mult x cadence -> UNKNOWN; (1x, gap_mult] -> DEGRADED
    gap_masked = False
    if state["last_ts"] is not None:
        dt = ts - state["last_ts"]
        if dt > cfg["gap_mult"] * CADENCE_NS:
            return _mk("UNKNOWN", float("nan"), ts, "UNKNOWN"), state
        if dt > CADENCE_NS:
            gap_masked = True

    # F1: parse per-name vols; missing cell -> missing name
    raw = [_parse_float(e.get(k)) for k in names]
    missing = [v is None for v in raw]
    present = [v for v, m in zip(raw, missing) if not m]
    if any(isinstance(v, float) and math.isnan(v) for v in present):
        return _mk("UNKNOWN", float("nan"), ts, "UNKNOWN"), state  # F1/F2
    if any(v < 0 for v in present):
        return _mk("UNKNOWN", float("nan"), ts, "UNKNOWN"), state  # F2
    coverage = len(present) / n
    if coverage < cfg["min_coverage_frac"]:
        return _mk("UNKNOWN", float("nan"), ts, "UNKNOWN"), state  # F1

    # Corporate-action guard: single-name vol spike vs its trailing median
    # is bad data, not volatility -> UNKNOWN (never silently absorbed).
    if len(state["hist"]) >= 5:
        for j, (v, m) in enumerate(zip(raw, missing)):
            if m:
                continue
            trail = [h[j] for h in state["hist"][-20:] if h[j] is not None]
            if len(trail) >= 5:
                med = statistics.median(trail)
                if med > 0 and v > cfg["ca_jump_tol"] * med:
                    return _mk("UNKNOWN", float("nan"), ts, "UNKNOWN"), state

    xs = _xs_of(present)
    if not math.isfinite(xs):  # F2
        return _mk("UNKNOWN", float("nan"), ts, "UNKNOWN"), state

    label = _hysteresis(state["prev"], xs, cfg)

    # F3: leave-one-name-out band agreement (dual estimator). A label that
    # flips when one name is dropped is outlier-driven -> DEGRADED, never OK.
    reasons = []
    if gap_masked:
        reasons.append("gap-masked")
    if coverage < 1.0:
        reasons.append("partial-coverage")
    base_band = _band(xs, cfg)
    for i in range(len(present)):
        sub = present[:i] + present[i + 1:]
        if len(sub) >= 2 and _band(_xs_of(sub), cfg) != base_band:
            reasons.append("outlier-driven")
            break

    module_state = "DEGRADED" if reasons else "OK"
    rs = _mk(label, xs, ts, module_state)
    if reasons:
        rs["degraded_reasons"] = ";".join(reasons)

    full = [None if m else v for v, m in zip(raw, missing)]
    state["hist"].append(full)
    state["last_ts"] = ts
    state["prev"] = label
    state["last"] = rs
    return rs, state


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal: the label at position t uses only events[:t+1]. Empty input ->
    UNKNOWN (F1). Invalid input -> UNKNOWN, never interpolate. Halt/auction
    events freeze per the market-state table. Emits regime labels and
    cost-interface adjustments only.
    """
    state = state if state is not None else _new_state()
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    for e in events:
        rs, state = _step(state, e, cfg)
        out.append(rs)
    return out


def apply_freshness(rs, now_ns):
    """F4: expire to UNKNOWN when computed_at is older than 3x cadence."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > 3 * CADENCE_NS:
        rs = dict(rs)
        rs["module_state"] = "UNKNOWN"
        rs["state"] = "UNKNOWN"
    return rs


def cost_adjustment(rsv_state, base):
    """Cost interface (module SR5): regime state -> cost-function adjustment.

    base: dict(spread_bps, impact_bps, borrow_bps, fees_bps) from the gated
    strategy's COST block. Only spread and impact scale with cross-sectional
    vol; borrow/fees do not. UNKNOWN is restrictive: trade_ok = False.
    """
    adj = dict(base)
    if rsv_state == "WIDE":
        adj["spread_mult"] = 2.0  # [example] starting point — calibrate per SR5
        adj["impact_mult"] = 2.0  # [example]
        adj["trade_ok"] = True
    elif rsv_state == "UNKNOWN":
        adj["trade_ok"] = False  # restrictive default: never benign
    else:  # NORMAL / NARROW
        adj["spread_mult"] = 1.0  # [default]
        adj["impact_mult"] = 1.0  # [default]
        adj["trade_ok"] = True
    adj["borrow_mult"] = 1.0  # [default] borrow does not scale with vol-of-vol
    adj["fees_mult"] = 1.0    # [default] fees do not scale with vol-of-vol
    return adj


def _load(name):
    p = os.path.join(os.path.dirname(__file__), "..", "fixtures", name)
    with open(p) as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def _close(a, b, tol):
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return abs(a - b) <= tol


def _evt(ts_day, vols, market_state=None):
    e = {"ts_ns": str(1788984000000000000 + ts_day * CADENCE_NS)}
    for i, v in enumerate(vols, 1):
        e["v%d" % i] = "" if v is None else str(v)
    if market_state:
        e["market_state"] = market_state
    return e


# ---- acceptance tests ----

def test_fixture_replay():
    tape = _load("R045_tape.csv")
    exp = _load("R045_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R045_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)


def test_regime_state_vector_schema():
    tape = _load("R045_tape.csv")
    for rs in detect(None, tape, CFG):
        for k in ("regime_id", "state", "value", "estimator_version",
                  "data_vintage", "computed_at", "module_state",
                  "min_lag_bars"):
            assert k in rs, k
        assert rs["regime_id"] == RID
        assert rs["estimator_version"] == ESTIMATOR_VERSION
        assert rs["min_lag_bars"] >= 1


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R045_tape.csv")
    full = detect(None, tape, CFG)
    for k in range(1, len(tape) + 1):
        prefix = detect(None, tape[:k], CFG)
        assert len(prefix) == k
        for a, b in zip(prefix, full[:k]):
            assert a["state"] == b["state"], (k, a, b)
            assert a["module_state"] == b["module_state"]
            assert _close(a["value"], b["value"], TOL), (k, a["value"], b["value"])


def test_hysteresis_transition_sequence():
    """NORMAL -> WIDE (entry) -> WIDE (hold below entry) -> NORMAL (exit) ->
    NARROW (entry) -> NARROW (hold above entry) -> NORMAL (exit)."""
    tape = _load("R045_tape.csv")
    got = detect(None, tape, CFG)
    states = [g["state"] for g in got[:7]]
    assert states == ["NORMAL", "WIDE", "WIDE", "NORMAL",
                      "NARROW", "NARROW", "NORMAL"], states
    # hysteresis holds are OK (not UNKNOWN): the label persisted on value alone
    assert got[2]["module_state"] == "OK"
    assert got[5]["module_state"] == "OK"
    # holds sit strictly inside the hysteresis bands
    assert CFG["wide_exit"] < got[2]["value"] < CFG["wide_entry"]
    assert CFG["narrow_entry"] < got[5]["value"] < CFG["narrow_exit"]


def test_hysteresis_entry_exit_boundaries():
    """Exact boundary pinning: entry is strict (>=), exit is sticky."""
    c = CFG
    # exact wide entry enters from NORMAL
    assert _hysteresis("NORMAL", c["wide_entry"], c) == "WIDE"
    # exact wide exit holds while WIDE
    assert _hysteresis("WIDE", c["wide_exit"], c) == "WIDE"
    # one tick below exit leaves WIDE
    assert _hysteresis("WIDE", c["wide_exit"] - 1e-12, c) == "NORMAL"
    # exact narrow entry enters from NORMAL
    assert _hysteresis("NORMAL", c["narrow_entry"], c) == "NARROW"
    # exact narrow exit holds while NARROW
    assert _hysteresis("NARROW", c["narrow_exit"], c) == "NARROW"
    # one tick above exit leaves NARROW
    assert _hysteresis("NARROW", c["narrow_exit"] + 1e-12, c) == "NORMAL"
    # far-band jumps from any state
    assert _hysteresis("NARROW", c["wide_entry"], c) == "WIDE"
    assert _hysteresis("WIDE", c["narrow_entry"], c) == "NARROW"


def test_f1_empty_events_unknown():
    got = detect(None, [], CFG)
    assert len(got) == 1
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"


def test_partial_coverage_degraded():
    """One name missing (7/8 = 0.875 >= 0.75): label over present names,
    DEGRADED — never silently OK, never interpolated."""
    tape = _load("R045_tape.csv")
    got = detect(None, tape, CFG)
    row = got[7]  # tape row 8: v1 empty
    assert row["module_state"] == "DEGRADED", row
    assert row["state"] == "NORMAL", row
    assert "partial-coverage" in row.get("degraded_reasons", ""), row


def test_f1_insufficient_coverage_unknown():
    vols = [1.2, 0.9, 1.5, None, None, None, 0.7, 1.4]  # 5/8 = 0.625 < 0.75
    got = detect(None, [_evt(0, vols)], CFG)
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"


def test_f2_nonfinite_unknown():
    tape = _load("R045_tape.csv")
    bad = [dict(r) for r in tape]
    bad[0]["v1"] = "nan"
    got = detect(None, bad, CFG)
    assert got[0]["module_state"] == "UNKNOWN", got[0]


def test_f3_outlier_driven_degraded():
    """Single-name-dominated XS: label emitted but never OK."""
    tape = _load("R045_tape.csv")
    got = detect(None, tape, CFG)
    row = got[9]  # tape row 10: one name dominates the cross-section
    assert row["state"] == "WIDE", row
    assert row["module_state"] == "DEGRADED", row
    assert row.get("degraded_reasons") == "outlier-driven", row


def test_f4_staleness_expires_to_unknown():
    tape = _load("R045_tape.csv")
    rs = detect(None, tape, CFG)[1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f4_gap_policy():
    base = [1.2, 0.9, 1.5, 1.1, 1.8, 0.7, 1.4, 1.0]
    evs = [_evt(0, base), _evt(2, base)]  # 2-day gap: masked, DEGRADED
    got = detect(None, evs, CFG)
    assert got[1]["module_state"] == "DEGRADED", got[1]
    assert got[1]["state"] == "NORMAL"
    evs2 = [_evt(0, base), _evt(4, base)]  # 4-day gap: stale -> UNKNOWN
    got2 = detect(None, evs2, CFG)
    assert got2[1]["module_state"] == "UNKNOWN", got2
    assert got2[1]["state"] == "UNKNOWN"


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R045_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_corporate_action_guard_unknown():
    tape = _load("R045_tape.csv")
    got = detect(None, tape, CFG)
    row = got[10]  # tape row 11: v1 = 40% — unadjusted jump vs trailing median
    assert row["module_state"] == "UNKNOWN", row
    assert row["state"] == "UNKNOWN"


def test_halt_freezes_and_unknown():
    base = [1.2, 0.9, 1.5, 1.1, 1.8, 0.7, 1.4, 1.0]
    wide = [2.5, 1.0, 3.0, 1.2, 2.8, 0.8, 2.2, 1.5]
    evs = [_evt(0, base), _evt(1, wide), _evt(2, base, "HALTED"),
           _evt(3, base)]
    got = detect(None, evs, CFG)
    assert got[1]["state"] == "WIDE"
    assert got[2]["module_state"] == "UNKNOWN"  # halt: freeze, emit UNKNOWN
    assert got[2]["state"] == "UNKNOWN"
    assert got[3]["state"] == "NORMAL"  # resumes; halt bar never entered history


def test_auction_holds_last_degraded():
    base = [1.2, 0.9, 1.5, 1.1, 1.8, 0.7, 1.4, 1.0]
    wide = [2.5, 1.0, 3.0, 1.2, 2.8, 0.8, 2.2, 1.5]
    evs = [_evt(0, base), _evt(1, wide), _evt(2, wide, "AUCTION")]
    got = detect(None, evs, CFG)
    assert got[2]["state"] == "WIDE"  # hold last label
    assert got[2]["module_state"] == "DEGRADED"
    assert got[2]["value"] == got[1]["value"]  # no new computation


def test_cost_interface_wide_scales_spread_impact():
    base = {"spread_bps": 4.0, "impact_bps": 2.0,
            "borrow_bps": 1.0, "fees_bps": 0.5}
    adj = cost_adjustment("WIDE", base)
    assert adj["spread_mult"] == 2.0
    assert adj["impact_mult"] == 2.0
    assert adj["borrow_mult"] == 1.0  # borrow does not scale with vol-of-vol
    assert adj["fees_mult"] == 1.0
    assert adj["trade_ok"] is True
    eff = (base["spread_bps"] * adj["spread_mult"]
           + base["impact_bps"] * adj["impact_mult"])
    assert eff == 4.0 * 2.0 + 2.0 * 2.0


def test_cost_interface_unknown_restrictive():
    base = {"spread_bps": 4.0, "impact_bps": 2.0,
            "borrow_bps": 1.0, "fees_bps": 0.5}
    adj = cost_adjustment("UNKNOWN", base)
    assert adj["trade_ok"] is False  # never benign
    adj_n = cost_adjustment("NORMAL", base)
    assert adj_n["spread_mult"] == 1.0 and adj_n["trade_ok"] is True


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R2)."""
    tape = _load('R045_tape.csv')
    got = detect(None, tape, CFG)
    assert abs(got[0]['value'] - 0.3546) <= 1e-4, got[0]['value']
    assert got[0]['state'] == 'NORMAL'
    assert abs(got[1]['value'] - 0.8565) <= 1e-4, got[1]['value']
    assert got[1]['state'] == 'WIDE'
