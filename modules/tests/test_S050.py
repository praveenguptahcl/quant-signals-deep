"""Acceptance tests for S050 — Engle–Granger z-score.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic. Tests 6–9 use
synthetic inline episodes (the fixture tape covers only one long-spread entry
and hold; see §S4 coverage limits).

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
    beta_stip: float = 2.0       # pinned stipulated ratio [calibrate]
    formation_window_days: int = 12       # [example]; production calibrate 60-252
    adf_significance: float = 0.05        # [calibrate]
    coint_lag_max: int = 10               # [default]
    formation_fresh_days: int = 63        # [default]
    ols_window_days: int = 252            # [default]
    drift_tolerance: float = 0.10         # [default]
    confidence_denom: float = 3.0         # [default] normative §S3


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
    # normative confidence: min(1, |z|/confidence_denom) (§S3)
    z = _positions(days, mu, sd, cfg)[-1][4]
    confidence = min(1.0, abs(z) / cfg.confidence_denom) if direction and z == z else 0.0
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
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


# -------------------------------- synthetic inline episodes (fixture has no
# exit/short/veto episodes; see §S4 coverage limits)
def synthetic_rows(spreads, baseB=100.0, day0=1, ts0=1757000000000000000):
    """Synthetic pair rows with spread = A - BETA_STIP * B (B pinned at baseB)."""
    rows = []
    for i, sp in enumerate(spreads):
        d = day0 + i
        ts = ts0 + i * 86_400_000_000_000
        rows.append({"id": "d%dA" % d, "event_ts": ts, "sym": "A",
                     "close": BETA_STIP * baseB + sp})
        rows.append({"id": "d%dB" % d, "event_ts": ts + 1_000_000_000,
                     "sym": "B", "close": baseB})
    return rows


def alternating_formation(n=12):
    """mu=0, sd=sqrt(3/11) formation spreads."""
    return [0.5, -0.5] * (n // 2)


def test_exit_crossing_exits():
    # day13 spread -1.0 -> z≈-1.915 <= -1.5 (long); day14 spread -0.2 -> |z|≈0.383 -> exit
    rows = synthetic_rows(alternating_formation() + [-1.0, -0.2])
    feats = compute_features(rows)
    by_id = {f["id"]: f for f in feats}
    assert by_id["d13"]["dir"] == 1
    assert abs(by_id["d13"]["z"] - (-1.0 / (3.0 / 11) ** 0.5)) < 1e-9
    assert by_id["d14"]["dir"] == 0  # exit at |z| <= 0.5


def test_short_side_entry():
    rows = synthetic_rows(alternating_formation() + [1.0])
    feats = compute_features(rows)
    assert feats[-1]["dir"] == -1   # z≈+1.915 >= +1.5 -> short the spread


def test_cost_gate_veto_at_signal_level():
    rows = synthetic_rows(alternating_formation() + [-1.0])
    veto_cfg = Config(cost_gate_k=0.05)  # 0.05 * ~38.3bps = ~1.9bps < 3.8bps cost
    s_veto = signal(dict(), rows, veto_cfg)
    assert s_veto.module_state == "OK" and s_veto.direction == 0
    s_pass = signal(dict(), rows, Config())
    assert s_pass.direction == 1  # defaults: 0.5 * ~38.3bps = ~19.2bps >= 3.8bps


def test_insufficient_formation_data_no_entry():
    rows = synthetic_rows(alternating_formation(n=6))  # 6 days < 12 required
    s = signal(dict(), rows, Config())
    assert s.module_state == "OK" and s.direction == 0
