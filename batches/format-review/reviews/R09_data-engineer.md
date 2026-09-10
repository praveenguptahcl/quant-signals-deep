# Reviewer 09 — Data engineer (read S003, S020, T003 full; skimmed S1/S6/S8/T2/T5 across chapters; RB-list; notes/chapter-template.md)

## CRITICAL

1. (a) S6 "Type" column is not a type. All 100 S6 tables sampled: top values float (99), float/int (27), reference (26), events (23), numeric (14), int (12), dates, bool, derived, ±1 — granularity/provenance/ad-hoc labels mixed in one column. Ex: S020 S6 "Trade price, size, timestamp, exchange/TRF code | events | per trade". No nullability, units, enum values, partition/sort keys (0 hits nullable/primary key/CREATE TABLE). Fix: machine-readable schema block per input dataset — field, dtype, units, nullable, enum/partition/sort, one logical name per concept.
2. (a) No timestamp contract — only 15/100 S6 sections state units/zone. ts_event, ts_recv, SIP, "exchange timestamps" interchangeable with no authoritative-clock definition; bar open-labeled vs close-labeled never specified. Fix: Timestamps block per S6/T5 — authoritative clock, units, zone, which ts drives causality, bar-label convention.
3. (a) Missing/stale-data policy is prose in checklists, not machine rules. Fix: port RB-list F1–F5 into every S/T chapter as "Data fail-safes" block with explicit state transitions.
4. (a) Entitlement/licensing exists only as cost prose. "entitlement" 1× in 36k lines; no per-module rule for allowed uses, history expiry, audit requirements. Fix: one-row "Data rights" block per S6 — allowed uses, redistribution flag, expiry, audit field.
5. (a) No data lineage identifiers. Ex: S003 S6 "Collection: Databento MBP-1, Polygon L2 per the report entry" — no dataset ID, schema version, symbol-map, adjustment source. Fix: dataset fingerprint per S6 — vendor + product + schema version + adjustment source + vintage.

## MAJOR

6. (a) Field names vendor-fragile, no canonical mapping. Ex: S003 sketch uses Databento columns; S020 uses generic price/size/symbol. Fix: logical field names in schema block + per-vendor column-mapping row.
7. (a) "Cheapest data source" answer is human-only. Fix: emit S8 verdict as structured row — min_tier, latency_class, required_fields, price_band, build_or_buy.
8. (a) Quality checks are prose, not assertions. 27 `assert` mentions in 36,207 lines; S003 sketch filters empty books but never asserts I ∈ [-1,1]. Fix: ingest sketch includes quality checks as executable assertions incl. output bounds.
9. (b) Duplicated verdict locations can diverge (S1 "Build-or-buy in one line" vs S8 full verdict; same T1/T6). Fix: one verdict location (S8/T6); S1/T1 link to it.
10. (b) `example` parameters used as exact arithmetic in worked examples. Ex: T003 §T4 penny-exact P&L ($162.71 net) from all-`example` thresholds. Fix: mark non-example rules explicitly as `rule`; keep worked examples quarantined as illustrations.
11. (b) S1 "When it dies" restates S10 failure modes. Fix: S1 keeps trigger phrases only; S10 keeps mechanism + mitigation; dedupe at merge.
12. (b) Session-calendar rules are scattered one-liners. Fix: explicit "Session calendar" rule block in S6/T5 — calendar source, half-day/DST handling, auction/halt exclusion, citing applicable R-numbers.

## MINOR

13. (b) Parameter provenance unlabeled. Fix: Provenance column in parameter tables — paper | measured | example.
14. (a/b) Plot-script pointers repo-relative, invisible from readable copy. Fix: footnote the repo-relative root once per document header.
15. (b) Provenance tag [D] defined per chapter but never indexed. Fix: one global provenance taxonomy block at document head.

## Recommended follow-up
Cheapest high-leverage change: schema-block + fail-safes retrofit template (issues 1–3) applied at merge time via Gate QC — RB-list F1–F5 is already the house standard for R-chapters and ports directly.
