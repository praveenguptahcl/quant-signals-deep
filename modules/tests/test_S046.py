"""Acceptance tests for S046 — Intraday U-shape timer.

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S046.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S046_tape.csv"
EXPECTED = FIX / "S046_expected.csv"

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



WINDOWS = {"open": (0, 6), "lunch": (18, 21), "close": (36, 39)}


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({"id": r["id"], "event_ts": int(r["event_ts"]),
                     "abs_bp": float(r["abs_bp"]),
                     "signed_bp": float(r["signed_bp"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "abs_bp": -3.0,
            "signed_bp": 3.0}  # negative absolute move


FEATURE_COLS = ["obs", "typ", "typ_sd", "z", "active", "signed", "dir"]


def _typ(window, cfg):
    return {"open": (cfg.typ_open, cfg.sd_open),
            "lunch": (cfg.typ_lunch, cfg.sd_lunch),
            "close": (cfg.typ_close, cfg.sd_close)}[window]


def compute_features(rows):
    cfg = Config()
    out = []
    for w, (a, b) in WINDOWS.items():
        seg = rows[a:b]
        if not seg:  # window not yet populated on short prefixes
            typ, sd = _typ(w, cfg)
            out.append({"id": w, "obs": float("nan"), "typ": typ,
                        "typ_sd": sd, "z": float("nan"), "active": 0,
                        "signed": float("nan"), "dir": 0})
            continue
        obs = sum(r["abs_bp"] for r in seg) / len(seg)
        signed = sum(r["signed_bp"] for r in seg) / len(seg)
        typ, sd = _typ(w, cfg)
        z = (obs - typ) / sd
        active = 1 if abs(z) >= cfg.z_thresh else 0
        # fade the SIGNED observed move — the timer is a deseasonalizer
        d = (-1 if signed > 0 else (1 if signed < 0 else 0)) * active
        out.append({"id": w, "obs": obs, "typ": typ, "typ_sd": sd,
                    "z": z, "active": active, "signed": signed, "dir": d})
    return out


@dataclass
class Config:
    typ_open: float = 21.5        # typical open abs move [example]
    sd_open: float = 2.84         # open dispersion [example]
    typ_lunch: float = 7.8        # typical lunch abs move [example]
    sd_lunch: float = 3.46        # lunch dispersion [example]
    typ_close: float = 23.1       # typical close abs move [example]
    sd_close: float = 1.76        # close dispersion [example]
    z_thresh: float = 1.5        # activity trigger [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: U-shape window fade, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.00   # concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S046 reference stub).

    A timer/deseasonalizer, not a standalone alpha: it emits only when a
    window's activity clears the trigger, fading the signed window move.
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["abs_bp"] < 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    feats = compute_features(evs)
    act = [f for f in feats if f["active"]]
    direction = act[0]["dir"] if act else 0
    confidence = 0.5 if direction else 0.0  # timer conviction [example]
    capital = 0.5 * confidence
    # cost gate predicate (normative): expected_cost_bps(...) <= k * edge_bps
    edge_bps = 10.0  # window-move edge [example]
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
    lunch = by_id["lunch"]
    # Chapter S4 hand-checks (seed 46): open 19.0bp -> z=0.88; lunch 14.0bp ->
    # z=1.79 (only window clearing 1.5); close 25.0bp -> z=1.08.
    assert abs(by_id["open"]["z"] - (-0.8803)) < 0.02, by_id["open"]
    assert by_id["open"]["active"] == 0
    assert abs(lunch["z"] - 1.7919) < 0.02, lunch
    assert lunch["active"] == 1
    assert abs(by_id["close"]["z"] - 1.0795) < 0.02, by_id["close"]
    assert by_id["close"]["active"] == 0
    # direction fades the signed window move: lunch signed -14bp -> long
    assert lunch["signed"] < 0 and lunch["dir"] == 1
    s = signal(dict(), rows, Config())
    assert s.direction == 1 and s.module_state == "OK"



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
