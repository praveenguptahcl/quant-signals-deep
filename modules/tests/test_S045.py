"""Acceptance tests for S045 — Stretched-move z-score.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S045.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S045_tape.csv"
EXPECTED = FIX / "S045_expected.csv"

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


FEATURE_COLS = ["mean", "sd", "z", "vol_ratio", "dir"]


def compute_features(rows):
    N, cfg = Config().lookback, Config()
    closes = [r["close"] for r in rows]
    vols = [r["volume"] for r in rows]
    out = []
    for t, r in enumerate(rows):
        if t < N - 1:
            out.append({"id": r["ev"], "mean": float("nan"),
                        "sd": float("nan"), "z": float("nan"),
                        "vol_ratio": float("nan"), "dir": 0})
            continue
        # PINNED inclusion convention: the 20-bar window INCLUDES the current
        # bar, population sd. Prior-only gives a radically different z.
        win = closes[t - N + 1:t + 1]
        mu = sum(win) / N
        sd = (sum((x - mu) ** 2 for x in win) / N) ** 0.5
        z = (r["close"] - mu) / sd
        vwin = vols[t - N + 1:t + 1]
        vr = r["volume"] / (sum(vwin) / N)
        vol_ok = 1 if vr <= cfg.vol_max_ratio else 0
        d = 0
        if vol_ok and z >= cfg.z_thresh:
            d = -1  # stretched up, no volume expansion -> fade short
        elif vol_ok and z <= -cfg.z_thresh:
            d = 1
        out.append({"id": r["ev"], "mean": mu, "sd": sd, "z": z,
                    "vol_ratio": vr, "dir": d})
    return out


@dataclass
class Config:
    lookback: int = 20           # rolling window N [example]
    z_thresh: float = 3.0        # stretch trigger [example]
    vol_max_ratio: float = 1.5   # no-expansion ceiling [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: stretched-move fade, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.00   # concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S045 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["high"] < e["low"] or e["close"] <= 0 or e["high"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    if len(evs) < cfg.lookback:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    feats = compute_features(evs)
    f = feats[-1]
    direction = f["dir"]
    confidence = min(1.0, abs(f["z"]) / 5.0) if direction else 0.0  # |z|=5 full [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(f["z"]) * 15.0  # 15bps per unit z [example]
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
    b30 = by_id[30]
    # Chapter S4 hand-checks: bar 30 close 102.00, mean 100.29, sd 0.3923,
    # z = +4.36, no volume expansion -> short fade.
    assert abs(b30["mean"] - 100.29) < 1e-9, b30
    assert abs(b30["sd"] - 0.3923) < 1e-3, b30
    assert abs(b30["z"] - 4.359) < 0.02, b30
    assert b30["vol_ratio"] < 1.5, b30          # no volume expansion
    assert b30["dir"] == -1
    # the inclusion convention is pinned: prior-only window would give a
    # radically different z (assert it differs, guarding the convention)
    closes = [r["close"] for r in rows]
    win_prior = closes[10:29]                    # bars 11-29 only, excl. bar 30
    mu_p = sum(win_prior) / 20
    sd_p = (sum((x - mu_p) ** 2 for x in win_prior) / 20) ** 0.5
    z_prior = (102.00 - mu_p) / sd_p
    assert abs(z_prior - b30["z"]) > 1.0, (z_prior, b30["z"])



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
