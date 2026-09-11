"""Acceptance tests for S060 — Cross-asset lead-lag via Hayashi-Yoshida.

Template v1.0.0; deep-reviewed 2026-09-11. Reference implementation of the
chapter's normative pseudocode (§S3): real assertions including causality
(assert fill_event > signal_event), the ρ-gate, the cost-gate as a veto
(direction -> 0 with state staying OK, never an exception), invalid -> UNKNOWN,
the C11 exchange-timestamp input contract, and fixture TYPE/seed headers.

Decision change vs the first draft: the old `min_abs_hy = 5.0` [example] was in
HY-covariance units while the decision layer compares |rho_hat| on [-1, 1].
The unit bug is fixed: the gate is |rho_hat| >= cfg.rho_min (0.35 [example]).

Run: python3 -m pytest modules/tests/test_S060.py -q   (from repo root)
"""
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S060_tape.csv"
EXPECTED = FIX / "S060_expected.csv"

TOL = 1e-9  # float tolerance [default]
EXPECTED_COLS = ['hy_m1', 'hy_0', 'hy_p1', 'chosen_lag']
COL_TYPES = {'i': 'int', 'event_ts': 'int', 'asof_ts': 'int',
             'dx': 'float', 'dy': 'float', 'ts_source': 'str'}
LAG_GRID = (-1, 0, 1)  # fixture lag grid [example]


# ---------------------------------------------------------------- fixtures
def _raw_lines(path):
    with open(path) as f:
        return f.read().splitlines()


