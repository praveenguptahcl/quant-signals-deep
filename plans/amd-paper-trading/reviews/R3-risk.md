# R3 — Risk-controls red team: AMD paper-trading PLAN.md v0.1

Scope: §5 portfolio allocator, the 10-rule compliance blocks, cost gates,
kill switch, broker reconciliation loop, §7 validation gates. Read 2026-09-11.
PLAN.md was not modified.

Adversarial premise: paper money is fake, but the paper book must behave like
a real book or the validation means nothing. Every finding below is a way the
loop misbehaves, halts spuriously, or silently invalidates its own results.

---

## 1. [HIGH] No net/directional exposure cap — the whole book can pile one way on a single ticker

**Flaw.** Caps are per-strategy (≤25%) and gross (≤100%). Nothing limits *net*
direction. Four strategies each 25% long AMD = 100% gross, **+100% net long** —
on one ticker, where "diversification" is a fiction (pairwise correlation = 1).
Worse, §5 normalizes weights across *active* strategies, so if every survivor
happens to be long-biased in a given regime, the allocator will happily put
the entire paper book on one side of one name. A 25% cap that four strategies
can stack is not a concentration limit; it is a speed bump.

**Fix.** Add a net-exposure cap (e.g. |net| ≤ 60% of equity) *and* a single-name
gross cap below 100% (e.g. 75%) for phase 1. Enforce pre-trade, not just at
rebalance. Log net exposure per bar on the dashboard next to gross.

## 2. [HIGH] Normalization allocates the full budget even when conviction is near zero

**Flaw.** Weights are proportional to `confidence × DSR_rank_weight`,
*normalized across active strategies each rebalance bar*. If every active
strategy emits confidence 0.08, normalization still hands out ~100% of the
vol-scaled budget. There is no minimum-conviction threshold and no default-to-
flat state. Low-conviction environments — exactly when a disciplined book
should be in cash — get full size.

**Fix.** Gate allocation on aggregate conviction: e.g. allocate only
`min(1, total_confidence / conviction_floor)` of the budget, else hold cash.
Add an explicit FLAT state as the default, requiring positive evidence to
leave it. Log the conviction scalar per bar.

## 3. [HIGH] Regime-gate flicker will whipsaw the book

**Flaw.** §5: "strategies whose required regime is not active get weight 0."
Regime modules output discrete states bar-to-bar with no hysteresis. A regime
detector flickering active/inactive/active across three bars zeroes then
restores a strategy's full allocation repeatedly — forced liquidations and
re-entries, churning paper fills at exactly the moments the regime model is
least sure of itself.

**Fix.** Debounce every gate: require N consecutive confirming bars (or a
probabilistic threshold with hysteresis band) before a gate toggles, and a
minimum dwell time before it can toggle back. Log every gate transition with
cause. Backtest the *gated* strategy, not just the signal, so flicker cost is
measured in Stage 3.

## 4. [HIGH] Reconciliation "mismatch → halt" has no tolerance and undefined halt semantics

**Flaw.** §6: reconciliation matches broker positions vs. internal book every
bar; mismatch → halt and alert. Paper venues produce benign mismatches
constantly: delayed position updates, partial fills, a fill reported one bar
late, corporate-action adjustments. Zero-tolerance halt means the loop will be
halted more often than it runs — and every halt invalidates the "continuous
paper session" the validation is supposed to demonstrate. Worse, "halt" is
undefined: does it stop new orders, or flatten the book? If a spurious
mismatch triggers a flatten, the risk control *causes* the liquidation it was
meant to prevent.

**Fix.** Define halt precisely (recommend: halt = no new entries; existing
positions held; separate explicit command to flatten). Add a deadband:
mismatch must exceed max($25, 0.5% of equity) *and* persist for M bars before
halting. Classify mismatches (timing vs. quantity vs. unknown) and only halt
on quantity/unknown. Chaos-test this path (see finding 13).

## 5. [HIGH] Caps are checked at daily rebalance but intraday entries can breach them

**Flaw.** §5: "daily bars for sizing; intraday signals gate entries only,
never resize the book mid-day." So the 25% per-strategy cap is computed at the
daily rebalance — but intraday entries *add* exposure mid-day. A strategy sized
at 24% at the open that receives three intraday entry gates can end the day at
35%+, breaching the cap for hours with no check firing. The cap exists on
paper and not in the loop.

