# Reviewer 17 — Trading-cost analyst / TCA (read T001, T002, T100 full; skimmed RB-list.md; scripted checks across 100 T chapters)

One-line summary: strong cost honesty norms (T7 before/after-cost column, "Where the example is optimistic," "indicative — verify before budgeting") but no cost architecture: no callable cost function, no fee versioning, no single source of truth per chapter. An AI implementer gets 95 different prose paragraphs; a human auditor gets cost numbers scattered across 5+ sections.

## CRITICAL (a)

1. No cost model exists as a FUNCTION anywhere. Best case T100 §T2: "$80 per unit round-trip all-in" — flat constant, no inputs. Closest to formula is prose "temporary impact ≈ λ̂q²/2 + s/2·q + fees 0.003·q" — no venue input, no ADV normalization. Fix: COST block with callable signature expected_cost_bps(notional, adv_pct, venue, side, urgency) + reference implementation in chapter's plot script.
2. Zero fee-schedule versioning. 0 as-of dates on any cost assumption in 36,207 lines. Fix: every cost block carries fee_schedule_as_of: YYYY-MM-DD, venue, tier, source.
3. Working cost assumptions unlabeled despite marker taxonomy existing. T001/T002: "commission $0.005/share each way ($0.01 RT/share)" with NO example/indicative/[documented] marker — yet T001 §T10 admits "cost convention… adapted from Grok's TB1 answers" (chatbot-sourced). Fix: tag every cost-model value with existing taxonomy; unlabeled cost numbers fail validation.

## MAJOR

4. No single source of truth: cost restated in 5+ sections, sometimes contradicting. Ex: T050 §T2 two "Cost model" paragraphs back-to-back with different RT assumptions, no reconciliation. Fix: one COST block in T2; T4/T6/T7/T8 reference it by name — re-stating numbers elsewhere is validation failure.
5. Before/after-cost separation missing in 34/100 T7 tables. T044–T047, T061–T081 lack the column; cost basis buried in free-text caveats. Fix: Before/after-cost column mandatory in every T7/S9 table.
6. Fee-covering entry gate as code in 1/100 chapters. T002 §T3 has ecost <= 2*abs(dev); T001's equivalent only in T8 mitigation prose; T001's T3 has 0 cost-gate terms. Fix: T3 pseudocode must include cost gate as executable predicate — default expected_cost_bps(...) <= k * edge_bps.
7. Capacity is prose, never parameterized. T001 T1: "Near zero for a non-colocated taker"; T100 T1: "$5–20M (example)". Fix: capacity as max_notional derived from cost function's impact parameters (participation cap × ADV), not prose hint.
8. T4 P&L arithmetic-reproducible but not cost-function-reproducible. T001 T4 (gross +$550 / comm −$600 / net −$50) and T002 T4 (gross +$245 / −$300 / −$55) check out line-by-line, but cost column is assumed constant, never a function call. Fix: each T4 trade row shows the cost-function call (inputs → bps → $), not just a cost column.
9. Measured vs assumed costs visually identical. Only 2 [measured]-style markers in 36k lines. Fix: add [measured] to marker taxonomy; require provenance on every T4 cost figure.
10. Borrow-cost convention inconsistent across chapters. T001 T2 "no borrow fee" (reason unstated); others 2.0%/ann; others "No borrow assumed — GC names only." Fix: borrow_bps_per_day required cost-block field; 0 must carry explicit reason.
11. Taker/maker side not a structured field. Nothing machine-readable binds fee direction to execution style. Fix: side: taker | maker | mixed as required cost-block field; fee components keyed off it.
12. R-chapter format defines no cost interface. RB-list.md has no cost block; R010 (spread regime) has no contract for exposing its cost implication to T-chapter cost blocks. Fix: fifth R-block — "Cost interface: regime state → cost-function adjustment" — before R chapters are written.

## MINOR

13. Best cost-model form in doc is not the T-chapter standard. Explicit 4-component stack (spread + fees + borrow + impact, per-component $) in only 3 chapters (all S-chapters, e.g. S049: "spread ≈ $40; commissions/fees ≈ $20; borrow ≈ $3; impact/slippage ≈ $20. All-in ≈ $83"). Fix: promote 4-component stack to mandatory T2 cost-block schema.
14. Marker taxonomy section-gated, not global. "Indicative — verify before budgeting" 576× but only on T6 vendor pricing; only 2 T2 cost paragraphs use "indicative". Fix: apply taxonomy uniformly, or declare COST block the single marked zone and validate it.
15. Slippage optimism not in cost units or fixed place. Fix: standardize "known-optimistic assumptions" checklist attached to every T4, quantified in bps.
16. T6 venue rows quote data prices but never the venue's fee. Fix: each T6 venue row carries that venue's taker/maker fee as indicative figure next to data price.

Caveats: T4 arithmetic spot-verified for T001, T002 (both check); scripted counts exact (95/100 cost blocks, 34 T7 tables lack column, 1 gate-as-code). S-chapters only skimmed via S049. Biggest structural gap: #1 (no callable cost function).
