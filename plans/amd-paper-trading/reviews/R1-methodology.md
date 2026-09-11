# R1 — Methodology red-team: AMD selection pipeline (PLAN.md v0.1)

**Reviewer role:** quant methodology. **Scope:** the 4-stage selection pipeline
(§4), walk-forward/embargo design (§4 st.1, §9), DSR multiple-testing correction
for 250 candidates (§4 st.1, §10.4), regime conditioning logic (§4 st.3),
frozen survivor-list rule (§4 st.4, §10.3). Architecture, broker integration,
and dashboard are out of scope for this review.

**Overall read:** the pipeline's shape is right — separate-module universe,
mechanical applicability filter, walk-forward with embargo, DSR, redundancy
pruning, regime conditioning, frozen list. The flaws below are not in the
shape; they are in the *unspecified parameters and the trial accounting*.
As written, the plan can be executed in a way that reproduces exactly the
overfit it claims to prevent, while appearing compliant. Every high-severity
finding is a place where a researcher degree of freedom is currently
undocumented.

**Key reference:** Bailey & López de Prado (2014), "The Deflated Sharpe Ratio."
DSR corrects one observed Sharpe for selection over N trials. It requires:
(a) N = the number of configurations *actually tried* (the full trial ledger),
(b) an estimate of the variance of Sharpe ratios across those trials V̂,
(c) a benchmark SR₀. The plan names DSR but specifies none of (a)–(c).

---

## HIGH severity

### H1. "DSR for 250 candidates" misstates the trial count — N is not 250

**Flaw.** DSR's N must equal every configuration tried during selection, not
the number of modules that exist. The true trial count here includes: 250
modules × every parameter variant tried per module (modules carry config
tables and grid-search calibration recipes — each grid point is a trial) ×
every cluster-membership choice in Stage 2 × every signal×regime pair scored
in Stage 3. Plugging N=250 understates N, which *overstates* DSR — the
correction becomes theater while the plan claims rigor. Correlated trials
(five imbalance variants) further distort the effective N.

**Fix.** (1) Maintain a **frozen trial ledger**: every backtest configuration
run during Stages 0–3 is appended (module id, parameter vector, regime
variant, cluster choice, timestamp, seed) — nothing runs off-ledger.
(2) Compute DSR once, at final selection, with N = ledger row count and V̂
estimated from the ledger's Sharpe distribution within frequency stratum
(see M2). (3) State SR₀ = 0 and the annualization convention explicitly in
the plan. (4) If Stages 1–3 need interim DSR for pruning, use a conservative
N (upper bound of planned trials, pre-registered) and recompute at the end.

### H2. Stages 2 and 3 are selection steps with no multiplicity accounting

**Flaw.** Stage 2 ("keep the best risk-adjusted performer per cluster") is a
max-over-trials operation — one selection per cluster, with the number of
clusters itself data-dependent. Stage 3 scores each surviving signal against
each regime module: up to (survivors × 50) implicit signal×regime trials,
then keeps the "strong conditional" pairs. Neither stage is covered by the
Stage-1 DSR. This is the exact snooping pattern the plan warns about, moved
one stage downstream: by Stage 4, the survivor list has been selected *three
times* on the same AMD history with only the first selection corrected.

**Fix.** Either (a) fold Stages 2–3 into the trial ledger and the final DSR
(H1), or — cleaner and recommended — (b) split the history: run Stages 0–3
on a **selection window**, then evaluate the frozen survivor list exactly once
on a **held-out validation window** that no selection decision has ever
touched, reporting PSR (no further selection allowed). The validation-window
PSR is the only performance number allowed near the paper loop. See H3.

### H3. No train/selection/validation split is specified — walk-forward is hand-wavy

**Flaw.** "Walk-forward backtests with embargo gaps per Meridian doctrine" is
a pointer, not a design. The plan never states: number of folds, fold
boundaries, embargo length in bars, or — critically — whether any segment of
AMD history is reserved as a true holdout for the frozen survivor list. Without
a holdout, every number attached to SURVIVORS.md is in-sample-by-construction
(it was selected on that data), and the paper loop becomes the first genuine
out-of-sample test. DSR mitigates selection bias; it does not create
out-of-sample evidence.