**Fix.** Enforce all caps as **pre-trade checks on every order**, not as
rebalance-time arithmetic. Any order that would breach a cap is rejected and
logged; repeated rejections page. The daily rebalance sets *targets*; the
pre-trade check enforces *limits*.

## 6. [HIGH] No drawdown circuit breaker on the paper book

**Flaw.** The kill switch is manual (§7 gate 4 drills it, good). Nothing
automatic stops a slow bleed: the book can lose 30% of paper equity across
two weeks of correlated losers and the loop keeps allocating at full budget
(the vol-scaler may even *increase* size if realized vol stays near median).
A paper test with no loss limit teaches nothing about risk discipline.

**Fix.** Automatic, non-overridable-in-session: halt new entries at −10% from
peak paper equity; require explicit re-arm with a written note; flatten-and-
review at −20%. Track peak equity in the WAL so it survives restarts.

## 7. [HIGH] Allocator can fail open — no sanity checks on its own output

**Flaw.** One allocator process computes every weight. A NaN confidence, a
zero-division in normalization (all weights zero → 0/0), or a corrupt DSR
table propagates garbage to the entire book in one bar. There is no
fail-closed behavior specified.

**Fix.** Post-computation assertions on every rebalance: weights finite,
non-negative, sum ≤ gross cap, per-strategy ≤ cap, regime-gated strategies
exactly zero. On any assertion failure: hold previous bar's weights (or go
flat if none exist) and page. Never allocate on unchecked output.

## 8. [HIGH] No idempotent order submission — retries can double-fill

**Flaw.** §6 names no idempotency mechanism. The first time the loop times out
waiting for an Alpaca/IBKR ack and retries, the "lost" order may already be
working — resulting in double the intended position with the internal book
believing it sent one order. Reconciliation then sees a quantity mismatch and
(finding 4) halts. The retry path manufactures the emergency.

**Fix.** Every order carries a deterministic client order id
(`{date, strategy, signal, bar}`); the router treats broker "duplicate"
responses as success-with-existing-id, never as a new order. Log all
retry paths; test them in the chaos gate (finding 13).

## 9. [MED] Single-signal look-through concentration is uncapped

**Flaw.** The 25% cap is per *strategy*, but nothing stops six strategies from
all keying off the same dominant signal. If S007 is the star of Stage 1 and
half the surviving strategies consume it, effective exposure to one signal's
view can be 60–100% of the book. Strategy-level diversification is an
illusion when the signal graph converges.

**Fix.** Attribute each strategy's weight back to its input signals
(proportional to declared signal weights) and cap aggregate exposure per
signal (e.g. ≤40% of equity attributable to any single signal). Report the
top-3 signal attributions on the dashboard.

## 10. [MED] Vetoes don't propagate — and they anti-select for recklessness

**Flaw.** "Any strategy emitting a hard risk veto zeroes its own allocation
for the bar." A veto is treated as a private opinion: strategy A sees danger
and stands down while B, C, D stay at full size. Two deeper problems: (a) a
genuine risk signal (e.g. data staleness, correlation spike) should arguably
halt *entries* book-wide, not just excuse one strategy; (b) vetoes are
self-reported, so capital flows toward strategies that never veto —
adverse selection for the most reckless modules.

**Fix.** Two-tier vetoes: strategy-level veto zeroes that strategy (as now);
*book-level* veto conditions (data stale, reconciliation mismatch, vol
extreme) halt new entries for all strategies. Additionally, track veto
frequency per strategy as a health metric — a strategy that never vetoes in
6 months is suspicious, not virtuous.

## 11. [MED] No portfolio-level turnover budget — confidence jitter becomes churn

**Flaw.** Cost gates exist per module, but there is no *portfolio* turnover
control. Daily renormalization on jittering confidences shifts weights every
bar; each shift trades. Death by a thousand rebalances: paper spread/slippage
bleeds the book while every module individually passes its cost gate.

**Fix.** Portfolio turnover budget per rebalance (e.g. ≤15% of equity traded
per day absent a regime change) plus hysteresis: only apply weight changes
exceeding a minimum delta (e.g. 2% of equity). Measure realized turnover vs.
budget in gate 3 replay and on the live dashboard.

## 12. [MED] Confidences are uncalibrated — the loudest signal wins, not the best

