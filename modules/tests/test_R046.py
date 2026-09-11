"""R046 — Liquidity commonality: acceptance tests (reference implementation + checks).

Reference `detect()` implements the normative §R2.6 pseudocode of R046 v1.1.0:
causal trailing window, pairwise-complete Amihud-change correlations, entry/exit
hysteresis state machine, name-day exclusion (missing / non-finite /
unadjusted-jump), F3 dual-cut band agreement, halt freeze, warm-up DEGRADED.

Definition of done: `python3 -m pytest modules/tests/test_R046.py -q` exits 0.
"""
import csv
import math
import os
import statistics

RID = "R046"
TOL = 1e-9
ESTIMATOR_VERSION = "1.1.0"
CADENCE_NS = 86400000000000
DATA_VINTAGE = "2026-09-09"

CFG = {
    "common_entry": 0.40,   # [default] calibrate per §R2.5
    "common_exit": 0.30,    # [default] hysteresis exit
    "frag_entry": 0.15,     # [default] calibrate per §R2.5
    "frag_exit": 0.22,      # [default] hysteresis exit
    "W": 63,                # [default] trailing window (bars)
    "min_obs": 3,           # [default] warm-up: corr degenerate below 3 obs
    "min_pairs": 3,         # [default] need >= 3 valid pairs (F2)
    "min_pair_obs": 3,      # [default] per-pair observations
    "adj_jump_tol": 5.0,    # [default] |return| jump tolerance (decimal)
    "min_lag_bars": 1,      # [default]
}

NAMES = ["a%d" % i for i in range(1, 7)]
CUT = [1, 3, 5]  # F3 dual cut: interleaved half-universe (a2, a4, a6)

# Cost interface record (mirrors §R5 Cost interface block, v1.1.0)
COST_ADJUSTMENT_R046 = {
    "regime_id": "R046",
    "version": "1.1.0",
    "COMMON": {"spread_mult": 2.0, "impact_mult": 3.0, "borrow_mult": 1.0,
               "fee_add_bps": 0.0, "trade_ok": True, "applies_to": ["exit"],
               "tag": "[default]"},
    "MIXED": {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0,
              "fee_add_bps": 0.0, "trade_ok": True, "applies_to": ["exit"],
              "tag": "[default]"},
    "FRAGMENTED": {"spread_mult": 1.0, "impact_mult": 1.0, "borrow_mult": 1.0,
                   "fee_add_bps": 0.0, "trade_ok": True, "applies_to": ["exit"],
                   "tag": "[default]"},
    # UNKNOWN is restrictive: priced like the costly state, never benign.
    "UNKNOWN": {"spread_mult": 2.0, "impact_mult": 3.0, "borrow_mult": 1.0,
                "fee_add_bps": 0.0, "trade_ok": False, "applies_to": ["exit"],
                "tag": "[default]"},
}


