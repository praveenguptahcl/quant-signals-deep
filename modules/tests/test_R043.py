"""R043 — Short interest / crowdedness: acceptance tests.

Implements the normative §R2.1 detection pseudocode (entry/exit hysteresis
bands, F1-F5 edge cases) against the fixture tape, plus the §Cost-interface
adjustment record. Real imports, real assertions — not a production harness.

Definition of done: `python3 -m pytest modules/tests/test_R043.py -q` exits 0.
"""
import csv
import math
import os

RID = "R043"
TOL = 1e-9
DUAL_TOL = 1e-12
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 1296000000000000  # ~15 days, bi-monthly [example]
DATA_VINTAGE = "2026-09-09"

CFG = {
    "squeeze": 0.25, "squeeze_exit": 0.22,
    "crowded": 0.12, "crowded_exit": 0.09,
    "dtc_crit": 5.0, "dtc_exit": 4.0,
    "min_lag_bars": 1, "staleness_days": 45,
}

COST_ADJUSTMENT_R043 = {
    "regime_id": "R043", "version": "1.1.0",
    "SQUEEZE_WATCH": {"spread_mult": 1.5, "impact_mult": 2.0,
                      "borrow_mult": 5.0, "fee_add_bps": 0.0, "tag": "[example]"},
    "CROWDED": {"spread_mult": 1.1, "impact_mult": 1.25,
                "borrow_mult": 2.0, "fee_add_bps": 0.0, "tag": "[example]"},
    "NORMAL": {"spread_mult": 1.0, "impact_mult": 1.0,
               "borrow_mult": 1.0, "fee_add_bps": 0.0, "tag": "[default]"},
    "UNKNOWN": {"spread_mult": 1.0, "impact_mult": 1.0,
                "borrow_mult": 1.0, "fee_add_bps": 0.0, "tag": "[default]"},
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
        "min_lag_bars": CFG["min_lag_bars"],
    }


def _row_value(e):
    """short_pct from the tape; raises on missing/non-finite (F1/F2)."""
    s = _parse_float(e["short_pct_float"])
    d = _parse_float(e["days_to_cover"])
    if not (math.isfinite(s) and math.isfinite(d)):
        raise ValueError("missing or non-finite SI inputs")
    if s < 0 or d < 0:
        raise ValueError("negative short_pct or DTC is unphysical")
    return s, d


def _state_of(prev, short_pct, dtc, cfg):
    """Normative classify() per §R2.1: entry bands + exit (hysteresis) bands.

    prev is the last *valid* label for this name; hysteresis memory survives
    UNKNOWN prints. Entry requires the entry band; holding the flag requires
    only the exit band.
    """
    s, d = short_pct, dtc
    if s >= cfg["squeeze"]:
        return "SQUEEZE_WATCH"
    if prev == "SQUEEZE_WATCH" and s >= cfg["squeeze_exit"]:
        return "SQUEEZE_WATCH"
    if s >= cfg["crowded"] or d >= cfg["dtc_crit"]:
        return "CROWDED"
    if prev in ("SQUEEZE_WATCH", "CROWDED") and (
            s >= cfg["crowded_exit"] or d >= cfg["dtc_exit"]):
        return "CROWDED"
    return "NORMAL"


def _dual_state_of(short_pct, dtc, cfg):
    """Independent second implementation (F3): entry-only re-derivation, no
    hysteresis — used to cross-check the no-hysteresis path and bounds."""
    s, d = short_pct, dtc
    if s >= cfg["squeeze"]:
        return "SQUEEZE_WATCH"
    if s >= cfg["crowded"] or d >= cfg["dtc_crit"]:
        return "CROWDED"
    return "NORMAL"


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal: the label at position t uses only events[:t+1] and the module's
    own hysteresis memory. Empty input or an unparseable row yields
    module_state UNKNOWN (F1); out-of-bounds values yield UNKNOWN (F2).
    Never interpolates. Halt events (market_state == 'HALTED') freeze:
    UNKNOWN emitted, memory preserved.
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    memory = {}  # per-name last valid label (hysteresis)
    for e in events:
        ts = int(float(e["ts_ns"]))
        name = e.get("name", "AAA")
        prev = memory.get(name, "NORMAL")
        if e.get("market_state") == "HALTED":
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
            continue  # freeze: memory preserved, no label
        try:
            s, d = _row_value(e)
        except ValueError:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
            continue  # F1/F2: UNKNOWN, memory NOT updated
        label = _state_of(prev, s, d, cfg)
        memory[name] = label
        out.append(_mk(label, s, ts, "OK"))
    return out


