"""Acceptance tests for S051 — OU half-life timing overlay.

Template v1.0.0. Concrete: loads the fixture tape, runs a reference
implementation of the chapter's normative pseudocode (S051.md S3), and asserts
causality, the cost gate, unit-root/fit-failure handling, and hand-checked
fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S051.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S051_tape.csv"
EXPECTED = FIX / "S051_expected.csv"

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
                     "spread": float(r["spread"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "spread": float("nan")}


FEATURE_COLS = ["spread", "phi", "alpha", "kappa", "halflife",
                "active", "scalar", "dir"]


def ou_fit(spreads):
    """OLS of s_t on s_{t-1} -> (phi, alpha); kappa = -ln(phi)/dt (dt=1 day).

    Denominator zero (constant spread) or non-finite result -> NaN tuple
    (fit failure), handled as UNKNOWN (F2) by signal(), per S051 S3.
    """
    y = spreads[1:]
    x = spreads[:-1]
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    den = sum((v - mx) ** 2 for v in x)
    if den == 0.0:
        nan = float("nan")
        return nan, nan, nan, nan
    phi = sum((x[i] - mx) * (y[i] - my) for i in range(n)) / den
    alpha = my - phi * mx
    if not (math.isfinite(phi) and phi > 0.0):
        nan = float("nan")
        return nan, nan, nan, nan
    kappa = -math.log(phi)          # per day
    halflife = math.log(2.0) / kappa
    return phi, alpha, kappa, halflife


def compute_features(rows):
    cfg = Config()
    out = []
    for i, r in enumerate(rows):
        if i < cfg.min_points - 1:
            out.append({"id": r["id"], "spread": r["spread"],
                        "phi": float("nan"), "alpha": float("nan"),
                        "kappa": float("nan"), "halflife": float("nan"),
                        "active": 0, "scalar": 0.0, "dir": 0})
            continue
        seg = [x["spread"] for x in rows[:i + 1]]
        phi, alpha, kappa, hl = ou_fit(seg)
        active = 1 if hl <= cfg.max_halflife_d else 0
        # timing overlay: never an entry (dir 0); the scalar sizes the consumer
        out.append({"id": r["id"], "spread": r["spread"], "phi": phi,
                    "alpha": alpha, "kappa": kappa, "halflife": hl,
                    "active": active, "scalar": 1.0 if active else 0.0,
                    "dir": 0})
    return out


@dataclass
class Config:
    min_points: int = 5          # minimum points for the AR(1) fit [default]
    max_halflife_d: float = 10.0  # timer active while half-life <= 10d [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: int = 300        # post-exit cooldown, seconds [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: timing overlay (no orders of its own).

    Mirrors the COST block in S051 S2: maker branch included for symmetry.
    """
    spread_bps = 0.50   # consumer's reference [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # overlay emits no orders [default]; reason in table
    impact_bps = 1.00   # consumer's impact [example]
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S051 reference stub).

    Timing overlay: direction is always 0; the timer scalar rides in
    ``capital`` (1.0 active / 0.0 inactive) for the consumer to size with.

    Normative semantics (S051 S3):
      * empty events / non-finite spread -> UNKNOWN (F1/F2)
      * < min_points -> OK, scalar 0.0 (warmup)
      * fit failure (den==0 / NaN phi) -> UNKNOWN (F2)
      * phi >= 1.0 -> OK, scalar 0.0 (unit root: informative veto)
      * cost gate binds only on direction != 0 (never for the timer);
        the scalar is NEVER gated by it — the consumer applies its own gate.
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if not math.isfinite(e["spread"]):
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    if len(evs) < cfg.min_points:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    phi, alpha, kappa, hl = ou_fit([x["spread"] for x in evs])
    if not math.isfinite(phi):
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")  # F2 fit failure
    if phi >= 1.0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "OK")  # unit root: no reversion
    active = hl <= cfg.max_halflife_d
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = 0.0  # timer has no own edge [default]
    cost_ok = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") \
        <= cfg.cost_gate_k * edge_bps
    direction = 0  # timer: never an entry
    if direction != 0 and not cost_ok:
        direction = 0  # C2: gate binds only on direction != 0
    # normative: the scalar is never gated by cost_ok; the consumer gates (C11)
    scalar = 1.0 if active else 0.0
    return SignalVector("TEST:XNAS", direction, 0.0, scalar,
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
    # Exact-decay fixture: spread_t = 8 * 0.8**(t-1) -> AR(1) phi = 0.8,
    # alpha = 0, kappa = -ln(0.8) = 0.2231/day, half-life = 3.1063 days.
    b60 = by_id["d60"]
    assert abs(b60["phi"] - 0.8) < 1e-9, b60
    assert abs(b60["alpha"]) < 1e-9, b60
    assert abs(b60["kappa"] - 0.2231436) < 1e-6, b60
    assert abs(b60["halflife"] - 3.1062837) < 1e-6, b60
    assert b60["active"] == 1 and b60["scalar"] == 1.0 and b60["dir"] == 0
    # the running fit is exact on every defined row (deterministic decay)
    for i in range(5, 61):
        f = by_id["d%d" % i]
        assert abs(f["halflife"] - 3.1062837) < 1e-6, (i, f)
        assert f["active"] == 1
    # warmup rows carry blank estimates
    assert by_id["d1"]["active"] == 0 and by_id["d4"]["scalar"] == 0.0
    # stub: timer scalar rides in capital, direction always 0
    s = signal(dict(), rows, Config())
    assert s.direction == 0 and s.capital == 1.0 and s.module_state == "OK"



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
    # maker branch mirrors the COST block: rebate reduces the stack
    maker = expected_cost_bps(1.0, 0.001, "XNAS", "maker", "normal")
    assert abs(maker - (0.50 - 0.20 + 0.0 + 1.00)) < 1e-12, maker
    assert abs(cost - 1.80) < 1e-12, cost


def test_invalid_input_yields_unknown():
    s = signal(dict(), [bad_event()], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0


def _events_from(spreads, t0=1757000000000000000, step=86400000000000):
    return [{"id": "x%d" % i, "event_ts": t0 + i * step,
             "spread": float(v)} for i, v in enumerate(spreads)]


def test_unit_root_fit_is_informative_veto():
    """phi >= 1 -> no reversion: OK with scalar 0.0, not a fit failure."""
    evs = _events_from([1.0 * (1.1 ** i) for i in range(10)])  # explosive
    s = signal(dict(), evs, Config())
    assert s.module_state == "OK"
    assert s.direction == 0 and s.capital == 0.0  # informative veto


def test_fit_failure_yields_unknown():
    """Constant spread -> zero OLS denominator -> UNKNOWN (F2)."""
    evs = _events_from([2.0] * 10)
    s = signal(dict(), evs, Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0


def test_warmup_below_min_points():
    evs = _events_from([8.0 * (0.8 ** i) for i in range(3)])  # 3 < min_points
    s = signal(dict(), evs, Config())
    assert s.module_state == "OK"
    assert s.direction == 0 and s.capital == 0.0


def test_cost_gate_never_gates_scalar():
    """Normative pin: with edge_bps = 0 the gate fails, yet an active
    timer still emits scalar 1.0 — the gate binds only on direction != 0."""
    cfg = Config()
    rows = tape()
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert not (cost <= cfg.cost_gate_k * 0.0)  # gate fails (edge 0) [default]
    s = signal(dict(), rows, cfg)
    assert s.direction == 0 and s.capital == 1.0 and s.module_state == "OK"
