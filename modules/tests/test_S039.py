"""Acceptance tests for S039 — Idiosyncratic residual reversal.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode (§S3), and asserts features, causality, the cost
gate, guards, cooldown, and fixture provenance.

Run: python3 -m pytest modules/tests/test_S039.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S039_tape.csv"
EXPECTED = FIX / "S039_expected.csv"

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



SIGMA = {"A": 0.1233, "B": 0.22}  # pinned residual-vol estimates [example]


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({"id": r["id"], "event_ts": int(r["event_ts"]),
                     "bucket": int(r["bucket"]), "name": r["name"],
                     "mkt": float(r["mkt"]), "beta": float(r["beta"]),
                     "raw": float(r["raw"]),
                     "beta_age_days": 0,          # fresh beta [example]
                     "locate_asserted": True})   # consumer-asserted locate
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "bucket": 1, "name": "A",
            "mkt": 0.01, "beta": -1.0, "raw": 0.01,   # negative beta
            "beta_age_days": 0, "locate_asserted": True}


FEATURE_COLS = ["u", "cum", "z", "fade", "dir"]


def compute_features(rows):
    th = Config().z_thresh
    cum = {}
    out = []
    for r in rows:
        u = r["raw"] - r["beta"] * r["mkt"]          # idiosyncratic residual
        cum[r["name"]] = cum.get(r["name"], 0.0) + u
        z = cum[r["name"]] / SIGMA[r["name"]]
        fade = 1 if abs(z) >= th else 0
        d = (-1 if z > 0 else (1 if z < 0 else 0)) * fade  # fade the residual
        out.append({"id": r["id"], "u": u, "cum": cum[r["name"]],
                    "z": z, "fade": fade, "dir": d})
    return out


@dataclass
class Config:
    beta_A: float = 1.0           # market beta, name A [example] (fixture constant)
    beta_B: float = 0.9           # market beta, name B [example] (fixture constant)
    beta_window_days: int = 60    # rolling beta estimation window [example]
    vol_window_days: int = 20     # trailing residual-vol window [example]
    z_thresh: float = 2.0        # fade trigger [example]
    cost_gate_k: float = 0.5     # cost-gate multiplier [default]
    cooldown_s: float = 3600.0   # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: residual reversal, liquid large-cap."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.50   # [example] = borrow_bps_per_day; reason: intraday horizon, fade may short
    impact_bps = 1.00   # concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S039 reference stub).

    Mirrors the §S3 normative pseudocode: F1/F2 guards, §S2 entry guards,
    the cost-gate predicate, and the C10 cooldown. Never interpolates.
    """
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")          # F1
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["beta"] <= 0 or e["name"] not in SIGMA:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    feats = compute_features(evs)
    f = feats[-1]
    direction = f["dir"]
    # §S2 entry guards (Boolean, normative)
    beta_fresh = e["beta_age_days"] <= cfg.beta_window_days            # C11
    locate_ok = direction != -1 or e["locate_asserted"]                # C7
    edge_bps = abs(f["z"]) * 50.0                                      # [example]
    cost_ok = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal") \
        <= cfg.cost_gate_k * edge_bps                                  # cost-gate predicate
    entered = (direction != 0 and beta_fresh and locate_ok and cost_ok
               and e["event_ts"] >= state.get("cooldown_until", 0))     # C10
    confidence = min(1.0, abs(f["z"]) / 3.0) if entered else 0.0        # |z|=3 full [example]
    capital = 0.5 * confidence                                          # [default]
    direction = direction if entered else 0
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
    b6A, b6B = by_id["b6A"], by_id["b6B"]
    # Chapter S4 hand-checks: cumA=-0.09% zA=-0.73 (no fade); cumB=-0.47%
    # zB=-2.15 -> fade B only (long B)
    assert abs(b6A["cum"] - (-0.09)) < 1e-9, b6A
    assert abs(b6A["z"] - (-0.73)) < 0.015, b6A
    assert b6A["fade"] == 0 and b6A["dir"] == 0
    assert abs(b6B["cum"] - (-0.473)) < 1e-9, b6B
    assert abs(b6B["z"] - (-2.15)) < 0.015, b6B
    assert b6B["fade"] == 1 and b6B["dir"] == 1
    # causality: the residual at bucket t uses only bucket t's market return
    assert abs(by_id["b1A"]["u"] - (0.01 - 1.0 * 0.02)) < 1e-12
    assert abs(by_id["b1B"]["u"] - (-0.12 - 0.9 * 0.02)) < 1e-12



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


def test_empty_events_yields_unknown():
    """F1: no events -> UNKNOWN, never a fabricated signal."""
    s = signal(dict(), [], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.confidence == 0.0


def test_cooldown_suppresses_reentry():
    """C10: while now < cooldown_until, entries are suppressed even on a trigger."""
    rows = tape()
    cfg = Config()
    state = {"cooldown_until": rows[-1]["event_ts"] + cfg.cooldown_s}
    s = signal(state, rows, cfg)  # b6B triggers fade, but cooldown is active
    assert s.module_state == "OK"
    assert s.direction == 0 and s.confidence == 0.0 and s.capital == 0.0


def test_fixture_type_header_and_provenance():
    """Fixtures carry a TYPE header and synthetic provenance labels."""
    with open(TAPE) as fh:
        tape_head = [fh.readline(), fh.readline()]
    assert tape_head[0].strip() == "# TYPE: validation-run"
    assert "synthetic" in tape_head[1].lower()
    assert "seed 39" in tape_head[1]
    with open(EXPECTED) as fh:
        exp_head = fh.readline()
    assert exp_head.strip() == "# TYPE: validation-run"


def test_cost_gate_on_fixture_edge():
    """The cost gate resolves on the fixture's own edge, not just synthetic edges.

    b6B: z=-2.15 [example] -> edge_bps = 50*2.15 = 107.5; k*edge = 53.75,
    which clears the reference cost stack (2.30 bps), so the gate passes.
    """
    rows = tape()
    cfg = Config()
    s = signal(dict(), rows, cfg)
    assert s.direction == 1 and s.module_state == "OK"   # fade B only, long B
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert abs(cost - 2.30) < 1e-12                        # reference stack total
    assert cost <= cfg.cost_gate_k * (50.0 * 2.15)          # gate passes on fixture edge
    assert not (cost <= cfg.cost_gate_k * 0.01)             # sub-0.01 bps edge blocked
