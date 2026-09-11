"""Acceptance tests for S041 — Bollinger-band reversal (v1.1.0).

Template v1.0.0. Loads the fixture tape, runs a reference implementation of
the chapter's normative pseudocode (§S3 of modules/signals/S041.md), and pins
behavior: tag-then-re-entry confirmation, the executable cost-gate predicate,
causality (no signal-bar fills), cooldown/locate/staleness gates, fixture TYPE
headers, and deterministic replay.

Run: python3 -m pytest modules/tests/test_S041.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S041_tape.csv"
EXPECTED = FIX / "S041_expected.csv"

TOL = 1e-9  # [default] tolerance on float comparisons
STALENESS_TTL_NS = 300_000_000_000  # 300 s [default] — §S0.4 / §S3


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
                     "asof_ts": int(r["event_ts"]),  # bars are point-in-time at bar close
                     "close": float(r["close"]), "bb_mid": float(r["bb_mid"]),
                     "bb_up": float(r["bb_up"]), "bb_lo": float(r["bb_lo"]),
                     "symbol": "TEST:XNAS"})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "asof_ts": 1, "close": 100.0,
            "bb_mid": 100.0, "bb_up": 99.0, "bb_lo": 101.0,  # crossed bands
            "symbol": "TEST:XNAS"}


def zero_close_event():
    return {"id": "zero", "event_ts": 1, "asof_ts": 1, "close": 0.0,
            "bb_mid": 100.0, "bb_up": 101.0, "bb_lo": 99.0,
            "symbol": "TEST:XNAS"}


FEATURE_COLS = ["tag_lo", "tag_hi", "re_lo", "re_hi", "dir"]


def compute_features(rows):
    """Tag/re-entry arithmetic — the arithmetic the fixture expected file pins."""
    out = []
    prev_tag_lo = prev_tag_hi = 0
    for r in rows:
        tag_lo = 1 if r["close"] < r["bb_lo"] else 0
        tag_hi = 1 if r["close"] > r["bb_up"] else 0
        # tag-then-re-entry confirmation: the tag bar itself never signals
        re_lo = 1 if (prev_tag_lo and r["close"] >= r["bb_lo"]) else 0
        re_hi = 1 if (prev_tag_hi and r["close"] <= r["bb_up"]) else 0
        d = 1 if re_lo else (-1 if re_hi else 0)
        out.append({"id": r["id"], "tag_lo": tag_lo, "tag_hi": tag_hi,
                    "re_lo": re_lo, "re_hi": re_hi, "dir": d})
        prev_tag_lo, prev_tag_hi = tag_lo, tag_hi
    return out


@dataclass
class Config:
    n: int = 20                    # Bollinger lookback [example]
    mult: float = 2.0              # band multiplier [example]
    conviction_scale: float = 50.0  # re-entry depth scale, bps [example]
    cost_gate_k: float = 0.5       # cost-gate multiplier [default]
    cooldown_s: float = 600.0      # post-exit cooldown [default]


@dataclass
class ModuleState:
    module_state: str = "OK"
    cooldown_until: int = 0        # int64 ns; no cooldown by default
    locate_ok: bool = True         # long-biased reference; C7 gates SHORTs


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model (§S2 COST block): band-reversal, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # bps/day; [default] long-biased reference — shorts accrue in the strategy ledger
    impact_bps = 1.00   # [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _valid(e):
    """F1/F2 predicate from §S3 normative pseudocode."""
    return (math.isfinite(e["close"]) and e["close"] > 0
            and math.isfinite(e["bb_mid"]) and math.isfinite(e["bb_up"])
            and math.isfinite(e["bb_lo"])
            and e["bb_up"] > e["bb_mid"] > e["bb_lo"])


def _conviction(e, direction, conviction_scale):
    """Re-entry depth relative to band width, bps; [example] mapping from §S3."""
    if direction == +1:
        depth_bps = (e["close"] - e["bb_lo"]) / e["close"] * 1e4
    elif direction == -1:
        depth_bps = (e["bb_up"] - e["close"]) / e["close"] * 1e4
    else:
        return 0.0
    return min(1.0, max(0.0, depth_bps) / conviction_scale)


def signal(state: ModuleState, events, cfg: Config) -> SignalVector:
    """signal(state, events, cfg) -> SignalVector (S041 reference implementation).

    Mirrors the §S3 normative pseudocode: confirmation-required entries, the
    executable cost-gate predicate, cooldown (C10) and locate (C7) gates,
    staleness TTL, fat-finger bounds (C4), and the t->t+1 causality assertion.
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")  # F1
    e = evs[-1]
    if not _valid(e):
        return SignalVector(e.get("symbol", "?"), 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")          # F1/F2: never interpolate
    now = e["event_ts"]                                          # causality: event time only
    staleness = now - e.get("asof_ts", now)
    if staleness > STALENESS_TTL_NS:
        return SignalVector(e["symbol"], 0, 0.0, 0.0,
                            e["event_ts"], staleness, "UNKNOWN")
    p = evs[-2] if len(evs) >= 2 else None
    re_lo = 1 if (p is not None and p["close"] < p["bb_lo"]
                  and e["close"] >= e["bb_lo"]) else 0
    re_hi = 1 if (p is not None and p["close"] > p["bb_up"]
                  and e["close"] <= e["bb_up"]) else 0
    direction = 1 if re_lo else (-1 if re_hi else 0)  # tag bar: 0, always
    confidence = _conviction(e, direction, cfg.conviction_scale)
    capital = 0.5 * confidence                       # 0.5 [default]
    edge_bps = abs(e["close"] - e["bb_mid"]) / e["close"] * 1e4  # midline distance [example]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    cost_ok = cost <= cfg.cost_gate_k * edge_bps     # normative cost-gate predicate (C2)
    if not cost_ok:
        direction, confidence, capital = 0, 0.0, 0.0
    if now < state.cooldown_until:
        direction, confidence, capital = 0, 0.0, 0.0  # C10 post-exit cooldown
    if direction == -1 and not state.locate_ok:
        direction, confidence, capital = 0, 0.0, 0.0  # C7: no SHORT without locate
    assert 0.0 <= confidence <= 1.0 and 0.0 <= capital <= 0.5  # C4 bounds
    return SignalVector(e["symbol"], direction, confidence, capital,
                        e["event_ts"], staleness, state.module_state)


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
    # Lower event: bar 32 tags (97.652 < 97.999), bar 33 re-enters -> long.
    # The tag bar itself never signals (confirmation required).
    assert by_id["L32"]["tag_lo"] == 1 and by_id["L32"]["dir"] == 0
    assert by_id["L33"]["re_lo"] == 1 and by_id["L33"]["dir"] == 1
    # Upper event: bar 54 tags (102.132 > 101.947), bar 55 re-enters -> short.
    assert by_id["U54"]["tag_hi"] == 1 and by_id["U54"]["dir"] == 0
    assert by_id["U55"]["re_hi"] == 1 and by_id["U55"]["dir"] == -1
    # all other bars: no tag, no re-entry, no signal
    quiet = [b for b in by_id if b not in ("L32", "L33", "U54", "U55")]
    assert all(by_id[b]["dir"] == 0 for b in quiet), quiet
    assert all(by_id[b]["tag_lo"] == 0 and by_id[b]["tag_hi"] == 0 for b in quiet)


def test_signal_emits_valid_signalvector():
    rows = tape()
    cfg, state = Config(), ModuleState()
    sigs = [signal(state, rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 0.5
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = tape()
    cfg, state = Config(), ModuleState()
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
    for ev in (bad_event(), zero_close_event()):
        s = signal(ModuleState(), [ev], Config())
        assert s.module_state == "UNKNOWN", ev["id"]
        assert s.direction == 0 and s.capital == 0.0


def test_chapter_event_bars_signal_with_cost_gate():
    """§S3 chapter events: L33 -> +1, U55 -> -1 with the cost gate active (k=0.5)."""
    rows = tape()
    by_id = {r["id"]: r for r in rows}
    cfg, state = Config(), ModuleState()
    ids = [r["id"] for r in rows]
    s33 = signal(state, rows[: ids.index("L33") + 1], cfg)
    s55 = signal(state, rows[: ids.index("U55") + 1], cfg)
    assert s33.direction == +1, s33
    assert s55.direction == -1, s55
    assert s33.confidence > 0 and s55.confidence > 0
    # tag bars themselves must stay flat even with the cost gate on
    s32 = signal(state, rows[: ids.index("L32") + 1], cfg)
    s54 = signal(state, rows[: ids.index("U54") + 1], cfg)
    assert s32.direction == 0 and s54.direction == 0


def test_consecutive_tags_then_reentry():
    """Tag persisting two bars: still no signal until the re-entry bar."""
    base = {"asof_ts": 0, "bb_mid": 100.0, "bb_up": 101.0, "bb_lo": 99.0,
            "symbol": "TEST:XNAS"}
    mk = lambda i, c: dict(base, id="t%d" % i, event_ts=i, close=c)
    rows = [mk(1, 100.0), mk(2, 98.5), mk(3, 98.7), mk(4, 99.5)]
    cfg, state = Config(), ModuleState()
    dirs = [signal(state, rows[: i + 1], cfg).direction for i in range(4)]
    assert dirs == [0, 0, 0, 1], dirs


def test_cooldown_suppresses_entries():
    """C10: entries suppressed while now < cooldown_until; state stays OK."""
    rows = tape()
    ids = [r["id"] for r in rows]
    cfg = Config()
    state = ModuleState()
    prefix = rows[: ids.index("L33") + 1]
    state.cooldown_until = event_ts(prefix[-1]) + 1  # cooldown still active
    s = signal(state, prefix, cfg)
    assert s.direction == 0 and s.confidence == 0.0
    assert s.module_state == "OK"
    state.cooldown_until = 0  # cooldown expired -> the same event signals
    s = signal(state, prefix, cfg)
    assert s.direction == +1


def test_missing_locate_zeroes_shorts():
    """C7: SHORT direction requires locate_ok; LONG is unaffected."""
    rows = tape()
    ids = [r["id"] for r in rows]
    cfg = Config()
    state = ModuleState(locate_ok=False)
    s55 = signal(state, rows[: ids.index("U55") + 1], cfg)
    assert s55.direction == 0 and s55.module_state == "OK"
    s33 = signal(state, rows[: ids.index("L33") + 1], cfg)
    assert s33.direction == +1


def test_stale_input_yields_unknown():
    """Staleness TTL (300 s [default]): stale input -> UNKNOWN, never interpolate."""
    rows = tape()
    stale = dict(rows[-1])
    stale["asof_ts"] = stale["event_ts"] - (STALENESS_TTL_NS + 1)
    s = signal(ModuleState(), [stale], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.confidence == 0.0
    # at exactly the TTL the input is still usable
    fresh = dict(rows[-1])
    fresh["asof_ts"] = fresh["event_ts"] - STALENESS_TTL_NS
    s = signal(ModuleState(), [fresh], Config())
    assert s.module_state == "OK"


def test_fixture_type_headers():
    """Both fixture files carry the mandatory '# TYPE: validation-run' header."""
    for path in (TAPE, EXPECTED):
        head = [ln for ln in path.read_text().splitlines() if ln.startswith("#")]
        assert any("TYPE: validation-run" in ln for ln in head), path


def test_deterministic_replay():
    """Seed-41 fixture replays deterministically: two passes, identical vectors."""
    rows = tape()
    cfg = Config()
    first = [signal(ModuleState(), rows[: i + 1], cfg) for i in range(len(rows))]
    second = [signal(ModuleState(), rows[: i + 1], cfg) for i in range(len(rows))]
    assert first == second
