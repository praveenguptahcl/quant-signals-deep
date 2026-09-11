"""R042 — Cross-sectional dispersion / stock-picking environment: acceptance tests.

Real imports, fixture load, real assertions. Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_R042.py -q` exits 0.

v1.1.0: hysteresis entry/exit machine (§R2 normative), per-bar F3 dual-label
agreement, market-state freeze rows, corporate-action guard, cost interface
(§R5) pins, config-table match.
"""
import csv
import math
import os
import statistics

RID = "R042"
TOL = 1e-9
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

CFG = {"picker_entry": 0.015, "picker_exit": 0.012,
       "index_entry": 0.007, "index_exit": 0.010,
       "N": 6, "min_lag_bars": 1, "max_abs_return": 0.50}


def validate_cfg(cfg):
    assert cfg["picker_exit"] < cfg["picker_entry"], "deadband must be positive"
    assert cfg["index_entry"] < cfg["index_exit"], "deadband must be positive"
    assert cfg["picker_exit"] > cfg["index_exit"], "deadbands must be disjoint"
    assert cfg["N"] >= 2
    assert cfg["min_lag_bars"] >= 1
    assert cfg["max_abs_return"] > 0
    return cfg


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


def _name_values(e):
    keys = sorted(k for k in e if k.startswith("s"))
    return [_parse_float(e[k]) for k in keys]


def transition(prev, d, cfg):
    """Hysteresis state machine (normative §R2). Entry bands strict, exits looser."""
    if prev == "STOCK_PICKER":
        return "NEUTRAL" if d < cfg["picker_exit"] else "STOCK_PICKER"
    if prev == "INDEX_ONLY":
        return "NEUTRAL" if d > cfg["index_exit"] else "INDEX_ONLY"
    if d >= cfg["picker_entry"]:
        return "STOCK_PICKER"
    if d <= cfg["index_entry"]:
        return "INDEX_ONLY"
    return "NEUTRAL"


def _dispersion(xs, cfg):
    if any(not math.isfinite(v) for v in xs):
        raise ValueError("F1: missing/non-finite name return")
    if any(abs(v) > cfg["max_abs_return"] for v in xs):
        raise ValueError("F2: unadjusted corporate-action spike")
    n = len(xs)
    m = sum(xs) / n
    d = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    if not math.isfinite(d) or d < 0:
        raise ValueError("F2: out-of-bounds dispersion")
    return d


def _dual_dispersion(xs, cfg):
    if any(not math.isfinite(v) for v in xs):
        raise ValueError("F1")
    if any(abs(v) > cfg["max_abs_return"] for v in xs):
        raise ValueError("F2")
    return statistics.stdev(xs)


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal: the label at position t uses only events[:t+1] and the threaded
    prev label. `state` may carry {"prev_label": ...}; None starts NEUTRAL
    [default]. Empty input -> UNKNOWN (F1). Missing name return -> UNKNOWN
    (F1, mask, never interpolate). Non-finite D or |r| > max_abs_return ->
    UNKNOWN (F2). F3: dual-estimator (statistics.stdev) label disagreement ->
    UNKNOWN. Market-state rows: HALTED -> freeze label + UNKNOWN; AUCTION ->
    hold label + DEGRADED; CLOSED -> emit nothing.
    """
    validate_cfg(cfg)
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    prev = (state or {}).get("prev_label") or "NEUTRAL"
    ncol = None
    for e in events:
        ts = int(float(e["ts_ns"]))
        mkt = e.get("market_state", "CONTINUOUS_TRADING")
        if mkt == "CLOSED":
            continue
        if mkt == "HALTED":
            out.append(_mk(prev, float("nan"), ts, "UNKNOWN"))  # freeze label, unknown health
            continue
        if mkt == "AUCTION":
            out.append(_mk(prev, float("nan"), ts, "DEGRADED"))  # hold last state
            continue
        xs = _name_values(e)
        if ncol is None:
            ncol = len(xs)
        if len(xs) != ncol or len(xs) != cfg["N"]:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1: panel shape changed
            continue
        try:
            v = _dispersion(xs, cfg)
            v2 = _dual_dispersion(xs, cfg)
        except ValueError:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1/F2
            continue
        if transition(prev, v, cfg) != transition(prev, v2, cfg):
            out.append(_mk("UNKNOWN", v, ts, "UNKNOWN"))  # F3: dual-label disagreement
            continue
        prev = transition(prev, v, cfg)
        out.append(_mk(prev, v, ts, "OK"))
    return out


def apply_freshness(rs, now_ns):
    """F4: expire to UNKNOWN when computed_at is older than 3x cadence."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > 3 * CADENCE_NS:
        rs = dict(rs)
        rs["module_state"] = "UNKNOWN"
        rs["state"] = "UNKNOWN"
    return rs


