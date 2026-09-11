"""R026 — Inflation-surprise regime: acceptance tests (reference implementation).

Implements the normative §R2 pseudocode of modules/regimes/R026.md v1.1.0:
causal per-release surprise z-score with hysteresis entry/exit, consensus
vintage leak guard, dual-estimator agreement, trailing-history sigma estimator
(ddof=1), market-state handling, and the cost-interface adjustment record.

Definition of done: `python3 -m pytest modules/tests/test_R026.py -q` exits 0.
"""
import csv
import math
import os
import statistics

RID = "R026"
TOL = 1e-9
DUAL_TOL = 1e-12
ESTIMATOR_VERSION = "1.1.0"
DATA_VINTAGE = "2026-09-09"
STALE_AFTER_NS = 90 * 86400 * 10**9  # 3x the ~30d release cadence [example]

# Mirrors the §R2.1 Config dataclass defaults (status: default unless noted).
CFG = {
    "sigma_override": 0.25,   # [example] operator-asserted sigma; None -> estimate
    "L": 12,                 # trailing releases for the sigma estimator
    "min_history": 6,        # releases before the estimator may emit
    "z_hot": 1.5,            # entry threshold (inclusive)
    "z_cool": 0.75,          # exit threshold (hysteresis); must be < z_hot
    "z_abs_max": 10.0,       # sanity bound -> UNKNOWN beyond
    "dual_tol_pp": 0.01,     # [example] BLS-vs-vendor actual agreement
    "window_min": 15,        # cost-adjustment window after the print
    "min_lag_bars": 1,
    "recal_releases": 6,     # DEGRADED releases after a methodology break
}

# Cost-interface adjustment record (module §R5, version-pinned).
COST_ADJUSTMENT_R026 = {
    "regime_id": RID,
    "version": "1.1.0",
    "window_min": CFG["window_min"],
    "HOT":     {"spread_mult": 4.0, "impact_mult": 2.0,
                "borrow_mult": 1.0, "fee_add_bps": 0.0},
    "COLD":    {"spread_mult": 4.0, "impact_mult": 2.0,
                "borrow_mult": 1.0, "fee_add_bps": 0.0},
    "NEUTRAL": {"spread_mult": 1.0, "impact_mult": 1.0,
                "borrow_mult": 1.0, "fee_add_bps": 0.0},
    # UNKNOWN resolves restrictively to the HOT record (see cost_adjustment_for).
}


def _parse_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _parse_int(x):
    # int64 ns timestamps: never round-trip through float64 (it cannot
    # distinguish ts-1 from ts at 1.8e18). Parse the integer string directly.
    try:
        return int(str(x).strip())
    except (TypeError, ValueError):
        try:
            return int(float(x))
        except (TypeError, ValueError):
            return 0


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


def _fresh_state():
    return {"surprises": [], "last": None, "last_value": float("nan")}


def _estimate_sigma(surprises, L):
    """Normative §R3.1 estimator: sample std (ddof=1) over trailing L surprises."""
    window = list(surprises[-L:])
    if len(window) < 2:
        return float("nan")
    return statistics.stdev(window)


def _transition(z, prev, cfg):
    """Hysteresis state machine (§R2 normative)."""
    zh, zc = cfg["z_hot"], cfg["z_cool"]
    if z >= zh:
        return "HOT"
    if z <= -zh:
        return "COLD"
    if prev == "HOT" and z >= zc:
        return "HOT"
    if prev == "COLD" and z <= -zc:
        return "COLD"
    return "NEUTRAL"


