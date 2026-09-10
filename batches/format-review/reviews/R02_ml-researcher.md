# Reviewer 02 — ML researcher

## CRITICAL

1. (a) No feature/label contract per chapter. Ex: S001 §S3: horizon h = "500 ms — example", no label definition (forward-return horizon, tick-vs-bps units, timestamping). Fix: mandatory "Label contract" block — target variable, horizon, units, causal timestamping.
2. (a) No train/validation/test split spec per chapter. Prose "purged/embargoed validation (S088)" but no split dates, walk-forward cadence, fold count, embargo length. Note: S088's worked example removes the FIRST 3 test events vs de Prado's standard (last train observations) — the (S088) pointer is implementationally ambiguous. Fix: per-chapter "Validation protocol" block — split type, folds, purge/embargo lengths, convention side, data windows.
3. (a) t→t+1 causality stated but scattered, not machine-extractable. No fixed identically-worded "Causality contract" at a fixed section; RB-list.md's formal lookahead rule has no per-chapter counterpart. Fix: one identically-worded Causality block in the same subsection of every chapter.
4. (a) No evaluation-metric definitions or acceptance thresholds. T7 tables report prediction R² (not after-cost P&L); synthetic walks explicitly "not a backtest". "Working module" undefined. Fix: per-chapter "Acceptance criteria" — named metrics + formulas + pass thresholds on held-out period.

## MAJOR

5. (a) Parameter tables conflate FIXED vs CALIBRATE vs EXAMPLE under one `example` marker. Ex: S002 §S3 ridge λ default "cross-validated (example)" with no CV scheme. Fix: add "Status" column: FIXED / CALIBRATE (with protocol pointer) / EXAMPLE.
6. (a) Fitted components lack fit protocols and fit-quality acceptance. Ex: T002 G* bins — bin edges, symmetrization checks, fit-failure criteria are prose. Fix: fit-window spec, CV/estimation scheme, fit-quality acceptance checks.
7. (a) Cross-chapter refs are prose, not a versioned dependency graph. Ex: T001 re-derives z^OFI with 15-min EWMA while S001's table lists only "depth-normed z-score — example" with no halflife → strategy invents the feature instead of calling a pinned interface. Fix: per-signal "Output schema" block (columns, dtypes, causality, version); strategies import by ID+version, never re-derive.
8. (a) No per-chapter unit-test invariants. Ex: S001 §S4 hand-checks are narrative, not stated invariants (e.g. OFI antisymmetry under bid/ask swap). Fix: per-chapter "Invariants" bullet list.
9. (b) "No after-cost edge" verdict structurally demoted below build instructions. Ex: T001's "no documented positive after-cost edge" (T7) sits below the full T2–T4 build spec. Fix: promote tradability verdict badge (PREDICTIVE-FEATURE-ONLY vs AFTER-COST-EDGE) into S1/T1.
10. (a) 22-item QC gate machine-readability is internal-only. Fix: append the machine-checkable QC subset as a per-chapter checklist block.

## MINOR

11. (b) Verdict-table layout inconsistent across chapters. Fix: lock one S1/T1 layout for all 200.
12. (a) Worked-example script paths don't resolve from the delivered copy (no batches/ dir); seed conventions drift (42 vs 20260902 vs 88088). Fix: bundle scripts or pin canonical repo-relative paths + one seed convention.
13. (b) Duplicate statements of the same rule invite audit drift. Fix: state each rule once in its canonical section; cross-reference.
14. (b) Provenance tag [D] legend not repeated. Fix: one-line provenance legend in every chapter header block.

## Caveats
- Synthetic-example labeling is genuinely good (278 "SYNTHETIC" banners) — NOT a finding.
- The corpus is honest in prose (contemporaneous-vs-forward, before-vs-after-cost); the gap is none of it is machine-extractable.