def cost_adjustment(rsv, base):
    """Cost interface (§R5): regime state -> cost-function adjustment.

    Dispersion conditions the opportunity set; it does not move cost inputs
    directly, so all cost multipliers are identity [default]. The adjustment
    routes entry permission (trade_ok) and the required-edge multiplier.
    """
    adj = dict(base)
    adj["spread_mult"] = 1.0   # [default] dispersion does not move cost inputs
    adj["impact_mult"] = 1.0   # [default]
    adj["borrow_mult"] = 1.0   # [default]
    adj["fee_add_bps"] = 0.0   # [default]
    adj["edge_mult"] = 1.0     # [default]
    adj["tags"] = ["R042:" + rsv["state"]]
    st, ms = rsv["state"], rsv["module_state"]
    if ms == "UNKNOWN":
        adj["trade_ok"] = False   # [default] restrictive: unknown blocks new entries
    elif ms == "DEGRADED":
        adj["trade_ok"] = False   # [default] halt/auction rows: label withheld
        adj["edge_mult"] = 1.5    # [example]
    elif st == "STOCK_PICKER":
        adj["trade_ok"] = True
        adj["edge_mult"] = 0.8    # [example] dispersion opportunity compensates
    elif st == "INDEX_ONLY":
        adj["trade_ok"] = True
        adj["edge_mult"] = 1.5    # [example] thin alpha demands more edge
    else:  # NEUTRAL
        adj["trade_ok"] = True    # passthrough
    return adj


