"""Acceptance tests for S049 — Distance-method pair.

Template v1.0.0; module deep-reviewed 2026-09-11 (module v1.1.0): the formation
window is a configurable parameter (Config.form_days), the cost stack
decomposes into named components with an explicit per-day borrow rate, and the
acceptance tests pin the cost-gate veto, window parameterization, and
incomplete-day masking in addition to the fixture arithmetic and causality.

Run: python3 -m pytest modules/tests/test_S049.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S049_tape.csv"
EXPECTED = FIX / "S049_expected.csv"

TOL = 1e-9  # [default] tolerance on float comparisons

# --- named module constants (mirror §S2 COST block / §S0.2 Config) ---
FORM_DAYS_DEFAULT = 12        # [example] fixture window; production 60-250 [example]
EDGE_BPS_PER_Z = 20.0         # [example] edge model: bps per unit of spread z
BORROW_BPS_PER_DAY = 1.37     # [example] ~500 bps/yr GC-ish short rate, illustrative
HOLD_DAYS_REF = 1.5           # [example] expected holding days for the reference stack


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
    """Group rows into complete (A,B) days -> [(day, ts, closeA, closeB)].

    Incomplete days (a leg missing) are masked: no contribution, state carries
    forward (§S3 normative pseudocode). Causality: ts = max of the leg stamps.
    """
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


def formation_days(days, form_days):
    """First `form_days` complete days = the formation window (Gatev-style)."""
    return [(d, ts, ca, cb) for d, ts, ca, cb in days if d <= form_days]


def formation_stats(days, form_days):
    """Pinned formation: spread = A/B - 1, sample sd (ddof=1)."""
    f = [ca / cb - 1.0 for d, _, ca, cb in formation_days(days, form_days)]
    mu = sum(f) / len(f)
    sd = (sum((x - mu) ** 2 for x in f) / (len(f) - 1)) ** 0.5
    return mu, sd


def _positions(days, mu, sd, cfg):
    """Position state machine: fade the stretch, exit on reversion."""
    pos = 0
    out = []
    for d, _, ca, cb in days:
        sp = ca / cb - 1.0
        if d <= cfg.form_days:  # formation window: stats shown, z/dir blank
            out.append((d, sp, mu, sd, float("nan"), 0))
            continue
        z = (sp - mu) / sd
        if pos == 0:
            if z >= cfg.entry_z:
                pos = -1      # spread stretched up -> short spread
            elif z <= -cfg.entry_z:
                pos = 1
        elif abs(z) <= cfg.exit_z:
            pos = 0
        out.append((d, sp, mu, sd, z, pos))
    return out


def compute_features(rows, cfg=None):
    cfg = cfg or Config()
    days = complete_days(rows)
    mu, sd = formation_stats(days, cfg.form_days)
    out = []
    for d, sp, mu_, sd_, z, pos in _positions(days, mu, sd, cfg):
        out.append({"id": "d%d" % d, "spread": sp, "form_mean": mu_,
                    "form_sd": sd_, "z": z, "dir": pos})
    return out


@dataclass
class Config:
    entry_z: float = 2.0          # entry trigger [example]
    exit_z: float = 0.5           # exit trigger [example]
    cost_gate_k: float = 0.5      # cost-gate multiplier [default]
    cooldown_s: float = 86_400.0  # one position per episode [default]
    form_days: int = FORM_DAYS_DEFAULT  # formation window [example]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: pairs distance entry, liquid large-caps.

    Stack (bps): spread 0.50 [example] + fees (taker 0.30 incl. regulatory
    [example]; maker -0.20 rebate [example]) + borrow
    BORROW_BPS_PER_DAY * HOLD_DAYS_REF [example] + impact 1.00 [example].
    """
    spread_bps = 0.50
    fee_bps = 0.30
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    borrow_bps = BORROW_BPS_PER_DAY * HOLD_DAYS_REF  # short leg [example]; C7 locate
    impact_bps = 1.00
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S049 reference stub).

    Fixture context assumes a healthy, locatable, cointegrated pair
    (state.pair_cointegrated / locate_ok True); production paths add the
    §S3 eligibility gates on top of the same arithmetic.
    """
    state = dict(state or {})
    state.setdefault("pair_cointegrated", True)
    state.setdefault("locate_ok", True)
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
    if len(formation_days(days, cfg.form_days)) < cfg.form_days:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    mu, sd = formation_stats(days, cfg.form_days)
    if not (sd > 0 and math.isfinite(mu) and math.isfinite(sd)):
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "UNKNOWN")
    track = _positions(days, mu, sd, cfg)
    pos = track[-1][5]
    z = track[-1][4]
    direction = pos
    # eligibility gates (§S2 entry rule): broken pair or missing locate -> FLAT
    if not state["pair_cointegrated"] or not state["locate_ok"]:
        direction = 0
    confidence = 0.6 if direction else 0.0  # entry conviction [example]
    capital = 0.5 * confidence
    # normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps (C2)
    edge_bps = abs(z) * EDGE_BPS_PER_Z if z == z else 0.0
    ok = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
    if not ok:
        direction, confidence, capital = 0, 0.0, 0.0
    return SignalVector("TEST:XNAS", direction, confidence, capital,
                        e["event_ts"], 0, "OK")


def rows_through(rows, day):
    """Event rows up to and including day `day` (causal prefix)."""
    return [r for r in rows if _day_key(r["id"]) <= day]


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
    # Chapter S4 hand-checks (seed 49): formation days 1-12 mean 0.000417,
    # sample sd 0.010326; day 13 z = +2.3807 -> short; day 15 z = +0.4438 -> exit.
    b12 = by_id["d12"]
    assert abs(b12["form_mean"] - 0.000417) < 1e-9, b12
    assert abs(b12["form_sd"] - 0.010326) < 1e-9, b12
    b13, b14, b15, b16 = by_id["d13"], by_id["d14"], by_id["d15"], by_id["d16"]
    assert abs(b13["z"] - 2.3807) < 1e-4, b13
    assert b13["dir"] == -1                    # entry: short the spread
    assert b14["dir"] == -1                    # hold: |z| > 0.5
    assert abs(b15["z"] - 0.4438) < 1e-4, b15
    assert b15["dir"] == 0                     # exit at 0.5 sigma
    assert b16["dir"] == 0
    # warmup days carry blank stats and no position
    assert by_id["d1"]["dir"] == 0
    # signal stub agrees with the feature state machine on the full tape
    s = signal(dict(), rows, Config())
    assert s.direction == 0 and s.module_state == "OK"   # flat after exit


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


def test_cost_stack_decomposes():
    """The 4-component stack is exactly: spread + fees + borrow/day*hold + impact."""
    taker = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert abs(taker - (0.50 + 0.30 + BORROW_BPS_PER_DAY * HOLD_DAYS_REF + 1.00)) < TOL
    maker = expected_cost_bps(1.0, 0.001, "XNAS", "maker", "normal")
    assert abs(maker - (0.50 - 0.20 + BORROW_BPS_PER_DAY * HOLD_DAYS_REF + 1.00)) < TOL
    assert maker < taker  # rebate side strictly cheaper in the reference stack


def test_gate_veto_zeros_direction():
    """On the entry day, a failing cost gate forces FLAT (C2 bona-fide-intent)."""
    rows = rows_through(tape(), 13)  # causal prefix ending at the entry day
    entry = signal(dict(), rows, Config())
    assert entry.direction == -1 and entry.module_state == "OK"  # gate passes at k=0.5
    vetoed = signal(dict(), rows, Config(cost_gate_k=0.001))
    assert vetoed.direction == 0 and vetoed.capital == 0.0
    assert vetoed.module_state == "OK"  # veto is a decision, not a failure


def test_formation_window_parameterized():
    """form_days is normative: changing it recomputes formation stats and the
    formation/trading boundary (pins §S0.2 Config.form_days)."""
    rows = tape()
    base = {f["id"]: f for f in compute_features(rows, Config())}
    alt = {f["id"]: f for f in compute_features(rows, Config(form_days=6))}
    # formation boundary moves: d7 leaves formation, so z appears on d7
    assert math.isnan(base["d7"]["z"]) and not math.isnan(alt["d7"]["z"])
    # stats recompute: mean/sd over 6 days differ from the 12-day window
    assert abs(alt["d13"]["form_mean"] - base["d13"]["form_mean"]) > 1e-6
    assert abs(alt["d13"]["z"] - base["d13"]["z"]) > 1e-6
    # the day-13 episode still reads as a stretched spread under both windows
    assert base["d13"]["dir"] == -1 and alt["d13"]["dir"] == -1


def test_incomplete_day_masked():
    """A day with only one leg contributes nothing: no crash, state carries."""
    rows = tape() + [{"id": "d17A", "event_ts": 1758382400000000000,
                      "sym": "A", "close": 101.0}]
    s = signal(dict(), rows, Config())
    assert s.module_state == "OK" and s.direction == 0  # flat carries from d16
    feats = compute_features(rows)
    assert len(feats) == 16  # d17 absent: masked, not interpolated


def test_invalid_input_yields_unknown():
    s = signal(dict(), [bad_event()], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0