def load_csv(path):
    lines = [ln for ln in _raw_lines(path)
             if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def _conv(v, t):
    if t == "int":
        return int(v)
    if t == "float":
        return float(v)
    return v


def parse_tape():
    return [{k: _conv(r[k], COL_TYPES[k]) for k in COL_TYPES} for r in load_csv(TAPE)]


# --------------------------------------- reference: normative pseudocode §S3
@dataclass(frozen=True)
class SignalVector:
    symbol: str
    direction: int          # +1 | -1 | 0
    confidence: float       # 0..1
    capital: float          # 0..1
    computed_at: int        # int64 ns UTC
    staleness: int          # ns
    module_state: str       # OK | DEGRADED | UNKNOWN | OFF


def _hy(dx, dy, lag):
    """Reference HY overlap sum (textbook formula, chapter §S3).

    Binary overlap indicator 1{I_i^X ∩ (I_j^Y + lag) != ∅} on the fixture
    geometry X_i = [i, i+1], Y_j = [j+0.5, j+1.5].
    """
    tot = 0.0
    for i, a in enumerate(dx):
        for j, b in enumerate(dy):
            lo = max(i, j + 0.5 - lag)
            hi = min(i + 1, j + 1.5 - lag)
            if hi > lo:
                tot += a * b
    return tot


def _rho(dx, dy, lag):
    """HY correlation rho_hat(lag); 0.0 on degenerate variance (never NaN)."""
    cxx = sum(x * x for x in dx)
    cyy = sum(y * y for y in dy)
    if cxx <= 0.0 or cyy <= 0.0:
        return 0.0
    return _hy(dx, dy, lag) / math.sqrt(cxx * cyy)


def _argmax_lag(rho):
    """argmax over the lag grid; deterministic tie-break: smallest |lag|,
    then positive lag. Chapter §S3 tie-break rule."""
    return min(LAG_GRID, key=lambda l: (-rho[l], abs(l), -l))


def _count_overlaps(n, m):
    """Overlapping (X_i, Y_j) pairs on the fixture geometry, lag 0."""
    return sum(1 for i in range(n) for j in range(m)
               if min(i + 1, j + 1.5) > max(i, j + 0.5))


def recompute(rows):
    dx = [r["dx"] for r in rows]
    dy = [r["dy"] for r in rows]
    h = {l: _hy(dx, dy, l) for l in LAG_GRID}
    rho = {l: _rho(dx, dy, l) for l in LAG_GRID}
    return [{"hy_m1": h[-1], "hy_0": h[0], "hy_p1": h[1],
             "chosen_lag": _argmax_lag(rho)}]


@dataclass
class Config:
    rho_min: float = 0.35       # |rho_hat| gate [example]
    cost_gate_k: float = 0.5    # [default]
    lag_grid_max_s: float = 30.0    # ±30 s [example]
    lag_grid_step_ms: float = 100.0  # 100 ms steps [example]
    tolerance_ms: float = 10.0  # overlap tolerance 10 ms [example]
    cooldown_s: float = 60.0    # post-exit cooldown 60 s [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Callable cost model — reference stack for S060 (§S2 COST block)."""
    spread_bps = 0.50   # laggard-leg half-spread [example]
    fee_bps = 0.30      # taker fee [example]
    borrow_bps = 0.00   # reason: long-laggard reference leg [default]
    impact_bps = 0.50   # laggard fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps  # 1.30 bps [example]


def signal(state, bars, cfg):
    """Reference implementation of the §S3 normative pseudocode.

    Cost gate is a VETO (direction -> 0, state stays OK), not an assert.
    Causality: earliest fill is the next bar's open, strictly after the signal.
    """
    bars = list(bars)
    t = bars[-1]["event_ts"] if bars else 0
    invalid = (
        not bars
        or any(r.get("ts_source") != "exchange" for r in bars)  # C11
        or any(not math.isfinite(r["dx"]) or not math.isfinite(r["dy"])
               for r in bars)  # F1/F2, never interpolate
        or _count_overlaps(len(bars), len(bars)) < 2
    )
    if invalid:
        return SignalVector("TEST", 0, 0.0, 0.0, t, 0, "UNKNOWN")
    dx = [r["dx"] for r in bars]
    dy = [r["dy"] for r in bars]
    rho = {l: _rho(dx, dy, l) for l in LAG_GRID}
    lag_hat = _argmax_lag(rho)
    rho_hat = rho[lag_hat]

    direction = 0
    if lag_hat > 0 and abs(rho_hat) >= cfg.rho_min:
        leader_move = dx[-1]  # last X interval return; intervals end <= t
        direction = 1 if leader_move > 0 else (-1 if leader_move < 0 else 0)

    edge_bps = 100.0 * max(0.0, abs(rho_hat) - cfg.rho_min)  # modeled edge [example]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    if direction and not (cost <= cfg.cost_gate_k * edge_bps):
        direction = 0  # cost-gate veto: hint suppressed, module stays OK

    confidence = min(1.0, max(0.0, abs(rho_hat) - cfg.rho_min) / (1.0 - cfg.rho_min))
    if not direction:
        confidence = 0.0
    sig = SignalVector("TEST", direction, confidence, 0.5 * confidence, t,
                       bars[-1]["asof_ts"] - t, "OK")
    return sig


def _rows(n, dx_last=1.0):
    """Synthetic exchange-timestamped rows for decision-layer tests."""
    return [{"i": i, "event_ts": 1_000_000_000 * (i + 1), "asof_ts": 1_000_000_000 * (i + 1) + 12_000,
             "dx": dx_last if i == n - 1 else 0.0, "dy": 0.0, "ts_source": "exchange"}
            for i in range(n)]


# ------------------------------------------------------------------- tests
def test_fixture_headers_and_contract():
    """TYPE header, seed line, and the C11 ts_source input contract."""
    for path in (TAPE, EXPECTED):
        lines = _raw_lines(path)
        assert any(l.startswith("# TYPE: validation-run") for l in lines), path
        assert any(l.startswith("# seed: 60") for l in lines), path
    rows = parse_tape()
    assert len(rows) == 11  # hand-verified row count [measured]
    assert all(r["ts_source"] == "exchange" for r in rows)
    for r in rows:  # dual timestamps, int64 ns, asof >= event
        assert r["asof_ts"] >= r["event_ts"] > 0
        assert math.isfinite(r["dx"]) and math.isfinite(r["dy"])


def test_fixture_recomputes_to_expected():
    """Reference recomputation of the tape matches expected.csv."""
    rows = parse_tape()
    exp = load_csv(EXPECTED)
    got = recompute(rows)
    assert len(got) == len(exp) == 1
    for g, e in zip(got, exp):
        for k in EXPECTED_COLS:
            gv, ev = g[k], e[k]
            try:
                assert abs(float(gv) - float(ev)) <= TOL, (k, gv, ev)
            except (ValueError, TypeError):
                assert str(gv) == str(ev), (k, gv, ev)
    # chapter hand-checks: grand sums exact
    assert abs(got[0]["hy_0"] - 17.0) < 1e-9
    assert abs(got[0]["hy_m1"] - (-7.0)) < 1e-9
    assert abs(got[0]["hy_p1"] - 15.0) < 1e-9
    assert got[0]["chosen_lag"] == 0  # argmax is the zero lag: no lead measured


def test_fixture_end_to_end_signal_is_flat():
    """Zero-lag argmax -> FLAT: direction 0, state OK, valid SignalVector."""
    rows = parse_tape()
    s = signal({}, rows, Config())
    assert s.module_state == "OK"
    assert s.direction == 0  # lag_hat == 0: no lead-lag edge to trade
    assert s.confidence == 0.0 and s.capital == 0.0
    assert 0.0 <= s.confidence <= 1.0 and 0.0 <= s.capital <= 1.0
    assert s.computed_at == rows[-1]["event_ts"]


def test_rho_gate_pass_pins_direction_and_confidence(monkeypatch):
    """Decision layer: |rho_hat| >= rho_min and lag > 0 -> signed direction,
    confidence from the chapter formula."""
    monkeypatch.setattr(sys.modules[__name__], "_rho",
                        lambda dx, dy, lag: {-1: -0.2, 0: 0.1, 1: 0.8}[lag])
    s = signal({}, _rows(3, dx_last=2.0), Config())
    assert s.module_state == "OK"
    assert s.direction == 1  # lag +1, leader moved up
    assert abs(s.confidence - (0.8 - 0.35) / (1.0 - 0.35)) < 1e-12
    assert abs(s.capital - 0.5 * s.confidence) < 1e-12
    s2 = signal({}, _rows(3, dx_last=-2.0), Config())
    assert s2.direction == -1  # leader moved down -> short the laggard


def test_rho_gate_fail_blocks_direction(monkeypatch):
    """|rho_hat| < rho_min -> direction 0 even with a positive lag."""
    monkeypatch.setattr(sys.modules[__name__], "_rho",
                        lambda dx, dy, lag: {-1: 0.1, 0: 0.05, 1: 0.2}[lag])
    s = signal({}, _rows(3), Config())
    assert s.module_state == "OK"
    assert s.direction == 0 and s.confidence == 0.0 and s.capital == 0.0


def test_cost_gate_veto_zeroes_direction_keeps_ok(monkeypatch):
    """Tiny modeled edge -> cost-gate veto: direction 0 but state stays OK
    (a veto is not an error; UNKNOWN is reserved for invalid input)."""
    monkeypatch.setattr(sys.modules[__name__], "_rho",
                        lambda dx, dy, lag: {-1: 0.1, 0: 0.05, 1: 0.36}[lag])
    s = signal({}, _rows(3), Config())
    # edge = 100 * (0.36 - 0.35) = 1.0 bps; cost 1.30 > 0.5 * 1.0 -> veto
    assert s.module_state == "OK"
    assert s.direction == 0 and s.confidence == 0.0


def test_reference_cost_stack_and_predicate():
    """Reference stack sums to 1.30 bps; predicate passes on large edge,
    blocks on tiny edge (k = 0.5 [default])."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert abs(cost - 1.30) < 1e-12  # reference stack [example]
    assert cost <= k * 100000.0   # huge edge -> gate passes
    assert not (cost <= k * 0.0001)  # tiny edge -> gate blocks


def test_no_signal_bar_fills():
    """Causality: computed_at is the signal bar's event_ts; the earliest
    fill is the next bar's open, strictly later (assert fill > signal)."""
    rows = parse_tape()
    for i in range(len(rows)):
        s = signal({}, rows[: i + 1], Config())
        assert s.computed_at == rows[i]["event_ts"], "signal stamped at its bar"
        if i + 1 < len(rows):
            earliest_fill = rows[i + 1]["event_ts"]  # open(t+1)
            assert earliest_fill > s.computed_at, "signal-bar fill"


def test_invalid_inputs_yield_unknown():
    cfg = Config()
    empty = signal({}, [], cfg)
    assert empty.module_state == "UNKNOWN" and empty.direction == 0
    bad_num = {"i": 0, "event_ts": 1, "asof_ts": 2, "dx": float("nan"),
               "dy": 1.0, "ts_source": "exchange"}
    s = signal({}, [bad_num, bad_num], cfg)
    assert s.module_state == "UNKNOWN" and s.direction == 0  # F1/F2
    bad_src = dict(bad_num, dx=1.0, ts_source="sip")
    s2 = signal({}, [bad_src, bad_src], cfg)
    assert s2.module_state == "UNKNOWN" and s2.direction == 0  # C11
    single = {"i": 0, "event_ts": 1, "asof_ts": 2, "dx": 1.0,
              "dy": 1.0, "ts_source": "exchange"}
    s3 = signal({}, [single], cfg)
    assert s3.module_state == "UNKNOWN"  # fewer than 2 overlapping intervals
