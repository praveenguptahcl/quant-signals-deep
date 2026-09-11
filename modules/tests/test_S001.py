"""Acceptance tests for S001 — Order-flow imbalance (Cont-Kukanov-Stoikov).

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked OFI arithmetic.

Run: python -m pytest modules/tests/test_S001.py -q   (from repo root)
"""
import csv
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S001_tape.csv"
EXPECTED = FIX / "S001_expected.csv"

TOL = 1e-9  # tolerance on float comparisons


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({
            "ev": int(r["ev"]),
            "event_ts": int(r["event_ts"]),
            "asof_ts": int(r["asof_ts"]),
            "bid_px": float(r["bid_px"]), "bid_sz": int(r["bid_sz"]),
            "ask_px": float(r["ask_px"]), "ask_sz": int(r["ask_sz"]),
        })
    return rows


# ------------------------------------------------- normative pseudocode stub
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
    window_events: int = 10        # OFI accumulation window (events) [default]
    z_entry: float = 2.0           # |z| entry threshold [default]
    depth_window: int = 10         # rolling depth normalizer window [default]
    cost_gate_k: float = 0.5       # cost-gate multiplier [default]


def cks_contributions(pb, qb, pa, qa, pb_l, qb_l, pa_l, qa_l):
    """Per-event CKS contributions e^b_n, e^a_n (report convention)."""
    if pb > pb_l:
        eb = qb
    elif pb == pb_l:
        eb = qb - qb_l
    else:
        eb = -qb_l
    if pa > pa_l:
        ea = qa_l
    elif pa == pa_l:
        ea = -(qa - qa_l)
    else:
        ea = -qa
    return eb, ea


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: decomposed fee stack (impact=0 flagged [example]).

    Mirrors the S001.md COST block. Tags per the module's tag law.
    """
    spread_bps = 0.43    # half-spread of 1 tick at $231.40 reference px [example]
    take_fee_bps = 0.13  # exchange take fee $0.0030/share / $231.40 [example]
    sec31_bps = 0.00     # SEC Section 31 $0.00/million eff. 2025-05-14 [documented]
    taf_bps = 0.01       # FINRA TAF $0.000195/share eff. 2026-01-01 / $231.40 [documented]
    fee_bps = take_fee_bps + sec31_bps + taf_bps  # ~= 0.14 [example composite]
    borrow_bps = 0.0      # long-only signal; 0 with reason: no borrow [default]
    impact_bps = 0.0      # flagged [example]; calibrated per venue at scale-up
    if side == "maker":
        fee_bps = -0.20   # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def ofi_z(hist, d_bar):
    """Normative z_ofi (S001.md §S3): population-std z of the depth-normalized
    window cumulative OFI against the per-event distribution."""
    n = len(hist)
    cum = sum(hist)
    mu = sum(hist) / n / d_bar
    var = sum((h / d_bar - mu) ** 2 for h in hist) / n  # POPULATION (normative)
    sd = var ** 0.5
    return (cum / d_bar - mu) / sd if sd >= 1e-12 else 0.0


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S001 reference stub).

    Mirrors the normative pseudocode in S001.md §S3, including the F1 locked/
    crossed-quote skip, the n<5 insufficient-sample veto, the cost-gate
    predicate, and t->t+1 causality. regime_gates() is stubbed to ALLOW;
    a live harness must wire the §S2 machine records (R001/R010).
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["bid_px"] <= 0 or e["ask_px"] <= 0 or e["bid_px"] >= e["ask_px"]:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], e["asof_ts"] - e["event_ts"], "UNKNOWN")
    prev = state.get("prev")
    if prev is None:
        state["prev"] = e
        state.setdefault("ofi_hist", [])
        state.setdefault("depth_hist", [])
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "OK")
    # F1: event_ts must be strictly increasing; no reordering
    if e["event_ts"] <= prev["event_ts"]:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], e["asof_ts"] - e["event_ts"], "UNKNOWN")
    eb, ea = cks_contributions(e["bid_px"], e["bid_sz"], e["ask_px"], e["ask_sz"],
                               prev["bid_px"], prev["bid_sz"],
                               prev["ask_px"], prev["ask_sz"])
    dofi = eb + ea
    state["ofi_hist"].append(dofi)
    depth = (e["bid_sz"] + e["ask_sz"]) / 2.0
    state["depth_hist"].append(depth)
    state["prev"] = e
    hist = state["ofi_hist"][-cfg.window_events:]
    d_hist = state["depth_hist"][-cfg.depth_window:]
    d_bar = sum(d_hist) / len(d_hist)
    z = ofi_z(hist, d_bar)
    # insufficient-sample veto [default]: n < 5 -> direction 0
    if len(hist) < 5:
        direction, confidence, capital = 0, 0.0, 0.0
    else:
        direction = 1 if z >= cfg.z_entry else (-1 if z <= -cfg.z_entry else 0)
        confidence = min(1.0, abs(z) / (2.0 * cfg.z_entry)) if direction else 0.0
        capital = 0.5 * confidence
        # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
        edge_bps = abs(z) * 0.35  # modeled per-trade edge [example]
        gate = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") <= cfg.cost_gate_k * edge_bps
        if not gate:
            direction, confidence, capital = 0, 0.0, 0.0
    return SignalVector("TEST:XNAS", direction, confidence, capital,
                        e["event_ts"], e["asof_ts"] - e["event_ts"], "OK")


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """CKS hand-checks: recomputed e^b/e^a/cum OFI/mid match expected CSV."""
    evs = tape()
    exp = {int(r["ev"]): r for r in load_csv(EXPECTED)}
    prev = None
    cum = 0
    for e in evs:
        if prev is not None:
            eb, ea = cks_contributions(e["bid_px"], e["bid_sz"],
                                       e["ask_px"], e["ask_sz"],
                                       prev["bid_px"], prev["bid_sz"],
                                       prev["ask_px"], prev["ask_sz"])
            dofi = eb + ea
            cum += dofi
            want = exp[e["ev"]]
            assert eb == int(want["exp_e_b"]), e["ev"]
            assert ea == int(want["exp_e_a"]), e["ev"]
            assert dofi == int(want["exp_d_ofi"]), e["ev"]
            assert cum == int(want["exp_cum_ofi"]), e["ev"]
            mid = (e["bid_px"] + e["ask_px"]) / 2.0
            assert abs(mid - float(want["exp_mid"])) < TOL, e["ev"]
        prev = e
    assert cum == 1820  # chapter S4 hand-check: final cumulative OFI


def test_signal_emits_valid_signalvector():
    evs = tape()
    cfg, state = Config(), {}
    sigs = [signal(state, evs[: i + 1], cfg) for i in range(len(evs))]
    assert len(sigs) == len(evs)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    evs = tape()
    cfg, state = Config(), {}
    for i in range(len(evs) - 1):
        s = signal(state, evs[: i + 1], cfg)
        fill_event_ts = evs[i + 1]["event_ts"]  # earliest possible fill: next event
        assert fill_event_ts > s.computed_at, f"signal-bar fill at ev {i+1}"


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert cost > 0
    assert cost <= k * 100.0   # huge edge -> gate passes
    assert not (cost <= k * 0.01)  # tiny edge -> gate blocks


def test_invalid_input_yields_unknown():
    bad = {"bid_px": 100.0, "bid_sz": 10, "ask_px": 99.0, "ask_sz": 10,
           "event_ts": 1, "asof_ts": 2}  # crossed quote
    s = signal({}, [bad], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0


def test_z_ofi_pinned():
    """Normative z definition pinned: independent recomputation of the fixture
    tape (locked ev3 skipped, F1) must reproduce the §S3 anchor exactly.

    Guards the population-vs-sample-std convention: sample std would yield
    5.4025380815780, not the pinned 5.7302569696536.
    """
    evs = tape()
    hist, depth_hist, prev = [], [], None
    for e in evs:
        if prev is None:
            prev = e
            continue
        if e["bid_px"] <= 0 or e["ask_px"] <= 0 or e["bid_px"] >= e["ask_px"]:
            continue  # locked/crossed -> skip, never interpolate (F1)
        if e["event_ts"] <= prev["event_ts"]:
            raise AssertionError("tape out of order")
        eb, ea = cks_contributions(e["bid_px"], e["bid_sz"], e["ask_px"], e["ask_sz"],
                                   prev["bid_px"], prev["bid_sz"],
                                   prev["ask_px"], prev["ask_sz"])
        hist.append(eb + ea)
        depth_hist.append((e["bid_sz"] + e["ask_sz"]) / 2.0)
        prev = e
    cfg = Config()
    d_bar = sum(depth_hist[-cfg.depth_window:]) / cfg.depth_window
    z = ofi_z(hist[-cfg.window_events:], d_bar)
    assert abs(z - 5.7302569696536) < 1e-9  # §S3 normative anchor [measured]
    # and the live stub agrees on the same tape
    state = {}
    for i in range(len(evs)):
        s = signal(state, evs[: i + 1], cfg)
    assert s.direction == 1  # z=5.73 >= z_entry=2.0, gate passes


def test_event_ts_monotonic():
    """F1: canonical events arrive in non-decreasing event_ts order; a
    reordered event must yield UNKNOWN rather than corrupt the windows."""
    evs = tape()
    ts = [e["event_ts"] for e in evs]
    assert all(b > a for a, b in zip(ts, ts[1:]))
    cfg, state = Config(), {}
    for i in range(len(evs) - 1):
        signal(state, evs[: i + 1], cfg)
    swapped = evs[-2].copy()  # replay an older event -> out of order
    s = signal(state, evs + [swapped], cfg)
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0


def test_locked_quote_skipped_not_interpolated():
    """ev3 is a locked quote (bid == ask): F1 says skip without advancing
    prev_book and without interpolating; ev4's contribution then spans
    ev2 -> ev4 and the cumulative sum is unchanged (1,820)."""
    evs = tape()
    cfg, state = Config(), {}
    sigs = [signal(state, evs[: i + 1], cfg) for i in range(len(evs))]
    assert sigs[3].module_state == "UNKNOWN"  # ev3 locked
    assert state["prev"]["ev"] == 10  # prev advanced to ev10; locked ev3 never became prev
    assert len(state["ofi_hist"]) == 9  # 10 events, one locked skip
    assert sum(state["ofi_hist"]) == 1820


def test_insufficient_sample_veto():
    """n < 5 -> direction 0 regardless of z magnitude (normative veto)."""
    evs = tape()
    cfg, state = Config(), {}
    for i in range(5):  # ev0..ev4 -> contributions at ev1, ev2, ev4 (ev3 locked)
        s = signal(state, evs[: i + 1], cfg)
    assert len(state["ofi_hist"]) == 3
    assert s.direction == 0
    assert s.module_state == "OK"


def test_maker_rebate_branch():
    """expected_cost_bps honors the maker rebate branch."""
    taker = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    maker = expected_cost_bps(1.0, 0.001, "XNAS", "maker", "normal")
    assert abs(taker - 0.57) < 1e-9   # 0.43 + 0.13 + 0.00 + 0.01 [example composite]
    assert abs(maker - 0.23) < 1e-9   # 0.43 - 0.20 rebate [example]
    assert maker < taker
