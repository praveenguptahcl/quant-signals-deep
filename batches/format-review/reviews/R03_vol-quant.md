# Reviewer 03 — Volatility quant (read S001, S002, T001 full; T002 skimmed; S004, S006, S008, S036, T010 skimmed; RB-list R001–R006 full)

## CRITICAL

1. (a) Annualization day-count never declared; chapters contradict. Ex: line 14465 annualizes RV with 252×Σrᵢ²; T010 §T2 uses √(T/365); RB-list R001 says "annualized" with no day-count. 252↔365 shifts vol ~17%. Fix: per-chapter Conventions block — day-count, return definition, time unit, timestamp zone.
2. (a) Return convention delegated instead of declared. Ex: S036 §S3 "simple returns; log is fine too — pick one and stay consistent." Fix: every chapter fixes its return definition in the math section; no opt-outs.
3. (a) No typed module interface per chapter. Units collide: S004's G* in cents, T001's mid in dollars, S002's Δmid in ticks, S001's Δm in dollars; T001's example reconciles by hand. Fix: Module contract table (input/output names, types, units, cadence) per chapter.
4. (a) "Example" marking not machine-detectable. ≥5 variants: (`example`) 696×, *example — not an institutional standard* 133×, [example] (RB-list only), "Default (example)" 65× vs "Default example" 16× vs "Default (example — not an institutional standard)" 7×. Fix: one machine-readable tag (fixed token + one table-header convention) on every literal threshold.
5. (a) Numerical edge cases unspecified (~4 divide-by-zero-type guards in 36k lines). Ex: ΔP ≈ OFI/(2D) with no D_k=0 rule; T001 N=⌊R/|P_entry−P_stop|⌋ zero stop-distance; z-scores with σ=0. Fix: edge-case row in every parameter table (zero-depth, zero-variance, empty-window, crossed-book).

## MAJOR

6. (a) No calibration procedures — only calibration verbs. "calibrat*" 261× but hand-waves. Ex: S002 §S3 Ridge λ "cross-validated (example)" — no fold scheme, metric, grid, acceptance. Fix: calibration recipe line per example parameter — search grid, objective metric, validation scheme, acceptance threshold.
7. (a) Estimator-disagreement specs exist only in RB-list, not signal chapters. Ex: S008 VPIN has no second estimator, tolerance, or UNKNOWN behavior. Fix: port RB fail-safe block into each S chapter — second estimator + tolerance + UNKNOWN rule.
8. (a) Vol-unit schizophrenia. Line 14465 RV "annualized in percent"; T010 vega "$/vol-point"; R002 mixes variance and vol points; 0.18 vs 18.0 alternating without decimal-vs-percent declaration. Fix: per-chapter units line in math section.
9. (a) Timestamp/timezone and latency budget not declared as build rules. Fix: Conventions block includes timestamp zone, DST rule, latency-budget field.
10. (b) Strategy chapters lack parameter tables; thresholds buried in prose. Ex: T001 embeds 10+ thresholds in T2 prose. Fix: T-chapters get the same Parameter/Symbol/Range/Default table as S-chapters.
11. (b) Worked example violates its own exit precedence. Ex: T001 §T4 trade 6 exits "+2.5 ticks" via time stop, but +2-tick profit target must fire first. Fix: QC gate replaying every worked example against stated rules (assertion, not eyeball).
12. (b) Worked example implements different formula than documented. Ex: S002 §S3 iOFI as PCA projection v₁ᵀ(OFI−μ) (unitless) but §S4 computes "iOFI (shares)" equal-weight sum. Fix: examples implement canonical formula; variants belong in formula section.
13. (a) Greeks contract missing where load-bearing. Ex: T010 §T2 "rebalance when |Δ| > 0.10 per straddle" — no pricing model, Δ units, same-model vega/θ. Fix: Pricing & greeks contract block for options chapters — model, r/q, per-contract vs per-share units, day-count.
14. (a) Regime chapters have no machine-readable hook into S/T chapters. Fix: each S/T chapter gets a Regime gates table — regime ID → affected parameter → adjustment rule.

## MINOR

15. (b) Strategy overrides of signal defaults undeclared. Ex: S001 defaults 1-s bars; T001 silently uses 100-event window + 15-min EWMA. Fix: T-chapters list parameter overrides of consumed signals.
16. (b) Corporate-action/halt handling in checklists, not the math. Fix: fold halt/split mask into math section as explicit edge-case rule.
17. (b) Provenance/chatbot source logs inflate chapter bodies. Fix: move source logs to appendix or hidden_files; keep S12 to verified sources.

## Notes for parent
- T chapters use T1–T10, not T1–T12 — section-count spec should be updated.
- Templates worth preserving: S004's G* contract (units in ¢, fit-window discipline); T010's dollar-P&L cost arithmetic.
- Merge headers "plot verified" (e.g. Stage 1/200 line 12) should be spot-checked against actual image files before trusting as QC evidence.
