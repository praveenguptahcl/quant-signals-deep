"""R039 — OpEx / quad-witching pinning: acceptance tests (concrete sketch).

Normative behavior lives in the module's §R2 pseudocode; this harness is a
faithful, test-only implementation of it: snapshot-grouped max-pain K*,
hysteresis entry/exit, HALT freeze, SPLIT rebase, corporate-action guard.

Definition of done: `python3 -m pytest modules/tests/test_R039.py -q` exits 0.
"""
import csv
import math
import os

RID = "R039"
TOL = 1e-9
DUAL_TOL = 1e-12
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

CFG = {"pin_tol_entry": 0.005, "pin_tol_exit": 0.008, "min_lag_bars": 1}
# Hysteresis invariant: exit tolerance is strictly wider than entry tolerance.
assert CFG["pin_tol_exit"] > CFG["pin_tol_entry"]


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


def _transition(prev_label, dist, cfg):
    """Hysteresis state machine (§R2): entry inclusive, exit strict."""
    if prev_label == "PIN":
        return "PIN" if dist <= cfg["pin_tol_exit"] else "WATCH"
    return "PIN" if dist <= cfg["pin_tol_entry"] else "WATCH"


def _kstar(strikes, calls, puts):
    def _pi(k):
        return sum(max(0.0, k - ki) * p for ki, p in zip(strikes, puts)) + \
               sum(max(0.0, ki - k) * c for ki, c in zip(strikes, calls))
    return float(min(strikes, key=_pi))


def _kstar_dual(strikes, calls, puts):
    _pis = {}
    for k in strikes:
        _pis[k] = sum(max(0.0, k - ki) * p for ki, p in zip(strikes, puts)) + \
                  sum(max(0.0, ki - k) * c for ki, c in zip(strikes, calls))
    return float(min(_pis, key=lambda k: _pis[k]))


def _bounds_ok(value, cfg):
    return math.isfinite(value) and value > 0.0


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState], one per snapshot/control row.

    Snapshot rows are grouped by ts_ns (ascending); each snapshot yields one
    label computed from that snapshot's rows only. Control rows:
    HALT -> freeze + UNKNOWN (state retained, never interpolated);
    SPLIT(f) -> rebase cached K* by f, emit DEGRADED.
    Corporate-action guard: spot outside [min_strike/2, max_strike*2] -> UNKNOWN.
    Empty input or an unparseable row yields module_state UNKNOWN (F1);
    out-of-bounds indicator values yield UNKNOWN (F2).
    """
    st = {"k_star": None, "label": "OFF"} if state is None else dict(state)
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    snap_rows, snap_ts = [], None

    def _flush():
        if not snap_rows:
            return
        ts = snap_ts
        try:
            ks = [_parse_float(r["strike"]) for r in snap_rows]
            cs = [_parse_float(r["call_oi"]) for r in snap_rows]
            ps = [_parse_float(r["put_oi"]) for r in snap_rows]
            spot = _parse_float(snap_rows[0]["spot"])
        except Exception:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1
            return
        if not all(math.isfinite(v) for v in ks + cs + ps) \
                or not (math.isfinite(spot) and spot > 0):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1/F2
            return
        if spot < min(ks) / 2.0 or spot > max(ks) * 2.0:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F2 guard
            return
        kstar = _kstar(ks, cs, ps)
        if not _bounds_ok(kstar, cfg):
            out.append(_mk("UNKNOWN", kstar, ts, "UNKNOWN"))  # F2
            return
        dist = abs(spot - kstar) / spot
        label = _transition(st["label"], dist, cfg)
        st["k_star"], st["label"] = kstar, label
        out.append(_mk(label, kstar, ts, "OK"))

    for e in events:
        et = (e.get("event_type") or "").strip().upper()
        ts = int(float(e["ts_ns"]))
        if et in ("HALT", "SPLIT"):
            _flush()
            snap_rows, snap_ts = [], None
            if et == "HALT":
                # Freeze: retain cached K*, emit UNKNOWN, discard contributions.
                out.append(_mk("UNKNOWN",
                               st["k_star"] if st["k_star"] is not None else float("nan"),
                               ts, "UNKNOWN"))
            else:
                f = _parse_float(e.get("factor"))
                spot = _parse_float(e.get("spot"))
                if not (math.isfinite(f) and f > 0) or st["k_star"] is None \
                        or not (math.isfinite(spot) and spot > 0):
                    out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
                    continue
                v = st["k_star"] * f
                dist = abs(spot - v) / spot
                label = _transition(st["label"], dist, cfg)
                st["k_star"], st["label"] = v, label
                out.append(_mk(label, v, ts, "DEGRADED"))
            continue
        if snap_ts is None:
            snap_ts = ts
        if ts != snap_ts:
            _flush()
            snap_rows, snap_ts = [], ts
        snap_rows.append(e)
    _flush()
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


def _check_replay(tape_name, exp_name):
    p = os.path.join(os.path.dirname(__file__), "..", "fixtures", tape_name)
    assert open(p).readline().startswith("# TYPE: validation-run"), \
        "tape needs TYPE header"
    tape, exp = _load(tape_name), _load(exp_name)
    assert tape and exp, "fixtures must be non-empty"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)
        assert g["estimator_version"] == ESTIMATOR_VERSION
    return got


def test_fixture_replay():
    _check_replay("R039_tape.csv", "R039_expected.csv")


def test_no_lookahead():
    """The label at snapshot t must be identical with and without later data."""
    tape = _load("R039_tape.csv")
    tss = sorted({int(float(r["ts_ns"])) for r in tape
                  if not (r.get("event_type") or "").strip()})
    full = detect(None, tape, CFG)
    assert len(full) == len(tss)
    for k in range(1, len(tss) + 1):
        prefix = detect(None, [r for r in tape if int(float(r["ts_ns"])) <= tss[k - 1]], CFG)
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
    tape = _load("R039_tape.csv")
    bad = [dict(r) for r in tape]
    bad[2]["call_oi"] = "nan"  # corrupt one row of the first snapshot
    got = detect(None, bad, CFG)
    assert got[0]["module_state"] == "UNKNOWN", got[0]
    assert got[1]["module_state"] == "OK", got[1]  # later snapshots unaffected


def test_f3_dual_estimator_agreement():
    tape = _load("R039_tape.csv")
    rows = [r for r in tape if int(float(r["ts_ns"])) == 1789588800000000000]
    ks = [float(r["strike"]) for r in rows]
    cs = [float(r["call_oi"]) for r in rows]
    ps = [float(r["put_oi"]) for r in rows]
    v1, v2 = _kstar(ks, cs, ps), _kstar_dual(ks, cs, ps)
    assert _bounds_ok(v1, CFG)
    assert _close(v1, v2, DUAL_TOL), (v1, v2)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R039_tape.csv")
    rs = detect(None, tape, CFG)[-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R039_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3)."""
    tape = _load("R039_tape.csv")
    rows = [r for r in tape if int(float(r["ts_ns"])) == 1789588800000000000]
    ks = [float(r["strike"]) for r in rows]
    cs = [float(r["call_oi"]) for r in rows]
    ps = [float(r["put_oi"]) for r in rows]
    # Pi(K) hand-computed: {96:940, 98:680, 100:560, 102:600, 104:780}
    assert _kstar(ks, cs, ps) == 100.0
    got = detect(None, tape, CFG)
    assert got[0]["value"] == 100.0 and got[0]["state"] == "PIN"


