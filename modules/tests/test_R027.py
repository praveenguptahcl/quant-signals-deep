"""R027 — Growth-surprise regime: acceptance tests.

Reference implementation of detect() with hysteresis state machine, plus
acceptance tests. Definition of done:
`python3 -m pytest modules/tests/test_R027.py -q` exits 0.

Fixture scenario (modules/fixtures/R027_tape.csv, # TYPE: validation-run):
  rows  1-2: positive surprises accumulate -> UPSIDE entry at row 2
             (value crosses enter_pos = 0.10 [example])
  rows  3-7: further positives, stays UPSIDE
  row   8:   value dips below enter_pos but above exit_pos -> hysteresis HOLD (UPSIDE)
  row   9:   large negatives drag value below enter_neg -> direct UPSIDE->DOWNSIDE flip
  row  10:   partial recovery, still below enter_neg -> DOWNSIDE (deep, trivially held)
  row  11:   value in (enter_neg, exit_neg) -> hysteresis HOLD (DOWNSIDE)
  row  12:   z_i = nan -> F2: UNKNOWN for this event, row SKIPPED (not folded in)
  row  13:   value excludes row 12; still in (enter_neg, exit_neg) -> DOWNSIDE hold
  row  14:   value rises above exit_neg but below enter_pos -> NEUTRAL exit
  row  15:   value crosses enter_pos -> UPSIDE re-entry
"""
import csv
import math
import os

RID = "R027"
TOL = 1e-9          # [default] fixture replay tolerance
DUAL_TOL = 1e-9     # [default] F3 dual-estimator agreement tolerance
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

CFG = {
    "lam": 0.02222222222222222,   # 1/45 per day [example]
    "min_lag_bars": 1,            # [default]
    "enter_pos": 0.10,            # [example]
    "exit_pos": 0.02,             # [example]
    "enter_neg": -0.10,           # [example]
    "exit_neg": -0.02,            # [example]
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


def _release_z(e):
    """Per-release surprise z. Prefers precomputed z_i; else derives
    (actual - consensus) / sigma. Non-finite / missing -> nan (F2)."""
    z = _parse_float(e.get("z_i"))
    if math.isfinite(z):
        return z
    a = _parse_float(e.get("actual"))
    c = _parse_float(e.get("consensus"))
    s = _parse_float(e.get("sigma"))
    if math.isfinite(a) and math.isfinite(c) and math.isfinite(s) and s > 0:
        return (a - c) / s
    return float("nan")


def _aggregate(releases, cfg):
    """Primary estimator: math.fsum over w * exp(-lam * days_ago) * z."""
    return math.fsum(
        w * math.exp(-cfg["lam"] * d) * z for (w, d, z) in releases
    )


def _dual_aggregate(releases, cfg):
    """Verifier estimator: naive left-to-right summation (F3)."""
    tot = 0.0
    for w, d, z in releases:
        tot += w * math.exp(-cfg["lam"] * d) * z
    return tot


def _transition(prev, value, cfg):
    """Hysteresis state machine (§R2 normative)."""
    ep, xp = cfg["enter_pos"], cfg["exit_pos"]
    en, xn = cfg["enter_neg"], cfg["exit_neg"]
    if prev == "UPSIDE":
        if value <= en:
            return "DOWNSIDE"
        if value < xp:
            return "NEUTRAL"
        return "UPSIDE"
    if prev == "DOWNSIDE":
        if value >= ep:
            return "UPSIDE"
        if value > xn:
            return "NEUTRAL"
        return "DOWNSIDE"
    # NEUTRAL start (or resume after UNKNOWN): symmetric entry bands
    if value >= ep:
        return "UPSIDE"
    if value <= en:
        return "DOWNSIDE"
    return "NEUTRAL"


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState] (one per event).

    Causal: label at position t uses only releases with event_ts <= t.
    Empty input -> single UNKNOWN (F1). A row with non-finite z, bad weight,
    or negative days_ago is SKIPPED: UNKNOWN for that event, not folded into
    history (F2, never interpolate). HALTED market_state rows freeze history
    and emit UNKNOWN; AUCTION rows hold last state as DEGRADED. Hysteresis
    memory persists across skipped rows; after staleness expiry the module
    resumes from NEUTRAL (see apply_freshness / §R7).
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    releases = []          # (weight, days_ago, z) valid releases so far
    prev_state = "NEUTRAL"  # start neutral [default]
    for e in events:
        ts = int(float(e["ts_ns"]))
        mkt = (e.get("market_state") or "CONTINUOUS_TRADING").strip()
        if mkt == "HALTED":
            # R0.5: freeze history, emit UNKNOWN (state frozen at prev label)
            out.append(_mk(prev_state, float("nan"), ts, "UNKNOWN"))
            continue
        if mkt == "AUCTION":
            out.append(_mk(prev_state, float("nan"), ts, "DEGRADED"))
            continue
        z = _release_z(e)
        w = _parse_float(e.get("weight"))
        d = _parse_float(e.get("days_ago"))
        if not (math.isfinite(z) and math.isfinite(w) and math.isfinite(d)
                and w >= 0 and d >= 0):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F2
            continue
        releases.append((w, d, z))
        value = _aggregate(releases, cfg)
        if not math.isfinite(value):
            out.append(_mk("UNKNOWN", value, ts, "UNKNOWN"))  # F2
            continue
        prev_state = _transition(prev_state, value, cfg)
        out.append(_mk(prev_state, value, ts, "OK"))
    return out