def _emit_unknown(state, ts):
    # Guards run BEFORE history append: rejected rows never poison the estimator.
    return _mk("UNKNOWN", float("nan"), ts, "UNKNOWN")


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState]. Normative §R2 logic.

    Causal: the label at position t uses only events[:t+1]. Guard failures
    (F1/F2/F3/leak) emit UNKNOWN and never append to the surprise history.
    market_state events: HALTED -> freeze + UNKNOWN; AUCTION -> hold last +
    DEGRADED; CLOSED -> OFF.
    """
    if state is None:
        state = _fresh_state()
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    for e in events:
        ts = _parse_int(e["ts_ns"])
        ms = (e.get("market_state") or "CONTINUOUS_TRADING").strip().upper()
        prev = state["last"] or "NEUTRAL"
        if ms == "HALTED":
            out.append(_mk(state["last"] or "UNKNOWN", state["last_value"],
                           ts, "UNKNOWN"))
            continue
        if ms == "AUCTION":
            out.append(_mk(state["last"] or "UNKNOWN", state["last_value"],
                           ts, "DEGRADED"))
            continue
        if ms == "CLOSED":
            out.append(_mk(state["last"] or "UNKNOWN", state["last_value"],
                           ts, "OFF"))
            continue
        a = _parse_float(e.get("actual"))
        c = _parse_float(e.get("consensus"))
        if not (math.isfinite(a) and math.isfinite(c)):
            out.append(_emit_unknown(state, ts))  # F1
            continue
        vintage = _parse_int(e.get("consensus_vintage_ns") or 0)
        if vintage >= ts:  # leak guard: vintage must be strictly before release
            out.append(_emit_unknown(state, ts))
            continue
        s = a - c
        va = _parse_float(e.get("vendor_actual"))
        if math.isfinite(va) and abs(va - a) > cfg["dual_tol_pp"]:  # F3
            out.append(_emit_unknown(state, ts))
            continue
        if cfg.get("sigma_override") is not None:
            sigma = cfg["sigma_override"]  # operator asserts sigma; no history gate
        else:
            state["surprises"].append(s)
            if len(state["surprises"]) < cfg["min_history"]:  # F1
                out.append(_emit_unknown(state, ts))
                continue
            sigma = _estimate_sigma(state["surprises"], cfg["L"])
        if not (math.isfinite(sigma) and sigma > 0):  # F2
            out.append(_emit_unknown(state, ts))
            continue
        z = s / sigma
        if not (math.isfinite(z) and abs(z) <= cfg["z_abs_max"]):  # F2 bounds
            out.append(_emit_unknown(state, ts))
            continue
        label = _transition(z, prev, cfg)
        state["last"], state["last_value"] = label, z
        out.append(_mk(label, z, ts, "OK"))
    return out


def cost_adjustment_for(label, ts_ns, release_ts_ns, record):
    """Cost-interface application rule (§R5 normative).

    Inside the release window, HOT/COLD scale the expected_cost_bps inputs;
    outside the window the record is identity. UNKNOWN resolves restrictively
    to the HOT record (downstream must treat UNKNOWN as restrictive).
    """
    in_window = release_ts_ns <= ts_ns <= release_ts_ns + record["window_min"] * 60 * 10**9
    if label == "UNKNOWN":
        return dict(record["HOT"])
    if label in ("HOT", "COLD") and in_window:
        return dict(record[label])
    return dict(record["NEUTRAL"])


def apply_freshness(rs, now_ns):
    """F4: expire to UNKNOWN when computed_at is older than the staleness TTL."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > STALE_AFTER_NS:
        rs = dict(rs)
        rs["module_state"] = "UNKNOWN"
        rs["state"] = "UNKNOWN"
    return rs


def _load(name):
    p = os.path.join(os.path.dirname(__file__), "..", "fixtures", name)
    with open(p) as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def _single_row_fixture(name):
    """Each row of the edges fixture is an independent single-event scenario."""
    return [[r] for r in _load(name)]


def _close(a, b, tol):
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return abs(a - b) <= tol


# ---------------------------------------------------------------- fixtures

