"""Acceptance tests for S088 - Purged / embargoed cross-validation.

Template v1.0.0. Loads the fixture tape, runs a reference implementation of the
chapter's normative pseudocode (S3), and asserts causality, the cost gate, the
embargo hard rule, machine-readable regime behavior, and hand-checked arithmetic.

Run: python3 -m pytest modules/tests/test_S088.py -q   (from repo root)
"""
import csv
import math
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S088_tape.csv"
EXPECTED = FIX / "S088_expected.csv"

TOL = 1e-9  # [default]

# Reference config mirrors S0.2. embargo_n = 5 satisfies the hard rule
# embargo_n >= max label horizon (5 days) [documented].
CFG = {
    "test_start": 41,          # [example] fixture fold: events 41..60
    "test_end": 60,            # [example]
    "horizon": 5,              # [example] label horizon in days
    "embargo_n": 5,            # [example] >= max horizon (hard rule)
    "k": 0.5,                  # [default] cost-gate multiplier
    "convention": "first-test-events",  # [documented] chapter convention
    "cooldown_s": 0,           # [default] batch validator: no re-arm delay
    "ttl_s": None,             # [default] None = batch; F4 staleness when set
}

# The S2 COST block, verbatim: the procedure executes no trades, holds no
# positions, and emits no orders, so every component is 0.0 [documented].
COST_BLOCK = {
    "spread_bps": 0.0,
    "fee_bps": 0.0,
    "borrow_bps": 0.0,     # borrow_bps_per_day = 0.0: no positions, no leverage
    "impact_bps": 0.0,
    "slippage_bps": 0.0,
}


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    # Callable cost model - mirrors the S2 COST block exactly [documented].
    return (COST_BLOCK["spread_bps"] + COST_BLOCK["fee_bps"]
            + COST_BLOCK["borrow_bps"] + COST_BLOCK["impact_bps"]
            + COST_BLOCK["slippage_bps"])


def cost_gate_passes(edge_bps, k, **cost_kwargs) -> bool:
    # Executable cost-gate predicate (template form):
    # expected_cost_bps(...) <= k * edge_bps
    return expected_cost_bps(**cost_kwargs) <= k * edge_bps


def apply_gate(raw_direction, edge_bps, cost_bps, k, locate_ok=True):
    # Gate veto path (S3/C2/C7): sub-threshold emissions and un-located
    # shorts become direction 0; the veto is logged downstream.
    if raw_direction == 0:
        return 0
    if not (cost_bps <= k * edge_bps):
        return 0
    if raw_direction == -1 and not locate_ok:
        return 0
    return raw_direction


def validate_cfg(cfg, max_horizon):
    # Embargo hard rule (S2 FLOOR): L_E >= max label horizon [documented].
    # A shorter embargo leaks by construction -> the run must abort.
    if cfg["embargo_n"] < max_horizon:
        raise ValueError(
            "embargo_n=%s < max_horizon=%s: leaks by construction"
            % (cfg["embargo_n"], max_horizon))
    if cfg["convention"] not in ("first-test-events", "after-test-fold"):
        raise ValueError("unknown embargo convention: %r" % cfg["convention"])


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def init_state():
    return {"n_train": 0, "n_test": 0, "n_removed": 0,
            "frozen": False, "last_block_ns": None}


