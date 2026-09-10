# Reviewer 06 — Options desk quant (read S070/S071 risk reversal, straddle-implied move; T093 options-to-equity lead; T049 UOA follower; skimmed T-VRP; RB-list R001/R002)

## CRITICAL

1. (a) No canonical options chain snapshot schema. Ex: S070 §S6 defines `chain: ts, expiry, strike, cp, bid, ask` inline — no OCC symbol, OI, volume, Greeks, underlying ref, dividend/rate inputs, settlement convention, halt/stale flags. Every options chapter reinvents its own ad-hoc schema. Fix: one shared ChainSnapshot schema appendix (OCC symbol, event_ts, asof_ts, expiry, strike, cp, exercise style, settlement, bid/ask/size, IV, greeks, OI, volume, spot, div yield, rate, halt/stale flags); every options chapter's S6/T5 references it.
2. (a) Greeks computation never specified as a model. Ex: S071 §S3 prints European BS delta with q; only American-note anywhere is buried in S070 §S6 checklist. Agent codes European BS → wrong deltas/pillars on all single names. Fix: "Greeks model" block per options chapter — pricing model (CRR vs Black-76), r/q sources, dividend model, American handling, validation tolerance.
3. (a) No machine field for minimum viable data tier — fail-closed requirements live in prose. Ex: T049 §T5 "UOA dies on delayed data… no 'stale sweep' mode" but nothing in the contract forbids wiring Tier-0 delayed chains. Fix: header field min_data_tier + fatal_if_below.
4. (a) Exercise/assignment are failure bullets, not code rules. Ex: T-VRP §T8 "7. Early exercise / dividends" → mitigate "prefer SPX"; pin-risk "never hold into expiry" at line 28008. Fix: "expiry/assignment machine rules" table — ex-div calendar source, early-exercise trigger formula, auto-exercise ITM threshold, expiry-day position rule, pin-risk guard.
5. (a) No backtest fill simulator contract. Feed granularity specified but no fill rules: bid/ask capture %, partial fills, no-fill on stale quotes, latency assumption. Fix: "backtest fill rules" block — fill price rule, partial fills, no-fill conditions, assumed latency.

## MAJOR

6. (a) Borrow mentioned but never a machine spec. Ex: T093 §T2 "Borrow: N/A in the worked example — hard-to-borrow names would charge multiples of 0.35%". Fix: standard borrow block — source feed, accrual formula, hard cutoff, buy-in note.
7. (a) Options cost model is narrative, not a ledger schema; margin absent. Ex: S071 §S10 wing spreads; VRP chapter admits "no margin requirement or financing drag" in optimism list; "margin" 109× in doc, zero modeled cost lines. Fix: "cost ledger schema" per chapter — per-leg spread capture, per-contract commission + exchange/clearing fees, OCC clearing, margin-financing drag formula.
8. (a) Dual timestamps (event vs vintage) required by prose, not schema. Ex: S071 §S10 "pin the snapshot vintage"; T049 §T5 "OI vintages (as-of, never revised)". Fix: mandate (event_ts, asof_ts) on every S6/T5 table + unit-test stub: joins use asof_ts ≤ signal_ts.
9. (a) Settlement conventions an afterthought. Ex: AM vs PM once (S073 checklist); S070 straddle math never states assumed settlement. Fix: "settlement convention" required row in every options chapter's data table.
10. (b) Sign/quoting conventions scattered, not registered. Ex: S071 repeats RR FX-vs-equity sign flip and delta conventions across 3 sections; §S12 "garbled render, do NOT code". Fix: top-of-chapter "Conventions register" box — every sign/quoting/delta convention in one glance.
11. (a) Zero regime cross-references — R001–R050 disconnected. grep for R-IDs in 36,207-line compendium returns 0. Fix: annotate every chapter's S1/T1 with applicable R-IDs + modulation direction (ordered annotation task still pending).
12. (a) Dividend model unspecified. Ex: S071 §S3 d₁ uses continuous q; ex-div handling in T8/T093 prose only. Fix: dividend-model field (discrete vs yield + calendar source) in S6/T5.

## MINOR

13. (b) Cross-chapter pointers lack section anchors. Ex: S071 §S10 "see S070" — hunt for the number. Fix: cite as "S070 §S10 cost blowup" (chapter + section) everywhere.
14. (b) Unverified items flagged inline (good) but no chapter-level roll-up. Fix: standard end-of-chapter "Open/unverified items" box + master tracker.
15. (a) No options-specific capacity field. Ex: T093 §T1 equity capacity $1–5M but nothing on wing-pillar depth (25Δ OI/quote size). Fix: "options capacity" (pillar OI depth, typical wing size) in T1.

## Keep (don't break)
S8/T6 buy-vs-build tiers answer "cheapest data source per module" (good); T4 ledgers fully costed with optimism lists; [example]/[documented] tagging and causal-timing statements first-class; "When it dies" verdicts give fast human risk reads.