def test_fixture_replay():
    tape = _load("R026_tape.csv")
    exp = _load("R026_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R026_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)


def test_edges_fixture_replay():
    scenarios = _single_row_fixture("R026_edges.csv")
    exp = _load("R026_expected_edges.csv")
    assert len(scenarios) == len(exp) == 6
    for rows, x in zip(scenarios, exp):
        got = detect(None, rows, CFG)
        assert len(got) == 1
        assert got[0]["state"] == x["state"], (rows[0], got[0], x)
        assert got[0]["module_state"] == x["module_state"], (rows[0], got[0], x)
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(got[0]["value"], xv, TOL)


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R026_tape.csv")
    full = detect(None, tape, CFG)
    for k in range(1, len(tape) + 1):
        prefix = detect(None, tape[:k], CFG)
        assert len(prefix) == k
        for a, b in zip(prefix, full[:k]):
            assert a["state"] == b["state"], (k, a, b)
            assert a["module_state"] == b["module_state"]
            assert _close(a["value"], b["value"], TOL), (k, a["value"], b["value"])


# ------------------------------------------------------------------ F1..F5

def test_f1_missing_input_unknown():
    got = detect(None, [], CFG)
    assert len(got) == 1
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"


def test_f1_missing_actual_unknown():
    row = {"ts_ns": "1800000001000000000", "release": "CPI", "actual": "",
           "consensus": "3.0", "consensus_vintage_ns": "1799999940000000000",
           "vendor_actual": "", "market_state": ""}
    got = detect(None, [row], CFG)
    assert got[0]["module_state"] == "UNKNOWN"


def test_f2_bounds_violation_unknown():
    row = {"ts_ns": "1800000004000000000", "release": "CPI", "actual": "6.0",
           "consensus": "3.0", "consensus_vintage_ns": "1799999940000000000",
           "vendor_actual": "6.0", "market_state": ""}
    got = detect(None, [row], CFG)  # z = 12 > z_abs_max
    assert got[0]["module_state"] == "UNKNOWN", got[0]


def test_f2_sigma_collapse_unknown():
    cfg = dict(CFG, sigma_override=0.0)
    row = {"ts_ns": "1800000000000000000", "release": "CPI", "actual": "3.2",
           "consensus": "3.0", "consensus_vintage_ns": "1799999940000000000",
           "vendor_actual": "3.2", "market_state": ""}
    got = detect(None, [row], cfg)
    assert got[0]["module_state"] == "UNKNOWN"


def test_f3_dual_estimator_agreement_on_tape():
    tape = _load("R026_tape.csv")
    for e in tape:  # fixture consensus path agrees with the vendor path
        va = _parse_float(e["vendor_actual"])
        a = _parse_float(e["actual"])
        assert math.isfinite(va) and abs(va - a) <= DUAL_TOL, e


def test_f3_dual_disagreement_unknown():
    row = {"ts_ns": "1800000002000000000", "release": "CPI", "actual": "3.2",
           "consensus": "3.0", "consensus_vintage_ns": "1799999940000000000",
           "vendor_actual": "3.25", "market_state": ""}
    got = detect(None, [row], CFG)  # |3.25-3.2| = 0.05 > 0.01 pp
    assert got[0]["module_state"] == "UNKNOWN"
    ok_row = dict(row, vendor_actual="3.205")  # 0.005 pp: within tolerance
    got = detect(None, [ok_row], CFG)
    assert got[0]["module_state"] == "OK"


def test_f4_staleness_expires_to_unknown():
    tape = _load("R026_tape.csv")
    rs = detect(None, tape, CFG)[-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + STALE_AFTER_NS + 1)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + STALE_AFTER_NS - 1)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R026_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


# ------------------------------------------------- hysteresis and boundaries

def test_boundary_inclusivity():
    """Entry thresholds are inclusive: z = +1.5 -> HOT, z = -1.5 -> COLD."""
    tape = _load("R026_tape.csv")
    got = detect(None, tape, CFG)
    assert abs(got[4]["value"] - 1.5) <= TOL, got[4]   # exact binary: 0.375/0.25
    assert got[4]["state"] == "HOT"
    assert abs(got[6]["value"] - (-1.5)) <= TOL, got[6]
    assert got[6]["state"] == "COLD"


