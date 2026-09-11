"""Acceptance tests for S048 — LOB resiliency / temporary-impact reversion.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S048.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S048_tape.csv"
EXPECTED = FIX / "S048_expected.csv"

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
                     "t_sec": float(r["t_sec"]),
                     "impact_bps": float(r["impact_bps"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "t_sec": 0.0,
            "impact_bps": -1.0}  # negative impact


FEATURE_COLS = ["kappa", "halflife", "dir"]


def fit_decay(ts, imps):
    """OLS: log(|impact|) = intercept - kappa * t -> (kappa, intercept, halflife)."""
    ly = [math.log(abs(x)) for x in imps]
    n = len(ts)
    mx, my = sum(ts) / n, sum(ly) / n
    den = sum((t - mx) ** 2 for t in ts)
    slope = sum((t - mx) * (l - my) for t, l in zip(ts, ly)) / den
    kappa = -slope
    intercept = my - slope * mx
    hl = math.log(2.0) / kappa if kappa > 0 else float("nan")
    return kappa, intercept, hl


def compute_features(rows):
    cfg = Config()
    out = []
    for i, r in enumerate(rows):
        if i < 2:
            out.append({"id": r["id"], "kappa": float("nan"),
                        "halflife": float("nan"), "dir": 0})
            continue
        seg = rows[:i + 1]
        kappa, _, hl = fit_decay([x["t_sec"] for x in seg],
                                 [x["impact_bps"] for x in seg])
        valid = 1 if (kappa > 0 and cfg.hl_min_s <= hl <= cfg.hl_max_s) else 0
        # fade the signed shock only if the estimated decay is valid
        d = -cfg.shock_sign * valid
        out.append({"id": r["id"], "kappa": kappa, "halflife": hl, "dir": d})
    return out


@dataclass
class Config:
    shock_sign: int = 1          # +1 = buy shock [example]
    hl_min_s: float = 1.0        # valid half-life band [example]
    hl_max_s: float = 120.0      # valid half-life band [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 300.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: impact-reversion, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.00   # concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S048 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["impact_bps"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    if len(evs) < 3:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    kappa, _, hl = fit_decay([x["t_sec"] for x in evs],
                             [x["impact_bps"] for x in evs])
    valid = kappa > 0 and cfg.hl_min_s <= hl <= cfg.hl_max_s
    direction = -cfg.shock_sign if valid else 0
    confidence = 0.6 if valid else 0.0  # decay-fit conviction [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = 5.0  # half the shock decays [example]
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

    kappa, intercept, hl = fit_decay([r["t_sec"] for r in rows],
                                     [r["impact_bps"] for r in rows])
    # Exact-decay fixture: I(t) = 10*exp(-0.05 t) -> kappa = 0.05/s,
    # half-life = ln2/0.05 = 13.8629 s.
    assert abs(kappa - 0.05) < 1e-9, kappa
    assert abs(intercept - math.log(10.0)) < 1e-9, intercept
    assert abs(hl - 13.8629) < 1e-3, hl
    by_id = {f["id"]: f for f in feats}
    assert by_id["s30"]["dir"] == -1  # fade the +signed shock
    assert abs(by_id["s30"]["kappa"] - 0.05) < 1e-9
    # running fit is exact on every defined row (deterministic decay)
    assert all(abs(by_id["s%d" % i]["halflife"] - math.log(2) / 0.05) < 1e-9
               for i in range(2, 31))



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