**Fix.** Pre-register the split in the plan before any backtest runs, e.g.:
selection window 2018-01 → 2023-12 for Stages 0–3; validation window
2024-01 → 2025-12 for one frozen-list evaluation, zero selection decisions;
paper from 2026-09 forward. Embargo length set mechanically (see L1). Any
change to the split after seeing results is a new trial (ledger it).

### H4. The re-admission rule has a p-hacking loophole

**Flaw.** "Re-admission requires a new documented selection run." Documentation
does not reset researcher degrees of freedom. A failed module, a tweaked
parameter grid, a "documented" re-run on the *same* AMD history — repeated
until something passes — is p-hacking with paperwork. The frozen rule as
written permits unlimited bites at the same data.

**Fix.** Re-admission is allowed only if (a) it uses data from *after* the
freeze date (the paper period — genuinely new observations), or (b) the
cumulative trial ledger carries across runs and DSR is recomputed with the
larger N. Pre-register a cap on re-selection runs per quarter (e.g., ≤ 2).
Log every re-run attempt, including ones that fail.

---

## MEDIUM severity

### M1. Stage 1 scores strategies standalone, but strategies consume signals — the harness is undefined

**Flaw.** A strategy plug-in's backtest depends on which signals feed it. The
plan says each signal/strategy is "backtested individually" but never states
what feeds the strategies in Stage 1: all 100 signals? stub signals (the ones
used in module tests)? If strategies are scored on the full 100-signal set
and Stage 2 then prunes signals, every strategy score is stale — the
strategies were evaluated on inputs they will never see in production.

**Fix.** Define the evaluation harness explicitly: Stage 1 strategies scored
against the full post-Stage-0 signal universe; after Stage 2 pruning,
**re-score all surviving strategies on the pruned signal set** before Stage 3;
record in SURVIVORS.md exactly which signal set each strategy score used.
Strategies whose performance collapses on the pruned set are cut — that is
itself a finding, not a bug to patch by keeping the full set.

### M2. One DSR pool for 250 heterogeneous modules is wrong

**Flaw.** DSR's V̂ (variance of trial Sharpes) must come from comparable
trials. Daily-bar swing signals and intraday signals have different return
horizons, different annualization, and different Sharpe sampling error;
pooling them mixes distributions and corrupts both the correction and the
ranking. The plan's single "DSR for 250 candidates" number is therefore
mis-specified even if H1 were fixed.

**Fix.** Stratify: compute DSR separately within frequency/horizon strata
(e.g., daily-bar modules vs. intraday modules; or by maximum holding period
bucket from YAML). Estimate V̂ from the trial ledger *within* stratum. Rank
and cut within stratum, then allocate across strata at the portfolio layer —
do not compare a daily Sharpe against an intraday Sharpe for selection.

### M3. Redundancy pruning is hand-wavy — no metric, method, or threshold

**Flaw.** "Correlate signal outputs, cluster, keep the best risk-adjusted
performer per cluster" specifies nothing: correlation of what (raw signal
values? positions? daily P&L contributions — these have different scales and
give different clusters)? Which clustering method and cutoff? Tie-break rule?
And the dangerous case: a *negatively* correlated pair looks "redundant" by
|ρ| but is a diversifier — naive pruning destroys the portfolio's best
hedges. "Best risk-adjusted" by what statistic — raw Sharpe (uncorrected)?

**Fix.** Pre-register: (a) correlate **daily P&L contributions** (strategy-level,
same capital base), not raw signal values; (b) hierarchical clustering with a
stated cutoff (e.g., ρ > 0.7 merges); (c) keep the highest **DSR** (not raw
Sharpe) per cluster; (d) exempt pairs with ρ < −0.3 from pruning entirely
(diversifiers); (e) publish the cluster map in SURVIVORS.md so the pruning is
auditable.

### M4. Regime conditioning on tiny samples — no minimum-active-bars rule

**Flaw.** "Strong conditional Sharpe in a detectable regime" — some regimes
(R041 overnight-gap dominance, tail-risk regimes) are active a small fraction
of days. A conditional Sharpe on 40 active days has enormous standard error;
PSR/DSR on tiny samples is noise dressed as signal. Worse, the regime modules
themselves are unvalidated on AMD: a regime that never triggers (or always
triggers) makes its gate vacuous, and a signal "conditioned" on it is just an
unconditional signal with extra steps.

