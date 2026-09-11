"""R034 — Energy / commodity shock regime: acceptance tests.

Reference implementation of the §R2 normative pseudocode (hysteresis state
machine, F1–F5 fail-safes), fixture replay, and logic-drift pins.
Definition of done: `python3 -m pytest modules/tests/test_R034.py -q` exits 0.
"""
import csv
import math
import os
import statistics

RID = "R034"
TOL = 1e-9
DUAL_TOL = 1e-12
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

# §R0.2 Config defaults (test_config_defaults_match_r02_table pins these).
CFG = {
    "H": 20,
    "z_entry": 2.0,
    "deadband": 0.5,
    "moments_window": 252,
    "moments_min_bars": 63,
    "staleness_mult": 3.0,
    "min_lag_bars": 1,
}

VALID_MODULE_STATES = {"OK", "DEGRADED", "UNKNOWN", "OFF"}


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
    """Per-bar shock z. Raises ValueError on invalid inputs (F1/F2)."""
    pn = _parse_float(e["P_now"])
    pt = _parse_float(e["P_then"])
    mu = _parse_float(e["mu_R"])
    sg = _parse_float(e["sigma_R"])
    if not math.isfinite(pn) or not math.isfinite(pt):
        raise ValueError("F1: missing/non-finite settlement")
    if pn <= 0 or pt <= 0:
        raise ValueError("F2: non-positive price (log undefined)")
    if not math.isfinite(mu) or not (math.isfinite(sg) and sg > 0):
        raise ValueError("F2: bad trailing moments")
    return (math.log(pn / pt) - mu) / sg


def _dual_row_value(e):
    """Alternate algebraic form of the same z (F3 dual-estimator guard)."""
    pn = _parse_float(e["P_now"])
    pt = _parse_float(e["P_then"])
    mu = _parse_float(e["mu_R"])
    sg = _parse_float(e["sigma_R"])
    if pn <= 0 or pt <= 0 or sg <= 0:
        raise ValueError("bad inputs")
    return (math.log(pn) - math.log(pt) - mu) / sg


def transition(prev, z, cfg):
    """Hysteresis state machine (normative, §R2.2)."""
    assert cfg["z_entry"] - cfg["deadband"] > 0, "startup assertion: deadband must not swallow the entry band"
    up_out = cfg["z_entry"] - cfg["deadband"]
    if prev == "SHOCK_UP":
        return "NORMAL" if z <= up_out else "SHOCK_UP"
    if prev == "SHOCK_DOWN":
        return "NORMAL" if z >= -up_out else "SHOCK_DOWN"
    if z >= cfg["z_entry"]:
        return "SHOCK_UP"
    if z <= -cfg["z_entry"]:
        return "SHOCK_DOWN"
    return "NORMAL"


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState].

    Causal: the label at position t uses only events[:t+1] plus the carried
    hysteresis label. Empty input -> UNKNOWN (F1); unparseable row -> UNKNOWN
    (F1); out-of-bounds indicator values -> UNKNOWN (F2); halted bar -> freeze
    label/value and emit UNKNOWN (§R0.5). Never interpolates.
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    prev_label = (state or {}).get("label", "NORMAL")
    prev_value = (state or {}).get("shock_z", 0.0)
    out = []
    for e in events:
        ts = int(float(e["ts_ns"]))
        if str(e.get("halt", "0")).strip() == "1":
            # §R0.5 HALTED: freeze state, emit UNKNOWN, discard contributions.
            out.append(_mk(prev_label, prev_value, ts, "UNKNOWN"))
            continue
        try:
            z = _row_value(e)
        except ValueError:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1/F2
            continue
        if not math.isfinite(z):
            out.append(_mk("UNKNOWN", z, ts, "UNKNOWN"))  # F2
            continue
        prev_label = transition(prev_label, z, cfg)
        prev_value = z
        out.append(_mk(prev_label, z, ts, "OK"))
    return out


def trailing_moments(returns, cfg):
    """Normative §R3.2 estimator: leave-one-out trailing mean/sd of the last
    `moments_window` H-day log returns. Returns (mu, sd, module_state)."""
    hist = [r for r in returns if math.isfinite(r)]
    if len(hist) < cfg["moments_min_bars"]:
        return None, None, "DEGRADED"  # warming: label withheld
    win = hist[-cfg["moments_window"]:]
    mu = statistics.fmean(win)
    sd = statistics.stdev(win) if len(win) > 1 else 0.0
    if sd <= 0:
        return mu, None, "UNKNOWN"  # F2: degenerate history
    return mu, sd, "OK"


