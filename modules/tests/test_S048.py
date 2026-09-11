"""Acceptance tests for S048 — LOB resiliency / temporary-impact reversion.

Template v1.0.0. Loads the fixture tape, runs the reference implementation of
the chapter's normative pseudocode (§S3), and asserts warmup handling, the
decay-validity gates (snapshot count, R^2, kappa sign, half-life band),
cooldown, the locate veto, the cost gate, seq-gap DEGRADED, shock-registration
(F1/C11), and the t->t+1 causality contract.

Run: python3 -m pytest modules/tests/test_S048.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, field
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


@dataclass
class Config:
    shock_sign: int = 1          # +1 = buy shock [example]; fixed by the shock-ID rule, not calibrated
    min_snapshots: int = 10      # fit needs >= this many snapshots [default]
    r2_min: float = 0.5          # log-fit R^2 floor [default]
    hl_min_s: float = 1.0        # valid half-life band [default]
    hl_max_s: float = 120.0      # valid half-life band [default]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 300.0    # post-exit cooldown, C10 hygiene [default]
    seq_tol: int = 1             # max tolerated seq gap [default]


@dataclass
class ModuleState:
    module_state: str = "OK"
    registered_shock: dict = None       # {'t0': event_ts, 'sign': +1/-1, 'size_bps': float}
    cooldown_until: int = 0             # int64 ns UTC
    market_state: str = "CONTINUOUS_TRADING"
    locate_ok: bool = True


FEATURE_COLS = ["kappa", "halflife", "dir"]


def fit_decay(ts, imps):
    """OLS: log(|impact|) = intercept - kappa * t -> (kappa, intercept, halflife, r2)."""
    ly = [math.log(abs(x)) for x in imps]
    n = len(ts)
    mx, my = sum(ts) / n, sum(ly) / n
    den = sum((t - mx) ** 2 for t in ts)
    slope = sum((t - mx) * (l - my) for t, l in zip(ts, ly)) / den
    kappa = -slope
    intercept = my - slope * mx
    ss_res = sum((l - (intercept + slope * t)) ** 2 for t, l in zip(ts, ly))
    ss_tot = sum((l - my) ** 2 for l in ly)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    hl = math.log(2.0) / kappa if kappa > 0 else float("nan")
    return kappa, intercept, hl, r2


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({"id": r["id"], "event_ts": int(r["event_ts"]),
                     "t_sec": float(r["t_sec"]),
                     "impact_bps": float(r["impact_bps"]),
                     "seq": int(r["seq"])})
    return rows


def shock_state(rows, sign=1, size_bps=10.0):
    """Registered shock for the fixture: buy shock at t=0 [example]."""
    return ModuleState(registered_shock={"t0": rows[0]["event_ts"],
                                        "sign": sign, "size_bps": size_bps})


def bad_event():
    return {"id": "bad", "event_ts": 1, "t_sec": 0.0,
            "impact_bps": -1.0, "seq": 0}  # negative impact


def compute_features(rows):
    cfg = Config()
    out = []
    for i, r in enumerate(rows):
        if i < 2:
            out.append({"id": r["id"], "kappa": float("nan"),
                        "halflife": float("nan"), "dir": 0})
            continue
        seg = rows[:i + 1]
        kappa, _, hl, _r2 = fit_decay([x["t_sec"] for x in seg],
                                      [x["impact_bps"] for x in seg])
        valid = 1 if (kappa > 0 and cfg.hl_min_s <= hl <= cfg.hl_max_s) else 0
        # fade the signed shock only if the estimated decay is valid
        d = -cfg.shock_sign * valid
        out.append({"id": r["id"], "kappa": kappa, "halflife": hl, "dir": d})
    return out


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: impact-reversion, liquid large-cap. Callable per §S2."""
    spread_bps = 0.50         # half-spread [example]
    fee_bps = 0.30            # taker incl. regulatory [example]
    borrow_bps_per_day = 0.0  # long-biased reference; ~seconds holding period [default]
    impact_bps = 1.00         # concession [example]
    if side == "maker":
        fee_bps = -0.20       # rebate [example]
    return spread_bps + fee_bps + borrow_bps_per_day + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S048 reference implementation).

    Implements the §S3 normative pseudocode: shock-registration gate (C11),
    market-state freeze, F1/F2 invalid-input -> UNKNOWN, warmup hold,
    decay-validity gates (snapshot count, kappa sign, R^2 floor, half-life
    band), cooldown (C10), cost gate (C2), locate veto for SHORT (C7),
    seq-gap -> DEGRADED, and the t->t+1 causality assertion.
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")  # F1
    e = evs[-1]
    # market-state freeze (§S0.5)
    if state.market_state == "HALTED":
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "UNKNOWN")
    if state.market_state == "AUCTION":
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "DEGRADED")
    if state.market_state == "CLOSED":
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OFF")
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["impact_bps"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    # seq-gap beyond tolerance -> DEGRADED (restart windows)
    seqs = [x["seq"] for x in evs]
    if any(b - a > cfg.seq_tol for a, b in zip(seqs, seqs[1:])):
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "DEGRADED")
    # C11: no fade without an identified (registered) shock
    shock = state.registered_shock
    if shock is None or e["event_ts"] < shock["t0"]:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "UNKNOWN")
    # warmup: too few snapshots -> hold flat, OK (not an input failure)
    snaps = [x for x in evs if x["event_ts"] >= shock["t0"]]
    n = len(snaps)
    if n < cfg.min_snapshots:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    # C10: post-exit cooldown
    if e["event_ts"] < state.cooldown_until:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    kappa, _icept, hl, r2 = fit_decay([x["t_sec"] for x in snaps],
                                      [x["impact_bps"] for x in snaps])
    # decay-validity gates (§S2 Robustness, every prose guard)
    valid = (kappa > 0 and r2 >= cfg.r2_min
             and cfg.hl_min_s <= hl <= cfg.hl_max_s)
    direction = -shock["sign"] if valid else 0
    conviction = r2 * min(1.0, n / 30.0)              # [example]
    confidence = min(1.0, conviction) if direction != 0 else 0.0
    capital = 0.5 * confidence                        # 0.5 [default]
    # normative edge and cost-gate predicate (C2 bona-fide intent)
    edge_bps = shock["size_bps"] / 2.0                # half the shock decays back [default]
    cost_ok = (expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
               <= cfg.cost_gate_k * edge_bps)
    if not cost_ok:
        direction, confidence, capital = 0, 0.0, 0.0
    # C7: SHORT requires an asserted locate
    if direction == -1 and not state.locate_ok:
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

    kappa, intercept, hl, r2 = fit_decay([r["t_sec"] for r in rows],
                                         [r["impact_bps"] for r in rows])
    # Exact-decay fixture: I(t) = 10*exp(-0.05 t) -> kappa = 0.05/s,
    # half-life = ln2/0.05 = 13.8629 s, R^2 = 1.
    assert abs(kappa - 0.05) < 1e-9, kappa
    assert abs(intercept - math.log(10.0)) < 1e-9, intercept
    assert abs(hl - 13.8629) < 1e-3, hl
    assert abs(r2 - 1.0) < 1e-9, r2
    by_id = {f["id"]: f for f in feats}
    assert by_id["s30"]["dir"] == -1  # fade the +signed shock
    assert abs(by_id["s30"]["kappa"] - 0.05) < 1e-9
    # running fit is exact on every defined row (deterministic decay)
    assert all(abs(by_id["s%d" % i]["halflife"] - math.log(2) / 0.05) < 1e-9
               for i in range(2, 31))
    # warmup rows are NaN-held (fixture mirrors the warmup hold)
    assert math.isnan(by_id["s0"]["kappa"]) and math.isnan(by_id["s1"]["kappa"])


