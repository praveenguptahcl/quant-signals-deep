"""Acceptance tests for S046 — Intraday U-shape timer.

Template v1.0.0. Loads the fixture tapes, runs a reference implementation of
the chapter's normative pseudocode (§S3), and pins behavior: fixture
arithmetic, window-completeness gating, boundary activation, the confidence
formula, cooldown, the locate veto, the cost gate (taker + maker), causality,
and UNKNOWN on invalid input.

Run: python3 -m pytest modules/tests/test_S046.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S046_tape.csv"
EXPECTED = FIX / "S046_expected.csv"
BOUNDARY = FIX / "S046_boundary.csv"

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


# bucket spans per window (10-min [fixed] buckets from session open)
WINDOWS = {"open": (0, 6), "lunch": (18, 21), "close": (36, 39)}


def tape(path=TAPE):
    rows = []
    for r in load_csv(path):
        rows.append({"id": r["id"], "event_ts": int(r["event_ts"]),
                     "abs_bp": float(r["abs_bp"]),
                     "signed_bp": float(r["signed_bp"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "abs_bp": -3.0,
            "signed_bp": 3.0}  # negative absolute move


def halt_event():
    return {"id": "h", "event_ts": 1, "abs_bp": 8.0,
            "signed_bp": 8.0, "event_type": "HALTED"}


FEATURE_COLS = ["obs", "typ", "typ_sd", "z", "active", "signed", "dir"]


def _typ(window, cfg):
    return {"open": (cfg.typ_open, cfg.sd_open),
            "lunch": (cfg.typ_lunch, cfg.sd_lunch),
            "close": (cfg.typ_close, cfg.sd_close)}[window]


def compute_features(rows):
    cfg = Config()
    by_id = {r["id"]: r for r in rows}
    out = []
    for w, (a, b) in WINDOWS.items():
        span = ["b%d" % k for k in range(a, b)]
        seg = [by_id[s] for s in span if s in by_id]
        complete = 1 if len(seg) == len(span) else 0  # complete-window gating
        typ, sd = _typ(w, cfg)
        if not seg:
            out.append({"id": w, "obs": float("nan"), "typ": typ,
                        "typ_sd": sd, "z": float("nan"), "active": 0,
                        "signed": float("nan"), "dir": 0, "complete": 0})
            continue
        obs = sum(r["abs_bp"] for r in seg) / len(seg)
        signed = sum(r["signed_bp"] for r in seg) / len(seg)
        z = (obs - typ) / sd
        # normative rule: incomplete windows are masked — never active
        active = 1 if (complete and abs(z) >= cfg.z_thresh) else 0
        # fade the SIGNED observed move — the timer is a deseasonalizer
        d = (-1 if signed > 0 else (1 if signed < 0 else 0)) * active
        out.append({"id": w, "obs": obs, "typ": typ, "typ_sd": sd,
                    "z": z, "active": active, "signed": signed, "dir": d,
                    "complete": complete})
    return out


@dataclass
class Config:
    typ_open: float = 21.5        # typical open abs move [example]
    sd_open: float = 2.84         # open dispersion [example]
    typ_lunch: float = 7.8        # typical lunch abs move [example]
    sd_lunch: float = 3.46        # lunch dispersion [example]
    typ_close: float = 23.1       # typical close abs move [example]
    sd_close: float = 1.76        # close dispersion [example]
    z_thresh: float = 1.5         # activity trigger [example]
    cost_gate_k: float = 0.5      # cost-gate multiplier [default]
    edge_bps: float = 10.0        # window-move edge when active [example]
    cooldown_s: float = 600.0     # post-exit cooldown, seconds [default]
    locate_ok: bool = True        # consumer asserts Reg-SHO locate [default]
    bucket_min: int = 10          # bucket width, minutes [fixed]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: U-shape window fade, liquid large-cap.

    Fee component [documented]: Nasdaq Rule 7018 standard remove-liquidity
    fee $0.0030/share at the $50 [example] reference print -> 0.60 bps.
    """
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.60      # [documented] $0.0030/share ÷ $50 reference print [example]
    borrow_bps = 0.0    # [default] long-biased reference; reason: no borrow
    impact_bps = 1.00   # concession [example]
    if side == "maker":
        fee_bps = -0.20  # rebate [example]; verify against the live tier at scale
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S046 reference stub).

    Normative §S3 pseudocode: a timer/deseasonalizer, not a standalone alpha.
    Fires only on COMPLETE abnormal windows (|z| >= z_thresh), fading the
    signed window move; the loudest abnormal window wins (argmax |z|).
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")      # F1
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["abs_bp"] < 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    # §S0.5 market states: halt freezes, auction holds (DEGRADED)
    if e.get("event_type") == "HALTED":
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    if e.get("event_type") == "AUCTION":
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "DEGRADED")

    feats = compute_features(evs)
    act = [f for f in feats if f["active"]]
    direction, z_star = 0, 0.0
    if act:
        w = max(act, key=lambda f: abs(f["z"]))                     # loudest abnormal window
        z_star = w["z"]
        direction = w["dir"]

    # C10: post-exit cooldown suppresses re-entry (state stays OK)
    if e["event_ts"] < state.get("cooldown_until", 0):
        direction = 0
    # C7: SHORT requires an asserted locate
    if direction < 0 and not cfg.locate_ok:
        direction = 0
    # normative confidence: linear in abnormality above the trigger [default]
    confidence = (_clip((abs(z_star) - cfg.z_thresh) / (2.5 - cfg.z_thresh),
                        0.0, 1.0) if direction else 0.0)
    capital = 0.5 * confidence                                       # 0.5 [default]
    # C2 / normative cost-gate predicate: expected_cost_bps(...) <= k * edge_bps
    ok = (expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
          <= cfg.cost_gate_k * cfg.edge_bps)
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
        assert f["complete"] == 1  # full tape: every window complete

    by_id = {f["id"]: f for f in feats}
    lunch = by_id["lunch"]
    # Chapter S4 hand-checks (seed 46): open 19.0bp -> z=-0.88; lunch 14.0bp ->
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
    assert abs(cost - 2.10) < 1e-9  # 0.50 [example] + 0.60 [documented] + 0.0 [default] + 1.00 [example]
    assert cost <= k * 100.0   # huge edge -> gate passes
    assert not (cost <= k * 0.01)  # tiny edge -> gate blocks