**Flaw.** Weights use raw confidence 0–1 straight from signal plug-ins. Nothing
requires confidences to be calibrated or even comparable across signals: a
signal emitting a constant 0.9 dominates one emitting a well-calibrated
0.55, regardless of actual hit rates. DSR_rank_weight partially compensates,
but the confidence term is still garbage-in.

**Fix.** Calibrate before weighting: map each signal's confidence through its
walk-forward empirical hit-rate curve (Stage 1 data already exists for this),
or replace raw confidence with cross-sectional rank. Reject signals whose
confidence has zero correlation with realized outcomes — that is itself a
Stage 1 exit criterion.

## 13. [MED] §7 gates don't test the failure paths — only the happy path

**Flaw.** Gate 3 replays history through *simulated* fills, but the live loop
uses *broker paper* fills — different code path, different failure modes.
Gate 5 sends 1-share test orders (connectivity only). Nothing in §7 exercises:
partial fills, rejected orders, stale bars, gateway disconnects, duplicate
acks, or a regime flicker storm. The gates validate that the loop works when
nothing goes wrong.

**Fix.** Add gate 6 (chaos): scripted injection of rejects, partial fills,
5-minute-stale bars, and venue timeouts against both paper connectors;
assert the loop degrades to hold-and-page, never to double-orders or silent
drift. Gate 3 should replay through the *same fill-handling code* as live,
with the fill *source* swapped — not a separate simulator.

## 14. [MED] No data-staleness guard — the loop will trade on yesterday's bars

**Flaw.** Nothing in §5–§7 checks that the AMD feed is fresh. If the data
connector stalls, the bar-close-driven loop keeps firing on the last good bar:
signals recomputed on stale inputs, confidences unchanged, orders placed
against a market that has moved. This is the classic paper-to-live divergence
that makes paper results untrustworthy.

**Fix.** Freshness guard as a book-level veto (finding 10): if the latest bar
is older than the session expectation (e.g. >15 min into regular hours with
no new bar), halt new entries and page. Stamp every allocation decision with
the as-of timestamp of its input bar; show data age on the dashboard.

## 15. [MED] Regime modules skip rigorous selection themselves

**Flaw.** Stages 1–2 select signals and strategies, but the regime modules
that *gate* them get no specified selection criteria of their own. A regime
detector with a 40% false-positive rate will gate good signals off half the
time — and because gating is silent (weight 0, no trade), the damage is
invisible in P&L attribution. The plan says "a few regimes" survive without
saying how they earn it.

**Fix.** Regime modules pass their own Stage 1: backtest detection quality
(precision/recall vs. labeled regimes, or incremental Sharpe of gated vs.
ungated signals) with the same embargo discipline. A regime gate must prove
it adds risk-adjusted value *net of flicker cost* (finding 3) before it is
allowed to zero anyone's allocation.

## 16. [LOW] Corporate actions will trip reconciliation

**Flaw.** AMD splits or pays dividends; the broker adjusts positions/cash and
the internal book doesn't. Next bar, reconciliation sees a quantity/cash
mismatch and — per finding 4 — halts on a non-event.

**Fix.** Subscribe to corporate-action events (or detect via the deadband
classifier in finding 4) and auto-adjust the internal book with an audit
entry. Test with a historical split replay.

## 17. [LOW] Kill-switch drill doesn't cover the ugly cases

**Flaw.** Gate 4 drills halt-mid-session → flat → re-arm under calm
conditions. Untested: kill switch during a partial-fill storm, during a venue
timeout (are unacked orders cancelled or left working?), and who is
authorized to hit it (auth + two-step confirm per the dashboard spec —
referenced nowhere in the plan).

**Fix.** Extend the drill: kill during injected chaos (finding 13), assert all
working orders are cancelled-or-accounted-for before declaring flat, and
write the auth/two-step requirement into the plan, not just the dashboard
spec. Add a dead-man's switch: loop heartbeat to a watchdog; missed
heartbeats page (positions left unmanaged by a dead loop are finding 14's
cousin).

---

### Cross-cutting note

The 10-rule compliance blocks are *module-scoped* (per-module YAML). Nearly
every high-severity finding above is a *portfolio-level* property —
net exposure, turnover, veto propagation, allocator sanity — that no
module-level block can see. The plan needs an explicit portfolio-level
compliance block (the risk layer in the §3 diagram) with its own numbered
rules mirroring the module blocks, tested in gate 3/6. Without it, the risk
layer is a diagram box, not a control.
