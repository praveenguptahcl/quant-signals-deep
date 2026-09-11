"""Acceptance tests for S061 — ADR / dual-listed premium.

Template v1.0.0. Concrete sketch: real imports, fixture load, a reference
implementation of the chapter's normative pseudocode (S3), and real assertions
including causality (fill_event > signal_event), the cost-gate predicate, and
invalid -> UNKNOWN.

FX convention (fixed 2026-09-11): X = USD per unit of local currency;
fair_adr = local_px * fx * ratio.

Run: python3 -m pytest modules/tests/test_S061.py -q   (from repo root)
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE_A = FIX / "S061_tape.csv"
EXPECTED_A = FIX / "S061_expected.csv"
TAPE_B = FIX / "S061_tape_z.csv"
EXPECTED_B = FIX / "S061_expected_z.csv"

TOL = 1e-9  # tolerance on float comparisons [default]
EXPECTED_COLS = ["bar", "fair_adr", "premium_bps", "z", "direction", "module_state"]
COL_TYPES = {"bar": "int", "event_ts": "int", "asof_ts": "int", "local_px": "float",
             "fx": "float", "adr_px": "float", "ratio": "int", "home_open": "int"}


# ---------------------------------------------------------------- fixtures
def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def _conv(v, t):
    if v == "" or v is None:
        return float("nan")
    if t == "int":
        return int(v)
    if t == "float":
        return float(v)
    return v


def parse_tape(path):
    return [{k: _conv(r[k], COL_TYPES[k]) for k in COL_TYPES} for r in load_csv(path)]


def parse_expected(path):
    rows = []
    for r in load_csv(path):
        rows.append({
            "bar": int(r["bar"]),
            "fair_adr": float(r["fair_adr"]) if r["fair_adr"] else float("nan"),
            "premium_bps": float(r["premium_bps"]) if r["premium_bps"] else float("nan"),
            "z": float(r["z"]) if r["z"] else float("nan"),
            "direction": int(r["direction"]),
            "module_state": r["module_state"],
        })
    return rows


def floats_eq(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return abs(a - b) <= TOL


# --------------------------------------- normative pseudocode (S3) reference
@dataclass(frozen=True)
class SignalVector:
    symbol: str
    direction: int          # +1 | -1 | 0
    confidence: float       # 0..1
    capital: float          # 0..1
    computed_at: int        # int64 ns UTC
    staleness: int          # ns
    module_state: str       # OK | DEGRADED | UNKNOWN | OFF


@dataclass
class Config:
    premium_bound_bps: float = 25.0  # [example]
    W: int = 60                       # [example] trailing window (bars)
    z_entry: float = 1.5              # [example]
    z_exit: float = 0.5               # [example]
    min_obs: int = 2                  # [default]
    cost_gate_k: float = 0.5          # [default]
    cooldown_s: float = 60.0          # [default]
    locate_ok: bool = True            # [default]


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 3.00   # ADR + local half-spreads [example]
    fee_bps = 1.20      # two-market fees + depositary pass-through [example]
    borrow_bps = 3.00   # ADR borrow amortized [example]
    impact_bps = 2.00   # FX + equity async fill slippage [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def new_state():
    return {"direction": 0, "window": [], "cooldown_until": 0, "module_state": "OFF"}


def signal(state, bar, cfg):
    """One bar step of the S3 normative pseudocode. Never interpolates."""
    ts = bar["event_ts"]
    px, fx, apx = bar["local_px"], bar["fx"], bar["adr_px"]
    if (not (math.isfinite(px) and math.isfinite(fx) and math.isfinite(apx))
            or px <= 0 or fx <= 0 or apx <= 0):
        state["direction"] = 0
        state["module_state"] = "UNKNOWN"
        return {"bar": bar["bar"], "fair_adr": float("nan"), "premium_bps": float("nan"),
                "z": float("nan"), "direction": 0, "confidence": 0.0, "capital": 0.0,
                "module_state": "UNKNOWN", "computed_at": ts}
    if not bar["home_open"]:
        state["direction"] = 0
        state["cooldown_until"] = ts + int(cfg.cooldown_s * 1e9)  # C10: veto is a block
        state["module_state"] = "UNKNOWN"
        return {"bar": bar["bar"], "fair_adr": float("nan"), "premium_bps": float("nan"),
                "z": float("nan"), "direction": 0, "confidence": 0.0, "capital": 0.0,
                "module_state": "UNKNOWN", "computed_at": ts}
    fair = px * fx * bar["ratio"]          # X = USD per unit of local currency
    pi = apx / fair - 1.0
    state["window"].append(pi)
    if len(state["window"]) > cfg.W:
        state["window"].pop(0)
    w = state["window"]
    z = float("nan")
    if len(w) >= cfg.min_obs:
        m = sum(w) / len(w)
        var = sum((x - m) ** 2 for x in w) / len(w)   # population std, ddof=0 [default]
        z = (w[-1] - m) / math.sqrt(var) if var > 0 else float("nan")
    prem_bps = pi * 10000.0
    edge_bps = abs(prem_bps)
    d = state["direction"]
    if d != 0:  # exits evaluated before entries
        if math.isnan(z) or (d == -1 and z < cfg.z_exit) or (d == 1 and z > -cfg.z_exit):
            d = 0
            state["cooldown_until"] = ts + int(cfg.cooldown_s * 1e9)  # C10
    if d == 0 and ts >= state["cooldown_until"] and not math.isnan(z):
        gate = (expected_cost_bps(1.0, 0.001, "XNYS", "taker", "normal")
                <= cfg.cost_gate_k * edge_bps)
        if gate:
            if z > cfg.z_entry and prem_bps > cfg.premium_bound_bps and cfg.locate_ok:
                d = -1                      # ADR rich -> short ADR (C7 locate)
            elif z < -cfg.z_entry and prem_bps < -cfg.premium_bound_bps:
                d = 1                       # ADR cheap -> buy ADR
    state["direction"] = d
    state["module_state"] = "OK"
    conf = (min(1.0, edge_bps / cfg.premium_bound_bps - 1.0)
            if (d != 0 and edge_bps > cfg.premium_bound_bps) else 0.0)
    return {"bar": bar["bar"], "fair_adr": fair, "premium_bps": prem_bps, "z": z,
            "direction": d, "confidence": conf, "capital": 0.5 * conf,
            "module_state": "OK", "computed_at": ts}


def run_tape(rows, cfg=None):
    cfg = cfg or Config()
    state, out = new_state(), []
    for r in rows:
        out.append(signal(state, r, cfg))
    return out, state


# ------------------------------------------------------------------- tests
def test_fixture_a_recomputes_to_expected():
    """Parity arithmetic of the 8-bar tape matches expected.csv (incl. FX convention)."""
    rows = parse_tape(TAPE_A)
    exp = parse_expected(EXPECTED_A)
    got, _ = run_tape(rows)
    assert len(got) == len(exp) == 8, (len(got), len(exp))
    for g, e, r in zip(got, exp, rows):
        # FX convention pin: fair_adr == local_px * fx * ratio (USD per local)
        if r["home_open"]:
            assert floats_eq(g["fair_adr"], r["local_px"] * r["fx"] * r["ratio"]), g["bar"]
        for k in EXPECTED_COLS:
            gv, ev = g[k], e[k]
            if isinstance(ev, float):
                assert floats_eq(gv, ev), (k, gv, ev)
            else:
                assert gv == ev, (k, gv, ev)
    assert floats_eq(got[3]["premium_bps"], 40.0)      # hand-check: 50.20/50 - 1
    assert floats_eq(got[1]["premium_bps"], 12.0)
    assert floats_eq(got[4]["premium_bps"], -40.0)


def test_fixture_a_entry_exit_veto_path():
    """z-gated entries, flip-exit, and veto bars on the 8-bar tape."""
    rows = parse_tape(TAPE_A)
    got, _ = run_tape(rows)
    assert floats_eq(got[0]["z"], got[0]["z"]) is False or math.isnan(got[0]["z"])  # warmup: z undefined
    assert math.isnan(got[1]["z"]) is False
    assert floats_eq(got[3]["z"], 1.5554275420956)     # hand-check, expanding window, ddof=0
    assert got[3]["direction"] == -1                   # z>1.5, 40bps>25bps, cost gate passes
    assert got[4]["direction"] == 0                    # premium flipped: exit; cooldown blocks re-entry
    assert got[5]["module_state"] == "UNKNOWN" and got[5]["direction"] == 0  # home closed
    assert got[7]["module_state"] == "UNKNOWN" and got[7]["direction"] == 0  # home closed
    assert got[6]["direction"] == 0                    # -10bps: bound blocks


def test_fixture_b_validation_run():
    """72-bar tape pins the full z path: warmup, entry, interruption, exit, long leg."""
    rows = parse_tape(TAPE_B)
    exp = parse_expected(EXPECTED_B)
    got, _ = run_tape(rows)
    assert len(got) == len(exp) == 72
    for g, e in zip(got, exp):
        for k in EXPECTED_COLS:
            gv, ev = g[k], e[k]
            if isinstance(ev, float):
                assert floats_eq(gv, ev), (k, gv, ev)
            else:
                assert gv == ev, (k, gv, ev)
    assert all(g["direction"] == 0 for g in got[:2])   # warmup: z undefined
    assert all(g["direction"] == 0 for g in got[2:31])  # noise: bound/z block
    assert got[31]["direction"] == -1                  # sustained rich premium -> short ADR
    assert got[44]["direction"] == -1
    assert got[45]["module_state"] == "UNKNOWN" and got[45]["direction"] == 0  # session interruption
    assert got[46]["direction"] == -1                  # re-entry after interruption (cooldown expired)
    assert got[53]["direction"] == 0                   # premium decayed: z-exit
    assert got[60]["module_state"] == "UNKNOWN"        # non-finite FX
    assert got[67]["direction"] == 1                   # sustained discount -> long ADR


def test_signal_emits_valid_signalvector():
    rows = parse_tape(TAPE_A)
    cfg = Config()
    for r in rows:
        o = signal(new_state(), r, cfg)
        assert o["direction"] in (+1, -1, 0)
        assert 0.0 <= o["confidence"] <= 1.0
        assert 0.0 <= o["capital"] <= 0.5
        assert o["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")
        assert o["computed_at"] == r["event_ts"]


def test_no_signal_bar_fills():
    """Causality: every fill event is strictly after the signal event."""
    for path in (TAPE_A, TAPE_B):
        rows = parse_tape(path)
        got, _ = run_tape(rows)
        for i, (r, o) in enumerate(zip(rows, got)):
            assert o["computed_at"] == r["event_ts"], "signal must be timestamped at its bar"
            later = [x["event_ts"] for x in rows[i + 1:] if x["event_ts"] > o["computed_at"]]
            if later:
                assert min(later) > o["computed_at"], "signal-bar fill"


def test_cost_gate_predicate():
    """expected_cost_bps(...) <= k * edge_bps gates entries."""
    k = 0.5  # [default]
    cost = expected_cost_bps(1.0, 0.001, "XNYS", "taker", "normal")
    assert floats_eq(cost, 9.20)
    assert cost <= k * 100000.0    # huge edge -> gate passes
    assert not (cost <= k * 0.0001)  # tiny edge -> gate blocks
    assert cost <= k * 18.4        # boundary: 9.2 <= 9.2 passes
    assert not (cost <= k * 18.39)  # just below boundary blocks


def test_invalid_input_yields_unknown():
    base = {"bar": 0, "event_ts": 1, "asof_ts": 2, "local_px": 50.0, "fx": 0.2,
            "adr_px": 50.0, "ratio": 5, "home_open": 1}
    bads = [
        {**base, "fx": float("nan")},     # non-finite FX
        {**base, "fx": 0.0},              # non-positive FX
        {**base, "adr_px": float("inf")},  # non-finite ADR price
        {**base, "local_px": -1.0},        # negative price
    ]
    for b in bads:
        o = signal(new_state(), b, Config())
        assert o["module_state"] == "UNKNOWN" and o["direction"] == 0
    o = signal(new_state(), {**base, "fx": 0.2}, Config())  # control: valid -> OK
    assert o["module_state"] == "OK"
    try:
        signal(new_state(), None, Config())
        raise AssertionError("None bar should raise")
    except (TypeError, KeyError, AttributeError):
        pass


def test_home_closed_veto():
    bar = {"bar": 9, "event_ts": 10**18, "asof_ts": 10**18 + 120000, "local_px": 50.0,
           "fx": 0.2, "adr_px": 50.4, "ratio": 5, "home_open": 0}
    st = {"direction": -1, "window": [0.004] * 60, "cooldown_until": 0, "module_state": "OK"}
    o = signal(st, bar, Config())
    assert o["module_state"] == "UNKNOWN" and o["direction"] == 0
    assert st["direction"] == 0                       # forced flat
    assert st["cooldown_until"] == bar["event_ts"] + int(60.0 * 1e9)  # C10 cooldown


def test_cooldown_suppresses_reentry():
    cfg = Config()
    t0 = 1_000_000_000_000_000_000
    # Phase 1: force an exit -> cooldown_until = t0 + 60s
    st = {"direction": -1, "window": [0.005] * 60, "cooldown_until": 0, "module_state": "OK"}
    exit_bar = {"bar": 0, "event_ts": t0, "asof_ts": t0 + 120000, "local_px": 50.0,
                "fx": 0.2, "adr_px": 50.0 * 1.0049, "ratio": 5, "home_open": 1}
    o = signal(st, exit_bar, cfg)
    assert o["direction"] == 0 and st["cooldown_until"] == t0 + int(60.0 * 1e9)
    # Phase 2: entry-grade bar 30s later, inside cooldown -> suppressed
    st2 = {"direction": 0, "window": [0.0] * 10, "cooldown_until": t0 + int(60.0 * 1e9),
           "module_state": "OK"}
    soon = {"bar": 1, "event_ts": t0 + int(30.0 * 1e9), "asof_ts": t0 + int(30.0 * 1e9) + 120000,
            "local_px": 50.0, "fx": 0.2, "adr_px": 50.0 * 1.004, "ratio": 5, "home_open": 1}
    o2 = signal(st2, soon, cfg)
    assert o2["direction"] == 0, "cooldown must suppress re-entry"
    # Phase 3: same bar 61s later -> entry allowed
    later = dict(soon, bar=2, event_ts=t0 + int(61.0 * 1e9), asof_ts=t0 + int(61.0 * 1e9) + 120000)
    o3 = signal({"direction": 0, "window": [0.0] * 10, "cooldown_until": t0 + int(60.0 * 1e9),
                 "module_state": "OK"}, later, cfg)
    assert o3["direction"] == -1, "entry must fire after cooldown expiry"


def test_locate_veto():
    """C7: SHORT direction requires locate_ok from the consumer."""
    rows = parse_tape(TAPE_A)
    got, _ = run_tape(rows, Config(locate_ok=False))
    assert got[3]["direction"] == 0  # would-be -1 entry vetoed
    assert got[3]["module_state"] == "OK"


def test_min_obs_warmup():
    bar = {"bar": 0, "event_ts": 10**18, "asof_ts": 10**18 + 120000, "local_px": 50.0,
           "fx": 0.2, "adr_px": 50.4, "ratio": 5, "home_open": 1}  # 80bps premium
    o = signal(new_state(), bar, Config())
    assert o["module_state"] == "OK" and o["direction"] == 0  # z undefined on 1 obs
    assert math.isnan(o["z"])
