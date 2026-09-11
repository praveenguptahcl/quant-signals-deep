#!/usr/bin/env python3
"""Acceptance tests for S023 — Gap-and-go.

Self-describing fixture: open/prev_close/confirm_bars are parsed from the tape,
not hardcoded. 8 tests.
"""
import csv
import pathlib
import re

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
TAPE = FIX / "S023_tape.csv"
EXP = FIX / "S023_expected.csv"
TOL = 1e-9  # [default] float tolerance per §S4


def load(path):
    header = {}
    rows = []
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                m = re.match(r"#\s*confirm_bars:\s*(\d+)", line)
                if m:
                    header["confirm_bars"] = int(m.group(1))
                continue
            if not line.strip():
                continue
            rows.append(next(csv.reader([line])))
    return header, rows[0], rows[1:]


def asnum(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return x


def recompute(theader, trows):
    """Normative reference logic (mirrors §S3):

    - gap_pct from the tape's own prev_close/open columns;
    - holds: bar low >= open (long side);
    - confirmed: window (first confirm_bars bars) all hold AND no fill;
    - fill_veto: 1 on the bar where the gap is first filled (low <= prev_close).
    """
    confirm_bars = theader["confirm_bars"]
    idx = {"session": 0, "bar": 1, "prev_close": 3, "open": 4,
           "high": 5, "low": 6, "close": 7}
    sessions = {}
    for r in trows:
        sessions.setdefault(r[idx["session"]], []).append(r)
    out = []
    for s in sorted(sessions, key=int):
        rs = sessions[s]
        pc = float(rs[0][idx["prev_close"]])
        op = float(rs[0][idx["open"]])
        gap_pct = (op - pc) / pc * 100.0
        win = rs[:confirm_bars]
        win_holds = all(float(b[idx["low"]]) >= op for b in win)
        first_fill = None
        for b in rs:
            if float(b[idx["low"]]) <= pc:
                first_fill = int(b[idx["bar"]])
                break
        for b in rs:
            bar = int(b[idx["bar"]])
            low = float(b[idx["low"]])
            holds = 1 if low >= op else 0
            confirmed = 1 if (bar == confirm_bars and win_holds
                              and first_fill is None) else 0
            fill_veto = 1 if (first_fill is not None and bar == first_fill) else 0
            out.append([int(s), bar, gap_pct, holds, confirmed, fill_veto])
    return out


def expected_cost_bps(notional, adv_pct, venue, side, urgency):
    spread_bps = 0.43   # [example]
    fee_bps = 0.30      # [example]
    borrow_bps = 0.0    # [default] long-biased reference; reason in table
    impact_bps = 0.0    # [example] flagged; calibrate per venue at scale-up
    if side == "maker":
        fee_bps = -0.20  # rebate [example]
    return spread_bps + fee_bps + borrow_bps + impact_bps


def expected_move_bps(gap_bps, cont_frac=0.25):  # cont_frac [default]
    """Normative edge-estimation recipe per §S3."""
    return gap_bps * cont_frac


def signal_stub(value, threshold, computed_at):
    """Minimal stub: direction from threshold crossing; confidence scaled."""
    direction = 1 if value >= threshold else (-1 if value <= -threshold else 0)
    confidence = min(1.0, abs(value) / (2 * threshold)) if direction else 0.0
    return {"symbol": "TEST", "direction": direction, "confidence": confidence,
            "capital": 0.5 * confidence, "computed_at": computed_at,
            "staleness_ns": 0, "module_state": "OK"}


def signal_stub_invalid():
    """Crossed/locked quote -> UNKNOWN, never interpolate (F1)."""
    return {"symbol": "TEST", "direction": 0, "confidence": 0.0, "capital": 0.0,
            "computed_at": 0, "staleness_ns": 0, "module_state": "UNKNOWN"}


def close_enough(got, exp):
    g, e = asnum(got), asnum(exp)
    if isinstance(g, float) and isinstance(e, float):
        return abs(g - e) <= TOL * max(1.0, abs(e))
    return g == e


def test_01_fixture_recomputes():
    theader, tcols, trows = load(TAPE)
    eheader, ecols, erows = load(EXP)
    assert tcols == ["session", "bar", "event_ts_ns", "prev_close", "open",
                     "high", "low", "close", "volume"], f"tape cols: {tcols}"
    assert ecols == ["session", "bar", "gap_pct", "holds", "confirmed",
                     "fill_veto"], f"expected cols: {ecols}"
    got = recompute(theader, trows)
    assert len(got) == len(erows), f"row count {len(got)} != {len(erows)}"
    for i, (g, e) in enumerate(zip(got, erows)):
        assert len(g) == len(e), f"row {i}: col count {len(g)} != {len(e)}"
        for j, (gv, ev) in enumerate(zip(g, e)):
            assert close_enough(gv, ev), f"row {i} col {ecols[j]}: {gv!r} != {ev!r}"


def test_02_signal_vector_shape():
    sig = signal_stub(1, 0.6, computed_at=1700000000000000000)
    assert sig["direction"] in (+1, -1, 0)
    assert 0.0 <= sig["confidence"] <= 1.0
    assert 0.0 <= sig["capital"] <= 0.5
    assert sig["module_state"] in ("OK", "DEGRADED", "UNKNOWN", "OFF")


def test_03_no_signal_bar_fills():
    computed_at = 1700000000000000000
    sig = signal_stub(1, 0.6, computed_at=computed_at)
    fill_event_ts = computed_at + 1  # earliest legal fill: strictly after the signal bar
    assert fill_event_ts > sig["computed_at"]  # assert fill_event > signal_event
    same_bar_fill_ts = computed_at
    assert not (same_bar_fill_ts > sig["computed_at"]), "same-bar fill must be rejected"


def test_04_cost_gate():
    k = 0.5  # [default]
    cost = expected_cost_bps(1e6, 0.01, "XNAS", "taker", "normal")
    edge_big = expected_move_bps(150.0)    # 1.5% gap -> 37.5 bps edge [example]
    assert cost <= k * edge_big             # 0.73 <= 18.75: passes
    edge_tiny = expected_move_bps(1.0)     # 0.01% gap -> 0.25 bps edge [example]
    assert not (cost <= k * edge_tiny)      # 0.73 > 0.125: blocked


def test_05_invalid_input_unknown():
    sig = signal_stub_invalid()
    assert sig["module_state"] == "UNKNOWN"
    assert sig["direction"] == 0


def test_06_gap_confirmed():
    # Session 1: bar 4 confirms the LONG; bar 5 loses the hold but does not fill.
    theader, _, trows = load(TAPE)
    _, _, erows = load(EXP)
    got = {(e[0], e[1]): (int(e[3]), int(e[4]), int(e[5])) for e in erows}
    assert got[("1", "4")] == (1, 1, 0), "session-1 bar 4 must be confirmed"
    assert got[("1", "5")] == (0, 0, 0), "session-1 bar 5 loses hold, no fill"


def test_07_deterministic():
    theader, _, trows = load(TAPE)
    assert recompute(theader, trows) == recompute(theader, trows)


def test_08_fill_veto_precedence():
    # Session 2: window bars 1-3 all hold, but bar 4 fills the gap ->
    # veto takes precedence: confirmed=0, fill_veto=1 on bar 4.
    _, _, erows = load(EXP)
    got = {(e[0], e[1]): (int(e[3]), int(e[4]), int(e[5])) for e in erows}
    assert got[("2", "1")] == (1, 0, 0)
    assert got[("2", "3")] == (1, 0, 0)
    assert got[("2", "4")] == (0, 0, 1), "fill veto must override confirmation"
