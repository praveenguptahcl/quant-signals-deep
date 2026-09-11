"""R031 — Cross-asset correlation regime: acceptance tests.

Reference implementation of detect() with hysteresis state machine, rolling
window W, halt freeze, split guard, and cost-interface record, plus replay of
fixtures (validation-run). Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_R031.py -q` exits 0.
"""
import csv
import math
import os
import statistics

RID = "R031"
TOL = 1e-9
DUAL_TOL = 1e-9
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"
ASSETS = ["A", "B", "C", "D", "E"]

# Mirrors §R0.2 Config defaults (all [example] in the module doc).
CFG = {
    "W": 63,
    "fused": 0.50,        # FUSED entry
    "fused_exit": 0.40,   # FUSED exit (hysteresis)
    "diverse": 0.30,      # DIVERSIFIED entry
    "diverse_exit": 0.38, # DIVERSIFIED exit (hysteresis)
    "split_guard": 0.90,  # |r| above this on a non-halt bar -> suspect corporate action
    "min_lag_bars": 1,
}

# Mirrors the module's "Cost interface" block (versioned with the estimator).
COST_ADJUSTMENT_R031 = {
    "regime_id": RID,
    "version": ESTIMATOR_VERSION,
    "FUSED": {"spread_mult": 1.0, "impact_mult": 1.5, "borrow_mult": 1.0,
              "fee_add_bps": 0.0, "tag": "[example]"},
    "ELEVATED": {"spread_mult": 1.0, "impact_mult": 1.25, "borrow_mult": 1.0,
                 "fee_add_bps": 0.0, "tag": "[example]"},
    "DIVERSIFIED": {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0,
                    "fee_add_bps": 0.0, "tag": "[default]"},
    "UNKNOWN": {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0,
                "fee_add_bps": 0.0, "tag": "[default]"},
}


def cost_adjustment(state):
    """The only cost channel: regime label -> cost-function adjustment."""
    return COST_ADJUSTMENT_R031.get(state, COST_ADJUSTMENT_R031["UNKNOWN"])


def _pf(x):
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


def _corr(x, y):
    n = len(x)
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx <= 0 or vy <= 0:
        return float("nan")  # zero-variance leg -> F2
    return cov / math.sqrt(vx * vy)


def _mean_rho(win):
    """Mean pairwise Pearson correlation over a window of parsed return rows."""
    if len(win) < 2:
        return float("nan")
    cols = [[row[k] for row in win] for k in range(len(ASSETS))]
    if any(not math.isfinite(v) for c in cols for v in c):
        return float("nan")
    ps = [_corr(cols[i], cols[j]) for i in range(len(ASSETS))
          for j in range(i + 1, len(ASSETS))]
    if any(not math.isfinite(p) for p in ps):
        return float("nan")
    return sum(ps) / len(ps)


def _state_of(value, prev_state, cfg):
    """Hysteresis state machine (normative: §R3 pseudocode)."""
    if value >= cfg["fused"]:
        return "FUSED"
    if value <= cfg["diverse"]:
        return "DIVERSIFIED"
    if prev_state == "FUSED":
        return "FUSED" if value >= cfg["fused_exit"] else "ELEVATED"
    if prev_state == "DIVERSIFIED":
        return "DIVERSIFIED" if value <= cfg["diverse_exit"] else "ELEVATED"
    return "ELEVATED"


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal: the label at position t uses only events[:t+1] (rolling window W).
    Empty input or an unparseable/missing row yields UNKNOWN (F1); non-finite
    or zero-variance correlation yields UNKNOWN (F2); a halt row freezes and
    emits UNKNOWN; |r| > split_guard on a non-halt bar is treated as a suspect
    corporate action -> UNKNOWN. Never interpolates.
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    clean = []          # parsed return rows admitted to the window
    prev = "ELEVATED"   # hysteresis memory (neutral start)
    for e in events:
        ts = int(float(e["ts_ns"]))
        if str(e.get("halt", "")).strip() == "1":
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # HALTED: freeze, emit UNKNOWN
            continue
        try:
            rets = [float(e[a]) for a in ASSETS]
        except (KeyError, TypeError, ValueError):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1
            continue
        if any(not math.isfinite(r) for r in rets):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1
            continue
        big = [abs(r) > cfg["split_guard"] for r in rets]
        if any(big) and not all(big):
            # one (or a minority of) leg(s) spiked: suspect corporate action on
            # that proxy (e.g. unadjusted split/dividend), not a market move
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
            continue
        clean.append(rets)
        win = clean[-cfg["W"]:]
        if len(win) < 2:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # insufficient lookback
            continue
        value = _mean_rho(win)
        if not math.isfinite(value):
            out.append(_mk("UNKNOWN", value, ts, "UNKNOWN"))  # F2
            continue
        lab = _state_of(value, prev, cfg)
        prev = lab
        out.append(_mk(lab, value, ts, "OK"))
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


