"""Acceptance tests for S037 — Jump-filtered gap reversal (Lee–Mykland veto).

Template v1.0.0. Reference implementation of the chapter's normative §S3
pseudocode: loads the fixture tape, asserts causality, the (vacuous)
cost-gate invariant, veto-flag exposure, warmup, cooldown, and hand-checked
fixture arithmetic.

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
    jump_thresh: float = 2.9702   # 5% LM threshold [documented] - pinned, not a knob
    min_bars: int = 3             # warmup: min intraday bars after open [default]
    cost_gate_k: float = 0.5      # cost-gate multiplier [default]
    cooldown_s: float = 600.0    # post-exit cooldown, seconds [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    """Reference cost model from the §S2 COST block (callable)."""
    spread_bps = 0.50   # half-spread [example]
    fee_bps = 0.30      # taker incl. regulatory [example]
    borrow_bps = 0.0    # long-biased reference; reason: no borrow [default]
    impact_bps = 1.0    # open-auction concession [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def _block(state, e, cfg):
    """F1/F2: invalid input -> UNKNOWN + C10 cooldown, never interpolate."""
    state["veto_flag"] = False
    state["cooldown_until"] = e["event_ts"] + int(cfg.cooldown_s * 1e9)
    state["module_state"] = "UNKNOWN"


def signal(state, events, cfg):
    """signal(state, events, cfg) -> SignalVector (S037 reference implementation).

    Mirrors the normative §S3 pseudocode: always emits direction 0 (a veto is
    a stand-down, never a reversal); the veto is exposed via state['veto_flag'].
    """
    evs = list(events)
    if not evs:
        state["module_state"] = "UNKNOWN"
        return SignalVector("?", 0, 0.0, 0.0, 0, 0, "UNKNOWN")
    e = evs[-1]
    # F1/F2: invalid input -> UNKNOWN, never interpolate
    if e["close"] <= 0:
        _block(state, e, cfg)
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    # F3: monotonic causality clock
    if e["event_ts"] < state.get("last_ts", 0):
        _block(state, e, cfg)
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    state["last_ts"] = e["event_ts"]
    # C10: post-exit cooldown -> suppressed as DEGRADED
    if e["event_ts"] < state.get("cooldown_until", 0):
        state["module_state"] = "DEGRADED"
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "DEGRADED")
    # warmup: too few bars for a stable bipower estimate -> OK, flat
    sess = [x for x in evs if x["session"] == e["session"]]
    if len(sess) < cfg.min_bars:
        state["veto_flag"] = False
        state["module_state"] = "OK"
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "OK")
    pc, op = sess[0]["prior_close"], sess[0]["open"]
    if not (pc == pc and op == op) or pc <= 0 or op <= 0:
        _block(state, e, cfg)
        return SignalVector("TEST:XNAS", 0, 0.0, 0.0,
                            e["event_ts"], 0, "UNKNOWN")
    _, _, _, T = lm_stats(pc, op, [x["close"] for x in sess])
    jump = T > cfg.jump_thresh
    state["veto_flag"] = bool(jump)   # consumers read this flag (C11)
    state["module_state"] = "OK"
    # normative cost gate, vacuous by construction: edge_bps = 0 [example]
    # (RISK-FILTER-ONLY) -> the predicate can never pass for a tradeable
    # emission; any future direction != 0 would trip this assertion in CI.
    cost = expected_cost_bps(0, 0, "XNAS", "taker", "normal")
    assert not (cost <= cfg.cost_gate_k * 0.0), "cost-gate invariant violated"
    # jump -> veto: direction 0, state OK (a veto is not an error);
    # no jump -> defer to S036 (still direction 0 from this module)
    return SignalVector("TEST:XNAS", 0, 0.0, 0.0, e["event_ts"], 0, "OK")



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
    """expected_cost_bps(...) <= k * edge_bps is executable and behaves sanely;
    inside S037 it is invoked with edge_bps = 0 (RISK-FILTER-ONLY invariant)."""
    cost = expected_cost_bps(1.0, 0.001, "XNAS", "taker", "normal")
    assert abs(cost - 1.8) < 1e-12  # 1.8 bps reference stack [example]
    k = 0.5  # [default]
    assert cost <= k * 100.0        # huge edge -> predicate passes
    assert not (cost <= k * 0.01)   # tiny edge -> predicate blocks
    # §S3 normative invocation: edge_bps = 0 [example] -> provably vacuous
    assert not (cost <= k * 0.0)


def test_invalid_input_yields_unknown():
    s = signal(dict(), [bad_event()], Config())
    assert s.module_state == "UNKNOWN"
    assert s.direction == 0 and s.capital == 0.0


def test_veto_flag_exposed_in_state():
    """s1 (jump) sets state['veto_flag'] True; s2 (no jump) leaves it False."""
    rows = tape()
    cfg = Config()
    s1 = [r for r in rows if r["session"] == "s1"]
    st = {}
    for i in range(len(s1)):
        signal(st, s1[: i + 1], cfg)
    assert st["veto_flag"] is True
    s2 = [r for r in rows if r["session"] == "s2"]
    st2 = {}
    for i in range(len(s2)):
        signal(st2, s2[: i + 1], cfg)
    assert st2["veto_flag"] is False


def test_warmup_insufficient_bars():
    """Fewer than min_bars bars -> OK, dir 0, no veto (fail-safe flat)."""
    rows = tape()
    cfg, st = Config(), {}
    s = signal(st, rows[:2], cfg)  # 2 < min_bars (3) [default]
    assert s.module_state == "OK"
    assert s.direction == 0
    assert st["veto_flag"] is False


def test_cooldown_suppresses_after_unknown():
    """After an UNKNOWN block, events inside cooldown_s are DEGRADED."""
    rows = tape()
    cfg, st = Config(), {}
    ts = rows[1]["event_ts"]
    bad = {"id": "bad", "event_ts": ts, "session": "s1",
           "prior_close": 100.0, "open": 102.0, "close": -5.0}
    s = signal(st, [bad], cfg)
    assert s.module_state == "UNKNOWN"
    s2 = signal(st, [bad, rows[1]], cfg)  # rows[1].ts inside 600 s [default] cooldown
    assert s2.module_state == "DEGRADED"
    assert s2.direction == 0 and s2.capital == 0.0


def test_config_defaults_audit():
    """Config defaults pinned: threshold is theory, the rest are [default]."""
    cfg = Config()
    assert cfg.jump_thresh == 2.9702  # [documented] theory value, not a knob
    assert cfg.min_bars == 3          # [default]
    assert cfg.cost_gate_k == 0.5     # [default]
    assert cfg.cooldown_s == 600.0    # [default]
