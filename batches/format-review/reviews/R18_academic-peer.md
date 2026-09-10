# Reviewer 18 — Python research-stack lead (read S001, S002 full; T001, T100 skimmed; RB-list.md threshold convention; chapter-template.md)

## CRITICAL

1. (a) No replication recipe block. Ex: S001 §S4 "synthetic (batches/SB1/plot_S001.py, seed 42)" — no single block stating script + seed + lib versions + data vintage. "replication recipe" appears 0× in MASTER.md. Fix: §S4/T4 machine-readable `Repro:` block (script, seed, commit, lib pins, data vintage or none-synthetic).
2. (a) Per-claim provenance tagging NOT machine-complete. Tag set isn't one fixed enum (`(example)` vs `[example]` vs plain text). Untagged quantitative claims: S001 §S7 "~100–500k events/sec", "2–8 GB/symbol-day", "20–60 h ≈ $3,000–9,000". Fix: one enum ([documented]/[example]/[unverified]/[internal-est]) + require on every numeric claim + linter.
3. (a) Seed convention broken. Workflow says seed 7; chapters report 42, 101, 20260902, 200; Stage-8 build log claims "plot verified (seed 7)". Fix: enforce one seed everywhere or record actual seed in Repro: block.
4. (b) Provenance code chapter-level only, but chapters are mixed. Ex: S001 header [D] but §S9 cites third-party GitHub replication ("replication quality unverified") and quotes Duck.ai phrasing. Fix: per-section provenance tags, not one per chapter.

## MAJOR

5. (a/b) Sources vs Unverified-leads boundary leaks. Ex: T001 §T7 row cites Grok study with "units unverified" inside the main evidence table; S002 §S12 re-admits chatbot numbers "with printed-total discrepancy noted". Fix: never cite chatbot-only items in main tables; refer only to Unverified-leads block.
6. (a) Cross-references one-way and unversioned. Fix: per-chapter "Dependencies" manifest — chapter IDs consumed + provenance tags + frozen MASTER commit hash.
7. (b) Failure-mode mitigations untestable. Ex: S001 §S10 #8 "Mitigation: S6 checklist; drop crossed/locked quotes; halt-aware masks" — no acceptance test. Fix: each failure mode gets a `check:` line (invariant + where to assert).
8. (a) Parameter tables mix roles without a decision table. Fix: add "tuning order + freeze criteria" row to every parameter table.
9. (b) Mermaid diagrams format-inconsistent (mixed \n vs <br/> escaping; flowchart LR vs TD). Fix: one escaping convention in visual-spec.md + linter.
10. (b) Success-ratio sections hide the answer in tables — honest bottom line comes ~200 words after 4-row table. Fix: lead each efficacy section with 2-line "verdict first" box; tables as appendix detail.

## MINOR

11. (a) Data-vintage language prose-only. Fix: add `Vintage` column to every data-spec table.
12. (b) Capacity and cost numbers scattered across 4 sections. Fix: one "total cost of ownership" summary box per chapter.
13. (a) Chart-caption honesty varies. T100 §T9 watermark caption excellent; S001 §S11 has no such caption. Fix: require T100-style synthetic-data caption on every §S11/§T9 figure.
14. (b) Regime chapters introduce a third tag convention. Fix: adopt RB-list.md's tag set + RSV schema as single document-wide standard before R-chapter merges.
15. (b) "Example" vs "documented" flips between draft passes. Fix: inherited citations carry [inherited, unverified-this-pass] inline.
16. (a) Ingest sketches partial and unpinnable (… ellipses). Fix: companion runnable file in scripts/ or explicit "sketch-only — not runnable" flag.

## Net assessment
Skeleton strong (Sources/Unverified-leads split, "simulated only" tags, RB-list conventions = good academic hygiene). Provenance must be claim-grained not chapter-grained; reproducibility metadata must sit in one block.
