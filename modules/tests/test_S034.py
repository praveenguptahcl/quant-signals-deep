"""Acceptance tests for S034 — Scheduled macro-announcement drift.

Template v1.0.0. Reference implementation of the chapter's normative
pseudocode (§S3): loads the fixture tape, asserts fixture arithmetic,
causality, the cost gate, the leak veto, the locate veto, cooldown, and
the confidence formula.

Run: python3 -m pytest modules/tests/test_S034.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S034_tape.csv"
EXPECTED = FIX / "S034_expected.csv"

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
                     "p_pre": float(r["p_pre"]), "p_ann": float(r["p_ann"]),
                     "p_j1": float(r["p_j1"]), "p_j2": float(r["p_j2"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "p_pre": 6000.0, "p_ann": 0.0,
            "p_j1": 6000.0, "p_j2": 6000.0}  # non-positive announce price


FEATURE_COLS = ["R_pre_bp", "R_jump_bp", "dir"]


def _bp(a, b):
    return math.log(b / a) * 1e4


def compute_features(rows, cfg=None):
    """Normative feature computation incl. the leak veto (dir pin)."""
    th = (cfg or Config()).jump_thresh_bp
    out = []
    for r in rows:
        rp = _bp(r["p_pre"], r["p_ann"])
        rj = _bp(r["p_ann"], r["p_j2"])
        d = 0
        if abs(rp) < abs(rj) and abs(rj) >= th:  # leak veto: |R_pre| >= |R_jump| -> flat
            d = 1 if rj > 0 else -1
        out.append({"id": r["id"], "R_pre_bp": rp, "R_jump_bp": rj, "dir": d})
    return out


@dataclass
class Config:
    jump_thresh_bp: float = 10.0   # diurnal-vol jump threshold [default]
    cost_gate_k: float = 0.5       # cost-gate multiplier [default]
    cooldown_s: float = 3600.0     # one signal per announcement [default]
    max_hold_min: float = 30.0     # flat by tau+30min [example]
    ref_notional: float = 100_000.0  # cost-gate reference ticket [example]
    venue: str = "XNAS"            # reference venue [example]


@dataclass
class State:
    cooldown_until: int = 0        # int64 ns; set on exit/compliance block
    adv_pct: float = 0.001         # participation estimate [example]
    module_state: str = "OK"
    locate_ok: bool = True         # C7: consumer locate assertion for shorts
    decisions: list = field(default_factory=list)


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: §S2 COST block, callable."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; per-day borrow 0 (30-min hold) [default]
    impact_bps = 1.0    # fast-window concession [example]
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    if urgency == "high":
        impact_bps *= 2.0  # [example]
    if adv_pct is not None and adv_pct > 0.01:
        impact_bps *= 1.0 + 10.0 * (adv_pct - 0.01)  # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def bar_open_after(event_ts_ns):
    """Earliest fill: open of the next 1-minute bar after the signal event."""
    return ((event_ts_ns // 60_000_000_000) + 1) * 60_000_000_000


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S034 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    now = e["event_ts"]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if min(e["p_pre"], e["p_ann"], e["p_j1"], e["p_j2"]) <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    thresh = cfg.jump_thresh_bp
    rp = math.log(e["p_ann"] / e["p_pre"]) * 1e4   # audit only; never an entry feature
    rj = math.log(e["p_j2"] / e["p_ann"]) * 1e4    # the tradeable jump

    leak = abs(rp) >= abs(rj)                       # leak veto: pre-drift priced the jump; never reverse
    in_cooldown = now < state.cooldown_until

    direction = 0
    if (not leak) and (not in_cooldown) and abs(rj) >= thresh:
        direction = 1 if rj > 0 else -1
        if direction == -1 and not state.locate_ok:  # C7: no locate -> no short
            direction = 0

    confidence = min(1.0, abs(rj) / (5.0 * thresh)) if direction != 0 else 0.0
    capital = 0.5 * confidence

    # normative cost-gate predicate (concrete args)
    edge_bps = 0.5 * abs(rj)  # [example]
    cost_bps = expected_cost_bps(notional=cfg.ref_notional, adv_pct=state.adv_pct,
                                 venue=cfg.venue, side="taker", urgency="normal")
    if not (cost_bps <= cfg.cost_gate_k * edge_bps):  # C2 bona-fide intent
        direction, confidence, capital = 0, 0.0, 0.0

    staleness = now - e["event_ts"]  # asof == event in the stub harness
    sig = SignalVector("TEST:XNAS", direction, confidence, capital,
                       e["event_ts"], staleness, state.module_state)

    # causality: earliest fill strictly after the signal event (t -> t+1)
    earliest_fill_ts = bar_open_after(e["event_ts"])
    assert earliest_fill_ts > sig.computed_at, "signal-bar fill"
    return sig


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
    e1 = by_id["e1"]
    # Chapter S4 hand-checks: R_pre = +15.8bp, R_jump = -29.8bp -> short
    assert abs(e1["R_pre_bp"] - 15.77) < 0.02, e1
    assert abs(e1["R_jump_bp"] - (-29.80)) < 0.02, e1
    assert e1["dir"] == -1
    # e2: positive jump clears the threshold -> long; e3: -5.4bp under it -> flat
    assert by_id["e2"]["dir"] == 1
    assert by_id["e3"]["dir"] == 0
    assert abs(by_id["e3"]["R_jump_bp"] - (-5.40)) < 0.02
    # e4: decisive jump, but R_pre >= thresh -> leak veto -> flat
    e4 = by_id["e4"]
    assert abs(e4["R_pre_bp"] - 25.00) < 0.02, e4
    assert e4["R_jump_bp"] > 10.0, e4
    assert e4["dir"] == 0


def test_signal_emits_valid_signalvector():
    rows = tape()
    cfg = Config()
    sigs = [signal(State(), rows[: i + 1], cfg) for i in range(len(rows))]
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
        s = signal(State(), rows[: i + 1], cfg)
        fill_event_ts = event_ts(rows[i + 1])  # earliest possible fill: next event
        assert fill_event_ts > s.computed_at, "signal-bar fill at row %d" % i
        assert bar_open_after(s.computed_at) > s.computed_at


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(notional=100_000.0, adv_pct=0.001,
                             venue="XNAS", side="taker", urgency="normal")
    assert cost > 0
    assert cost <= k * 100.0   # huge edge -> gate passes
    assert not (cost <= k * 0.01)  # tiny edge -> gate blocks
    # urgency/ADV scaling is exercised, not bypassed
    urgent = expected_cost_bps(notional=100_000.0, adv_pct=0.001,
                               venue="XNAS", side="taker", urgency="high")
    assert urgent > cost
    heavy = expected_cost_bps(notional=100_000.0, adv_pct=0.05,
                              venue="XNAS", side="taker", urgency="normal")
    assert heavy > cost
    maker = expected_cost_bps(notional=100_000.0, adv_pct=0.001,
                              venue="XNAS", side="maker", urgency="normal")
    assert maker < cost  # rebate reduces cost


def test_invalid_input_yields_unknown():
    s = signal(State(), [bad_event()], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0


def test_leak_veto_pins_flat():
    """e4: decisive +jump, but |R_pre| >= |R_jump| -> vetoed, never reversed."""
    rows = tape()
    e4 = next(r for r in rows if r["id"] == "e4")
    s = signal(State(), [e4], Config())
    assert s.direction == 0
    assert s.confidence == 0.0 and s.capital == 0.0
    assert s.module_state == "OK"  # veto is a rule outcome, not an error


def test_locate_veto_on_short():
    """C7: short candidate without locate_ok -> 0; with locate_ok -> -1."""
    rows = tape()
    e1 = next(r for r in rows if r["id"] == "e1")  # short candidate
    cfg = Config()
    s_no_locate = signal(State(locate_ok=False), [e1], cfg)
    assert s_no_locate.direction == 0
    s_locate = signal(State(locate_ok=True), [e1], cfg)
    assert s_locate.direction == -1


def test_cooldown_and_confidence():
    """Cooldown suppresses re-entry; confidence pins min(1, |R_jump|/(5*thresh))."""
    rows = tape()
    cfg = Config()
    e1 = next(r for r in rows if r["id"] == "e1")
    s = signal(State(), [e1], cfg)
    assert s.direction == -1
    rj = abs(math.log(e1["p_j2"] / e1["p_ann"]) * 1e4)
    assert abs(s.confidence - min(1.0, rj / (5.0 * cfg.jump_thresh_bp))) < 1e-12
    assert abs(s.capital - 0.5 * s.confidence) < 1e-12
    # cooldown: same event re-evaluated inside the block window -> flat
    blocked = signal(State(cooldown_until=e1["event_ts"] + 1), [e1], cfg)
    assert blocked.direction == 0