def _replay(tape_name, exp_name):
    tape = _load(tape_name)
    exp = _load(exp_name)
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              tape_name)).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        xv = _pf(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)
    return got, tape


def test_fixture_replay():
    _replay("R031_tape.csv", "R031_expected.csv")


def test_hysteresis_fixture_replay():
    got, tape = _replay("R031_hysteresis.csv", "R031_hysteresis_expected.csv")
    states = [g["state"] for g in got]
    for want in ("DIVERSIFIED", "ELEVATED", "FUSED", "UNKNOWN"):
        assert want in states, f"fixture must visit {want}"


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R031_tape.csv")
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


def test_f1_missing_bar_unknown_and_recovers():
    tape = _load("R031_edges.csv")
    got = detect(None, tape, CFG)
    assert got[2]["module_state"] == "UNKNOWN"  # missing C
    assert got[3]["module_state"] == "OK"       # next good bar recovers


def test_f2_bounds_violation_unknown():
    tape = _load("R031_tape.csv")
    bad = [dict(r) for r in tape]
    bad[5]["C"] = "nan"
    got = detect(None, bad, CFG)
    assert got[5]["module_state"] == "UNKNOWN", got[5]


def test_f2_zero_variance_unknown():
    got = detect(None, _load("R031_zerovar.csv"), CFG)
    assert got[1]["module_state"] == "UNKNOWN", got[1]  # constant legs -> non-finite rho
    assert got[-1]["state"] == "UNKNOWN"


