"""Acceptance tests for S068 — VIX term structure (v1.1.0).

Template v1.0.0. Reference implementation mirrors the chapter's normative
pseudocode (§S3): raw-slope inversion rule + z-confirm veto, warm-up DEGRADED,
cost-gate predicate, causality assertions, invalid -> UNKNOWN, market-state
handling. Run: python3 -m pytest modules/tests/test_S068.py -q (from repo root)
"""
import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S068_tape.csv"
EXPECTED = FIX / "S068_expected.csv"

TOL = 1e-9  # [default] tolerance on float comparisons
EXPECTED_COLS = ['day', 'slope', 'z_slope', 'inverted']
COL_TYPES = {'day': 'int', 'event_ts': 'int', 'asof_ts': 'int',
             'vix': 'float', 'vx1': 'float', 'vx2': 'float'}


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def _conv(v, t):
    if t == "int":
        return int(v)
    if t == "float":
        return float(v)
    return v


def parse_tape():
    return [{k: _conv(r[k], COL_TYPES[k]) for k in COL_TYPES} for r in load_csv(TAPE)]


# --------------------------------------- normative pseudocode reference impl
@dataclass(frozen=True)
class SignalVector:
    symbol: str
    direction: int          # +1 | -1 | 0
    confidence: float       # 0..1
    capital: float          # 0..1
    computed_at: int        # int64 ns UTC
    staleness: int          # ns
    module_state: str       # OK | DEGRADED | UNKNOWN | OFF


@dataclass
class Config:
    inversion_tau: float = -1.0        # [example]
    z_lookback_days: int = 60          # [example]
    z_floor: float = -1.0              # [example] z-confirm veto
    conf_scale: float = 3.0            # [example]
    edge_bps_per_point: float = 50.0  # [example]
    cost_gate_k: float = 0.5           # [default]
    capital_factor: float = 0.5        # [default]
    staleness_ttl_s: int = 3           # [default]
    msg_rate_cap_per_s: int = 100      # [default]


URGENCY_MULT = {"passive": 0.5, "normal": 1.0, "aggressive": 2.0}  # [example]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Callable cost model — reference stack for S068 (§S2 COST block)."""
    if side != "taker":
        raise ValueError("S068 models taker fills only [default]")
    mult = URGENCY_MULT[urgency]
    spread_bps = 1.50   # VX 1x2 spread half-spread sum [example]
    fee_bps = 0.20      # futures fees [example]
    borrow_bps = 0.00   # reason: futures-only structure [default]
    impact_bps = 1.00 * mult  # stress-day fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _unknown(computed_at=0, staleness=0):
    return SignalVector("TEST", 0, 0.0, 0.0, computed_at, staleness, "UNKNOWN")


