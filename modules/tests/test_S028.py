"""Acceptance tests for S028 — Donchian breakout.

Template v1.0.0. Concrete: loads the fixture tape, runs a reference
implementation of the chapter's normative pseudocode (entry rule, spread/locate
gates, conviction, cost-gate predicate, exit/cooldown state machine), and pins
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S028.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S028_tape.csv"
EXPECTED = FIX / "S028_expected.csv"

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
        rows.append({"ev": int(r["ev"]), "event_ts": int(r["event_ts"]),
                     "open": float(r["open"]), "high": float(r["high"]),
                     "low": float(r["low"]), "close": float(r["close"]),
                     "volume": int(r["volume"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"ev": -1, "event_ts": 1, "open": 100.0, "high": 99.0,
            "low": 100.0, "close": 100.0, "volume": 10}  # high < low


FEATURE_COLS = ["donch_up", "donch_lo", "mid", "brk"]


def _nz(x):
    return float(x) if x != "" else float("nan")


def compute_features(rows):
    N = Config().lookback
    out = []
    for t, r in enumerate(rows):
        if t < N:
            out.append({"id": r["ev"], "donch_up": float("nan"),
                        "donch_lo": float("nan"), "mid": float("nan"), "brk": 0})
            continue
        win = rows[t - N:t]  # completed-bar convention: bar t excluded
        up = max(x["high"] for x in win)
        lo = min(x["low"] for x in win)
        mid = (up + lo) / 2.0
        brk = 1 if r["close"] > up else (-1 if r["close"] < lo else 0)
        out.append({"id": r["ev"], "donch_up": up, "donch_lo": lo,
                    "mid": mid, "brk": brk})
    return out


@dataclass
class Config:
    lookback: int = 5            # N bars (fixture override; module default 20) [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown [default]
    max_spread_ticks: int = 3    # spread filter [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: intraday 5-min breakout, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0     # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0     # breakout chasing concession [example]
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S028 reference stub).

    Implements the §S3 normative pseudocode: F1/F2 validation, completed-bar
    channel, exit/cooldown state machine, spread + locate gates, conviction,
    and the executable cost-gate predicate. `state` is a plain dict carrying
    module-owned state (position, cooldown_until, locate_ok, module_state).
    """
    def flat(module_state, ts):
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, ts, 0, module_state)

    evs = list(events)
    if not evs:
        return flat("UNKNOWN", 0)
    e = evs[-1]
    ts = e["event_ts"]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    req = ("event_ts", "open", "high", "low", "close", "volume")
    if any(k not in e or e[k] is None for k in req) or \
            e["high"] < e["low"] or e["close"] <= 0 or e["high"] <= 0:
        return flat("UNKNOWN", ts)
    # warmup: need N completed bars before the triggering bar
    if len(evs) <= cfg.lookback:
        return flat("OK", ts)
    win = evs[-cfg.lookback - 1:-1]  # completed-bar convention: bar t excluded
    up = max(x["high"] for x in win)
    lo = min(x["low"] for x in win)
    mid = (up + lo) / 2.0
    mstate = state.get("module_state", "OK")
    # exit handling on an open signal position (C10)
    pos = state.get("position")
    if pos is not None and pos["direction"] != 0:
        bars_held = len(evs) - pos["entry_len"]
        if pos["direction"] == 1:
            exit_hit = e["close"] <= mid or e["close"] < lo
        else:
            exit_hit = e["close"] >= mid or e["close"] > up
        exit_hit = exit_hit or bars_held >= 10 or mstate != "OK"
        if exit_hit:
            state["position"] = None
            state["cooldown_until"] = ts + int(cfg.cooldown_s * 1e9)
            return flat(mstate, ts)
    # C10 post-exit cooldown: no re-entry
    if ts < state.get("cooldown_until", 0):
        return flat(mstate, ts)
    # entry rule: close-through breakout
    brk = 1 if e["close"] > up else (-1 if e["close"] < lo else 0)
    spread_ok = e.get("spread_ticks") is None or \
        e["spread_ticks"] <= cfg.max_spread_ticks  # absent -> pass [default]
    direction = brk if spread_ok else 0
    # C7 locate gate: no SHORT without asserted locate
    if direction == -1 and not state.get("locate_ok", False):
        direction = 0
    # conviction [default] functional form; calibrate OOS per §S2 recipes
    if direction != 0:
        rail = up if direction == 1 else lo
        break_bps = abs(e["close"] - rail) / e["close"] * 1e4
        vol_ratio = e["volume"] / max(sum(x["volume"] for x in win) / len(win), 1.0)
        conviction = min(0.95, 0.40 + break_bps / 10.0 + 0.20 * min(vol_ratio, 2.0))
    else:
        conviction = 0.0
    confidence = conviction
    capital = 0.5 * confidence
    # normative cost-gate predicate (C2), concrete arguments
    edge_bps = abs(e["close"] - mid) / e["close"] * 1e4  # rail distance [example]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    if not (cost <= cfg.cost_gate_k * edge_bps):
        direction, confidence, capital = 0, 0.0, 0.0
    # book-keep entry for exit/cooldown tracking
    if direction != 0:
        state["position"] = {"direction": direction, "entry_len": len(evs)}
    sig = SignalVector("TEST:XNAS", direction, confidence, capital, ts, 0, mstate)
    # t->t+1 causality assertion: earliest fill is a later event, never this bar
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
    # Hand-check bar 8 (N=5, completed-bar: window = bars 3..7):
    # up = max(101.00,101.10,101.20,101.00,100.90) = 101.20
    # lo = min(100.00,100.10,100.20,100.30,100.00) = 100.00 ; mid = 100.60
    assert abs(by_id[8]["donch_up"] - 101.20) < TOL, by_id[8]
    assert abs(by_id[8]["donch_lo"] - 100.00) < TOL, by_id[8]
    assert abs(by_id[8]["mid"] - 100.60) < TOL, by_id[8]
    assert by_id[8]["brk"] == 1  # close 102.00 > 101.20 -> bullish close-breakout
    assert by_id[7]["brk"] == 0  # bar 7 inside the channel



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


