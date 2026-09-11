"""Acceptance tests for S029 — Keltner / Bollinger breakouts.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of
the chapter's normative pseudocode, and asserts causality, the cost gate,
the OR-leg entry rule, warmup-flat behavior, and hand-checked fixture
arithmetic.

Run: python3 -m pytest modules/tests/test_S029.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S029_tape.csv"
EXPECTED = FIX / "S029_expected.csv"

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
    return {"ev": -1, "event_ts": 1, "open": 100.0, "high": 100.5,
            "low": 100.6, "close": 100.0, "volume": 10}  # high < low


FEATURE_COLS = ["sma", "sd", "bb_up", "bb_lo", "atr", "kc_up", "kc_lo", "bb_brk", "kc_brk"]


def _tr(cur, prev_close):
    if prev_close is None:
        return cur["high"] - cur["low"]
    return max(cur["high"] - cur["low"], abs(cur["high"] - prev_close),
               abs(cur["low"] - prev_close))


def compute_features(rows):
    N, m = Config().lookback, Config().multiplier
    closes = [r["close"] for r in rows]
    out = []
    for t, r in enumerate(rows):
        if t < N - 1:
            out.append({"id": r["ev"], "sma": float("nan"), "sd": float("nan"),
                        "bb_up": float("nan"), "bb_lo": float("nan"),
                        "atr": float("nan"), "kc_up": float("nan"),
                        "kc_lo": float("nan"), "bb_brk": 0, "kc_brk": 0})
            continue
        win = closes[t - N + 1:t + 1]
        mu = sum(win) / N
        sd = (sum((x - mu) ** 2 for x in win) / N) ** 0.5
        bb_up, bb_lo = mu + m * sd, mu - m * sd
        trs = [_tr(rows[j], rows[j - 1]["close"] if j > 0 else None)
               for j in range(t - N + 1, t + 1)]
        atr = sum(trs) / N
        ema = mu  # SMA-seeded EMA (chapter's example convenience)
        kc_up, kc_lo = ema + m * atr, ema - m * atr
        out.append({"id": r["ev"], "sma": mu, "sd": sd, "bb_up": bb_up,
                    "bb_lo": bb_lo, "atr": atr, "kc_up": kc_up, "kc_lo": kc_lo,
                    "bb_brk": 1 if r["close"] > bb_up else (-1 if r["close"] < bb_lo else 0),
                    "kc_brk": 1 if r["close"] > kc_up else (-1 if r["close"] < kc_lo else 0)})
    return out


@dataclass
class Config:
    lookback: int = 20           # N bars [example]
    atr_window: int = 20         # ATR window (often = N) [example]
    multiplier: float = 2.0      # m / k [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model (§S2 COST block): intraday envelope breakout."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0    # breakout chasing concession [example]
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S029 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["high"] < e["low"] or e["close"] <= 0 or e["high"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    feats = compute_features(evs)
    f = feats[-1]
    import math as _m
    if _m.isnan(f["bb_up"]):
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    # OR-leg entry per §S2/§S3 normative pseudocode: either envelope leg fires.
    bb_brk, kc_brk = f["bb_brk"], f["kc_brk"]
    direction = bb_brk if bb_brk else kc_brk
    confidence = 0.7 if direction else 0.0  # envelope-break conviction [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(e["close"] - f["sma"]) / e["close"] * 1e4  # midline distance [example]
    gate = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    if not gate:
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
    b30 = by_id[30]
    # Chapter S4 verified numbers (seed 29, N=20, bars 11-30 window):
    # sma=100.29, sd=0.3923, bb_up=101.0746, bb_lo=99.5054, atr=1.075,
    # kc_up=102.44, kc_lo=98.14 ; C30=102.00 -> BB break, Keltner high-through only
    assert abs(b30["sma"] - 100.29) < 1e-9, b30
    assert abs(b30["sd"] - 0.3923) < 1e-3, b30
    assert abs(b30["bb_up"] - 101.0746) < 1e-3, b30
    assert abs(b30["bb_lo"] - 99.5054) < 1e-3, b30
    assert abs(b30["atr"] - 1.075) < 1e-9, b30
    assert abs(b30["kc_up"] - 102.44) < 1e-9, b30
    assert abs(b30["kc_lo"] - 98.14) < 1e-9, b30
    assert b30["bb_brk"] == 1 and b30["kc_brk"] == 0



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


def test_warmup_emits_flat():
    """Warmup bars (NaN features, t < N) emit direction 0 with state OK."""
    rows = tape()
    cfg, state = Config(), dict()
    warmup = [signal(state, rows[: i + 1], cfg) for i in range(cfg.lookback - 1)]
    assert len(warmup) == cfg.lookback - 1
    for s in warmup:
        assert s.direction == 0 and s.confidence == 0.0 and s.capital == 0.0
        assert s.module_state == "OK"


def _craft_bb_only_break():
    """21 synthetic bars: flat 100.0 closes -> sd=0 (bb_up=100.0),
    range 1.0 -> atr=1.0 (kc_up=102.0); bar 21 closes at 101.0,
    which breaks the Bollinger leg only (kc_up ~= 102.10)."""
    ts = 1757000000000000000
    bars = [{"ev": i + 1, "event_ts": ts + i * 60_000_000_000, "open": 100.0,
             "high": 100.5, "low": 99.5, "close": 100.0, "volume": 100}
            for i in range(20)]
    bars.append({"ev": 21, "event_ts": ts + 20 * 60_000_000_000, "open": 100.5,
                 "high": 101.5, "low": 100.5, "close": 101.0, "volume": 500})
    return bars


def test_bollinger_leg_entry_via_or():
    """OR-leg entry: a Bollinger-only break emits +1 (Keltner leg silent)."""
    bars = _craft_bb_only_break()
    f = compute_features(bars)[-1]
    assert f["bb_brk"] == 1 and f["kc_brk"] == 0, f
    # edge ~= 94 bps [example]; cost 1.80 bps <= 0.5 * edge -> gate passes
    s = signal(dict(), bars, Config())
    assert s.module_state == "OK"
    assert s.direction == 1


def test_maker_cost_lt_taker():
    """§S2 maker-rebate branch: maker stack is cheaper than taker stack."""
    taker = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    maker = expected_cost_bps(1.0, 0.001, "XNAS", "maker", "normal")
    assert abs(taker - 1.80) < 1e-9
    assert abs(maker - 1.30) < 1e-9
    assert maker < taker


def test_fixture_type_header():
    """Fixture tape carries the mandatory TYPE header."""
    with open(TAPE) as fh:
        first = fh.readline().strip()
    assert first.startswith("# TYPE:"), first
    assert "validation-run" in first, first


def test_fixture_bar_count():
    """Chapter tape is exactly 30 synthetic bars."""
    assert len(tape()) == 30  # [example]