def back_adjust(prices, rolls):
    """Normative §R3.1 arithmetic back-adjustment.

    prices: list of (ts, contract_id, price) ascending — one bar per ts, the
      roll-date bar already taken from the NEW contract.
    rolls: list of (roll_ts, old_id, old_close, new_id, new_close); roll_ts is
      the first ts sourced from the new contract.
    Returns list of (ts, adjusted_price) in current-contract terms: every bar
    strictly before roll_ts is shifted by (new_close - old_close), compounded
    across rolls. Bars on/after a roll are already in new-contract terms and
    take no adjustment.
    """
    out = []
    for ts, cid, px in prices:
        adj = sum(new_c - old_c for (rts, _o, old_c, _n, new_c) in rolls if rts > ts)
        out.append((ts, px + adj))
    return out


def f3_agree(z_a, z_b, tol=0.25):
    """Second-vendor agreement (§R5): |Δz| within tol [example] or UNKNOWN."""
    if not (math.isfinite(z_a) and math.isfinite(z_b)):
        return False
    return abs(z_a - z_b) <= tol


def cost_adjustment(rsv, base):
    """§R5 cost interface: regime state -> cost-function adjustment."""
    adj = dict(base)
    adj["edge_mult"] = 1.0                      # [default]
    adj["tags"] = ["R034:" + rsv["state"]]      # provenance tag
    st, ms = rsv["state"], rsv["module_state"]
    if ms == "UNKNOWN":
        adj["trade_ok"] = False                 # [default] restrictive
        adj["edge_mult"] = 2.0                  # [example]
    elif ms == "DEGRADED":
        adj["trade_ok"] = False                 # [default] warming: block
        adj["edge_mult"] = 1.5                  # [example]
    elif st in ("SHOCK_UP", "SHOCK_DOWN"):
        adj["trade_ok"] = True
        adj["edge_mult"] = 2.0                              # [example]
        adj["spread_bps"] = base["spread_bps"] * 3.0        # [example]
        adj["impact_bps"] = base["impact_bps"] * 3.0        # [example]
        adj["borrow_bps"] = base["borrow_bps"] * 1.25       # [example]
    else:  # NORMAL
        adj["trade_ok"] = True                  # passthrough [default]
    return adj


