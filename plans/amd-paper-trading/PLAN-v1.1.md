# AMD Paper-Trading Build — Plan v1.1 (FROZEN)

**Status:** v0.1 drafted 2026-09-10 → red-teamed by 4 independent reviewer
agents (63 findings: R1 methodology 12, R2 architecture 22, R3 risk 17,
R4 execution 12 — full reports in `reviews/`) → all findings reconciled
→ **v1.0 frozen 2026-09-11** → independent external verification by Grok
(2026-09-11): verdict **APPROVE-WITH-FIXES**, 8 new findings (3 HIGH, 3 MED,
2 LOW), none repeating the 63 → all 8 incorporated below →
**v1.1 frozen**. v1.0 is preserved untouched as `PLAN-v1.0.md` in the repo;
this document is the operative plan. Changes after this freeze require a
version bump and a written rationale; the frozen decisions in §10 are not
re-litigated.

**Objective:** run all 250 quant modules against AMD, select the tradable
subset through a pre-registered selection pipeline, and generate real paper
trades on **Alpaca paper (phase 1)** with portfolio allocation — per-strategy
percentage allocations from confidences, regime-gated, risk-limited.
**Paper trading only. No real-money orders exist in any phase of this plan.**

---

## 1. Starting position (verified inventory)

- 250 standalone modules in `quant-signals-deep` (100S/100T/50R), deep-reviewed,
  pushed, `DEEP_REVIEW_REPORT.md` committed.
- 250 plug-ins built into Meridian `plugins/modules/` (100 signal, 100 strategy,
  50 regime). Batch builds complete.
- Meridian core: 1,266 tests green, 10 red-team rounds, pushed.
- Meridian invariants (non-negotiable): signals emit intentions only
  (symbol, direction, confidence 0–1, capital); strategies see bars through
  bar t only; walk-forward + embargo; PSR/DSR multiplicity control;
  REAL/SYNTHETIC/PAPER stamping.
- Dashboard: Command Center variant is the visual spec; production rebuild
  in-house.

## 2. Architecture

```
AMD market data (Alpaca; stamped REAL-IEX, split/dividend-adjusted)
        │
Intention layer: 100 signal plug-ins + 100 strategy plug-ins
  (CORRECTED per R2-H1: strategies are self-contained and emit intentions
  directly — signals and strategies are TWO PARALLEL intention sources,
  both emitting meridian.research.Signal. There is no signal-consumption
  handoff. The allocator treats all ~200 intention streams uniformly.)
        │
Regime layer: 50 regime modules → regime-binding table per strategy
  (R2-M2): per strategy (regime module id, allowed states, gate behavior).
  Unbound strategies run ungated (stated). Non-terminal states
  ("warming", unknown) gate closed.
        │
Allocator (NEW): §4 — confidence-weighted, shrunk, regime-gated,
  volatility-scaled; consumes the STRATEGY-EMITTED Signal.confidence
  (R2-L4). Allocator output OVERRIDES module-level notional hints (R2-H7).
        │
Netting stage (NEW, R2-M1): net intentions to portfolio-level orders per
  venue per bar. Phase 1 is single-venue (Alpaca), so cross-venue netting
  is out of scope until phase 2.
        │
Risk layer: portfolio-level compliance block §8 (numbered rules P1–P10),
  module 10-rule blocks, cost gates, KillSwitch, pre-trade cap checks.
        │
Execution: Alpaca connector behind Meridian's EXISTING broker interface —
  NO parallel order path (R2-H2). Every order routes through
  ExecutionEngine (WAL exactly-once, kill switch inside submit path,
  refusal accounting). Venue selection lives inside the engine's submit
  path.
        │
PAPER fills → portfolio tracker → dashboard (tenant: amd-paper, R2-L3)
```

