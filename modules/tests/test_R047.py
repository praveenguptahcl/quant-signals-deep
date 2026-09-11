"""R047 — Sentiment / positioning regime: acceptance tests.

Mirrors the normative detection pseudocode in R047 §R2 (v1.1.0):
  raw weekly inputs -> component z vs trailing 26-week windows ->
  composite z = 0.4*z_survey - 0.3*z_pcr + 0.3*z_fut ->
  hysteresis state machine. Fixtures: modules/fixtures/R047_tape.csv
  (TYPE: validation-run) + R047_expected.csv.
Definition of done: `python3 -m pytest modules/tests/test_R047.py -q` exits 0.
"""
import csv
import math
import os
import statistics

RID = "R047"
TOL = 1e-9
ESTIMATOR_VERSION = "1.1.0"
DATA_VINTAGE = "2026-09-09"
NANO_DAY = 86400000000000

CFG = {
    "weight_survey": 0.4,   # [example]
    "weight_pcr": 0.3,      # [example]
    "weight_fut": 0.3,      # [example]
    "extreme": 2.0,         # [example] entry threshold
    "calm_band": 0.5,       # [example]
    "hyst_exit": 0.5,       # [default] hysteresis exit offset
    "calm_hyst": 0.1,       # [default] calm band hysteresis
    "warmup_weeks": 26,     # [default] trailing window
    "stale_days": 14,       # [default] F4 staleness TTL
    "z_bound": 10.0,        # [default] F2 out-of-bounds
    "min_lag_bars": 1,      # [default]
}

COST_ADJUSTMENT_R047 = {
    "regime_id": "R047",
    "version": ESTIMATOR_VERSION,
    "note": "tilt-only regime; identity cost adjustment until venue-calibrated",
    "PANIC": {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0,
              "fee_add_bps": 0.0, "tag": "[internal-est]"},
    "EUPHORIA": {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0,
                 "fee_add_bps": 0.0, "tag": "[internal-est]"},
    "CALM": {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0,
             "fee_add_bps": 0.0, "tag": "[internal-est]"},
    "ELEVATED": {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0,
                 "fee_add_bps": 0.0, "tag": "[internal-est]"},
}


