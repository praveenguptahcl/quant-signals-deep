---
appendix: canonical-event-bar-schema
appendix_version: 1.0.0
title: Canonical Event / Bar schema
scope: global — imported by reference from every S/T/R module file; never duplicated
---

# Appendix A — Canonical Event / Bar schema

All module inputs are expressed in this canonical schema. Modules map their
vendor-specific columns to these logical names once, in `§S0/§T0` ("Mapping to
canonical Event/Bar schema"); the mapping is written once and never restated
elsewhere in the file.

## A.1 Timestamps — dual-clock rule

Every event and every bar carries **two** timestamps:

| Field | Type | Meaning |
|---|---|---|
| `event_ts` | int64 nanoseconds, UTC | When the event occurred *at the source* (exchange timestamp). This is the authoritative causality clock. |
| `asof_ts` | int64 nanoseconds, UTC | When the event became *known to us* (arrival at our ingest). Used for latency accounting and staleness. |

Rules:
- `asof_ts >= event_ts` always (an event cannot be known before it occurs). CI asserts this on fixtures.
- Causality ordering is decided by `event_ts` only. `asof_ts` is bookkeeping.
- UTC canonical; no local-time columns in canonical data. Display TZ is a presentation concern only.

## A.2 Event schema (tick / quote / trade / book events)

| Field | Type | Required | Notes |
|---|---|---|---|
| `event_ts` | int64 ns UTC | yes | exchange timestamp |
| `asof_ts` | int64 ns UTC | yes | ingest arrival |
| `symbol` | string | yes | canonical ticker, exchange-qualified |
| `venue` | string | yes | MIC code where applicable |
| `event_type` | enum | yes | `QUOTE` \| `TRADE` \| `ADD` \| `CANCEL` \| `EXECUTE` \| `HALT` \| `AUCTION` |
| `bid_px` | decimal | quote/add | best bid price |
| `bid_sz` | int | quote/add | displayed size, shares |
| `ask_px` | decimal | quote/add | best ask price |
| `ask_sz` | int | quote/add | displayed size, shares |
| `trade_px` | decimal | trade/execute | trade price |
| `trade_sz` | int | trade/execute | trade size, shares |
| `trade_cond` | string | trade | condition codes (odd-lot, dark, …) |
| `seq` | int | yes | per-venue sequence number; gap detection key |

Invalid, crossed (`bid_px > ask_px`), locked, or negative-size events are dropped
at ingest. A dropped event never enters the module; module-state is reported as
`DEGRADED` while drops exceed the per-chapter tolerance, otherwise `OK`.
Invalid *input rows* reaching a module directly (e.g. in test) → module-state
`UNKNOWN` per F1, never interpolated (see appendix f).

## A.3 Bar schema (time bars and event bars)

| Field | Type | Required | Notes |
|---|---|---|---|
| `event_ts` | int64 ns UTC | yes | bar *open* time (see bar-label rule) |
| `asof_ts` | int64 ns UTC | yes | when the bar *closed* (finalized) in our ingest |
| `symbol` | string | yes | |
| `venue` | string | yes | |
| `bar_type` | enum | yes | `TIME` \| `EVENT` \| `DOLLAR` \| `VOLUME` \| `TICK` |
| `bar_span` | string | yes | e.g. `1s`, `500ms`, `100ev`, `$1M` |
| `open` | decimal | yes | |
| `high` | decimal | yes | |
| `low` | decimal | yes | |
| `close` | decimal | yes | |
| `volume` | int | yes | shares |
| `trades` | int | conditional | required for `EVENT`/`TICK` bars |
| `is_partial` | bool | yes | `true` while the bar is still forming; modules never signal on partial bars |

**Bar-label rule (fixed):** a bar is labeled by its **open time**, `event_ts = open`.
The bar covering interval `[t, t+Δ)` is labeled `t`. A signal computed on bar `t`
may first act on bar `t+1` — the `signal@t → earliest fill @open(t+1)` discipline
(see appendix e).

## A.4 Staleness TTL and gap policy

- Every module declares a `staleness_ttl` in its `§S0/§T0` Time contract: the
  maximum allowed age of the freshest input before the module-state expires to
  `UNKNOWN` (F4: TTL defaults to 3× the module cadence).
- **Gap policy (no interpolation):** sequence gaps (`seq` jumps) and timestamp
  gaps longer than the chapter's `max_gap` are masked as unknown — bars spanning
  a gap are marked `is_partial` and excluded from statistics; cumulative features
  (e.g. OFI) restart after a gap. Interpolation of prices or sizes across a gap
  is forbidden.
- Halts/auctions: events with `event_type ∈ {HALT, AUCTION}` flip the runtime
  market state (see appendix e); contributions accrued across a halt reopen are
  discarded, not interpolated.

## A.5 Reference (normative wording for §S0/§T0)

> Input mapping: `<vendor columns> → canonical Event/Bar schema (Appendix A,
> v1.0.0)`. Dual timestamps `event_ts`/`asof_ts` int64 ns UTC; causality by
> `event_ts`. Bar label = open time. Staleness TTL = `<ttl>`; gap policy = mask,
> no interpolation; halt/auction → discard across reopen.
