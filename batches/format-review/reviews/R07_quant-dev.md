# Reviewer 07 — Quant developer (read S003, S020, T003, T075 full; RB-list; notes/chapter-template.md; regex census over 200 chapters)

## CRITICAL (a)

1. No code interface spec in any chapter. 0/200 define a function/class signature, typed inputs/outputs, or config object. Ex: S003 §S3 formula I_t = (Qb−Qa)/(Qb+Qa); §S6 polars ingest sketch — but no module contract (input event struct, output type, call cadence). Fix: "Interface contract" subsection — typed signature + config dataclass + return type — in S3/T3.
2. Dependencies are prose names, not callable contracts. Ex: T003 header "Signals S008, S021, S032"; sketch calls VPIN(trailing 50 buckets) but S008 defines no callable VPIN() (args, returns, state). S-chapters have no dependency header at all. Fix: machine-readable dependency table per chapter (callee ID + function name + arg/return types + version); S chapters get the same header line T chapters have.
3. No per-chapter test/acceptance command. 0 pytest targets, 0 acceptance criteria. batches/SB1/plot_S003.py regenerates charts, not tests; S4 hand-checks are not machine assertions. Fix: one "Acceptance" line per chapter (e.g. pytest tests/test_S003.py) + input/output fixture vector with expected values.
4. No error taxonomy or missing-data output convention. 0 chapters define error types; 5/200 mention "missing data" as policy. Ex: S003 §S6 silently .filter((qb+qa)>0) — emit NaN? skip? carry-forward? Fix: shared error taxonomy (DataStale, EmptyBook, FeedGap…) + per-chapter invalid-input output convention in the interface contract.
5. No chapter versioning. Provenance tags [D]/[SR]/[D/SR] track evidence source, not contract version. Fix: version: x.y.z + one-line changelog in each chapter header; pin consumed-signal versions in dependency table.

## MAJOR (a)

6. Config parameters scattered, all (example), none in a config object. Ex: κ=±0.5 in S003's S3 table AND hardcoded 0.5 in S6 sketch; T003's gates in T2 prose, T3 table, and sketch. Fix: single "Config" block per chapter — every parameter with type, default, allowed range, status.
7. Determinism is a bare seed with no RNG binding. "seed 42" but only plot scripts name np.random.default_rng; no numpy pin; no statement outputs reproducible from (seed, inputs). Fix: RNG algorithm + library version in chapter; acceptance test asserts byte-identical regeneration.
8. No canonical input schema. Ex: S003 sketch Databento columns (bid_sz_00); S020 generic (price, size, symbol). Fix: one canonical event/bar schema doc; each chapter maps its fields to it.
9. Code sketches are ingest code, not the signal function. 96/100 S chapters' ```python is batch ingest; signal math inline or prose. Fix: code block must be the module's core function with typed signature, covering documented edge cases (empty book, zero denominator, stale input).
10. Regime wiring has no structured slot. RB-list.md defines RSV + 5 fail-safes, but chapters have only prose "Regimes where it fails"; 0 R-ID references in 200 chapters. Fix: "Regime interaction" table (R-ID, modulation direction, UNKNOWN-state behavior) in S/T templates before annotation starts.

## MAJOR (b)

11. Internal numeric contradiction between sections. Ex: T075 §T2 "taker fee 5 bps/side" vs §T4 ledger "12.65 bps round-trip" ($33.59 expected vs −$8.50 modeled). Fix: one cost-model table referenced by T2 and T4; declare the ledger's rate binding.
12. Every threshold (example) with no calibration status. Fix: per-parameter status tag (calibrated-OOS / literature / placeholder).
13. Risk-budget math split across sections. Ex: T003 §T2 sizing on expected fill; §T4 trade shows $200 budget exceeded 1.5% from gap-through + exit spread — three sections apart. Fix: fill-assumption → actual-risk accounting adjacent to sizing rule.
14. S→S dependencies invisible. T→S structured; S020→S007 quote rule and S003↔S004 identity only in prose. Fix: same dependency header line for S chapters.
15. Worked examples sometimes demonstrate the conclusion. Ex: T003 §T4 vetoed trade "scripted to have lost". Fix: each worked example includes one case where the chapter's own mechanism backfires.

## MINOR (b)

16. Inconsistent subsections across chapters. Fix: lock template's subsection checklist; mark absent subsections "none" explicitly.
17. Mermaid diagrams restate text instead of specifying behavior. Fix: state/event diagrams with exact trigger events.
18. Unverified-leads blocks per-chapter with no global index. Fix: one global unverified-leads index file.

## Verified strengths (don't regress)
Stage↔ID mapping perfectly consistent (Stage N = S0NN; Stage 100+M = T0MM) — keep as machine key. t→t+1 stated in every chapter; data tables give per-field types/granularity; (example)/"indicative"/SYNTHETIC labeling consistent; plot scripts real, seeded, reproducible (np.random.default_rng).