**Execution policy (R2-H3, Grok-2):** intentions decided on bar t REST until
bar t+1's open, then submit as **limit + day** inside the pre-open window
08:00–09:28 ET. OPG/CLS time-in-force is NOT used in phase 1: Alpaca
documents opg/cls as available only to Elite Smart Router users (verified
against Alpaca's order docs 2026-09-11), and OPG submitted after 09:28 ET
is rejected — so "market-on-open where supported" is struck from this plan.
No submit 09:28–09:35 ET. OPG may only enter via a confirmed Elite paper
account plus a market-hours opg drill passing Gate 5. Fills timestamped and
stamped PAPER. The live loop gets the same automated t→t+1 fill-vs-bar-boundary
audit as the backtest.

**Safety boundary (R2-H4):** `PAPER_VENUES_ONLY` guard — connector construction
allowlists paper base URLs only (`https://paper-api.alpaca.markets`, IBKR paper
gateway in phase 2) and refuses anything else. Credentials via Secure Vault,
paper-scoped. Paper credentials are still credentials: revised threat model
documented at build time.

**Fault isolation (R2-H5):** per-plug-in try/except per bar; exception → excluded
for the bar and ledgered; 3 consecutive failures → quarantined for the session
with alert. Per-plug-in wall-clock budget per bar (armed by default, sized from
measured p99); timeout = failure, never silent skip. Per-bar intention cap =
2× survivor count; excess → ledgered refusal (R2-L5).

**State (R2-H6):** plug-in state checkpointed per bar (serialized, versioned)
into the state dir; restart replays from last checkpoint. Gate 4 drills
"restart mid-session, verify state continuity."

**Bars (R2-M8, R4-11):** canonical bar type defined at the orchestrator boundary
with a validated converter (types, finiteness, provenance stamping; rejects
SYNTHETIC on the live path). Production paths must not import plug-in CSV
loaders (CI import check). NYSE calendar pinned; incomplete bars skipped and
logged, never computed on; post-holiday gap rule in vol scaling.
Extended-hours bars are REJECTED in phase 1 unless an extended-hours policy
is written and frozen (Grok-2; Alpaca paper 24/5 accepts overnight DAY/GTC
limits the NYSE calendar does not model).

**Loop cadence (R2-L2):** daily-close loop for sizing/rebalance; optional 5-min
intraday bars for entry gating only (no mid-day resizing). No bar → no signals
→ no orders (fail-closed); intentions have exactly one-bar TTL (R2-M4).

**Shorts (R2-M7):** hard-vetoed in phase 1 — no locate attestation feed exists.
Revisit in phase 2.

**Idempotency (R2-M6, R3-8, Grok-5):** TWO ids. `intention_id =
"amd-paper/{bar_ts}/{module_id}/{side}/{seq}"` (per module, WAL only —
attribution grain). `client_order_id =
"amd-paper/{bar_ts}/{venue}/{side}/{net_seq}"` (netted order grain — what
the broker sees). Netting (R2-M1) collapses many intentions into one venue
order; the WAL records the many-to-one map so crash recovery reconciles one
broker order against many intentions without inventing dummy module ids.
Broker "duplicate" responses = success-with-existing-id. Gate 4 drills a
restart BETWEEN net and broker ack.

## 3. Selection pipeline (pre-registered — R1)

**Pre-registration rule (R1-H1/H3):** the full selection design — splits,
embargo rule, strata, clustering spec, minimum-active-bars, shrinkage λ,
conviction floor — is frozen in this document BEFORE any AMD backtest runs.
Whoever runs selection may not change parameters after seeing data.

**Data split (frozen):**
- Selection window: 2018-01 → 2023-12 (Stages 0–3).
- Validation window: 2024-01 → 2025-12 — the frozen survivor list is evaluated
  here EXACTLY ONCE, zero selection decisions allowed. The validation PSR is
  the only performance number allowed near the paper loop.
- **Validation decision rule, pre-registered (Grok-6):** the holdout is one
  name, two years, one regime path — weak power, not a leak. The paper loop
  starts if validation PSR > 0.5 (probability the true Sharpe exceeds 0).
  If PSR ≤ 0.5 (inconclusive), the loop still starts — this is paper, and
  paper P&L proves plumbing, not edge — but with the conviction floor raised
  (0.4 → 0.6 of N_active) and size halved until two quarters of paper data
  exist. A noisy holdout pass is never read as proof of edge and never
  licenses universe expansion.
- Paper: from 2026-09 forward.
- Any change to the split after seeing results = a new trial, ledgered.

**Trial ledger (R1-H1/H4):** every backtest configuration run in Stages 0–3
is appended (module id, parameter vector, regime variant, cluster choice,
timestamp, seed). Nothing runs off-ledger. DSR computed ONCE at final
selection with N = ledger row count, V̂ from ledger Sharpe distribution
within stratum, SR₀ = 0, annualization stated. Interim pruning uses a
pre-registered conservative N (upper bound of planned trials).

**Stratification (R1-M2):** DSR computed separately within horizon strata
(daily-bar vs. intraday modules, from YAML max-holding-period). Rank and cut
within stratum; allocate across strata at the portfolio layer.

**Embargo (R1-L1):** embargo (trading days) = max signal lookback + max holding
period across the evaluated set, read from YAML headers, enforced
programmatically. The resulting number is logged per selection run.

**Stage 0 — Applicability filter (mechanical).** YAML data requirements vs.
available feed (Alpaca IEX in phase 1 → SIP-dependent modules excluded,
R4-4). Cost-gate check runs against a PINNED, dated cost model for AMD
(commissions $0 + documented spread/slippage assumption for a liquid NASDAQ
name); modules gated on `[unverified]` placeholder schedules are marked
provisional, never cut (R1-L2). Regime eligibility pre-screen: a regime module
must trigger on 5%–95% of selection-window days or it is cut here as a
vacuous gate (R1-M4).

**Stage 1 — Per-module walk-forward (Grok-1, supersedes R1-M1 as reconciled
in v1.0).** Signals and strategies are TWO PARALLEL intention families (§2,
R2-H1): there is no signal-consumption handoff and no strategy-to-signal
dependency graph. Every module — signal or strategy — is scored STANDALONE
on its own on_bar output only. The v1.0 sentences about strategies being
"scored against the full post-Stage-0 signal universe" and "RE-SCORED on
the pruned signal set" are STRUCK; they described a graph that does not
exist. Stage 2 clusters on daily P&L contributions of those standalone
outputs (same capital base), unchanged. Confidence calibration
check per signal: bucket outputs by confidence decile, require monotonic
(or non-inverted) hit-rate/mean-return; uncalibrated signals fail Stage 1
(R1-L4, R3-12). Regime modules pass their own Stage 1: detection quality
(precision/recall or gated-vs-ungated incremental Sharpe) with embargo (R3-15).

**Stage 2 — Redundancy pruning (pre-registered spec, R1-M3).** Correlate DAILY
P&L CONTRIBUTIONS (same capital base), hierarchical clustering, merge at
ρ > 0.7; keep the highest DSR per cluster; pairs with ρ < −0.3 exempt
(diversifiers). Cluster map published in the survivor registry.

**Stage 3 — Regime conditioning.** Conditional scores count only with
≥ 60 active bars across ≥ 3 distinct episodes (R1-M4). Gate debounce:
3 consecutive confirming bars + 5-bar minimum dwell before toggling back;
the GATED strategy (not just the signal) is backtested so flicker cost is
measured (R3-3).

**Survivor registry (R2-M3):** `SURVIVORS.json` — per module
`(module_id, version, sha256_of_plugin_file, dsr, stratum, cluster_id,
regime_binding, calibration_curve_ref)`. The orchestrator refuses plug-ins
whose hash differs. Human-readable `SURVIVORS.md` rendered from it.

**Re-admission (R1-H4):** allowed ONLY on post-freeze data (the paper period)
or with the cumulative ledger carried across runs (DSR recomputed, larger N).
Cap: ≤ 2 re-selection runs per quarter. Every attempt logged, including failures.

**Frozen rule:** any module failing a stage is out. No hand-overrides.

## 4. Portfolio allocator

- Base weight ∝ `calibrated_confidence × shrunk_DSR_rank_weight`,
  with shrinkage w ∝ 0.5·(1/N) + 0.5·DSR_rank_weight, λ = 0.5 pre-registered
  (R1-L3).
- **Conviction gate (R3-2):** allocate fraction =
  min(1, Σconfidence / (0.4 × N_active)); otherwise hold cash. Default state
  is FLAT; positive evidence required to leave it. Conviction scalar logged
  per bar.
- Volatility scaling: gross exposure ∝ 1 / (AMD realized vol vs. trailing
  median), with the vol-scaler UPSIDE capped at 1.25× — a pre-earnings vol
  crush must not lever the book into the print (Grok-3).
- **Caps (all enforced as PRE-TRADE checks on every order, R3-5):**
  per-strategy ≤ 25%, |net| ≤ 60% (R3-1), single-name gross ≤ 75%,
  total gross ≤ 100% (no leverage), intention-family concentration: no
  single module_id (signal OR strategy) > 25% of allocated equity —
  replaces the v1.0 "per-signal look-through attribution ≤ 40%", which
  assumed a strategy-to-signal graph that does not exist (Grok-1).
  Top-3 module attributions on dashboard.
- Regime gating with debounce (§2); gated strategies exactly zero.
- Strategy-level veto zeroes that strategy; **book-level vetoes**
  (data stale > 15 min into session, reconciliation mismatch, vol extreme)
  halt ALL new entries (R3-10). Veto frequency tracked per strategy as a
  health metric.
- **Turnover budget (R3-11):** ≤ 15% of equity traded per rebalance absent
  regime change; weight changes < 2% of equity ignored (hysteresis).
- **Fail-closed (R3-7):** post-computation assertions (finite, non-negative,
  sums ≤ caps, gated = 0). On failure: hold previous bar's weights (or flat
  if none) and page. Never allocate on unchecked output.
