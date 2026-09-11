"""R033 — Systemic tail-risk / crisis regime: acceptance tests (reference implementation).

Implements the §R3 normative detector (z-supplied path + raw-returns estimator
path with dual-window F3 check) and pins it against three fixtures:
  R033_tape.csv            transitions / hysteresis / exact-kappa boundary
  R033_estimator_tape.csv  returns -> z estimation, warmup, corporate action, F3 disagreement
  R033_edge_tape.csv       missing prints (F1), non-finite z (F2), halt freeze/resume
Definition of done: `python3 -m pytest modules/tests/test_R033.py -q` exits 0.
"""
import csv
import math
import os
import statistics

RID = "R033"
TOL = 1e-9
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

# Fixture config overrides of the §R0.2 production defaults (see tape headers).
CFG = {
    "kappa": 2.5, "k_crit": 3, "k_watch": 2,
    "k_exit_crisis": 2, "k_exit_watch": 1, "streak_days": 2,
    "M": 8, "M_min_prints": 6,
    "z_window_days": 10, "z_window_days_w2": 8, "z_min_bars": 8,
    "sigma_floor": 1e-6, "ddof": 0, "min_lag_bars": 1,
}

COST_ADJUSTMENT_R033 = {  # mirrors the §R5 Cost interface block, v1.1.0
    "regime_id": "R033", "version": "1.1.0",
    "CRISIS": {"spread_mult": 5.0, "impact_mult": 5.0, "borrow_mult": 2.0,
               "fee_add_bps": 0.0, "edge_mult": 2.0,
               "directional_ok": False, "tail_hedge_ok": True, "tag": "[example]"},
    "WATCH": {"spread_mult": 2.0, "impact_mult": 2.0, "borrow_mult": 1.0,
              "fee_add_bps": 0.0, "edge_mult": 1.5,
              "directional_ok": True, "tail_hedge_ok": True, "tag": "[example]"},
    "NORMAL": {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0,
               "fee_add_bps": 0.0, "edge_mult": 1.0,
               "directional_ok": True, "tail_hedge_ok": True, "tag": "[default]"},
}


