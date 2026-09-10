# Reviewer 10 — Backtest-platform architect (read S003, S020 full; T003, T100 skimmed; RB-list.md lookahead; S001/S004/S016/S047 timing conventions)

## CRITICAL

1. (a) No mandatory fill-model contract per strategy. Ex: T003 §T2 "Cost model" has commission + assumed 2¢ spread + gap-through fill, but no latency (ms), partial-fill probability, market-impact function, queue-position model; §T4 then admits "Bar-open fills assumed available in full size, no partial fills." Fix: mandatory "Fill model" parameter table in every T2 — order type, latency assumption (ms), partial-fill probability, impact model name, queue-position modeled y/n.
2. (a) Causality is prose, not a machine-checkable assertion. Ex: S003 §S3 "no earlier than t+1" trailing paragraph; T003 §T2 "fill at the open of bar t+1". Fix: code-level contract line in every T3 pseudocode (fill := open[t+1]; assert fill_event > signal_event) + mandatory unit-test template "no signal-bar fills".
3. (a) No per-strategy "minimum viable backtest" spec. Ex: T003 §T7 headline Zarattini 2.81 Sharpe is commission-only $25k book publication-sample RVOL sort; chapter defines no required OOS protocol. Fix: Backtest acceptance checklist per T7 — walk-forward + embargo, min OOS trades, cost level (L0–L3), DSR/PBO or "not claimed".
4. (a) Worked examples synthetic-labeled but not type-labeled — accounting demos masquerade as method validation. Ex: T100 §T4 meta p̂ values "assigned, not estimated"; T003 §T4 vetoed break "scripted to have lost". Fix: machine-readable header per S4/T4: TYPE=accounting-demo vs validation-run + seed= + script= fields.
5. (a) Regime lookahead rule global but no per-indicator lag contract. Ex: R001 (daily close + 30-min refresh), R014 (per-bucket VPIN), R035 (earnings timestamp) never reduce to indicator_ts, decision_ts, min_bar_offset, vintage_field, compatible bar frequencies. Fix: every R-chapter gets a Lag contract block.
6. (a) No selection/multiplicity disclosure. Ex: T003 §T7 reports top-20 RVOL sort Sharpe 2.81 without variant count (multiple OR windows "decay to 0.21/0.40"); DSR/PBO only via S086 note "0/42 clear the Deflated Sharpe bar". Fix: Selection disclosure field in T7 — variants tested, selection rule, multiplicity-adjusted metric or "not computed".

## MAJOR

7. (a) Cost assumptions inconsistent across chapters — no canonical cost-level hierarchy. Ex: T003 §T2 2¢ spread both sides; T004 "gap-through on entry bar only in conservative variant". Fix: canonical cost levels L0 (mid, no cost) → L1 (commission-only) → L2 (+spread) → L3 (+slippage/impact/borrow); every T4/T7 declares its level.
8. (a) No maker/taker fill-type taxonomy with adverse-fill rates. Ex: T022 passive maker, S047 bid-ask-bounce; no chapter declares fill type as parameter or adverse-fill probability. Fix: mandatory fill-type declaration (taker/maker/both) + adverse-fill probability for maker legs.
9. (b) Everything tagged `example`, so nothing is actually specified. Ex: T003 §T2 ~20 inline example tags; no "author's recommended starting config" vs "illustrative placeholder" distinction. Fix: two-tier tagging — `default` (recommended starting config) vs `example` (must calibrate).
10. (b) Before/after-cost status is prose, not a scannable token. Ex: T003 §T7 "Sharpe 2.81" while qualifier "no spread, impact, or borrow model" is a separate cell. Fix: standardize cost column to single tokens BEFORE-COST / COMM-ONLY / FULL-COST.
11. (b) Regime gating buried in failure-mode prose. Ex: S003 §S10.8 "toxicity overlay (VPIN, S008)" mitigation bullet. Fix: Regime-gate table (R-ID, gate direction improve/die, min lag in chapter bar units) in S10/T8.
12. (b) Timing-contract wording/placement inconsistent. Ex: S003 §S3 "Causal timing:" paragraph vs S004 two sentences later in different words vs T003 bar-based. Fix: standard one-line "Timing contract" box at top of every S3/T2: signal@t (5-min bars, ET) → earliest fill @open(t+1).
13. (b) Failure-mode mitigations cite techniques with no acceptance criteria. Ex: S003 §S10.7 "Mitigation: walk-forward" — no folds, embargo, pass/fail. Fix: every mitigation names a quantified acceptance test or points to T7 checklist.
14. (a) Signal data specs lack staleness/timeout fields — RB-list fail-safes F1–F5 not wired into S/T. Fix: Staleness/timeout row in every S6; T5 declares F1–F5 fail-safe mapping (UNKNOWN → restrictive).
15. (a) Timestamp domain declared inconsistently — no mandatory clock row. Fix: mandatory "Clock / timestamp domain" row in S6 (exchange ts / SIP ts / consolidated; sync rule; skew budget).

## MINOR

16. (b) T100 title implies authority its text disclaims. Fix: standardize scope banner on meta/assembly chapters: "Assembly demo — not a trade recommendation" in T1 verdict table.
17. (b) Seed/script provenance detached from readable copy. Fix: render script paths as repo-root-absolute references in readable copy.

## Keep (don't break)
SYNTHETIC labeling with seeds; [example] vs [documented] convention; before/after-cost column; "Where the example is optimistic" blocks (make mandatory).