def apply_freshness(rs, now_ns):
    """F4: expire to UNKNOWN when computed_at is older than 3x cadence."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > 3 * CADENCE_NS:
        rs = dict(rs)
        rs["module_state"] = "UNKNOWN"
        rs["state"] = "UNKNOWN"
    return rs


def apply_cost_adjustment(state_label, cost_bps):
    """Cost interface §Cost-interface: scale the strategy's
    expected_cost_bps components by the regime's adjustment record."""
    adj = COST_ADJUSTMENT_R043[state_label]
    out = dict(cost_bps)
    out["spread_bps"] = cost_bps["spread_bps"] * adj["spread_mult"]
    out["impact_bps"] = cost_bps["impact_bps"] * adj["impact_mult"]
    out["borrow_bps"] = cost_bps["borrow_bps"] * adj["borrow_mult"]
    out["fee_bps"] = cost_bps["fee_bps"] + adj["fee_add_bps"]
    return out


def _load(name):
    p = os.path.join(os.path.dirname(__file__), "..", "fixtures", name)
    with open(p) as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def _close(a, b, tol):
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return abs(a - b) <= tol


def _evt(ts, name, s, d, market_state="CONTINUOUS_TRADING"):
    return {"ts_ns": str(ts), "name": name, "short_pct_float": str(s),
            "days_to_cover": str(d), "market_state": market_state}


def test_fixture_replay():
    tape = _load("R043_tape.csv")
    exp = _load("R043_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R043_tape.csv")).readline()
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
    tape = _load("R043_tape.csv")
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
    tape = _load("R043_tape.csv")
    bad = [dict(r) for r in tape]
    bad[0]["days_to_cover"] = "nan"
    got = detect(None, bad, CFG)
    assert got[0]["module_state"] == "UNKNOWN", got[0]
    assert got[0]["state"] == "UNKNOWN"


def test_f2_negative_short_pct_unknown():
    evts = [_evt(1, "AAA", -0.01, 1.0)]
    got = detect(None, evts, CFG)
    assert got[0]["module_state"] == "UNKNOWN"


