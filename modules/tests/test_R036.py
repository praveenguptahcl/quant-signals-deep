"""R036 — Macro announcement windows: acceptance tests.

Normative detector: per-bar `detect(state, events, cfg)` implementing the
hysteresis state machine from module section R2/R3. Empty input or an
unparseable row yields module_state UNKNOWN (F1); out-of-bounds indicator
values yield UNKNOWN (F2); the previous *valid* regime label is frozen across
UNKNOWN events (no interpolation, resume on recovery). Never emits orders.

Definition of done: `python3 -m pytest modules/tests/test_R036.py -q` exits 0.
"""
import csv
import math
import os

RID = "R036"
TOL = 1e-9
DUAL_TOL = 1e-12
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 60000000000
DATA_VINTAGE = "2026-09-09"

CFG = {
    "M_active_entry": 3.0,
    "M_active_exit": 2.5,
    "M_watch_entry": 1.5,
    "M_watch_exit": 1.0,
    "win_half_min": 45,
    "min_lag_bars": 1,
}


def _parse_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _parse_t_rel(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


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


def _transition(prev, m, in_window, cfg):
    """Hysteresis state machine (module §R2, normative).

    Entry thresholds differ from exit thresholds so the label cannot flap at
    a boundary: ACTIVE is held until M < M_active_exit (strict), WATCH until
    M < M_watch_exit (strict). Exact entry values (==) always enter.
    """
    ae, ax = cfg["M_active_entry"], cfg["M_active_exit"]
    we, wx = cfg["M_watch_entry"], cfg["M_watch_exit"]
    if prev in ("QUIET", "UNKNOWN"):
        if m >= ae or in_window:
            return "ACTIVE"
        if m >= we:
            return "WATCH"
        return "QUIET"
    if prev == "WATCH":
        if m >= ae or in_window:
            return "ACTIVE"
        if m < wx:
            return "QUIET"
        return "WATCH"
    if prev == "ACTIVE":
        if in_window:
            return "ACTIVE"
        if m < wx:
            return "QUIET"
        if m < ax:
            return "WATCH"
        return "ACTIVE"
    raise ValueError("unreachable prev state: %r" % (prev,))


def _transition_dual(prev, m, in_window, cfg):
    """Independent re-derivation of the hysteresis machine (F3 dual estimator).

    Written as memoryless mapping + hysteresis correction, a deliberately
    different code path from _transition. Must agree on every state.
    """
    ae, ax = cfg["M_active_entry"], cfg["M_active_exit"]
    we, wx = cfg["M_watch_entry"], cfg["M_watch_exit"]
    if m >= ae or in_window:
        return "ACTIVE"
    if prev == "ACTIVE" and m >= ax:
        return "ACTIVE"  # hysteresis hold above the exit band
    if m >= we:
        return "WATCH"
    if prev in ("ACTIVE", "WATCH") and m >= wx:
        return "WATCH"  # hysteresis hold above the exit band
    return "QUIET"


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal: the label at position t uses only events[:t+1] plus the frozen
    previous label (no later data). F1: empty events or an unparseable row ->
    UNKNOWN, prev frozen. F2: non-finite or negative M -> UNKNOWN, prev
    frozen. Never interpolates across the gap.
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    prev = "QUIET"
    for e in events:
        ts = int(float(e["ts_ns"]))
        m = _parse_float(e.get("M"))
        t_rel = _parse_t_rel(e.get("t_rel_min"))
        if not math.isfinite(m):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1/F2
            continue  # prev frozen: no interpolation across the gap
        if m < 0.0:
            out.append(_mk("UNKNOWN", m, ts, "UNKNOWN"))  # F2: impossible value
            continue
        in_window = t_rel is not None and abs(t_rel) <= cfg["win_half_min"]
        new = _transition(prev, m, in_window, cfg)
        out.append(_mk(new, m, ts, "OK"))
        prev = new
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


# ---------------------------------------------------------------- fixtures

def test_fixture_replay():
    tape = _load("R036_tape.csv")
    exp = _load("R036_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R036_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        assert g["estimator_version"] == ESTIMATOR_VERSION
        assert g["regime_id"] == RID
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R036_tape.csv")
    full = detect(None, tape, CFG)
    for k in range(1, len(tape) + 1):
        prefix = detect(None, tape[:k], CFG)
        assert len(prefix) == k
        for a, b in zip(prefix, full[:k]):
            assert a["state"] == b["state"], (k, a, b)
            assert a["module_state"] == b["module_state"]
            assert _close(a["value"], b["value"], TOL), (k, a["value"], b["value"])


# ---------------------------------------------------------------- F1 / F2

def test_f1_missing_input_unknown():
    got = detect(None, [], CFG)
    assert len(got) == 1
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"


def test_f1_unparseable_row_unknown_then_recovery():
    tape = _load("R036_tape.csv")
    bad = [dict(r) for r in tape]
    bad[6]["M"] = "not-a-number"
    got = detect(None, bad, CFG)
    assert got[6]["module_state"] == "UNKNOWN", got[6]
    assert got[6]["state"] == "UNKNOWN"
    # prev label frozen across the gap: row 5 was WATCH, row 7 (M=1.0) resumes WATCH
    assert got[5]["state"] == "WATCH"
    assert got[7]["state"] == "WATCH" and got[7]["module_state"] == "OK"


def test_f2_bounds_violation_unknown():
    tape = _load("R036_tape.csv")
    bad = [dict(r) for r in tape]
    bad[1]["M"] = "nan"
    got = detect(None, bad, CFG)
    assert got[1]["module_state"] == "UNKNOWN", got[1]
    # frozen prev (ACTIVE from row 0) resumes: row 2 M=2.5 stays ACTIVE
    assert got[2]["state"] == "ACTIVE" and got[2]["module_state"] == "OK"


def test_f2_negative_m_unknown():
    tape = _load("R036_tape.csv")
    bad = [dict(r) for r in tape]
    bad[0]["M"] = "-0.5"  # |.|/sigma can never be negative: corrupt feed
    got = detect(None, bad, CFG)
    assert got[0]["module_state"] == "UNKNOWN", got[0]


# ---------------------------------------------------------------- F3 dual

def test_f3_dual_estimator_agreement():
    """Two independent implementations of the transition machine agree."""
    tape = _load("R036_tape.csv")
    primary = detect(None, tape, CFG)
    prev = "QUIET"
    for e, p in zip(tape, primary):
        m = _parse_float(e.get("M"))
        t_rel = _parse_t_rel(e.get("t_rel_min"))
        if not math.isfinite(m) or m < 0.0:
            assert p["module_state"] == "UNKNOWN"
            continue  # prev frozen in both paths
        in_window = t_rel is not None and abs(t_rel) <= CFG["win_half_min"]
        d = _transition_dual(prev, m, in_window, CFG)
        assert d == p["state"], (e, d, p["state"])
        assert _close(m, p["value"], DUAL_TOL)
        prev = p["state"]


# ---------------------------------------------------------------- F4 / F5

def test_f4_staleness_expires_to_unknown():
    tape = _load("R036_tape.csv")
    rs = detect(None, tape, CFG)[-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R036_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


# ---------------------------------------------------------------- behavior pins (logic-drift guards)

def test_exact_threshold_boundaries():
    """== entry always enters; == exit never exits (strict < on the way out)."""
    got = detect(None, _load("R036_tape.csv"), CFG)
    assert got[0]["state"] == "ACTIVE" and got[0]["value"] == 3.0   # M == 3.0 enters
    assert got[9]["state"] == "WATCH" and got[9]["value"] == 1.5    # M == 1.5 enters
    assert got[2]["state"] == "ACTIVE" and got[2]["value"] == 2.5   # M == 2.5 holds
    assert got[7]["state"] == "WATCH" and got[7]["value"] == 1.0    # M == 1.0 holds


def test_hysteresis_hold_and_exit():
    """ACTIVE persists below the entry band until the exit band is crossed."""
    got = detect(None, _load("R036_tape.csv"), CFG)
    assert got[1]["state"] == "ACTIVE"   # M=2.8 < 3.0 entry, >= 2.5 exit: hold
    assert got[5]["state"] == "WATCH"    # M=2.4 < 2.5 exit, out of window: step down
    assert got[6]["state"] == "WATCH"    # M=1.6 >= 1.0 exit: hold
    assert got[8]["state"] == "QUIET"    # M=0.9 < 1.0 exit: step down


def test_hysteresis_invariants():
    """Drift guard: exit bands must sit strictly below entry bands."""
    assert CFG["M_active_exit"] < CFG["M_active_entry"]
    assert CFG["M_watch_exit"] < CFG["M_watch_entry"]
    assert CFG["M_watch_entry"] <= CFG["M_active_exit"], "bands must not overlap"


def test_window_boundary_and_override():
    """|t_rel| <= win_half_min forces ACTIVE even on tiny M; 50 min does not."""
    got = detect(None, _load("R036_tape.csv"), CFG)
    assert got[3]["state"] == "ACTIVE" and got[3]["value"] == 0.2  # t_rel=-45: in window
    assert got[4]["state"] == "ACTIVE"                             # window overrides M=1.2
    assert got[5]["state"] == "WATCH"                              # t_rel=50: out of window
    assert got[13]["state"] == "ACTIVE"                            # t_rel=-45 re-entry from QUIET


def test_unknown_freezes_and_recovers():
    got = detect(None, _load("R036_tape.csv"), CFG)
    assert got[10]["state"] == "UNKNOWN" and got[10]["module_state"] == "UNKNOWN"
    assert math.isnan(got[10]["value"])
    # frozen label was WATCH (row 9); row 11 resumes from it, no interpolation
    assert got[11]["state"] == "WATCH" and got[11]["module_state"] == "OK"
    assert got[11]["value"] == 1.2
    assert got[12]["state"] == "QUIET"


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3)."""
    got = detect(None, _load("R036_tape.csv"), CFG)
    assert got[0]["state"] == "ACTIVE" and got[0]["value"] == 3.0
    assert got[5]["state"] == "WATCH" and got[5]["value"] == 2.4
    assert got[8]["state"] == "QUIET" and got[8]["value"] == 0.9