def step(state, row, cfg, now_ns=None):
    """One event through the S3 normative pseudocode. Returns (signal, state)."""
    ts = row.get("event_ts")
    i = row.get("ev")
    t0 = row.get("t0_day")
    t1 = row.get("t1_day")
    market = row.get("market_state", "CONTINUOUS_TRADING")
    out = {"computed_at": ts, "signal_event_ts": ts, "fill_event_ts": None,
           "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0, "cost_bps": 0.0,
           "status": "INVALID", "is_train": 0, "is_purged": 0,
           "is_embargoed": 0, "is_test": 0,
           "train_n": 0, "test_n": 0, "removed_n": 0}
    # F1: invalid input -> UNKNOWN; never interpolate.
    if _bad(ts) or i is None or _bad(t0) or _bad(t1) or t1 < t0:
        state["last_block_ns"] = now_ns
        return out, state
    out["fill_event_ts"] = ts + 1  # ts is a valid int from here on
    # S0.5 market-state guards: halt -> freeze (UNKNOWN); auction -> hold (DEGRADED).
    if market == "HALTED":
        state["frozen"] = True
        state["last_block_ns"] = now_ns
        return out, state
    if market == "AUCTION":
        out["module_state"] = "DEGRADED"
        out["status"] = "HELD"
        return out, state
    if state.get("frozen"):
        return out, state  # UNKNOWN until reopened
    # F4 staleness: TTL exceeded -> UNKNOWN.
    ttl_s = cfg.get("ttl_s")
    if now_ns is not None and ttl_s is not None and (now_ns - ts) > ttl_s * 1_000_000_000:
        return out, state
    # C10 post-exit cooldown: no re-entry while the block is fresh.
    last_block = state.get("last_block_ns")
    if (last_block is not None and now_ns is not None
            and (now_ns - last_block) < cfg["cooldown_s"] * 1_000_000_000):
        return out, state
    out["module_state"] = "OK"
    Ta = cfg["test_start"]
    Tb = cfg["test_end"] + cfg["horizon"]  # full test-fold interval [T_a, T_b]
    n = cfg["embargo_n"]
    in_fold = cfg["test_start"] <= i <= cfg["test_end"]
    if cfg["convention"] == "first-test-events":
        embargoed = in_fold and i < cfg["test_start"] + n
    else:  # "after-test-fold" (AFML 7.2): train rows just after the test fold
        embargoed = (not in_fold) and (cfg["test_end"] < t0 <= cfg["test_end"] + n)
    if embargoed:
        out["status"] = "EMBARGOED"
        out["is_embargoed"] = 1
        state["n_removed"] += 1
    elif in_fold:
        out["status"] = "TEST"
        out["is_test"] = 1
        state["n_test"] += 1
    elif t0 <= Tb and t1 >= Ta:  # purge: label interval touches the fold
        out["status"] = "PURGED"
        out["is_purged"] = 1
        state["n_removed"] += 1
    else:
        out["status"] = "TRAIN"
        out["is_train"] = 1
        state["n_train"] += 1
    # Executable cost-gate predicate; vacuous by construction here (0 <= k*0).
    ck = dict(notional=0.0, adv_pct=0.0, venue="NONE", side="taker", urgency="n/a")
    out["cost_bps"] = expected_cost_bps(**ck)
    assert cost_gate_passes(out["edge_bps"], cfg["k"], **ck)
    # Causality: t -> t+1; no-signal-bar fills (mandatory).
    assert out["fill_event_ts"] > out["signal_event_ts"]
    return out, state


def blocked_folds(n, K):
    """Contiguous blocked folds on time-sorted events; NOT modulo interleaving."""
    base, rem = divmod(n, K)
    folds, start = [], 0
    for f in range(K):
        size = base + (1 if f < rem else 0)
        folds.append(list(range(start, start + size)))
        start += size
    return folds


def run(rows, cfg=None, now_ns=None):
    cfg = dict(CFG) if cfg is None else cfg
    max_horizon = 0
    for r in rows:
        t0, t1 = r.get("t0_day"), r.get("t1_day")
        if not _bad(t0) and not _bad(t1) and t1 >= t0:
            max_horizon = max(max_horizon, t1 - t0)
    validate_cfg(cfg, max_horizon)  # hard rule enforced before any computation
    st = init_state()
    out = []
    for r in rows:
        sig, st = step(st, r, cfg, now_ns=now_ns)
        out.append(sig)
    for sig in out:
        if sig["module_state"] == "OK":
            sig["train_n"] = st["n_train"]
            sig["test_n"] = st["n_test"]
            sig["removed_n"] = st["n_removed"]
    return out


def load_csv(path):
    with open(path) as f:
        lines = [ln for ln in f if not ln.startswith("#") and ln.strip()]
    return list(csv.DictReader(lines))