def _parse_float(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _valid_day(e, i):
    """Name-day validity: finite value, and no unadjusted jump."""
    v = _parse_float(e.get(NAMES[i]))
    if v is None:
        return False
    j = _parse_float(e.get("j%d" % (i + 1)))  # |daily return|, optional
    if j is not None and j > CFG["adj_jump_tol"] and not e.get("adj_ok"):
        return False  # unadjusted corporate-action jump: bad data, exclude
    return True


def _pair_corr(xs, ys):
    n = len(xs)
    if n < CFG["min_pair_obs"]:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    vx = sum((a - mx) ** 2 for a in xs)
    vy = sum((b - my) ** 2 for b in ys)
    if vx <= 0 or vy <= 0:
        return None
    return cov / math.sqrt(vx * vy)


def _mean_pairwise_corr(window, sub):
    """Mean pairwise Pearson correlation over pairwise-complete observations."""
    series = {}
    for i in sub:
        s = []
        for r in window:
            if _valid_day(r, i):
                s.append(float(r[NAMES[i]]))
            else:
                s.append(None)
        series[i] = s
    ps = []
    idx = list(sub)
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            i, j = idx[a], idx[b]
            xy = [(x, y) for x, y in zip(series[i], series[j])
                  if x is not None and y is not None]
            if not xy:
                continue
            xs, ys = zip(*xy)
            c = _pair_corr(list(xs), list(ys))
            if c is not None:
                ps.append(c)
    if len(ps) < CFG["min_pairs"]:
        return None  # F2: insufficient valid pairs
    return sum(ps) / len(ps)


def _entry_band(v):
    if v >= CFG["common_entry"]:
        return "COMMON"
    if v <= CFG["frag_entry"]:
        return "FRAGMENTED"
    return "MIXED"


def next_state(prev, v):
    """Hysteresis state machine (§R2.7). Entry is strict; exit is sticky."""
    if v is None or not math.isfinite(v):
        return "UNKNOWN"
    if v >= CFG["common_entry"]:
        return "COMMON"  # spike promotes from any state
    if prev == "COMMON":
        if v >= CFG["common_exit"]:
            return "COMMON"  # hysteresis hold
        return "FRAGMENTED" if v <= CFG["frag_entry"] else "MIXED"
    if prev == "FRAGMENTED":
        return "FRAGMENTED" if v <= CFG["frag_exit"] else "MIXED"
    # prev in (None, "MIXED", "UNKNOWN"): entry bands decide
    if v <= CFG["frag_entry"]:
        return "FRAGMENTED"
    return "MIXED"


def _mk(state, value, ts_ns, module_state, reason=""):
    return {
        "regime_id": RID,
        "state": state,
        "value": value,
        "estimator_version": ESTIMATOR_VERSION,
        "data_vintage": DATA_VINTAGE,
        "computed_at": ts_ns,
        "module_state": module_state,
        "min_lag_bars": CFG["min_lag_bars"],
        "reason": reason,
    }


def detect(state, events, cfg):
    """detect(state, events, cfg) -> list[RegimeState]. Causal per prefix.

    F1: empty input -> UNKNOWN. F2: insufficient valid pairs -> UNKNOWN.
    F3: dual-cut band disagreement -> UNKNOWN. F4: staleness via
    apply_freshness. Warm-up (T < min_obs) -> DEGRADED, label withheld.
    HALTED rows freeze (label carried, module_state UNKNOWN); the halted row
    never enters the correlation history. Never interpolates.
    """
    if not events:
        return [_mk("UNKNOWN", float("nan"), 0, "UNKNOWN", "no-events")]  # F1
    out = []
    hist = []  # non-halted rows only
    prev_label, prev_value = None, float("nan")
    for e in events:
        ts = int(float(e["ts_ns"]))
        ms = (e.get("market_state") or "").strip().upper()
        if ms == "HALTED":
            # freeze: carry last label/value, module_state UNKNOWN; row excluded
            out.append(_mk(prev_label if prev_label else "UNKNOWN", prev_value,
                           ts, "UNKNOWN", "halted-freeze"))
            continue
        if ms == "AUCTION":
            out.append(_mk(prev_label if prev_label else "UNKNOWN", prev_value,
                           ts, "DEGRADED", "auction-hold"))
            continue
        hist.append(e)
        w_eff = min(len(hist), cfg["W"])
        window = hist[-w_eff:]
        if len(hist) < cfg["min_obs"]:
            out.append(_mk("UNKNOWN", float("nan"), ts, "DEGRADED", "warming"))
            continue
        value = _mean_pairwise_corr(window, list(range(6)))
        if value is None or not math.isfinite(value):
            out.append(_mk("UNKNOWN", float("nan"), ts, "UNKNOWN", "f2-no-pairs"))
            prev_label, prev_value = "UNKNOWN", float("nan")
            continue
        cut = _mean_pairwise_corr(window, CUT)
        if cut is None or _entry_band(cut) != _entry_band(value):
            out.append(_mk("UNKNOWN", value, ts, "UNKNOWN", "f3-cut-disagree"))
            prev_label, prev_value = "UNKNOWN", value
            continue
        label = next_state(prev_label, value)
        out.append(_mk(label, value, ts, "OK", ""))
        prev_label, prev_value = label, value
    return out


def apply_freshness(rs, now_ns):
    """F4: expire to UNKNOWN when computed_at is older than 3x cadence."""
    if rs["computed_at"] and (now_ns - rs["computed_at"]) > 3 * CADENCE_NS:
        rs = dict(rs)
        rs["module_state"] = "UNKNOWN"
        rs["state"] = "UNKNOWN"
        rs["reason"] = "stale"
    return rs


def cost_adjustment(state):
    """§R5 application rule: exit-leg multipliers; UNKNOWN is restrictive."""
    rec = COST_ADJUSTMENT_R046[state if state in COST_ADJUSTMENT_R046 else "UNKNOWN"]
    return dict(rec)


def _load(name):
    p = os.path.join(os.path.dirname(__file__), "..", "fixtures", name)
    with open(p) as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    return list(csv.DictReader(lines))


def _close(a, b, tol):
    if isinstance(a, float) and math.isnan(a):
        return isinstance(b, float) and math.isnan(b)
    if isinstance(b, float) and math.isnan(b):
        return False
    return abs(a - b) <= tol


# ---------------------------------------------------------------- fixtures
def test_fixture_replay():
    tape = _load("R046_tape.csv")
    exp = _load("R046_expected.csv")
    assert tape and exp, "fixtures must be non-empty"
    first = open(os.path.join(os.path.dirname(__file__), "..", "fixtures",
                              "R046_tape.csv")).readline()
    assert first.startswith("# TYPE: validation-run"), "tape needs TYPE header"
    got = detect(None, tape, CFG)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, x in zip(got, exp):
        assert g["state"] == x["state"], (g["state"], x["state"])
        assert g["module_state"] == x["module_state"], (g, x)
        xv = float(x["value"]) if x["value"].strip() else float("nan")
        assert _close(g["value"], xv, TOL), (g["value"], xv)


def test_fixture_state_path():
    """The tape pins the full lifecycle: warm-up, entry, hold, exit, freeze."""
    got = detect(None, _load("R046_tape.csv"), CFG)
    states = [g["state"] for g in got]
    assert states[0] == "UNKNOWN" and states[1] == "UNKNOWN"          # warm-up
    assert all(s == "FRAGMENTED" for s in states[2:7])
    assert states[7] == "COMMON"                                      # entry >= 0.40
    assert got[9]["module_state"] == "OK"                             # a3 missing: name-day
    assert all(s == "COMMON" for s in states[7:32])                   # hold + hysteresis
    assert all(s == "MIXED" for s in states[32:40])                   # exit < 0.30
    assert got[40]["module_state"] == "UNKNOWN"                      # HALTED freeze
    assert got[40]["state"] == "MIXED"                               # label carried
    assert _close(got[40]["value"], got[39]["value"], TOL)


def test_hysteresis_hold_vs_entry():
    """Same value band, different history: COMMON persists, MIXED does not enter."""
    got = detect(None, _load("R046_tape.csv"), CFG)
    # rows 29-32 (0-based 28-31): rho in [0.30, 0.40) yet COMMON persists
    for g in got[28:32]:
        assert 0.30 <= g["value"] < 0.40, g["value"]
        assert g["state"] == "COMMON", g
    # row 8 (0-based 7): rho 0.4375 >= entry -> direct promote FRAGMENTED -> COMMON
    assert got[7]["value"] >= 0.40
    assert got[7]["state"] == "COMMON"
    # row 33 (0-based 32): rho 0.2883 < exit -> COMMON exits to MIXED
    assert got[32]["value"] < 0.30
    assert got[32]["state"] == "MIXED"


def test_hysteresis_boundary_units():
    assert next_state("COMMON", 0.40) == "COMMON"
    assert next_state("COMMON", 0.30) == "COMMON"      # exit band inclusive
    assert next_state("COMMON", 0.299999) == "MIXED"   # just below exit -> exit
    assert next_state("MIXED", 0.40) == "COMMON"       # entry strict
    assert next_state("MIXED", 0.399999) == "MIXED"
    assert next_state("MIXED", 0.15) == "FRAGMENTED"   # frag entry inclusive
    assert next_state("MIXED", 0.150001) == "MIXED"
    assert next_state("FRAGMENTED", 0.22) == "FRAGMENTED"
    assert next_state("FRAGMENTED", 0.220001) == "MIXED"
    assert next_state("FRAGMENTED", 0.40) == "COMMON"  # spike promotes from any
    assert next_state(None, 0.5) == "COMMON"
    assert next_state(None, float("nan")) == "UNKNOWN"


def test_frag_entry_from_mixed_synthetic():
    """Anti-correlated panel -> FRAGMENTED even from a MIXED start."""
    series = {
        "a1": [-0.0248, -0.0100, 0.0278, 0.0155, -0.0229],
        "a2": [-0.0152, -0.0239, -0.0264, 0.0178, -0.0193],
        "a3": [0.0036, -0.0032, -0.0186, 0.0139, -0.0221],
        "a4": [0.0086, -0.0230, -0.0048, -0.0172, -0.0138],
        "a5": [0.0283, 0.0182, -0.0118, 0.0231, -0.0174],
        "a6": [-0.0063, 0.0213, 0.0085, -0.0240, 0.0294],
    }
    rows = []
    for t in range(5):
        r = {"ts_ns": str(1788465600000000000 + t * CADENCE_NS), "market_state": ""}
        for nm in NAMES:
            r[nm] = str(series[nm][t])
        rows.append(r)
    got = detect(None, rows, CFG)
    assert got[-1]["state"] == "FRAGMENTED", got[-1]
    assert got[-1]["value"] <= CFG["frag_entry"]


def test_no_lookahead():
    """The label at t must be identical with and without later data."""
    tape = _load("R046_tape.csv")
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


def test_warmup_degraded_not_unknown():
    tape = _load("R046_tape.csv")
    got = detect(None, tape[:2], CFG)
    assert all(g["module_state"] == "DEGRADED" for g in got)
    assert all(g["state"] == "UNKNOWN" for g in got)  # label withheld


def test_f2_insufficient_pairs_unknown():
    """< min_pairs valid pairs -> UNKNOWN, never interpolated."""
    tape = _load("R046_tape.csv")
    bad = [dict(r) for r in tape[:6]]
    for r in bad:
        for nm in NAMES[:4]:  # only a5, a6 survive -> 1 pair < 3
            r[nm] = ""
    got = detect(None, bad, CFG)
    assert got[-1]["module_state"] == "UNKNOWN", got[-1]
    assert got[-1]["state"] == "UNKNOWN"


def test_zero_volume_name_day_exclusion():
    """A missing name-day is excluded from its pairs; the panel survives."""
    tape = _load("R046_tape.csv")
    got = detect(None, tape, CFG)
    g = got[9]  # fixture row 10: a3 missing
    assert g["module_state"] == "OK", g
    assert g["state"] == "COMMON", g


def test_f3_dual_cut_agreement_on_fixture():
    for g in detect(None, _load("R046_tape.csv"), CFG):
        assert g["reason"] != "f3-cut-disagree", g


def test_f3_cut_disagreement_unknown_synthetic():
    """Cut concentrated on divergent names -> band disagreement -> UNKNOWN."""
    rows = []
    base = 1788465600000000000
    # odd names (a1,a3,a5) co-move; even names (a2,a4,a6 = the F3 cut) diverge
    series = {
        "a1": [0.0102, 0.0213, 0.0290, 0.0397, 0.0516],
        "a2": [-0.0033, -0.0094, 0.0235, 0.0188, 0.0237],
        "a3": [0.0108, 0.0197, 0.0308, 0.0413, 0.0506],
        "a4": [-0.0157, -0.0123, -0.0054, 0.0163, 0.0034],
        "a5": [0.0102, 0.0213, 0.0284, 0.0405, 0.0493],
        "a6": [0.0036, 0.0201, -0.0151, 0.0271, -0.0253],
    }
    for t in range(5):
        r = {"ts_ns": str(base + t * CADENCE_NS), "market_state": ""}
        for nm in NAMES:
            r[nm] = str(series[nm][t])
        rows.append(r)
    got = detect(None, rows, CFG)
    assert got[-1]["reason"] == "f3-cut-disagree", got[-1]
    assert got[-1]["module_state"] == "UNKNOWN"


def test_corporate_action_guard():
    """Unadjusted jump day is excluded like a bad name-day; adjusted is kept."""
    rows = []
    base = 1788465600000000000
    for t in range(5):
        r = {"ts_ns": str(base + t * CADENCE_NS), "market_state": ""}
        for i, nm in enumerate(NAMES):
            # heterogeneous series so that excluding one name-day moves the value
            r[nm] = str(round(0.01 * (t + 1) + 0.002 * i * ((-1) ** t), 6))
            r["j%d" % (i + 1)] = "0.02"
        rows.append(r)
    rows[4]["j1"] = "9.0"  # 900% one-day move, no adj_factor -> bad data
    got = detect(None, rows, CFG)
    assert got[-1]["module_state"] == "OK"
    # equivalence: same as if a1's day-5 cell were missing
    rows2 = [dict(r) for r in rows]
    rows2[4]["a1"] = ""
    del rows2[4]["j1"]
    got2 = detect(None, rows2, CFG)
    assert _close(got[-1]["value"], got2[-1]["value"], TOL)
    # with adj_ok set, the jump day is kept -> different (unexcluded) value
    rows3 = [dict(r) for r in rows]
    rows3[4]["adj_ok"] = "1"
    got3 = detect(None, rows3, CFG)
    assert not _close(got[-1]["value"], got3[-1]["value"], 1e-12)


def test_halt_freeze_and_reopen_discards():
    tape = _load("R046_tape.csv")
    pre = detect(None, tape[:40], CFG)
    # HALTED row carries a bogus value; it must not contaminate history
    halted = [dict(r) for r in tape[:40]]
    halted.append({"ts_ns": str(int(tape[39]["ts_ns"]) + CADENCE_NS),
                   "market_state": "HALTED",
                   "a1": "0.9", "a2": "0.9", "a3": "0.9",
                   "a4": "0.9", "a5": "0.9", "a6": "0.9"})
    nxt = dict(halted[-1])
    nxt["market_state"] = ""
    nxt["ts_ns"] = str(int(nxt["ts_ns"]) + CADENCE_NS)
    for i, nm in enumerate(NAMES):  # clean continuation: copy of row-39 values
        nxt[nm] = tape[38][nm]
    halted.append(nxt)
    got = detect(None, halted, CFG)
    assert got[40]["module_state"] == "UNKNOWN"          # frozen
    assert got[40]["state"] == pre[-1]["state"]          # label carried
    assert _close(got[40]["value"], pre[-1]["value"], TOL)
    # the halted row was discarded: identical to a run that never saw it
    clean = [dict(r) for r in tape[:40]] + [dict(nxt)]
    ref = detect(None, clean, CFG)
    assert got[41]["module_state"] == ref[-1]["module_state"] == "OK"
    assert got[41]["state"] == ref[-1]["state"]
    assert _close(got[41]["value"], ref[-1]["value"], TOL)


def test_auction_hold_degraded():
    tape = _load("R046_tape.csv")
    rows = [dict(r) for r in tape[:20]]
    rows.append({"ts_ns": str(int(rows[-1]["ts_ns"]) + CADENCE_NS),
                 "market_state": "AUCTION"})
    got = detect(None, rows, CFG)
    assert got[-1]["module_state"] == "DEGRADED"
    assert got[-1]["state"] == got[-2]["state"]


def test_f4_staleness_expires_to_unknown():
    tape = _load("R046_tape.csv")
    rs = detect(None, tape[:40], CFG)[-1]
    assert rs["computed_at"] > 0
    aged = apply_freshness(rs, rs["computed_at"] + 4 * CADENCE_NS)
    assert aged["module_state"] == "UNKNOWN"
    assert aged["state"] == "UNKNOWN"
    fresh = apply_freshness(rs, rs["computed_at"] + CADENCE_NS)
    assert fresh["module_state"] == rs["module_state"]


def test_f5_no_expost_selection():
    assert not hasattr(detect, "select_backtest_periods")
    tape = _load("R046_tape.csv")
    for rs in detect(None, tape, CFG):
        assert rs["min_lag_bars"] >= 1
        assert rs["computed_at"] >= 0


def test_spot_handcheck():
    """Independent recomputation (statistics.correlation, pairwise-complete)."""
    tape = _load("R046_tape.csv")
    got = detect(None, tape, CFG)

    def indep(window):
        cols = [[float(r[nm]) if r[nm].strip() else None for r in window]
                 for nm in NAMES]
        ps = []
        for i in range(6):
            for j in range(i + 1, 6):
                xy = [(x, y) for x, y in zip(cols[i], cols[j])
                      if x is not None and y is not None]
                if len(xy) >= CFG["min_pair_obs"]:
                    xs, ys = zip(*xy)
                    ps.append(statistics.correlation(xs, ys))
        return sum(ps) / len(ps)

    for k, g in enumerate(got[:40]):  # exclude the HALTED freeze row
        if g["module_state"] == "OK":
            assert _close(g["value"], indep(tape[:k + 1]), 1e-9), (k, g["value"])
    # anchor: row 8 (entry bar) value pinned to 1e-6
    assert _close(got[7]["value"], 0.4374648, 1e-6), got[7]["value"]
    assert got[7]["state"] == "COMMON"
    assert got[0]["module_state"] == "DEGRADED"  # warm-up


def test_cost_interface_record():
    rec = COST_ADJUSTMENT_R046
    assert rec["version"] == "1.1.0" and rec["regime_id"] == "R046"
    common = cost_adjustment("COMMON")
    assert common["spread_mult"] == 2.0 and common["impact_mult"] == 3.0
    assert common["borrow_mult"] == 1.0 and common["fee_add_bps"] == 0.0
    assert common["applies_to"] == ["exit"] and common["trade_ok"] is True
    for s in ("MIXED", "FRAGMENTED"):
        adj = cost_adjustment(s)
        assert adj["spread_mult"] == 1.0 and adj["impact_mult"] == 1.0
        assert adj["trade_ok"] is True
    # UNKNOWN is restrictive: priced like the costly state, entries blocked
    unk = cost_adjustment("UNKNOWN")
    assert unk["spread_mult"] == 2.0 and unk["impact_mult"] == 3.0
    assert unk["trade_ok"] is False