**Fix.** (a) Minimum-sample rule, pre-registered: a conditional score counts
only if the regime was active ≥ 60 bars **and** across ≥ 3 distinct active
episodes in the selection window. (b) Regime eligibility pre-screen: a regime
module must trigger on 5%–95% of selection-window days on AMD, else it is cut
in Stage 0 (vacuous gate). (c) Regime modules go through Stage-1-style
validation themselves — "does this detector detect anything on AMD?" — before
any signal is conditioned on them.

---

## LOW severity

### L1. Embargo length is a pointer ("per Meridian doctrine"), not a number

**Flaw.** The embargo must exceed the maximum lookback-plus-holding overlap
between train and test to stop leakage through overlapping return windows.
With 100 signals carrying different lookbacks (some 60+ days), a fixed
5-day-style embargo silently leaks for long-lookback modules: their test
"predictions" are functions of train-period returns.

**Fix.** Compute the embargo mechanically from module metadata: embargo =
max signal lookback + max holding period across the evaluated set (read from
YAML headers), in trading days, enforced programmatically in the backtest
harness. State the resulting number in the selection-run log.

### L2. Stage 0 cost gates run on placeholder fee schedules

**Flaw.** Deep review (round 2, e.g. S003) flagged COST-block fee schedules as
`[unverified]` placeholders. If Stage 0's "cost-gate check per module" runs
against made-up costs, modules pass/fail the mechanical filter on fiction —
and a module killed in Stage 0 never gets a second chance (frozen rule).

**Fix.** Before Stage 0 runs, pin one real, dated cost model for AMD
(Alpaca/IBKR paper: commissions $0, plus a documented spread + slippage
assumption for a liquid NASDAQ name, with the date it was sourced). Any
module whose gate was evaluated on placeholder data is marked provisional in
SURVIVORS.md, not cut.

### L3. Allocator reuses DSR ranks for sizing with no shrinkage

**Flaw.** Weights ∝ confidence × DSR_rank_weight: DSR ranks estimated on the
selection window are noisy, and raw rank-weighting concentrates capital on
the luckiest survivors (the very estimation error DSR warns about).
Additionally, regime gating zeroes weights bar-by-bar, so the traded
portfolio's composition drifts daily — validation gate 3's "historical
replay" must replicate the *identical* allocator code path (gating, vetoes,
normalization), not a simplified version, or the replay validates a different
strategy than the one traded.

**Fix.** Shrink weights toward equal weight (e.g., w ∝ 0.5·(1/N) +
0.5·DSR_rank_weight, pre-registered λ) and state it in §5. Require gate 3's
replay to call the production allocator function directly — same code, same
gating dynamics — with an automated diff-check that the replayed allocations
match a logged reference.

### L4. Signal confidence is never calibrated, but the allocator multiplies by it

**Flaw.** Signals emit confidence ∈ [0,1]; the allocator treats it as a
weight. Nothing in Stages 0–4 checks calibration: does confidence 0.8
correspond to ~80% directional hit rate (or to monotonically better outcomes
at all)? An overconfident-but-mediocre signal gets systematically overweight;
a well-calibrated modest signal gets underweight. Selection scores P&L, not
calibration.

**Fix.** Add a calibration check in Stage 1: bucket each signal's outputs by
confidence decile on the selection window, report hit-rate / mean return per
bucket in SURVIVORS.md, require monotonicity (or at least non-inversion) for
any signal whose confidence enters the allocator. Consider shrinking raw
confidence toward 0.5 (e.g., c′ = 0.5 + 0.5·(c − 0.5)) unless calibration is
demonstrated.

---

## What I would change, in priority order

1. **Pre-register the full selection design** (splits, embargo rule, strata,
   clustering spec, minimum-active-bars, shrinkage λ) *before* any AMD
   backtest runs. Right now the plan is a shape with free parameters; whoever
   fills them in after seeing data owns the overfit.
2. **Trial ledger + final DSR** (H1, H4) — the single highest-leverage fix.
3. **Selection/validation split** (H2, H3) — the only honest performance
   number comes from data no selection decision touched.
4. **Strategy harness on pruned signals** (M1) and **regime eligibility
   pre-screen** (M4) — both are cases where the current staging order
   silently invalidates its own scores.
5. Everything in LOW is cheap to fix now, expensive to argue about later —
   do L1–L4 before the first backtest, not after.

*Review written 2026-09-10. PLAN.md was not modified.*
