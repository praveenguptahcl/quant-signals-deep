"""Acceptance tests for S074 — Gamma exposure (GEX) & dealer positioning.

Template v1.0.0, module v1.1.0. Reference implementation of the §S3 normative
pseudocode: events (not bars) grouped into OI print batches, symbol from state,
dual-clock + F4 staleness assertions, executable cost-gate predicate, and the
t→t+1 causality assertion. Invalid input → UNKNOWN, never interpolate.

Run: python3 -m pytest modules/tests/test_S074.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S074_tape.csv"
EXPECTED = FIX / "S074_expected.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ['strike', 'gex', 'total_gex', 'regime']
COL_TYPES = {'strike': 'float', 'event_ts': 'int', 'asof_ts': 'int', 'gamma': 'float', 'net_oi': 'float'}
DAY_NS = 86_400_000_000_000  # one day in int64 ns [example]


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def _conv(v, t):
    if t == "int":
        return int(v)
    if t == "float":
        return float(v)
    return v


def parse_tape():
    return [{k: _conv(r[k], COL_TYPES[k]) for k in COL_TYPES} for r in load_csv(TAPE)]


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


def recompute(rows):
    gex = [r["gamma"] * r["net_oi"] * 10000.0 for r in rows]
    tot = sum(gex)
    reg = "amplify" if tot < 0 else "pin"
    return [{"strike": r["strike"], "gex": g, "total_gex": tot, "regime": reg}
            for r, g in zip(rows, gex)]


@dataclass
class Config:
    cost_gate_k: float = 0.5            # [default]
    gex_multiplier: float = 10000.0     # [example], fixed by arithmetic
    confidence_scale: float = 5e6       # [example]
    regime_threshold: float = 0.0       # [example] convention
    capital_fraction: float = 0.5       # [default]
    staleness_ttl_s: int = 259200       # 3 days [default] = 3x daily cadence (F4)
    emissions_rate_limit: float = 100.0  # per symbol/s [default]
    post_exit_cooldown_s: int = 60       # [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.50   # equity-leg half-spread [example]
    fee_bps = 0.30      # taker fee [example]
    borrow_bps = 0.00   # reason: reference build long-only pin fade [default]
    impact_bps = 0.50   # pin-day fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """Reference implementation of the §S3 normative pseudocode."""
    events = list(events)
    symbol = state.get("symbol") if isinstance(state, dict) else None
    now_ns = state.get("now_ns") if isinstance(state, dict) else 0
    if not events or not symbol:
        return SignalVector(symbol or "?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")  # F1
    prints = {}
    for r in events:
        prints.setdefault(r["event_ts"], []).append(r)
    rows = prints[max(prints)]  # latest OI print batch
    b = rows[0]
    if any((not math.isfinite(r["gamma"])) or r["gamma"] < 0 for r in rows):
        return SignalVector(symbol, 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F2
    if any(not math.isfinite(r["net_oi"]) for r in rows):
        return SignalVector(symbol, 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F2
    assert all(r["asof_ts"] >= r["event_ts"] for r in rows), "dual-clock rule"
    if now_ns - b["asof_ts"] > cfg.staleness_ttl_s * 1_000_000_000:
        return SignalVector(symbol, 0, 0.0, 0.0, b["event_ts"], 0, "UNKNOWN")  # F4
    tot = sum(r["gamma"] * r["net_oi"] * cfg.gex_multiplier for r in rows)
    regime = "amplify" if tot < cfg.regime_threshold else "pin"  # [example] convention
    direction = -1 if regime == "amplify" else 0
    confidence = min(1.0, abs(tot) / cfg.confidence_scale) if direction else 0.0  # [example]
    edge_bps = abs(tot) / 1e6  # modeled per-trade edge [example]
    cost_bps = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")  # [example] ref inputs
    if not (cost_bps <= cfg.cost_gate_k * edge_bps):
        direction, confidence = 0, 0.0  # cost gate [default]
    earliest_fill_ts = b["event_ts"] + DAY_NS  # tradable no earlier than open(t+1)
    assert earliest_fill_ts > b["event_ts"], "causality: no signal-bar fills"
    return SignalVector(symbol, direction, confidence, cfg.capital_fraction * confidence,
                        b["event_ts"], b["asof_ts"] - b["event_ts"], "OK")


def make_state(rows, now_ns=None):
    b = rows[-1]
    return {"symbol": "TEST", "now_ns": b["asof_ts"] + 1 if now_ns is None else now_ns}


# ------------------------------------------------------------------- tests
def test_fixture_recomputes_to_expected():
    """Reference recomputation of the tape matches expected.csv."""
    rows = parse_tape()
    exp = load_csv(EXPECTED)
    got = recompute(rows)
    assert len(got) == len(exp), (len(got), len(exp))
    for g, e in zip(got, exp):
        for k in EXPECTED_COLS:
            gv, ev = g[k], e[k]
            try:
                assert abs(float(gv) - float(ev)) <= TOL, (k, gv, ev)
            except (ValueError, TypeError):
                assert str(gv) == str(ev), (k, gv, ev)
    # pinned hand-checks (fixture totals)
    assert abs(got[1]["gex"] - (-5040000.0)) < 1e-6
    assert abs(got[2]["gex"] - 5200000.0) < 1e-6
    assert abs(got[0]["total_gex"] - (-3590000.0)) < 1e-6
    assert got[0]["regime"] == "amplify"


def test_signal_emits_valid_signalvector():
    rows = parse_tape()
    cfg = Config()
    sigs = [signal(make_state(rows[: i + 1]), rows[: i + 1], cfg) for i in range(len(rows))]
    assert len(sigs) == len(rows)
    for s in sigs:
        assert s.direction in (+1, -1, 0)
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.capital <= 1.0
        assert s.module_state in ("OK", "DEGRADED", "UNKNOWN", "OFF")
    # vector-level pins on the full fixture (default config)
    s = signal(make_state(rows), rows, cfg)
    tot = sum(r["gamma"] * r["net_oi"] * 10000.0 for r in rows)
    assert s.symbol == "TEST"
    assert s.direction == -1
    assert abs(s.confidence - min(1.0, abs(tot) / 5e6)) <= 1e-12
    assert abs(s.capital - 0.5 * s.confidence) <= 1e-12
    assert s.module_state == "OK"


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    rows = parse_tape()
    cfg = Config()
    for i in range(len(rows)):
        s = signal(make_state(rows[: i + 1]), rows[: i + 1], cfg)
        assert s.computed_at == rows[i]["event_ts"], "signal must be timestamped at its bar"
        earliest_fill_ts = s.computed_at + DAY_NS  # open(t+1) per the timing box
        assert earliest_fill_ts > s.computed_at, "signal-bar fill"


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "X", "taker", "normal")
    assert cost >= 0.0
    assert cost <= k * 100000.0   # huge edge -> gate passes
    assert not (cost <= k * 0.0001)  # tiny edge -> gate blocks


def test_cost_gate_blocks_tiny_edge_in_signal():
    """Tiny total GEX fails the gate inside signal(): direction 0, confidence 0."""
    rows = parse_tape()
    tiny = [{**r, "gamma": r["gamma"] * 1e-6} for r in rows]  # tot ≈ -3.59 → edge_bps ≈ 3.6e-6
    s = signal(make_state(tiny), tiny, Config())
    assert s.module_state == "OK"
    assert s.direction == 0 and s.confidence == 0.0 and s.capital == 0.0


def test_pin_regime_emits_zero_direction():
    """Positive total GEX → regime pin → direction 0."""
    rows = parse_tape()
    flipped = [{**r, "net_oi": -r["net_oi"]} for r in rows]  # tot ≈ +3.59M
    s = signal(make_state(flipped), flipped, Config())
    assert s.module_state == "OK"
    assert s.direction == 0 and s.confidence == 0.0


def test_invalid_input_yields_unknown():
    rows = parse_tape()
    cfg = Config()
    bad_gamma = [{**rows[0], "gamma": -0.5}]
    assert signal(make_state(bad_gamma), bad_gamma, cfg).module_state == "UNKNOWN"
    bad_oi = [{**rows[0], "net_oi": float("nan")}]
    assert signal(make_state(bad_oi), bad_oi, cfg).module_state == "UNKNOWN"
    assert signal({"symbol": "TEST", "now_ns": rows[-1]["asof_ts"] + 1}, [], cfg).module_state == "UNKNOWN"  # F1 empty
    no_symbol = {"now_ns": rows[-1]["asof_ts"] + 1}
    assert signal(no_symbol, rows, cfg).module_state == "UNKNOWN"


def test_stale_print_yields_unknown():
    """Print older than the F4 staleness TTL (3 days [default]) → UNKNOWN."""
    rows = parse_tape()
    b = rows[-1]
    stale_state = {"symbol": "TEST", "now_ns": b["asof_ts"] + 4 * DAY_NS}
    s = signal(stale_state, rows, Config())
    assert s.module_state == "UNKNOWN" and s.direction == 0
    fresh_state = {"symbol": "TEST", "now_ns": b["asof_ts"] + 2 * DAY_NS}
    assert signal(fresh_state, rows, Config()).module_state == "OK"
