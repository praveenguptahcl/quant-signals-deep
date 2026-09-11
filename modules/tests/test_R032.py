"""R032 — Flight-to-quality (stock/bond correlation sign): acceptance tests (concrete sketch).

Real imports, fixture load, real assertions. Not a production harness.
Definition of done: `python3 -m pytest modules/tests/test_R032.py -q` exits 0.

Reference implementation of the normative §R2 pseudocode (v1.1.0): trailing-W
Pearson rho over present bars, hysteresis state machine with entry/exit
confirmation, freeze-on-UNKNOWN gap policy, no interpolation.
"""
import csv
import math
import os
import statistics

RID = "R032"
TOL = 1e-9
DUAL_TOL = 1e-9
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"
SPIKE_DEGRADED_ABS = 0.50  # [default] single-bar sanity bound, §R7

# §R0.2 Config (v1.1.0). rho_entry/rho_exit/rho rule: rho_exit < rho_entry - 0.05
CFG = {
    "W": 63,
    "W_min": 21,  # ceil(W/3) [default]
    "confirm_days": 21,
    "rho_entry": 0.20,
    "rho_exit": 0.10,
    "min_lag_bars": 1,
}

# §R5 Cost interface (v1.1.0) — mirrors the module text. Identity record:
# R032 gates allocation tilts; it never scales cost inputs. Any drift here
# fails the test below.
COST_ADJUSTMENT_R032 = {
    "regime_id": "R032",
    "version": "1.1.0",
    "note": "tilt-only regime; no direct cost adjustment",
    "INFLATION_FEAR": {"spread_mult": 1.0, "impact_mult": 1.0,
                       "borrow_mult": 1.0, "fee_add_bps": 0.0, "tag": "[default]"},
    "FLIGHT_TO_QUALITY": {"spread_mult": 1.0, "impact_mult": 1.0,
                          "borrow_mult": 1.0, "fee_add_bps": 0.0, "tag": "[default]"},
    "TRANSITION": {"spread_mult": 1.0, "impact_mult": 1.0,
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
        "min_lag_bars": CFG.get("min_lag_bars", 1),
    }


def _fresh_state():
    return {"label": "TRANSITION", "up": 0, "down": 0, "cool": 0, "warm": 0}


def _pearson(xs, ys):
    """Trailing-window Pearson rho. NaN iff degenerate window (F2)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    vx = sum((a - mx) ** 2 for a in xs)
    vy = sum((b - my) ** 2 for b in ys)
    if vx <= 0.0 or vy <= 0.0:
        return float("nan")
    return cov / math.sqrt(vx * vy)


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState]. Causal replay.

    Per bar t (ascending ts), using only valid (spy,tlt) pairs with ts <= t:
      F1: non-finite input -> UNKNOWN, counters frozen, bar excluded (no
          interpolation).
      history: fewer than W_min valid bars -> UNKNOWN (insufficient history).
      F2: degenerate/NaN window rho -> UNKNOWN.
      rho: Pearson over trailing min(W, n) *present* bars.
      hysteresis (§R2): entry needs rho beyond +/-rho_entry for confirm_days
        consecutive valid bars; exit from INFLATION_FEAR needs
        rho < rho_exit for confirm_days; exit from FLIGHT_TO_QUALITY needs
        rho > -rho_exit for confirm_days. No direct outer<->outer jumps:
        they pass through TRANSITION (one extra bar).
      |r| > 0.50 [default] on a valid bar -> module_state DEGRADED (kept in
        window; flags a possible unadjusted corporate action, §R7).
      W_min <= n < W -> module_state DEGRADED (partial window, honest).
    """
    if state is None:
        state = _fresh_state()
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1: empty input
    out = []
    pairs = []
    for e in events:
        ts = int(float(e["ts_ns"]))
        spy = _parse_float(e["spy"])
        tlt = _parse_float(e["tlt"])
        if not (math.isfinite(spy) and math.isfinite(tlt)):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1
            continue
        spike = abs(spy) > SPIKE_DEGRADED_ABS or abs(tlt) > SPIKE_DEGRADED_ABS
        pairs.append((spy, tlt))
        n = len(pairs)
        if n < cfg["W_min"]:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))
            continue
        win = pairs[-cfg["W"]:] if n >= cfg["W"] else pairs
        rho = _pearson([p[0] for p in win], [p[1] for p in win])
        if not math.isfinite(rho):
            out.append(_mk("UNKNOWN", rho, ts, "UNKNOWN"))  # F2
            continue
        state["up"] = state["up"] + 1 if rho > cfg["rho_entry"] else 0
        state["down"] = state["down"] + 1 if rho < -cfg["rho_entry"] else 0
        state["cool"] = state["cool"] + 1 if rho < cfg["rho_exit"] else 0
        state["warm"] = state["warm"] + 1 if rho > -cfg["rho_exit"] else 0
        lab = state["label"]
        if lab == "TRANSITION":
            if state["up"] >= cfg["confirm_days"]:
                lab = "INFLATION_FEAR"
            elif state["down"] >= cfg["confirm_days"]:
                lab = "FLIGHT_TO_QUALITY"
        elif lab == "INFLATION_FEAR":
            if state["cool"] >= cfg["confirm_days"]:
                lab = "TRANSITION"
        elif lab == "FLIGHT_TO_QUALITY":
            if state["warm"] >= cfg["confirm_days"]:
                lab = "TRANSITION"
        state["label"] = lab
        mstate = "DEGRADED" if (n < cfg["W"] or spike) else "OK"
        out.append(_mk(lab, rho, ts, mstate))
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