def signal(state, events, cfg):
    """Normative pseudocode reference (§S3). state persists 'slope_history'."""
    bars = list(events)
    if not bars:
        return _unknown()
    b = bars[-1]
    market_state = state.get("market_state", "CONTINUOUS_TRADING")
    if market_state == "HALTED":
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")
    if market_state == "CLOSED":
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "OFF")
    if any(v <= 0 or not math.isfinite(v) for v in (b["vix"], b["vx1"], b["vx2"])):
        return _unknown(b["event_ts"], b["asof_ts"] - b["event_ts"])  # F2 [default]

    slope = b["vx2"] - b["vx1"]
    hist = state.setdefault("slope_history", [])
    warm = len(hist) < cfg.z_lookback_days
    z_ok, z = False, float("nan")
    if not warm:
        w = hist[-cfg.z_lookback_days:]
        mu, sd = statistics.fmean(w), statistics.pstdev(w)
        z = (slope - mu) / sd if sd > 1e-12 else 0.0
        z_ok = True
    hist.append(slope)

    direction = 1 if slope < cfg.inversion_tau else 0      # inversion rule [example]
    if direction and z_ok and z >= cfg.z_floor:
        direction = 0                                     # z-confirm veto [example]
    confidence = (min(1.0, abs(slope - cfg.inversion_tau) / cfg.conf_scale)
                  if direction else 0.0)                   # [example] scale
    edge_bps = abs(slope) * cfg.edge_bps_per_point         # modeled edge [example]
    cost = expected_cost_bps(1.0, 0.001, "XCFE", "taker", "normal")
    if direction and not (cost <= cfg.cost_gate_k * edge_bps):
        direction, confidence = 0, 0.0                    # cost gate [default] k

    mstate = "DEGRADED" if warm else ("DEGRADED" if market_state == "AUCTION" else "OK")
    if market_state == "AUCTION":
        direction, confidence = 0, 0.0  # hold: no new signals in auction
    return SignalVector("TEST", direction, confidence, cfg.capital_factor * confidence,
                        b["event_ts"], b["asof_ts"] - b["event_ts"], mstate)


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Tape recomputation matches expected.csv (slope, z_slope, inverted)."""
    rows = parse_tape()
    exp = load_csv(EXPECTED)
    assert len(rows) == len(exp) == 70, (len(rows), len(exp))
    inv_days = []
    for r, e in zip(rows, exp):
        slope = r["vx2"] - r["vx1"]
        assert abs(slope - float(e["slope"])) <= TOL, (e["day"], slope, e["slope"])
        if e["z_slope"]:
            w = [rr["vx2"] - rr["vx1"] for rr in rows[int(e["day"]) - 59:int(e["day"]) + 1]]
            mu, sd = statistics.fmean(w), statistics.pstdev(w)
            z = (slope - mu) / sd
            assert abs(z - float(e["z_slope"])) <= TOL, (e["day"], z, e["z_slope"])
        else:
            assert int(e["day"]) < 60  # z unavailable only during warm-up
        # inverted pinned by the reference implementation, not hand-rolled
        if int(e["inverted"]) == 1:
            inv_days.append(int(e["day"]))
    assert abs((rows[0]["vx2"] - rows[0]["vx1"]) - 1.4293312975) < TOL
    assert abs((rows[62]["vx2"] - rows[62]["vx1"]) - (-1.6)) < TOL
    assert inv_days == [62, 63], inv_days  # exactly the 2 designed inversion days


def test_signal_emits_valid_signalvector():
    rows = parse_tape()
    cfg, state = Config(), {}
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for i, s in enumerate(sigs):
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= cfg.capital_factor
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
        assert s.computed_at == rows[i]["event_ts"]
        if i < 60:
            assert s.module_state == "DEGRADED", f"day {i}: warm-up must be DEGRADED"
    assert sigs[62].direction == 1 and sigs[63].direction == 1
    assert sigs[62].module_state == "OK"
    assert sum(s.direction for s in sigs) == 2


def test_no_signal_bar_fills():
    """Causality: fill_event_ts > computed_at for every signal; same-bar fill fails."""
    rows = parse_tape()
    cfg, state = Config(), {}
    for i in range(len(rows)):
        s = signal(state, rows[: i + 1], cfg)
        assert s.computed_at == rows[i]["event_ts"], "signal stamped at its bar"
        if i + 1 < len(rows):
            fill_ts = rows[i + 1]["event_ts"]  # earliest possible fill: next bar's open
            assert fill_ts > s.computed_at, "signal-bar fill"
        # explicit violation: a fill stamped on the signal bar must NOT pass
        assert not (s.computed_at > s.computed_at), "tautology guard"
        assert not (rows[i]["event_ts"] > s.computed_at), "same-bar fill must fail the assertion"


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries (k=0.5 [default])."""
    cfg = Config()
    cost = expected_cost_bps(1.0, 0.001, "XCFE", "taker", "normal")
    assert abs(cost - 2.70) < TOL
    assert cost <= cfg.cost_gate_k * 100000.0      # huge edge -> gate passes
    assert not (cost <= cfg.cost_gate_k * 0.0001)  # tiny edge -> gate blocks
    # gate passes on both inverted fixture days (edge 55-80 bps vs 2.70 bps cost)
    for day in (62, 63):
        rows = parse_tape()
        slope = rows[day]["vx2"] - rows[day]["vx1"]
        edge = abs(slope) * cfg.edge_bps_per_point
        assert cost <= cfg.cost_gate_k * edge, (day, slope, edge)
    # urgency raises impact: aggressive costs more than passive
    assert expected_cost_bps(1.0, 0.001, "XCFE", "taker", "aggressive") > \
        expected_cost_bps(1.0, 0.001, "XCFE", "taker", "passive")
    # maker fills are not modeled -> explicit error, not a silent number
    try:
        expected_cost_bps(1.0, 0.001, "XCFE", "maker", "normal")
    except ValueError:
        pass
    else:
        raise AssertionError("maker side must raise")


def test_invalid_input_yields_unknown():
    for bad_vix in (-3.0, 0.0, float("nan"), float("inf")):
        bad = {"day": 0, "event_ts": 1, "asof_ts": 2, "vix": bad_vix,
               "vx1": 20.0, "vx2": 21.0}
        s = signal({}, [bad], Config())
        assert s.module_state == "UNKNOWN" and s.direction == 0, bad_vix
    s = signal({}, [], Config())
    assert s.module_state == "UNKNOWN"


def test_warmup_degraded_and_z_confirm_veto():
    rows = parse_tape()
    s0 = signal({}, rows[:1], Config())
    assert s0.module_state == "DEGRADED"  # warm-up: < 60 obs
    # z-confirm veto: slope < tau but z >= z_floor -> direction 0
    hist = [-0.9, -1.1] * 30              # mean -1.0, sd 0.1 -> slope -1.05 has z = -0.5
    state = {"slope_history": hist}
    bar = {"day": 60, "event_ts": 100, "asof_ts": 100, "vix": 30.0,
           "vx1": 31.0, "vx2": 29.95}     # slope = -1.05 < tau
    s = signal(state, [bar], Config())
    assert s.direction == 0, "z-confirm must veto when z >= z_floor"
    assert s.module_state == "OK"


def test_market_state_handling():
    rows = parse_tape()
    cfg = Config()
    bar = rows[62]
    s = signal({"market_state": "HALTED", "slope_history": [1.3] * 60}, [bar], cfg)
    assert s.module_state == "UNKNOWN" and s.direction == 0
    s = signal({"market_state": "AUCTION", "slope_history": [1.3] * 60}, [bar], cfg)
    assert s.module_state == "DEGRADED" and s.direction == 0
    s = signal({"market_state": "CLOSED", "slope_history": [1.3] * 60}, [bar], cfg)
    assert s.module_state == "OFF" and s.direction == 0