def _num(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        pass
    try:
        return float(v)
    except (ValueError, TypeError):
        return v


def tape():
    rows = []
    for r in load_csv(TAPE):
        rows.append({k: _num(v) for k, v in r.items()})
    return rows


def _close(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(b))
    return a == b


# ---------------------------------------------------------------- tests ---

def test_fixtures_exist_and_typed():
    assert TAPE.exists(), "tape fixture missing"
    assert EXPECTED.exists(), "expected fixture missing"
    for path in (TAPE, EXPECTED):
        with open(path) as f:
            head = [next(f) for _ in range(3)]
        assert any(l.startswith("# TYPE:") for l in head), f"{path.name} missing TYPE header"
    assert len(tape()) == 60, "tape must hold the 60-event schedule"


def test_expected_matches_reference():
    rows = tape()
    sigs = run(rows)
    exp = load_csv(EXPECTED)
    assert len(exp) == len(sigs), "expected row count != tape row count"
    cols = ["computed_at", "direction", "confidence", "capital", "module_state",
            "edge_bps", "cost_bps", "status", "is_train", "is_purged",
            "is_embargoed", "is_test", "train_n", "test_n", "removed_n"]
    for i, (s, e) in enumerate(zip(sigs, exp)):
        assert int(e["ev"]) == int(rows[i]["ev"]), "row %d ev mismatch" % i
        for c in cols:
            got, want = s[c], _num(e[c])
            assert _close(got, want), "row %d col %s: got %r want %r" % (i, c, got, want)


def test_hand_pins_and_counts():
    # Operator-verified pins (S4): purge = E_36..E_40, embargo = E_41..E_45.
    sigs = run(tape())
    by_ev = {int(r["ev"]): s for r, s in zip(tape(), sigs)}
    assert by_ev[35]["status"] == "TRAIN", "E_35 [35,40] must not be purged"
    assert by_ev[36]["status"] == "PURGED", "E_36 [36,41] touches fold start"
    assert by_ev[40]["status"] == "PURGED", "E_40 [40,45] overlaps the fold"
    assert by_ev[41]["status"] == "EMBARGOED", "first test event embargoed"
    assert by_ev[45]["status"] == "EMBARGOED", "last embargoed test event"
    assert by_ev[46]["status"] == "TEST", "first kept test event"
    assert by_ev[60]["status"] == "TEST", "last test event"
    train = sum(s["is_train"] for s in sigs)
    test = sum(s["is_test"] for s in sigs)
    removed = sum(s["is_purged"] + s["is_embargoed"] for s in sigs)
    assert (train, test, removed) == (35, 15, 10), (train, test, removed)
    assert train + test + removed == 60
    assert sigs[0]["train_n"] == 35 and sigs[0]["test_n"] == 15 and sigs[0]["removed_n"] == 10


def test_embargo_floor_hard_rule():
    # Machine check of the S2 FLOOR rule: embargo must cover the label horizon.
    rows = tape()
    horizon = max(r["t1_day"] - r["t0_day"] for r in rows)
    assert CFG["embargo_n"] >= horizon, "fixture embargo violates the hard rule"
    validate_cfg(CFG, horizon)  # passes
    # Regression: the pre-review fixture used embargo_n=3 < horizon=5 (leaked
    # by construction). That config must now abort the run, not silently leak.
    bad = dict(CFG, embargo_n=3)
    try:
        run(rows, cfg=bad)
    except ValueError:
        return
    raise AssertionError("embargo_n < max horizon must abort, not leak")


def test_embargo_convention_sides():
    # The boundary side matters: chapter convention vs AFML 7.2 (after the fold).
    base = 1788912000000000000
    rows = [{"ev": i, "event_ts": base + (i - 1) * 86400000000000,
             "t0_day": i, "t1_day": i + 5} for i in range(1, 13)]
    cfg = dict(CFG, test_start=7, test_end=10, horizon=5, embargo_n=5)
    chapter = run(rows, cfg=dict(cfg, convention="first-test-events"))
    assert [s["status"] for s in chapter][6:10] == ["EMBARGOED"] * 4
    counts = {k: sum(s["is_" + k] for s in chapter) for k in ("train", "test")}
    counts["removed"] = sum(s["is_purged"] + s["is_embargoed"] for s in chapter)
    assert (counts["train"], counts["test"], counts["removed"]) == (1, 0, 11), counts
    afml = run(rows, cfg=dict(cfg, convention="after-test-fold"))
    emb = [i for i, s in enumerate(afml) if s["status"] == "EMBARGOED"]
    assert emb == [10, 11], "AFML 7.2 embargoes train rows just after the fold, got %r" % emb
    assert [s["status"] for s in afml][6:10] == ["TEST"] * 4


def test_signal_vector_valid():
    for s in run(tape()):
        assert s["direction"] in (+1, -1, 0), "direction not in {+1,-1,0}"
        assert 0.0 <= s["confidence"] <= 1.0, "confidence out of [0,1]"
        assert 0.0 <= s["capital"] <= 0.5, "capital out of [0,0.5]"
        assert s["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()):
        assert s["fill_event_ts"] > s["signal_event_ts"]
        assert s["computed_at"] == s["signal_event_ts"]


def test_cost_gate():
    # Normative predicate: expected_cost_bps(...) <= k * edge_bps.
    k = CFG["k"]  # 0.5 [default]
    kw = dict(notional=1e6, adv_pct=0.01, venue="XNAS", side="taker", urgency="normal")
    c = expected_cost_bps(**kw)
    assert c == 0.0, "procedure executes no trades; cost must be exactly 0"
    assert cost_gate_passes(0.0, k, **kw), "0 <= 0.5 * 0 is the vacuous infra pass"
    # Callable mirrors the S2 block exactly: 4-component (+slippage) sum.
    assert c == sum(COST_BLOCK.values())


def test_cost_gate_veto_path():
    # A sub-threshold raw emission is forced to direction 0 (C2); an
    # un-located short is forced to 0 (C7); a passing gate keeps the side.
    assert apply_gate(1, edge_bps=0.0, cost_bps=1.0, k=0.5) == 0
    assert apply_gate(-1, edge_bps=100.0, cost_bps=1.0, k=0.5, locate_ok=False) == 0
    assert apply_gate(1, edge_bps=100.0, cost_bps=1.0, k=0.5) == 1
    assert apply_gate(0, edge_bps=0.0, cost_bps=1.0, k=0.5) == 0


def test_invalid_input_unknown():
    st = init_state()
    bad_rows = [
        {"ev": 1, "event_ts": float("nan"), "t0_day": 1, "t1_day": 6},
        {"ev": 1, "event_ts": 1788912000000000000, "t0_day": float("nan"), "t1_day": 6},
        {"ev": 1, "event_ts": 1788912000000000000, "t0_day": 1, "t1_day": float("nan")},
        {"ev": 1, "event_ts": 1788912000000000000, "t0_day": 6, "t1_day": 1},  # t1 < t0
        {"ev": 1, "event_ts": 1788912000000000000},                            # missing t0/t1
        {"ev": None, "event_ts": 1788912000000000000, "t0_day": 1, "t1_day": 6},
    ]
    for bad in bad_rows:
        sig, _ = step(init_state(), bad, CFG)
        assert sig["module_state"] == "UNKNOWN", "invalid input must be UNKNOWN, got %r" % sig
        assert sig["status"] == "INVALID", "invalid input status must be INVALID"
    # Empty event list -> no signals at all, no crash.
    assert run([]) == []


def test_boundary_zero_horizon():
    # t1 == t0 (single-bar label) is valid and classifiable; nothing may crash.
    row = {"ev": 1, "event_ts": 1788912000000000000, "t0_day": 1, "t1_day": 1}
    sig, _ = step(init_state(), row, CFG)
    assert sig["module_state"] == "OK"
    assert sig["status"] == "TRAIN", "single-bar label before the fold is TRAIN"


def test_market_state_guards():
    row = {"ev": 1, "event_ts": 1788912000000000000, "t0_day": 1, "t1_day": 6}
    sig, st = step(init_state(), dict(row, market_state="HALTED"), CFG)
    assert sig["module_state"] == "UNKNOWN" and st["frozen"], "halt must freeze"
    sig2, _ = step(st, row, CFG)
    assert sig2["module_state"] == "UNKNOWN", "frozen state stays UNKNOWN"
    sig3, _ = step(init_state(), dict(row, market_state="AUCTION"), CFG)
    assert sig3["module_state"] == "DEGRADED" and sig3["status"] == "HELD"


def test_staleness_unknown():
    # F4: event older than the staleness TTL -> UNKNOWN, never interpolated.
    cfg = dict(CFG, ttl_s=86400)  # 1 day [default]
    ts = 1788912000000000000
    row = {"ev": 1, "event_ts": ts, "t0_day": 1, "t1_day": 6}
    fresh, _ = step(init_state(), row, cfg, now_ns=ts)
    assert fresh["module_state"] == "OK"
    stale, _ = step(init_state(), row, cfg, now_ns=ts + 2 * 86400000000000)
    assert stale["module_state"] == "UNKNOWN", "stale input must be UNKNOWN"


def test_blocked_folds_contiguous():
    # Chapter requires blocked (contiguous) folds, NOT modulo interleaving.
    folds = blocked_folds(60, 5)
    assert folds[0] == list(range(12)), "first fold must be events 0..11"
    assert all(len(f) == 12 for f in folds)
    modulo_first = [i for i in range(60) if i % 5 == 0]
    assert folds[0] != modulo_first, "modulo interleaving is forbidden"