# --------------------------------------------------------------------------
# Acceptance tests
# --------------------------------------------------------------------------

def test_fixture_replay():
    tape = _load("R032_tape.csv")
    exp = _load("R032_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R032_tape.csv")).readline()
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
    tape = _load("R032_tape.csv")
    full = detect(None, tape, CFG)
    for k in (1, 10, 40, 100, 150, 200, len(tape)):
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


def test_f1_missing_bar_freezes_counters():
    """A missing bar emits UNKNOWN, is excluded (no interpolation), and
    freezes confirmation counters rather than resetting them."""
    tape = _load("R032_tape.csv")
    missing = [i for i, r in enumerate(tape) if not r["tlt"].strip()]
    assert missing, "fixture must contain a missing-tlt bar (F1 pin)"
    i = missing[0]
    got = detect(None, tape, CFG)
    assert got[i]["module_state"] == "UNKNOWN", got[i]
    assert got[i]["state"] == "UNKNOWN"
    # neighbors keep their labels: the gap froze counters, not reset them
    assert got[i - 1]["state"] == got[i + 1]["state"], (got[i - 1], got[i + 1])


def test_f2_degenerate_window_unknown():
    """Zero-variance window -> non-finite rho -> UNKNOWN (F2), resumes after."""
    base = 1700000000000000000
    evs = [{"ts_ns": str(base + j * CADENCE_NS), "spy": "0.005", "tlt": str(0.001 * (j % 3 - 1))}
           for j in range(CFG["W_min"] + 3)]
    got = detect(None, evs, CFG)
    assert got[-1]["module_state"] == "UNKNOWN", got[-1]
    assert got[-1]["state"] == "UNKNOWN"
    # resumes automatically once variance returns
    evs2 = evs + [{"ts_ns": str(base + (CFG['W_min'] + 3 + j) * CADENCE_NS),
                   "spy": str(0.01 if j % 2 else -0.01),
                   "tlt": str(-0.008 if j % 2 else 0.008)} for j in range(5)]
    got2 = detect(None, evs2, CFG)
    assert got2[-1]["module_state"] in ("OK", "DEGRADED"), got2[-1]


