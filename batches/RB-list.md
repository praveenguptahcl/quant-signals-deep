# Regime Master List — R001–R050 (Part III research basis)

**Purpose.** The 50 market regimes that most influence the efficacy of the S001–S100 signals
and T001–T100 strategies in this document. Each entry gives: (1) precise definition,
(2) calculation recipe — formula, data inputs, cadence, thresholds, (3) efficacy modulation
— which signal/strategy families it affects, in which direction, and by what mechanism,
(4) automated-loop spec — how it is detected inside a multi-agent research/verification loop.

**Threshold convention.** Bands marked `[documented]` come from published literature or
long-run market statistics. Bands marked `[example]` are illustrative starting points that
must be recalibrated per instrument, venue, and horizon. Chapters must never present
`[example]` bands as institutional standards.

**Lookahead rule.** Every regime indicator is causal: computed at time *t* using only data
with timestamps ≤ *t*. A regime label may gate a signal evaluated at *t* only for trades
executable at *t+1* or later. Any backtest that conditions on a regime must lag the label
by at least one bar.

---

## Automated research/verification multi-agent loop — roles

| Agent | Responsibility |
|---|---|
| **Sentinel** | Computes every regime indicator on its cadence from live/historical feeds. Publishes the Regime State Vector (RSV): `{regime_id, state, value, estimator_version, data_vintage, computed_at}`. |
| **Verifier** | Independently recomputes each indicator with a second estimator or independent implementation; flags disagreement beyond tolerance; runs bounds checks and staleness timeouts. |
| **Grok-Researcher** | Answers the structured RB question batches; retrieves literature, proposes thresholds and mechanisms. All output is a *lead* until the Verifier reproduces it. |
| **Adversary** | Attacks the regime pipeline: injects lookahead, stale data, and missing-data gaps; checks that conditioning a signal on a regime does not leak future information into the evaluation. |
| **Gate** | Enforces the 22-item QC (notes/merge-protocol.md) before any R-chapter merge; owns quarantine. |

**Universal fail-safes (apply to every regime).**
- F1. Missing or stale input → state `UNKNOWN`; downstream signals treat `UNKNOWN` as *restrictive*
  (reduce size / widen stops), never as benign.
- F2. Every indicator value must satisfy its mathematical bounds (e.g. VPIN ∈ [0,1], HHI ∈ (0,1]);
  out-of-bounds → `UNKNOWN` + alert.
- F3. Dual-estimator agreement: Sentinel and Verifier must agree within the stated tolerance or the
  state is `UNKNOWN`.
- F4. Staleness timeout: if `computed_at` is older than 3× the cadence, the state expires to `UNKNOWN`.
- F5. No regime label may be used to *select* backtest periods ex post without a pre-registered
  definition (Adversary checks for regime-mining).

---

## VOLATILITY REGIMES

### R001 — Realized-volatility level regime

**Definition.** The current short-horizon realized volatility of the instrument, expressed as a
percentile of its own trailing distribution. The single most important efficacy modulator:
it scales spreads, impact, stop distances, and the signal-to-noise ratio of almost every family.

**Calculation.**
- Estimator (intraday): Yang–Zhang realized variance from 5-minute bars, annualized:
  `σ²_YZ = σ²_overnight + k·σ²_open-close + (1−k)·σ²_RS`, with the Rogers–Satchell term for
  drift robustness. Daily fallback: Garman–Klass `σ²_GK = 0.5·ln(H/L)² − (2·ln2−1)·ln(C/O)²`.
- Regime score: `z_RV = (RV_5d − median(RV_252d)) / IQR(RV_252d)`, or percentile
  `p = rank(RV_5d)/252`.
- Cadence: daily close for the level; intraday 30-minute refresh for execution gating.
- Bands `[example]`: `p < 0.2` complacent · `0.2–0.8` normal · `0.8–0.95` elevated · `p > 0.95` extreme.
  Calibrate per name: a mega-cap's 95th percentile is a small-cap's median.

**Efficacy modulation.**
- Microstructure signals (OFI, queue imbalance, microprice — S001/S003/S008 family): **improve**
  in elevated RV (more adverse-selection edge per trade) but **die** in extreme RV when spreads
  widen beyond the edge; mechanism: edge ∝ volatility, cost ∝ spread, and spread is convex in RV.
- Mean-reversion (RSI-2/IBS family): **improve** mildly elevated (wider swings to fade), **die** in
  extreme (trends emerge, stops detonate). Mechanism: reversion assumes stationary variance.
- Trend/momentum: **improve** in elevated RV (bigger drifts); chop in complacent RV.
- Pairs/stat-arb: spreads widen in extreme RV → **worse** fills, **better** paper divergence.

**Loop spec.** Sentinel computes YZ-RV at close + 30-min intraday refresh; Verifier recomputes
with Parkinson as second estimator, tolerance ±15% relative. Adversary checks the percentile
lookback does not include the evaluation window (no in-sample percentile). Fail-safe: on
`UNKNOWN`, execution agents halve size.

### R002 — Implied-vs-realized spread (variance risk premium)

**Definition.** `VRP_t = IV_t² − E_t[RV²_{t→t+30d}]`, proxied in practice by `VIX² − RV_30d²`
(annualized variance points). Positive VRP = options expensive vs subsequent realized vol —
the compensation option sellers earn. Sign flips mark fear/complacency turning points.

**Calculation.**
- Inputs: VIX (or single-name 30d IV from the options surface), 30-day trailing realized variance.
- `VRP = IV² − RV²` in variance points; normalize by trailing 252-day std for a z-score.
- Cadence: daily (uses close prints).
- Bands `[documented]`: SPX VRP averages ≈ +3 to +5 variance points (≈ +4 vol points);
  `[example]` bands on the z-score: `z < −1.5` fear (IV bid up) · `|z| ≤ 1.5` normal · `z > 1.5`
  complacent (IV cheap vs realized — rare, mean-reverts fast).

**Efficacy modulation.**
- Option-selling / premium-harvest strategies: **improve** when VRP strongly positive;
  **die** when VRP negative (you are buying fear at the wrong time). Mechanism: expected edge
  ≈ VRP minus gap risk.
- Volatility-breakout signals: **improve** when VRP deeply negative (realized about to exceed
  implied — repricing ahead).
- Directional intraday equity signals: roughly neutral; VRP is a *positioning* filter, not a
  trigger.

**Loop spec.** Sentinel pulls VIX + computes RV_30d; Verifier cross-checks IV from a second
surface source (e.g. CBOE vs broker IV), tolerance ±1 vol point. Adversary verifies the RV
window is strictly trailing (no realized-vol lookahead into the "forecast" window). Fail-safe:
single-name VRP requires ≥5 strikes/tenor liquidity or state is `UNKNOWN`.

### R003 — Volatility term-structure slope

**Definition.** `Slope = (IV_long − IV_short) / IV_short`, e.g. `(VIX3M − VIX) / VIX`.
Contango (positive slope) is the normal state; flattening/inversion (backwardation) marks
stress and near-term event risk.

**Calculation.**
- Inputs: two points on the IV term structure (VIX and VIX3M for index; 30d vs 90d ATM IV
  for single names).
- Cadence: daily; intraday on event days.
- Bands `[example]`: `Slope > +0.10` steep contango (calm) · `−0.05…+0.10` flat (watch) ·
  `Slope < −0.05` backwardation (stress/event bid).

**Efficacy modulation.**
- Calendar/vol-carry strategies: **improve** in steep contango (roll-down harvest);
  **die** in backwardation (term structure pays you to be short front vol — crowded).
- Event-driven (earnings/FOMC) strategies: backwardation **confirms** the event is priced;
  fade-the-event trades **improve** after the print when slope normalizes.
- Mean-reversion equity signals: persistent backwardation = trending fear → **worse**.

