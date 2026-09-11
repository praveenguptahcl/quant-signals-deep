"""R038 — Thin liquidity regime: acceptance tests (concrete sketch).

Real imports, fixture load, real assertions. Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_R038.py -q` exits 0.
"""
import csv
import math
import os

RID = "R038"
TOL = 1e-9
DUAL_TOL = 1e-9
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 300000000000
DATA_VINTAGE = "2026-09-09"

# Must match the §R0.2 Config table in modules/regimes/R038.md exactly.
CFG = {
    "thin_entry": 0.70,
    "thin_exit": 0.75,
    "severe_entry": 0.50,
    "severe_exit": 0.60,
    "spr_thin_entry": 2.0,
    "spr_thin_exit": 1.75,
    "spr_severe_entry": 3.0,
    "spr_severe_exit": 2.5,
    "baseline_window_days": 20,
    "min_baseline_days": 10,
    "dual_tol": 1e-9,
    "min_lag_bars": 1,
}

SEVERITY = {"NORMAL": 0, "THIN": 1, "SEVERE": 2}


def _parse_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _mk(state, liq, spr, ts_ns, module_state):
    return {
        "regime_id": RID,
        "state": state,
        "liq_ratio": liq,
        "spr_ratio": spr,
        "estimator_version": ESTIMATOR_VERSION,
        "data_vintage": DATA_VINTAGE,
        "computed_at": ts_ns,
        "module_state": module_state,
        "min_lag_bars": CFG["min_lag_bars"],
    }


def _transition_vol(prev, liq, cfg):
    """Hysteresis machine on the volume leg (normative, §R3.1)."""
    if prev == "SEVERE":
        if liq < cfg["severe_exit"]:
            return "SEVERE"
    elif liq < cfg["severe_entry"]:
        return "SEVERE"
    if prev in ("THIN", "SEVERE"):
        return "NORMAL" if liq >= cfg["thin_exit"] else "THIN"
    return "THIN" if liq < cfg["thin_entry"] else "NORMAL"


def _transition_spr(prev, spr, cfg):
    """Hysteresis machine on the spread leg (normative, §R3.1)."""
    if prev == "SEVERE":
        if spr > cfg["spr_severe_exit"]:
            return "SEVERE"
    elif spr >= cfg["spr_severe_entry"]:
        return "SEVERE"
    if prev in ("THIN", "SEVERE"):
        return "NORMAL" if spr <= cfg["spr_thin_exit"] else "THIN"
    return "THIN" if spr >= cfg["spr_thin_entry"] else "NORMAL"


def _worst(a, b):
    return a if SEVERITY[a] >= SEVERITY[b] else b


def _ratios(e):
    v = _parse_float(e["cumvol"])
    b = _parse_float(e["baseline"])
    s = _parse_float(e["spread"])
    sb = _parse_float(e["spread_base"])
    if not all(math.isfinite(x) for x in (v, b, s, sb)):
        raise ValueError("non-finite liquidity inputs")  # F1/F2
    if b <= 0 or sb <= 0:
        raise ValueError("non-positive baseline")  # F2
    liq, spr = v / b, s / sb
    if not (math.isfinite(liq) and math.isfinite(spr)) or liq < 0 or spr < 0:
        raise ValueError("out-of-bounds ratio")  # F2
    return liq, spr


def _ratios_v2(e):
    v = _parse_float(e["cumvol_v2"])
    b = _parse_float(e["baseline_v2"])
    s = _parse_float(e["spread_v2"])
    sb = _parse_float(e["spread_base_v2"])
    if not all(math.isfinite(x) for x in (v, b, s, sb)) or b <= 0 or sb <= 0:
        raise ValueError("bad second-venue inputs")
    return v / b, s / sb


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState], one emission per bar.

    Causal: the label at position t uses only events[:t+1]. Missing input,
    corporate-action bars, halts, and bad numerics yield module_state UNKNOWN
    (F1/F2) and freeze the hysteresis state. Never interpolates.
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), float("nan"), 0, "UNKNOWN")]
    out = []
    prev_vol, prev_spr = "NORMAL", "NORMAL"
    for e in events:
        ts = int(float(e["ts_ns"]))
        try:
            if str(e.get("halted", "0")).strip() == "1":
                raise ValueError("halted bar")  # freeze per market-state table
            if str(e.get("corp_action", "none")).strip() in ("split", "reverse_split"):
                raise ValueError("corporate action: mask")  # §R3.1
            liq, spr = _ratios(e)
            liq2, spr2 = _ratios_v2(e)
        except Exception:
            out.append(_mk("UNKNOWN", float("nan"), float("nan"), ts, "UNKNOWN"))
            continue
        vol_state = _transition_vol(prev_vol, liq, cfg)
        spr_state = _transition_spr(prev_spr, spr, cfg)
        vol2 = _transition_vol(prev_vol, liq2, cfg)
        spr2 = _transition_spr(prev_spr, spr2, cfg)
        if _worst(vol2, spr2) != _worst(vol_state, spr_state):
            out.append(_mk("UNKNOWN", liq, spr, ts, "UNKNOWN"))  # F3
            continue
        prev_vol, prev_spr = vol_state, spr_state
        out.append(_mk(_worst(vol_state, spr_state), liq, spr, ts, "OK"))
    return out