def test_signal_emits_valid_signalvector():
    rows = tape()
    cfg, state = Config(), shock_state(rows)
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    # warmup rows hold flat, OK (n < min_snapshots=10); the 10th snapshot goes live
    assert [s.direction for s in sigs[:9]] == [0] * 9
    assert sigs[9].direction == -1
    # once the fit matures, the reference fade is live
    assert sigs[-1].direction == -1


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = tape()
    cfg, state = Config(), shock_state(rows)
    for i in range(len(rows) - 1):
        s = signal(state, rows[: i + 1], cfg)
        fill_event_ts = rows[i + 1]["event_ts"]  # earliest possible fill: next event
        assert fill_event_ts > s.computed_at, "signal-bar fill at row %d" % i


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert cost > 0
    assert cost <= k * 100.0   # huge edge -> gate passes
    assert not (cost <= k * 0.01)  # tiny edge -> gate blocks


def test_cost_gate_side_variants():
    """Side field is exercised: maker rebate lowers the stack."""
    taker = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    maker = expected_cost_bps(1.0, 0.001, "XNAS", "maker", "normal")
    assert abs(taker - 1.80) < 1e-9, taker
    assert abs(maker - 1.30) < 1e-9, maker  # 0.50 - 0.20 + 0.0 + 1.00
    assert maker < taker