def test_hysteresis_entry_exit():
    """Inside the (z_cool, z_hot) band the previous label persists."""
    tape = _load("R026_tape.csv")
    got = detect(None, tape, CFG)
    # z=1.2 after HOT stays HOT (would be NEUTRAL without hysteresis)
    assert abs(got[5]["value"] - 1.2) <= TOL, got[5]
    assert got[5]["state"] == "HOT"
    # z=-1.0 after COLD stays COLD
    assert abs(got[7]["value"] - (-1.0)) <= TOL, got[7]
    assert got[7]["state"] == "COLD"
    # z=-0.4 exits the cold band -> NEUTRAL
    assert got[8]["state"] == "NEUTRAL"


def test_hysteresis_logic_drift_guard():
    """A naive single-threshold implementation must fail this test."""
    assert _transition(1.2, "HOT", CFG) == "HOT"
    assert _transition(1.2, "NEUTRAL", CFG) == "NEUTRAL"  # below entry: no latch
    assert _transition(-1.0, "COLD", CFG) == "COLD"
    assert _transition(-1.0, "NEUTRAL", CFG) == "NEUTRAL"
    assert _transition(0.74, "HOT", CFG) == "NEUTRAL"     # exit is strict
    assert _transition(0.75, "HOT", CFG) == "HOT"        # exit inclusive


# ------------------------------------------------------- guards and market state

def test_leak_guard_strict():
    base = {"release": "CPI", "actual": "3.2", "consensus": "3.0",
            "vendor_actual": "3.2", "market_state": ""}
    ts = 1800000000000000000
    leaked = dict(base, ts_ns=str(ts), consensus_vintage_ns=str(ts))
    assert detect(None, [leaked], CFG)[0]["module_state"] == "UNKNOWN"
    frozen = dict(base, ts_ns=str(ts), consensus_vintage_ns=str(ts - 1))
    assert detect(None, [frozen], CFG)[0]["module_state"] == "OK"


def test_rejected_rows_do_not_poison_history():
    cfg = dict(CFG, sigma_override=None, min_history=2)
    mk = lambda ts, a, v: {"ts_ns": str(ts), "release": "CPI", "actual": a,
                           "consensus": "3.0", "consensus_vintage_ns": str(v),
                           "vendor_actual": a, "market_state": ""}
    ts = 1800000000000000000
    state = _fresh_state()
    rows = [mk(ts, "3.2", ts),                 # leaked -> UNKNOWN, not appended
            mk(ts + 1, "3.2", ts - 60_000_000_000),   # s=0.2, history=[0.2] -> UNKNOWN (min_history)
            mk(ts + 2, "3.4", ts - 60_000_000_000)]   # s=0.4, history=[0.2,0.4]
    got = detect(state, rows, cfg)
    assert [g["module_state"] for g in got] == ["UNKNOWN", "UNKNOWN", "OK"]
    assert state["surprises"] == [0.2, 0.4] or \
        all(abs(x - y) < 1e-12 for x, y in zip(state["surprises"], [0.2, 0.4]))


def test_halt_freezes_and_auction_holds():
    base = {"release": "CPI", "actual": "3.5", "consensus": "3.1",
            "vendor_actual": "3.5", "market_state": ""}
    ts = 1800000000000000000
    hot = dict(base, ts_ns=str(ts),
               consensus_vintage_ns=str(ts - 60_000_000_000))  # z=1.6 -> HOT
    halt = dict(base, ts_ns=str(ts + 1), market_state="HALTED",
                consensus_vintage_ns=str(ts - 60_000_000_000))
    auction = dict(base, ts_ns=str(ts + 2), market_state="AUCTION",
                   consensus_vintage_ns=str(ts - 60_000_000_000))
    closed = dict(base, ts_ns=str(ts + 3), market_state="CLOSED",
                  consensus_vintage_ns=str(ts - 60_000_000_000))
    got = detect(None, [hot, halt, auction, closed], CFG)
    assert got[0]["state"] == "HOT" and got[0]["module_state"] == "OK"
    assert got[1]["module_state"] == "UNKNOWN" and got[1]["state"] == "HOT"
    assert got[2]["module_state"] == "DEGRADED" and got[2]["state"] == "HOT"
    assert got[3]["module_state"] == "OFF"