def apply_freshness(rs, now_ns):
    """F4: expire to UNKNOWN when computed_at is older than staleness_mult x cadence."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > CFG["staleness_mult"] * CADENCE_NS:
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
    if isinstance(a, float) and math.isnan(a) or isinstance(b, float) and math.isnan(b):
        return (isinstance(a, float) and math.isnan(a)) and (isinstance(b, float) and math.isnan(b))
    return abs(a - b) <= tol


def _synth_row(z, ts=1790107200000000000):
    p = 70.0 * math.exp(z)
    return {"ts_ns": str(ts), "P_now": repr(p), "P_then": "70.0",
            "mu_R": "0.0", "sigma_R": "1.0", "halt": "0"}


def test_fixture_replay():
    tape = _load("R034_tape.csv")
    exp = _load("R034_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R034_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        xv = _parse_float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)


def test_state_sequence_pins_transitions():
    """The tape pins every transition class: entry, deadband hold, exact
    boundaries, no-direct-flip, halt freeze, missing -> UNKNOWN."""
    got = detect(None, _load("R034_tape.csv"), CFG)
    seq = [(g["state"], g["module_state"]) for g in got]
    assert seq == [
        ("SHOCK_UP", "OK"),     # z=2.59 entry
        ("NORMAL", "OK"),       # z=0.30 exit
        ("NORMAL", "OK"),       # z=1.8 below entry
        ("SHOCK_UP", "OK"),     # z=2.1 entry
        ("SHOCK_UP", "OK"),     # z=1.8 deadband HOLD (same z as 2 rows up, other label)
        ("NORMAL", "OK"),       # z=1.5 exact exit boundary
        ("SHOCK_UP", "OK"),     # z=2.0 exact entry boundary
        ("NORMAL", "OK"),       # z=-2.5: no direct SHOCK_UP -> SHOCK_DOWN flip
        ("SHOCK_DOWN", "OK"),   # z=-2.5 downside entry
        ("SHOCK_DOWN", "OK"),   # z=-1.6 downside deadband HOLD
        ("NORMAL", "OK"),       # z=-1.4 downside exit
        ("NORMAL", "UNKNOWN"),  # halted bar: label frozen, module UNKNOWN
        ("UNKNOWN", "UNKNOWN"), # missing settlement: UNKNOWN
    ]
    # Hysteresis kills stateless implementations: same z, different label.
    assert got[2]["value"] == got[4]["value"]
    assert got[2]["state"] != got[4]["state"]
    # Halt freeze: value held, not recomputed.
    assert got[11]["value"] == got[10]["value"]


def test_entry_exit_boundary_pins():
    """Exact-band behavior is normative (§R2.2): entry at z >= z_entry,
    exit at z <= z_entry - deadband."""
    assert transition("NORMAL", 2.0, CFG) == "SHOCK_UP"
    assert transition("NORMAL", 1.9999, CFG) == "NORMAL"
    assert transition("SHOCK_UP", 1.5, CFG) == "NORMAL"
    assert transition("SHOCK_UP", 1.5001, CFG) == "SHOCK_UP"
    assert transition("NORMAL", -2.0, CFG) == "SHOCK_DOWN"
    assert transition("SHOCK_DOWN", -1.5, CFG) == "NORMAL"
    assert transition("SHOCK_DOWN", -1.5001, CFG) == "SHOCK_DOWN"


def test_no_direct_shock_flip():
    """A swing from SHOCK_UP to a deep negative z passes through NORMAL —
    the machine never flips polarity in one bar (§R2.2)."""
    assert transition("SHOCK_UP", -3.0, CFG) == "NORMAL"
    assert transition("SHOCK_DOWN", 3.0, CFG) == "NORMAL"


def test_halt_freeze():
    rows = [_synth_row(2.5), _synth_row(0.1, 1790193600000000000)]
    rows[1]["halt"] = "1"
    got = detect(None, rows, CFG)
    assert got[0]["state"] == "SHOCK_UP" and got[0]["module_state"] == "OK"
    assert got[1]["module_state"] == "UNKNOWN"
    assert got[1]["state"] == "SHOCK_UP"      # label frozen
    assert got[1]["value"] == got[0]["value"]  # value frozen, no contribution


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R034_tape.csv")
    full = detect(None, tape, CFG)
    for k in range(1, len(tape) + 1):
        prefix = detect(None, tape[:k], CFG)
        assert len(prefix) == k
        for a, b in zip(prefix, full[:k]):
            assert a["state"] == b["state"], (k, a, b)
            assert a["module_state"] == b["module_state"]
            assert _close(a["value"], b["value"], TOL), (k, a["value"], b["value"])


def test_f1_empty_events_unknown():
    got = detect(None, [], CFG)
    assert len(got) == 1
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"


def test_f1_missing_bar_unknown():
    row = _synth_row(2.5)
    row["P_now"] = ""  # missing settlement
    got = detect(None, [row], CFG)
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"
    assert math.isnan(got[0]["value"])


def test_f2_bounds_violation_unknown():
    row = _synth_row(2.5)
    row["sigma_R"] = "0"
    got = detect(None, [row], CFG)
    assert got[0]["module_state"] == "UNKNOWN", got[0]
    neg = _synth_row(2.5)
    neg["P_now"] = "-37.63"  # negative print: log undefined -> UNKNOWN, never clipped
    got = detect(None, [neg], CFG)
    assert got[0]["module_state"] == "UNKNOWN"
    bad = _synth_row(2.5)
    bad["mu_R"] = "nan"
    got = detect(None, [bad], CFG)
    assert got[0]["module_state"] == "UNKNOWN"


def test_f3_dual_estimator_agreement():
    tape = _load("R034_tape.csv")
    for e in tape:
        if str(e.get("halt", "0")).strip() == "1" or not e["P_now"].strip():
            continue
        v1 = _row_value(e)
        v2 = _dual_row_value(e)
        assert _close(v1, v2, DUAL_TOL), (v1, v2)
    # Second-vendor agreement rule (§R5): |Δz| <= 0.25 [example] or UNKNOWN.
    assert f3_agree(2.6, 2.7) is True
    assert f3_agree(2.6, 3.0) is False
    assert f3_agree(2.6, float("nan")) is False


def test_f4_staleness_expires_to_unknown():
    tape = _load("R034_tape.csv")
    rs = detect(None, tape, CFG)[0]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R034_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_trailing_moments_handcheck():
    """Normative §R3.2 estimator, hand-computed:
    returns [0.01, -0.02, 0.03, -0.01, 0.02], window=5 -> mean 0.006,
    sample sd sqrt(0.00172/4) = 0.0207364..."""
    cfg = dict(CFG, moments_window=5, moments_min_bars=5)
    mu, sd, ms = trailing_moments([0.01, -0.02, 0.03, -0.01, 0.02], cfg)
    assert ms == "OK"
    assert abs(mu - 0.006) <= 1e-12, mu
    assert abs(sd - 0.02073644135332772) <= 1e-9, sd
    # Leave-one-out: window caps history; older bars do not leak in.
    mu2, _, _ = trailing_moments([0.99] + [0.01, -0.02, 0.03, -0.01, 0.02], cfg)
    assert abs(mu2 - 0.006) <= 1e-12
    # Warm-up: too few bars -> DEGRADED, label withheld.
    mu3, sd3, ms3 = trailing_moments([0.01, 0.02], cfg)
    assert ms3 == "DEGRADED" and mu3 is None and sd3 is None
    # Degenerate flat history -> UNKNOWN (F2), never a fake z.
    _, _, ms4 = trailing_moments([0.01] * 10, cfg)
    assert ms4 == "UNKNOWN"


def test_back_adjust_handcheck():
    """Normative §R3.1 arithmetic back-adjustment, hand-computed.
    Roll at t=2: old close 71, new close 73 -> +2 applied to all earlier bars;
    the roll-date bar is taken from the new contract (B)."""
    prices = [(1, "A", 70.0), (2, "B", 73.0), (3, "B", 74.0)]
    rolls = [(2, "A", 71.0, "B", 73.0)]
    got = back_adjust(prices, rolls)
    assert got == [(1, 72.0), (2, 73.0), (3, 74.0)], got
    # Two rolls compound arithmetically (roll_ts = first bar of the new contract).
    prices2 = [(1, "A", 70.0), (2, "B", 73.0), (3, "C", 76.0)]
    rolls2 = [(2, "A", 70.0, "B", 72.0), (3, "B", 73.0, "C", 76.0)]
    got2 = back_adjust(prices2, rolls2)
    assert got2 == [(1, 75.0), (2, 76.0), (3, 76.0)], got2


def test_cost_interface():
    """§R5 multipliers pinned per state; UNKNOWN/DEGRADED block entries."""
    base = {"spread_bps": 2.0, "impact_bps": 4.0, "borrow_bps": 30.0}
    shock = cost_adjustment(_mk("SHOCK_UP", 2.5, 1, "OK"), base)
    assert shock["trade_ok"] is True
    assert shock["edge_mult"] == 2.0
    assert shock["spread_bps"] == 6.0 and shock["impact_bps"] == 12.0
    assert shock["borrow_bps"] == 37.5
    assert shock["tags"] == ["R034:SHOCK_UP"]
    down = cost_adjustment(_mk("SHOCK_DOWN", -2.5, 1, "OK"), base)
    assert down["spread_bps"] == 6.0 and down["edge_mult"] == 2.0
    normal = cost_adjustment(_mk("NORMAL", 0.3, 1, "OK"), base)
    assert normal["trade_ok"] is True and normal["edge_mult"] == 1.0
    assert normal["spread_bps"] == 2.0  # passthrough
    unk = cost_adjustment(_mk("UNKNOWN", float("nan"), 1, "UNKNOWN"), base)
    assert unk["trade_ok"] is False and unk["edge_mult"] == 2.0
    deg = cost_adjustment(_mk("warming", 0.0, 1, "DEGRADED"), base)
    assert deg["trade_ok"] is False and deg["edge_mult"] == 1.5


def test_config_defaults_match_r02_table():
    assert CFG == {
        "H": 20, "z_entry": 2.0, "deadband": 0.5, "moments_window": 252,
        "moments_min_bars": 63, "staleness_mult": 3.0, "min_lag_bars": 1,
    }


def test_module_state_enum_valid():
    for rs in detect(None, _load("R034_tape.csv"), CFG):
        assert rs["module_state"] in VALID_MODULE_STATES, rs
        assert rs["estimator_version"] == ESTIMATOR_VERSION


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3):
    log(82.6/70)=0.165514..., (0.165514-0.01)/0.06=2.5919."""
    tape = _load("R034_tape.csv")
    got = detect(None, tape, CFG)
    assert abs(got[0]["value"] - 2.5919) <= 1e-3, got[0]["value"]
    assert got[0]["state"] == "SHOCK_UP"
    assert got[1]["state"] == "NORMAL"