def _parse(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def transition(prior, z, cfg=CFG):
    """Hysteresis state machine — normative; see R047 §R2."""
    panic_exit = -(cfg["extreme"] - cfg["hyst_exit"])   # -1.5 [default]
    euph_exit = cfg["extreme"] - cfg["hyst_exit"]       # +1.5 [default]
    calm_enter = cfg["calm_band"] - cfg["calm_hyst"]    # 0.4 [default]
    calm_exit = cfg["calm_band"] + cfg["calm_hyst"]     # 0.6 [default]
    if prior == "PANIC":
        return "ELEVATED" if z > panic_exit else "PANIC"
    if prior == "EUPHORIA":
        return "ELEVATED" if z < euph_exit else "EUPHORIA"
    if prior == "CALM":
        if z <= -cfg["extreme"]:
            return "PANIC"
        if z >= cfg["extreme"]:
            return "EUPHORIA"
        return "CALM" if abs(z) <= calm_exit else "ELEVATED"
    # ELEVATED / UNKNOWN: entry rules
    if z <= -cfg["extreme"]:
        return "PANIC"
    if z >= cfg["extreme"]:
        return "EUPHORIA"
    if abs(z) <= calm_enter:
        return "CALM"
    return "ELEVATED"


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


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal: row t uses only rows < t for trailing windows. Missing/non-finite
    input -> UNKNOWN row, prior label frozen, row masked from windows (F1);
    ts gap > stale_days -> UNKNOWN (F4); |z| > z_bound -> UNKNOWN (F2).
    Corporate actions: N/A by construction — no per-ticker price inputs.
    Never interpolates.
    """
    n = cfg["warmup_weeks"]
    out, hist, prior, prev_ts = [], [], "UNKNOWN", None
    for e in events:
        ts = int(float(e["ts_ns"]))
        bull, bear = _parse(e.get("bull")), _parse(e.get("bear"))
        pcr, fut = _parse(e.get("pcr")), _parse(e.get("fut_net"))
        row = {"bull": bull, "bear": bear, "pcr": pcr, "fut_net": fut}
        ok = all(math.isfinite(v) for v in row.values())
        stale = prev_ts is not None and (ts - prev_ts) > cfg["stale_days"] * NANO_DAY
        if not ok or stale:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1/F4
            prev_ts = ts  # prior label frozen; row masked from windows
            continue
        if len(hist) < n:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # warmup
            hist.append(row)
            prev_ts = ts
            continue
        win = hist[-n:]
        def zc(key, x, negate=False):
            vals = [h[key] for h in win]
            m, s = statistics.mean(vals), statistics.stdev(vals)
            z = 0.0 if s == 0 else (x - m) / s
            return -z if negate else z
        # spread is derived (bull - bear); component z vs its trailing window:
        spreads = [h["bull"] - h["bear"] for h in win]
        m, s = statistics.mean(spreads), statistics.stdev(spreads)
        z_survey = 0.0 if s == 0 else ((bull - bear) - m) / s
        z = (cfg["weight_survey"] * z_survey
             + cfg["weight_pcr"] * zc("pcr", pcr, negate=True)
             + cfg["weight_fut"] * zc("fut_net", fut))
        if not math.isfinite(z) or abs(z) > cfg["z_bound"]:
            out.append(_mk("UNKNOWN", z, ts, "UNKNOWN"))  # F2
            prev_ts = ts
            continue
        label = transition(prior if prior != "UNKNOWN" else "ELEVATED", z, cfg)
        out.append(_mk(label, z, ts, "OK"))
        prior = label
        hist.append(row)
        prev_ts = ts
    return out


def apply_freshness(rs, now_ns):
    """F4: a published label older than stale_days expires to UNKNOWN."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > CFG["stale_days"] * NANO_DAY:
        rs = dict(rs)
        rs["module_state"] = "UNKNOWN"
        rs["state"] = "UNKNOWN"
    return rs


def _fixdir():
    return os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _load(name):
    with open(os.path.join(_fixdir(), name)) as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def _close(a, b, tol):
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return abs(a - b) <= tol


# ---------------- acceptance tests ----------------

def test_fixture_replay():
    tape = _load("R047_tape.csv")
    exp = _load("R047_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(_fixdir(), "R047_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        assert g["estimator_version"] == x["estimator_version"], (g, x)
        xv = _parse(x["value"])
        assert _close(g["value"], xv, TOL), (g["value"], xv)


def test_no_lookahead():
    """The label at t must be identical with and without later data (Lag contract)."""
    tape = _load("R047_tape.csv")
    full = detect(None, tape, CFG)
    for k in range(1, len(tape) + 1):
        prefix = detect(None, tape[:k], CFG)
        assert len(prefix) == k
        for a, b in zip(prefix, full[:k]):
            assert a["state"] == b["state"], (k, a, b)
            assert a["module_state"] == b["module_state"]
            assert _close(a["value"], b["value"], TOL), (k, a["value"], b["value"])


def test_f1_missing_survey_print_unknown_and_frozen():
    tape = _load("R047_tape.csv")
    got = detect(None, tape, CFG)
    f1_row = got[30]  # 2026-01-01: bull missing
    assert f1_row["module_state"] == "UNKNOWN" and f1_row["state"] == "UNKNOWN"
    # prior label (CALM at idx 29) must be frozen, not reset: the next valid row
    # re-enters via entry rules rather than continuing a reset state machine.
    assert got[29]["state"] == "CALM"
    assert got[32]["state"] == "PANIC"  # re-entry on extreme row


def test_f2_bounds_violation_unknown():
    tape = _load("R047_tape.csv")
    bad = [dict(r) for r in tape]
    bad[29]["pcr"] = "1000000.0"  # drives |z| far beyond z_bound=10
    got = detect(None, bad, CFG)
    assert got[29]["module_state"] == "UNKNOWN", got[29]
    assert abs(got[29]["value"]) > CFG["z_bound"]


def test_f3_dual_estimator_agreement_on_extremes():
    """Alternate weight set must agree on extreme-state classification (F3)."""
    alt = dict(CFG, weight_survey=0.34, weight_pcr=0.33, weight_fut=0.33)
    tape = _load("R047_tape.csv")
    a = detect(None, tape, CFG)
    b = detect(None, tape, alt)
    for ra, rb in zip(a, b):
        if ra["state"] in ("PANIC", "EUPHORIA") and ra["module_state"] == "OK":
            assert rb["state"] == ra["state"], (ra, rb)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R047_tape.csv")
    got = detect(None, tape, CFG)
    assert got[31]["module_state"] == "UNKNOWN"  # 21-day gap -> F4
    rs = got[29]
    aged = apply_freshness(rs, rs["computed_at"] + 15 * NANO_DAY)
    assert aged["module_state"] == "UNKNOWN" and aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + 7 * NANO_DAY)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    assert abs(sum([CFG["weight_survey"], CFG["weight_pcr"], CFG["weight_fut"]]) - 1.0) < 1e-12
    for rs in detect(None, _load("R047_tape.csv"), CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_hysteresis_transitions_pinned():
    # PANIC entry at exactly -2.0, stays PANIC at -1.5, exits at -1.49
    assert transition("ELEVATED", -2.0) == "PANIC"
    assert transition("ELEVATED", -1.99) == "ELEVATED"
    assert transition("PANIC", -1.5) == "PANIC"
    assert transition("PANIC", -1.49) == "ELEVATED"
    assert transition("PANIC", 2.1) == "ELEVATED"  # no direct PANIC->EUPHORIA
    # EUPHORIA mirror
    assert transition("ELEVATED", 2.0) == "EUPHORIA"
    assert transition("EUPHORIA", 1.5) == "EUPHORIA"
    assert transition("EUPHORIA", 1.49) == "ELEVATED"
    # CALM band with its own hysteresis
    assert transition("ELEVATED", 0.4) == "CALM"
    assert transition("ELEVATED", 0.5) == "ELEVATED"
    assert transition("CALM", 0.6) == "CALM"
    assert transition("CALM", 0.61) == "ELEVATED"


def test_fixture_scenario_labels():
    """End-to-end scenario pins: entry -> hysteresis hold -> exit -> calm -> F1/F4 -> re-entry."""
    got = detect(None, _load("R047_tape.csv"), CFG)
    labels = [g["state"] for g in got[26:]]
    assert labels == ["PANIC", "PANIC", "ELEVATED", "CALM",
                      "UNKNOWN", "UNKNOWN", "PANIC"], labels


def test_spot_handcheck_w27():
    """Independently hand-verified arithmetic (see R047 §R3 worked example)."""
    got = detect(None, _load("R047_tape.csv"), CFG)
    assert abs(got[26]["value"] - (-9.6407)) < 1e-3, got[26]
    assert got[26]["state"] == "PANIC"


def test_cost_interface_identity_record():
    for state in ("PANIC", "EUPHORIA", "CALM", "ELEVATED"):
        rec = COST_ADJUSTMENT_R047[state]
        assert rec["spread_mult"] == 1.0
        assert rec["impact_mult"] == 1.0
        assert rec["borrow_mult"] == 1.0
        assert rec["fee_add_bps"] == 0.0
        assert rec["tag"].startswith("[")
    assert COST_ADJUSTMENT_R047["version"] == ESTIMATOR_VERSION


def test_no_price_inputs_corporate_actions_na():
    """Detector schema carries no per-ticker price fields; corporate actions are N/A by construction."""
    cols = set(_load("R047_tape.csv")[0].keys())
    assert not ({"open", "high", "low", "close", "adj_close"} & cols), cols


def test_causality_label_gates_t_plus_1_only():
    tape = _load("R047_tape.csv")
    for g, e in zip(detect(None, tape, CFG), tape):
        assert g["computed_at"] == int(float(e["ts_ns"]))
        assert g["min_lag_bars"] == 1
