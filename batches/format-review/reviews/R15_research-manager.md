# Reviewer 15 — Research manager (read S001, T001, T002 full; skimmed S002, S003, S020, T050, RB-list.md, cost-model.md; machine-checked 200 chapters)

Headline: chapter content strong (honest bottom lines, causality discipline, example-flagging). Format not manager- or machine-actionable: triage metadata exists only as prose, cross-links one-third broken, and neither named consumer can do their job — agent-builder cannot sequence/size the work from one chapter, human cannot kill/keep a chapter in 5 minutes.

## CRITICAL

1. No machine-readable per-chapter metadata block. Ex: S001 hours buried mid-S7 "Engineering time: Tier M (plan §6) → 20–60 h"; T062 "40–100 hours at $150/hr" in T5; S097 "(cost-model: 60–200 engineering hours…)" tier as bold-wrapped "Tier **H**"; 30 build sections lack a Tier letter entirely (S011, S013, T044–T045, T061–T080 group). Fix: mandatory YAML frontmatter — tier, hours_lo/hi, data_tier, latency_class, risk_class, maturity, edge_verdict.
2. No dependency DAG / build order. 64 T→S links unreciprocated (T001 consumes S004 — S004's S5 omits T001; T008/T022 consume S001 — S001's S5 omits both); 27 S→T links likewise. Fix: one machine-readable edge list as single source of truth; generate S5/T3 tables from it; publish computed build tier (1 = leaf signals first).
3. No staged milestones per chapter. Prototype→research-grade→production staging in only 4/200 build sections (S022, S023, S026, S070). Fix: three hour bands per chapter — prototype / research-grade / production.
4. No triage card: no build-first/skip/kill metadata. Kill signal buried at end of T7 (T001's bottom line ~7,500 words in); missing entirely in 32 T-chapters' T7 and 21 S-chapters' S9. Fix: fixed 5-field triage card under chapter header — edge verdict · build cost · data cost · latency class · risk class.
5. No standard module interface contract for the AI builder. T3 combination-logic pseudocode absent in T071–T080 (all ten lack any code block in T3); S-chapters only ingest sketches in S6, no function signature/I/O schema/timing guarantee. Fix: mandatory `## API contract` block per chapter — signature, inputs/outputs, causality guarantee, statefulness.
6. Regime annotations missing: 0/200 chapters reference R001–R050. Fix: applicable_regimes: [R001, …] + one-line impact note in each chapter header block.

## MAJOR (b/human mostly)

7. Honest bottom line missing/mislabeled in 53/200 chapters. 21 S-chapters lack it in S9; 32 T-chapters lack it in T7; "**Bottom line:**" vs "**Honest bottom line.**" Fix: required, fixed-label subsection as last paragraph of every S9/T7.
8. T-schema is T1–T10, not the documented T1–T12 (task brief says T1–T12). T8 titled "Failure modes" in 88 chapters, "Failure modes & pitfalls" in 12. Fix: reconcile schema doc with actual 10 sections; normalize T8 title.
9. S1 verdict table has two layouts (93 chapters 2-col bold-row; 7 chapters 4-col header-row; T1 third variant). Fix: one canonical S1/T1 triage table schema.
10. Effort fields not comparable. ≥4 phrasings; T018–T020, T044–T045, T081–T090 no hour band; Tier letter missing in 30 sections. Fix: canonical line `Tier M · 20–60 h · $3k–9k loaded` in every build section.
11. Data cost not a single comparable field. No per-chapter "research data spend $/mo" summary. Fix: one-line data-cost field in triage card (research $/mo + production $/mo).
12. Research-grade vs production-ready status never stated. "production-ready" 0× in 36,207 lines. Fix: explicit maturity: field (concept / research-grade / paper-validated / production-ready).
13. Cross-reference integrity broken for human navigation. 64 T→S links no reciprocal S5; 27 S→T no reciprocal T3. Fix: generate S5/T3 from single edge list.
14. No acceptance criteria for agent-builder. S4/T4 worked examples re-runnable but explicitly "not a backtest"; no pass/fail criteria. Fix: per-chapter acceptance: block — smoke test (S4/T4 reproduction tolerance) + one validation gate.

## MINOR

15. Latency class and risk class unnamed. Fix: latency_class (µs/ms/sec/min/daily) and risk_class fields in triage card.
16. Capacity and edge verdicts qualitative, not comparable. Fix: capacity as rough $ band; edge_verdict fixed enum in triage card.

Note: highest-leverage single intervention — add the machine-readable header block (C1); unlocks C2–C4, M4–M6, m1–m2 in one pass.
