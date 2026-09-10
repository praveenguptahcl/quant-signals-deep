# Reviewer 11 — Portfolio construction quant (read S050, T100 full; T030, S010, T002/T007/T031 skimmed; chapter template; RB-list; programmatic checks over all 200 chapters)

## CRITICAL (a)

1. No uniform signal-output contract anywhere. Ex: T100 §T2 claims base strategies "each emitting a standardized score per bar" — but no chapter defines it. Heterogeneous emissions: S050 z-score, S063 "output is a probability", S085 side s_t ∈ {−1,+1}, S081 Ψ ∈ [−1,1]. Fix: one canonical SIGNAL_VECTOR = {symbol, timestamp, direction ∈ {−1,0,+1}, score ∈ [−1,1], confidence ∈ [0,1], capital_scale, estimator_version, data_vintage} — required S0/T0 subsection in all 200 chapters.
2. Cross-chapter dependency maps not machine-parseable and internally inconsistent. S5 prose bullets; T3 two header variants (82 use "| Signal | Role | Weight / logic |", 18 use "| Signal | Role | Combination logic |"); 23/100 S-chapters have asymmetric links (e.g. S006 S5 lists T025 but T025's T3 never lists S006). Fix: normalize T3 header; require S5 bullets in machine form "- **T###** — role:"; CI script asserting S5↔T3 symmetry.
3. No per-module capacity or market-impact model field. Capacity hint in T1 only (strategies); signal chapters have zero capacity fields; no structured impact model (Kyle λ S010, Amihud R012 never wired as per-module inputs). Fix: required "Capacity & impact" subsection per chapter — max_notional(ADV, spread_regime), impact function reference, decay half-life.
4. Position sizing is buried prose, not a callable function. 85/100 have "**Position sizing.**" subheading; incompatible forms (T030 fixed 200 shares; T002 N=⌊R/stop_width⌋ R=$50; T031 0.25–1.0% NAV at 2σ). Fix: fenced sizing function per strategy — shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost) — formula stable, numbers example.
5. No portfolio-assembly layer: 200 modules, zero risk-budgeting framework. T100: "synthetic worked example, not a production book… No live capital allocation is described." Fix: capstone portfolio-construction chapter/section — allocation function (risk budgets from trailing covariance, correlation caps, gross/net constraints) with example parameters.

## MAJOR

6. T100's dependency table incomplete; real dependencies in prose. T100 T3 lists only S082/S086/S088; actual inputs T091/T093/T094/T096/T098 in prose below. Fix: every consumed signal/strategy in T3 table; header ID set == T3 ID set (CI-checkable).
7. Regime-efficacy modulation (R001–R050) has no per-chapter schema. Grep R001|R007|R014 in MASTER.md: 0 matches. Fix: required "Regime gates" field — regime IDs, gate logic (veto/halve/widen), RSV fields consumed.
8. No correlation/crowding/shared-input metadata per module. Fix: "Correlated with" and "Shares data feed with" ID lists + crowding-proxy field in header block.
9. T2 subsection coverage unreliable: Cost model 73/100, Entry rule 68/100, Exit rule 70/100, Risk limits 82/100. Fix: make Entry rule / Exit rule / Position sizing / Risk limits / Cost model mandatory labeled subsections of T2; CI-check presence.
10. Signal chapters blend signal validation with trading economics. Ex: S050 §S4 walks a full trade with four-component cost stack and position sizes — portfolio-layer decisions as signal mechanics. Fix: split S4 into S4a (signal computation — pure alpha) and S4b (illustrative economics, fenced portfolio-layer).
11. Interface naming inconsistent in mermaid diagrams ("per-bar signal vector" vs "per-print signal vector"). Fix: one canonical edge label (signal_vector[t]) defined in output-contract section.

## MINOR

12. T8 title variant breaks extraction ("Failure modes" 88 vs "Failure modes & pitfalls" 12). Fix: rename the 12.
13. T4 title variants (98 "(SYNTHETIC)" vs 2 "(SYNTHETIC, SIMULATED-ONLY)"). Fix: one title string.
14. Jargon-definition convention inconsistent (S050 inline vs T030 "Jargon, defined once" block). Fix: adopt T030 glossary-block convention in template.
15. RB-list agent-loop contract orphaned. Fix: reference the loop spec from template's data/infra section.
16. Verdict-table row labels differ between S1/T1; signal S1 has no Capacity row. Fix: add Capacity row to signal S1 table.

## Summary for parent
Gaps are all at chapter interfaces: no output contract (C1), non-parseable/inconsistent dependency maps (C2, M6), no capacity/impact fields (C3), sizing as prose not functions (C4), no portfolio-assembly layer (C5), regimes defined but referenced by zero chapters (M7). Fixing C1–C5 plus M7/M8 makes the compendium implementable as a multi-strategy book. Section numbering near-uniform (S1–S12 ×100, T1–T10 ×100).
