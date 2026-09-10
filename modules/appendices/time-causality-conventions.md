---
appendix: time-causality-conventions
appendix_version: 1.0.0
title: Time and causality conventions
scope: global — every S/T/R module; fixed wording required where noted
---

# Appendix E — Time and causality conventions

## E.1 Clock domain

- Canonical time: **UTC**, int64 nanoseconds since epoch. Every timestamp field
  in every schema is int64 ns UTC unless explicitly suffixed otherwise.
- The **authoritative causality clock** is `event_ts` (source time). Arrival
  time (`asof_ts`) is never used to order events.
- Display/session timezone is declared per chapter in the Time contract
  (e.g. `America/New_York` for US equities); it affects labels only.

## E.2 Skew and jitter budgets

| Parameter | Meaning | Declared in |
|---|---|---|
| `max_skew` | maximum tolerated clock disagreement between our ingest and the venue source clock | §S0/§T0 Time contract |
| `jitter_budget` | maximum allowed `asof_ts − event_ts` per event before the event is flagged stale-at-arrival | §S0/§T0 Time contract |

Events arriving with `asof_ts − event_ts > jitter_budget` are flagged and
excluded from feature computation; persistent violation → `DEGRADED` → alert.
SIP-sourced timestamps carry 10s-of-microseconds jitter: any latency claim on
SIP data is labeled *simulated only — requires MBO/ITCH*.

## E.3 The t→t+1 causality discipline (mandatory)

- A signal computed from inputs with newest `event_ts = t` (bar `t`, labeled by
  open time) may first execute at **bar `t+1`'s open** — never inside bar `t`.
- Fixed wording, placed atop every §S3/§T2 in a **Timing box**:

> `signal@t (<cadence>, <TZ>) → earliest fill @open(t+1)`

- Mandatory unit test in every chapter: **no-signal-bar fills** —
  `assert fill_event.event_ts > signal.computed_at` for every simulated fill.
  The assertion is inline in §S3/§T3 pseudocode and enforced in
  `tests/test_<SID>.py`.
- Lookahead audit: features used for a bar-`t` decision may include events with
  `event_ts ≤ t` only. Bar-close values of bar `t` are not available until bar
  `t` finalizes (`asof_ts` of the bar close).

## E.4 R-chapter lag contract

R modules add a **Lag contract**: `min_lag` (minimum bars between regime-state
computation and use as a gate), `unknown_behavior` (restrictive default:
`veto` unless the chapter justifies otherwise), and the same t→t+1 assertion
for any trade conditioned on a regime label.

## E.5 Reference (normative wording for §S0/§T0)

> Time contract: clock domain UTC, int64 ns; authoritative causality clock =
> `event_ts`; max_skew = `<…>`; jitter budget = `<…>`; bar-label = open time;
> staleness TTL = `<…>`; gap policy = mask, no interpolation.
> Timing: `signal@t (<cadence>, <TZ>) → earliest fill @open(t+1)`.
> Causality assertion: `assert fill_event > signal_event` (no-signal-bar-fills
> test mandatory).