- Gate-3 replay calls the PRODUCTION allocator function directly (same code,
  same gating); automated diff-check vs. logged reference (R1-L3).

## 5. Execution (phase 1: Alpaca paper only — R4)

- **Phase 1 venue: Alpaca paper only.** IBKR moves to phase 2 (gateway on
  headless infra, Xvfb/supervisor, daily re-auth, pacing drill, delayed-data
  verification, DU… account-ID interlock — R4-1/2/3/8). Venue capability matrix
  built AFTER SURVIVORS.json; default assumption: Alpaca covers 100% of
  phase-1 needs (R4-9).
- **Data:** Alpaca IEX feed, phase 1. Bars stamped `REAL-IEX`,
  split/dividend-adjusted. The EXACT historical extract used for Stages 0–3
  and the live adjuster are checksummed against the SAME dated
  corporate-action calendar (splits AND cash dividends); ingest FAILS on
  mismatch — a Gate 2 abort, not a log line (Grok-8; a silent raw-vs-adjusted
  mismatch wrecks Stage 1 vs. live). Feed liveness heartbeat: no bar/heartbeat within 3× expected
  interval → pause signal computation, halt entries, page (R4-10, R3-14).
  Every allocation stamped with input-bar as-of timestamp; data age on dashboard.
- **Fill semantics (R4-7):** Alpaca paper fills at quote, no slippage, no
  partials — documented as an explicit assumption. Internal P&L accounting
  applies a slippage haircut so strategy comparisons aren't decided by
  simulator generosity.
