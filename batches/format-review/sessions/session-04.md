# Session 04 — Derivatives / crypto / venue-specific concerns + data/time/precision

Date: 2026-09-10 · Facilitator subagent · Focus: R06 (options), R08 (crypto), R04 (HFT infra), R19 (C++ low-latency), R09 (data eng), R03 (vol quant); cross-checked vs R01/R02/R05/R07/R10–R18/R20.

## 1. Event/time/causality contract (decisions)

1.1. Mandatory **Time contract** block per chapter (S6/T5 or §T0): `clock_domain` (exchange event-ts vs arrival vs SIP/consolidated), authoritative clock for causality, units = int64 ns, zone (UTC canonical; venue-local stated), `max_skew`, jitter budget, mandated live/simulated-only label.
1.2. Bar-label rule declared, not assumed: every chapter states open-labeled vs close-labeled bars; standard one-line box at top of S3/T2: `signal@t (<cadence>, <TZ>) → earliest fill @open(t+1)`.
1.3. t→t+1 is a machine-checked assertion, not prose: T3 pseudocode carries `assert fill_event > signal_event`; QC gate replays every worked example against stated rules ("no signal-bar fills").
1.4. Dual timestamps on data tables: every S6/T5 table carries `(event_ts, asof_ts)`; causality joins must use `asof_ts ≤ signal_ts` (vintage, never revised values).
1.5. Staleness contract per chapter: staleness TTL, feed-lag halt trigger, gap-fill policy (default: never interpolate — flatten/stand down), UNKNOWN propagation rule. Standardized module-state enum: OK / DEGRADED / UNKNOWN / OFF (adopted house-wide, incl. R-chapters).
1.6. Event contract block per chapter: ordering guarantee, tie-break rule, out-of-order window, duplicate handling, gap behavior — replaces implicit "sort ts_event".
1.7. Market-state table per chapter (CONTINUOUS_TRADING / HALTED / AUCTION / CLOSED) with allowed action per state; halt/auction is runtime state, not just backtest masking.

## 2. Asset-class extensions (decisions)

2.1. Required structured **Domain & session** block (top of S6/T5): asset class, venues, session windows + timezone, canonical clock, calendar/holiday convention, settlement convention. "No official close / 24/7" is a first-class peer of RTH — no equity-native defaults leak into crypto chapters (NBBO/SIP/DST/half-day marked N/A).
2.2. Options modules add three mandatory blocks: (a) ChainSnapshot referencing the single shared canonical chain schema (OCC symbol, event_ts, asof_ts, expiry, strike, cp, exercise style, settlement AM/PM, bid/ask/size, IV, Greeks, OI, volume, underlying ref, spot, div yield, rate, halt/stale flags) — no per-chapter ad-hoc chain schemas; (b) **Pricing & Greeks block** — model (e.g. CRR vs Black-76), r/q sources, dividend model, American handling, validation tolerance; (c) **Expiry/assignment rules** — ex-div calendar source, early-exercise trigger, auto-exercise ITM threshold, expiry-day position rule, pin-risk guard.
2.3. Options cost ledger: canonical T4 ledger gains options lines — per-leg spread capture, per-contract commission + exchange/clearing fees, OCC clearing, margin-financing drag, borrow cost (borrow block: feed source, accrual formula, hard cutoff), plus venue-risk reserve where applicable.
2.4. Options fill rules block in T2: fill price rule, partial fills, no-fill on stale quotes, assumed latency; and a backtest fill-model table (order type, latency ms, partial-fill probability, impact model, queue-position modeled y/n).
2.5. Crypto modules add: per-venue **funding interval** parameter (h), **Venue definition snapshot** in T5 (funding formula version, OI definition, premium-index constituents, effective dates — never splice across formula changes), and a **Margin & self-liquidation** block (margin mode, max leverage, liquidation-price formula, margin-call behavior; T4 ledger carries ADL/clawback/insurance-fund venue-risk reserve line).
2.6. Anti-bloat rule: asset-class extension blocks are conditional — they appear only when the domain needs them. Shared material (chain schema, glossary, cost levels L0–L3) lives in appendices referenced by ID, never re-stated. Format stays standalone-module: every chapter self-contained with version-pinned, verbatim dependency recaps — no dangling "see MASTER.md" references.