def _bar(ev, ts, o, h, l, c, v, **kw):
    row = {"ev": ev, "event_ts": ts, "open": o, "high": h,
           "low": l, "close": c, "volume": v}
    row.update(kw)
    return row


def test_completed_bar_exclusion_pins_no_lookahead():
    """Pinning the §S3 completed-bar convention: the triggering bar's own
    extremes must not move the rail. Perturbing bar 8's high to 200.0 must
    leave donch_up == 101.20 (window = bars 3..7 only)."""
    rows = tape()
    tampered = [dict(r) for r in rows]
    tampered[-1]["high"] = 200.0  # extreme print inside the triggering bar
    feats = compute_features(tampered)
    by_id = {f["id"]: f for f in feats}
    assert abs(by_id[8]["donch_up"] - 101.20) < TOL, by_id[8]
    assert by_id[8]["brk"] == 1
    # the stub agrees: rail unaffected by the triggering bar's own high
    s_clean = signal(dict(), rows, Config())
    s_tamp = signal(dict(), tampered, Config())
    assert s_clean.direction == s_tamp.direction == 1


def test_warmup_rows_emit_flat_ok():
    """Fewer than N completed bars -> flat direction, OK state, no crash."""
    rows = tape()
    cfg = Config()
    for i in range(cfg.lookback):
        s = signal(dict(), rows[: i + 1], cfg)
        assert s.direction == 0, i
        assert s.confidence == 0.0 and s.capital == 0.0, i
        assert s.module_state == "OK", i


def test_short_break_requires_locate():
    """C7: a short breakout emits -1 only with locate_ok; otherwise flat."""
    rows = tape()
    base_ts = rows[-1]["event_ts"]
    # synthetic bar 9: close 99.00 < lo 100.00 (window bars 4..8, N=5) -> brk=-1
    bar9 = _bar(9, base_ts + 300_000_000_000, 100.2, 100.3, 98.8, 99.0, 900)
    evs = rows + [bar9]
    s_no_locate = signal(dict(), evs, Config())
    assert s_no_locate.direction == 0  # locate veto -> flat
    st = {"locate_ok": True}
    s_locate = signal(st, evs, Config())
    assert s_locate.direction == -1
    assert 0.0 < s_locate.confidence <= 1.0
    assert st["position"]["direction"] == -1  # entry booked for exit tracking


def test_spread_veto_blocks_entry():
    """Spread gate: spread_ticks above max_spread_ticks vetoes the entry;
    absent spread_ticks passes (default)."""
    rows = tape()
    bar_wide = dict(rows[-1]); bar_wide["spread_ticks"] = 10
    evs_wide = rows[:-1] + [bar_wide]
    s_wide = signal(dict(), evs_wide, Config())
    assert s_wide.direction == 0  # vetoed despite the breakout
    bar_ok = dict(rows[-1]); bar_ok["spread_ticks"] = 2
    s_ok = signal(dict(), rows[:-1] + [bar_ok], Config())
    assert s_ok.direction == 1  # within spread budget -> breakout emits


def test_cooldown_suppresses_reentry():
    """C10: after an exit, entries are suppressed until cooldown_s elapses."""
    rows = tape()
    cfg = Config()  # cooldown_s = 600.0 [default]
    state = {}
    s_entry = signal(state, rows, cfg)
    assert s_entry.direction == 1
    base_ts = rows[-1]["event_ts"]
    # bar 9 (+300s): close back at the midline -> exit, cooldown starts
    bar9 = _bar(9, base_ts + 300_000_000_000, 101.0, 101.1, 100.0, 100.6, 800)
    s_exit = signal(state, rows + [bar9], cfg)
    assert s_exit.direction == 0
    assert state["cooldown_until"] == bar9["event_ts"] + int(600.0 * 1e9)
    # bar 10 (+600s): fresh breakout shape but inside cooldown -> suppressed
    bar10 = _bar(10, bar9["event_ts"] + 300_000_000_000,
                 100.6, 103.0, 100.5, 102.8, 2600)  # close 102.8 > rail 102.5
    s_supp = signal(state, rows + [bar9, bar10], cfg)
    assert s_supp.direction == 0, "re-entry inside cooldown must be suppressed"
    # bar 11 (+1300s after exit): cooldown elapsed -> breakout emits again
    bar11 = _bar(11, bar9["event_ts"] + 1_000_000_000_000,
                 100.6, 103.0, 100.5, 102.8, 2600)
    s_re = signal(state, rows + [bar9, bar11], cfg)
    assert s_re.direction == 1, "breakout after cooldown must not be suppressed"


def test_maker_side_rebate_below_taker():
    """Side field pinned: maker cost (rebate) is strictly below taker cost."""
    args = dict(notional=1.0, adv_pct=0.001, venue="XNAS", urgency="normal")
    taker = expected_cost_bps(side="taker", **args)
    maker = expected_cost_bps(side="maker", **args)
    assert abs(taker - 1.80) < 1e-9, taker   # 0.50 + 0.30 + 0.0 + 1.0 [example]
    assert abs(maker - 1.30) < 1e-9, maker   # 0.50 + (-0.20) + 0.0 + 1.0 [example]
    assert maker < taker
