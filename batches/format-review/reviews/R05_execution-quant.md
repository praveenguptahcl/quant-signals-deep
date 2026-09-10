# Reviewer 05 — Execution quant (read S001, T001 full; S002/T002 skimmed; RB-list full)

## CRITICAL

1. (a) No signal-module output contract. Ex: S001 §S3/S6 defines math + data spec but never what the module emits — no function signature, output schema, cadence contract. Fix: mandatory "Module contract" box per S chapter — tick(symbol, events≤t) → Signal{symbol, direction∈{long,short,flat}, confidence∈[0,1], capital∈[0,1]}, cadence.
2. (a) No order-ticket schema. Ex: T001/T002 §T2 "Order/execution sketch" prose; across 36,207 lines time_in_force appears 0×, order type 3×, GTC/IOC/FOK 24 scattered hits. Fix: one global OrderTicket schema (order_id, symbol, side, qty, order_type, limit_px, TIF, venue/router, strategy_ref, parent/child); every T chapter fills it.
3. (a) Signal→order boundary never stated as doctrine. No chapter says signals emit trading intentions only and never orders; T001's sketch does touch orders; T021 blurs the line. Fix: global boundary statement in doc preamble + per-chapter "may emit / must NOT emit" line.
4. (a) Strategy→execution handoff is a sketch, not a contract. No parent-order spec, child-order decomposition, order-state machine, partial-fill policy (60 "partial fill" hits are disclaimers, never handling logic). Fix: per T chapter — child-order state machine + partial-fill policy (rest/chase/leave-remainder) + cancel-replace rules.

## MAJOR

5. (a) Zero test vectors. "test vector" = 0 hits compendium-wide. Fix: each chapter ships N deterministic input→output vectors with exact expected values.
6. (a) No market-closed / stale-output contract for signal modules. "market closed" = 1 hit; no S chapter states closed/stale output (flat? UNKNOWN? last value?). Fix: each S chapter states closed/stale behavior with max-staleness TTL.
7. (a) Signals lack the versioned state vector regimes have. S chapters carry no estimator_version, data_vintage, computed_at; T001's G* table unversioned. Fix: Signal State Vector mirroring RB-list.md RSV.
8. (a) Venue routing and order-type fields unsystematic. 328 "venue" hits are vendor talk, not routing. Fix: execution-ticket fields in every T chapter — order_type, TIF, venue/router, fallback when primary venue unavailable.
9. (b) Honest after-cost verdict buried ~1,500 words deep. T001 §T7 "no documented positive after-cost edge" after entry/exit/sizing/pseudocode. Fix: move after-cost verdict into T1/S1 verdict tables.
10. (b) Example-parameter sprawl, no parameter register. T001 §T2: ~15 example thresholds in prose. Fix: one "Parameter register" table per chapter (name, example default, calibrated-vs-placeholder status).
11. (b) Section-title drift across chapters. "Failure modes" vs "Failure modes & pitfalls"; S-section descriptors vary. QC C1 checks sections "present, in order" not exact titles. Fix: freeze exact section titles in merge-protocol.md C1.
12. (b) T2 prose and T3 pseudocode are two sources of truth. Ex: T001 §T2 vs §T3 different notation (z^OFI_t vs z). Fix: one canonical rule block per T chapter; pseudocode derived, never parallel.

## MINOR

13. (a) No confidence→capital mapping. Fix: each T chapter states sizing function signature (risk_budget, signal_confidence) → notional.
14. (b) "Simulated only — requires MBO/ITCH" labels are inline asides, not a summary. Fix: "Executability" row in T1/S1 — live-executable vs simulated-only.
15. (a) No staleness TTL on signal state. Fix: per-S max-age contract for stateful baselines; expire to UNKNOWN/flat.

## Deliberately not flagged
t→t+1 causality (605 hits, well enforced), kill-switch specs, halt handling, synthetic labeling. RB-list.md's RSV + fail-safes F1–F4 is the template S/T chapters should mirror.
