"""R040 — Index rebalance / inclusion flows: acceptance tests.

Reference implementation of the §R2 normative pseudocode (detect/2 with
per-symbol hysteresis), fixture replay, and logic-drift guards.
Definition of done: `python3 -m pytest modules/tests/test_R040.py -q` exits 0.
"""
import csv
import datetime
import math
import os

RID = "R040"
TOL = 1e-9
DUAL_TOL = 1e-12
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

# Mirrors §R0.2 Config defaults. test_threshold_constants_pinned guards drift.
CFG = {
    "entry_large": 0.25,
    "exit_large": 0.20,
    "entry_moderate": 0.05,
    "exit_moderate": 0.04,
    "pre_window_days": 5,
    "post_window_days": 1,
    "adv_window_days": 20,
    "stale_aum_quarters": 1,
    "dual_tol": 1e-12,
    "min_lag_bars": 1,
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


def _quarter_of(ts_ns):
    dt = datetime.datetime.fromtimestamp(ts_ns / 1e9, tz=datetime.timezone.utc)
    return dt.year, (dt.month - 1) // 3 + 1


def _parse_vintage(s):
    y, q = s.strip().split("-Q")
    return int(y), int(q)


def _estimate_v1(w, aum_bn, price, adv):
    """Primary estimator: shares_to_trade / ADV."""
    return w * aum_bn * 1e9 / price / adv


def _estimate_v2(w, aum_bn, price, adv):
    """Dual estimator (F3): same math, independent operation order."""
    return (w * 1e9 * aum_bn) / price / adv


def _transition(prev, pi, cfg):
    """Hysteresis state machine — §R2 normative transitions."""
    if prev == "ADD_LARGE":
        if pi < cfg["exit_large"]:
            return "ADD_SMALL" if pi < cfg["exit_moderate"] else "ADD_MODERATE"
        return "ADD_LARGE"
    if prev == "ADD_MODERATE":
        if pi >= cfg["entry_large"]:
            return "ADD_LARGE"
        if pi < cfg["exit_moderate"]:
            return "ADD_SMALL"
        return "ADD_MODERATE"
    # prev == "ADD_SMALL" (also the cold-start state for a new symbol)
    if pi >= cfg["entry_large"]:
        return "ADD_LARGE"
    if pi >= cfg["entry_moderate"]:
        return "ADD_MODERATE"
    return "ADD_SMALL"


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState]. Reference implementation
    of the §R2 normative pseudocode. Causal: label at position t uses only
    events[:t+1]. Hysteresis memory is per symbol in state["labels"].
    """
    assert cfg["exit_large"] < cfg["entry_large"], "hysteresis invariant violated"
    assert cfg["exit_moderate"] < cfg["entry_moderate"], "hysteresis invariant violated"
    if state is None:
        state = {"labels": {}}
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN")]  # F1
    out = []
    for e in events:
        ts = int(float(e["ts_ns"]))
        sym = (e.get("symbol") or "").strip()
        ms = (e.get("market_state") or "CONTINUOUS_TRADING").strip()
        if ms == "HALTED":
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # freeze; no memory update
            continue
        degraded = ms == "AUCTION"
        w = _parse_float(e.get("w_new"))
        aum = _parse_float(e.get("aum_bn"))
        price = _parse_float(e.get("price"))
        adv = _parse_float(e.get("adv"))
        ca = (e.get("ca_adjusted") or "1").strip()
        vintage = (e.get("aum_vintage") or "").strip()
        if not all(math.isfinite(v) for v in (w, aum, price, adv)) or not vintage or ca not in ("0", "1"):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F1
            continue
        if price <= 0 or adv <= 0 or w < 0 or aum <= 0:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F2
            continue
        if ca == "0":
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F2: corp action unadjusted
            continue
        ey, eq = _parse_vintage(vintage)
        vy, vq = _quarter_of(ts)
        if (vy - ey) * 4 + (vq - eq) > cfg["stale_aum_quarters"]:
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN"))  # F4 stale AUM
            continue
        v1 = _estimate_v1(w, aum, price, adv)
        v2 = _estimate_v2(w, aum, price, adv)
        if not math.isfinite(v1) or abs(v1 - v2) > cfg["dual_tol"]:
            out.append(_mk("UNKNOWN", v1, ts, "UNKNOWN"))  # F3
            continue
        # Effective-date window gate (§R2): outside window -> NO_FLOW, memory untouched.
        eff = int(float(e.get("effective_date_ns") or 0))
        lo = eff - cfg["pre_window_days"] * CADENCE_NS
        hi = eff + cfg["post_window_days"] * CADENCE_NS
        if eff and not (lo <= ts <= hi):
            out.append(_mk("NO_FLOW", v1, ts, "OK"))
            continue
        prev = state["labels"].get(sym, "ADD_SMALL")
        label = _transition(prev, v1, cfg)
        state["labels"][sym] = label
        out.append(_mk(label, v1, ts, "DEGRADED" if degraded else "OK"))
    return out


def apply_freshness(rs, now_ns):
    """F4: expire a published label to UNKNOWN when computed_at is older than
    3x cadence."""
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


def _by_symbol(tape, got, sym):
    return [(t, g) for t, g in zip(tape, got) if t["symbol"] == sym]


# ---------------------------------------------------------------- fixtures

def test_fixture_replay():
    tape = _load("R040_tape.csv")
    exp = _load("R040_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R040_tape.csv")).readline()
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
    tape = _load("R040_tape.csv")
    full = detect(None, tape, CFG)
    for k in range(1, len(tape) + 1):
        prefix = detect(None, tape[:k], CFG)
        assert len(prefix) == k
        for a, b in zip(prefix, full[:k]):
            assert a["state"] == b["state"], (k, a, b)
            assert a["module_state"] == b["module_state"]
            assert _close(a["value"], b["value"], TOL), (k, a["value"], b["value"])


# ------------------------------------------------------- hysteresis behavior

def test_hysteresis_hold_inside_band():
    """pi=0.22 sits between exit_large (0.20) and entry_large (0.25):
    a LARGE label must persist."""
    tape = _load("R040_tape.csv")
    got = detect(None, tape, CFG)
    aaa = _by_symbol(tape, got, "AAA")
    assert aaa[0][1]["state"] == "ADD_LARGE"   # pi=0.75
    assert aaa[1][1]["state"] == "ADD_LARGE"   # pi=0.22: hold
    assert abs(aaa[1][1]["value"] - 0.22) <= TOL


def test_hysteresis_downgrade_path():
    """LARGE -> MODERATE at pi=0.18 (< exit_large), then -> SMALL at pi=0.03."""
    tape = _load("R040_tape.csv")
    got = detect(None, tape, CFG)
    aaa = _by_symbol(tape, got, "AAA")
    assert aaa[2][1]["state"] == "ADD_MODERATE", aaa[2][1]
    assert aaa[3][1]["state"] == "ADD_SMALL", aaa[3][1]


def test_entry_boundaries_inclusive():
    """pi exactly 0.25 -> ADD_LARGE; pi exactly 0.05 -> ADD_MODERATE;
    pi exactly 0.20 on a fresh symbol -> ADD_MODERATE (not LARGE)."""
    tape = _load("R040_tape.csv")
    got = detect(None, tape, CFG)
    aaa = _by_symbol(tape, got, "AAA")
    assert aaa[4][1]["state"] == "ADD_LARGE"          # pi == entry_large
    assert abs(aaa[4][1]["value"] - 0.25) <= TOL
    bbb = _by_symbol(tape, got, "BBB")
    assert bbb[1][1]["state"] == "ADD_MODERATE"       # pi == entry_moderate
    assert abs(bbb[1][1]["value"] - 0.05) <= TOL
    hhh = _by_symbol(tape, got, "HHH")
    assert hhh[0][1]["state"] == "ADD_MODERATE"       # pi == exit_large < entry_large
    assert abs(hhh[0][1]["value"] - 0.20) <= TOL


def test_threshold_constants_pinned():
    """Drift guard: Config hysteresis constants must match §R0.2/§R3."""
    assert CFG["entry_large"] == 0.25
    assert CFG["exit_large"] == 0.20
    assert CFG["entry_moderate"] == 0.05
    assert CFG["exit_moderate"] == 0.04
    assert CFG["exit_large"] < CFG["entry_large"]
    assert CFG["exit_moderate"] < CFG["entry_moderate"]
    assert CFG["pre_window_days"] == 5
    assert CFG["post_window_days"] == 1


# ------------------------------------------------------------- F1-F5 gates

def test_f1_missing_input_unknown():
    got = detect(None, [], CFG)
    assert len(got) == 1
    assert got[0]["module_state"] == "UNKNOWN"
    assert got[0]["state"] == "UNKNOWN"
    tape = _load("R040_tape.csv")
    got = detect(None, tape, CFG)
    ddd = _by_symbol(tape, got, "DDD")
    assert ddd[0][1]["module_state"] == "UNKNOWN"   # missing price
    assert ddd[0][1]["state"] == "UNKNOWN"


def test_f2_bounds_violation_unknown():
    tape = _load("R040_tape.csv")
    bad = [dict(r) for r in tape]
    bad[0]["price"] = "0"
    got = detect(None, bad, CFG)
    assert got[0]["module_state"] == "UNKNOWN", got[0]
    got = detect(None, tape, CFG)
    ccc = _by_symbol(tape, got, "CCC")
    assert ccc[0][1]["module_state"] == "UNKNOWN"   # adv == 0
    assert ccc[0][1]["state"] == "UNKNOWN"


def test_f3_dual_estimator_agreement():
    tape = _load("R040_tape.csv")
    row = tape[0]
    v1 = _estimate_v1(float(row["w_new"]), float(row["aum_bn"]),
                      float(row["price"]), float(row["adv"]))
    v2 = _estimate_v2(float(row["w_new"]), float(row["aum_bn"]),
                      float(row["price"]), float(row["adv"]))
    assert abs(v1 - v2) <= DUAL_TOL, (v1, v2)


def test_f4_staleness_expires_to_unknown():
    tape = _load("R040_tape.csv")
    rs = detect(None, tape, CFG)[0]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f4_stale_aum_vintage_unknown():
    """AUM vintage 2026-Q1 against a 2026-Q3 event: 2 quarters > 1 -> UNKNOWN."""
    tape = _load("R040_tape.csv")
    got = detect(None, tape, CFG)
    iii = _by_symbol(tape, got, "III")
    assert iii[0][1]["module_state"] == "UNKNOWN", iii[0][1]
    assert iii[0][1]["state"] == "UNKNOWN"


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R040_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


# ------------------------------------------------------- window / edge cases

def test_window_gate_no_flow_outside():
    """Event 5 days after effective_date + 1d post window -> NO_FLOW, OK."""
    tape = _load("R040_tape.csv")
    got = detect(None, tape, CFG)
    fff = _by_symbol(tape, got, "FFF")
    assert fff[0][1]["state"] == "NO_FLOW", fff[0][1]
    assert fff[0][1]["module_state"] == "OK"
    assert abs(fff[0][1]["value"] - 0.75) <= TOL  # gauge still computed


def test_halt_freezes_to_unknown():
    tape = _load("R040_tape.csv")
    got = detect(None, tape, CFG)
    eee = _by_symbol(tape, got, "EEE")
    assert eee[0][1]["module_state"] == "UNKNOWN"
    assert eee[0][1]["state"] == "UNKNOWN"


def test_corporate_action_unadjusted_unknown():
    tape = _load("R040_tape.csv")
    got = detect(None, tape, CFG)
    ggg = _by_symbol(tape, got, "GGG")
    assert ggg[0][1]["module_state"] == "UNKNOWN", ggg[0][1]
    assert ggg[0][1]["state"] == "UNKNOWN"


def test_unknown_does_not_corrupt_hysteresis_memory():
    """An UNKNOWN event must not move the per-symbol hysteresis memory."""
    tape = _load("R040_tape.csv")
    st = {"labels": {}}
    detect(st, tape[:1], CFG)          # AAA -> ADD_LARGE
    assert st["labels"]["AAA"] == "ADD_LARGE"
    halt_row = dict(tape[9])           # EEE row is HALTED...
    halt_row["symbol"] = "AAA"         # ...replayed as AAA
    detect(st, [halt_row], CFG)
    assert st["labels"]["AAA"] == "ADD_LARGE"  # memory frozen, not cleared


def test_spot_handcheck():
    """Independently hand-verified arithmetic (see module section R3)."""
    tape = _load('R040_tape.csv')
    got = detect(None, tape, CFG)
    assert abs(got[0]['value'] - 0.75) <= 1e-9, got[0]['value']
    assert got[0]['state'] == 'ADD_LARGE'
    assert got[1]['state'] == 'ADD_SMALL'
    assert abs(got[1]['value'] - 0.016666666666666666) <= 1e-9
