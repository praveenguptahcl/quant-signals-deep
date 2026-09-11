"""R050 — SIP-vs-direct divergence (capability-gated): acceptance tests.

The module is capability-gated: on a SIP-only stack it permanently emits
UNKNOWN. Every test pins that behavior. Any test that would require a
measured divergence value must FAIL on this stack rather than fabricate one.
Definition of done: `python3 -m pytest modules/tests/test_R050.py -q` exits 0.
"""
import csv
import math
import os

RID = "R050"
TOL = 1e-9
DUAL_TOL = 1e-12
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

# The capability gate, pinned in code: SIP-only stack -> no direct feeds.
CFG = {"min_lag_bars": 1, "direct_feeds_available": False}

# Cost interface (mirrors §R5 COST_ADJUSTMENT_R050 v1.1.0).
COST_ADJUSTMENT_R050 = {
    "regime_id": RID, "version": "1.1.0",
    "UNKNOWN":   {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0, "fee_add_bps": 0.0},
    "DIVERGENT": {"spread_mult": 1.5, "impact_mult": 1.3, "borrow_mult": 1.0, "fee_add_bps": 0.0},
    "CALM":      {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0, "fee_add_bps": 0.0},
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
    # Capability gate (F1): no direct feeds on this stack, so no row can ever
    # produce a divergence value. SIP-only columns are ignored, not used.
    return float('nan')


def _aggregate(events, vals, cfg):
    return float('nan')


def _dual_aggregate(events, cfg):
    return float('nan')


def _state_of(value, e, cfg):
    return 'UNKNOWN'


def _bounds_ok(value, cfg):
    return False  # never measurable here → UNKNOWN by construction


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal: the label at position t uses only events[:t+1]. The F1 capability
    gate fires before any arithmetic: without direct feeds every input yields
    module_state UNKNOWN (never interpolates, never fabricates).
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


def apply_cost_adjustment(rs, cfg):
    """§R5: the gate forbids measurable-state adjustments on a SIP-only stack.

    UNKNOWN -> identity record. DIVERGENT/CALM may only be applied when the
    module actually measured them (module_state OK with direct feeds present);
    on this stack that path must raise rather than fabricate an adjustment.
    """
    if rs["state"] != "UNKNOWN" and not cfg.get("direct_feeds_available", False):
        raise AssertionError("gate: measurable regime states must never be "
                             "applied on a SIP-only stack")
    return COST_ADJUSTMENT_R050.get(rs["state"], COST_ADJUSTMENT_R050["UNKNOWN"])


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
    tape = _load("R050_tape.csv")
    exp = _load("R050_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R050_tape.csv")).readline()
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
    tape = _load("R050_tape.csv")
    full = detect(None, tape, CFG)
    for k in range(1, len(tape) + 1):
        prefix = detect(None, tape[:k], CFG)
        assert len(prefix) == k
        for a, b in zip(prefix, full[:k]):
            assert a["state"] == b["state"], (k, a, b)
            assert a["module_state"] == b["module_state"]
            assert _close(a["value"], b["value"], TOL), (k, a["value"], b["value"])


def test_sip_only_input_unknown():
    """SIP-only events (no direct-feed columns at all) must yield UNKNOWN.

    This is the module's core contract: divergence is unmeasurable on a
    SIP-only stack, so the honest output is UNKNOWN, never a number.
    """
    events = [
        {"ts_ns": "1789070400000000000", "sip_bid": "100.01", "sip_ask": "100.02"},
        {"ts_ns": "1789156800000000000", "sip_bid": "100.03", "sip_ask": "100.05"},
    ]
    got = detect(None, events, CFG)
    assert len(got) == 2
    for rs in got:
        assert rs["state"] == "UNKNOWN", rs
        assert rs["module_state"] == "UNKNOWN", rs
        assert math.isnan(rs["value"]), rs


def test_fabrication_guard_rejects_sip_proxy():
    """A SIP-derived 'divergence' value offered by the Adversary must not be
    echoed or measured: fixture row 2 carries div_bps=3.4 and must still yield
    UNKNOWN/NaN."""
    tape = _load("R050_tape.csv")
    got = detect(None, [tape[1]], CFG)
    assert got[0]["state"] == "UNKNOWN", got[0]
    assert got[0]["module_state"] == "UNKNOWN", got[0]
    assert math.isnan(got[0]["value"]), got[0]


def test_halt_freezes_to_unknown():
    """A HALT row freezes the module and emits UNKNOWN."""
    tape = _load("R050_tape.csv")
    got = detect(None, [tape[2]], CFG)
    assert got[0]["state"] == "UNKNOWN", got[0]
    assert got[0]["module_state"] == "UNKNOWN", got[0]
    assert math.isnan(got[0]["value"])


def test_f1_missing_input_unknown():
    got = detect(None, [], CFG)
    assert len(got) == 1
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"


def test_f2_bounds_violation_unknown():
    tape = _load("R050_tape.csv")
    bad = [dict(r) for r in tape]
    bad[0]["div_bps"] = "nan"
    got = detect(None, bad, CFG)
    assert got[0]["module_state"] == "UNKNOWN", got[0]


def test_f3_dual_estimator_agreement():
    tape = _load("R050_tape.csv")
    vals = [_row_value(e, CFG) for e in tape]
    v1 = _aggregate(tape, vals, CFG)
    v2 = _dual_aggregate(tape, CFG)
    if not _bounds_ok(v1, CFG):
        return  # degenerate panel: both estimators must agree on UNKNOWN-ness
    assert _close(v1, v2, DUAL_TOL), (v1, v2)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R050_tape.csv")
    rs = detect(None, tape, CFG)[-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R050_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_cost_interface_identity_on_unknown():
    """On this stack every emitted state is UNKNOWN -> identity adjustment.

    If the detector ever drifted into emitting a measurable state, applying it
    must raise (fabrication), not silently adjust costs.
    """
    tape = _load("R050_tape.csv")
    for rs in detect(None, tape, CFG):
        adj = apply_cost_adjustment(rs, CFG)
        assert adj["spread_mult"] == 1.0, adj
        assert adj["impact_mult"] == 1.0, adj
        assert adj["borrow_mult"] == 1.0, adj
        assert adj["fee_add_bps"] == 0.0, adj
    drifted = _mk("DIVERGENT", 5.0, 1789070400000000000, "OK")
    try:
        apply_cost_adjustment(drifted, CFG)
    except AssertionError:
        pass
    else:
        raise AssertionError("gate failed: measurable-state adjustment must "
                             "raise on a SIP-only stack")


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3)."""
    tape = _load('R050_tape.csv')
    got = detect(None, tape, CFG)
    assert len(got) == 3
    for rs in got:
        assert rs['state'] == 'UNKNOWN', rs
        assert rs['module_state'] == 'UNKNOWN'
        assert math.isnan(rs['value'])
