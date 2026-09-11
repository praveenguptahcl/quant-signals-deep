"""Acceptance tests for S031 — Consecutive-bar streaks (runs).

Template v1.0.0. Loads the fixture tape, runs a reference implementation of
the chapter's normative pseudocode, and asserts causality, the cost gate,
the locate veto, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S031.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S031_tape.csv"
EXPECTED = FIX / "S031_expected.csv"

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
    return {"ev": -1, "event_ts": 1, "open": 100.0, "high": 100.0,
            "low": 100.0, "close": -5.0, "volume": 10}  # negative close


FEATURE_COLS = ["s", "direction"]


def compute_features(rows):
    k1, k2 = Config().k_cont, Config().k_exhaust
    out, streak, prev = [], 0, None
    for r in rows:
        s = 0 if prev is None or r["close"] == prev else (1 if r["close"] > prev else -1)
        prev = r["close"]
        if s == 0:
            streak = 0  # zero-return rule: break streak (example choice)
        elif (streak >= 0 and s > 0) or (streak <= 0 and s < 0):
            streak = streak + s
        else:
            streak = s
        a = abs(streak)
        if a >= k2:
            d = -1 if streak > 0 else 1    # exhaustion fade
        elif a >= k1:
            d = 1 if streak > 0 else -1    # continuation
        else:
            d = 0
        out.append({"id": r["ev"], "s": streak, "direction": d})
    return out


@dataclass
class Config:
    k_cont: int = 3              # continuation threshold k1 [example]
    k_exhaust: int = 6           # exhaustion threshold k2 [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: intraday streak signal, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0     # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0     # chasing concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg, locate_ok=True):
    """signal(state, events, cfg) -> SignalVector (S031 reference stub).

    locate_ok is the consumer-asserted Reg-SHO flag (C7): production
    state.locate_ok defaults False [default] (shorts vetoed); the harness
    asserts it True here to pin the continuation-down arithmetic.
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["close"] <= 0 or e["high"] < e["low"]:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    feats = compute_features(evs)
    direction = feats[-1]["direction"]
    if direction == -1 and not locate_ok:
        direction = 0  # C7: no locate -> no SHORT
    confidence = 0.6 if direction else 0.0  # streak conviction [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = 6.0 * abs(feats[-1]["s"]) / cfg.k_cont  # scales with streak [example]
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
    # Tape signs: +,+,-,+,+,+,-,-,-,-,-,-,-,+,0 ; k1=3, k2=6    assert by_id[6]["s"] == 3 and by_id[6]["direction"] == 1, by_id[6]   # continuation up
    assert by_id[9]["s"] == -3 and by_id[9]["direction"] == -1, by_id[9]  # continuation down
    assert by_id[12]["s"] == -6 and by_id[12]["direction"] == 1, by_id[12]  # exhaustion fade
    assert by_id[13]["s"] == -7 and by_id[13]["direction"] == 1, by_id[13]
    assert by_id[14]["s"] == 1 and by_id[14]["direction"] == 0, by_id[14]
    assert by_id[15]["s"] == 0 and by_id[15]["direction"] == 0, by_id[15]  # zero-return breaks streak



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


def test_cost_gate_blocks_entry_end_to_end():
    """Cost-gate blocking wired through signal(): bar-6 s=3 is +1 by default,
    but cost_gate_k=0.0 zeroes it (1.8 bps cost [example] > 0.0 * edge)."""
    rows = tape()
    gated = signal(dict(), rows[:6], Config(cost_gate_k=0.0))
    assert gated.direction == 0 and gated.confidence == 0.0 and gated.capital == 0.0
    # Sanity: default k=0.5 [default] lets the same bar through (0.5 * 6 bps = 3 > 1.8)
    open_sig = signal(dict(), rows[:6], Config())
    assert open_sig.direction == 1 and open_sig.module_state == "OK"


def test_short_vetoed_without_locate():
    """C7: SHORT direction requires locate_ok; bar-9 s=-3 is -1 with locate."""
    rows = tape()
    vetoed = signal(dict(), rows[:9], Config(), locate_ok=False)
    assert vetoed.direction == 0
    located = signal(dict(), rows[:9], Config(), locate_ok=True)
    assert located.direction == -1


def test_empty_events_yields_unknown():
    s = signal(dict(), [], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0


def test_zero_return_resets_streak():
    """Zero-return rule = break [example]: equal closes collapse the streak to 0."""
    bars = [
        {"ev": 1, "event_ts": 1, "open": 100.0, "high": 100.1, "low": 99.9,
         "close": 100.0, "volume": 10},
        {"ev": 2, "event_ts": 2, "open": 100.0, "high": 100.1, "low": 99.9,
         "close": 100.0, "volume": 10},  # zero-return bar: close == prev close
    ]
    feats = compute_features(bars)
    assert feats[-1]["s"] == 0 and feats[-1]["direction"] == 0
    s = signal(dict(), bars, Config())
    assert s.direction == 0 and s.module_state == "OK"