BASE_COST = {"spread_bps": 2.0, "impact_bps": 3.0, "borrow_bps": 1.0}


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
    tape = _load("R042_tape.csv")
    exp = _load("R042_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R042_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)
        assert g["estimator_version"] == ESTIMATOR_VERSION
        assert g["regime_id"] == RID


def test_hysteresis_state_sequence():
    """Fixture pins entry, deadband holds, exits, and re-entry."""
    tape = _load("R042_tape.csv")
    got = detect(None, tape, CFG)
    seq = [g["state"] for g in got[:9]]
    assert seq == ["NEUTRAL", "NEUTRAL", "INDEX_ONLY", "INDEX_ONLY", "NEUTRAL",
                   "STOCK_PICKER", "STOCK_PICKER", "NEUTRAL", "STOCK_PICKER"], seq
    # bar4: D=0.0085 > index_entry(0.007) — stateless banding would emit NEUTRAL;
    # hysteresis holds INDEX_ONLY.
    assert 0.007 < got[3]["value"] < 0.010 and got[3]["state"] == "INDEX_ONLY"
    # bar7: D=0.0135 < picker_entry(0.015) — stateless banding would emit NEUTRAL;
    # hysteresis holds STOCK_PICKER.
    assert 0.012 < got[6]["value"] < 0.015 and got[6]["state"] == "STOCK_PICKER"
    # bar10: missing name return pins F1 UNKNOWN inside the fixture.
    assert got[9]["state"] == "UNKNOWN" and got[9]["module_state"] == "UNKNOWN"


def test_hysteresis_boundary_behavior():
    """Exact-band semantics: entry on >= / <=, exit only past the exit band."""
    c = CFG
    assert transition("NEUTRAL", 0.015, c) == "STOCK_PICKER"      # entry on >=
    assert transition("NEUTRAL", 0.014999999, c) == "NEUTRAL"
    assert transition("NEUTRAL", 0.007, c) == "INDEX_ONLY"        # entry on <=
    assert transition("NEUTRAL", 0.007000001, c) == "NEUTRAL"
    assert transition("STOCK_PICKER", 0.012, c) == "STOCK_PICKER"  # exit only past
    assert transition("STOCK_PICKER", 0.011999999, c) == "NEUTRAL"
    assert transition("INDEX_ONLY", 0.010, c) == "INDEX_ONLY"
    assert transition("INDEX_ONLY", 0.010000001, c) == "NEUTRAL"


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R042_tape.csv")
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
    tape = _load("R042_tape.csv")
    assert detect(None, tape, CFG)[9]["module_state"] == "UNKNOWN"  # NaN name return


def test_f2_bounds_violation_unknown():
    tape = _load("R042_tape.csv")
    bad = [dict(r) for r in tape[:2]]
    bad[1]["s3"] = "nan"
    got = detect(None, bad, CFG)
    assert got[1]["module_state"] == "UNKNOWN", got[1]
    # corporate-action guard: unadjusted split-like spike trips F2
    spike = [dict(r) for r in tape[:2]]
    spike[1]["s2"] = "1.5"   # 150% single-day move [example]
    got2 = detect(None, spike, CFG)
    assert got2[1]["module_state"] == "UNKNOWN", got2[1]


def test_f3_dual_estimator_label_agreement():
    """statistics.stdev code path must reproduce every fixture label."""
    tape = _load("R042_tape.csv")
    primary = detect(None, tape, CFG)
    prev = "NEUTRAL"
    for e, rs in zip(tape, primary):
        xs = _name_values(e)
        if rs["module_state"] != "OK":
            continue
        v2 = _dual_dispersion(xs, CFG)
        assert transition(prev, v2, CFG) == rs["state"], (e, rs)
        prev = rs["state"]


def test_f4_staleness_expires_to_unknown():
    tape = _load("R042_tape.csv")
    rs = detect(None, tape, CFG)[-2]  # last OK row (bar9; bar10 is UNKNOWN)
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R042_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_market_state_freeze():
    """HALTED freezes the label (module UNKNOWN); AUCTION holds + DEGRADED; CLOSED emits nothing."""
    tape = _load("R042_tape.csv")
    halted = [dict(r) for r in tape[:4]]
    halted[3]["market_state"] = "HALTED"
    got = detect(None, halted, CFG)
    assert got[3]["module_state"] == "UNKNOWN", got[3]
    assert got[3]["state"] == "INDEX_ONLY", got[3]  # label frozen at bar3
    auction = [dict(r) for r in tape[:4]]
    auction[3]["market_state"] = "AUCTION"
    got2 = detect(None, auction, CFG)
    assert got2[3]["module_state"] == "DEGRADED"
    assert got2[3]["state"] == "INDEX_ONLY"
    closed = [dict(r) for r in tape[:4]]
    closed[3]["market_state"] = "CLOSED"
    got3 = detect(None, closed, CFG)
    assert len(got3) == 3, got3


def test_gap_no_interpolation():
    """Dropping a bar must not change any other bar's label (mask, never interpolate)."""
    tape = _load("R042_tape.csv")
    full = detect(None, tape, CFG)
    gapped = [r for i, r in enumerate(tape) if i != 1]  # drop bar2 (NEUTRAL; no path effect)
    got = detect(None, gapped, CFG)
    assert len(got) == len(full) - 1
    for a, b in zip(got[:1], full[:1]):
        assert a["state"] == b["state"] and _close(a["value"], b["value"], TOL)
    # after the gap the hysteresis machine continues from the same prior label
    for a, b in zip(got[1:], full[2:]):
        assert a["state"] == b["state"] and _close(a["value"], b["value"], TOL)


def test_cost_interface():
    """§R5: identity on cost inputs [default]; routing + edge_mult per state."""
    for st, exp_mult, exp_ok in [
        ("STOCK_PICKER", 0.8, True), ("NEUTRAL", 1.0, True),
        ("INDEX_ONLY", 1.5, True),
    ]:
        rsv = {"state": st, "module_state": "OK"}
        adj = cost_adjustment(rsv, BASE_COST)
        assert adj["spread_mult"] == 1.0 and adj["impact_mult"] == 1.0
        assert adj["borrow_mult"] == 1.0 and adj["fee_add_bps"] == 0.0
        assert adj["edge_mult"] == exp_mult, (st, adj)
        assert adj["trade_ok"] is exp_ok
        assert adj["tags"] == ["R042:" + st]
    for ms in ("UNKNOWN", "DEGRADED"):
        rsv = {"state": "NEUTRAL", "module_state": ms}
        adj = cost_adjustment(rsv, BASE_COST)
        assert adj["trade_ok"] is False, (ms, adj)  # restrictive, never benign


def test_config_defaults_match_r0_2():
    """CFG must equal the §R0.2 table."""
    expected = {"picker_entry": 0.015, "picker_exit": 0.012,
                "index_entry": 0.007, "index_exit": 0.010,
                "N": 6, "min_lag_bars": 1, "max_abs_return": 0.50}
    assert CFG == expected, (CFG, expected)
    validate_cfg(dict(CFG))


def test_invalid_cfg_rejected():
    bad = dict(CFG, picker_exit=0.016)  # exit above entry: no deadband
    try:
        validate_cfg(bad)
    except AssertionError:
        pass
    else:
        raise AssertionError("overlapping bands must be rejected")
    bad2 = dict(CFG, index_exit=0.013)  # deadbands overlap
    try:
        validate_cfg(bad2)
    except AssertionError:
        pass
    else:
        raise AssertionError("overlapping deadbands must be rejected")


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3)."""
    tape = _load('R042_tape.csv')
    got = detect(None, tape, CFG)
    assert abs(got[0]['value'] - 0.0108197) <= 1e-6, got[0]['value']
    assert got[0]['state'] == 'NEUTRAL'
    assert got[2]['state'] == 'INDEX_ONLY'
    # bar4: |0.01-(-0.00552)|*sqrt(0.3) = 0.0085006541 (hand-computed);
    # D > index_entry(0.007) yet state stays INDEX_ONLY: the hysteresis hold.
    assert abs(got[3]['value'] - 0.0085006541) <= 1e-6, got[3]['value']
    assert got[3]['state'] == 'INDEX_ONLY'
    # bar6 (index 5): |0.018-(-0.011212)|*sqrt(0.3) = 0.0160000713 (hand-computed).
    assert abs(got[5]['value'] - 0.0160000713) <= 1e-6, got[5]['value']
    assert got[5]['state'] == 'STOCK_PICKER'
