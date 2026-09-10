---
appendix: glossary
appendix_version: 1.0.0
title: Glossary
scope: global — canonical term definitions; chapters use these terms without redefining them
---

# Appendix H — Glossary

| Term | Definition |
|---|---|
| **Module** | One standalone file (S001–S100 signals, T001–T100 strategies, R001–R050 regimes) implementing the `signal(state, events, cfg)` contract. |
| **SignalVector** | The single canonical signal output: `{symbol, direction, confidence, capital, computed_at, staleness, module_state}` (appendix b). |
| **OrderTicket** | An order *intent* emitted by a T-module: `{symbol, side, qty, limit, tif, ticket_id, parent_signal, intent_ts, state}` (appendix c). Strategies emit intentions only; brokers create orders. |
| **Intentions only** | The doctrine that T-modules emit `OrderTicket` intents and never place orders, hold exchange sessions, or mutate wire state. |
| **Cadence** | Emission rhythm, one of `per_event` \| `per_bar` \| `per_snapshot`. Fixed per module. |
| **event_ts / asof_ts** | Dual timestamps: source-time (authoritative causality clock) vs our ingest-arrival time (appendix a). |
| **Bar label** | A bar is labeled by its open time. The bar covering `[t, t+Δ)` is labeled `t`. |
| **t→t+1** | Causality discipline: signal from bar `t` may first fill at bar `t+1`'s open; `assert fill_event > signal_event` (appendix e). |
| **Staleness TTL** | Maximum age of the freshest input before module-state expires to `UNKNOWN`; default 3× cadence (F4). |
| **No interpolation** | Gap policy: missing data is masked as unknown; prices/sizes are never interpolated across gaps. Invalid input → `UNKNOWN`, never a guess (appendix f). |
| **Module-state** | One of `OK \| DEGRADED \| UNKNOWN \| OFF` (appendix k). `UNKNOWN` is restrictive, never benign. |
| **COST block** | The single source of truth for costs in a chapter: 4-component stack + callable `expected_cost_bps` (appendix i, §S2/§T2 sub-block). |
| **expected_cost_bps** | Callable `expected_cost_bps(notional, adv_pct, venue, side, urgency) → bps`. Reference implementation per chapter. |
| **Cost gate** | Executable predicate `expected_cost_bps(...) <= k * edge_bps`; trades must pass it (default `k = 0.5` `[default]` unless the chapter calibrates otherwise). |
| **Cost-level tokens** | `BEFORE-COST` \| `COMM-ONLY` \| `FULL-COST` — which cost stack a reported number includes (appendix i). |
| **bps** | Basis points; 1 bps = 0.01%. |
| **Marker tags** | `[documented]` `[default]` `[example]` `[unverified]` `[internal-est]` `[measured]` — provenance of every numeric literal (appendix i). |
| **Provenance tiers** | `[P]` peer-reviewed paper · `[D]` documented industry source · `[I]` internal/chabot-derived · legend in compendium header. |
| **Decision log** | Append-only, hash-chained audit record per material action (appendix g). |
| **Kill switch** | State machine `ARMED → TRIPPED → RECOVERY → ARMED` with re-arm checklist (T-modules; §T0 risk contract). |
| **Regime gate** | Machine record `{regime_id, direction, mechanism, condition, action, min_lag, unknown_behavior}` gating a module on regime state. |
| **Sentinel / Verifier** | Dual estimators required to agree within tolerance or state is `UNKNOWN` (F3). |
| **ADV** | Average daily volume (shares). `adv_pct` = intended notional ÷ (ADV × price). |
| **SIP** | Securities Information Processor — consolidated national quote feed; slower than direct exchange feeds. SIP-based latency claims are labeled *simulated only — requires MBO/ITCH*. |
| **MBO / ITCH** | Market-by-order / direct exchange feed protocols. |
| **L1 / L2** | Top-of-book (best bid/ask) / deeper book levels. |
| **NBBO** | National Best Bid and Offer. |
| **TAQ** | Trades and Quotes — historical record of every trade and quote. |
