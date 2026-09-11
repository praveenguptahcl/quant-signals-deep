"""Acceptance tests for S050 — Engle–Granger z-score.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S050.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S050_tape.csv"
EXPECTED = FIX / "S050_expected.csv"

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



BETA_STIP = 2.0  # stipulated hedge ratio (pinned; never silently replaced)


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({"id": r["id"], "event_ts": int(r["event_ts"]),
                     "sym": r["sym"], "close": float(r["close"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "d0A", "event_ts": 1, "sym": "A", "close": -5.0}


FEATURE_COLS = ["spread", "form_mean", "form_sd", "z", "dir"]


def _day_key(rid):
    return int(rid[1:-1])  # "d13A" -> 13


def complete_days(rows):
    by_day = {}
    for r in rows:
        d = _day_key(r["id"])
        by_day.setdefault(d, {})[r["sym"]] = (r["close"], r["event_ts"])
    out = []
    for d in sorted(by_day):
        if "A" in by_day[d] and "B" in by_day[d]:
            (ca, ta), (cb, tb) = by_day[d]["A"], by_day[d]["B"]
            out.append((d, max(ta, tb), ca, cb))
    return out


def formation_stats(days):
    """Pinned formation: days 1..12, spread = A - BETA_STIP * B."""
    f = [ca - BETA_STIP * cb for d, _, ca, cb in days if d <= 12]
    mu = sum(f) / len(f)
    sd = (sum((x - mu) ** 2 for x in f) / (len(f) - 1)) ** 0.5
    return mu, sd


def full_tape_ols(days):
    """Full-sample OLS of A on B: the ESTIMATED ratio (diagnostic only)."""
    A = [ca for _, _, ca, _ in days]
    Bv = [cb for _, _, _, cb in days]
    n = len(days)
    mb, ma = sum(Bv) / n, sum(A) / n
    varB = sum((b - mb) ** 2 for b in Bv) / n
    covAB = sum((A[i] - ma) * (Bv[i] - mb) for i in range(n)) / n
    beta_hat = covAB / varB
    alpha_hat = ma - beta_hat * mb
    return beta_hat, alpha_hat


def _positions(days, mu, sd, cfg):
    pos = 0
    out = []
    for d, _, ca, cb in days:
        sp = ca - BETA_STIP * cb
        if d <= 12:  # formation window: stats shown, z/dir blank
            out.append((d, sp, mu, sd, float("nan"), 0))
            continue
        z = (sp - mu) / sd
        if pos == 0:
            if z <= -cfg.entry_z:
                pos = 1       # A cheap vs stipulated ratio -> long spread
            elif z >= cfg.entry_z:
                pos = -1
        elif abs(z) <= cfg.exit_z:
            pos = 0
        out.append((d, sp, mu, sd, z, pos))
    return out


def compute_features(rows):
    cfg = Config()
    days = complete_days(rows)
    mu, sd = formation_stats(days)
    out = []
    for d, sp, mu_, sd_, z, pos in _positions(days, mu, sd, cfg):
        out.append({"id": "d%d" % d, "spread": sp, "form_mean": mu_,
                    "form_sd": sd_, "z": z, "dir": pos})
    return out


@dataclass
class Config:
    entry_z: float = 1.5         # entry trigger [example]
    exit_z: float = 0.5          # exit trigger [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 86_400.0  # one position per episode [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: cointegration-spread entry, liquid large-caps."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 2.00   # short leg [example]; flagged, C7 locate
    impact_bps = 1.00   # concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S050 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    # F1/F2: invalid input -> UNKNOWN, never interpolate (before completeness)
    for r in evs:
        if r["close"] <= 0:
            return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                                r["event_ts"], 0, "UNKNOWN")
    e = evs[-1]
    days = complete_days(evs)
    if len([d for d in days if d[0] <= 12]) < 12:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    mu, sd = formation_stats(days)
    pos = _positions(days, mu, sd, cfg)[-1][5]
    direction = pos
    confidence = 0.6 if direction else 0.0  # coint-spread conviction [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    z = _positions(days, mu, sd, cfg)[-1][4]
    edge_bps = abs(z) * 20.0 if z == z else 0.0  # 20bps per unit z [example]
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
    days = complete_days(rows)
    # Chapter S4 hand-checks (seed 50): stipulated beta 2.0; formation
    # mean 0, sd 1.3009; day-15 z = -1.5374 -> long spread.
    mu, sd = formation_stats(days)
    assert abs(mu) < 1e-9, mu
    assert abs(sd - 1.3009) < 1e-9, sd
    b15 = by_id["d15"]
    assert abs(b15["z"] - (-1.5374)) < 1e-4, b15
    assert b15["dir"] == 1                     # entry: long the spread
    assert by_id["d14"]["dir"] == 0
    assert by_id["d30"]["dir"] == 1            # held: |z| never <= 0.5
    # the stipulated-vs-estimated distinction: full-sample OLS differs
    beta_hat, alpha_hat = full_tape_ols(days)
    assert abs(beta_hat - 1.720914) < 1e-6, beta_hat
    assert abs(alpha_hat - 3.545001) < 1e-6, alpha_hat
    assert abs(beta_hat - BETA_STIP) > 0.1    # estimated != stipulated
    # signal stub agrees with the feature state machine
    s = signal(dict(), rows, Config())
    assert s.direction == 1 and s.module_state == "OK"



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
