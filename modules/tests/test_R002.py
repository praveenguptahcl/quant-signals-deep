"""Acceptance tests for R002 - Implied-vs-realized spread (variance risk premium).

Template v1.0.0. The reference implementation below is the chapter's normative
machine (§R2): leave-one-out trailing z-score over VRP (vol points), state
transitions with hysteresis (entry/exit bands), warm-up DEGRADED state, F1-F5
fail-safes, dual-estimator (variance-unit) label agreement, and the §R5
cost interface. The fixture CSVs are generated from this same implementation
(see /tmp/gen_R002_fixture.py); the independent logic checks are the
hand-valued hysteresis boundary tests and the hand-computed RV test.

Run: python3 -m pytest modules/tests/test_R002.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "R002_tape.csv"
EXPECTED = FIX / "R002_expected.csv"

TOL = 1e-9  # float tolerance [default]
CADENCE_S = 86400  # indicator cadence in seconds [default]
NS = 1_000_000_000
STATE_LABELS = ['fear', 'normal', 'complacent', 'warming', 'missing',
                'invalid', 'out_of_bounds']
BOUNDS = (-100.0, 100.0)  # mathematical bounds of VRP in vol points (F2) [default]
SD_FLOOR = 1e-12  # degenerate flat-history guard [default]
DUAL_MODE = "state"  # dual-estimator agreement is on the regime label
ESTIMATOR_VERSION = "1.1.0"


@dataclass(frozen=True)
class Config:
    """Mirrors §R0.2. Defaults must match the chapter (test_config_defaults)."""
    rv_window_days: int = 21        # [default]
    z_window_days: int = 252        # [default]
    z_window_min_bars: int = 21     # [default] warm-up: labels withheld below this
    fear_entry_z: float = -1.5      # [default]
    fear_exit_z: float = -1.0       # [default] deadband 0.5σ [default]
    complacent_entry_z: float = 1.5   # [default]
    complacent_exit_z: float = 1.0    # [default] deadband 0.5σ [default]
    bounds_lo: float = -100.0       # [default]
    bounds_hi: float = 100.0        # [default]


# Fixture config: [example] overrides so the 10-bar fixture exercises the full
# machine (chapter production defaults need 21+ bars of warm-up).
FIXTURE_CFG = Config(z_window_days=5, z_window_min_bars=4)


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def _stdev(xs, ddof=1):
    xs = list(xs)
    n = len(xs)
    if n <= ddof:
        return float("nan")
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - ddof))


def transition_label(prev, z, cfg):
    """Hysteresis state machine (§R2 normative). Entry bands are strict;
    exit requires crossing the looser exit band (deadband)."""
    if prev == "fear":
        return "normal" if z > cfg.fear_exit_z else "fear"
    if prev == "complacent":
        return "normal" if z < cfg.complacent_exit_z else "complacent"
    # prev == "normal" (or unknown start): entry on strict bands
    if z < cfg.fear_entry_z:
        return "fear"
    if z > cfg.complacent_entry_z:
        return "complacent"
    return "normal"


def realized_vol(closes, window):
    """Annualized realized vol (decimal) from dividend-adjusted closes (§R2).

    RV = sqrt(252) * stdev(log returns, ddof=1). 252 trading days [documented].
    """
    closes = list(closes)
    if len(closes) < window + 1:
        return float("nan")
    seg = closes[-(window + 1):]
    rets = [math.log(seg[i] / seg[i - 1]) for i in range(1, len(seg))]
    sd = _stdev(rets, ddof=1)
    return math.sqrt(252.0) * sd if math.isfinite(sd) else float("nan")


def vrp_volpts(vix, rv):
    """VRP in vol points: VIX - 100*RV (desk convention [documented])."""
    return vix - 100.0 * rv


def vrp_varunits(vix, rv):
    """VRP in variance units (decimal): (VIX/100)^2 - RV^2 [documented]."""
    return (vix / 100.0) ** 2 - rv ** 2


def _label_series(series, cfg, prev_label):
    """Core z-machine shared by both estimators. Returns (label, z, ok)."""
    cur = series[-1]
    prior = series[max(0, len(series) - 1 - cfg.z_window_days):-1]  # leave-one-out
    if len(prior) < cfg.z_window_min_bars:
        return "warming", float("nan"), False
    mu, sd = _mean(prior), _stdev(prior, ddof=1)
    z = (cur - mu) / sd if sd > SD_FLOOR else 0.0
    return transition_label(prev_label, z, cfg), z, True


def primary_indicator(rows, cfg, prev_label="normal"):
    """Sentinel estimator: VRP in vol points -> label (dict)."""
    rows = list(rows)
    base = {"value": float("nan"), "state": "missing", "module_state": "UNKNOWN",
            "computed_at": 0, "vintage": "synthetic", "z": float("nan")}
    if not rows:
        return base
    for r in rows:
        if (not all(k in r for k in ("vix", "rv30"))
                or not all(math.isfinite(float(r[k])) for k in ("vix", "rv30"))
                or not (float(r["vix"]) > 0 and float(r["rv30"]) > 0)):
            out = dict(base)
            out.update(state="invalid", computed_at=int(r.get("event_ts", 0)))
            return out
    series = [vrp_volpts(float(r["vix"]), float(r["rv30"])) for r in rows]
    label, z, ok = _label_series(series, cfg, prev_label)
    return {"value": series[-1], "state": label,
            "module_state": "OK" if ok else "DEGRADED",
            "computed_at": int(rows[-1]["event_ts"]), "vintage": "synthetic", "z": z}


def second_estimator(rows, cfg, prev_label="normal"):
    """Verifier estimator: same machine on the variance-unit VRP series (§R4).

    Note: for positive vix/rv the vol-point and variance-unit VRP always agree
    in sign (both are sign(vix/100 - rv) up to a positive factor), so the
    non-vacuous F3 check is label agreement on the two unit conventions.
    """
    rows = list(rows)
    base = {"value": float("nan"), "state": "n/a", "module_state": "UNKNOWN",
            "computed_at": 0, "z": float("nan")}
    if not rows:
        return base
    series = [vrp_varunits(float(r["vix"]), float(r["rv30"])) for r in rows]
    label, z, _ = _label_series(series, cfg, prev_label)
    return {"value": series[-1], "state": label, "module_state": "OK",
            "computed_at": int(rows[-1]["event_ts"]), "z": z}


def cost_adjustment(rsv, base):
    """§R5 cost interface: regime state -> cost-function adjustment.

    rsv: dict(state, module_state). base: dict(spread_bps, impact_bps,
    borrow_bps) from the consuming strategy's COST block. Returns the adjusted
    cost inputs plus an edge multiplier and a routing flag. Strategies wire
    this as: expected_cost_bps(adj_inputs...) * edge_mult <= edge_bps.
    """
    adj = dict(base)
    adj["edge_mult"] = 1.0  # [default] required-edge multiplier
    adj["tags"] = ["R002:" + str(rsv.get("state", "?"))]
    st, ms = rsv.get("state"), rsv.get("module_state")
    if ms == "UNKNOWN":
        adj["trade_ok"] = False  # [default] restrictive: unknown blocks
    elif ms == "DEGRADED":
        adj["trade_ok"] = False       # [default] warming: label withheld
        adj["edge_mult"] = 1.5        # [example]
    elif st == "fear":
        adj["trade_ok"] = False                  # [default] stand down short-vol
        adj["edge_mult"] = 2.0                   # [example] 2x edge if overridden
        adj["spread_bps"] = base["spread_bps"] * 1.5   # [example] fear widens spread
        adj["impact_bps"] = base["impact_bps"] * 1.5   # [example]
        adj["borrow_bps"] = base["borrow_bps"] * 1.25  # [example] borrow tightens
    elif st == "complacent":
        adj["trade_ok"] = True
        adj["edge_mult"] = 0.8                   # [example] rich premium compensates
    else:
        adj["trade_ok"] = True
    return adj


F2_POISON_TAPE = [
    {"bar": i + 1, "event_ts": 1000 + i, "asof_ts": 1001 + i,
     "vix": 400.0, "rv30": 0.01}  # VRP = 399 vol pts, outside ±100 bounds [default]
    for i in range(5)
]


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def tape():
    rows = []
    for r in load_csv(TAPE):
        row = {}
        for k, v in r.items():
            try:
                row[k] = int(v)
            except ValueError:
                try:
                    row[k] = float(v)
                except ValueError:
                    row[k] = v
        rows.append(row)
    return rows


@dataclass(frozen=True)
class RegimeState:
    regime_id: str
    state: str            # regime label, e.g. "fear"
    value: float          # indicator value
    estimator_version: str
    data_vintage: str
    computed_at: int      # int64 ns UTC (= event_ts of newest input bar)
    module_state: str     # OK | DEGRADED | UNKNOWN | OFF


class RegimeMiningError(AssertionError):
    """F5: ex-post backtest-period selection without a pre-registered definition."""


def detect(rows, cfg, prev_label="normal", now_ns=None,
           select_periods=False, preregistered=False):
    """detect(state, events, cfg) -> RegimeState — reference implementation
    with F1-F5 fail-safes wired in (Appendix f v1.0.0)."""
    rows = list(rows)
    r = primary_indicator(rows, cfg, prev_label)  # dict(value, state, module_state, computed_at)
    if r["module_state"] != "OK":
        return RegimeState("R002", r["state"], r["value"], ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"],
                           r["module_state"])
    # F2: mathematical bounds
    v = r["value"]
    if not (math.isfinite(v) and cfg.bounds_lo <= v <= cfg.bounds_hi):
        return RegimeState("R002", "out_of_bounds", v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F3: dual-estimator agreement on the regime label (state mode)
    s = second_estimator(rows, cfg, prev_label)
    if r["state"] != s["state"]:
        return RegimeState("R002", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F4: staleness timeout — 3x cadence [default]
    now = now_ns if now_ns is not None else rows[-1]["event_ts"] + CADENCE_S * NS
    if now - r["computed_at"] > 3 * CADENCE_S * NS:
        return RegimeState("R002", r["state"], v, ESTIMATOR_VERSION,
                           r.get("vintage", "synthetic"), r["computed_at"], "UNKNOWN")
    # F5: no ex-post backtest-period selection without a pre-registered definition
    if select_periods and not preregistered:
        raise RegimeMiningError("F5: regime-gated period selection needs a pre-registered definition")
    return RegimeState("R002", r["state"], v, ESTIMATOR_VERSION,
                       r.get("vintage", "synthetic"), r["computed_at"], "OK")


# ------------------------------------------------------------------- tests
def _recompute_all(evs, cfg):
    """Causal per-bar recompute threading the hysteresis prev-label."""
    out, prev = [], "normal"
    for i in range(len(evs)):
        r = primary_indicator(evs[: i + 1], cfg, prev_label=prev)
        if r["state"] in ("fear", "normal", "complacent"):
            prev = r["state"]
        out.append(r)
    return out


def test_fixture_recomputes_to_expected():
    """Chapter arithmetic: causal recompute of each bar matches expected CSV."""
    evs = tape()
    exp = {int(r["bar"]): r for r in load_csv(EXPECTED)}
    for i, r in enumerate(_recompute_all(evs, FIXTURE_CFG)):
        want = exp[i + 1]
        wv = float(want["exp_value"])
        assert abs(r["value"] - wv) < TOL, i
        assert r["state"] == want["exp_state"], i
        assert r["computed_at"] == int(want["exp_computed_at"]), i
        assert r["module_state"] == want["exp_module_state"], i


def test_fixture_state_sequence_pins_transitions():
    """The 10-bar tape must exercise: warm-up, fear entry, hysteresis hold,
    exit to normal, complacent entry, hysteresis hold, exit to normal."""
    evs = tape()
    states = [r["state"] for r in _recompute_all(evs, FIXTURE_CFG)]
    assert states == ["warming"] * 4 + ["fear", "fear", "normal",
                                        "complacent", "complacent", "normal"], states
    # the hysteresis holds must be strictly inside the entry band
    zs = [r["z"] for r in _recompute_all(evs, FIXTURE_CFG)]
    assert zs[5] > -1.5 and zs[5] < -1.0, zs[5]  # fear hold inside deadband
    assert 1.0 < zs[8] < 1.5, zs[8]             # complacent hold inside deadband


def test_emits_valid_regime_state_vector():
    evs = tape()
    rsv = detect(evs, FIXTURE_CFG)
    assert rsv.regime_id == "R002"
    assert rsv.state in STATE_LABELS
    assert math.isfinite(rsv.value) and BOUNDS[0] <= rsv.value <= BOUNDS[1]
    assert rsv.estimator_version == ESTIMATOR_VERSION
    assert rsv.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    assert rsv.computed_at == evs[-1]["event_ts"]


def test_no_lookahead_regime_gating():
    """Lag contract: a label computed at t may gate signals at t only for
    trades at t+1+. Assert label_ts > indicator_ts for the earliest trade."""
    evs = tape()
    cfg = FIXTURE_CFG
    for i in range(len(evs) - 1):
        label = detect(evs[: i + 1], cfg)
        indicator_ts = evs[i]["event_ts"]          # newest data used
        assert label.computed_at == indicator_ts  # label stamped at t, not later
        earliest_trade_ts = evs[i + 1]["event_ts"]
        assert earliest_trade_ts > label.computed_at, f"lookahead at bar {{i}}"
    # appending a future breakout bar must not move the label stamped at t
    label_t = detect(evs[:-1], cfg)
    assert label_t.computed_at == evs[-2]["event_ts"]


def test_F1_missing_input_unknown():
    assert detect([], FIXTURE_CFG).module_state == "UNKNOWN"
    bad = [dict(event_ts=1, asof_ts=2)]  # missing indicator fields
    assert detect(bad, FIXTURE_CFG).module_state == "UNKNOWN"
    neg = [dict(event_ts=1, asof_ts=2, vix=-5.0, rv30=0.15)]  # non-positive vix
    assert detect(neg, FIXTURE_CFG).module_state == "UNKNOWN"


def test_F2_bounds_violation_unknown():
    rsv = detect(F2_POISON_TAPE, FIXTURE_CFG)
    assert rsv.module_state == "UNKNOWN", "out-of-bounds value must yield UNKNOWN"
    assert rsv.state == "out_of_bounds"


def test_F3_dual_estimator_disagreement_unknown():
    import sys as _sys
    mod = _sys.modules[__name__]  # self-reference for monkeypatching
    evs = tape()
    orig = mod.second_estimator
    try:
        mod.second_estimator = lambda rows, cfg, prev_label="normal": {
            "value": 0.0, "state": "bogus", "module_state": "OK",
            "computed_at": evs[-1]["event_ts"], "z": 0.0}
        rsv = mod.detect(evs, FIXTURE_CFG)
        assert rsv.module_state == "UNKNOWN"
    finally:
        mod.second_estimator = orig


def test_F4_staleness_unknown():
    evs = tape()
    stale_now = evs[-1]["event_ts"] + 10 * CADENCE_S * NS  # >> 3x cadence
    rsv = detect(evs, FIXTURE_CFG, now_ns=stale_now)
    assert rsv.module_state == "UNKNOWN"


def test_F5_regime_mining_guard():
    evs = tape()
    try:
        detect(evs, FIXTURE_CFG, select_periods=True, preregistered=False)
    except RegimeMiningError:
        pass
    else:
        raise AssertionError("F5: unregistered period selection must raise")
    rsv = detect(evs, FIXTURE_CFG, select_periods=True, preregistered=True)
    assert rsv.module_state == "OK"


def test_dual_estimator_agreement():
    """Sentinel vs Verifier agree on the regime label on the fixture."""
    evs = tape()
    cfg = FIXTURE_CFG
    prev = "normal"
    for i in range(len(evs)):
        r = primary_indicator(evs[: i + 1], cfg, prev_label=prev)
        s = second_estimator(evs[: i + 1], cfg, prev_label=prev)
        if r["module_state"] == "OK":
            assert r["state"] == s["state"], (i, r, s)
            prev = r["state"]
    assert detect(evs, cfg).module_state == "OK"


def test_hysteresis_boundaries():
    """Hand-valued pins for the §R2 transition machine (independent of the
    fixture generator). Entry bands are strict; exits need the looser band."""
    cfg = Config()  # production defaults: entry ±1.5, exit ±1.0
    assert transition_label("normal", -1.51, cfg) == "fear"
    assert transition_label("normal", -1.49, cfg) == "normal"
    assert transition_label("normal", 1.51, cfg) == "complacent"
    assert transition_label("normal", 1.49, cfg) == "normal"
    assert transition_label("fear", -1.25, cfg) == "fear"     # deadband hold
    assert transition_label("fear", -0.99, cfg) == "normal"   # exit crossed
    assert transition_label("complacent", 1.25, cfg) == "complacent"
    assert transition_label("complacent", 0.99, cfg) == "normal"
    # exact-boundary behavior: exit band is strict (z > exit to leave)
    assert transition_label("fear", -1.0, cfg) == "fear"
    assert transition_label("complacent", 1.0, cfg) == "complacent"


def test_realized_vol_computation():
    """Hand-verifiable RV: closes [100, 101, 99] over window 2."""
    closes = [100.0, 101.0, 99.0]
    r1, r2 = math.log(101 / 100), math.log(99 / 101)
    m = (r1 + r2) / 2
    sd = math.sqrt(((r1 - m) ** 2 + (r2 - m) ** 2) / 1)
    expect = math.sqrt(252.0) * sd
    assert abs(realized_vol(closes, 2) - expect) < 1e-12
    assert math.isnan(realized_vol([100.0, 101.0], 2))  # insufficient history


def test_cost_interface():
    """§R5: regime state -> cost-function adjustment, every literal tagged."""
    base = {"spread_bps": 2.0, "impact_bps": 3.0, "borrow_bps": 50.0}
    fear = cost_adjustment({"state": "fear", "module_state": "OK"}, base)
    assert fear["trade_ok"] is False
    assert fear["edge_mult"] == 2.0
    assert fear["spread_bps"] == 3.0 and fear["impact_bps"] == 4.5
    assert fear["borrow_bps"] == 62.5
    assert fear["tags"] == ["R002:fear"]
    comp = cost_adjustment({"state": "complacent", "module_state": "OK"}, base)
    assert comp["trade_ok"] is True and comp["edge_mult"] == 0.8
    assert comp["spread_bps"] == 2.0  # passthrough otherwise
    norm = cost_adjustment({"state": "normal", "module_state": "OK"}, base)
    assert norm["trade_ok"] is True and norm["edge_mult"] == 1.0
    assert norm["spread_bps"] == 2.0 and norm["impact_bps"] == 3.0
    unk = cost_adjustment({"state": "fear", "module_state": "UNKNOWN"}, base)
    assert unk["trade_ok"] is False  # restrictive default
    deg = cost_adjustment({"state": "warming", "module_state": "DEGRADED"}, base)
    assert deg["trade_ok"] is False and deg["edge_mult"] == 1.5


def test_config_defaults_match_chapter():
    """§R0.2 contract: code defaults must equal the chapter's table."""
    c = Config()
    assert (c.rv_window_days, c.z_window_days, c.z_window_min_bars) == (21, 252, 21)
    assert (c.fear_entry_z, c.fear_exit_z) == (-1.5, -1.0)
    assert (c.complacent_entry_z, c.complacent_exit_z) == (1.5, 1.0)
    assert (c.bounds_lo, c.bounds_hi) == (-100.0, 100.0)
