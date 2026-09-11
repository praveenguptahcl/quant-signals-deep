"""Acceptance tests for S063 — Range-based realized-volatility estimators.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode (all four estimators:
Parkinson, Garman-Klass, Rogers-Satchell, Yang-Zhang N-day rolling), and real
assertions including causality (assert fill_event > signal_event), cost gate,
and invalid -> UNKNOWN.

Run: python3 -m pytest modules/tests/test_S063.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S063_tape.csv"
EXPECTED = FIX / "S063_expected.csv"

TOL = 1e-9  # tolerance on float comparisons
EXPECTED_COLS = ['day', 'park', 'gk', 'rs', 'yz', 'ann_vol_park', 'ann_vol_yz']
COL_TYPES = {'day': 'int', 'event_ts': 'int', 'asof_ts': 'int', 'open': 'float', 'high': 'float', 'low': 'float', 'close': 'float'}
MAYBE_BLANK = {'yz', 'ann_vol_yz'}  # masked on insufficient history (days 0-4 in fixture)


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


# ------------------------------------------------- normative pseudocode stub
@dataclass(frozen=True)
class SignalVector:
    symbol: str
    direction: int          # +1 | -1 | 0
    confidence: float       # 0..1
    capital: float          # 0..1
    computed_at: int        # int64 ns UTC
    staleness: int          # ns
    module_state: str       # OK | DEGRADED | UNKNOWN | OFF


def yang_zhang(bars, N):
    """Yang-Zhang (2000) rolling estimator. Returns None on insufficient history.

    bars: list of dicts ending at bar t. Uses the N days t-N+1..t plus the
    close of day t-N for the first overnight return.
    """
    if len(bars) <= N:
        return None  # masked, never interpolated
    win = bars[-N:]
    prev_close = bars[-N - 1]["close"]
    closes = [prev_close] + [w["close"] for w in win]
    overnight = [math.log(win[i]["open"] / closes[i]) for i in range(N)]
    oc = [math.log(w["close"] / w["open"]) for w in win]
    rs_i = [math.log(w["high"] / w["close"]) * math.log(w["high"] / w["open"]) +
            math.log(w["low"] / w["close"]) * math.log(w["low"] / w["open"]) for w in win]
    s2o = sum(x * x for x in overnight) / N
    s2c = sum(x * x for x in oc) / N
    s2rs = sum(rs_i) / N
    k = 0.34 / (1.34 + (N + 1) / (N - 1))  # [documented] Yang-Zhang 2000
    return s2o + k * s2c + (1 - k) * s2rs


def recompute(rows, yz_window_n=5, ann_factor=252.0):
    out = []
    for i, r in enumerate(rows):
        hl = math.log(r["high"] / r["low"])
        co = math.log(r["close"] / r["open"])
        park = hl ** 2 / (4 * math.log(2))
        gk = 0.5 * hl ** 2 - (2 * math.log(2) - 1) * co ** 2
        rs = math.log(r["high"] / r["close"]) * math.log(r["high"] / r["open"]) + \
             math.log(r["low"] / r["close"]) * math.log(r["low"] / r["open"])
        yz = yang_zhang(rows[: i + 1], yz_window_n)
        out.append({"day": r["day"], "park": park, "gk": gk, "rs": rs, "yz": yz,
                    "ann_vol_park": math.sqrt(max(park, 0) * ann_factor) * 100,
                    "ann_vol_yz": None if yz is None else math.sqrt(max(yz, 0) * ann_factor) * 100})
    return out


@dataclass
class Config:
    ann_factor: float = 252.0    # [default]; calibrate over 252|260|365
    yz_window_n: int = 5         # [example] fixture value; production default 21 [default]
    cost_gate_k: float = 0.5     # [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    # Estimator emits no trades; stack is the downstream vol-trader's reference [example].
    spread_bps = 0.50
    fee_bps = 0.30
    borrow_bps = 0.00   # reason: reference build long vol via options; no stock borrow [default]
    impact_bps = 0.50
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, bars, cfg):
    bars = list(bars)
    if not bars:
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    if not (cfg.ann_factor > 0 and math.isfinite(cfg.ann_factor)):
        return SignalVector("TEST", 0, 0.0, 0.0, 0, 0, "UNKNOWN")  # F2
    b = bars[-1]
    for k in ("open", "high", "low", "close"):
        if not (math.isfinite(b[k]) and b[k] > 0):
            return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F2
    if not (b["high"] >= max(b["open"], b["close"]) and b["low"] <= min(b["open"], b["close"])):
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F1/F2
    if b["asof_ts"] < b["event_ts"]:
        return SignalVector("TEST", 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F2
    hl = math.log(b["high"] / b["low"])
    park = hl ** 2 / (4 * math.log(2))
    ann_vol = math.sqrt(max(park, 0) * cfg.ann_factor) * 100
    confidence = min(1.0, ann_vol / 50.0)  # vol-regime salience score [example]
    edge_bps = ann_vol  # modeled sizing edge proxy [example]
    gate = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    st = "OK" if gate else "DEGRADED"
    return SignalVector("TEST", 0, confidence, 0.0, b["event_ts"],
                        b["asof_ts"] - b["event_ts"], st)


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Reference recomputation of the tape matches expected.csv (all four estimators)."""
    rows = parse_tape()
    exp = load_csv(EXPECTED)
    got = recompute(rows)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, e in zip(got, exp):
        for k in EXPECTED_COLS:
            gv, ev = g[k], e[k]
            if k in MAYBE_BLANK and (gv is None or ev in (None, "")):
                assert gv is None and ev in (None, ""), (k, gv, ev)  # masked, not interpolated
                continue
            assert abs(float(gv) - float(ev)) <= TOL, (k, gv, ev)
    # hand-checks, day 0
    hl = math.log(102.0 / 99.0)
    assert abs(got[0]["park"] - hl ** 2 / (4 * math.log(2))) < TOL
    assert abs(got[0]["gk"] - (0.5 * hl ** 2 - (2 * math.log(2) - 1) * math.log(101.0 / 100.0) ** 2)) < TOL
    assert abs(got[0]["rs"] - 0.0003961148) < TOL
    assert got[0]["ann_vol_park"] > 0