def test_f3_dual_estimator_agreement():
    """Entry-only dual re-derivation agrees with the hysteresis detector
    everywhere the hysteresis band is not engaged."""
    tape = _load("R043_tape.csv")
    got = detect(None, tape, CFG)
    for e, g in zip(tape, got):
        if g["module_state"] != "OK":
            continue
        s, d = _row_value(e)
        dual = _dual_state_of(s, d, CFG)
        # hysteresis can only *raise* the label, never lower it
        rank = {"NORMAL": 0, "CROWDED": 1, "SQUEEZE_WATCH": 2}
        assert rank[g["state"]] >= rank[dual], (e, g["state"], dual)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R043_tape.csv")
    rs = detect(None, tape, CFG)[0]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]
    # boundary: exactly 3x cadence is still fresh (strict >)
    edge = apply_freshness(rs, rs["computed_at"] + 3 * CADENCE_NS)
    assert edge["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R043_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_hysteresis_entry_exit_boundaries():
    """Exact band edges: entry at the band, hold at the exit band, drop below."""
    t = 1000
    # from NORMAL: 0.12 enters CROWDED; 0.1199 does not
    assert detect(None, [_evt(t, "N1", 0.12, 1.0)], CFG)[0]["state"] == "CROWDED"
    assert detect(None, [_evt(t, "N2", 0.1199, 1.0)], CFG)[0]["state"] == "NORMAL"
    # from CROWDED: 0.09 holds, 0.089 exits
    seq = [_evt(t, "N3", 0.13, 1.0), _evt(t + 1, "N3", 0.09, 1.0)]
    assert [r["state"] for r in detect(None, seq, CFG)] == ["CROWDED", "CROWDED"]
    seq = [_evt(t, "N4", 0.13, 1.0), _evt(t + 1, "N4", 0.089, 1.0)]
    assert [r["state"] for r in detect(None, seq, CFG)] == ["CROWDED", "NORMAL"]
    # squeeze: 0.25 enters; hold at 0.22; 0.219 drops to CROWDED
    assert detect(None, [_evt(t, "N5", 0.25, 1.0)], CFG)[0]["state"] == "SQUEEZE_WATCH"
    seq = [_evt(t, "N6", 0.26, 1.0), _evt(t + 1, "N6", 0.22, 1.0),
           _evt(t + 2, "N6", 0.219, 1.0)]
    assert [r["state"] for r in detect(None, seq, CFG)] == [
        "SQUEEZE_WATCH", "SQUEEZE_WATCH", "CROWDED"]
    # DTC: 5.0 enters CROWDED via the DTC leg; hold at 4.0; 3.9 exits
    assert detect(None, [_evt(t, "N7", 0.05, 5.0)], CFG)[0]["state"] == "CROWDED"
    seq = [_evt(t, "N8", 0.05, 6.0), _evt(t + 1, "N8", 0.05, 4.0),
           _evt(t + 2, "N8", 0.05, 3.9)]
    assert [r["state"] for r in detect(None, seq, CFG)] == [
        "CROWDED", "CROWDED", "NORMAL"]


def test_hysteresis_memory_survives_unknown_print():
    """A bad print emits UNKNOWN but does not reset the hysteresis memory."""
    t = 1000
    seq = [_evt(t, "M1", 0.13, 1.0), _evt(t + 1, "M1", float("nan"), 1.0),
           _evt(t + 2, "M1", 0.10, 1.0)]
    got = detect(None, seq, CFG)
    assert [r["state"] for r in got] == ["CROWDED", "UNKNOWN", "CROWDED"]
    assert got[1]["module_state"] == "UNKNOWN"


def test_halt_freezes_preserves_memory():
    """HALTED events emit UNKNOWN and freeze the label memory (F-state)."""
    t = 1000
    seq = [_evt(t, "H1", 0.26, 1.0), _evt(t + 1, "H1", 0.26, 1.0, "HALTED"),
           _evt(t + 2, "H1", 0.23, 1.0)]
    got = detect(None, seq, CFG)
    assert [r["state"] for r in got] == [
        "SQUEEZE_WATCH", "UNKNOWN", "SQUEEZE_WATCH"]
    assert got[1]["module_state"] == "UNKNOWN"


def test_value_is_short_pct():
    tape = _load("R043_tape.csv")
    got = detect(None, tape, CFG)
    for e, g in zip(tape, got):
        if g["module_state"] == "OK":
            assert _close(g["value"], float(e["short_pct_float"]), TOL)


def test_cost_interface_record():
    """§Cost-interface: adjustment record values and application rule."""
    rec = COST_ADJUSTMENT_R043
    assert rec["regime_id"] == "R043" and rec["version"] == "1.1.0"
    assert set(rec) >= {"SQUEEZE_WATCH", "CROWDED", "NORMAL", "UNKNOWN"}
    for st, adj in rec.items():
        if st in ("regime_id", "version"):
            continue
        assert set(adj) == {"spread_mult", "impact_mult", "borrow_mult",
                            "fee_add_bps", "tag"}
        assert adj["tag"] in ("[example]", "[default]")
    base = {"spread_bps": 2.0, "impact_bps": 3.0, "borrow_bps": 10.0,
            "fee_bps": 0.5}
    sw = apply_cost_adjustment("SQUEEZE_WATCH", base)
    assert _close(sw["borrow_bps"], 50.0, TOL)
    assert _close(sw["spread_bps"], 3.0, TOL)
    assert _close(sw["impact_bps"], 6.0, TOL)
    assert _close(sw["fee_bps"], 0.5, TOL)
    n = apply_cost_adjustment("NORMAL", base)
    assert n == base  # identity [default]
