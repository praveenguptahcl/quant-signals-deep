"""Acceptance tests for S044 — Stochastic oscillator / Williams %R.

Template v1.0.0. Reference implementation of the chapter's normative
pseudocode (warmup guard, zero-range veto, cost gate, locate_ok, cooldown)
with 8 acceptance tests pinning fixture arithmetic, causality, the cost
gate, and fail-safe behavior.

Run: python3 -m pytest modules/tests/test_S044.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S044_tape.csv"
EXPECTED = FIX / "S044_expected.csv"

TOL = 1e-9  # [default] tolerance on float comparisons


def _num(x):
    """NaN-aware cell reader: blank expected cells encode NaN (warmup)."""
    return float("nan") if x == "" or x is None else float(x)


def _close(a, b):
    a = float(a)
    b = _num(b)
    if math.isnan(a) and math.isnan(b):
        return True
    if math.isnan(a) or math.isnan(b):
        return False
    return abs(a - b) < TOL


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


@dataclass(frozen=True)
class SignalVector:
    symbol: str
    direction: int          # +1 | -1 | 0
    confidence: float       # 0..1
    capital: float          # 0..1
    computed_at: int        # int64 ns UTC
    staleness: int          # ns
    module_state: str       # OK | DEGRADED | UNKNOWN | OFF



def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({"ev": int(r["ev"]), "event_ts": int(r["event_ts"]),
                     "open": float(r["open"]), "high": float(r["high"]),
                     "low": float(r["low"]), "close": float(r["close"]),
                     "volume": int(r["volume"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"ev": -1, "event_ts": 1, "open": 100.0, "high": 99.0,
            "low": 100.0, "close": 100.0, "volume": 10}  # high < low


FEATURE_COLS = ["K", "D", "R", "crossdn", "dir"]


def _pctK(rows, t, N):
    win = rows[t - N + 1:t + 1]
    Ln = min(x["low"] for x in win)
    Hn = max(x["high"] for x in win)
    if Hn == Ln:
        return float("nan")  # C11: zero-range window vetoed at %K level
    return 100.0 * (rows[t]["close"] - Ln) / (Hn - Ln)


def compute_features(rows):
    N, cfg = Config().n, Config()
    Ks = []
    for t in range(len(rows)):
        Ks.append(_pctK(rows, t, N) if t >= N - 1 else float("nan"))
    out = []
    for t, r in enumerate(rows):
        if t < N + 1:  # need K[t], K[t-1], K[t-2] for D and the crossover
            out.append({"id": r["ev"], "K": float("nan"), "D": float("nan"),
                        "R": float("nan"), "crossdn": 0, "dir": 0})
            continue
        K = Ks[t]
        D = (Ks[t] + Ks[t - 1] + Ks[t - 2]) / 3.0
        Dprev = (Ks[t - 1] + Ks[t - 2] + Ks[t - 3]) / 3.0
        R = K - 100.0  # Williams %R
        crossdn = 1 if (Ks[t - 1] >= Dprev and K < D and K > cfg.overbought) else 0
        out.append({"id": r["ev"], "K": K, "D": D, "R": R,
                    "crossdn": crossdn, "dir": -1 if crossdn else 0})
    return out


@dataclass
class Config:
    n: int = 14                  # %K lookback [example]
    smooth: int = 3              # %D SMA length [example]
    overbought: float = 80.0     # crossover zone [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: oscillator-crossover entry, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.00   # concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg, locate_ok=True):
    """signal(state, events, cfg) -> SignalVector (S044 reference stub).

    Implements the §S3 normative pseudocode: warmup guard (no signal before
    bar n+2), zero-range veto (C11), cost-gate predicate, locate_ok (C7),
    and post-exit cooldown via state["cooldown_until"] (C10).
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["high"] < e["low"] or e["close"] <= 0 or e["high"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    # C11: zero-range bar -> UNKNOWN for the bar, never emit a level
    if e["high"] == e["low"]:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    if len(evs) < cfg.n + 2:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    feats = compute_features(evs)
    f = feats[-1]
    direction = f["dir"]
    confidence = 0.6 if direction else 0.0  # crossover conviction [example]
    capital = 0.5 * confidence
    # normative cost gate: expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(f["K"] - f["D"]) * 10.0  # crossover gap [example]
    cost_ok = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    cooldown_active = e["event_ts"] < state.get("cooldown_until", 0)
    if not (cost_ok and locate_ok and not cooldown_active):
        direction, confidence, capital = 0, 0.0, 0.0
    return SignalVector("TEST:XNAS", direction, confidence, capital,
                        e["event_ts"], 0, "OK")



# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    rows = tape()
    feats = compute_features(rows)
    exp = load_csv(EXPECTED)
    assert len(feats) == len(exp), (len(feats), len(exp))
    for f, w in zip(feats, exp):
        assert str(f["id"]) == str(w["id"]), (f["id"], w["id"])
        for col in FEATURE_COLS:
            assert _close(f[col], w[col]), (f["id"], col)

    by_id = {f["id"]: f for f in feats}
    b16, b17, b18 = by_id[16], by_id[17], by_id[18]
    # Chapter S4 hand-checks (seed 44): bar 16 K=95.4/D=95.0; bar 17
    # K=94.3/D=94.8/R=-5.7 -> cross-down above 80 -> short.
    assert abs(b16["K"] - 95.4) < 1e-9, b16
    assert abs(b16["D"] - 95.0) < 1e-9, b16
    assert abs(b17["K"] - 94.3) < 1e-9, b17
    assert abs(b17["D"] - 94.8) < 1e-9, b17
    assert abs(b17["R"] - (-5.7)) < 1e-9, b17
    assert b17["crossdn"] == 1 and b17["dir"] == -1
    assert b18["crossdn"] == 0 and b18["dir"] == 0  # K17 < D17: no fresh cross
    # first tradable bar: bar 16 is the first with a defined %D
    assert by_id[16]["D"] == by_id[16]["D"]



def test_signal_emits_valid_signalvector():
    rows = tape()
    cfg, state = Config(), dict()
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = tape()
    cfg, state = Config(), dict()
    for i in range(len(rows) - 1):
        s = signal(state, rows[: i + 1], cfg)
        fill_event_ts = event_ts(rows[i + 1])  # earliest possible fill: next event
        assert fill_event_ts > s.computed_at, "signal-bar fill at row %d" % i


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert cost > 0
    assert cost <= k * 100.0   # huge edge -> gate passes
    assert not (cost <= k * 0.01)  # tiny edge -> gate blocks


def test_invalid_input_yields_unknown():
    s = signal(dict(), [bad_event()], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0


def test_zero_range_bar_yields_unknown():
    """C11: a zero-range bar (high == low) vetoes the bar -> UNKNOWN."""
    e = dict(tape()[16])  # bar 17: the fixture's crossover bar
    e["high"] = e["low"] = e["close"] = 104.715
    s = signal(dict(), [e], Config())
    assert s.module_state == "UNKNOWN", s
    assert s.direction == 0 and s.confidence == 0.0 and s.capital == 0.0
    # zero-range window at %K level also vetoes (NaN, no division by zero)
    flat = [dict(r) for r in tape()[:14]]
    for r in flat:
        r.update(high=100.0, low=100.0, close=100.0, open=100.0)
    assert math.isnan(_pctK(flat, 13, 14))


def test_warmup_bars_emit_no_signal():
    """Warmup: no signal before bar n+2; state stays OK, direction 0."""
    rows, cfg = tape(), Config()
    for i in range(1, cfg.n + 1):  # bars 1..15 (warmup zone)
        s = signal(dict(), rows[: i + 1], cfg)
        assert s.direction == 0, (i, s)
        assert s.module_state == "OK", (i, s)


def test_cooldown_suppresses_entry():
    """C10: an active cooldown_until suppresses even a confirmed crossover."""
    rows, cfg = tape(), Config()
    control = signal(dict(), rows[:17], cfg)
    assert control.direction == -1, "fixture crossover bar must fire without cooldown"
    suppressed = signal({"cooldown_until": rows[16]["event_ts"] + 600_000_000_000},
                        rows[:17], cfg)
    assert suppressed.direction == 0, suppressed
    assert suppressed.confidence == 0.0 and suppressed.capital == 0.0
    assert suppressed.module_state == "OK"