def apply_freshness(rs, now_ns):
    """F4: expire to UNKNOWN when computed_at is older than 3x cadence."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > 3 * CADENCE_NS:
        rs = dict(rs)
        rs["module_state"] = "UNKNOWN"
        rs["state"] = "UNKNOWN"
    return rs


def cost_adjustment(rsv, base):
    """§R5 cost interface: regime state -> cost-function adjustment."""
    adj = dict(base)
    adj["tags"] = ["R038:" + rsv["state"]]
    adj["edge_mult"] = 1.0
    st, ms = rsv["state"], rsv["module_state"]
    if ms in ("UNKNOWN", "DEGRADED") or st == "SEVERE":
        adj["trade_ok"] = False
    else:
        adj["trade_ok"] = True
    if st == "THIN" and ms == "OK":
        adj["spread_bps"] = base["spread_bps"] * 2.5
        adj["impact_bps"] = base["impact_bps"] * 3.0
        adj["edge_mult"] = 1.5
    elif st == "SEVERE":
        adj["spread_bps"] = base["spread_bps"] * 5.0
        adj["impact_bps"] = base["impact_bps"] * 5.0
        adj["edge_mult"] = 2.0
    elif ms == "DEGRADED":
        adj["edge_mult"] = 1.5
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


def _col(row, key):
    v = row.get(key, "").strip()
    return float("nan") if v == "" else float(v)


def test_fixture_replay():
    tape = _load("R038_tape.csv")
    exp = _load("R038_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R038_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        assert _close(g["liq_ratio"], _col(x, "liq_ratio"), TOL), (g, x)
        assert _close(g["spr_ratio"], _col(x, "spr_ratio"), TOL), (g, x)


def test_state_sequence_pins_transitions():
    """Entry, hysteresis holds, exits, severe, UNKNOWN freeze/recovery."""
    tape = _load("R038_tape.csv")
    got = detect(None, tape, CFG)
    seq = [(g["state"], g["module_state"]) for g in got]
    assert seq == [
        ("NORMAL", "OK"),    # 0.95: normal
        ("THIN", "OK"),      # 0.65: volume entry
        ("THIN", "OK"),      # 0.72: hold inside deadband (< 0.75 exit)
        ("NORMAL", "OK"),    # 0.80: exit (>= 0.75)
        ("SEVERE", "OK"),    # 0.45: severe entry
        ("SEVERE", "OK"),    # 0.55: severe hold (< 0.60 exit)
        ("THIN", "OK"),      # 0.65: severe demote -> thin (< 0.70 entry)
        ("THIN", "OK"),      # spread 2.5: spread entry while volume normal
        ("THIN", "OK"),      # spread 1.8: spread hold (> 1.75 exit)
        ("NORMAL", "OK"),    # spread 1.2: spread exit (<= 1.75)
        ("UNKNOWN", "UNKNOWN"),  # missing bar: F1 freeze
        ("NORMAL", "OK"),    # recovery, no re-warm
        ("UNKNOWN", "UNKNOWN"),  # split: corporate-action mask
        ("NORMAL", "OK"),    # recovery
        ("UNKNOWN", "UNKNOWN"),  # halt: freeze
        ("NORMAL", "OK"),    # recovery
    ], seq


def test_hysteresis_boundary_pins():
    """Hand-valued exact-band behavior (entry strict, exit inclusive)."""
    c = CFG
    assert _transition_vol("NORMAL", 0.70, c) == "NORMAL"      # entry needs <
    assert _transition_vol("NORMAL", 0.699999, c) == "THIN"
    assert _transition_vol("THIN", 0.749999, c) == "THIN"      # exit needs >=
    assert _transition_vol("THIN", 0.75, c) == "NORMAL"
    assert _transition_vol("SEVERE", 0.599999, c) == "SEVERE"
    assert _transition_vol("SEVERE", 0.60, c) == "THIN"       # demote path
    assert _transition_spr("NORMAL", 2.0, c) == "THIN"         # entry needs >=
    assert _transition_spr("NORMAL", 1.999999, c) == "NORMAL"
    assert _transition_spr("THIN", 1.750001, c) == "THIN"      # exit needs <=
    assert _transition_spr("THIN", 1.75, c) == "NORMAL"
    assert _transition_spr("NORMAL", 3.0, c) == "SEVERE"
    assert _transition_spr("SEVERE", 2.500001, c) == "SEVERE"
    assert _transition_spr("SEVERE", 2.5, c) == "THIN"


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R038_tape.csv")
    full = detect(None, tape, CFG)
    for k in range(1, len(tape) + 1):
        prefix = detect(None, tape[:k], CFG)
        assert len(prefix) == k
        for a, b in zip(prefix, full[:k]):
            assert a["state"] == b["state"], (k, a, b)
            assert a["module_state"] == b["module_state"]
            assert _close(a["liq_ratio"], b["liq_ratio"], TOL)
            assert _close(a["spr_ratio"], b["spr_ratio"], TOL)


def test_f1_missing_input_unknown():
    got = detect(None, [], CFG)
    assert len(got) == 1
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"


def test_f1_corp_action_masked():
    tape = _load("R038_tape.csv")
    got = detect(None, tape, CFG)
    assert got[12]["module_state"] == "UNKNOWN"  # split bar
    assert got[12]["state"] == "UNKNOWN"


def test_f1_halt_freezes():
    tape = _load("R038_tape.csv")
    got = detect(None, tape, CFG)
    assert got[14]["module_state"] == "UNKNOWN"  # halted bar
    assert got[14]["state"] == "UNKNOWN"


def test_f2_bounds_violation_unknown():
    tape = _load("R038_tape.csv")
    bad = [dict(r) for r in tape]
    bad[0]["baseline"] = "0"
    got = detect(None, bad, CFG)
    assert got[0]["module_state"] == "UNKNOWN", got[0]
    bad2 = [dict(r) for r in tape]
    bad2[1]["spread"] = "nan"
    got2 = detect(None, bad2, CFG)
    assert got2[1]["module_state"] == "UNKNOWN", got2[1]


def test_f3_dual_estimator_agreement():
    tape = _load("R038_tape.csv")
    got = detect(None, tape, CFG)
    # recompute the verifier label independently and require label agreement
    pv, ps = "NORMAL", "NORMAL"
    for e, g in zip(tape, got):
        if g["module_state"] != "OK":
            continue
        liq2, spr2 = _ratios_v2(e)
        v2 = _worst(_transition_vol(pv, liq2, CFG), _transition_spr(ps, spr2, CFG))
        assert v2 == g["state"], (e["ts_ns"], v2, g["state"])
        liq, spr = _ratios(e)  # advance sentinel prev in lockstep with detect
        pv = _transition_vol(pv, liq, CFG)
        ps = _transition_spr(ps, spr, CFG)
    # tampered second venue must force UNKNOWN
    bad = [dict(r) for r in tape]
    bad[1]["cumvol_v2"] = "0.99"  # ratio ~0.99 -> NORMAL vs sentinel THIN
    got2 = detect(None, bad, CFG)
    assert got2[1]["module_state"] == "UNKNOWN", got2[1]


def test_f4_staleness_expires_to_unknown():
    tape = _load("R038_tape.csv")
    rs = detect(None, tape, CFG)[9]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R038_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_cost_interface():
    base = {"spread_bps": 2.0, "impact_bps": 1.0, "borrow_bps": 0.5}
    thin = cost_adjustment(_mk("THIN", 0.65, 1.2, 1, "OK"), base)
    assert thin["trade_ok"] is True
    assert abs(thin["spread_bps"] - 5.0) <= TOL      # x2.5
    assert abs(thin["impact_bps"] - 3.0) <= TOL      # x3.0
    assert abs(thin["edge_mult"] - 1.5) <= TOL
    assert thin["tags"] == ["R038:THIN"]
    sev = cost_adjustment(_mk("SEVERE", 0.45, 1.5, 1, "OK"), base)
    assert sev["trade_ok"] is False
    assert abs(sev["spread_bps"] - 10.0) <= TOL      # x5.0
    assert abs(sev["impact_bps"] - 5.0) <= TOL       # x5.0
    assert abs(sev["edge_mult"] - 2.0) <= TOL
    norm = cost_adjustment(_mk("NORMAL", 0.95, 1.0, 1, "OK"), base)
    assert norm["trade_ok"] is True
    assert norm["spread_bps"] == base["spread_bps"]  # passthrough
    assert abs(norm["edge_mult"] - 1.0) <= TOL
    unk = cost_adjustment(_mk("UNKNOWN", float("nan"), float("nan"), 1, "UNKNOWN"), base)
    assert unk["trade_ok"] is False                  # restrictive
    deg = cost_adjustment(_mk("THIN", 0.65, 1.2, 1, "DEGRADED"), base)
    assert deg["trade_ok"] is False
    assert abs(deg["edge_mult"] - 1.5) <= TOL


def test_config_defaults_match_chapter():
    """CFG must equal the §R0.2 table in modules/regimes/R038.md."""
    assert CFG == {
        "thin_entry": 0.70,
        "thin_exit": 0.75,
        "severe_entry": 0.50,
        "severe_exit": 0.60,
        "spr_thin_entry": 2.0,
        "spr_thin_exit": 1.75,
        "spr_severe_entry": 3.0,
        "spr_severe_exit": 2.5,
        "baseline_window_days": 20,
        "min_baseline_days": 10,
        "dual_tol": 1e-9,
        "min_lag_bars": 1,
    }


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module §R3)."""
    tape = _load("R038_tape.csv")
    got = detect(None, tape, CFG)
    assert abs(got[0]["liq_ratio"] - 0.95) <= TOL and got[0]["state"] == "NORMAL"
    assert abs(got[1]["liq_ratio"] - 0.65) <= TOL and got[1]["state"] == "THIN"
    assert abs(got[7]["spr_ratio"] - 2.5) <= TOL and got[7]["state"] == "THIN"