def test_invalid_input_yields_unknown():
    s = signal(dict(), [bad_event()], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0


def test_boundary_activation():
    """|z| = 1.55 fires; |z| = 1.45 does not (trigger z_thresh = 1.5)."""
    rows = tape(BOUNDARY)
    by_id = {f["id"]: f for f in compute_features(rows)}
    assert abs(by_id["lunch"]["z"] - 1.55) < 1e-6
    assert by_id["lunch"]["active"] == 1
    assert abs(by_id["open"]["z"] - 1.45) < 1e-3
    assert by_id["open"]["active"] == 0
    assert by_id["close"]["active"] == 0
    s = signal(dict(), rows, Config())
    # lunch is the only active window: signed -13.163bp -> long
    assert s.direction == 1 and s.module_state == "OK"


def test_confidence_formula_pinned():
    """confidence = clip((|z| - z_thresh) / (2.5 - z_thresh), 0, 1) [default]."""
    s = signal(dict(), tape(), Config())
    z_lunch = 1.7919075144508672  # chapter S4 hand-check [example]
    exp_conf = (abs(z_lunch) - 1.5) / (2.5 - 1.5)
    assert abs(s.confidence - exp_conf) < 1e-9, s
    assert abs(s.capital - 0.5 * exp_conf) < 1e-9, s


def test_incomplete_window_never_fires():
    """Partial-day prefixes mask incomplete windows: no signal, state OK."""
    rows = tape()[:10]  # open window complete but inactive; lunch/close missing
    by_id = {f["id"]: f for f in compute_features(rows)}
    assert by_id["lunch"]["complete"] == 0
    assert by_id["close"]["complete"] == 0
    s = signal(dict(), rows, Config())
    assert s.direction == 0 and s.module_state == "OK"


def test_cooldown_suppresses_reentry():
    """C10: entries suppressed while now < cooldown_until; state stays OK."""
    rows = tape()
    state = {"cooldown_until": rows[-1]["event_ts"] + 600_000_000_000}
    s = signal(state, rows, Config())
    assert s.direction == 0 and s.confidence == 0.0
    assert s.module_state == "OK"


def test_maker_side_cost():
    """Maker side uses the rebate branch: cheaper than taker."""
    taker = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    maker = expected_cost_bps(1.0, 0.001, "XNAS", "maker", "normal")
    assert abs(maker - (0.50 - 0.20 + 0.0 + 1.00)) < 1e-9
    assert maker < taker


def test_short_requires_locate():
    """C7: SHORT direction needs cfg.locate_ok; otherwise zeroed."""
    rows = tape()
    # flip the lunch window's signed move positive -> fade direction is short
    flipped = []
    for r in rows:
        r = dict(r)
        if 18 <= int(r["id"][1:]) <= 20:
            r["signed_bp"] = -r["signed_bp"]
        flipped.append(r)
    s_off = signal(dict(), flipped, Config(locate_ok=False))
    assert s_off.direction == 0 and s_off.module_state == "OK"
    s_on = signal(dict(), flipped, Config(locate_ok=True))
    assert s_on.direction == -1 and s_on.module_state == "OK"


def test_halt_freezes_to_unknown():
    """§S0.5: a HALTED event freezes the module -> UNKNOWN, no direction."""
    s = signal(dict(), [halt_event()], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0
