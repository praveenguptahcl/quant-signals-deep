"""Acceptance tests for S040 — VWAP-deviation mean reversion.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S040.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S040_tape.csv"
EXPECTED = FIX / "S040_expected.csv"

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
        rows.append({"id": r["id"], "event_ts": int(r["event_ts"]),
                     "close": float(r["close"]), "vwap": float(r["vwap"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "close": 100.0,
            "vwap": 0.0}  # non-positive VWAP


FEATURE_COLS = ["dev", "sigma", "z", "trig", "dir"]


def compute_features(rows):
    cfg = Config()
    devs = [r["close"] - r["vwap"] for r in rows]
    out = []
    for t, r in enumerate(rows):
        w = devs[:t + 1]  # expanding window including the current bar
        if len(w) < cfg.min_periods:
            out.append({"id": r["id"], "dev": devs[t],
                        "sigma": float("nan"), "z": float("nan"),
                        "trig": 0, "dir": 0})
            continue
        mu = sum(w) / len(w)
        var = sum((x - mu) ** 2 for x in w) / (len(w) - 1)  # sample std
        sigma = math.sqrt(var)
        if sigma <= 0.0:
            # F2: degenerate window (all deviations equal) -> zero-width band;
            # never emit on it. sigma recorded so signal() can raise UNKNOWN.
            out.append({"id": r["id"], "dev": devs[t], "sigma": 0.0,
                        "z": float("nan"), "trig": 0, "dir": 0})
            continue
        z = devs[t] / sigma
        trig = 1 if abs(z) >= cfg.z_thresh else 0
        d = (-1 if z > 0 else (1 if z < 0 else 0)) * trig  # fade the deviation
        out.append({"id": r["id"], "dev": devs[t], "sigma": sigma,
                    "z": z, "trig": trig, "dir": d})
    return out


@dataclass
class Config:
    min_periods: int = 5         # sigma warmup bars [example]
    z_thresh: float = 2.0        # fade trigger [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: VWAP-reversion, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.00   # concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S040 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["vwap"] <= 0 or e["close"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    feats = compute_features(evs)
    f = feats[-1]
    if f["z"] != f["z"]:  # NaN z: warmup or degenerate window
        if f["sigma"] is not None and f["sigma"] <= 0.0:
            return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                                e["event_ts"], 0, "UNKNOWN")  # F2: never emit on a zero-width band
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")  # warmup guard: never trade the sigma warmup
    direction = f["dir"]
    confidence = min(1.0, abs(f["z"]) / 3.0) if direction else 0.0  # |z|=3 full [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(f["z"]) * 20.0  # 20bps per unit z [example]
    ok = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    if not ok:
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
    b5 = by_id["bar5"]
    # Chapter S4 hand-checks (seed 40): z series from bar 5:
    # 2.08, 1.45, 0.61, -0.28, -1.29, -1.58 [, -1.48, -1.45]
    assert abs(b5["z"] - 2.0795) < 0.01, b5
    assert b5["trig"] == 1 and b5["dir"] == -1  # short trigger at bar 5
    assert abs(by_id["bar6"]["z"] - 1.4515) < 0.01
    assert abs(by_id["bar7"]["z"] - 0.6057) < 0.02
    assert abs(by_id["bar8"]["z"] - (-0.2791)) < 0.02
    assert abs(by_id["bar9"]["z"] - (-1.2932)) < 0.02
    assert abs(by_id["bar10"]["z"] - (-1.5790)) < 0.02
    # warmup guard: bars 1-4 carry no z and never trigger
    assert all(by_id["bar%d" % i]["trig"] == 0 for i in range(1, 5))
    # t -> t+1: the bar-5 trigger is first tradable at bar 6's open
    s5 = signal(dict(), rows[:5], Config())
    assert s5.direction == -1 and s5.computed_at == rows[4]["event_ts"]



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


def test_empty_events_yields_unknown():
    # F1: empty event list -> UNKNOWN, never a phantom signal
    s = signal(dict(), [], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.confidence == 0.0 and s.capital == 0.0


def test_sigma_zero_window_yields_unknown():
    # F2: price glued to VWAP all session -> sigma == 0 -> UNKNOWN, not a crash
    ts = 1757000000000000000
    rows = [{"id": "flat%d" % i, "event_ts": ts + i * 60_000_000_000,
             "close": 100.0, "vwap": 100.0} for i in range(6)]
    feats = compute_features(rows)
    assert feats[-1]["sigma"] == 0.0
    s = signal(dict(), rows, Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0