def test_hysteresis_transitions():
    """t2 dist (0.005964) exceeds entry tol but stays PIN; t3 exits to WATCH.

    Fails on logic drift: a single-threshold rule (dist <= 0.005) would emit
    WATCH at t2, so this test pins the hysteresis band.
    """
    got = _check_replay("R039_tape.csv", "R039_expected.csv")
    assert [g["state"] for g in got] == ["PIN", "PIN", "WATCH"]
    # Drift guard: naive single-threshold would flip at t2.
    naive = ["PIN" if abs(float(r["spot"]) - 100.0) / float(r["spot"]) <= 0.005
             else "WATCH"
             for r in _load("R039_tape.csv")
             if int(float(r["ts_ns"])) == 1789675200000000000][:1]
    assert naive == ["WATCH"], "fixture t2 must discriminate hysteresis from naive"


def test_hysteresis_boundaries():
    """Entry inclusive at 0.005, exit strict at 0.008 — exact-boundary unit checks."""
    assert _transition("WATCH", 0.005, CFG) == "PIN"      # entry inclusive
    assert _transition("WATCH", 0.005 + 1e-9, CFG) == "WATCH"
    assert _transition("PIN", 0.008, CFG) == "PIN"        # exit strict
    assert _transition("PIN", 0.008 + 1e-9, CFG) == "WATCH"
    assert _transition("OFF", 0.005, CFG) == "PIN"
    got = _check_replay("R039_boundaries.csv", "R039_expected_boundaries.csv")
    assert [g["state"] for g in got] == ["WATCH", "PIN", "PIN", "WATCH"]


def test_halt_freeze():
    """HALT -> UNKNOWN with cached K* retained; next snapshot resumes PIN."""
    got = _check_replay("R039_halt.csv", "R039_expected_halt.csv")
    assert [g["state"] for g in got] == ["PIN", "UNKNOWN", "PIN"]
    assert [g["module_state"] for g in got] == ["OK", "UNKNOWN", "OK"]
    assert got[1]["value"] == 100.0  # frozen, not interpolated


def test_split_rebase():
    """SPLIT(0.5) rebases cached K* 100 -> 50, emits DEGRADED, then OK."""
    got = _check_replay("R039_split.csv", "R039_expected_split.csv")
    assert [(g["state"], g["value"], g["module_state"]) for g in got] == [
        ("PIN", 100.0, "OK"),
        ("PIN", 50.0, "DEGRADED"),
        ("PIN", 50.0, "OK"),
    ]


def test_unannounced_split_guard():
    """Spot far outside the strike band (no SPLIT event) -> UNKNOWN, page."""
    tape = _load("R039_tape.csv")
    bad = [dict(r) for r in tape if int(float(r["ts_ns"])) == 1789588800000000000]
    for r in bad:
        r["spot"] = "40"  # 40 < min_strike/2 = 48: unadjusted corporate action
    got = detect(None, bad, CFG)
    assert len(got) == 1
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"


def test_adversary_inversion():
    """Inverting the OI chain (puts<->calls) must move K*: estimator reads the chain."""
    st = [96, 98, 100, 102, 104]
    c, p = [10, 10, 10, 10, 10], [200, 10, 10, 10, 10]
    v1 = _kstar(st, c, p)   # hand-verified: Pi = {96:200, 98:520, 100:880, 102:1280, 104:1720}
    v2 = _kstar(st, p, c)   # hand-verified: Pi = {96:200, 98:140, 100:120, 102:140, 104:200}
    assert v1 == 96.0, v1
    assert v2 == 100.0, v2
    assert v1 != v2, "estimator must not be invariant to chain inversion"