def test_invalid_input_yields_unknown():
    s = signal(ModuleState(registered_shock={"t0": 1, "sign": 1, "size_bps": 10.0}),
               [bad_event()], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0


def test_shock_registration_required():
    """C11: no fade without an identified (registered) shock."""
    rows = tape()
    s = signal(ModuleState(registered_shock=None), rows, Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0


def test_r2_gate_blocks_poor_fit():
    """R^2 floor vetoes a decaying-but-noisy fit: kappa>0, half-life in band,
    R^2 = 0.22 < 0.5 -> direction 0, still OK (no input failure)."""
    base = 1757000000000000000
    ts = [2.0 * i for i in range(12)]
    imps = [10.0 * math.exp(-0.05 * t) * (1.8 if i % 2 == 0 else 0.3)
            for i, t in enumerate(ts)]
    rows = [{"id": "n%d" % i, "event_ts": base + int(t * 1e9),
             "t_sec": t, "impact_bps": imp, "seq": i}
            for i, (t, imp) in enumerate(zip(ts, imps))]
    kappa, _i, hl, r2 = fit_decay(ts, imps)
    assert kappa > 0 and 1.0 <= hl <= 120.0 and r2 < 0.5, (kappa, hl, r2)
    state = ModuleState(registered_shock={"t0": base, "sign": 1, "size_bps": 10.0})
    s = signal(state, rows, Config())
    assert s.module_state == "OK"
    assert s.direction == 0 and s.confidence == 0.0


def test_negative_kappa_vetoes_fade():
    """Growing impact (kappa <= 0) is the opposite regime -> no fade."""
    base = 1757000000000000000
    ts = [2.0 * i for i in range(12)]
    imps = [1.0 * math.exp(0.05 * t) for t in ts]  # permanent/growing impact
    rows = [{"id": "g%d" % i, "event_ts": base + int(t * 1e9),
             "t_sec": t, "impact_bps": imp, "seq": i}
            for i, (t, imp) in enumerate(zip(ts, imps))]
    state = ModuleState(registered_shock={"t0": base, "sign": 1, "size_bps": 10.0})
    s = signal(state, rows, Config())
    assert s.direction == 0 and s.confidence == 0.0
    assert s.module_state == "OK"


def test_cost_gate_vetoes_in_signal():
    """A near-zero cost-gate k blocks the fade inside the signal path (C2)."""
    rows = tape()
    cfg = Config(cost_gate_k=1e-9)  # [example] adversarially tiny k
    s = signal(shock_state(rows), rows, cfg)
    assert s.direction == 0 and s.confidence == 0.0 and s.capital == 0.0
    assert s.module_state == "OK"


def test_cooldown_suppresses_entries():
    """C10: entries suppressed while now < cooldown_until."""
    rows = tape()
    state = shock_state(rows)
    state.cooldown_until = rows[-1]["event_ts"] + 1  # cooldown still active
    s = signal(state, rows, Config())
    assert s.direction == 0 and s.confidence == 0.0
    assert s.module_state == "OK"


def test_locate_veto_blocks_short():
    """C7: SHORT direction is zeroed without an asserted locate."""
    rows = tape()
    state = shock_state(rows)
    state.locate_ok = False
    s = signal(state, rows, Config())
    assert s.direction == 0 and s.confidence == 0.0
    assert s.module_state == "OK"


def test_seq_gap_degrades():
    """Seq gap beyond tolerance -> DEGRADED (restart windows)."""
    rows = tape()
    gapped = rows[:12] + rows[13:]  # drop seq 12
    s = signal(shock_state(rows), gapped, Config())
    assert s.module_state == "DEGRADED"
    assert s.direction == 0


def test_confidence_formula():
    """Normative conviction: confidence = min(1, r2 * n/30) on a live fade."""
    rows = tape()
    cfg, state = Config(), shock_state(rows)
    snaps = rows  # all 31 snapshots >= min_snapshots
    kappa, _i, hl, r2 = fit_decay([x["t_sec"] for x in snaps],
                                  [x["impact_bps"] for x in snaps])
    expected = min(1.0, r2 * len(snaps) / 30.0)
    s = signal(state, snaps, cfg)
    assert s.direction == -1
    assert abs(s.confidence - expected) < 1e-9, (s.confidence, expected)
    assert abs(s.capital - 0.5 * expected) < 1e-9
