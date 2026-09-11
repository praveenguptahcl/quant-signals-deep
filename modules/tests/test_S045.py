"""Acceptance tests for S045 — Stretched-move z-score.

Template v1.0.0. Reference implementation of the chapter's normative
pseudocode (§S3, v1.1.0): pinned incl-current/population convention, warmup,
cooldown, locate gate (C7), executable cost-gate predicate (C2), and the
mandatory no-signal-bar-fills causality assertion.

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


def compute_features(rows, cfg):
    N = cfg.lookback
    closes = [r["close"] for r in rows]
    vols = [r["volume"] for r in rows]
    out = []
    for t, r in enumerate(rows):
        if t < N - 1:
            out.append({"id": r["ev"], "mean": float("nan"),
                        "sd": float("nan"), "z": float("nan"),
                        "vol_ratio": float("nan"), "dir": 0})
            continue
        # PINNED inclusion convention: the N-bar window INCLUDES the current
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
    cooldown_s: float = 600.0    # post-exit cooldown, seconds [default]
    locate_ok: bool = True       # consumer-asserted locate for SHORT [default]
    side: str = "taker"          # cost-function leg [default]
    venue: str = "XNAS"          # cost-function leg [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: stretched-move fade, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.00   # concession [example]
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (§S3 normative, v1.1.0)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")  # F1
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["high"] < e["low"] or e["close"] <= 0 or e["high"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    if len(evs) < cfg.lookback:                                   # warmup
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "OK")
    feats = compute_features(evs, cfg)
    f = feats[-1]
    if e["event_ts"] < state.get("cooldown_until", 0):             # C10
        direction = 0
    else:
        short_fade = (f["z"] >= cfg.z_thresh and f["vol_ratio"] <= cfg.vol_max_ratio
                      and cfg.locate_ok)                          # C7
        long_fade = (f["z"] <= -cfg.z_thresh and f["vol_ratio"] <= cfg.vol_max_ratio)
        direction = -1 if short_fade else (1 if long_fade else 0)
    # normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps (C2)
    edge_bps = abs(f["z"]) * 15.0  # 15 bps per unit z [example]
    ok = (expected_cost_bps(1.0, 0.001, cfg.venue, cfg.side, "normal")
          <= cfg.cost_gate_k * edge_bps)
    if not ok:
        direction = 0
    confidence = min(1.0, abs(f["z"]) / 5.0) if direction else 0.0  # |z|=5 full [example]
    capital = 0.5 * confidence                                    # 0.5 [default]
    return SignalVector("TEST:XNAS", direction, confidence, capital,
                        e["event_ts"], 0, "OK")


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    rows = tape()
    cfg = Config()
    feats = compute_features(rows, cfg)
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
    # the inclusion convention is pinned: prior-only window (bars 10-29,
    # 20 bars, excluding the stretching bar 30) gives a radically different z
    closes = [r["close"] for r in rows]
    win_prior = closes[9:29]                     # indices 9..28 -> bars 10..29
    assert len(win_prior) == 20, len(win_prior)
    mu_p = sum(win_prior) / 20
    sd_p = (sum((x - mu_p) ** 2 for x in win_prior) / 20) ** 0.5
    z_prior = (102.00 - mu_p) / sd_p
    assert abs(z_prior - b30["z"]) > 1.0, (z_prior, b30["z"])


def test_signal_emits_valid_signalvector():
    rows = tape()
    cfg = Config()
    sigs = [signal(dict(), rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = tape()
    cfg = Config()
    for i in range(len(rows) - 1):
        s = signal(dict(), rows[: i + 1], cfg)
        fill_event_ts = event_ts(rows[i + 1])  # earliest possible fill: next event
        assert fill_event_ts > s.computed_at, "signal-bar fill at row %d" % i


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries, both legs."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert abs(cost - 1.80) < TOL                    # 0.50+0.30+0+1.00 [example] stack
    assert cost <= k * 100.0   # huge edge -> gate passes
    assert not (cost <= k * 0.01)  # tiny edge -> gate blocks
    maker = expected_cost_bps(1.0, 0.001, "XNAS", "maker", "normal")
    assert abs(maker - 1.30) < TOL                  # rebate leg: 0.50-0.20+0+1.00


def test_invalid_input_yields_unknown():
    s = signal(dict(), [bad_event()], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0


def test_cost_gate_wires_through_signal():
    """C2: tiny k zeroes the bar-30 fade; default k keeps it."""
    rows = tape()
    sig_default = signal(dict(), rows, Config())
    assert sig_default.direction == -1, sig_default
    cfg_tiny = Config()
    cfg_tiny.cost_gate_k = 0.0001  # k*edge ~= 0.0065 < 1.80 bps cost
    sig_tiny = signal(dict(), rows, cfg_tiny)
    assert sig_tiny.direction == 0
    assert sig_tiny.confidence == 0.0 and sig_tiny.capital == 0.0


def test_locate_gate_zeroes_short():
    """C7: SHORT fade requires locate_ok; missing locate -> direction 0."""
    rows = tape()
    cfg = Config()
    cfg.locate_ok = False
    s = signal(dict(), rows, cfg)
    assert s.direction == 0, s
    assert s.module_state == "OK"  # locate veto is a flat signal, not an error


def test_cooldown_suppresses_entry():
    """C10: future cooldown_until suppresses entry without erroring."""
    rows = tape()
    state = {"cooldown_until": rows[-1]["event_ts"] + 10 ** 15}
    s = signal(state, rows, Config())
    assert s.direction == 0, s
    assert s.module_state == "OK"


def test_warmup_bars_emit_flat_ok():
    """Fewer than `lookback` bars -> direction 0, state OK (no NaN leak)."""
    rows = tape()
    for n in (1, 10, 19):  # all < lookback=20 [example]
        s = signal(dict(), rows[:n], Config())
        assert s.direction == 0 and s.confidence == 0.0, n
        assert s.module_state == "OK", n


def test_volume_expansion_vetoes_fade():
    """Volume expansion (> vol_max_ratio) vetoes the fade: direction 0."""
    rows = tape()
    base = rows[-20:]  # full window of real bars
    vols = [r["volume"] for r in base]
    mean_vol = sum(vols) / len(vols)
    # stretch the close (+4% [example]) with 3x [example] mean volume
    stretched = dict(base[-1])
    stretched["ev"] = base[-1]["ev"] + 1
    stretched["event_ts"] = base[-1]["event_ts"] + 60 * 10 ** 9
    stretched["close"] = base[-1]["close"] * 1.04
    stretched["high"] = stretched["close"] * 1.001
    stretched["volume"] = int(mean_vol * 3.0)
    s = signal(dict(), base[:-1] + [stretched], Config())
    assert s.direction == 0, s  # volume expansion -> no fade, never a breakout long


def test_bar30_end_to_end():
    """Bar-30 fixture episode: short fade, pinned confidence, gate passes."""
    rows = tape()
    s = signal(dict(), rows, Config())
    assert s.direction == -1, s
    assert abs(s.confidence - 4.359 / 5.0) < 0.02, s   # min(1, |z|/5) [example]
    assert abs(s.capital - 0.5 * s.confidence) < TOL
    assert s.module_state == "OK"
