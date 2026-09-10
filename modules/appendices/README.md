---
appendix: appendices-index
appendix_version: 1.0.0
title: Global appendices index
scope: index of the 11 global appendices
---

# Global appendices — index (v1.0.0)

Module files import these **by reference**; their content is never duplicated
inside a module file. Reference format: `Appendix <letter> (v<version>)`.

- **(a)** `canonical-event-bar-schema.md` — Canonical Event/Bar schema: dual `event_ts`/`asof_ts` int64-ns UTC timestamps, bar-label rule, staleness TTL, gap policy.
- **(b)** `signal-vector-schema.md` — SignalVector schema: symbol, direction ∈ {+1,−1,0}, confidence 0–1, capital 0–1, computed_at, staleness, emission cadence.
- **(c)** `order-ticket-schema.md` — OrderTicket schema: intents only (symbol, side, qty, limit, tif); child-order state machine NEW→WORKING→FILLED/CANCELLED/PARTIAL; partial-fill and cancel-replace rules; intentions-only doctrine.
- **(d)** `chain-snapshot-schema.md` — ChainSnapshot schema for options-extension modules.
- **(e)** `time-causality-conventions.md` — Time/causality conventions: clock domain, authoritative causality clock, max_skew, jitter budget, `assert fill_event > signal_event`, no-signal-bar-fills test, timing-box wording.
- **(f)** `f1-f5-failsafes.md` — F1–F5 universal fail-safes (verbatim from RB-list) and module-state enum OK|DEGRADED|UNKNOWN|OFF; invalid input → UNKNOWN, never interpolate.
- **(g)** `decision-log-schema.md` — Decision-log (audit) record schema for compliance.
- **(h)** `glossary.md` — Glossary of canonical terms.
- **(i)** `marker-taxonomy-legend.md` — Marker taxonomy: numeric tags documented/default/example/unverified/internal-est/measured, BEFORE-COST/COMM-ONLY/FULL-COST tokens, provenance tiers, COST-block contract.
- **(j)** `data-rights-conventions.md` — Data-rights conventions: startup entitlement assertions and vendor mapping rules.
- **(k)** `module-state-enum.md` — Module-state enum: the single canonical state vocabulary.
