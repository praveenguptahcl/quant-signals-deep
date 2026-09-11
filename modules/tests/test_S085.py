"""Acceptance tests for S085 — Triple-barrier labeling (v1.1.0).

Template v1.0.0. Two layers:
  1. Fixture acceptance: loads the 20-day tape, runs the tape reference
     implementation, and asserts causality, the cost gate, and hand-checked
     arithmetic against modules/fixtures/S085_expected.csv.
  2. Normative-core unit tests: label_px() mirrors the §S3 normative
     pseudocode (all guards bound) — boundary touches, tie-break, vertical
     fallback, invalid input -> UNKNOWN, locate/cooldown/staleness/halt
     guards, gate veto paths, and causality/leakage pins.

Run: python3 -m pytest modules/tests/test_S085.py -q   (from repo root)
"""
import csv
import math
import re
from pathlib import Path

import yaml  # pyyaml; regime-gate machine-record validation

FIX = Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S085_tape.csv"
EXPECTED = FIX / "S085_expected.csv"
MODULE_MD = Path(__file__).resolve().parent.parent / "signals" / "S085.md"

TOL = 1e-9  # tolerance on float comparisons [default]


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
        d = {}
        for k, v in r.items():
            d[k] = _num(v)
        rows.append(d)
    return rows


CFG = {"event_day": 15, "side": 1, "k_u": 1.0, "k_l": 1.0,
       "sig_cfg": 1.0,      # vol-scale reproducing the chapter's stated +-1.0pt barriers [example]
       "sig_hat": 1.2978,   # chapter vol estimate sqrt(32/19) [documented]
       "H": 5}              # horizon in days [example]
DAY = 86400000000000


def expected_cost_bps(notional, adv_pct, venue, side, urgency) -> float:
    # Mirrors the §S2 COST block exactly: labeling executes no trades. [documented]
    spread_bps = 0.0
    fee_bps = 0.0
    borrow_bps = 0.0   # borrow_bps_per_day = 0.00; no positions taken [documented]
    impact_bps = 0.0
    return spread_bps + fee_bps + borrow_bps + impact_bps


def cost_gate_passes(cost_bps, edge_bps, k):
    # Executable predicate: expected_cost_bps(...) <= k * edge_bps
    if edge_bps is None:
        return True  # gate not applicable; C2 still forces direction 0 on sub-threshold
    return cost_bps <= k * edge_bps


def init_state():
    return {"entry": None, "label": "", "exit_day": "", "status": "pre_event"}