- **Throttling:** Alpaca 200 req/min token bucket, per-venue (R4-8).
- **Reconciliation (R3-4, R4-5):** broker positions = source of truth; grace
  window before declaring mismatch; halt only on PERSISTENT mismatch
  (deadband max($25, 0.5% equity), 3 consecutive bars, quantity/unknown only —
  timing mismatches logged, not halted). Halt = no new entries (NOT flatten;
  flatten is a separate explicit command) via the shared
  `ExecutionEngine.trip_and_cancel` — one flag, not two (R2-M9). Per-venue
  books, never netted across venues.
- **Corporate actions (R3-16):** auto-adjust internal book with audit entry;
  tested with historical split replay.

## 6. Validation gates (all must pass before the live paper loop)

1. All 250 module tests + Meridian suite green.
2. Selection pipeline completes; `SURVIVORS.json` frozen (hash-pinned).
3. Historical replay through the production allocator + fill-handling code
   (fill *source* swapped, not a separate simulator — R3-13) with automated
   t→t+1 audit and allocation diff-check.
4. Kill-switch drill: halt mid-session → verify flat → re-arm; PLUS restart
   mid-session → verify state continuity (R2-H6); kill-switch auth = two-step
   confirm; dead-man's switch: loop heartbeat to watchdog, missed beats page
   (R3-17).
5. **Realistic drill (R4-6, Grok-2, replaces 1-share test):** full loop in a
   live market-hours session with strategy-sized orders —
   signal → allocation → order → fill → broker position → reconciliation →
   dashboard. Must run during market hours AND must exercise the pinned
   limit+day pre-open order path (08:00–09:28 ET) — a 10:00 DAY market-order
   drill does not prove the rest-until-open policy works.