**Loop spec.** Sentinel computes from surface snapshots; Verifier checks put-call IV parity
(no-arbitrage sanity: call/put IV within 2 vol points). Stale surface (>1 day) → `UNKNOWN`.

### R004 — Volatility clustering / persistence state

**Definition.** Whether variance is currently in a high-persistence (clustered) or
low-persistence state, measured by GARCH(1,1) persistence `α+β` fitted on a rolling window,
or by the HAR-RV daily/weekly/monthly coefficient profile.

**Calculation.**
- Fit GARCH(1,1) on 252 days of daily returns, rolling monthly: persistence `π = α + β`;
  half-life `HL = ln(0.5)/ln(π)` in days.
- Alternative: HAR-RV regression `RV_{t+1} = c + β_d·RV_t + β_w·RV_{t-4:t} + β_m·RV_{t-21:t}`;
  persistence ≈ `β_d + β_w + β_m`.
- Cadence: weekly refit.
- Bands `[example]`: `π < 0.85` low persistence (shocks die fast — fade vol spikes) ·
  `0.85–0.95` normal · `π > 0.95` extreme clustering (shocks persist — do not fade; HL > 14 days).

**Efficacy modulation.**
- Vol-fade / short-gamma intraday tactics: **improve** in low persistence, **die** in extreme
  clustering (the spike you faded doubles). Mechanism: persistence sets the expected
  mean-reversion speed of variance itself.
- Stop-loss calibration: stops sized on unconditional vol **fail** in high-persistence states;
  scale stops by `√(HL/HL_baseline)`.

**Loop spec.** Sentinel fits GARCH; Verifier fits HAR and requires the same qualitative state
(low/normal/extreme) — tolerance is on the *state*, not the parameter. Adversary checks the
fitting window excludes the evaluation period.

### R005 — Jump regime (discontinuity state)

**Definition.** Whether the price process is currently jump-dominated vs diffusion-dominated,
measured by the share of realized variance attributable to detected jumps.

**Calculation.**
- Lee–Mykland test on intraday returns with pre-averaging: jump at bar *i* if
  `|r_i| / σ̂_i > g(α)·Δ_n^{−ϖ}`-style threshold (practically: standardized return > 4.5 with
  bipower-variation local vol).
- Jump share `J = 1 − BV/RV` (Barndorff-Nielsen–Shephard: BV = bipower variation).
- Cadence: daily (from intraday bars); intraday flag on detection.
- Bands `[example]`: `J < 0.1` diffusion · `0.1–0.25` jumpy · `J > 0.25` jump-dominated
  (overnight gaps and halts dominate the variance budget).

**Efficacy modulation.**
- Stop-based and latency-sensitive strategies: **die** in jump-dominated states (slippage
  through stops; fills at dislocated prints). Mechanism: diffusion assumptions (continuous
  hedging, stop fills near trigger) break.
- Gap-fade strategies (overnight reversal): **improve** when jumps are isolated and
  liquidity returns; **die** when jumps cluster (news regime — see R047).
- Options market-making: jump risk reprices wings → widen quotes or withdraw.

**Loop spec.** Sentinel runs Lee–Mykland on 5-min bars; Verifier uses BNS `J` as the second
estimator; states must agree. Jump *detection* latency is acknowledged: the flag is
confirmatory, never predictive — Gate rejects any chapter that trades "predicted jumps."

### R006 — Vol-of-vol regime

**Definition.** The volatility of volatility itself — `σ(σ)`, proxied by VVIX (index) or by
the trailing std of daily changes in 30-day ATM IV (single names).

**Calculation.**
- Index: VVIX level and its percentile vs 252-day history.
- Single name: `VoV = stdev(ΔIV_30d, 20d) / mean(IV_30d)` (coefficient of variation of IV changes).
- Cadence: daily.
- Bands `[example]`: VVIX < 85 calm · 85–110 normal · > 110 stressed (vol itself is unstable).

**Efficacy modulation.**
- Vol-targeting / risk-parity overlays: **die** when VoV is high — the vol estimate you size
  on is itself noise; leverage whipsaws. Mechanism: sizing error ∝ VoV.
- Vega-weighted strategies: edge exists but mark-to-market variance explodes; **reduce**.
- Directional signals: second-order effect; use as a *sizing* input, not a trigger.

**Loop spec.** Sentinel computes both VVIX percentile and single-name VoV; Verifier
cross-checks IV-change series against a second surface vendor. High VoV + `UNKNOWN` on any
input → force `UNKNOWN` (do not size on noisy vol).

---

## TREND / RANGE REGIMES

### R007 — Trend-strength regime

**Definition.** Whether the market is in a directed (trending) or directionless state,
measured by ADX(14) and/or the Hurst exponent over the trading horizon.