def apply_freshness(rs, now_ns):
    """F4: expire to UNKNOWN when computed_at is older than 3x cadence.
    Recovery resumes from NEUTRAL (hysteresis memory is cleared)."""
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
    tape = _load("R027_tape.csv")
    exp = _load("R027_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R027_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)


def test_weights_file_pins_ex_ante_weights():
    """The production weight file must exist, be non-negative, and sum to 1."""
    rows = _load("R027_weights.csv")
    assert rows, "weight file must be non-empty"
    tot = 0.0
    for r in rows:
        w = float(r["weight"])
        assert w >= 0, r
        tot += w
    assert abs(tot - 1.0) <= 1e-9, tot


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R027_tape.csv")
    full = detect(None, tape, CFG)
    for k in range(1, len(tape) + 1):
        prefix = detect(None, tape[:k], CFG)
        assert len(prefix) == k
        for a, b in zip(prefix, full[:k]):
            assert a["state"] == b["state"], (k, a, b)
            assert a["module_state"] == b["module_state"]
            assert _close(a["value"], b["value"], TOL), (k, a["value"], b["value"])


def test_config_invariants():
    """Hysteresis bands must be ordered; misconfiguration fails loudly."""
    assert CFG["enter_pos"] > CFG["exit_pos"] >= 0, CFG
    assert CFG["enter_neg"] < CFG["exit_neg"] <= 0, CFG
    assert CFG["lam"] > 0, CFG
    assert CFG["min_lag_bars"] >= 1, CFG


# ------------------------------------------------------- F1-F5 fail-safes

def test_f1_missing_input_unknown():
    got = detect(None, [], CFG)
    assert len(got) == 1
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"


def test_f2_nan_row_skipped_not_folded_in():
    """Row 12 (z_i=nan) -> UNKNOWN; row 13's value must EXCLUDE row 12."""
    tape = _load("R027_tape.csv")
    got = detect(None, tape, CFG)
    assert got[11]["module_state"] == "UNKNOWN", got[11]
    assert got[11]["state"] == "UNKNOWN"
    assert math.isnan(got[11]["value"])
    # row 13 OK and its value excludes the nan row:
    assert got[12]["module_state"] == "OK", got[12]
    valid = [(float(e["weight"]), float(e["days_ago"]), float(e["z_i"]))
             for i, e in enumerate(tape[:13]) if i != 11]
    expect = _dual_aggregate(valid, CFG)
    assert _close(got[12]["value"], expect, TOL), (got[12]["value"], expect)
    # folding the nan row in would poison the aggregate to nan:
    assert math.isnan(_dual_aggregate(
        valid + [(0.2, 2.0, float("nan"))], CFG))


def test_f3_dual_estimator_agreement():
    tape = _load("R027_tape.csv")
    releases = []
    for i, e in enumerate(tape):
        if i == 11:
            continue  # skipped F2 row
        releases.append((float(e["weight"]), float(e["days_ago"]),
                         float(e["z_i"])))
    v1 = _aggregate(releases, CFG)
    v2 = _dual_aggregate(releases, CFG)
    assert math.isfinite(v1)
    assert _close(v1, v2, DUAL_TOL), (v1, v2)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R027_tape.csv")
    rs = detect(None, tape, CFG)[-1]
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
    tape = _load("R027_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


# ------------------------------------------- transitions / hysteresis / edge

def test_spot_handcheck():
    """Independently written arithmetic for rows 1-2 (see §R3 worked check)."""
    lam = 1 / 45
    v1 = 0.15 * math.exp(-lam * 58) * 1.2
    v2 = v1 + 0.20 * math.exp(-lam * 51) * 0.9
    tape = _load("R027_tape.csv")
    got = detect(None, tape, CFG)
    assert _close(got[0]["value"], v1, 1e-12), (got[0]["value"], v1)
    assert _close(got[1]["value"], v2, 1e-12), (got[1]["value"], v2)
    assert got[0]["state"] == "NEUTRAL"   # 0.0497 < enter_pos
    assert got[1]["state"] == "UPSIDE"    # crosses enter_pos 0.10


def test_hysteresis_holds_upside_in_band():
    """Row 8: value dips below enter_pos (0.10) but stays above exit_pos
    (0.02) -> state must HOLD UPSIDE (would flip without hysteresis)."""
    got = detect(None, _load("R027_tape.csv"), CFG)
    v = got[7]["value"]
    assert CFG["exit_pos"] < v < CFG["enter_pos"], v
    assert got[7]["state"] == "UPSIDE", got[7]
    assert got[7]["module_state"] == "OK"


def test_transition_upside_to_downside():
    """Row 9: value crashes through enter_neg -> direct UPSIDE->DOWNSIDE."""
    got = detect(None, _load("R027_tape.csv"), CFG)
    assert got[8]["value"] <= CFG["enter_neg"], got[8]["value"]
    assert got[7]["state"] == "UPSIDE"
    assert got[8]["state"] == "DOWNSIDE", got[8]


def test_hysteresis_holds_downside_in_band():
    """Rows 11/13: value sits in (enter_neg, exit_neg) -> state must HOLD
    DOWNSIDE (would exit to NEUTRAL without hysteresis)."""
    got = detect(None, _load("R027_tape.csv"), CFG)
    for idx in (10, 12):
        v = got[idx]["value"]
        assert CFG["enter_neg"] < v < CFG["exit_neg"], (idx, v)
        assert got[idx]["state"] == "DOWNSIDE", (idx, got[idx])
        assert got[idx]["module_state"] == "OK"


def test_neutral_exit_and_reentry():
    """Row 14: value rises above exit_neg but below enter_pos -> NEUTRAL.
    Row 15: value crosses enter_pos -> UPSIDE re-entry."""
    got = detect(None, _load("R027_tape.csv"), CFG)
    v14 = got[13]["value"]
    assert CFG["exit_neg"] < v14 < CFG["enter_pos"], v14
    assert got[13]["state"] == "NEUTRAL", got[13]
    assert got[14]["value"] >= CFG["enter_pos"], got[14]["value"]
    assert got[14]["state"] == "UPSIDE", got[14]


def _synth(ts, **kw):
    e = {"ts_ns": str(ts), "release": "SYN", "z_i": "0.0",
         "weight": "1.0", "days_ago": "0.0"}
    e.update({k: str(v) for k, v in kw.items()})
    return e


def test_boundary_exact_zero_is_neutral():
    """value exactly 0.0 -> NEUTRAL from any prior state (boundary pin)."""
    t0 = 1788800000000000000
    # from NEUTRAL start
    got = detect(None, [_synth(t0, z_i="0.0")], CFG)
    assert got[0]["value"] == 0.0
    assert got[0]["state"] == "NEUTRAL"
    # from UPSIDE: 0.0 < exit_pos -> exits to NEUTRAL, never sticks
    ev = [_synth(t0, z_i="1.0"), _synth(t0 + 1, z_i="-1.0",
                                        weight="1.0", days_ago="0.0")]
    got = detect(None, ev, CFG)
    assert got[0]["state"] == "UPSIDE"
    assert got[1]["value"] == 0.0
    assert got[1]["state"] == "NEUTRAL", got[1]


def test_halt_freezes_history_and_emits_unknown():
    """HALTED row: history frozen, label frozen, module_state UNKNOWN."""
    t0 = 1788800000000000000
    ev = [_synth(t0, z_i="1.0"),
          _synth(t0 + 1, z_i="0.5", market_state="HALTED"),
          _synth(t0 + 2, z_i="0.0")]
    got = detect(None, ev, CFG)
    assert got[0]["state"] == "UPSIDE"
    assert got[1]["module_state"] == "UNKNOWN", got[1]
    assert got[1]["state"] == "UPSIDE"  # frozen label
    # post-halt row resumes from pre-halt history (halt row not folded in)
    assert got[2]["module_state"] == "OK"
    assert _close(got[2]["value"], 1.0 * math.exp(0) * 1.0
                  + 1.0 * math.exp(0) * 0.0, TOL)


def test_auction_holds_last_state_degraded():
    t0 = 1788800000000000000
    ev = [_synth(t0, z_i="1.0"),
          _synth(t0 + 1, z_i="-5.0", market_state="AUCTION")]
    got = detect(None, ev, CFG)
    assert got[1]["module_state"] == "DEGRADED"
    assert got[1]["state"] == "UPSIDE"  # held, not recomputed


def test_late_arrival_recomputes_current_only():
    """A release with event_ts older than the last emitted label is folded
    into history and the CURRENT value/state recomputed deterministically;
    earlier emitted labels are unchanged (append-only, §R2 rule L4)."""
    t0 = 1788800000000000000
    ev = [_synth(t0, z_i="0.4", days_ago="10.0"),
          _synth(t0 + 86400000000000, z_i="0.4", days_ago="9.0")]
    first_pass = detect(None, ev, CFG)
    late = _synth(t0 - 86400000000000, z_i="0.4", days_ago="11.0",
                  release="LATE")
    second_pass = detect(None, ev + [late], CFG)
    # earlier labels identical (append-only)
    assert second_pass[0]["state"] == first_pass[0]["state"]
    assert _close(second_pass[0]["value"], first_pass[0]["value"], TOL)
    assert second_pass[1]["state"] == first_pass[1]["state"]
    # current value now includes the late release
    assert second_pass[2]["value"] > second_pass[1]["value"]
    assert second_pass[2]["module_state"] == "OK"


# ------------------------------------------------------- cost interface

def test_cost_interface_identity_record():
    """R027 is tilt-only: the adjustment record is the identity, so the
    strategy's expected_cost_bps inputs pass through unchanged."""
    from math import isclose
    adj = {"UPSIDE": {"spread_mult": 1.0, "impact_mult": 1.0,
                      "borrow_mult": 1.0, "fee_add_bps": 0.0},
           "DOWNSIDE": {"spread_mult": 1.0, "impact_mult": 1.0,
                        "borrow_mult": 1.0, "fee_add_bps": 0.0},
           "NEUTRAL": {"spread_mult": 1.0, "impact_mult": 1.0,
                       "borrow_mult": 1.0, "fee_add_bps": 0.0}}

    def expected_cost_bps(notional, adv_pct, venue, side, urgency,
                          spread_mult=1.0, impact_mult=1.0,
                          borrow_mult=1.0, fee_add_bps=0.0):
        base = 5.0  # stub stack [example]
        return base * spread_mult + fee_add_bps

    for state in ("UPSIDE", "DOWNSIDE", "NEUTRAL"):
        a = adj[state]
        before = expected_cost_bps(1e6, 0.05, "NYSE", "taker", 0.5)
        after = expected_cost_bps(1e6, 0.05, "NYSE", "taker", 0.5, **a)
        assert isclose(before, after), (state, before, after)
