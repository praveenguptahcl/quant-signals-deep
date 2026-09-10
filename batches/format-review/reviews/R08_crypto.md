# Reviewer 08 — Crypto market-structure specialist (read T075/T076/T077 full; S020, S095; skimmed T071/T078 T2; RB-list skimmed)

## FORMAT CORRECTION (meta)
The task brief said strategy chapters run T1–T12, but every T chapter in the corpus runs T1–T10. A parser built to T1–T12 spec fails. (Freeze exact section titles.)

## CRITICAL

1. (a) No module interface contract. Ex: T075 §T2 "Order/execution sketch" is prose; grep for input schema|output schema|API contract|function signature = 0 hits in 36,207 lines. Fix: "Module contract" block per chapter — input bar schema (fields, canonical timestamp), one function signature, output signal schema (units, cadence, UNKNOWN convention).
2. (a) T-chapters have no parameter tables. Ex: T075 §T2 vs S020 §S3 — 0 of 100 T-chapters have a parameter table (36 S-chapters do); thresholds buried in prose paragraphs. Fix: S3-style parameter table in every T chapter's T2.
3. (a) No structured venue/session/clock declaration. "Universe & session" is ad-hoc paragraph in only 87/200 chapters. Ex: T075 says "24/7" but never declares funding interval (venue-specific h=1h/4h/8h); T078 "RTH only" with no calendar/holiday rule; "timezone" 11×, "UTC" 9×, "fee tier" 2× corpus-wide. Fix: required structured sub-block — venues, session windows + timezone, canonical clock, per-venue funding intervals, calendar/holiday convention.
4. (a) Strategy's own liquidation mechanics absent — zero coverage in 200 chapters. Grep for maintenance margin|liquidation price|margin mode|isolated margin|cross margin = 0 hits; "leverage cap" 1×. Fix: "Margin & self-liquidation" block in T2 for leveraged chapters — margin mode, max leverage, liquidation-price formula, margin-call behavior.

## MAJOR

5. (a) Crypto-native cost lines (ADL, clawback, insurance-fund, withdrawal freeze) are T8 prose, never T4 ledger lines. Fix: "venue-risk reserve" line (ADL/clawback probability × severity) in T4 canonical ledger.
6. (a+b) T2 and T4 cost assumptions disagree within the same chapter. Ex: T075 §T2 "taker fee 5 bps/side" vs §T4 computing 12.65 bps round-trip (2×5=10 ≠ 12.65). Fix: one "cost assumption register" per chapter, referenced not restated by T2 and T4.
7. (a) No "Data contract" block. Staleness timeout, feed-lag halt, UNKNOWN behavior are prose fragments; 24/7 crypto has no daily close to resync. Fix: required Data contract — staleness timeout, feed-lag halt trigger, gap-fill policy, UNKNOWN propagation.
8. (a) No signal↔strategy interface. Ex: T075 §T3 consumes S095 funding with |F_ann| ≥ 40% but annualization conventions must agree and nothing forces it. Fix: T3 rows get required columns — signal output units, cadence, annualization convention, staleness/UNKNOWN behavior, applicable R-ids.
9. (b) T2 "Full mechanics" is an undifferentiated prose wall. Fix: split T2 into fixed mandatory sub-blocks — Universe, Entry, Exits, Sizing, Risk limits, Costs, Execution, Robustness.
10. (a) Venue definition versioning is advice, not a field. Ex: T075 §T5 "never splice funding history across a formula change" but no field to record the snapshot. Fix: required "Venue definition snapshot" in T5 — funding formula version, OI definition, premium-index constituents, effective dates.
11. (a) No acceptance-test section. Fix: required "Acceptance tests" block — 3–5 concrete pass/fail checks with T4 worked-example numbers as fixtures.
12. (b) T8 failure modes are prose bullets, not trigger→action table. Fix: T8 as table — condition, how detected, action, recovery.

## MINOR

13. (b) Equity-native defaults leak into the format (RTH, DST/half-days, NBBO/SIP, "M5 Max"). Fix: structured session block includes explicit "no official close / 24/7" as peer of RTH.
14. (b) T7 evidence format weaker than S9 — no before/after-cost column in strategy chapters. Fix: give T7 the S9 evidence table schema including Before/after-cost column.
15. (a) "Cheapest data source" tier taxonomy is equity-vendor-centric. Fix: annotate tier taxonomy with crypto mapping (free venue websocket = Tier 0-equivalent).

## Keep (don't break)
Funding as P&L line not cost (T075 T4); `reported_*` censored-tape honesty convention (T076); t→t+1 fill causality in every T2; full ledgers in T4; "never sum OI across venues"; venue-specific funding-interval parameter (S095).
