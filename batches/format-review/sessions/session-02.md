# Session 02 — Causality / backtesting / execution / costs
**Attending (paper reviews):** R10 backtest-arch · R05 execution-quant · R17 TCA ·
R06 options-desk · R08 crypto · R04 hft-infra
**Date:** 2026-09-10 · **Decision status:** all items DECIDED unless marked OPEN

## 1. Cost block form
- **DECIDED — both, not either/or.** Every T chapter carries a mandatory structured
  COST block in §T2 as the single source of truth, plus a callable cost function
  `expected_cost_bps(notional, adv_pct, venue, side, urgency)` with a reference
  implementation in the chapter's plot script (R17-1, R04-2).
- **DECIDED — mandatory COST block fields:** 4-component stack (spread + fees +
  borrow + impact, per-component $/bps) (R17-13); `fee_schedule_as_of: YYYY-MM-DD`
  + venue + tier + source (R17-2); `side: taker | maker | mixed` with fee components
  keyed off it (R17-11); `borrow_bps_per_day` — 0 must carry an explicit reason
  (R17-10); every value tagged with the existing marker taxonomy plus new
  **[measured]** (R17-3, R17-9).
- **DECIDED — no restating.** T4/T6/T7/T8 reference the COST block by name; re-stating
  numbers elsewhere is a validation failure (R17-4, R08-6).
- **DECIDED — canonical cost levels** L0 (mid, no cost) → L1 (commission-only) →
  L2 (+spread) → L3 (+slippage/impact/borrow); every T4/T7 declares its level
  (R10-7). Before/after-cost collapses to single tokens BEFORE-COST / COMM-ONLY /
  FULL-COST (R10-10). T7/S9 evidence tables all carry the column (R17-5, R08-14).
- **DECIDED — fifth R-block:** "Cost interface: regime state → cost-function
  adjustment" — regimes expose how they modulate cost parameters before R chapters
  are written (R17-12); every R chapter also gets a lag contract (indicator_ts,
  decision_ts, min_bar_offset, vintage_field) (R10-5).

## 2. Fee-covering entry gate
- **DECIDED — executable predicate required in T3 pseudocode**, not prose:
  `expected_cost_bps(...) <= k * edge_bps` with `k` a chapter parameter (example
  default, must-calibrate) (R17-6, R05-12 single-source-of-truth).
- **DECIDED — capacity derived, not prose:** `max_notional` from the cost function's
  impact parameters (participation cap × ADV) (R17-7).

## 3. Backtest / evaluation protocol (minimum standards)
- **DECIDED — per-chapter backtest acceptance checklist** (T7): walk-forward +
  embargo (folds, embargo length, pass/fail), min OOS trades, cost level (L0–L3),
  multiplicity-adjusted metric (DSR/PBO) or "not computed" with variant count and
  selection rule disclosed (R10-3, R10-6).
- **DECIDED — causality as code, not prose:** T3 carries `fill := open[t+1];
  assert fill_event > signal_event`; mandatory unit test "no signal-bar fills"
  (R10-2). One-line Timing-contract box at top of every S3/T2:
  `signal@t (bars, tz) → earliest fill @open(t+1)` (R10-12). Clock/timestamp domain
  row mandatory in S6 (R10-15, R04-7).
- **DECIDED — deterministic fixtures + test vectors:** every S4/T4 machine-readable
  header `TYPE=accounting-demo | validation-run` + seed + script (R10-4); canonical
  input-fixture CSV + expected outputs + tolerance per chapter (R04-4); each T4 trade
  row shows the cost-function call (inputs → bps → $), not a bare cost column
  (R17-8); 3–5 acceptance tests per chapter, T4 worked numbers reused as fixtures
  (R08-11); per-T4 "known-optimistic assumptions" checklist quantified in bps
  (R17-15).
- **DECIDED — mandatory fill-model table per T2** (R10-1): order type, latency
  assumption (ms), partial-fill probability, impact model name, queue-position
  modeled y/n, fill-type taker/maker/both + adverse-fill probability for maker legs
  (R10-8), plus backtest fill rules (fill-price rule, no-fill on stale quotes,
  partial-fill handling) (R06-5).
- **DECIDED — `default` vs `example` tagging:** recommended starting config vs
  must-calibrate placeholder; cost levels and gates ship as `default` (R10-9).

## 4. Strategy execution contract vs "intentions only" doctrine
- **DECIDED — boundary is doctrine, stated twice:** global preamble sentence
  "strategies emit trading intentions only and never touch orders" + per-chapter
  "may emit / must NOT emit" line (R05-3).
- **DECIDED — S-modules emit Signal{`symbol, direction∈{long,short,flat},
  confidence∈[0,1], capital∈[0,1}`} + cadence + UNKNOWN/stale behavior with
  max-staleness TTL; mandated Module-contract box per S chapter
  `tick(symbol, events≤t) → Signal` (R05-1, R05-6, R05-15); signal state vector
  versioned like RSV (estimator_version, data_vintage, computed_at) (R05-7).
- **DECIDED — T-modules emit order intents, not orders.** The T-module owns the full
  execution contract: global OrderTicket schema (order_id, symbol, side, qty,
  order_type, limit_px, TIF, venue/router, strategy_ref, parent/child) (R05-2);
  child-order state machine + partial-fill policy (rest/chase/leave-remainder) +
  cancel-replace rules per T chapter (R05-4); cost simulation and fill simulation
  live in the T-module/execution harness, never in the signal path.
- **DECIDED — sizing contract:** each T states `(risk_budget, signal_confidence) →
  notional` (R05-13); instrument config (tick_size, lot_size, currency, session_tz)
  mandatory (R04-5); T2 split into fixed sub-blocks — Universe, Entry, Exits, Sizing,
  Risk limits, Costs, Execution, Robustness (R08-9).

## 5. Cheapest-build path (minimum viable cost model)
- **DECIDED — MVB = L2 constant-stack + callable wrapper from day one.**
  Ship `expected_cost_bps()` as a stub returning the flat 4-component stack
  (half-spread constant + taker/maker fee + commission + borrow, impact = 0 flagged
  `[example]`), wired into the T3 cost gate and T4 ledger calls. Cost: one table +
  one function signature per chapter; no impact calibration needed to be runnable.
- **DECIDED — non-negotiable even in MVB:** `fee_schedule_as_of` versioning (free
  to add now, expensive to retrofit), `side: taker|maker|mixed` field, before/after
  cost token, and `TYPE=` headers on S4/T4 (R17-2, R17-11, R10-4).
- **DECIDED — deferred to first hardening pass, not MVB:** impact function λ̂
  calibration, adverse-fill probability estimation, venue-risk reserve lines
  (ADL/clawback) (R08-5), options margin-financing drag (R06-7).
- OPEN: exact example-default `k` for the cost gate (R17-6 default `k=0.5` vs
  T002-style `k=2`) — resolved per-chapter as `default` pending calibration data.

## Keep (explicitly preserved)
t→t+1 causality discipline · SYNTHETIC labeling with seeds · [example]/[documented]
convention · before/after-cost column · "Where the example is optimistic" blocks
(made mandatory) · RSV schema + fail-safes F1–F5 pattern · funding as P&L line.
