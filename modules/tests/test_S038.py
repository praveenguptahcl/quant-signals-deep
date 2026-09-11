"""Acceptance tests for S038 — Sub-hour microstructure reversal.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of
the chapter's normative pseudocode (§S3), and asserts causality, the cost
gate, cooldown/locate/halt guards, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S038.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S038_tape.csv"
EXPECTED = FIX / "S038_expected.csv"

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
                     "side": r["side"], "price": float(r["price"]),
                     "mid": float(r["mid"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "side": "ask",
            "price": 100.0, "mid": -1.0}  # negative midpoint


FEATURE_COLS = ["r_mid_0", "r_trade_0"]


def formation_stats(rows):
    """(trade formation ret, mid formation ret, trade reversal ret, mid reversal ret)."""
    m = [r["mid"] for r in rows]
    p = [r["price"] for r in rows]
    return (p[5] / p[0] - 1.0, m[5] / m[0] - 1.0,
            p[11] / p[5] - 1.0, m[11] / m[5] - 1.0)


def compute_features(rows):
    m0, p0 = rows[0]["mid"], rows[0]["price"]
    return [{"id": r["id"], "r_mid_0": r["mid"] / m0 - 1.0,
             "r_trade_0": r["price"] / p0 - 1.0} for r in rows]


@dataclass
class Config:
    form_bars: int = 6            # formation window (events) [example]
    mid_thresh: float = 0.0003   # 3 bps midpoint-move trigger [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 300.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: sub-hour reversal, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0    # reversal-chasing concession [example]
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _rising_events(n=6, start_ts=1757000000000000000):
    """Synthetic 6-event tape with the MIDPOINT rising ~1bp/event (fade -> SHORT)."""
    evs = []
    for i in range(n):
        mid = 100.0 * (1.0 + 0.0001 * i)
        evs.append({"id": "up%d" % i, "event_ts": start_ts + i * 10**9,
                    "side": "ask" if i % 2 else "bid",
                    "price": mid + 0.005, "mid": mid})
    return evs


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S038 reference stub).

    Generates on the MIDPOINT move, never on the bounce-contaminated trade
    move: the trigger is |mid formation return| >= mid_thresh. Guards wired
    per the normative pseudocode: cooldown (C10), locate for shorts (C7),
    halt/auction market states (§S0.5), fat-finger bounds (C4).
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["mid"] <= 0 or e["price"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    # §S0.5 market-state table
    market_state = state.get("market_state", "CONTINUOUS_TRADING")
    if market_state == "HALTED":
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    if market_state == "AUCTION":
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "DEGRADED")
    n = cfg.form_bars
    if len(evs) < n:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    win = evs[-n:]
    rm = win[-1]["mid"] / win[0]["mid"] - 1.0  # midpoint formation return
    direction = 0
    if abs(rm) >= cfg.mid_thresh:
        direction = -1 if rm > 0 else 1  # fade the midpoint move
    # C10: post-exit cooldown suppresses re-entry
    if e["event_ts"] < state.get("cooldown_until", 0):
        direction = 0
    # C7: SHORT requires locate_ok
    if direction == -1 and not state.get("locate_ok", True):
        direction = 0
    confidence = min(1.0, abs(rm) / 0.001) if direction else 0.0  # 10bps=full [example]
    capital = 0.5 * confidence  # [default]
    assert 0.0 <= confidence <= 1.0 and 0.0 <= capital <= 0.5  # C4 fat-finger
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(rm) * 1e4 * 0.5  # half the midpoint move reverts [example]
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

    rt_f, rm_f, rt_r, rm_r = formation_stats(rows)
    # Chapter S4 hand-checks: trade -0.0650% vs mid -0.0450% (formation);
    # trade +0.0330% vs mid +0.0130% (reversal) — the 2bp gap is the bounce.
    assert abs(rt_f - (-0.000650)) < 1e-6, (rt_f, rm_f)
    assert abs(rm_f - (-0.000450)) < 1e-6, (rt_f, rm_f)
    assert abs(rt_r - 0.000330) < 1e-6, (rt_r, rm_r)
    assert abs(rm_r - 0.000130) < 1e-6, (rt_r, rm_r)
    assert abs(abs(rt_f) - abs(rm_f) - 0.0002) < 1e-6  # bounce contamination = 2bps
    # at e5 the midpoint trigger is met (|mid| = 4.5bps >= 3bps) -> fade long,
    # but the reference cost gate blocks under default k = 0.5:
    # cost 1.8bps > 0.5 * edge 2.25bps (half the 4.5bps move reverts)
    s5 = signal(dict(), rows[:6], Config())
    assert s5.direction == 0 and s5.module_state == "OK", s5  # gate-blocked
    cfg_loose = Config(); cfg_loose.cost_gate_k = 2.0
    assert signal(dict(), rows[:6], cfg_loose).direction == 1  # trigger logic
    s4 = signal(dict(), rows[:5], Config())
    assert s4.direction == 0  # formation window not complete



def test_signal_emits_valid_signalvector():
    rows = tape()
    cfg, state = Config(), dict()
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 0.5  # C4: capital never exceeds the 0.5 cap
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


def test_cooldown_suppresses_reentry():
    """C10: now < cooldown_until -> direction forced to 0 even on a trigger."""
    evs = _rising_events()
    cfg = Config(); cfg.cost_gate_k = 2.0  # loose gate: trigger would fire
    # no cooldown -> SHORT fires
    assert signal(dict(), evs, cfg).direction == -1
    # cooldown in the future -> suppressed
    state = {"cooldown_until": evs[-1]["event_ts"] + 10**9}
    s = signal(state, evs, cfg)
    assert s.direction == 0 and s.capital == 0.0, s
    # cooldown in the past -> fires again
    state = {"cooldown_until": evs[-1]["event_ts"] - 1}
    assert signal(state, evs, cfg).direction == -1


def test_short_requires_locate():
    """C7: SHORT direction without locate_ok is vetoed to 0."""
    evs = _rising_events()
    cfg = Config(); cfg.cost_gate_k = 2.0  # loose gate so the SHORT would fire
    assert signal({"locate_ok": True}, evs, cfg).direction == -1
    s = signal({"locate_ok": False}, evs, cfg)
    assert s.direction == 0 and s.capital == 0.0 and s.confidence == 0.0, s


def test_halt_freezes_and_auction_degrades():
    """§S0.5 market-state table: HALTED -> UNKNOWN, AUCTION -> DEGRADED."""
    evs = _rising_events()
    cfg = Config(); cfg.cost_gate_k = 2.0
    h = signal({"market_state": "HALTED"}, evs, cfg)
    assert h.module_state == "UNKNOWN" and h.direction == 0, h
    a = signal({"market_state": "AUCTION"}, evs, cfg)
    assert a.module_state == "DEGRADED" and a.direction == 0, a


def test_maker_side_cost_gate():
    """Maker rebate lowers expected cost; the predicate still gates on edge."""
    taker = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    maker = expected_cost_bps(1.0, 0.001, "XNAS", "maker", "normal")
    assert abs(taker - 1.80) < 1e-9 and abs(maker - 1.30) < 1e-9, (taker, maker)
    assert maker < taker  # rebate reduces the hurdle
    k = 0.5  # [default]
    assert maker <= k * 100.0     # huge edge -> passes even taker
    assert not (taker <= k * 2.6)  # tiny edge -> taker still blocked (1.8 > 1.3)


def test_capital_bounded_by_fat_finger_rule():
    """C4: no emission may exceed the 0.5 capital cap, whatever the displacement."""
    evs = _rising_events(n=6)
    cfg = Config(); cfg.cost_gate_k = 2.0; cfg.mid_thresh = 0.00001  # hair trigger
    s = signal(dict(), evs, cfg)
    assert 0.0 <= s.confidence <= 1.0 and 0.0 <= s.capital <= 0.5, s