def _bad(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def step(state, row, cfg):
    ts = row.get("event_ts"); day = row.get("day"); sp = row.get("spread")
    out = {"computed_at": ts, "direction": 0, "confidence": 0.0, "capital": 0.0,
           "module_state": "UNKNOWN", "edge_bps": 0.0, "cost_bps": 0.0,
           "z": float("nan"), "is_event": 0, "r_s": "", "barrier_status": state["status"],
           "label": state["label"], "exit_day": state["exit_day"],
           "fill_event_ts": ts + DAY if isinstance(ts, int) else None}
    if ts is None or day is None or _bad(sp):
        return out, state  # invalid input -> UNKNOWN; never interpolate
    out["module_state"] = "OK"
    out["z"] = sp / cfg["sig_hat"]
    if day == cfg["event_day"]:
        state["entry"] = sp; state["status"] = "entry"
        out["is_event"] = 1; out["r_s"] = 0.0; out["barrier_status"] = "entry"
        return out, state
    if state["entry"] is None:
        return out, state  # pre-event rows: no label yet
    rs = cfg["side"] * (sp - state["entry"])
    out["r_s"] = rs
    if state["label"] == "":
        if rs >= cfg["k_u"] * cfg["sig_cfg"]:
            state["label"] = 1
            state["exit_day"] = day; state["status"] = "profit_hit"
        elif rs <= -cfg["k_l"] * cfg["sig_cfg"]:
            state["label"] = -1
            state["exit_day"] = day; state["status"] = "stop_hit"
        elif day >= cfg["event_day"] + cfg["H"]:
            state["label"] = 0
            state["exit_day"] = day; state["status"] = "vertical"
        else:
            state["status"] = "pending"
    elif state["status"] in ("profit_hit", "stop_hit", "vertical"):
        state["status"] = "decided"
    out["barrier_status"] = state["status"]
    out["label"] = state["label"]
    out["exit_day"] = state["exit_day"]
    return out, state


def run(rows):
    st = init_state(); out = []
    for r in rows:
        sig, st = step(st, r, CFG)
        out.append(sig)
    return out


# ---------------------------------------------------------------------------
# Normative core: mirrors the §S3 normative pseudocode (all variables bound).
# ---------------------------------------------------------------------------

def estimate_sigma(changes, L):
    """Sample std (ddof=1) of the last L pre-event changes.

    `changes` must contain data strictly before t_0; anything at/after t_0
    is a §S10-mode-1 leak. Raises ValueError on degenerate input (→ UNKNOWN).
    """
    w = list(changes[-L:])
    if len(w) < 2:
        raise ValueError("insufficient pre-event history")
    if any(not math.isfinite(x) for x in w):
        raise ValueError("non-finite change in vol window")
    mu = sum(w) / len(w)
    sig = math.sqrt(sum((x - mu) ** 2 for x in w) / (len(w) - 1))
    if not (math.isfinite(sig) and sig > 0):
        raise ValueError("degenerate vol")
    return sig


def label_px(px, hi, lo, ts, asof_ns, t0, side, ku, kl, sig, H,
             tie_rule="adverse_first", locate_ok=True, now_ns=0,
             last_block_ns=-10**18, cooldown_ns=300_000_000_000,
             ttl_ns=3_000_000_000, market_state="CONTINUOUS_TRADING"):
    """Normative §S3 procedure. Returns (label, tau, status); label None → UNKNOWN/DEGRADED."""
    # --- guards: locate / cooldown / staleness / halt ---
    if market_state in ("HALTED", "CLOSED"):
        return (None, None, "UNKNOWN")
    if market_state == "AUCTION":
        return (None, None, "DEGRADED")
    if side not in (1, -1):
        return (None, None, "UNKNOWN")
    if side == -1 and not locate_ok:
        return (None, None, "UNKNOWN")          # C7 locate gate
    if (now_ns - last_block_ns) < cooldown_ns:
        return (None, None, "UNKNOWN")          # C10 post-block cooldown
    if (asof_ns - ts[t0]) > ttl_ns:
        return (None, None, "UNKNOWN")          # F4 staleness TTL
    if not (math.isfinite(px[t0]) and px[t0] > 0):
        return (None, None, "UNKNOWN")          # F1 invalid price
    if t0 + H >= len(px):
        return (None, None, "UNKNOWN")          # path shorter than horizon
    for i in range(1, H + 1):
        if not (math.isfinite(px[t0 + i]) and px[t0 + i] > 0):
            return (None, None, "UNKNOWN")
        assert ts[t0 + i] > ts[t0 + i - 1], "non-monotonic event time"
    # --- barriers (additive spread form) ---
    profit_px = px[t0] + side * ku * sig
    stop_px = px[t0] - side * kl * sig
    for tau in range(1, H + 1):
        if side == 1:
            profit_hit = hi[t0 + tau] >= profit_px
            stop_hit = lo[t0 + tau] <= stop_px
        else:  # side == -1: short profits when the path falls
            profit_hit = lo[t0 + tau] <= profit_px
            stop_hit = hi[t0 + tau] >= stop_px
        if profit_hit and stop_hit:
            assert tie_rule == "adverse_first", "tie rule must be configured"
            return (-1, tau, "tie_adverse_first")
        if profit_hit:
            return (1, tau, "profit_hit")
        if stop_hit:
            return (-1, tau, "stop_hit")
    return (0, H, "vertical")                   # vertical barrier -> 0 [documented]


def _synth_path(px_list, start_ts=1_700_000_000_000_000_000, step_ns=DAY):
    ts = [start_ts + i * step_ns for i in range(len(px_list))]
    return list(px_list), list(px_list), list(px_list), ts


def _guard_kwargs(**over):
    kw = dict(tie_rule="adverse_first", locate_ok=True, now_ns=10**18,
              last_block_ns=0, cooldown_ns=300_000_000_000,
              ttl_ns=3_000_000_000, market_state="CONTINUOUS_TRADING")
    kw.update(over)
    return kw


# ---------------------------------------------------------------------------
# Fixture acceptance tests
# ---------------------------------------------------------------------------

def _close(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(b))
    return a == b


def test_fixtures_exist_and_typed():
    assert TAPE.exists(), "tape fixture missing"
    assert EXPECTED.exists(), "expected fixture missing"
    with open(TAPE) as f:
        head = [next(f) for _ in range(3)]
    assert any(l.startswith("# TYPE:") for l in head), "tape missing TYPE header"
    with open(EXPECTED) as f:
        head = [next(f) for _ in range(3)]
    assert any(l.startswith("# TYPE:") for l in head), "expected missing TYPE header"
    rows = tape()
    assert len(rows) >= 5, "fixture needs >=5 hand-checkable rows"


def test_expected_matches_reference():
    rows = tape()
    sigs = run(rows)
    exp = load_csv(EXPECTED)
    assert len(exp) == len(sigs), "expected row count != tape row count"
    cols = ["computed_at", "direction", "confidence", "capital", "module_state", "edge_bps", "cost_bps", "z", "is_event", "r_s", "barrier_status", "label", "exit_day"]
    for i, (s, e) in enumerate(zip(sigs, exp)):
        assert int(e["ev"]) == int(rows[i]["ev"]), f"row {i} ev mismatch"
        for c in cols:
            got = s[c]
            want = _num(e[c])
            assert _close(got, want), f"row {i} col {c}: got {got} want {want}"


def test_signal_vector_valid():
    for s in run(tape()):
        assert s["direction"] in (+1, -1, 0), "direction not in {+1,-1,0}"
        assert 0.0 <= s["confidence"] <= 1.0, "confidence out of [0,1]"
        assert 0.0 <= s["capital"] <= 0.5, "capital out of [0,0.5]"
        assert s["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_no_signal_bar_fills():
    # t -> t+1 causality: no fill may occur on or before its signal event.
    for s in run(tape()):
        fill_event = s["fill_event_ts"]
        signal_event = s["computed_at"]
        if fill_event is not None:
            assert fill_event > signal_event


def test_cost_gate():
    # Normative predicate with the canonical signature:
    #   expected_cost_bps(notional, adv_pct, venue, side, urgency) <= k * edge_bps
    k = 0.5  # [default]
    c = expected_cost_bps(notional=1e6, adv_pct=0.01, venue="XNAS",
                          side="taker", urgency="normal")
    assert c == 0.0, "labeling executes no trades; all four components are 0 [documented]"
    # Vacuous pass for the infrastructure module: 0 <= k * edge for any edge >= 0.
    assert cost_gate_passes(c, 0.0, k)
    assert cost_gate_passes(c, None, k), "gate not applicable when edge is absent"
    # Veto path exercised with a hypothetical non-zero cost (gate must block):
    assert not cost_gate_passes(10.0, 5.0, k), "cost 10bps > k*edge 2.5bps must veto"
    # Pass path:
    assert cost_gate_passes(1.0, 5.0, k), "cost 1bps <= k*edge 2.5bps must pass"


def test_invalid_input_unknown():
    rows = tape()
    bad = dict(rows[0])
    bad.update({'spread': float('nan')})
    st = init_state()
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "invalid input must map to UNKNOWN, never interpolate"


def test_missing_timestamp_unknown():
    rows = tape()
    bad = dict(rows[3])
    bad.update({'event_ts': None})
    st = init_state()
    for r in rows[:3]:
        _, st = step(st, r, CFG)
    sig, _ = step(st, bad, CFG)
    assert sig["module_state"] == "UNKNOWN", "missing event_ts must map to UNKNOWN"


def test_label_not_known_at_event_time():
    # Causality pin: at the event row itself the label is undecided ("");
    # the label is decided strictly after t_0 (day 16 > day 15 here).
    rows = tape()
    sigs = run(rows)
    event_row = next(s for s, r in zip(sigs, rows) if r["day"] == CFG["event_day"])
    assert event_row["is_event"] == 1
    assert event_row["label"] == "", "label must be undecided at the event time"
    decided = [s for s in sigs if s["barrier_status"] in ("profit_hit", "stop_hit", "vertical")]
    assert decided, "fixture must contain a decided label"
    first = decided[0]
    assert first["computed_at"] > event_row["computed_at"], \
        "label_known_ts must be strictly after the event ts"
    assert int(first["exit_day"]) == 16 and first["label"] == 1


# ---------------------------------------------------------------------------
# Normative-core unit tests (mirrors the §S3 pseudocode)
# ---------------------------------------------------------------------------

def test_boundary_profit_exact_touch():
    # Touch is inclusive: hi exactly == profit_px is a hit [example convention].
    px, hi, lo, ts = _synth_path([10.0, 10.0, 11.0, 10.5, 10.2, 10.1, 10.0])
    label, tau, status = label_px(px, hi, lo, ts, ts[0], 0, 1, 1.0, 1.0, 1.0, 5,
                                  **_guard_kwargs())
    assert (label, tau, status) == (1, 2, "profit_hit")


def test_boundary_stop_exact_touch():
    px, hi, lo, ts = _synth_path([10.0, 10.0, 9.0, 10.5, 10.2, 10.1, 10.0])
    label, tau, status = label_px(px, hi, lo, ts, ts[0], 0, 1, 1.0, 1.0, 1.0, 5,
                                  **_guard_kwargs())
    assert (label, tau, status) == (-1, 2, "stop_hit")


def test_vertical_fallback_zero_not_sign_noise():
    # Path drifts +0.4 but never touches ±1.0 → label 0, NOT sign(r_H) [documented §S10.6].
    px, hi, lo, ts = _synth_path([10.0, 10.1, 10.2, 10.3, 10.4, 10.4, 10.4])
    label, tau, status = label_px(px, hi, lo, ts, ts[0], 0, 1, 1.0, 1.0, 1.0, 5,
                                  **_guard_kwargs())
    assert (label, tau, status) == (0, 5, "vertical")
    assert label == 0, "vertical must be 0 even when the final drift is positive"


def test_tie_adverse_first():
    # Both barriers touched inside one bar → adverse-first tie-break → -1 [example].
    px = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    hi = [10.0, 12.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    lo = [10.0, 8.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    _, _, _, ts = _synth_path(px)
    label, tau, status = label_px(px, hi, lo, ts, ts[0], 0, 1, 1.0, 1.0, 1.0, 5,
                                  **_guard_kwargs())
    assert (label, tau, status) == (-1, 1, "tie_adverse_first")


def test_short_side_profit_frame():
    # side=-1: profit when the path falls to P0 - ku*sig; labels are side-relative.
    px, hi, lo, ts = _synth_path([10.0, 9.0, 9.5, 9.6, 9.7, 9.8, 9.9])
    label, tau, status = label_px(px, hi, lo, ts, ts[0], 0, -1, 1.0, 1.0, 1.0, 5,
                                  **_guard_kwargs())
    assert (label, tau, status) == (1, 1, "profit_hit")


def test_short_side_stop_frame():
    px, hi, lo, ts = _synth_path([10.0, 11.0, 10.5, 10.2, 10.1, 10.0, 9.9])
    label, tau, status = label_px(px, hi, lo, ts, ts[0], 0, -1, 1.0, 1.0, 1.0, 5,
                                  **_guard_kwargs())
    assert (label, tau, status) == (-1, 1, "stop_hit")


def test_invalid_price_unknown():
    for bad_px in ([10.0, float("nan"), 10.0, 10.0, 10.0, 10.0, 10.0],
                   [10.0, 0.0, 10.0, 10.0, 10.0, 10.0, 10.0],
                   [10.0, -3.0, 10.0, 10.0, 10.0, 10.0, 10.0]):
        px, hi, lo, ts = _synth_path(bad_px)
        label, tau, status = label_px(px, hi, lo, ts, ts[0], 0, 1, 1.0, 1.0, 1.0, 5,
                                      **_guard_kwargs())
        assert status == "UNKNOWN", f"bad price {bad_px[1]} must map to UNKNOWN, never interpolate"


def test_locate_guard_short_without_locate():
    # C7: SHORT labels require locate_ok from the consumer.
    px, hi, lo, ts = _synth_path([10.0, 9.0, 9.5, 9.6, 9.7, 9.8, 9.9])
    label, tau, status = label_px(px, hi, lo, ts, ts[0], 0, -1, 1.0, 1.0, 1.0, 5,
                                  **_guard_kwargs(locate_ok=False))
    assert status == "UNKNOWN", "short-side label without locate must be UNKNOWN"


def test_staleness_unknown():
    px, hi, lo, ts = _synth_path([10.0, 11.0, 10.5, 10.2, 10.1, 10.0, 9.9])
    stale_asof = ts[0] + 60_000_000_000  # 60 s after the event, TTL is 3 s [default]
    label, tau, status = label_px(px, hi, lo, ts, stale_asof, 0, 1, 1.0, 1.0, 1.0, 5,
                                  **_guard_kwargs())
    assert status == "UNKNOWN", "stale event (asof - event_ts > TTL) must be UNKNOWN"


def test_halt_and_auction_states():
    px, hi, lo, ts = _synth_path([10.0, 11.0, 10.5, 10.2, 10.1, 10.0, 9.9])
    for state, want in (("HALTED", "UNKNOWN"), ("CLOSED", "UNKNOWN"), ("AUCTION", "DEGRADED")):
        label, tau, status = label_px(px, hi, lo, ts, ts[0], 0, 1, 1.0, 1.0, 1.0, 5,
                                      **_guard_kwargs(market_state=state))
        assert status == want, f"market_state={state} must yield {want}"


def test_cooldown_unknown():
    # C10: within cooldown_s of a compliance block → no new labels.
    px, hi, lo, ts = _synth_path([10.0, 11.0, 10.5, 10.2, 10.1, 10.0, 9.9])
    kw = _guard_kwargs(now_ns=1_000_000_000, last_block_ns=900_000_000)  # 0.1 s < 300 s cooldown
    label, tau, status = label_px(px, hi, lo, ts, ts[0], 0, 1, 1.0, 1.0, 1.0, 5, **kw)
    assert status == "UNKNOWN", "cooldown window must yield UNKNOWN"


def test_sigma_uses_pre_event_data_only():
    # Leakage pin (§S10 mode 1): a post-event spike must not be able to move
    # the estimate — the caller must pass strictly pre-event changes.
    pre = [0.1, -0.2, 0.15, -0.1, 0.05, 0.12, -0.08, 0.2]
    sig_pre = estimate_sigma(pre, 30)
    sig_con = estimate_sigma(pre + [5.0], 30)  # contaminated with future data
    assert sig_con > 2 * sig_pre, "including future data moves the estimate → asof discipline required"
    assert math.isclose(sig_pre, math.sqrt(sum((x - sum(pre) / len(pre)) ** 2
                                               for x in pre) / (len(pre) - 1)), rel_tol=1e-12)


def test_sigma_degenerate_raises():
    for bad in ([0.5], [1.0, 1.0, 1.0], [float("nan"), 0.1]):
        try:
            estimate_sigma(bad, 30)
        except ValueError:
            pass
        else:
            raise AssertionError(f"degenerate vol window {bad} must raise (→ UNKNOWN)")


def test_regime_gates_machine_readable():
    # §1 regime gates must parse as machine records with the 7 required fields.
    text = MODULE_MD.read_text()
    m = re.search(r"```yaml\n(regime_gates:.*?)\n```", text, re.DOTALL)
    assert m, "machine-readable regime_gates YAML block missing from §1"
    gates = yaml.safe_load(m.group(1))["regime_gates"]
    required = {"regime_id", "direction", "mechanism", "condition", "action",
                "min_lag", "unknown_behavior"}
    assert len(gates) >= 3, "expected >=3 regime gate records"
    for g in gates:
        assert required <= set(g), f"gate {g.get('regime_id')} missing fields"
        assert g["direction"] in ("amplifies", "degrades", "inverts")
        assert g["action"] in ("veto", "halve", "double", "widen_stops", "pause_entry")