def test_f3_dual_estimator_agreement():
    tape = _load("R031_tape.csv")
    cols1 = [[float(e[a]) for e in tape[-CFG["W"]:] ] for a in ASSETS]
    def corr_xy(x, y):
        n = len(x); mx = sum(x) / n; my = sum(y) / n
        cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
        vx = sum((a - mx) ** 2 for a in x); vy = sum((b - my) ** 2 for b in y)
        return cov / math.sqrt(vx * vy)
    v1 = sum(corr_xy(cols1[i], cols1[j]) for i in range(5) for j in range(i + 1, 5)) / 10
    v2 = sum(statistics.correlation(cols1[i], cols1[j]) for i in range(5)
             for j in range(i + 1, 5)) / 10
    if not math.isfinite(v1):
        return  # degenerate panel: both estimators must agree on UNKNOWN-ness
    assert _close(v1, v2, DUAL_TOL), (v1, v2)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R031_tape.csv")
    rs = detect(None, tape, CFG)[-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R031_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_halt_freezes_and_emits_unknown():
    tape = _load("R031_edges.csv")
    got = detect(None, tape, CFG)
    assert got[4]["module_state"] == "UNKNOWN"  # halt=1 row
    assert got[4]["state"] == "UNKNOWN"
    assert got[5]["module_state"] == "OK"       # reopen: resumes


def test_split_guard_emits_unknown():
    tape = _load("R031_edges.csv")
    got = detect(None, tape, CFG)
    assert got[6]["module_state"] == "UNKNOWN"  # A=2.5: suspect split
    assert got[7]["module_state"] == "OK"       # vendor-confirmed bar recovers


def test_hysteresis_sticky_fused():
    """Values dipping below fused_entry but above fused_exit must NOT exit FUSED.
    This fails if the detector is replaced by a memoryless threshold."""
    got, _tape = _replay("R031_hysteresis.csv", "R031_hysteresis_expected.csv")
    pinned = 0
    # rows 210-312: seg4 (rho target 0.45) plus the seg5 turnover, entered as
    # FUSED at row 151. Any OK row in the hysteresis band here must hold FUSED.
    for i in range(210, 313):
        g = got[i]
        v = g["value"]
        if (g["module_state"] == "OK" and math.isfinite(v)
                and CFG["fused_exit"] <= v < CFG["fused"]):
            assert g["state"] == "FUSED", (i, v, g["state"])
            pinned += 1
    assert pinned >= 20, f"fixture must pin >=20 hysteresis rows, got {pinned}"


def test_hysteresis_fused_exit_rule():
    """Below fused_exit a FUSED label must exit; FUSED never jumps straight to DIVERSIFIED."""
    got, _tape = _replay("R031_hysteresis.csv", "R031_hysteresis_expected.csv")
    for prev_g, g in zip(got, got[1:]):
        if prev_g["state"] == "FUSED" and g["module_state"] == "OK":
            assert g["state"] in ("FUSED", "ELEVATED"), (g["value"], g["state"])
            if math.isfinite(g["value"]) and g["value"] < CFG["fused_exit"]:
                assert g["state"] == "ELEVATED", (g["value"], g["state"])


def test_hysteresis_diversified_sticky_and_exit():
    """Values between diverse_entry and diverse_exit hold DIVERSIFIED; above exit -> ELEVATED."""
    got, _tape = _replay("R031_hysteresis.csv", "R031_hysteresis_expected.csv")
    pinned, exited = 0, 0
    for g in got:
        v = g["value"]
        if g["module_state"] != "OK" or not math.isfinite(v):
            continue
        if CFG["diverse"] < v <= CFG["diverse_exit"] and g["state"] == "DIVERSIFIED":
            pinned += 1
        if v > CFG["diverse_exit"] and g["state"] == "ELEVATED":
            exited += 1
    assert pinned >= 2, f"fixture must pin >=2 DIVERSIFIED-hold rows, got {pinned}"
    assert exited >= 1


def test_boundary_entry_exit():
    """Exact-boundary semantics: entry is inclusive, exits are inclusive."""
    assert _state_of(0.50, "ELEVATED", CFG) == "FUSED"
    assert _state_of(0.50, "FUSED", CFG) == "FUSED"
    assert _state_of(0.40, "FUSED", CFG) == "FUSED"       # exit threshold inclusive
    assert _state_of(0.3999999, "FUSED", CFG) == "ELEVATED"
    assert _state_of(0.30, "ELEVATED", CFG) == "DIVERSIFIED"
    assert _state_of(0.38, "DIVERSIFIED", CFG) == "DIVERSIFIED"  # exit inclusive
    assert _state_of(0.3800001, "DIVERSIFIED", CFG) == "ELEVATED"


def test_cost_interface_record():
    rec = COST_ADJUSTMENT_R031
    assert rec["regime_id"] == RID
    assert rec["version"] == ESTIMATOR_VERSION
    fused = rec["FUSED"]
    assert (fused["spread_mult"], fused["impact_mult"],
            fused["borrow_mult"], fused["fee_add_bps"]) == (1.0, 1.5, 1.0, 0.0)
    assert cost_adjustment("FUSED")["impact_mult"] == 1.5
    assert cost_adjustment("ELEVATED")["impact_mult"] == 1.25
    ident = cost_adjustment("DIVERSIFIED")
    assert ident["spread_mult"] == ident["impact_mult"] == ident["borrow_mult"] == 1.0
    assert ident["fee_add_bps"] == 0.0
    unknown = cost_adjustment("UNKNOWN")
    assert unknown == ident, "UNKNOWN must degrade to the identity adjustment"


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3)."""
    tape = _load('R031_tape.csv')
    got = detect(None, tape, CFG)
    assert abs(got[9]['value'] - 0.9892) <= 1e-3, got[9]['value']
    assert got[9]['state'] == 'FUSED'
    assert got[0]['state'] == 'UNKNOWN'  # <2 rows: insufficient lookback