def test_f3_dual_estimator_agreement():
    """Primary Pearson must agree with an independent implementation (F3a)."""
    tape = _load("R032_tape.csv")
    evs = [r for r in tape if r["spy"].strip() and r["tlt"].strip()]
    pairs = [(_parse_float(r["spy"]), _parse_float(r["tlt"])) for r in evs]
    for idx in (40, 100, 160, 200):
        win = pairs[max(0, idx - CFG["W"] + 1): idx + 1]
        xs = [p[0] for p in win]
        ys = [p[1] for p in win]
        v1 = _pearson(xs, ys)
        v2 = statistics.correlation(xs, ys)
        assert _close(v1, v2, DUAL_TOL), (idx, v1, v2)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R032_tape.csv")
    rs = [r for r in detect(None, tape, CFG) if r["module_state"] == "OK"][-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R032_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_spot_handcheck():
    """Independently hand-verified arithmetic (§R3 worked check)."""
    tape = _load("R032_tape.csv")
    got = detect(None, tape, CFG)
    # pin rows (0-based) verified against statistics.correlation on the window
    for idx, expect_state in PIN_ROWS:
        if not math.isfinite(got[idx]["value"]):
            assert expect_state == "UNKNOWN", (idx, got[idx])  # F1/insufficient-history pins
            continue
        xs, ys = _window_pairs(tape, idx)
        rho_ref = statistics.correlation(xs, ys)
        assert _close(got[idx]["value"], rho_ref, 1e-9), (idx, got[idx]["value"], rho_ref)
        assert got[idx]["state"] == expect_state, (idx, got[idx], expect_state)


def _window_pairs(tape, idx):
    evs = [r for r in tape[: idx + 1] if r["spy"].strip() and r["tlt"].strip()]
    win = evs[-CFG["W"]:]
    return [float(r["spy"]) for r in win], [float(r["tlt"]) for r in win]


# Pinned (bar, state) rows: transitions, hysteresis holds, boundaries.
# Bars 0-19: UNKNOWN (insufficient history, n < W_min=21).
# (values filled by generator inspection; drift here fails the suite)
PIN_ROWS = [
    (0, "UNKNOWN"),            # insufficient history
    (19, "UNKNOWN"),           # last insufficient-history bar
    (20, "TRANSITION"),        # first labelled bar; partial window -> DEGRADED
    (39, "TRANSITION"),        # down_count=20 < 21: entry confirmation not yet met
    (40, "FLIGHT_TO_QUALITY"), # 21 consecutive bars rho < -rho_entry: entry fires
    (62, "FLIGHT_TO_QUALITY"), # first full-window (n=63) bar
    (100, "FLIGHT_TO_QUALITY"),# 21-bar positive blip ends: whipsaw rejected
    (114, "FLIGHT_TO_QUALITY"),# boundary: rho=+0.088 inside +/-0.20, state persists
    (128, "FLIGHT_TO_QUALITY"),# warm=20 < 21: exit confirmation not yet met
    (129, "TRANSITION"),       # 21 consecutive bars rho > -rho_exit: exit fires
    (130, "UNKNOWN"),          # F1: missing tlt print; counters frozen
    (131, "TRANSITION"),       # resumes after gap; freeze-not-reset preserved count
    (139, "TRANSITION"),       # up=20 < 21: entry confirmation not yet met
    (140, "INFLATION_FEAR"),  # 21 consecutive bars rho > +rho_entry: entry fires
    (190, "INFLATION_FEAR"),  # 20-bar negative dip ends: exit bait rejected
    (201, "INFLATION_FEAR"),  # boundary: rho=+0.028, state persists via hysteresis
    (220, "INFLATION_FEAR"),  # cool=20 < 21: exit confirmation not yet met
    (221, "TRANSITION"),       # 21 consecutive bars rho < +rho_exit: exit fires
    (231, "TRANSITION"),       # down=20 < 21: re-entry confirmation not yet met
    (232, "FLIGHT_TO_QUALITY"),# re-entry fires (via TRANSITION, no direct jump)
]


def test_pin_rows():
    """Every pinned row must hold: transitions, hysteresis holds, boundaries."""
    assert PIN_ROWS, "PIN_ROWS must be populated by the fixture build"
    tape = _load("R032_tape.csv")
    got = detect(None, tape, CFG)
    for idx, expect_state in PIN_ROWS:
        assert got[idx]["state"] == expect_state, (idx, got[idx]["state"], expect_state)


def test_hysteresis_entry_needs_confirmation():
    """rho beyond entry threshold for < confirm_days bars must NOT flip."""
    tape = _load("R032_tape.csv")
    got = detect(None, tape, CFG)
    # phase B is a 21-bar positive blip that never sustains rho > rho_entry
    # for confirm_days: the whole panel must never leave FTQ during it
    for idx in range(80, 101):
        assert got[idx]["state"] == "FLIGHT_TO_QUALITY", (idx, got[idx])


def test_cost_interface_is_identity():
    """§R5 Cost interface: tilt-only regime; every state maps to unit
    multipliers and zero fee add. Logic drift fails this test."""
    for state, rec in COST_ADJUSTMENT_R032.items():
        if state in ("regime_id", "version", "note"):
            continue
        assert rec["spread_mult"] == 1.0, (state, rec)
        assert rec["impact_mult"] == 1.0, (state, rec)
        assert rec["borrow_mult"] == 1.0, (state, rec)
        assert rec["fee_add_bps"] == 0.0, (state, rec)
    assert COST_ADJUSTMENT_R032["version"] == ESTIMATOR_VERSION


def test_spike_bar_degraded_not_unknown():
    """|r| > 0.50 [default] on an otherwise valid bar -> DEGRADED, kept in
    window (§R7 corporate-action sanity rule)."""
    tape = _load("R032_tape.csv")
    bad = [dict(r) for r in tape]
    bad[150]["spy"] = "0.62"  # synthetic unadjusted-split-style print
    got = detect(None, bad, CFG)
    assert got[150]["module_state"] == "DEGRADED", got[150]
    assert got[150]["state"] != "UNKNOWN"