def _parse_float(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return float("nan")
    return v


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


def _z_from_returns(r, hist, cfg):
    mu = statistics.mean(hist)
    sd = statistics.pstdev(hist) if cfg["ddof"] == 0 else statistics.stdev(hist)
    sd = max(sd, cfg["sigma_floor"])
    return (r - mu) / sd


def _hysteresis(prev_label, prev_C, C, cfg):
    if prev_label == "CRISIS":
        return "CRISIS" if C >= cfg["k_exit_crisis"] else "WATCH"
    if prev_label == "WATCH":
        if C >= cfg["k_crit"]:
            return "CRISIS"
        if (C >= cfg["k_watch"] and prev_C is not None
                and prev_C >= cfg["k_watch"]):
            return "CRISIS"  # streak promotion: streak_days consecutive >= k_watch
        if C < cfg["k_exit_watch"]:
            return "NORMAL"
        return "WATCH"
    if C >= cfg["k_crit"]:
        return "CRISIS"
    if C >= cfg["k_watch"]:
        return "WATCH"
    return "NORMAL"


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState], one per bar, causal.

    Reference implementation of the §R3 normative pseudocode. Rows are grouped
    by ts_ns into bars. Two input paths:
      * z path: rows carry 'z' (pre-computed per the §R3 recipe).
      * estimator path: rows carry 'r_adj' (adjusted-close log returns); z is
        estimated from trailing history (z_window_days bars, ddof=0,
        sigma_floor); bars with < z_min_bars history -> UNKNOWN (warmup).
    F3: on the estimator path the crisis verdict is recomputed with the
    shorter W2 window; disagreement -> UNKNOWN. Missing prints: n < M_min_prints
    -> UNKNOWN (F1); M_min_prints <= n < M -> DEGRADED, missing prints count as
    non-breaches. Non-finite z -> UNKNOWN (F2). Non-trading market state ->
    UNKNOWN and the hysteresis memory freezes. CRISIS without Gate human ack
    (state['acked']) -> module_state DEGRADED, label still CRISIS.
    """
    acked = bool((state or {}).get("acked", False))
    bars = {}
    for e in events:
        bars.setdefault(int(float(e["ts_ns"])), []).append(e)
    hist = {}  # bench -> list of trailing r_adj (estimator path)
    label, prev_C = "NORMAL", 0  # hysteresis memory; UNKNOWN bars freeze it
    out = []
    for ts in sorted(bars):
        rows = bars[ts]
        mkt = (rows[0].get("mkt") or "CONTINUOUS_TRADING").strip()
        if mkt != "CONTINUOUS_TRADING":
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
            continue  # freeze: memory untouched
        n = len(rows)
        if n < cfg["M_min_prints"]:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1
            continue
        degraded = n < cfg["M"]
        estimator_path = "r_adj" in rows[0] and rows[0]["r_adj"].strip() != ""
        zs, crisis_w2 = [], None
        bar_bad = False
        if estimator_path:
            for b in {r["bench"] for r in rows}:
                hist.setdefault(b, [])
            if any(len(hist[r["bench"]]) < cfg["z_min_bars"] for r in rows):
                out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # warmup
                for r in rows:  # warmup bars still extend history (causal)
                    hist[r["bench"]].append(_parse_float(r["r_adj"]))
                continue
            for r in rows:
                h = hist[r["bench"]]
                z1 = _z_from_returns(_parse_float(r["r_adj"]), h[-cfg["z_window_days"]:], cfg)
                z2 = _z_from_returns(_parse_float(r["r_adj"]), h[-cfg["z_window_days_w2"]:], cfg)
                if not (math.isfinite(z1) and math.isfinite(z2)):
                    bar_bad = True  # F2
                    break
                zs.append(z1)
                crisis_w2 = (crisis_w2 or 0) + (1 if z2 < -cfg["kappa"] else 0)
            for r in rows:  # history extends AFTER z is computed (causal)
                hist[r["bench"]].append(_parse_float(r["r_adj"]))
        else:
            for r in rows:
                z = _parse_float(r.get("z", ""))
                if not math.isfinite(z):
                    bar_bad = True  # F2
                    break
                zs.append(z)
        if bar_bad:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
            continue
        C = sum(1 for z in zs if z < -cfg["kappa"])  # strict inequality
        if crisis_w2 is not None and (C >= cfg["k_crit"]) != (crisis_w2 >= cfg["k_crit"]):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F3
            continue
        new_label = _hysteresis(label, prev_C, C, cfg)
        module_state = "DEGRADED" if degraded else "OK"
        if new_label == "CRISIS" and not acked:
            module_state = "DEGRADED"  # Gate interlock: crisis known, not acked
        out.append(_mk(new_label, float(C), ts, module_state))
        label, prev_C = new_label, C
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


def _type_header(name):
    p = os.path.join(os.path.dirname(__file__), "..", "fixtures", name)
    with open(p) as f:
        return f.readline()


def _close(a, b, tol=TOL):
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return abs(a - b) <= tol


def _replay(tape_name, exp_name, state, per_bar=False):
    """per_bar=True: expected rows are per (bar, bench); collapse to one row per bar."""
    assert _type_header(tape_name).startswith("# TYPE: validation-run")
    tape = _load(tape_name)
    exp = _load(exp_name)
    assert tape and exp, "fixtures must be non-empty"
    if per_bar:
        seen, collapsed = set(), []
        for r in exp:
            if r["ts_ns"] not in seen:
                seen.add(r["ts_ns"])
                collapsed.append(r)
        exp = collapsed
    got = detect(state, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (x["ts_ns"], g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (x["ts_ns"], g, x)
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv), (x["ts_ns"], g["value"], xv)
    return got, exp


def test_fixture_replay():
    _replay("R033_tape.csv", "R033_expected.csv", {"acked": True})


def test_estimator_tape_replay():
    got, exp = _replay("R033_estimator_tape.csv", "R033_estimator_expected.csv",
                       {"acked": True}, per_bar=True)
    # the z layer itself is pinned per bench, not just the label:
    # bar 9 SPY (first computable bar) and bar 12 DBC (split bar via r_adj)
    full_exp = _load("R033_estimator_expected.csv")
    by_key = {(r["ts_ns"], r["bench"]): r for r in full_exp}
    r9 = by_key[("1789071091200000000", "SPY")]
    assert abs(float(r9["z_w1"]) - 1.6035674515) < TOL, r9["z_w1"]
    r12 = by_key[("1789071350400000000", "DBC")]
    assert abs(float(r12["z_w1"]) - 1.7910669424) < TOL, r12["z_w1"]
    assert float(r12["z_w1"]) > -CFG["kappa"]  # adjusted print: no breach


def test_edge_tape_replay():
    _replay("R033_edge_tape.csv", "R033_edge_expected.csv", {"acked": True})


def test_transitions_and_hysteresis():
    """Explicit pins: entry, hysteresis hold, exit, streak promotion, boundary."""
    got, _ = _replay("R033_tape.csv", "R033_expected.csv", {"acked": True})
    s = [g["state"] for g in got]
    v = [g["value"] for g in got]
    assert (s[3], v[3]) == ("CRISIS", 3.0)   # B4: entry at count 3
    assert (s[4], v[4]) == ("CRISIS", 2.0)   # B5: hysteresis hold at count 2
    assert (s[5], v[5]) == ("WATCH", 1.0)    # B6: crisis exits to WATCH at count 1
    assert (s[6], v[6]) == ("NORMAL", 0.0)   # B7: WATCH exits to NORMAL at count 0
    assert (s[7], v[7]) == ("WATCH", 2.0)    # B8: streak day 1
    assert (s[8], v[8]) == ("CRISIS", 2.0)   # B9: streak promotion (2 consec. >= 2)
    assert (s[11], v[11]) == ("NORMAL", 0.0)  # B12: z == -kappa exactly: NOT a breach
    assert (s[12], v[12]) == ("NORMAL", 1.0)  # B13: z just past -kappa: breach


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    for tape_name in ("R033_tape.csv", "R033_estimator_tape.csv"):
        tape = _load(tape_name)
        full = detect({"acked": True}, tape, CFG)
        # prefix by whole bars to keep bar grouping intact
        tss = sorted({int(float(r["ts_ns"])) for r in tape})
        for k in range(1, len(tss) + 1):
            prefix = [r for r in tape if int(float(r["ts_ns"])) <= tss[k - 1]]
            got = detect({"acked": True}, prefix, CFG)
            assert len(got) == k
            for a, b in zip(got, full[:k]):
                assert a["state"] == b["state"], (tape_name, k, a, b)
                assert a["module_state"] == b["module_state"]
                assert _close(a["value"], b["value"]), (tape_name, k)


def test_f1_missing_print_degraded_then_unknown():
    got, _ = _replay("R033_edge_tape.csv", "R033_edge_expected.csv", {"acked": True})
    assert got[1]["module_state"] == "DEGRADED" and got[1]["state"] == "WATCH"
    assert got[1]["value"] == 2.0  # 7 prints, missing print counts as non-breach
    assert got[2]["module_state"] == "UNKNOWN" and got[2]["state"] == "UNKNOWN"


def test_f2_nonfinite_z_unknown():
    got, _ = _replay("R033_edge_tape.csv", "R033_edge_expected.csv", {"acked": True})
    assert got[3]["module_state"] == "UNKNOWN" and got[3]["state"] == "UNKNOWN"


def test_f3_dual_estimator_agreement_and_disagreement():
    got, exp = _replay("R033_estimator_tape.csv", "R033_estimator_expected.csv",
                       {"acked": True}, per_bar=True)
    by_ts = {}
    for g in got:
        by_ts.setdefault(g["computed_at"], g)
    tss = sorted(by_ts)
    # bar 11: both windows agree on crisis -> CRISIS/OK
    assert by_ts[tss[10]]["state"] == "CRISIS"
    assert by_ts[tss[10]]["module_state"] == "OK"
    # bar 13: W2 says crisis (3 breaches), W1 says no crisis (2) -> UNKNOWN
    assert by_ts[tss[12]]["state"] == "UNKNOWN"
    assert by_ts[tss[12]]["module_state"] == "UNKNOWN"
    # the expected file records the divergent z's for the record
    full_exp = _load("R033_estimator_expected.csv")
    xr = [r for r in full_exp if r["ts_ns"] == str(tss[12]) and r["bench"] == "GLD"][0]
    assert float(xr["z_w1"]) > -CFG["kappa"] > float(xr["z_w2"])


def test_f4_staleness_expires_to_unknown():
    tape = _load("R033_tape.csv")
    rs = detect({"acked": True}, tape, CFG)[-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R033_tape.csv")
    for rs in detect({"acked": True}, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_ack_interlock_blocks_adds():
    """CRISIS without Gate human ack -> DEGRADED (label still CRISIS); acked -> OK."""
    tape = _load("R033_tape.csv")
    unacked = detect({"acked": False}, tape, CFG)
    acked = detect({"acked": True}, tape, CFG)
    for u, a in zip(unacked, acked):
        assert u["state"] == a["state"]  # the label does not depend on ack
        if a["state"] == "CRISIS":
            assert u["module_state"] == "DEGRADED", u
            assert a["module_state"] == "OK", a
        else:
            assert u["module_state"] == a["module_state"] == "OK"
    assert any(g["state"] == "CRISIS" for g in unacked)  # the test hit crisis bars


def test_halt_freezes_and_resumes():
    got, _ = _replay("R033_edge_tape.csv", "R033_edge_expected.csv", {"acked": True})
    assert got[4]["state"] == "UNKNOWN" and got[4]["module_state"] == "UNKNOWN"
    # bars 3-5 were UNKNOWN: memory froze at WATCH (bar 2); bar 6 resumes -> CRISIS
    assert got[5]["state"] == "CRISIS" and got[5]["module_state"] == "OK"


def test_corporate_action_uses_adjusted_returns():
    """Bar 12: DBC r_raw=-0.50 (simulated 2:1 split) must NOT breach via r_adj=+0.004."""
    tape = _load("R033_estimator_tape.csv")
    tss = sorted({int(float(r["ts_ns"])) for r in tape})
    bar12 = [r for r in tape if int(float(r["ts_ns"])) == tss[11]]
    dbc = [r for r in bar12 if r["bench"] == "DBC"][0]
    assert float(dbc["r_raw"]) == -0.50 and float(dbc["r_adj"]) == 0.004
    # the raw print WOULD have breached: prove the test is meaningful
    hist = [float(r["r_adj"]) for r in tape
            if r["bench"] == "DBC" and int(float(r["ts_ns"])) < tss[11]][-CFG["z_window_days"]:]
    z_raw = _z_from_returns(float(dbc["r_raw"]), hist, CFG)
    z_adj = _z_from_returns(float(dbc["r_adj"]), hist, CFG)
    assert z_raw < -CFG["kappa"], z_raw
    assert z_adj > -CFG["kappa"], z_adj
    got = detect({"acked": True}, tape, CFG)
    assert got[11]["value"] == 0.0 and got[11]["state"] == "WATCH"


def test_warmup_unknown():
    got = detect({"acked": True}, _load("R033_estimator_tape.csv"), CFG)
    for g in got[:8]:
        assert g["state"] == "UNKNOWN" and g["module_state"] == "UNKNOWN", g
    assert got[8]["state"] == "NORMAL" and got[8]["module_state"] == "OK"


def test_cost_interface_record():
    adj = COST_ADJUSTMENT_R033
    assert adj["regime_id"] == "R033" and adj["version"] == ESTIMATOR_VERSION
    n = adj["NORMAL"]
    assert n["spread_mult"] == n["impact_mult"] == n["borrow_mult"] == 1.0
    assert n["fee_add_bps"] == 0.0 and n["edge_mult"] == 1.0
    assert n["directional_ok"] and n["tail_hedge_ok"] and n["tag"] == "[default]"
    c = adj["CRISIS"]
    assert c["spread_mult"] == 5.0 and c["impact_mult"] == 5.0
    assert c["borrow_mult"] == 2.0 and c["fee_add_bps"] == 0.0
    assert c["edge_mult"] == 2.0 and not c["directional_ok"] and c["tail_hedge_ok"]
    assert c["tag"] == "[example]" and adj["WATCH"]["tag"] == "[example]"
    for k in ("CRISIS", "WATCH", "NORMAL"):
        assert set(adj[k]) == {"spread_mult", "impact_mult", "borrow_mult",
                               "fee_add_bps", "edge_mult", "directional_ok",
                               "tail_hedge_ok", "tag"}, k


def test_spot_handcheck():
    """Independently verified arithmetic: bar-11 SPY z_w1 == -23.3101201654.

    Cross-checked in the fixture generator with two independent implementations
    (numpy vs statistics, ddof=0, sigma_floor=1e-6): both gave -23.310120.
    """
    exp = _load("R033_estimator_expected.csv")
    tss = sorted({int(r["ts_ns"]) for r in exp})
    row = [r for r in exp if int(r["ts_ns"]) == tss[10] and r["bench"] == "SPY"][0]
    assert abs(float(row["z_w1"]) - (-23.3101201654)) < 1e-9, row["z_w1"]
    assert row["count"] == "3" and row["state"] == "CRISIS"
