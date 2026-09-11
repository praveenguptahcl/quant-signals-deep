"""Acceptance tests for S037 — Jump-filtered gap reversal (Lee–Mykland veto).

Template v1.0.0. Sketch-level but concrete: loads the fixture tape, runs a
reference implementation of the chapter's normative pseudocode, and asserts
causality, the cost gate, and hand-checked fixture arithmetic.

Run: python3 -m pytest modules/tests/test_S037.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S037_tape.csv"
EXPECTED = FIX / "S037_expected.csv"

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



THRESH_5PCT = 2.9702  # Gumbel 95% quantile -ln(-ln(0.95)) [documented]


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({"id": r["id"], "event_ts": int(r["event_ts"]),
                     "session": r["session"],
                     "prior_close": float(r["prior_close"]) if r["prior_close"] else float("nan"),
                     "open": float(r["open"]) if r["open"] else float("nan"),
                     "close": float(r["close"])})
    return rows


def event_ts(row):
    return row["event_ts"]


def bad_event():
    return {"id": "bad", "event_ts": 1, "session": "bad",
            "prior_close": 100.0, "open": 102.0, "close": -5.0}  # negative close


FEATURE_COLS = ["r_open", "V", "Z", "T", "jump", "dir"]


def lm_stats(prior_close, open_, closes):
    """Lee-Mykland jump test on the overnight return vs intraday bipower var."""
    r_open = math.log(open_ / prior_close)
    px = [open_] + list(closes)
    rets = [math.log(px[i + 1] / px[i]) for i in range(len(px) - 1)]
    k = len(rets)
    adj = sum(abs(rets[i] * rets[i + 1]) for i in range(k - 1))
    # local bipower variation with the (k-1) averaging from the chapter
    V = (math.pi / 2.0) * adj / (k - 1)
    Z = r_open / math.sqrt(V)
    # extreme-value normalization, n = intraday return count (Lee-Mykland 2008)
    A = math.sqrt(2 * math.log(k)) - (math.log(math.pi) + math.log(math.log(k))) / (2 * math.sqrt(2 * math.log(k)))
    B = 1.0 / math.sqrt(2 * math.log(k))
    T = (Z - A) / B
    return r_open, V, Z, T


def compute_features(rows):
    sessions, order = {}, []
    for i, r in enumerate(rows):
        if r["session"] not in sessions:
            sessions[r["session"]] = []
            order.append(r["session"])
        sessions[r["session"]].append(i)
    out = []
    for s in order:
        idx = sessions[s]
        pc, op = rows[idx[0]]["prior_close"], rows[idx[0]]["open"]
        closes = [rows[i]["close"] for i in idx]
        r_open, V, Z, T = lm_stats(pc, op, closes)
        jump = 1 if T > THRESH_5PCT else 0
        # jump -> veto (stand down), never reverse or chase; no jump -> defer
        # to the gap-fade module (S036): fade only inside its gate
        gap = op / pc - 1.0
        s036_dir = (-1 if gap > 0 else (1 if gap < 0 else 0)) if 0.005 <= abs(gap) <= 0.05 else 0
        out.append({"id": s, "r_open": r_open, "V": V, "Z": Z, "T": T,
                    "jump": jump, "dir": 0 if jump else s036_dir})
    return out


@dataclass
class Config:
    jump_thresh: float = 2.9702   # 5% LM threshold [documented]
    cost_gate_k: float = 0.5      # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model: gap-fade entry gated by the jump filter."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0    # open-auction concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S037 reference stub)."""
    evs = list(events)
    if not evs:
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["close"] <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    sess = [x for x in evs if x["session"] == e["session"]]
    if len(sess) < 3:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")
    pc, op = sess[0]["prior_close"], sess[0]["open"]
    if not (pc == pc and op == op) or pc <= 0 or op <= 0:
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    _, _, _, T = lm_stats(pc, op, [x["close"] for x in sess])
    jump = T > cfg.jump_thresh
    # jump -> veto: direction 0, state OK (a veto is not an error)
    direction = 0
    confidence, capital = 0.0, 0.0
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
    s1 = by_id["s1"]
    # Chapter S4 hand-checks on the S036 tape: r_open=0.019803, V=1.535e-5,
    # Z=5.05, T far above the 5% threshold 2.970 -> jump -> veto (dir 0)
    assert abs(s1["r_open"] - 0.019803) < 1e-5, s1
    assert abs(s1["V"] - 0.0000153577) < 1e-9, s1
    assert abs(s1["Z"] - 5.053) < 0.01, s1
    assert abs(s1["T"] - 7.228) < 0.02, s1
    assert s1["jump"] == 1 and s1["dir"] == 0
    assert abs(THRESH_5PCT - 2.9702) < 1e-4
    # s2: small gap, quiet tape -> no jump -> defers to S036 (below gate -> 0)
    s2 = by_id["s2"]
    assert s2["jump"] == 0 and s2["dir"] == 0



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