6. **Chaos gate (R3-13):** scripted injection of rejects, partial fills,
   5-minute-stale bars, venue timeouts, regime flicker storm; assert the loop
   degrades to hold-and-page, never to double-orders or silent drift.
7. **Fill calibration (R2-M10):** survivor portfolio vs. simulated fills and
   paper-venue fills over a calibration window; record slippage divergence,
   set live-drift alert threshold.

## 7. Portfolio-level compliance block (R3 cross-cutting)

Module 10-rule blocks are module-scoped; the following portfolio rules are
enforced by the risk layer with numbered tests in gate 3/6:

- **P1** |net exposure| ≤ 60% equity, pre-trade enforced.
- **P2** Single-name gross ≤ 75%; total gross ≤ 100%.
- **P3** Per-strategy ≤ 25%; no single module_id (signal or strategy) > 25%
  of allocated equity (Grok-1).
- **P4** Conviction gate: below floor → FLAT (no normalization-to-full).
- **P5** Turnover ≤ 15% equity/rebalance; 2% hysteresis.
- **P6** Drawdown breaker: halt entries at −10% from peak equity (peak in
  WAL); flatten-and-review at −20%. Non-overridable in-session.
- **P6b — Earnings/event blackout (Grok-3):** no new entries from T−2
  through T+1 around AMD earnings dates and known extraordinary-dividend
  dates (corporate-action calendar pinned, dated). A book at −8% that gaps
  to −22% on a print never touches the −10% entry halt — the blackout is
  the actual defense, the breaker is the backstop. Flatten trigger also
  computed on open-to-open equity, not only marked peak.
- **P7** Allocator output assertions pass or fail-closed (hold/flat + page).
- **P8** Data staleness → book-level veto (no new entries).
- **P9** Every order pre-trade-checked against P1–P5; rejections logged, repeated
  rejections page.
- **P10** Reconciliation mismatch → shared KillSwitch (halt entries); flatten
  only by explicit command.

## 8. Timeline

**Phase 1 (~2 weeks, Alpaca paper only):**

| Days | Work |
|------|------|
| 1–2 | Alpaca paper connector + AMD IEX feed + liveness monitor (no logins needed for code; keys at connect time) |
| 2–5 | Orchestrator + allocator + risk layer + netting (plugs into ExecutionEngine) |
| 5–8 | Selection pipeline run on AMD history (history via Alpaca bulk API, throttled backfill) |
| 8–10 | Gates 1–7, live paper loop, dashboard wiring |

**Phase 2 (after phase-1 validation):** IBKR paper — gateway on headless infra,
DU… account interlock, pacing drill, delayed-data verification, venue matrix
decision, short-locate feed (lifts the phase-1 short veto).

Work needing no logins (orchestrator, allocator, selection code, historical
validation) starts immediately.

## 9. Risks and non-goals

- Paper fills ≠ live fills; paper P&L proves plumbing, not edge.
- Selection overfit is the #1 methodological risk; the defense is
  pre-registration + trial ledger + stratified DSR + selection/validation
  split + frozen survivor list.
- Perf: 100 signal plug-ins per bar get a timed smoke test with a per-bar
  compute budget before the live loop (R4-12).
- **Non-goals:** real-money trading, multi-ticker, leverage, intraday
  resizing, short selling (phase 1), HFT latencies.
- **Cadence honesty (Grok-7):** v1.0 builds a DAILY-SWING book — daily-close
  rebalance, optional 5-min entry gates, no mid-day resizing, shorts vetoed,
  rest-until-next-open. The five-ticker expansion is described as automated
  DAY trading; true intraday (mid-day resizing, PDT accounting, locate
  feeds, SIP data) is a SEPARATE later plan with its own cadence, risk, and
  venue analysis — not an extension of this one.

## 10. Frozen decisions (not re-litigated)

1. Paper only. No real-money path in this build.
2. AMD only until the loop is validated.
3. Selection pipeline mandatory; no module trades without passing it.
4. Pre-registered design + trial ledger + stratified DSR mandatory.
5. t→t+1 causality, REAL/PAPER stamping, PAPER_VENUES_ONLY allowlist.
6. Allocator = §4 unless the user explicitly changes it.
7. Phase 1 = Alpaca paper only; IBKR is phase 2.
8. Shorts vetoed in phase 1.
9. Grok is visual-prototyping only; production artifacts built in-house
   with tests.