## 3. Numeric contract (decisions)

3.1. Precision declared per chapter: `price_repr` (int64 cents/ticks), quantities int64, statistics double, exact scaling rules. 5-row compute contract per chapter: per-event ns budget, state bytes, alloc policy (none in hot path), worst-case events/sec, precision.
3.2. Units line mandatory in math section: decimal vs percent vol declared (0.18 vs 18.0 — no ambiguity); return definition fixed per chapter (no "pick one and stay consistent" opt-outs); annualization day-count declared (252 vs 365 stated, contradictions fail QC).
3.3. Canonical **Signal output contract**: SIGNAL_VECTOR = {symbol, timestamp, direction ∈ {−1,0,+1}, score ∈ [−1,1], confidence ∈ [0,1], capital_scale, estimator_version, data_vintage} — every S chapter conforms; T3 declares consumed signals' output units, cadence, annualization convention, staleness/UNKNOWN behavior.
3.4. Processing model fixed per chapter, one token: `per_event | per_bar(<period>) | per_snapshot` — QC-enforced against contradictions (event-driven T2 vs bar-driven diagram). Streaming chapters get named state vector + explicit `on_event(e)` transition spec with init/reset/warmup (warmup bars/events, warmup_output emit|hold, reset triggers).
3.5. Edge-case row in every parameter table: divide-by-zero → value, zero-variance, zero-depth, empty-window, crossed-book, counter width + saturation-vs-wrap. Quality checks are executable assertions incl. output bounds.

## 4. Data contract (decisions)

4.1. Schema block per input dataset: field, canonical logical name, dtype, units, nullable, enum/partition/sort keys. Vendor-fragile column names banned in sketches — sketches use logical names with a per-vendor column-mapping row.
4.2. **Dataset fingerprint** per S6/T5: vendor + product + schema version + adjustment source + symbol map + vintage.
4.3. One-row **Data rights** block: allowed uses, redistribution flag, expiry, audit field — surfaced as startup-gating assertions (entitlement key present, redistribution allowed/denied).
4.4. **Cheapest adequate source** emitted as structured S8/T6 verdict row: min_tier, latency_class, required_fields, price_band, build_or_buy. Header field `min_data_tier` + `fatal_if_below` makes fail-closed wiring machine-checkable. Tier taxonomy annotated with crypto mapping (free venue websocket = Tier-0 equivalent).
4.5. T2/T4 cost assumptions get a single **cost assumption register** per chapter (fee_schedule_as_of date, venue, tier, source; side taker|maker|mixed; borrow_bps_per_day with explicit reason if 0) — referenced, never restated; every cost value carries provenance tag.

## Cross-cutting / anti-bloat (decisions)

5.1. One fixed-wording **Causality block** in the same subsection of every chapter (also covers "Causality" row at top of every math/mechanics section).
5.2. "Conventions register" box at top of every chapter: sign/quoting/delta conventions, day-count, return definition, timestamp zone — one-glance, no hunting through 12 sections.
5.3. Single source of truth: config lives in §S0/§T0 (name, type, unit, provenance, value); prose/pseudocode reference parameter names only. Status tags FIXED / CALIBRATE / EXAMPLE, machine-detectable, one token.
5.4. Worked examples carry machine-readable headers: TYPE=accounting-demo vs validation-run, seed, script. Examples implement the canonical formula; variants get separate labeled mini-examples.
5.5. Failure modes as trigger→action table (condition, how detected, action, recovery); kill-switch safe-mode merged into entry/exit rule table with priority: override; ranked by expected P&L impact × likelihood.

## Deferred / flagged for parent

- RB-list RSV schema + fail-safes F1–F5 is the port target for per-chapter Data fail-safes — confirmed by R09/R12/R16; fold into shared §0 importable block.
- Compliance contract (T11/S13 regulatory & venue-compliance block, self-trade/STP rules, bona-fide-intent guards, audit decision-log schema) — Session 05 topic territory; session 04 confirms the slot exists and pseudocode is normative over prose.
- Regime-gates wiring (R-IDs per chapter) still pending as ordered annotation task; format slots (regime_ids[] header, Regime gates table) are decided and ready.