**Calculation.**
- ADX(14) (Wilder): `+DM/−DM` smoothed, `DX = 100·|+DI − −DI| / (+DI + −DI)`, ADX = Wilder mean of DX.
- Hurst via DFA or R/S on 63-day window.
- Cadence: daily; 60-minute for intraday strategies.
- Bands `[documented]`: ADX > 25 trending · ADX < 20 chop (Wilder's original cutoffs);
  `[example]` Hurst: `H > 0.55` trending · `0.45–0.55` random · `H < 0.45` mean-reverting.

**Efficacy modulation.**
- Momentum/breakout (Donchian, time-series momentum family): **improve** strongly with ADX > 25;
  **die** below 20 (whipsaw). Mechanism: trend filters convert a 50/50 entry into positive
  expectancy only when autocorrelation is positive.
- Mean-reversion: mirror image — **improve** in chop, **die** in trend (fade-the-move gets run over).
- This is the highest-leverage regime switch in the document: most strategy failures are
  trend/chop misclassification, not bad signals.

**Loop spec.** Sentinel computes ADX + Hurst; Verifier requires *agreement of the two*
(trend/chop/random) — disagreement → `UNKNOWN`. Adversary tests that ADX is computed on the
strategy's own bar frequency (daily ADX must not gate 5-minute signals without validation).

### R008 — Range compression / expansion (squeeze) regime

**Definition.** Bollinger/Keltner bandwidth percentile: `BW = (Upper − Lower) / Middle`
as a percentile of its 252-day history. Extreme compression ("squeeze") precedes
volatility expansion; extreme expansion marks exhaustion.

**Calculation.**
- `BW_20,2σ` percentile-ranked vs 252 days. Head-fake filter: require compression ≥ 6 bars.
- Cadence: daily; intraday on 15-min bars for day-trading.
- Bands `[example]`: percentile < 10 squeeze (breakout watch) · 10–90 normal ·
  > 90 expansion (fade new breakouts; expect reversion to mean width).

**Efficacy modulation.**
- Breakout entries: **improve** from squeeze (measured move ≈ expansion to median width);
  **die** when entering *after* expansion (buying the exhaustion tail). Mechanism: bandwidth
  mean-reverts; entry edge is the distance from compressed to normal width.
- Iron-condor / short-strangle premium sellers: **improve** entering at expansion extremes
  (IV rich, width about to contract).

**Loop spec.** Sentinel tracks BW percentile; Verifier recomputes with Keltner (ATR-based)
bands — squeeze must appear on *both*. Fail-safe: squeeze alone is not a *directional*
signal; Gate rejects chapters that assign direction to the squeeze.

### R009 — Mean-reversion vs momentum dominance

**Definition.** The sign of short-horizon return autocorrelation: variance ratio
`VR(q) = σ²(q) / (q·σ²(1))`; `VR > 1` = momentum dominance, `VR < 1` = mean-reversion dominance.

**Calculation.**
- Overlapping q-period variance ratio on the strategy's bar frequency (e.g. q=4 on hourly bars),
  with heteroskedasticity-robust (Kim) test statistics.
- Cadence: weekly (needs enough bars for the test to have power).
- Bands `[example]`: `VR < 0.85` MR-dominant · `0.85–1.15` indeterminate · `VR > 1.15` momentum-dominant.
  Require |z| > 1.96 before acting — most weeks are indeterminate.

**Efficacy modulation.**
- Directly gates the two biggest strategy families in opposite directions; see R007.
  Adds value over ADX because it is *signed*: it tells you *which* family to run, not just
  whether to trade.
- Pairs trading: **improve** when idiosyncratic VR < 1 (spreads mean-revert); **die** when
  the common factor goes momentum-dominant (pairs legs diverge together).

**Loop spec.** Sentinel computes VR; Verifier computes first-order autocorrelation sign as the
second estimator. Indeterminate is a first-class state (trade half size), not a failure.
Adversary checks for multiple-testing: VR scanned across many q values must use a joint test.

---

## LIQUIDITY / MICROSTRUCTURE REGIMES

### R010 — Spread regime

**Definition.** Current quoted and effective spread as a percentile of the trailing 63-day
distribution, per instrument. The most direct execution-cost state variable.

**Calculation.**
- Quoted: `(ask − bid) / mid`, time-weighted over the session. Effective:
  `2·|trade_price − mid_at_trade| / mid`, volume-weighted.
- Percentile vs 63-day history, per name (never pooled across names).
- Cadence: 15-minute intraday refresh; daily summary.
- Bands `[example]`: < 50th normal · 50–90th wide (halve size) · > 90th extreme (stand down
  for cost-sensitive strategies).

**Efficacy modulation.**
- High-turnover microstructure strategies (S001/S003/S008 family): edge is a few bps;
  **die** mechanically when effective spread > edge. Mechanism: expected P&L ≈ edge − spread − fees.
- Lower-turnover swing strategies: mildly negative (worse entries), not fatal.

**Loop spec.** Sentinel from SIP/L1; Verifier from a second feed or the Corwin–Schultz
estimator on bars as fallback. SIP-vs-direct divergence (R050) widens the tolerance.
Fail-safe: spread `UNKNOWN` → assume 90th percentile (conservative).

### R011 — Depth / liquidity-provision regime

**Definition.** Book depth available at/near the touch relative to normal, and the price
impact per unit volume (Kyle's λ). Thin books = high λ = fragile prices.

**Calculation.**
- Depth: `(bid_size_1 + ask_size_1)` in shares and in *minutes of average volume*;
  percentile vs 63-day.
- Kyle's λ: OLS `Δmid_t = λ·signed_volume_t + ε` on 5-min bars, rolling 21 days.
- Cadence: intraday 15-min for depth; daily for λ.
- Bands `[example]`: depth < 25th percentile = thin; λ > 75th percentile = toxic impact.

**Efficacy modulation.**
- Large-size execution strategies (VWAP/POV): **die** in thin-book/high-λ states —
  scheduled participation rates become predatory. Mechanism: impact ∝ λ·√(participation).
- Small-size microstructure signals: **improve** mildly (bigger microprice moves per imbalance)
  but fill rates collapse — net neutral to negative.

**Loop spec.** Sentinel needs L1/L2 (Databento MBP-1 or equivalent); without it, state is
`UNKNOWN` — Gate forbids SIP-only depth inference (per honesty rule H6). Verifier checks λ
regression t-stat > 2 before trusting the level.

### R012 — Price-impact / Amihud illiquidity regime

**Definition.** Amihud ratio `ILLIQ = mean(|r_d| / DollarVolume_d)` over 21 days, percentile-ranked
per name. The daily-frequency cousin of R011 for universes without intraday depth.

**Calculation.**
- 21-day mean of |daily return| / dollar volume; rank vs 252-day history.
- Cadence: daily.
- Bands `[example]`: < 60th normal · 60–90th illiquid (widen slippage model 2×) · > 90th
  extreme (no new positions for impact-sensitive strategies).

**Efficacy modulation.**
- Small-cap / high-turnover strategies: **die** in illiquid states — the backtest's slippage
  assumption is violated first. Mechanism: realized slippage scales with ILLIQ; most published
  backtests assume constant slippage.
- All strategies: slippage model must be *state-dependent*; fixed-slippage backtests run in
  illiquid regimes overstate returns systematically.

**Loop spec.** Sentinel from daily bars (cheap — runs on the full 500-name universe);
Verifier spot-checks λ (R011) agreement on liquid names. Corporate actions must be
adjusted first (Adversary injects an unadjusted split to test the pipeline).

### R013 — Abnormal volume / participation regime

**Definition.** Current volume pace vs its intraday seasonal norm: `VPace_t = Vol_{0→t} /
E[Vol_{0→t} | history]` using a 21-day seasonal profile.

**Calculation.**
- Build per-name 5-min seasonal volume profile (median over 21 days); cumulative ratio intraday.
- Cadence: 5-minute intraday.
- Bands `[example]`: 0.7–1.3 normal pace · 1.3–2.0 heavy (news/flow day) · > 2.0 extreme
  (halt risk, gap risk) · < 0.7 dead (holiday-like; expect mean-reversion chop).

**Efficacy modulation.**
- Volume-clock signals (VPIN, dollar bars): heavy pace **compresses** their effective horizon —
  recalibrate or stand down. Mechanism: volume-time runs faster than wall-clock time.
- News/intensity strategies: **improve** on heavy pace (something is happening); dead pace
  **kills** breakout signals (no fuel).

**Loop spec.** Sentinel maintains seasonal profiles (rebuilt weekly); Verifier checks profile
stability (KS test vs prior week). Half-days and holidays get separate profiles — Adversary
tests that a half-day is not scored against a full-day profile.

### R014 — Informed-flow toxicity (VPIN) regime

**Definition.** Volume-synchronized probability of informed trading:
`VPIN = mean(|V_b − V_s| / V)` over n volume buckets (bulk volume classification).

**Calculation.**
- 50 buckets, bucket = 1/50 of average daily volume; BVC with per-bar σ.
- Cadence: per-bucket (intraday).
- Bands `[documented]`: > 0.7 extreme toxicity (preceded the 2010 flash crash by 60–90 min;
  spreads run 2–3× normal) · 0.5–0.7 elevated (majority-informed flow) · < 0.3 clean.
  (Easley, López de Prado & O'Hara 2012.)

**Efficacy modulation.**
- Market-making / passive-fill strategies: **die** above 0.7 — adverse selection spikes;
  widen quotes 2–3× or withdraw. Mechanism: toxicity = probability the counterparty knows more.
- Informed-flow *following* (momentum ignition): **improve** in 0.5–0.7 (trade *with* the
  toxic flow's direction); **die** above 0.7 (untradeable chop/violence).
- Retail-style mean reversion: **die** — fading informed flow is donating.

**Loop spec.** Sentinel computes VPIN; Verifier recomputes with tick-rule classification as
second estimator, tolerance ±0.1. Bounds check VPIN ∈ [0,1] mandatory. Fail-safe: VPIN
`UNKNOWN` during volume droughts (buckets never fill) — do not extrapolate.

### R015 — Tick-constraint regime

**Definition.** Whether the instrument is tick-constrained: spread = 1 tick > 50% of the time
and quote updates cluster at the minimum increment. Binding ticks change queue dynamics
entirely (time priority dominates price priority).

**Calculation.**
- `TickBind = fraction of quotes with (ask − bid) == tick_size`, rolling 21 days.
- Cadence: daily.
- Bands `[example]`: > 0.5 tick-constrained · < 0.2 tick-free. (SEC Tick Pilot / post-2016
  literature uses the same 1-tick-spread criterion.)

**Efficacy modulation.**
- Queue-position / latency strategies: **only exist** in tick-constrained names (queues form
  because price cannot improve); **die** in tick-free names (spread absorbs the edge).
- Spread-capture market making: **improve** when constrained (1-tick spread is capturable);
  **die** when a constrained name becomes unconstrained (e.g. after a split — edge halves).

**Loop spec.** Sentinel from quote data; Verifier confirms with trade-price clustering
(>80% of trades at round ticks corroborates). Corporate-action monitor: splits/reverse-splits
force recomputation — Adversary tests with a 4:1 split event.

### R016 — Fragmentation / off-exchange regime

**Definition.** Share of volume executing off-exchange (dark pools, wholesalers/SI):
`OffEx% = off-exchange volume / total volume` (FINRA ATS + non-ATS transparency data).

**Calculation.**
- Weekly FINRA data per symbol; daily proxy from TRF prints in TAQ.
- Cadence: weekly (daily proxy intraday).
- Bands `[example]`: < 35% lit-dominated · 35–45% normal (current US large-cap norm) ·
  > 45% dark-dominated (price discovery migrates off-exchange; lit quotes are stubbier).

**Efficacy modulation.**
- Lit-book microstructure signals (OFI on SIP): **degrade** as OffEx% rises — the book you
  see is a smaller fraction of true liquidity. Mechanism: signal is computed on a
  non-representative sample.
- Retail-flow strategies (payment-for-flow / wholesaler internalization): **improve** with
  high OffEx% (more segmentable flow).

**Loop spec.** Sentinel ingests FINRA weekly files; Verifier cross-checks TRF-proxy daily.
Lag acknowledged: FINRA data is ~2 weeks stale — state carries a vintage tag; Gate rejects
chapters that treat it as real-time.

## FUNDING / POSITIONING REGIMES

### R017 — Funding-stress regime

**Definition.** Stress in short-term funding markets: `SOFR–OIS spread` and repo fails.
Elevated spreads = balance-sheet scarcity = forced deleveraging ahead.

**Calculation.**
- `FS = SOFR − OIS_3M` in bps, daily (FRED/NY Fed). Repo fails volume (NY Fed primary dealer stats, weekly).
- Cadence: daily.
- Bands `[documented]`: SOFR–OIS < 10 bps normal · 10–25 bps tight · > 25 bps stressed
  (Sept-2019 repo spike printed > 200 bps intraday; quarter-ends routinely print 5–15 bps).
  `[example]` fails: top-decile weekly fails = stress.

**Efficacy modulation.**
- Leveraged / basis strategies: **die** in stress — funding cost spikes and haircuts widen
  simultaneously. Mechanism: expected return ≈ spread − funding; both legs move against you.
- All strategies: stress **precedes** deleveraging cascades; treat as an early-warning
  *risk* input, not a trade trigger.

**Loop spec.** Sentinel pulls FRED/NY Fed; Verifier cross-checks against FRA–OIS as second
estimator. Data is T+1 — vintage-tagged; never presented as intraday.

### R018 — Equity positioning / crowding regime

**Definition.** How crowded consensus positioning is: composite of equity put/call ratio,
short interest % float, and CTA/managed-money net positioning proxies.

**Calculation.**
- `PCR_21d` (CBOE total put/call, 21-day MA); `SI%` (short interest / float, bi-weekly);
  positioning proxy: futures COT net non-commercial or a CTA-trend-following return proxy.
- Composite z-score (equal-weight, sign-aligned so + = crowded long).
- Cadence: weekly.
- Bands `[example]`: |z| < 1 normal · 1–2 crowded (fade new entries in the crowded direction) ·
  > 2 extreme (contrarian watch — crowded longs precede air pockets).

**Efficacy modulation.**
- Momentum/trend: **improve** entering when uncrowded; **die** when extremely crowded
  (no marginal buyer left; reversals are violent). Mechanism: positioning sets the fuel
  remaining for the trend.
- Mean-reversion: **improve** at crowding extremes (the unwind *is* the reversion).

**Loop spec.** Sentinel maintains the composite; Verifier requires at least 2 of 3 inputs
fresh or state is `UNKNOWN` (COT is weekly-lagged — vintage tag). Adversary checks the
composite weights were fixed ex ante (no weight-mining).

### R019 — Crypto funding-rate regime

**Definition.** Perpetual-futures funding rate: `f_8h` per 8-hour period; persistent positive
= longs pay shorts = crowded-long positioning; negative = crowded short.

**Calculation.**
- Inputs: exchange funding rates (Binance/Bybit/OKX), premium index.
- Annualized: `f_ann = (1 + f_8h)^1095 − 1` (1095 = 3 periods/day × 365).
- Cadence: 8-hour (per funding interval); daily summary.
- Bands `[example]`: |f_8h| < 0.01% neutral · 0.01–0.05% leaning · > 0.05% crowded
  (annualized ≈ 55%+ — longs are paying ruinous carry; reversal/cascade risk high).
  Use `reported_funding` labeling — public aggregators are censored lower bounds.

**Efficacy modulation.**
- Crypto momentum: **improve** when funding neutral-to-leaning (trend has carry support);
  **die** when extremely positive (longs pay 50%+ annualized — the trend is *rented*).
  Mechanism: funding is a direct holding cost; extreme funding = crowded = liquidation fuel.
- Basis/cash-and-carry: **improve** when |funding| large (harvest the spread); the
  SB10-verified example: 0.020/0.015/0.025% 8-h rates on $10k = $6 gross funding/day,
  minus 4 × 0.04% execution legs ($16) = −$10 net — costs dominate naive harvests.

**Loop spec.** Sentinel polls 3+ venues; Verifier requires cross-venue agreement on sign.
Exchange API outage → `UNKNOWN` (never carry a stale funding rate into sizing).

### R020 — Options gamma positioning (GEX) regime

**Definition.** Aggregate dealer gamma exposure: `GEX = Σ_strikes Γ · OI · S² · dealer_sign`,
positive = dealers long gamma (dampening, pinning), negative = dealers short gamma
(amplifying, gap risk). Requires **full-chain OI** — sampled chains understate.

**Calculation.**
- Inputs: full option chain OI + greeks, dealer positioning assumption (customers net long
  options ⇒ dealers net short, the standard proxy — disclosed as assumption, not fact).
- Normalize by average daily dollar volume → "gamma flip" distance in index points.
- Cadence: daily (15:30 ET snapshot); intraday on event days.
- Bands `[example]`: GEX > +0.5% of ADV$ = pinning (expect magnet toward high-OI strikes) ·
  |GEX| small = neutral · GEX < −0.5% = amplifying (expect trend-day violence; widen stops 2×).

**Efficacy modulation.**
- Intraday mean-reversion / pinning strategies: **improve** in positive-GEX (dealers hedge
  *against* moves — free reversion flow). **Die** in negative-GEX (dealer hedging *chases*
  moves — fades get run over). Mechanism: dealer delta-hedging is the largest intraday
  uninformed flow on many days.
- Breakout: mirror image — **improve** in negative GEX.

**Loop spec.** Sentinel needs full-chain OI (not sampled); Verifier recomputes with an
independent greeks engine (tolerance on *sign and quintile*, not the dollar value).
Honesty: GEX never reveals actual dealer positioning — chapters must say "GEX proxy,"
never "dealers are positioned X."

### R021 — Retail-flow dominance regime

**Definition.** Share of volume attributable to retail: odd-lot % of trades, wholesaler/SI
print share, small-trade (<$5k notional) volume fraction.

**Calculation.**
- `Retail% = odd-lot trades / total trades` (TAQ), or sub-penny/SI print share as proxy.
- Cadence: daily.
- Bands `[example]`: < 15% institutional tape · 15–25% mixed · > 25% retail-dominated
  (meme/0DTE names print 40%+).

**Efficacy modulation.**
- Microstructure signals calibrated on institutional flow: **degrade** when retail dominates
  (different adverse-selection profile — retail is uninformed but herded). Mechanism: the
  *composition* of counterparties changes the mapping from imbalance to future return.
- Attention/momentum-ignition strategies: **improve** (retail herding creates the drift).

**Loop spec.** Sentinel from TAQ odd-lot flags; Verifier uses SI-print share as second
estimator. Classification-rule changes (e.g. odd-lot definition updates) force recalibration
— Adversary tests with a simulated rule change.

### R022 — Hard-to-borrow / short-squeeze regime

**Definition.** Stock borrow cost and utilization: `fee` (annualized), `utilization` (on-loan /
lendable), days-to-cover (short interest / ADV).

**Calculation.**
- Inputs: securities-lending data (vendor indicative) or Reg SHO threshold list as a
  coarse public proxy; DTC from short-interest + ADV.
- Cadence: daily.
- Bands `[example]`: fee < 1% easy · 1–10% firm · > 10% hard-to-borrow · utilization > 90%
  + DTC > 5 = squeeze candidate (crowded short + no borrow left = explosive upside tail).

**Efficacy modulation.**
- Short strategies: **die** when fee > expected edge — borrow cost is a direct, uncapped
  negative carry; buy-ins add gap risk. Mechanism: P&L_short ≈ −return − fee − buy-in risk.
- Long-vol / convexity strategies: **improve** into squeeze candidates (right-tail cheap).

**Loop spec.** Sentinel ingests lending feed; without it, Reg SHO list is a coarse fallback
(state carries a low-confidence tag). Verifier checks fee vs utilization consistency
(high fee + low utilization = data error → `UNKNOWN`).

### R023 — Liquidation-cascade regime (crypto)

**Definition.** Forced-selling state in crypto derivatives: reported 24-h liquidations vs
trailing baseline, long/short liquidation skew.

**Calculation.**
- `LiqZ = (reported_liqs_24h − median_30d) / IQR_30d`; skew = long-liqs / total-liqs.
- Cadence: hourly.
- Bands `[example]`: LiqZ < 2 normal · 2–4 cascade watch (stops clustering) · > 4 active
  cascade (do not fade; liquidity is one-sided). Label everything `reported_*` — public
  aggregators are censored lower bounds (per SB10 correction).

**Efficacy modulation.**
- Mean-reversion dip-buys: **die** during active cascades (liquidation flow is price-insensitive;
  the "discount" keeps discounting). Mechanism: forced sellers have no reservation price.
- Post-cascade reversal: **improve** *after* LiqZ normalizes + funding resets (exhaustion signal).

**Loop spec.** Sentinel polls 2+ aggregators; Verifier requires agreement on cascade/no-cascade
state. Exchange status page monitored — matching-engine halts force `UNKNOWN`.

---

## MACRO REGIMES

### R024 — Interest-rate level/direction regime

**Definition.** The Fed policy stance: hiking / on-hold / cutting, plus the level of real rates.
Sets the discount-rate gravity for all risk assets and the carry on cash.

**Calculation.**
- Inputs: Fed funds target, 2y/10y real yields (TIPS), Fed meeting calendar.
- State machine: hike if last move + and next-meeting hike prob > 60% (Fed funds futures);
  cut symmetrically; else on-hold. Real 10y > 2% = restrictive `[example]`.
- Cadence: daily; event-driven on FOMC days.

**Efficacy modulation.**
- Duration-sensitive equity factors (growth vs value): **rotation driver** — rising real rates
  **kill** long-duration growth momentum and **help** value/cash-flow factors. Mechanism:
  discount-rate repricing hits long-duration cash flows hardest.
- Intraday signals: second-order; use as a *factor-tilt* input, not a trigger.

**Loop spec.** Sentinel tracks futures-implied probs; Verifier cross-checks with primary-dealer
survey medians. State changes only on actual moves or >60% threshold crossings (no flip-flop).

### R025 — Yield-curve shape regime

**Definition.** `2s10s = 10y − 2y` spread: normal/upward (positive), flat, inverted (negative).
Inversion is the classic late-cycle/recession warning; re-steepening marks regime change.

**Calculation.**
- Daily constant-maturity yields (FRED: DGS2, DGS10).
- Bands `[documented]`: > +100 bps steep · 0–100 normal · < 0 inverted (every US recession
  since 1976 was preceded by inversion; lag 6–18 months — it is a *cycle* indicator, not a
  timing signal).

**Efficacy modulation.**
- Bank/financial-sector signals: **improve** when steepening (NIM expansion); **die** deeply
  inverted (credit stress ahead).
- Curve-trade strategies: the regime *is* the signal — position for the re-steepening,
  not the inversion.

**Loop spec.** Sentinel from FRED; Verifier from Treasury XML as second source. Revisions
are rare; vintage-tag anyway.

### R026 — Inflation-surprise regime

**Definition.** Whether inflation prints are surprising up or down: standardized surprise
`S = (actual − consensus) / σ_surprises` on CPI/PPI/PCE, plus breakeven momentum.

**Calculation.**
- Surprise z-score per release, 12-month trailing σ; 5y5y breakeven 20-day change.
- Cadence: event-driven (release days) + daily breakeven monitor.
- Bands `[example]`: S > +1.5 hot surprise (rates reprice up; growth sells) · |S| < 1 neutral ·
  S < −1.5 cold (cut pricing; duration bid).

**Efficacy modulation.**
- Rates/FX intraday strategies: surprise days are the **highest-efficacy** sessions of the
  month (real information, directional). Mechanism: genuine news → informed repricing.
- Pre-release positioning fades: **die** — spreads widen 3–5× into the print (R010).

**Loop spec.** Sentinel ingests economic calendar + consensus (vendor); Verifier checks the
actual print against BLS release. Timestamp discipline: the regime flips only *after* the
8:30 ET print — Adversary tests for pre-print leakage.

### R027 — Growth-surprise regime

**Definition.** Citi-style Economic Surprise Index (ESI): 3-month rolling z-score of
(data − consensus) across growth releases (payrolls, ISM/PMI, retail sales).

**Calculation.**
- `ESI = Σ w_i·(actual_i − consensus_i)/σ_i` over trailing 63 releases; sign = growth
  surprising up/down.
- Cadence: daily (recomputed on each release).
- Bands `[example]`: ESI > +20 strong (risk-on tilt) · −20…+20 neutral · < −20 weak
  (defensive tilt; credit stress watch — see R028).

**Efficacy modulation.**
- Cyclical-vs-defensive rotation signals: ESI sign is a first-order tilt.
- Intraday equity momentum: positive ESI **extends** trend days (fundamental tailwind).

**Loop spec.** Sentinel computes from vendor surprise feed; Verifier spot-checks 3 releases
per month against primary sources. Methodology fixed ex ante (weights published in the
chapter) — no re-weighting after the fact.

### R028 — Credit-stress regime

**Definition.** High-yield option-adjusted spread (HY OAS) level and momentum — the market's
summary statistic for default fear and risk appetite.

**Calculation.**
- ICE BofA US High Yield OAS (FRED: BAMLH0A0HYM2), daily; 20-day change.
- Bands `[documented]`: < 350 bps calm · 350–550 bps watch · > 550 bps stressed
  (2008: >2000; 2020: ~880; 2022: ~600). `[example]` momentum: +100 bps in 20 days = acute.

**Efficacy modulation.**
- Credit-sensitive equity strategies (high-beta, small-cap): **die** as OAS blows out —
  the equity is a junior claim on the same deteriorating credit. Mechanism: Merton —
  equity vol and credit spreads are two views of one leverage state.
- Safe-haven / quality factors: **improve**.

**Loop spec.** Sentinel from FRED; Verifier from ICE direct. Revisions minimal. State is
slow-moving — Gate rejects chapters that day-trade off it.

### R029 — Dollar regime

**Definition.** DXY trend and level: a strong dollar tightens global financial conditions
(EM stress, commodity headwinds); a weak dollar loosens them.

**Calculation.**
- DXY 50-day vs 200-day (trend) + percentile vs 5-year range (level).
- Cadence: daily.
- Bands `[example]`: uptrend + >75th percentile = strong-dollar (risk-off tilt for EM/commodities) ·
  downtrend + <25th = weak-dollar (risk-on).

**Efficacy modulation.**
- Commodity/FX-carry strategies: first-order driver.
- US equity intraday: second-order; multinationals' earnings translation is the channel —
  use as a sector-tilt input.

**Loop spec.** Sentinel from FX feeds; Verifier from a second vendor. 24-hour market —
  define the "day" cut explicitly (17:00 ET) to avoid timestamp seams.

### R030 — Central-bank event proximity

**Definition.** Trading-day distance to the next scheduled FOMC/ECB/BOJ decision: pre-event
drift/compression vs event-day repricing vs post-event digestion.

**Calculation.**
- Calendar distance `d` in trading days to the next decision.
- Cadence: daily.
- Bands `[example]`: d > 5 normal · 1–5 pre-event (positioning drift, vol bid — see R003) ·
  d = 0 event day (intraday strategies: trade the *reaction*, not the decision; spreads 3–5×) ·
  d = −1…−3 post-event digestion (follow-through or reversal day).

**Efficacy modulation.**
- Pre-event: directionless drift **kills** breakout signals (false breakouts into the event).
- Event window: **highest** intraday efficacy for reaction strategies *after* the statement —
  genuine information, one-sided flow.
- Post-event: momentum **improves** (institutional repositioning takes days).

**Loop spec.** Sentinel owns the calendar (FOMC/ECB/BOJ schedules, updated yearly);
Verifier checks against exchange holiday calendars (no event-day trading on holidays).
Adversary tests the 14:00 ET statement timestamp — no pre-statement regime flip.

## CROSS-ASSET STRESS REGIMES

### R031 — Cross-asset correlation regime

**Definition.** Average pairwise correlation across major assets (equities, bonds, commodities,
FX): high correlation = diversification breakdown = "risk-on/risk-off" monoculture.

**Calculation.**
- 63-day rolling mean pairwise correlation of daily returns across N=8–12 liquid benchmarks
  (SPY, TLT, GLD, DBC, UUP, HYG, EEM, QQQ).
- Cadence: daily.
- Bands `[example]`: < 0.2 normal diversification · 0.2–0.4 elevated (macro factor dominates) ·
  > 0.4 monoculture (single-factor market; stock-picking edge collapses).

**Efficacy modulation.**
- Single-name / idiosyncratic signals (pairs, earnings drift): **die** in monoculture —
  everything moves with the factor; idiosyncratic edge is drowned. Mechanism: R² of the
  market factor → 1; residual variance → 0.
- Factor/macro-timing strategies: **improve** (the factor *is* the trade).

**Loop spec.** Sentinel computes on the fixed benchmark set (set published ex ante);
Verifier uses a second benchmark set. Benchmark changes require chapter errata —
Adversary checks the set was not cherry-picked ex post.

### R032 — Flight-to-quality (stock/bond correlation sign)

**Definition.** Sign of the 63-day stock–bond return correlation (SPY vs TLT): negative =
normal (bonds hedge equities); positive = inflation-fear regime (both sell off together).

**Calculation.**
- `ρ_63d(SPY, TLT)` daily returns.
- Cadence: daily.
- Bands `[example]`: ρ < −0.2 normal hedge · −0.2…+0.2 transition · ρ > +0.2
  inflation-fear (2022 printed sustained positive — the 60/40 portfolio's worst year).

**Efficacy modulation.**
- Risk-parity / balanced strategies: **die** when ρ flips positive — the hedge becomes a
  second loss. Mechanism: diversification ratio collapses.
- CTA/trend: **improve** (trends are cleaner when the macro driver is singular).

**Loop spec.** Sentinel computes; Verifier substitutes IEF for TLT (second estimator).
Sign flips require 21-day confirmation (no whipsaw on noise).

### R033 — Systemic tail-risk / crisis regime

**Definition.** Joint tail-risk state: co-occurrence of extreme moves across assets —
measured by the fraction of benchmarks jointly in their 5% tails, or a CoVaR-style
systemic-risk proxy.

**Calculation.**
- `TailCount_t = #{benchmarks with |r_t| > 2.5σ_63d} / N`; crisis if ≥ 3 of 8 on the same day,
  or 2 consecutive days with ≥ 2.
- Alternative: SRISK-style capital shortfall proxy (documented as slow-moving).
- Cadence: daily.
- Bands `[example]`: 0–1 normal · 2 watch · ≥3 crisis (stand down directional; only
  liquidity-provision-at-extreme-spread or flat).

**Efficacy modulation.**
- Nearly everything directional: **die** — correlations → 1, gaps dominate, fills are
  fictional vs backtest assumptions. Mechanism: the return distribution's tails, which
  backtests underweight, become the distribution.
- Explicit tail-hedge / long-gamma: the *only* family that **improves** — this is what it is for.

**Loop spec.** Sentinel counts tails; Verifier recomputes σ with a second window (126d).
Crisis state requires Gate-level human acknowledgment to *trade into* (fail-safe: default
action on crisis = reduce, never add).

### R034 — Energy / commodity shock regime

**Definition.** Oil (WTI/Brent) in shock state: 20-day move > 15% or price > 90th percentile
of 3-year range — an input-cost shock for the whole economy.

**Calculation.**
- `ShockZ = (P_t − mean_63d) / σ_63d` on front-month futures; shock if |ShockZ| > 3.
- Cadence: daily.
- Bands `[example]`: |Z| < 2 normal · 2–3 elevated · > 3 shock (1973/1990/2008/2022 playbook:
  airlines/transports sell off, energy momentum ignites, inflation expectations jump).

**Efficacy modulation.**
- Energy-sector momentum: **improve** violently (the shock *is* the trend).
- Transport/consumer-discretionary mean-reversion: **die** (fundamental repricing, not noise).
- Broad-market intraday: volatility up, direction hostage to headlines — halve size.

**Loop spec.** Sentinel from futures feeds; Verifier from a second vendor. Futures rolls
handled explicitly (back-adjusted series; Adversary injects a roll date to test).

---

## CALENDAR / EVENT REGIMES

### R035 — Earnings proximity / earnings season

**Definition.** Days-to-earnings for the name (`d_earn`) and the market-wide earnings-season
flag (weeks when > 20% of S&P 500 reports).

**Calculation.**
- Per-name: vendor earnings calendar; market: fraction of index reporting this week.
- Cadence: daily.
- Bands `[example]`: d_earn > 10 normal · 3–10 pre-earnings (IV bid — see R003; drift strategies
  work, breakout dies) · 0–2 post-earnings (PEAD/drift strategies at max efficacy — S100 family).

**Efficacy modulation.**
- Post-earnings drift (SUE-based): **improve** sharply days 0–5 — the most documented
  intraday/multi-day anomaly in the document. Mechanism: underreaction + institutional
  repositioning lags.
- Overnight-hold strategies: **die** into the print (binary gap risk); IV crush punishes
  long premium.

**Loop spec.** Sentinel owns the calendar; Verifier checks announced-date vs actual-report
timestamp (after-hours vs before-open matters — Adversary tests a date-shifted report).
Timestamp accuracy is load-bearing (per SB10 correction: close-to-close event returns do
not demonstrate intraday tradability).

### R036 — Macro announcement windows

**Definition.** Scheduled high-impact releases (CPI, payrolls, FOMC — see R030): pre-release
compression, release-minute repricing, post-release digestion.

**Calculation.**
- Economic calendar with impact ratings; window flags: T−60min…T−1min (compression),
  T…T+15min (repricing), T+15min…close (digestion).
- Cadence: event-driven, minute resolution.

**Efficacy modulation.**
- Breakout signals: **die** in compression (false breaks), **ignite** in repricing —
  but only trade *after* the number with limit orders; market orders in the first 60 seconds
  are filled at the worst print of the day. Mechanism: adverse selection is maximal when
  the information asymmetry is maximal.
- Post-release trend: **improve** (see R030).

**Loop spec.** Sentinel publishes machine-readable windows; Verifier checks release
timestamps against primary sources (BLS/Fed). Fail-safe: calendar feed down → assume
no-trade windows around *known* monthly dates (first Friday = payrolls).

### R037 — Month/quarter-end rebalancing

**Definition.** The last 2 and first 1 trading days of month/quarter: mechanical pension/mutual-fund
rebalancing flows (buy losers, sell winners to restore target weights).

**Calculation.**
- Calendar flag + estimated rebalance pressure: `(target_w − current_w) × AUM_proxy`
  for major indices (vendor model, indicative).
- Cadence: monthly/quarterly.

**Efficacy modulation.**
- Month-end reversal (buy-the-loser): **improve** — the most mechanical predictable flow in
  equities. Mechanism: price-insensitive rebalancing = free liquidity for contrarians.
- Momentum: **die** into month-end (winners get sold mechanically — head-fake).

**Loop spec.** Sentinel flags the window; Verifier estimates pressure with an independent
AUM model. Pressure estimates are `indicative` — Gate rejects chapters that size on them
precisely.

### R038 — Thin-liquidity sessions

**Definition.** Half-days, post-holiday sessions, summer-Friday afternoons: volume < 70% of
seasonal norm with normal news flow — spreads wide, depth thin, moves exaggerated.

**Calculation.**
- Exchange calendar (half-days: day after Thanksgiving, Christmas Eve, July 3rd when
  applicable) + `VPace < 0.7` (R013) confirmation.
- Cadence: daily.

**Efficacy modulation.**
- Everything cost-sensitive: **die** — effective spreads 1.5–2× normal with no compensating
  edge. Mechanism: fixed costs, thinner edge.
- Opportunistic liquidity provision: **improve** for patient limit orders (paid the wide spread).

**Loop spec.** Sentinel owns the exchange calendar (updated yearly); Verifier confirms with
realized VPace. Adversary tests that backtests *exclude* or separately model these sessions
(they are a classic backtest flatterer when mishandled).

### R039 — Options expiry / OpEx pinning

**Definition.** Monthly/quarterly options expiration weeks: pinning (stock gravitates to
high-OI strikes — see R020 GEX) and expiry-day volume/imbalance distortions.

**Calculation.**
- Calendar flag (third Friday monthly; quarterly = triple-witching); distance-to-strike for
  top-OI strikes.
- Cadence: weekly/daily in expiry week.

**Efficacy modulation.**
- Pinning strategies (short straddle into OpEx Friday): **improve** when GEX positive and
  stock within 0.5% of max-pain strike. Mechanism: dealer hedging *is* the pin.
- Directional breakout: **die** into expiry (pinned); **ignite** the Monday after
  (hedging flows release).

**Loop spec.** Sentinel combines calendar + OI snapshots; Verifier recomputes max-pain
independently. 0DTE regime note: daily expiries have *diluted* classic monthly pinning —
chapters must not apply 2010s pinning statistics to 2026 without re-verification.

### R040 — Index rebalance days

**Definition.** S&P/Dow/Russell rebalance effective dates: mechanical index-fund flows at the
close, announced in advance — the most telegraphed trade in equities.

**Calculation.**
- Index announcement calendars; estimated add/delete dollar flow = Δweight × index AUM.
- Cadence: quarterly (S&P), annual (Russell).

**Efficacy modulation.**
- Front-running adds/deletes: **improve** in the announcement-to-effective window
  (documented pre-effective drift); **die** after the effective close (the trade is over;
  post-effective reversal is the documented fade).
- Closing-auction strategies: **improve** on effective dates (record MOC volume).

**Loop spec.** Sentinel tracks announcements; Verifier checks effective-date timestamps.
Flow estimates indicative only. Fail-safe: additions/deletions fail or are delayed —
never assume the announced trade happened.

## SESSION / INTRADAY REGIMES

### R041 — Overnight-gap dominance regime

**Definition.** Whether the instrument's return variance is dominated by the overnight
(close-to-open) vs the intraday (open-to-close) session: `ON_share = σ²_overnight / σ²_total`.

**Calculation.**
- Variance decomposition on 63 days: overnight log-returns vs open-to-close.
- Cadence: weekly.
- Bands `[example]`: ON_share < 0.3 intraday-dominated (day-trade the signals; overnight holds
  add uncompensated gap risk) · 0.3–0.5 mixed · > 0.5 overnight-dominated (the signal lives in
  the gap — intraday-only strategies are trading the noise around it).

**Efficacy modulation.**
- Intraday-only strategies on overnight-dominated names (many large-cap tech names):
  systematically **underperform** their backtests — the backtest's close-to-close returns
  include gaps the strategy never traded. Mechanism: return attribution mismatch.
- Gap-fade / gap-continuation: **improve** where ON_share is high (the phenomenon is large).

**Loop spec.** Sentinel decomposes variance; Verifier uses a second corporate-action-adjusted
series. Dividends/splits must be adjusted first — Adversary injects an unadjusted special
dividend to test.

### R042 — Time-of-day liquidity (U-shape) regime

**Definition.** The intraday U-shape: spreads wide + volume heavy at open, thin midday,
volume-heavy into the close. The * tradability* of a signal varies by 2–3× across the day.

**Calculation.**
- Per-name 5-min seasonal profiles of spread and volume (21-day medians).
- Three states by clock: open (09:30–10:30 ET), midday (10:30–15:00), close (15:00–16:00).
- Cadence: profiles rebuilt weekly.

**Efficacy modulation.**
- Open: signals **strong but expensive** — information density highest, spreads widest;
  net edge often *lower* than midday despite stronger gross signals. Mechanism: edge − cost.
- Midday: **best net** for microstructure mean-reversion (tight spreads, patient fills).
- Close: **best net** for momentum/drift (MOC flows, institutional urgency — counterparties
  pay up).

**Loop spec.** Sentinel maintains profiles; Verifier KS-tests profile stability week to week.
Half-days get separate profiles (see R038). Gate rejects any chapter whose backtest assumes
constant intraday costs.

### R043 — Closing-auction imbalance regime

**Definition.** NYSE/Nasdaq closing-auction imbalance state: published imbalance (side + size)
in the 15:00–16:00 window vs its norm — predicts the closing-print dislocation.

**Calculation.**
- Inputs: exchange imbalance feeds (NYSE TAQ imbalance messages; Nasdaq NOII).
- `ImbZ = (imbalance_shares − median_21d) / IQR_21d`, signed by side.
- Cadence: 1-minute in the last 30 minutes.

**Efficacy modulation.**
- MOC/LOC strategies: |ImbZ| > 3 **is** the signal — fade small imbalances (liquidity
  arrives), follow large ones (price must move to clear). Mechanism: the auction *must*
  clear; the imbalance is public but the clearing price isn't.
- Strategies holding into the close for other reasons: large imbalances = **worse** fills;
  route around or flatten.

**Loop spec.** Sentinel ingests imbalance feeds (TAQ subscription required); without the
feed, state is `UNKNOWN` — SIP NBBO alone cannot see auction imbalances (honesty rule H6).
Latency note: imbalance data is delayed by design; chapters must state the feed's delay.

---

## STRUCTURAL REGIMES

### R044 — Market concentration regime

**Definition.** Cap concentration: top-10 weight in the S&P 500, or HHI `Σ w_i²` of the index.

**Calculation.**
- Monthly index weights; HHI on a 0–1 scale (×10,000 in antitrust units).
- Cadence: monthly.
- Bands `[example]`: top-10 < 25% diffuse · 25–35% concentrated · > 35% extreme
  (2024–2026 printed 35%+ — the most concentrated since the 1960s "Nifty Fifty").

**Efficacy modulation.**
- Equal-weight / small-cap rotation signals: **improve** when concentration is extreme
  (mean-reversion of concentration is a multi-year tailwind).
- Cap-weighted momentum: **improve** *during* the concentration trend (the mega-caps *are*
  the momentum); **die** at the turn.

**Loop spec.** Sentinel from index weight files; Verifier from a second vendor. Slow-moving —
  Gate rejects intraday triggers off it.

### R045 — Dispersion regime

**Definition.** Cross-sectional dispersion: `Disp = stdev(r_i) / |r_index|` — high dispersion =
stock-picking environment; low = macro-factor environment.

**Calculation.**
- Daily cross-sectional σ of S&P 500 constituent returns, normalized by index |return|;
  63-day MA.
- Cadence: daily.
- Bands `[example]`: percentile vs 5-year: < 30th low (pairs suffer — no idiosyncratic
  spread to harvest) · 30–70th normal · > 70th high (stock-picking golden age).

**Efficacy modulation.**
- Pairs / stat-arb / earnings-drift: **improve** strongly in high dispersion (more
  idiosyncratic variance = more spread to harvest). Mechanism: pair P&L ∝ idiosyncratic vol.
- Index-directional strategies: roughly neutral.

**Loop spec.** Sentinel computes on fixed constituent list (as-of membership to avoid
survivorship bias — Adversary checks); Verifier uses sector-neutralized dispersion as
second estimator.

### R046 — Factor-crowding regime

**Definition.** Crowding in rewarded factors (momentum, value, quality): factor return
autocorrelation and factor-vol percentile — crowded factors crash together (momentum crashes).

**Calculation.**
- Factor returns (vendor or Fama–French library); `CrowdZ` = 63-day factor vol percentile
  + 21-day factor return (extended winners = crowded).
- Cadence: weekly.
- Bands `[example]`: factor vol > 80th percentile + trailing return > +2σ = crowded
  (momentum-crash watch — Daniel & Moskowitz 2016 documented the crash anatomy).

**Efficacy modulation.**
- Factor-timing / factor-momentum: **improve** when uncrowded; **die** when crowded
  (crashes are fast, −20% months). Mechanism: crowding = correlated exit demand.
- Contrarian factor rotation: **improve** at crowding extremes.

**Loop spec.** Sentinel from factor library; Verifier with independently built factors
(tolerance on *quintile*, not bps). Factor definitions fixed ex ante.

### R047 — News-flow intensity / novelty regime

**Definition.** The rate and novelty of news: articles/day per ticker (intensity) and
embedding-novelty vs trailing corpus (novelty) — see T-batch news-novelty mechanics.

**Calculation.**
- Intensity: count/day vs 30-day median. Novelty: `1 − cos(e_i, centroid_trailing_10d)`
  on article embeddings (per SB10/T-batch convention).
- Cadence: daily; intraday on intensity spikes.
- Bands `[example]`: intensity > 3× median = news storm (prices driven by headlines —
  technical signals **die**); novelty < 0.2 = stale-news regime (fade-the-move **improves** —
  the move is liquidity/attention, not repricing).

**Efficacy modulation.**
- Technical/microstructure signals: **die** in news storms (order flow is information-driven;
  historical patterns don't bind). Mechanism: the data-generating process changes.
- News-novelty reversal: **improve** when novelty low (stale news fades); **die** when
  novelty high (fresh news reprices — do not fade).

**Loop spec.** Sentinel ingests news API (vendor); Verifier checks timestamp integrity
(wire time vs publish time — Adversary injects a delayed wire to test). Embargo-attribution
rule: the regime label uses only articles published ≤ *t*.

### R048 — Halt / limit-up-down proximity regime

**Definition.** Whether the instrument is approaching or in a trading halt / LULD band state:
distance to the LULD band in σ units, halt-history flag.

**Calculation.**
- `BandDist = (band_edge − price) / σ_5min`; halt if exchange halt feed active.
- Cadence: real-time (seconds).

**Efficacy modulation.**
- Everything: **stand down** inside 1σ of the band — fills are at dislocated prints,
  quotes may be stub, reopening auctions gap. Mechanism: the continuous-trading assumptions
  (S-chapter math) are void.
- Post-halt reopen strategies: a specialized family — only with explicit halt-reopen
  mechanics, never with continuous-session logic.

**Loop spec.** Sentinel monitors SIP halt messages + LULD bands; Verifier cross-checks the
exchange status page. Fail-safe: any halt-message parse failure → assume halted
(`UNKNOWN` = stand down, never trade through).

### R049 — Short-sale restriction regime

**Definition.** Reg SHO / exchange short-sale restrictions active: SSR (alternative uptick)
triggered (price −10% intraday), hard halts on shorting, or regulatory bans.

**Calculation.**
- `SSR_active = (day_low ≤ 0.9 × prev_close)` for US equities (Rule 201); ban lists from
  regulator notices.
- Cadence: daily + intraday trigger check.

**Efficacy modulation.**
- Short strategies: **die** mechanically — borrow disappears, uptick rule blocks entries,
  existing shorts face buy-ins. Mechanism: the strategy's *action set* is restricted.
- Long-only momentum: **improve** mildly (short-covering adds fuel; the 2008 ban
  documented short-squeeze amplification).

**Loop spec.** Sentinel computes the −10% trigger from adjusted closes; Verifier checks the
Reg SHO threshold list. Corporate actions adjusted first. Chapters must state the
jurisdiction — rules differ US/EU/Asia.

### R050 — Cross-venue / SIP-vs-direct divergence regime

**Definition.** Latency/divergence state between the SIP consolidated feed and direct
exchange feeds: quote divergence in bps and SIP latency in microseconds — the "two markets"
problem for anyone not colocated.

**Calculation.**
- `Div = |mid_direct − mid_SIP| / mid_SIP` in bps, sampled per second on a colocated box;
  SIP latency from feed timestamps.
- Cadence: real-time (requires colocation to measure honestly).
- Bands `[example]`: Div < 0.5 bps converged · 0.5–2 bps divergent (SIP signals degraded) ·
  > 2 bps fractured (SIP-only backtests are fiction — see honesty rule H6).

**Efficacy modulation.**
- All latency-sensitive signals backtested on SIP: **overstated** in divergent states —
  the fill you simulated never existed at your venue. Mechanism: queue position and price
  priority are venue-specific.
- Colocated strategies: **improve** relatively (the divergence *is* their edge).

**Loop spec.** Sentinel requires a colocated measurement box; without it, the state is
permanently `UNKNOWN` and every latency-sensitive chapter carries the
`simulated only — requires MBO/ITCH` label. This is a *capability* gate, not just a
regime: the M5 Max on a desk cannot measure R050 (per TB9 Grok verdict).

---

## Appendix — regime interaction notes (for chapter writers)

1. **Regimes compound.** R001 (high RV) + R014 (toxic flow) + R033 (crisis) is not three
   independent filters — it is one state: *untradeable for directional intraday*. Writers:
   state the *joint* implication, not three separate ones.
2. **Regime hierarchy for annotation.** When annotating S/T chapters (Phase 3), list at most
   6 regimes per chapter, ordered by impact magnitude. Prefer the *most specific* regime
   (R014 toxicity over R001 high-vol when the mechanism is adverse selection).
3. **Direction discipline.** Every annotation line states direction explicitly:
   "R007-trend strengthens momentum entries" / "R010-wide spreads erase the 2–4 bps edge."
   Never "affected by volatility."
4. **No regime-mining.** A regime may gate a strategy only with a pre-registered definition
   and lagged label. Post-hoc "it works when we exclude 2020" is quarantined on sight.
5. **Crypto chapters** use `reported_*` naming for all public liquidation/funding/OI inputs
   (censored lower bounds — per SB10 correction).
6. **GEX chapters** use "GEX proxy" phrasing; full-chain OI required; never claim actual
   dealer positioning (per SB10 correction).
7. **Cost-model cross-check.** Every R chapter's M5 Max costing cites notes/cost-model.md
   (§2/§3/§5) or is labeled `measured on <date>`; vendor prices suffixed
   `indicative — verify before budgeting`.