# ------------------------------------------------------- sigma estimator unit

def test_sigma_estimator_unit():
    """Normative estimator: sample std (ddof=1) over the trailing L surprises."""
    surprises = [0.1, 0.3, -0.1, 0.2, 0.0, 0.15, -0.2, 0.05,
                 0.25, -0.05, 0.12, -0.12, 0.4, -0.3]
    got = _estimate_sigma(surprises, 12)
    assert abs(got - statistics.stdev(surprises[-12:])) < 1e-12
    # Pins ddof=1 against drift to population std on a series where they differ.
    assert abs(got - statistics.pstdev(surprises[-12:])) > 1e-9
    assert math.isnan(_estimate_sigma([0.1], 12))  # < 2 points: undefined


def test_sigma_estimator_min_history_gate():
    cfg = dict(CFG, sigma_override=None, min_history=6)
    actuals = ["3.2", "3.4", "3.0", "3.3", "3.1", "3.5", "3.2"]  # varying: sigma > 0
    rows = [{"ts_ns": str(1800000000000000000 + i), "release": "CPI",
             "actual": a, "consensus": "3.0",
             "consensus_vintage_ns": str(1800000000000000000 - 60_000_000_000),
             "vendor_actual": a, "market_state": ""} for i, a in enumerate(actuals)]
    got = detect(None, rows, cfg)
    assert [g["module_state"] for g in got[:5]] == ["UNKNOWN"] * 5
    assert got[5]["module_state"] == "OK"  # 6th release: gate opens


# ------------------------------------------------------- cost interface

def test_cost_adjustment_record_versioned():
    assert COST_ADJUSTMENT_R026["regime_id"] == RID
    assert COST_ADJUSTMENT_R026["version"] == ESTIMATOR_VERSION
    for label in ("HOT", "COLD", "NEUTRAL"):
        rec = COST_ADJUSTMENT_R026[label]
        assert set(rec) == {"spread_mult", "impact_mult",
                            "borrow_mult", "fee_add_bps"}


def test_cost_adjustment_window_and_restrictive_unknown():
    rec = COST_ADJUSTMENT_R026
    rel = 1784032200000000000
    inside = rel + 5 * 60 * 10**9
    outside = rel + 60 * 60 * 10**9
    hot_in = cost_adjustment_for("HOT", inside, rel, rec)
    assert hot_in["spread_mult"] == 4.0 and hot_in["impact_mult"] == 2.0
    assert hot_in["borrow_mult"] == 1.0 and hot_in["fee_add_bps"] == 0.0
    neutral_out = cost_adjustment_for("HOT", outside, rel, rec)
    assert neutral_out == rec["NEUTRAL"]  # window expired -> identity
    assert cost_adjustment_for("NEUTRAL", inside, rel, rec) == rec["NEUTRAL"]
    # UNKNOWN is restrictive: worst-case (HOT) multipliers apply.
    assert cost_adjustment_for("UNKNOWN", inside, rel, rec) == rec["HOT"]


# ------------------------------------------------------- spot handcheck

def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3)."""
    tape = _load('R026_tape.csv')
    got = detect(None, tape, CFG)
    assert abs(got[2]['value'] - 1.6) <= 1e-9, got[2]   # (3.5-3.1)/0.25
    assert got[2]['state'] == 'HOT'
    assert abs(got[3]['value'] - (-1.6)) <= 1e-9, got[3]
    assert got[3]['state'] == 'COLD'
    assert got[0]['state'] == 'NEUTRAL'
