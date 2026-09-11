"""Acceptance tests for S042 — SOTM: settle-to-open momentum (monthly vol).

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative §S3 pseudocode, and asserts causality, the cost gate (exact
§S2 COST-block stack), locate-gated shorts, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S042.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S042_tape.csv"
EXPECTED = FIX / "S042_expected.csv"

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


TRADING_DAYS = 252.0


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({"id": r["id"], "event_ts": int(r["event_ts"]),
                     "leg": r["leg"], "close": float(r["close"]),
                     "symbol": "TEST:XNAS"})
    return rows


def flat_tape(n=24, close=4000.0):
    """Synthetic 24-equal-close tape: zero returns -> SOTM = -sigma_r/2 < -threshold.

    Deterministic (no seed needed); pins the SHORT branch and C7 locate gating.
    """
    base = 1_757_000_000_000_000_000
    return [{"id": "q%02d" % (i + 1), "event_ts": base + i * 86_400_000_000_000,
             "leg": "flat", "close": close, "symbol": "TEST:XNAS"}
            for i in range(n)]


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "leg": "prior",
            "close": 0.0, "symbol": "TEST:XNAS"}  # non-positive close


FEATURE_COLS = ["logret", "sqret"]


def compute_features(rows):
    out = []
    for i, r in enumerate(rows):
        if i == 0:
            out.append({"id": r["id"], "logret": float("nan"),
                        "sqret": float("nan")})
            continue
        lr = math.log(r["close"] / rows[i - 1]["close"])
        out.append({"id": r["id"], "logret": lr, "sqret": lr * lr})
    return out


def sotm_vol(rows, cfg):
    """SOTM vol = (fwd_var / T - realized_var) / (2 * realized_vol)."""
    feats = compute_features(rows)
    sq = [f["sqret"] for f in feats[1:]]
    fwd_var = sum(sq)
    T = len(sq) / TRADING_DAYS
    rv = cfg.realized_vol ** 2
    return (fwd_var / T - rv) / (2 * cfg.realized_vol)


@dataclass
class Config:
    window_closes: int = 24        # settle window in closes [example]
    realized_vol: float = 0.112   # trailing realized vol [example]
    sotm_threshold: float = 0.015  # entry threshold [example]
    confidence_slope: float = 20.0  # confidence scaling [example]
    cost_gate_k: float = 0.5       # cost-gate multiplier [default]
    cooldown_s: float = 86_400.0   # post-settle cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model — constants MUST match the §S2 COST block.

    Stack (bps): spread 0.50 [example] + fees 0.30 [example] + borrow 0.0
    [default] + impact (1.0 + 50.0 * adv_pct) [example]; maker rebate -0.20
    [example]. Reference total at adv_pct -> 0: 1.80 bps [example].
    """
    spread_bps = 0.50                          # [example]
    fee_bps = 0.30                             # [example]
    borrow_bps = 0.0                           # [default] borrow_bps_per_day; long-biased reference
    impact_bps = 1.0 + 50.0 * adv_pct          # [example] participation-scaled; calibrate per venue
    if side == "maker":
        fee_bps = -0.20                        # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (§S3 normative pseudocode)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")  # F1
    e = evs[-1]
    sym = e.get("symbol", "TEST:XNAS")
    if e["close"] <= 0:
        return SignalVector(sym, 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")  # F1/F2: never interpolate
    closes = evs[-cfg.window_closes:]
    if len(closes) < cfg.window_closes or any(c["close"] <= 0 for c in closes):
        return SignalVector(sym, 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")  # window must be full
    sv = sotm_vol(closes, cfg)
    edge_bps = abs(sv) * 1e4  # [example]
    cost_ok = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") \
        <= cfg.cost_gate_k * edge_bps  # normative cost-gate predicate
    now = e["event_ts"]
    in_cooldown = now < state.get("cooldown_until", 0)  # C10
    locate_ok = bool(state.get("locate_ok", False))     # C7; default False
    tol = 1e-12  # [default] numeric guard: calibrated equalities survive float noise
    if sv >= cfg.sotm_threshold - tol:
        direction = 1
    elif sv <= -cfg.sotm_threshold + tol:
        direction = -1
    else:
        direction = 0
    if direction == -1 and not locate_ok:
        direction = 0  # C7: no locate, no short
    if (not cost_ok) or in_cooldown:
        direction, confidence, capital = 0, 0.0, 0.0  # C2, C10
    else:
        confidence = min(1.0, cfg.confidence_slope * abs(sv)) if direction != 0 else 0.0
        capital = 0.5 * confidence  # 0.5 [default]
    return SignalVector(sym, direction, confidence, capital,
                        e["event_ts"], 0, "OK")


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    rows = tape()
    cfg = Config()
    feats = compute_features(rows)
    exp = load_csv(EXPECTED)
    assert len(feats) == len(exp), (len(feats), len(exp))
    for f, w in zip(feats, exp):
        assert str(f["id"]) == str(w["id"]), (f["id"], w["id"])
        for col in FEATURE_COLS:
            assert _close(f[col], w[col]), (f["id"], col)

    sv = sotm_vol(rows, cfg)
    # Tape calibrated (seed 42) so the chapter's +1.5% hand-check reproduces:
    assert abs(sv - 0.015) < 1e-9, sv
    feats = compute_features(rows)
    sq = [f["sqret"] for f in feats[1:]]
    assert len(sq) == cfg.window_closes - 1  # 24 closes -> 23 log returns
    assert abs(sum(sq) - (23 / 252.0) * (0.112 ** 2 + 0.015 * 2 * 0.112)) < 1e-12
    legs = [r["leg"] for r in rows]
    assert legs[:12] == ["prior"] * 12 and legs[12:] == ["scenario"] * 12


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
    # full window on the calibrated fixture -> LONG at +1.50%
    assert sigs[-1].module_state == "OK"
    assert sigs[-1].direction == 1
    assert abs(sigs[-1].confidence - min(1.0, 20.0 * 0.015)) < 1e-12


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = tape()
    cfg, state = Config(), dict()
    for i in range(len(rows) - 1):
        s = signal(state, rows[: i + 1], cfg)
        fill_event_ts = event_ts(rows[i + 1])  # earliest possible fill: next event
        assert fill_event_ts > s.computed_at, "signal-bar fill at row %d" % i


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries; stack matches §S2."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert abs(cost - 1.85) < 1e-12, cost  # 0.50+0.30+0.0+(1.0+50*0.001)
    assert cost <= k * 100.0   # huge edge -> gate passes
    assert not (cost <= k * 0.01)  # tiny edge -> gate blocks
    # participation scaling: higher adv_pct -> higher cost
    assert expected_cost_bps(1.0, 0.01, "XNAS", "taker", "normal") > cost
    # maker branch: rebate lowers cost
    maker = expected_cost_bps(1.0, 0.001, "XNAS", "maker", "normal")
    assert abs(maker - (cost - 0.50)) < 1e-12, maker  # fee 0.30 -> -0.20


def test_invalid_input_yields_unknown():
    s = signal(dict(), [bad_event()], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0


def test_empty_events_yields_unknown():
    s = signal(dict(), [], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0


def test_short_gated_by_locate():
    """C7: SHORT needs a consumer-asserted locate; default state -> FLAT."""
    rows = flat_tape()
    cfg = Config()
    sv = sotm_vol(rows, cfg)
    assert abs(sv + 0.056) < 1e-12, sv  # (0 - 0.112^2) / (2 * 0.112)
    no_locate = signal(dict(), rows, cfg)
    assert no_locate.direction == 0, "short without locate must be zeroed"
    with_locate = signal({"locate_ok": True}, rows, cfg)
    assert with_locate.direction == -1
    assert with_locate.module_state == "OK"


def test_cost_gate_vetoes_on_tiny_k():
    """C2: cost gate failure zeroes direction even on the +1.50% fixture."""
    rows = tape()
    cfg = Config(cost_gate_k=1e-6)
    s = signal(dict(), rows, cfg)
    assert s.direction == 0
    assert s.confidence == 0.0 and s.capital == 0.0
