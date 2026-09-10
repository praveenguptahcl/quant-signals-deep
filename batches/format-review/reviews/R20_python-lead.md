# Reviewer 20 — Python research-stack lead (read S001, T001 full; skimmed S002; RB-list.md; README; build log; actual plot scripts)

## CRITICAL (a)

1. No environment spec — the doc's own stack is not reproducible. No requirements.txt/environment.yml/pinned versions; import polars fails on build VM (only numpy 1.26.4/pandas 2.1.4/matplotlib 3.6.3) yet chapters prescribe "Python+polars" (S001 §S6) and import databento. Fix: pinned requirements.txt + minimum Python in repo; 3-line setup block referenced from every chapter.
2. Placeholder code in canonical "how to build it" section. S001 §S6 contains literal ellipses: .with_columns(pb_l=pl.col("pb").shift(1), ...) — prose wearing code formatting. Fix: complete code in §S6, or label "fill in" and point to complete reference implementation.
3. No testable output contract per chapter. No output frame schema (columns, dtypes, index, cadence) and no acceptance assertions. Fix: "Output contract + self-check" box per chapter — exact output columns/dtypes/cadence + 1–3 assert statements.
4. Referenced scripts dangle in the distributed copy. Chapters cite batches/SB1/plot_S001.py (65 refs repo-wide); reader's copy at ~/workspace/your_files/quant-signals-compendium/ ships only .md + images/ — no batches/. Fix: bundle batches/ with distributed copy, or repo-root-relative paths with "scripts live in the repo" note.

## MAJOR

5. No "run this to verify" command per chapter. plot_S001.py has no CLI (SEED hardcoded, no argparse); only "batches/SB1/plot_S001.py, seed 42" parenthetical. Fix: one-liner per chapter — python batches/SB1/plot_S001.py # → images/S001_example.png, exit 0, tape checksum ….
6. S002 §S6 schema and code disagree. Comment block declares schema (ts, symbol, action, side, level, price, size); code uses bid_px, bid_sz, ask_px, ask_sz. level_ofi(g) never shows group-by producing g. Fix: one canonical input-schema block per chapter; all code uses exactly those columns.
7. S002's worked example implements the wrong variant. §S3 canonical: PCA-integrated OFI (iOFI = v₁ᵀ(OFI−μ)); §S4 table computed with equal-weight sum — the "crude" variant §S3 argues against. Fix: worked example must use canonical method; variants get separate labeled mini-examples.
8. Strategy chapters have no parameter table. Signal chapters tabulate; T001 buries every threshold in §T2 prose. Fix: strategy chapters get same parameter table (parameter, symbol, value, example-marked, sensitivity).
9. In-chapter cross-references are plain text, not links. "T001 — …", "see S089" unlinked; only 200 ](#stage-…) anchors in file are ToC entries. Fix: link every S###/T###/R### mention to its stage anchor.
10. Multi-ticker readiness missing. S001 §S6 sorts by ts_event then shift(1) with no partition key — correct only for single-symbol aapl_mbp1.parquet. Fix: state partition keys (symbol, date); require .over("symbol","date") / group-by in event-state code.
11. Compute pattern per chapter unstated. Polars batch code vs event-loop discussion; no chapter says streaming state machine or vectorized batch recompute, nor complexity bound. Fix: one line per chapter — "streaming O(1)/event" or "vectorized batch recompute" + throughput envelope.
12. Cost verdict buried. After-cost conclusion in mid-§S9 prose ("Honest bottom line"), separated from §S10 failure modes and §S1 "When it dies." Fix: one risk box per chapter — before/after-cost evidence + "when it dies", adjacent.

## MINOR

13. §S12 process metadata pollutes reference tail. S001 §S12 ~25 lines of chatbot autopsy after Sources. Fix: move to appendix or collapse.
14. Inconsistent §S1 verdict table shape (S001 2-col vertical; S002 4-col horizontal). Fix: enforce one template.
15. Acronym expansions repeat per chapter. Fix: global glossary; expand once per chapter max.
16. Seeds deterministic but not overridable. SEED=42 hardcoded; no --seed CLI. Fix: --seed CLI arg; document seed convention in one place.
17. Cross-document refs dangle for standalone readers ("notes/cost-model.md §4", "S088", "cost-model §5"). Fix: resolve or footnote in distribution build.

Notes: RB-list.md is the strongest format in the repo — [documented] vs [example] threshold convention, lookahead rule, fail-safes F1–F5 up front. S/T chapters should adopt its conventions (esp. [documented]/[example] tagging and a stated output contract). Did not assess research correctness, only information architecture.
