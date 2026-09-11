"""Acceptance tests for S032 — Multi-asset crisis-regime filter.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S032.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S032_tape.csv"
EXPECTED = FIX / "S032_expected.csv"

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



SCORE_THRESHOLD = 0.9   # crisis rule [example]
ZWIN = 1260             # z-score trailing window [example]
RW = 60                # rolling window for vol / correlation / drawdown [example]


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({"id": r["id"], "event_ts": int(r["event_ts"]),
                     "close": float(r["close"]),
                     "bond_close": float(r["bond_close"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "close": -10.0,
            "bond_close": 100.0}  # negative close


FEATURE_COLS = ["rollvol", "rv60", "rollcor60", "drawdown", "volofvol",
                "regime_score", "crisis_flag", "regime_flag", "regime_p"]


def _fit_logistic(xs, ys, lam=1.0):
    b0, b1 = 0.0, 0.0
    for _ in range(50):
        g0, g1 = -lam * b0, -lam * b1
        h00, h01, h11 = lam, 0.0, lam
        for x, y in zip(xs, ys):
            z = b0 + b1 * x
            p = 1.0 / (1.0 + math.exp(-z)) if z >= -700 else 0.0
            w = p * (1.0 - p)
            g0 += (y - p); g1 += (y - p) * x
            h00 += w; h01 += w * x; h11 += w * x * x
        det = h00 * h11 - h01 * h01
        if det == 0:
            break
        d0 = (h11 * g0 - h01 * g1) / det
        d1 = (h00 * g1 - h01 * g0) / det
        b0 += d0; b1 += d1
        if abs(d0) + abs(d1) < 1e-12:
            break
    return b0, b1


def compute_features(rows):
    import math as _m
    n = len(rows)
    SQ252 = _m.sqrt(252.0)
    rx = [0.0] * n; rby = [0.0] * n
    for i in range(1, n):
        rx[i] = _m.log(rows[i]["close"] / rows[i - 1]["close"])
        rby[i] = _m.log(rows[i]["bond_close"] / rows[i - 1]["bond_close"])
    W, Z = RW, ZWIN
    rollvol = [float("nan")] * n; rv60 = [float("nan")] * n
    rho = [float("nan")] * n
    s1x = s2x = s1y = s2y = sxy = 0.0
    for i in range(n):
        if i >= 1:
            x, y = rx[i], rby[i]
            s1x += x; s2x += x * x; s1y += y; s2y += y * y; sxy += x * y
            if i - W >= 1:
                ox, oy = rx[i - W], rby[i - W]
                s1x -= ox; s2x -= ox * ox; s1y -= oy; s2y -= oy * oy
                sxy -= ox * oy
        if i >= W:
            var = (s2x - s1x * s1x / W) / (W - 1)
            rollvol[i] = SQ252 * _m.sqrt(max(var, 0.0))
            rv60[i] = SQ252 * _m.sqrt(s2x / W)
            den = (W * s2x - s1x * s1x) * (W * s2y - s1y * s1y)
            rho[i] = (W * sxy - s1x * s1y) / _m.sqrt(den) if den > 0 else 0.0
    dd = [float("nan")] * n
    for i in range(n):
        if i >= W - 1:
            hi = max(rows[j]["close"] for j in range(i - W + 1, i + 1))
            dd[i] = (hi - rows[i]["close"]) / hi
    vov = [float("nan")] * n
    for i in range(n):
        if i >= W + 19 and not _m.isnan(rollvol[i - 19]):
            wv = rollvol[i - 19:i + 1]
            m = sum(wv) / 20
            vov[i] = _m.sqrt(sum((z - m) ** 2 for z in wv) / 19)
    c6 = [float("nan")] * n
    for i in range(n):
        if i >= W and not _m.isnan(rho[i]):
            c6[i] = abs(rho[i] - sum(rho[i - W + 1:i + 1]) / W)
    comps = [rollvol, rv60,
             [abs(v) if not _m.isnan(v) else v for v in rho],
             dd, vov, c6]
    S = [0.0] * 6; SS = [0.0] * 6
    score = [float("nan")] * n
    for i in range(n):
        vals = [c[i] for c in comps]
        if any(_m.isnan(v) for v in vals):
            continue
        for k, v in enumerate(vals):
            S[k] += v; SS[k] += v * v
            if i - Z >= 0:
                ov = comps[k][i - Z]
                if not _m.isnan(ov):
                    S[k] -= ov; SS[k] -= ov * ov
        if i >= 79 + Z:
            zs = []
            for k in range(6):
                m = S[k] / Z
                var = (SS[k] - S[k] * S[k] / Z) / (Z - 1)
                sd = _m.sqrt(max(var, 0.0))
                zs.append((vals[k] - m) / sd if sd > 0 else 0.0)
            score[i] = sum(zs) / 6
    crisis = [0] * n
    for i in range(n):
        if not _m.isnan(score[i]) and score[i] >= SCORE_THRESHOLD:
            crisis[i] = 1
    # AR(1) logistic: fit ONCE on the trailing-Z scored days before the final
    # day (fixture simplification; production refits daily per the chapter).
    F = n - 1
    xs, ys = [], []
    for i in range(max(F - Z, 1), F):  # clamp: short prefixes

        if not _m.isnan(score[i]) and not _m.isnan(score[i - 1]):
            xs.append(score[i - 1]); ys.append(crisis[i])
    b0, b1 = _fit_logistic(xs, ys)
    out = []
    for i in range(n):
        r = rows[i]
        sc = score[i]
        if _m.isnan(sc) or i == 0 or _m.isnan(score[i - 1]):
            out.append({"id": r["id"], "rollvol": float("nan"),
                        "rv60": float("nan"), "rollcor60": float("nan"),
                        "drawdown": float("nan"), "volofvol": float("nan"),
                        "regime_score": float("nan"), "crisis_flag": 0,
                        "regime_flag": 0, "regime_p": float("nan")})
            continue
        z = b0 + b1 * score[i - 1]
        p = 1.0 / (1.0 + _m.exp(-z)) if z >= -700 else 0.0
        out.append({"id": r["id"], "rollvol": rollvol[i], "rv60": rv60[i],
                    "rollcor60": rho[i], "drawdown": dd[i],
                    "volofvol": vov[i], "regime_score": sc,
                    "crisis_flag": crisis[i],
                    "regime_flag": 1 if p >= 0.5 else 0, "regime_p": p})
    return out


@dataclass
class Config:
    roll_window: int = 60        # vol/corr/drawdown window [example]
    z_window: int = 1260         # z-score trailing window [example]
    crisis_threshold: float = 0.9  # crisis rule [example]
    cost_gate_k: float = 0.5      # cost-gate multiplier [default]
    cooldown_s: float = 86_400.0  # post-crisis cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: daily regime overlay (hedge overlay leg)."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0     # long-biased reference; reason: no borrow [default]
    impact_bps = 0.50    # daily-rebalance concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S032 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["close"] <= 0 or e["bond_close"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    feats = compute_features(evs)
    f = feats[-1]
    import math as _m
    if _m.isnan(f["regime_p"]):
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    defensive = f["regime_p"] >= 0.5
    direction = -1 if defensive else 0  # regime veto: de-risk, never a long call
    confidence = f["regime_p"] if defensive else 0.0
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = 2.0 * abs(f["regime_score"])  # stress-avoidance value [example]
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
    d1900 = by_id["d1900"]  # mid-crash day, operator-verified on the synthetic tape
    assert abs(d1900["rollvol"] - 0.4975) < 1e-3, d1900
    assert abs(d1900["rv60"] - 0.4966) < 1e-3, d1900
    assert abs(d1900["rollcor60"] - 0.865) < 1e-3, d1900
    assert abs(d1900["drawdown"] - 0.1757) < 1e-3, d1900
    assert abs(d1900["regime_score"] - 1.937) < 1e-3, d1900
    assert d1900["crisis_flag"] == 1
    assert abs(d1900["regime_p"] - 0.9996) < 1e-3, d1900
    assert d1900["regime_flag"] == 1
    # warmup: first scored day is d1341 (60-day vol + 20-day vol-of-vol + 1260-day z;
    # score starts at 0-indexed i=1339, regime_p needs a lagged score too)
    assert by_id["d1340"]["regime_p"] != by_id["d1340"]["regime_p"]  # NaN
    assert by_id["d1341"]["regime_p"] == by_id["d1341"]["regime_p"]  # not NaN



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