10. Re-admission only on post-freeze data or cumulative-ledger DSR, ≤ 2/quarter.
11. **Phase-3 expansion guardrail (Grok-4):** the AMD survivor list NEVER
    transfers to ARM/Intel/Synopsys/Apple — that is a new uncorrected
    selection (same modules, new series, no new N), and four of five names
    share a semiconductor factor. Phase 3 requires its own frozen amendment:
    (a) re-run Stages 0–3 per name, or a joint panel with N counting every
    name×config; (b) a book-level SECTOR net cap (|Σ semi-name nets| ≤ 60%
    of firm equity, not per-name); (c) pruning on cross-sectional residual
    correlation, not only same-name P&L ρ; (d) a new SURVIVORS.json per name
    — AMD hashes do not travel; (e) client_order_id/tenant namespaced per
    name. Decision 2 (AMD only until the loop is validated) stands.

---

## 11. v1.1 changelog — Grok independent verification (2026-09-11)

Verdict: **APPROVE-WITH-FIXES**. "The 63 reconciled items are real work.
The pipeline shape, trial ledger, holdout, paper-only interlock, and
ExecutionEngine routing are good enough to run an AMD paper book. What is
still wrong is mostly reconciliation residue (the plan absorbed R1 and R2
without making them consistent) plus a few load-bearing holes the four
reviews never named." Grok read the full plan + all four review reports via
its GitHub connector (18 sources). None of the 8 findings repeats the 63.

| # | Sev | Finding | Fix applied in v1.1 |
|---|-----|---------|---------------------|
| 1 | HIGH | Stage 1 still assumed strategies consume signals; architecture §2 says they do not (R1-M1 vs R2-H1 both "fixed", contradicting). | S/T are two parallel intention families; every module scored standalone on its own on_bar output; "pruned signal set" sentences struck; look-through P3 replaced with no-single-module_id > 25%. |
| 2 | HIGH | "Limit-at-open (market-on-open where supported)" is not what a standard Alpaca paper account can do: opg/cls TIF is Elite Smart Router only (verified in Alpaca's order docs 2026-09-11); OPG after 09:28 ET rejected. | Phase-1 order pinned: limit + day, pre-open window 08:00–09:28 ET, no submit 09:28–09:35; Gate 5 must drill the pinned path; extended-hours bars rejected without a frozen policy. |
| 3 | HIGH | Single-name earnings gaps walk through the drawdown breaker (book at −8% gaps to −22%; vol scaling levers INTO the quiet pre-print week). | P6b: hard book-level veto, no new entries T−2 → T+1 around AMD earnings/extra-div dates; flatten trigger also on open-to-open equity; vol-scaler upside capped 1.25×. |
| 4 | MED | DSR honest for AMD is not a license to reuse SURVIVORS.json on ARM/INTC/SNPS/AAPL (new uncorrected selection; five 60%-net books = one sector bet). | Frozen decision 11: phase-3 amendment requirements (per-name selection, sector net cap, residual-correlation pruning, per-name SURVIVORS.json, per-name id namespace). |
| 5 | MED | After netting, client_order_id keyed on module_id is ill-defined (many intentions → one broker order). | Two ids: intention_id (per module, WAL only) + client_order_id at netted grain; WAL many-to-one map; Gate 4 restarts between net and ack. |
| 6 | MED | Holdout PSR on one name/two years/one regime is weak power, not a leak — must not be read as proof of edge. | Pre-registered validation decision rule: PSR > 0.5 → loop starts; inconclusive → loop starts with conviction floor raised (0.4→0.6) and size halved. Paper P&L = plumbing. |
| 7 | LOW | "Automated day trading" is not what v1.0 builds (daily-swing book). | Cadence honesty note in §9: true intraday is a separate later plan. |
| 8 | LOW | IEX history vs live adjustment basis needs a dated pin, not a slogan (dividend/adjustment noise, not splits). | Exact extract + live adjuster checksummed against same dated corporate-action calendar; ingest fails on mismatch — Gate 2 abort. |

Grok's closing line: "Phase 1 AMD paper: go, after findings 1–3 and 5 are
written into the freeze list. Do not treat v1.0 as a 5-ticker plan."
All eight are now in the freeze list. Full verbatim review: `reviews/R5-grok-verification.md`.
