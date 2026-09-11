"""Acceptance tests for S041 — Bollinger-band reversal.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S041.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S041_tape.csv"
EXPECTED = FIX / "S041_expected.csv"

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
                     "close": float(r["close"]), "bb_mid": float(r["bb_mid"]),
                     "bb_up": float(r["bb_up"]), "bb_lo": float(r["bb_lo"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "close": 100.0, "bb_mid": 100.0,
            "bb_up": 99.0, "bb_lo": 101.0}  # crossed bands


FEATURE_COLS = ["tag_lo", "tag_hi", "re_lo", "re_hi", "dir"]


def compute_features(rows):
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
    n: int = 20                  # Bollinger lookback [example]
    mult: float = 2.0            # band multiplier [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: band-reversal, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.00   # concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S041 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["bb_up"] <= e["bb_lo"] or e["close"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    if len(evs) < 2:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    prev = evs[-2]
    re_lo = 1 if (prev["close"] < prev["bb_lo"] and e["close"] >= e["bb_lo"]) else 0
    re_hi = 1 if (prev["close"] > prev["bb_up"] and e["close"] <= e["bb_up"]) else 0
    direction = 1 if re_lo else (-1 if re_hi else 0)
    confidence = 0.7 if direction else 0.0  # tag+re-entry conviction [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = abs(e["close"] - e["bb_mid"]) / e["close"] * 1e4  # midline distance [example]
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