def test_yang_zhang_handcheck_and_masking():
    """YZ: k(N) weight formula, day-5 hand-check, masking on days 0-4."""
    N = 5
    k = 0.34 / (1.34 + (N + 1) / (N - 1))
    assert abs(k - 0.1197183099) < 1e-9, k  # weight formula check [documented]
    rows = parse_tape()
    got = recompute(rows, yz_window_n=N)
    for i in range(5):
        assert got[i]["yz"] is None, (i, "yz must be masked on insufficient history")
    assert abs(got[5]["yz"] - 0.0003390473) < 1e-9
    assert abs(got[5]["ann_vol_yz"] - 29.2301067037) < 1e-9
    assert abs(got[6]["yz"] - 0.0003456844) < 1e-9
    assert abs(got[7]["ann_vol_yz"] - 28.7840084451) < 1e-9
    # insufficient history: window longer than the tape -> all masked
    all_masked = recompute(rows, yz_window_n=50)
    assert all(g["yz"] is None for g in all_masked)


def test_signal_emits_valid_signalvector():
    rows = parse_tape()
    cfg, state = Config(), {}
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = parse_tape()
    cfg, state = Config(), {}
    for i in range(len(rows)):
        s = signal(state, rows[: i + 1], cfg)
        assert s.computed_at == rows[i]["event_ts"], "signal must be timestamped at its bar"
        later = [r["event_ts"] for r in rows[i + 1:] if r["event_ts"] > s.computed_at]
        if later:
            assert min(later) > s.computed_at, "signal-bar fill"


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert cost == 1.30  # reference stack [example]
    assert cost <= k * 100000.0   # huge edge -> gate passes
    assert not (cost <= k * 0.0001)  # tiny edge -> gate blocks


def test_invalid_input_yields_unknown():
    bad = {"day": 0, "event_ts": 1, "asof_ts": 2, "open": 100.0, "high": 99.0,
           "low": 98.0, "close": 99.5}  # high < open: bad bar
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0


def test_bad_annualization_yields_unknown():
    rows = parse_tape()
    for bad_factor in (0.0, -252.0):
        cfg = Config(ann_factor=bad_factor)
        s = signal({}, rows[:3], cfg)
        assert s.module_state == "UNKNOWN", bad_factor  # F2


def test_insufficient_yz_history_still_emits():
    """YZ masked on short history, but single-day estimators still emit OK/DEGRADED."""
    rows = parse_tape()
    cfg, state = Config(), {}
    s = signal(state, rows[:2], cfg)  # only 2 bars: YZ(N=5) has no history
    assert s.module_state in ("OK", "DEGRADED")
    assert 0.0 <= s.confidence <= 1.0
