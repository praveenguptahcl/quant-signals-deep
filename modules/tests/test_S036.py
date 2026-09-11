"""Acceptance tests for S036 — Overnight-gap fade (module v1.1.0).

Reference stub implementing the §S3 normative pseudocode. Pins: fixture
arithmetic (incl. the cost_ok column), gate-boundary semantics, the above-max
veto, locate/cooldown guards, halt/auction market states, the cost-gate
predicate, t→t+1 causality (no signal-bar fills), and F1/F2 invalid-input
handling (UNKNOWN, never interpolate).

locate_ok / news_flag are consumer-supplied context (locate service, news
calendar); the production wrapper injects them before calling signal.
market_state rides on each event per §S0.5.

Run: python3 -m pytest modules/tests/test_S036.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S036_tape.csv"
EXPECTED = FIX / "S036_expected.csv"

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
                     "session": r["session"],
                     "prior_close": float(r["prior_close"]) if r["prior_close"] else float("nan"),
                     "open": float(r["open"]) if r["open"] else float("nan"),
                     "close": float(r["close"]),
                     "market_state": "CONTINUOUS_TRADING"})
    return rows


@dataclass
class Config:
    gap_min: float = 0.005        # minimum tradeable gap [example]
    gap_max: float = 0.05         # maximum tradeable gap [example]
    max_hold_bars: int = 10       # fade horizon [example]
    cost_gate_k: float = 0.5      # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: open fade, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0    # open-auction concession [example]
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _in_gate(gap, cfg):
    """Normative gate predicate (§S3): two-sided, inclusive bounds."""
    return cfg.gap_min <= abs(gap) <= cfg.gap_max


def _unknown(ts):
    return SignalVector("TEST:XNAS", 0, 0.0, 0.0, ts, 0, "UNKNOWN")


def signal(state, events, cfg, locate_ok=True, news_flag=False):
    """signal(state, events, cfg, locate_ok, news_flag) -> SignalVector.

    Reference stub for the §S3 normative pseudocode.
    """
    evs = list(events)
    if not evs:
        return _unknown(0)
    e = evs[-1]
    ms = e.get("market_state", "CONTINUOUS_TRADING")
    if ms == "HALTED":
        return _unknown(e["event_ts"])          # §S0.5: freeze, UNKNOWN
    if ms == "AUCTION":
        last = state.get("last_vector")          # §S0.5: hold last, DEGRADED
        if last is not None:
            return SignalVector(last.symbol, last.direction, last.confidence,
                                last.capital, last.computed_at, last.staleness,
                                "DEGRADED")
        return _unknown(e["event_ts"])
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if not (e["close"] == e["close"]) or e["close"] <= 0:
        return _unknown(e["event_ts"])
    sess = [x for x in evs if x["session"] == e["session"]]
    pc, op = sess[0]["prior_close"], sess[0]["open"]
    if not (pc == pc and op == op) or pc <= 0 or op <= 0:
        return _unknown(e["event_ts"])
    gap = op / pc - 1.0
    in_gate = _in_gate(gap, cfg)
    raw_dir = (-1 if gap > 0 else (1 if gap < 0 else 0)) if in_gate else 0
    if news_flag:
        raw_dir = 0                              # failure mode 1 veto
    cooldown_ok = e["event_ts"] >= state.get("cooldown_until", 0)  # C10
    edge_bps = abs(gap) * 1e4 * 0.3              # 30% of the gap fills [example]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    cost_ok = cost <= cfg.cost_gate_k * edge_bps  # normative cost-gate predicate
    direction = raw_dir
    if not cooldown_ok:
        direction = 0                            # C10 post-exit cooldown
    if raw_dir < 0 and not locate_ok:
        direction = 0                            # C7 locate veto (Reg-SHO)
    if not cost_ok:
        direction = 0                            # C2 bona-fide intent
    confidence = min(1.0, abs(gap) / 0.03) if direction != 0 else 0.0  # [example]
    capital = 0.5 * confidence                   # [default]
    sig = SignalVector("TEST:XNAS", direction, confidence, capital,
                       e["event_ts"], 0, "OK")
    state["last_vector"] = sig
    return sig


FEATURE_COLS = ["gap", "in_gate", "dir", "fade_ret", "cost_ok"]


def compute_features(rows):
    """Reference feature computation matching §S4 expected outputs."""
    cfg = Config()
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    sessions, order = {}, []
    for i, r in enumerate(rows):
        if r["session"] not in sessions:
            sessions[r["session"]] = []
            order.append(r["session"])
        sessions[r["session"]].append(i)
    out = [None] * len(rows)
    for s in order:
        idx = sessions[s]
        pc, op = rows[idx[0]]["prior_close"], rows[idx[0]]["open"]
        gap = op / pc - 1.0
        in_gate = 1 if _in_gate(gap, cfg) else 0
        d = (-1 if gap > 0 else (1 if gap < 0 else 0)) * in_gate
        edge_bps = abs(gap) * 1e4 * 0.3
        cost_ok = 1 if cost <= cfg.cost_gate_k * edge_bps else 0
        for i in idx:
            out[i] = {"id": rows[i]["id"], "gap": gap, "in_gate": in_gate,
                      "dir": d, "fade_ret": rows[i]["close"] / op - 1.0,
                      "cost_ok": cost_ok}
    return out


def _session_events(prior_close, open_px, closes, start_ts=1757100000000000000,
                    session="t", market_state="CONTINUOUS_TRADING"):
    evs = []
    for i, c in enumerate(closes):
        evs.append({"id": "t%d" % i, "event_ts": start_ts + i * 60_000_000_000,
                    "session": session,
                    "prior_close": prior_close if i == 0 else float("nan"),
                    "open": open_px if i == 0 else float("nan"),
                    "close": c, "market_state": market_state})
    return evs


# ------------------------------------------------------------------- tests
def test_T1_fixture_recomputes_to_expected():
    rows = tape()
    feats = compute_features(rows)
    exp = load_csv(EXPECTED)
    assert len(feats) == len(exp) == 16, (len(feats), len(exp))
    for f, w in zip(feats, exp):
        assert str(f["id"]) == str(w["id"]), (f["id"], w["id"])
        for col in FEATURE_COLS:
            assert _close(f[col], w[col]), (f["id"], col)

    by_id = {f["id"]: f for f in feats}
    # Chapter S4 hand-checks: gap = +2.00% -> fade short
    s1 = by_id["s1b1"]
    assert abs(s1["gap"] - 0.02) < 1e-12, s1
    assert s1["in_gate"] == 1 and s1["dir"] == -1 and s1["cost_ok"] == 1
    assert abs(s1["fade_ret"] - (101.50 / 102.00 - 1.0)) < 1e-12, s1
    assert abs(s1["fade_ret"] - (-0.004902)) < 1e-5
    # s2: +0.20% gap is below the 0.50% minimum gate -> flat, but the cost
    # gate alone would pass (cost_ok=1): the gap gate is what vetoes noise.
    assert by_id["s2b1"]["in_gate"] == 0 and by_id["s2b1"]["dir"] == 0
    assert by_id["s2b1"]["cost_ok"] == 1
    # s3: +8.00% gap is above the 5% maximum gate -> flat (news-gap veto),
    # even though the cost gate passes on the large edge.
    assert by_id["s3b1"]["in_gate"] == 0 and by_id["s3b1"]["dir"] == 0
    assert by_id["s3b1"]["cost_ok"] == 1
    # every bar of a session shares the session gap and direction
    assert all(by_id["s1b%d" % i]["dir"] == -1 for i in range(1, 11))
    assert all(by_id["s3b%d" % i]["dir"] == 0 for i in range(1, 4))


def test_T2_gate_boundary_semantics():
    cfg = Config()
    assert _in_gate(0.005, cfg) is True    # exactly at gap_min
    assert _in_gate(-0.005, cfg) is True
    assert _in_gate(0.05, cfg) is True     # exactly at gap_max
    assert _in_gate(0.005 - 1e-9, cfg) is False
    assert _in_gate(0.05 + 1e-9, cfg) is False
    assert _in_gate(0.0, cfg) is False
    assert _in_gate(0.02, cfg) is True


def test_T3_above_max_gap_vetoed():
    rows = tape()
    cfg, state = Config(), dict()
    s3 = [r for r in rows if r["session"] == "s3"]
    sigs = [signal(state, s3[: i + 1], cfg) for i in range(len(s3))]
    assert all(s.direction == 0 for s in sigs)
    assert all(s.confidence == 0.0 and s.capital == 0.0 for s in sigs)
    assert all(s.module_state == "OK" for s in sigs)  # veto, not error


def test_T4_signal_emits_valid_signalvector():
    rows = tape()
    cfg, state = Config(), dict()
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    # s1 emits a fade-short on the first bar, s2/s3 emit flat
    assert sigs[0].direction == -1
    assert sigs[10].direction == 0
    assert sigs[13].direction == 0


def test_T5_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = tape()
    cfg, state = Config(), dict()
    for i in range(len(rows) - 1):
        s = signal(state, rows[: i + 1], cfg)
        fill_event_ts = rows[i + 1]["event_ts"]  # earliest possible fill: next event
        assert fill_event_ts > s.computed_at, "signal-bar fill at row %d" % i


def test_T6_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert cost > 0
    assert cost <= k * 100.0      # huge edge -> gate passes
    assert not (cost <= k * 0.01)  # tiny edge -> gate blocks
    # fixture column cross-check: every bar's cost_ok matches the predicate
    feats = compute_features(tape())
    for f in feats:
        edge_bps = abs(f["gap"]) * 1e4 * 0.3
        assert f["cost_ok"] == (1 if cost <= k * edge_bps else 0), f["id"]


def test_T7_invalid_input_yields_unknown():
    bad = {"id": "bad", "event_ts": 1, "session": "bad",
           "prior_close": 100.0, "open": -1.0, "close": 100.0}  # negative open
    s = signal(dict(), [bad], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0
    # empty events -> UNKNOWN
    s = signal(dict(), [], Config())
    assert s.module_state == "UNKNOWN"
    # NaN anchor (no clean open) -> UNKNOWN, never interpolated
    evs = _session_events(float("nan"), float("nan"), [100.0])
    s = signal(dict(), evs, Config())
    assert s.module_state == "UNKNOWN"


def test_T8_locate_veto():
    """SHORT without a Reg-SHO locate is zeroed (C7); LONG is unaffected."""
    cfg = Config()
    evs = _session_events(100.0, 102.0, [101.5])  # +2% gap -> fade short
    s = signal(dict(), evs, cfg, locate_ok=False)
    assert s.direction == 0 and s.module_state == "OK"
    assert s.confidence == 0.0 and s.capital == 0.0
    s = signal(dict(), evs, cfg, locate_ok=True)
    assert s.direction == -1 and s.module_state == "OK"
    # news flag vetoes the fade in both directions (failure mode 1)
    evs_long = _session_events(100.0, 98.0, [98.5])  # -2% gap -> fade long
    s = signal(dict(), evs_long, cfg, news_flag=True)
    assert s.direction == 0
    s = signal(dict(), evs_long, cfg, news_flag=False)
    assert s.direction == +1


def test_T9_cooldown_suppression():
    """Post-exit cooldown suppresses re-entry (C10)."""
    cfg = Config()
    evs = _session_events(100.0, 102.0, [101.5, 101.0])
    state = {"cooldown_until": evs[0]["event_ts"] + 10 ** 12}  # ~16 min out
    s = signal(state, evs[:1], cfg)
    assert s.direction == 0 and s.module_state == "OK"
    # cooldown cleared -> signal returns
    s = signal(dict(), evs[:1], cfg)
    assert s.direction == -1


def test_T10_halt_auction_states():
    """§S0.5 market-state table: HALTED -> UNKNOWN; AUCTION -> DEGRADED hold."""
    cfg = Config()
    evs = _session_events(100.0, 102.0, [101.5, 101.0])
    state = dict()
    s0 = signal(state, evs[:1], cfg)
    assert s0.direction == -1 and s0.module_state == "OK"
    # halted event -> UNKNOWN, state frozen
    halted = _session_events(100.0, 102.0, [101.5, 101.2],
                            market_state="HALTED")
    sh = signal(state, halted[:2], cfg)
    assert sh.module_state == "UNKNOWN" and sh.direction == 0
    # auction event -> DEGRADED, holds the last vector
    auction = _session_events(100.0, 102.0, [101.5, 101.2],
                             market_state="AUCTION")
    sa = signal(state, auction[:2], cfg)
    assert sa.module_state == "DEGRADED"
    assert sa.direction == s0.direction and sa.confidence == s0.confidence
