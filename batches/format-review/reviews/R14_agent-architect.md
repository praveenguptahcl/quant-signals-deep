# Reviewer 14 — AI-agent systems architect (read S001, T001 full; skimmed S002, T002, RB-list.md; scripted lint over 200 chapters)

## CRITICAL (a)

1. Zero machine-parseable metadata. 0 YAML front-matter / JSON schema in 200 chapters. Only structured data is `## Stage N/200 — SID: title` header plus italic prose metadata line whose schema differs between S and T chapters. Fix: uniform YAML front-matter (id, kind, batch, provenance, family, signals[], regime_ids[], seed, plot-script path) in every chapter.
2. Chapters not self-contained — dangling cross-document references. T001 §T2: "All quantities use the MASTER.md signal definitions"; T002 §T2 invokes S004/S006/S014 formulas without restating; 105/200 chapters cite notes/cost-model.md §§2–6 (208 refs) for throughput/RAM/storage numbers. Fix: per-chapter "Dependencies" manifest inlining verbatim formulas/constants needed, or ship chapter with its dependency closure.
3. No acceptance criteria / definition of done. "acceptance criteria", "definition of done", "self-check" in 0/200 chapters. T3 ≤25-line sketch calls undefined functions (microprice(state_t), signed_volume_delta()) with no error handling/state persistence/timestamp ordering; S001 §S6 sketch has literal "..." placeholders. Fix: S13/T11 "Build contract" section — numbered pseudocode, explicit I/O schema, runnable self-check checklist.
4. No deterministic test fixtures. Only 11/200 chapters even mention test vectors (as words); 136/200 have no plot-script reference, 45/200 no seed; only 9 T-chapters "re-runnable", 0 S-chapters. Fix: tests/test_<SID>.py with fixtures per chapter (e.g. S001 10-event tape → cum OFI +1,820).

## MAJOR

5. Illustrative thresholds unmarked in 91/200 chapters. (example)/[example] convention exists but 91 chapters use it zero times ("fade |z| ≥ 2.0" bare). Fix: lint-enforce (example) marker on every non-documented number.
6. Prose-as-spec inside entry/exit rules. Ex: T001 §T2 "mid has not jumped > 1 tick in the last 5 seconds (example) — no chasing". Fix: restate every rule as Boolean expression in combination-logic block; ban prose-only conditions there.
7. Consumer chapters defer signal math instead of re-deriving. T001 §T2 defers to "the Cont–Kukanov–Stoikov piecewise rules" without restating the six e^b_n/e^a_n cases — T001 alone unbuildable. Fix: repeat canonical 6-line piecewise formula verbatim in every consuming chapter's §T2.
8. Worked examples are narrative arithmetic, not fixtures. No CSV of the 10-event tape, no expected-output table. Fix: fixtures/<SID>_tape.csv + expected outputs per worked example.
9. Feasibility numbers buried behind cross-document pointers. Fix: inline the 2–3 decisive numbers per chapter; keep cost-model citation as source link.
10. Chatbot-sourced evidence interleaved with peer-reviewed evidence. T001 §T7 includes "Imbalance-taker fee study (2025, per Grok Q-TB1-3)" — units explicitly unverified — in same table as Cont–Kukanov–Stoikov (2014). Fix: move all chatbot-sourced rows into separate "Unverified leads" table inside §S9/§T7.
11. Regime chapters promised, zero linkage. 0 R001–R050 references in any S/T chapter; RB-list.md's loop spec has no chapter-side anchor. Fix: regime_ids[] in front-matter now (provisional); one-line "Regime gating" row in §T2.
12. Provenance codes have no up-front legend. Fix: one legend in document header; codes in front-matter.
13. Smoothing/window parameters under-specified for reproduction. Ex: T001 §T2 "trailing 15-minute EWMA baseline" — no α/half-life. Fix: every rolling statistic gets (window, weighting, α/half-life, min-periods) as numbers.

## MINOR

14. Redundant section pairs (§S1 "Build-or-buy in one line" vs §S8; §T1 "Capacity hint" vs §T7 "Capacity"). Fix: one-liner a strict summary of the section, or drop it.
15. Mermaid diagrams presentation-only — no interface table per box. Fix: interface table under each diagram.
16. T chapters have 10 sections (T1–T10), S chapters 12 (S1–S12) — consistent within kind, but T lacks "Data required" and "Local build" as separate sections (folded into §T5). Fix: document the intentional asymmetry once, or align to 12.

## What's already good (keep)
S12/T10 "Source log + Unverified leads" segregation and synthetic-data labeling (SYNTHETIC, seed, "simulated only — requires MBO/ITCH"); §S10/§T8 failure-mode lists and honest "no published after-cost Sharpe" bottom lines. Per-chapter files exist in repo (batches/SB1/S001.md etc.) — chunk retrievability achievable at file level.
