# Chatbot Question Bank — 20 batches × 3 copy-paste questions

**How to use.** Each batch below has exactly 3 questions. Copy the fenced text verbatim into any
no-login or logged-in chatbot (Grok web, Cursor chat, DeepSeek chat, Kimi/Moonshot).
Record which bot answered and the date. Treat every answer as a *lead*, not a fact:
anything without a checkable source (paper title/URL/arXiv ID) goes in the chapter's
`Unverified leads` list, never in `Sources`.

**The 4 demands in every question triple.**
- Q1 → (a) exact formulas with parameter ranges + (b) one concrete worked numerical example.
- Q2 → (c) local-build cost/feasibility on a 128GB Apple M5 Max Mac (throughput, RAM, stack,
  engineering hours) + buy-vs-build vendor options with indicative pricing.
- Q3 → (d) documented success ratios / after-cost efficacy + when it fails.

**Standing context to paste with Q1 of each batch (bots need it once):**
> Context: I am writing a deep-dive chapter for a quant research document. All numbers you give
> must be labeled as documented (with a citable paper/URL) or as illustrative estimates.
> Never invent paper titles, URLs, or statistics.

---

## SB1 — Core microstructure + session momentum (S001, S003, S004, S006, S008, S014, S024, S025, S035, S040)

### Q-SB1-1 — formulas + worked example
```
For these three intraday signals — (1) Cont–Kukanov–Stoikov order-flow imbalance (OFI),
(2) best-level queue (depth) imbalance I=(Qb-Qa)/(Qb+Qa), (3) Stoikov microprice —
give the EXACT formula of each with all symbols defined, typical parameter/lookback ranges
used in practice (event-time vs time-bar aggregation windows), and then ONE concrete worked
numerical example: a 10-event synthetic quote tape (bid/ask prices and sizes), computing
per-event OFI contributions, the OFI sum, queue imbalance, and microprice at each step,
with every intermediate number shown. Label clearly which parameter choices are your
illustrative examples vs documented standards, and cite the source paper for each formula.
```

### Q-SB1-2 — local build + buy vs build
```
I have a Mac with Apple M5 Max and 128GB unified memory (sunk cost, already owned).
For computing OFI, queue imbalance, microprice, VPIN, and quoted/effective/realized spread
decomposition in REAL TIME on US equities: (1) what data feed do I need (exact product names,
e.g. Databento MBP-1 vs SIP), (2) what throughput should I assume in events/sec for a
Python+polars implementation vs Rust, (3) RAM footprint for 1 day of L1 quote events for one
liquid symbol and for 60 days, (4) engineering hours to build a correct event-driven pipeline
including timestamp normalization, (5) buy-vs-build: name vendors with INDICATIVE monthly
pricing (mark as indicative) for L1/L2 data and for precomputed microstructure analytics,
and give a build-vs-buy verdict for a one-person research operation.
```

### Q-SB1-3 — success ratios, after-cost efficacy, failure modes
```
What do published papers and practitioner accounts DOCUMENT (cite each) about the predictive
power of order-flow imbalance / queue imbalance / microprice for next-tick to next-minute
returns — R² or hit rates, and critically, what remains AFTER spread + fees + impact costs?
Distinguish the contemporaneous price-impact regression result (Cont–Kukanov–Stoikov) from
forward tradability. In which regimes does it fail (high-vol, wide spreads, retail-dominated
names, crowded)? Give an honest bottom line: as a standalone trigger vs as a filter/market-making
input, with any documented Sharpe or bps-per-trade numbers labeled before/after cost.
```

---

## SB2 — Cost/vol infrastructure + session patterns (S011, S013, S021, S027, S032, S042, S043, S063, S066, S083)

### Q-SB2-1 — formulas + worked example
```
For (1) Amihud illiquidity ratio, (2) Corwin–Schultz high-low spread estimator,
(3) Crabel opening-range breakout, (4) RSI-2 mean reversion, (5) HAR realized-volatility
forecast, give EXACT formulas with symbols defined and practical parameter ranges
(lookbacks, thresholds). Then ONE worked numerical example each on a small synthetic
dataset: 10 days of OHLCV for Amihud/Corwin–Schultz, a synthetic opening 30-minute
5-min bar series for the ORB trigger, 10 closes for RSI-2, and a 22-day realized-variance
series for a 1-day-ahead HAR forecast — show every intermediate number. Mark illustrative
parameter choices as examples, cite sources.
```

### Q-SB2-2 — local build + buy vs build
```
On a 128GB Apple M5 Max Mac (sunk cost): how do I build a daily+intraday pipeline for
Amihud, Corwin–Schultz, RSI-2/IBS, RVOL, range-based realized vol, HAR forecasts, and
multi-clock bars (tick/volume/dollar/imbalance bars) over a 500-stock US universe?
Give: (1) cheapest adequate data (daily OHLCV + 1-min bars — name vendors, indicative
$/mo), (2) expected compute time for the full universe daily refresh in polars, (3) RAM and
disk for 60 days of 1-min bars for 500 symbols, (4) engineering hours, (5) buy-vs-build
verdict vs vendors like Polygon/Tiingo/Alpaca for bars and vs precomputed analytics.
```

### Q-SB2-3 — success ratios, after-cost efficacy, failure modes
```
Documented evidence check with citations: (1) opening-range breakout profitability after
costs — what do Crabel's own results and later replication attempts show, and does it
survive modern spreads? (2) RSI-2/IBS Connors-style mean reversion — published hit rates
and the drawdown regimes; (3) HAR vs GARCH for intraday vol forecasting — documented
accuracy gains; (4) end-of-day momentum/last-hour drift — effect size and whether it is
tradable after the closing-auction spread. For each: before/after-cost labeling, markets
and periods studied, and when it breaks.
```

---

## SB3 — Pairs foundations + validation/ML layer + news (S049, S050, S056, S079, S081, S085, S086, S088, S091, S094)

### Q-SB3-1 — formulas + worked example
```
For (1) Gatev–Goetzmann–Rouwenhorst distance pairs, (2) Engle–Granger cointegration
z-score pairs, (3) HMM regime-switching (2-state Gaussian) for intraday regimes,
(4) triple-barrier labeling, (5) purged/embargoed cross-validation, give EXACT procedures
with formulas, symbols defined, and practical parameter ranges (formation/trading windows,
z-entry/exit thresholds, embargo lengths as % of sample). Then a worked numerical example:
20 synthetic daily closes for two cointegrated stocks — compute the spread, hedge ratio,
z-score, a triple-barrier label for one position, and show how purging+embargo changes a
train/test split on 60 labeled events. Cite the papers.
```

### Q-SB3-2 — local build + buy vs build
```
On a 128GB M5 Max Mac: what does it take to run a daily pairs pipeline (distance +
cointegration screening over ~2000 US stocks, ~10 years daily) plus an HMM regime filter
and a purged-CV + triple-barrier + meta-labeling ML validation stack? Give: (1) data needed
and cheapest adequate vendors with indicative pricing, (2) expected runtime for the
pairwise distance screen in polars/numpy (pairs ≈ 2M), (3) RAM for the price panel and for
an sklearn/XGBoost meta-labeler, (4) engineering hours by component, (5) buy-vs-build:
QuantConnect/Composer-style platforms vs self-build, and precomputed pairs analytics
vendors if any — with verdict.
```

### Q-SB3-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) Gatev et al. pairs — original 1999 excess returns, and what happened
after 2000s crowding/decay (Do–Faff and later replication numbers, after costs);
(2) cointegration z-score pairs intraday — documented Sharpe after costs;
(3) ETF-vs-basket/iNAV arbitrage — who captures it and what is left for a small operation
after fees and creation-unit minimums; (4) machine-readable news first-minute reaction —
documented drift magnitudes and half-lives; (5) meta-labeling/triple-barrier — what de Prado
documents it adds (if any) vs the primary model, with the caveat that it cannot create
alpha. After-cost honesty throughout, plus failure regimes.
```

---

## SB4 — Order-flow estimation toolkit (S002, S005, S007, S010, S012, S015, S017, S018, S020, S047)

### Q-SB4-1 — formulas + worked example
```
For (1) multi-level OFI / integrated OFI (Cont–Cucuringu–Zhang), (2) Lee–Ready trade
classification and Bulk Volume Classification (BVC), (3) Kyle's lambda estimation by
regression, (4) Roll implied spread from return autocovariance, (5) Hawkes self-exciting
intensity for order flow, give EXACT formulas with symbols defined and practical parameter
ranges (levels L, bar sizes for BVC, regression windows, Hawkes decay kernels). Then ONE
worked numerical example: a 12-trade synthetic tape with prices/sizes/quotes — classify
each trade by Lee–Ready AND by BVC on 3 volume bars, compute Roll's spread from the return
series, and estimate Kyle's lambda from a 10-observation regression by hand. Cite sources.
```

### Q-SB4-2 — local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for an L2 depth pipeline (multi-level OFI, book pressure,
Hawkes intensity) vs an L1/trade-only pipeline (BVC, Roll, Kyle's lambda, Huang–Stoll
decomposition) for 50 liquid US symbols in real time. Give: (1) required feeds with
indicative pricing (Databento MBP-10 vs MBP-1 vs SIP), (2) events/sec throughput assumptions
for Python+polars vs Rust per symbol for full-depth, (3) RAM/disk for 1 day and 60 days of
L2 depth for 50 symbols, (4) engineering hours for each pipeline, (5) buy-vs-build verdict,
including whether SIP data is honest enough for each signal (and where it is NOT — label
simulated-only).
```

### Q-SB4-3 — success ratios, after-cost efficacy, failure modes
```
Documented evidence with citations: (1) does multi-level OFI beat touch-only OFI
out-of-sample, and by how much (Xu–Gould–Howison numbers)? (2) Lee–Ready vs BVC
classification accuracy on modern data — documented rates and their limits;
(3) Kyle's lambda / Amihud as execution-cost predictors — how well do they forecast
realized slippage; (4) Hawkes order-flow models — documented forecasting edge for
micro-price moves and whether it survives fees; (5) retail/odd-lot flow — what the
 literature documents about its informativeness (or lack thereof). After-cost framing
and failure regimes for each.
```

---

## SB5 — Breakout & session-pattern family (S022, S023, S026, S028, S029, S030, S031, S033, S044, S045)

### Q-SB5-1 — formulas + worked example
```
For (1) Donchian breakout, (2) Keltner-channel breakout, (3) Bollinger bandwidth squeeze,
(4) first-hour range expansion / initial balance, (5) stretched-move z-score, give EXACT
formulas with symbols defined and practical parameter ranges (lookbacks N, ATR multiples,
bandwidth percentiles, z thresholds). Then ONE worked numerical example on a synthetic
intraday 5-minute bar series (30 bars: OHLCV): compute Donchian(20) levels, Keltner(20, 2×ATR),
bandwidth percentile, mark the initial-balance high/low, and compute the stretched-move
z-score at bar 30 — show every intermediate number. Mark illustrative parameters as
examples; cite sources.
```

### Q-SB5-2 — local build + buy vs build
```
On a 128GB M5 Max Mac: cost to build a full-session pattern engine over 500 US stocks —
Donchian/Keltner/Bollinger channels, squeeze detection, initial-balance levels,
auction-imbalance reads, consecutive-bar streaks, stretched-move z-scores — refreshed on
1-minute bars intraday. Give: (1) data feeds needed with indicative pricing (1-min bars,
auction imbalance feeds), (2) compute load: bars/sec in polars for 500 symbols and whether
real-time 1-min refresh is trivial, (3) RAM/disk for 60 days of 1-min bars, (4) engineering
hours, (5) buy-vs-build vs TradingView-style screeners or vendor pattern APIs — verdict
for a research operation that needs point-in-time correctness.
```

### Q-SB5-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) Donchian/ATR-channel breakouts intraday — documented after-cost results
and the trend-vs-chop regime dependence; (2) Bollinger squeeze → expansion — is there
documented edge or is it mostly a volatility-timing story; (3) gap-and-go vs gap-fade base
rates — what fraction of opening gaps continue vs reverse, after costs; (4) first-half-hour
→ last-half-hour momentum (Heston et al.) — effect size, markets, and tradability;
(5) open-auction imbalance continuation — documented predictive power and who can actually
trade it (latency/venue constraints). After-cost honesty and failure regimes throughout.
```

---

## SB6 — Mean-reversion + lead-lag family (S034, S036, S037, S038, S039, S041, S046, S048, S059, S060)

### Q-SB6-1 — formulas + worked example
```
For (1) overnight-gap fade and its jump-filtered variant (Lee–Mykland jump test),
(2) sub-hour microstructure reversal, (3) idiosyncratic/residual short-term reversal,
(4) LOB resiliency / temporary-impact reversion, (5) Hayashi–Yoshida lead-lag estimator,
give EXACT formulas with symbols defined and practical parameter ranges (gap thresholds,
jump-test significance, reversal lookbacks, resiliency half-life estimation, HY
synchronization). Then ONE worked numerical example: synthetic prior close + 10 one-minute
opening bars for a gap-fade calculation with a Lee–Mykland jump statistic computed by hand,
and a 12-observation two-asset tick series for the Hayashi–Yoshida covariance — show every
intermediate number. Cite sources; mark illustrative parameters as examples.
```

### Q-SB6-2 — local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for (a) an overnight-gap scanner over 3000 US stocks
(gap %, jump filter, prior-day RVOL), (b) a futures-spot and cross-asset lead-lag engine
(ES vs SPY, sector ETFs vs constituents) on 1-second/1-min bars, (c) a resiliency estimator
from L1 data. Give: (1) data needed with indicative pricing (daily + intraday bars, futures
data, L1 for resiliency), (2) compute: time for the 3000-stock gap scan in polars, HY
estimation throughput, (3) RAM/disk footprints, (4) engineering hours per component,
(5) buy-vs-build verdict — including whether lead-lag is honestly measurable on SIP
timestamps or needs exchange timestamps.
```

### Q-SB6-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) overnight-gap fade — documented returns and the finding that it can
go to zero/negative after realistic costs (state which studies); (2) jump-filtered gap
reversal — does filtering jumps actually improve after-cost results; (3) short-term
reversal (Jegadeesh/Lehmann) intraday — documented magnitude and the bid–ask bounce
contamination issue; (4) futures-spot and cross-asset lead-lag — documented lead times
and whether a non-colocated trader can capture them; (5) scheduled macro-announcement
drift — documented pre/post announcement returns and the latency needed. After-cost
honesty and failure regimes for each.
```

---

## SB7 — Pairs & cross-sectional extensions (S051, S052, S053, S054, S055, S057, S058, S061, S062, S090)

### Q-SB7-1 — formulas + worked example
```
For (1) Ornstein–Uhlenbeck half-life estimation from a spread, (2) Kalman-filter dynamic
hedge ratio (state-space setup), (3) copula pairs trading (marginal → copula → conditional
probability trigger), (4) variance-ratio / Hurst exponent regime test, give EXACT formulas
with symbols defined and practical parameter ranges (regression windows, Kalman Q/R,
copula family choices, VR horizons). Then ONE worked numerical example: a 20-observation
synthetic spread — estimate the OU half-life by regression showing every step; then a
10-observation price series — compute variance ratios for 2- and 4-period horizons and the
Hurst interpretation. Cite sources; mark illustrative parameters as examples.
```

### Q-SB7-2 — local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for (a) OU half-life + Kalman hedge-ratio estimation
refreshed daily over 500 candidate pairs, (b) a copula pairs backtester, (c) Johansen VECM
screening, (d) futures calendar-spread and cash-and-carry monitoring, (e) ADR premium
tracking with FX adjustment. Give: (1) data needed with indicative pricing (daily equity,
futures curves, FX, borrow data), (2) compute: VECM over candidate baskets, Kalman updates
in numpy/polars, (3) RAM/disk, (4) engineering hours per component, (5) buy-vs-build verdict
vs prime-broker pairs analytics or vendor stat-arb screens.
```

### Q-SB7-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) OU half-life timing — documented improvement over fixed-window
z-score exits; (2) Kalman dynamic hedge vs static OLS hedge — documented after-cost
difference; (3) copula pairs — documented results vs linear cointegration, and sensitivity
to copula misspecification; (4) index futures cash-and-carry and calendar spreads —
documented yields and who captures them (capital/borrow constraints for a small account);
(5) ADR/dual-listed premium convergence — documented half-lives and FX frictions;
(6) variance-ratio/Hurst as a regime toggle — documented value-add vs standalone use.
After-cost honesty and failure regimes throughout.
```

---

## SB8 — Volatility & options-informed (S064, S065, S067, S068, S069, S070, S071, S072, S073, S074)

### Q-SB8-1 — formulas + worked example
```
For (1) bipower variation (jump-robust realized variance), (2) intraday GARCH(1,1),
(3) variance risk premium (implied vs realized), (4) 25-delta risk reversal,
(5) gamma exposure (GEX) per strike, give EXACT formulas with symbols defined and
practical parameter ranges (sampling frequency, GARCH windows, IV interpolation,
delta-targeting). Then ONE worked numerical example: 12 synthetic 5-min returns —
compute realized variance AND bipower variation by hand showing every term; then a
5-strike synthetic options chain (OI, gamma, spot) — compute total GEX and the per-strike
contributions. Cite sources; mark illustrative parameters as examples.
```

### Q-SB8-2 — local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for (a) a realized-vol engine (range estimators,
bipower, HAR, GARCH) on 1-min bars for 500 symbols, (b) an options analytics pipeline:
IV surface from OPRA-style chains, straddle-implied moves, 25-delta risk reversals,
put/call ratios, unusual-activity scans, (c) a GEX/dealer-positioning estimator requiring
FULL-chain open interest. Give: (1) data needed with indicative pricing — especially
OPRA full-chain data cost tiers and cheaper alternatives (Cboe delayed), (2) compute and
RAM: full SPX chain snapshot size, Greeks for 3000 symbols, (3) engineering hours,
(4) buy-vs-build verdict per component — and state explicitly which pieces CANNOT be
honestly built without full-chain OI.
```

### Q-SB8-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) variance risk premium — documented returns, and the honest note that
the strongest evidence is at LONGER horizons than intraday; (2) straddle-implied move vs
realized — documented hit rates for event fades; (3) unusual options activity → stock
direction — documented predictive power and the open/close-flag data problem;
(4) GEX/pinning — documented effect sizes and the full-chain-OI requirement;
(5) put/call ratio contrarian — documented efficacy and sentiment-regime dependence.
After-cost honesty (options spreads are wide — say so with numbers) and failure regimes.
```

---

## SB9 — Stat/ML infrastructure + MM skew (S075, S076, S077, S078, S080, S082, S084, S087, S089, S016)

### Q-SB9-1 — formulas + worked example
```
For (1) Kalman-filtered local-level fair value, (2) PCA/eigenportfolio residual reversal,
(3) Hasbrouck (1991) trade–quote VAR, (4) fractional differentiation (fixed-width window),
(5) Avellaneda–Stoikov reservation price and optimal spread, give EXACT formulas with
symbols defined and practical parameter ranges (Kalman Q/R, PCA window/factors, VAR lags,
fracdiff d and window, A-S gamma/kappa). Then ONE worked numerical example: 10 synthetic
prices — run 3 Kalman update steps by hand showing prediction/update; then a 3-asset
10-day panel — compute the first PC residual for one asset. Cite sources; mark
illustrative parameters as examples.
```

### Q-SB9-2 — local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for (a) Kalman/HMM/ARMA signal library over 500 symbols
on 1-min bars, (b) a PCA/statistical-factor engine (500×252 panel, rolling), (c) a
DeepLOB-style LOB sequence model — training AND inference throughput on M5 Max GPU/CPU,
(d) fractional-differentiation preprocessing, (e) an Avellaneda–Stoikov quoting engine
(tick loop). Give: (1) data needs and indicative pricing, (2) training time estimates
for the deep model and inference latency per prediction on M5 Max, (3) RAM for panels and
LOB tensors, (4) engineering hours per component, (5) buy-vs-build verdict — including
whether the deep-learning components are worth it vs gradient-boosted trees on
handcrafted features (cite documented comparisons if you know any).
```

### Q-SB9-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) DeepLOB and successors — documented out-of-sample accuracy/AUC on
LOB mid-price prediction and the honest gap between prediction accuracy and tradable P&L
after costs; (2) PCA residual reversal — documented returns and crowding; (3) dispersion
trading — documented edge, capital intensity, and the 2008-style correlation-break
risk; (4) Avellaneda–Stoikov market making — documented performance and the inventory-risk
reality for a small account; (5) Hasbrouck information share — what it documents about
venue price discovery and its limits as a trading signal. After-cost honesty throughout.
```

---

## SB10 — Hard microstructure + alt-data (S009, S019, S092, S093, S095, S096, S097, S098, S099, S100)

### Q-SB10-1 — formulas + worked example
```
For (1) PIN (probability of informed trading, Easley–O'Hara) estimation, (2) crypto
funding-rate / basis cash-and-carry return, (3) Google Trends ASVI (abnormal search
volume intensity), (4) post-earnings-announcement drift intraday leg (SUE sorts),
give EXACT formulas/procedures with symbols defined and practical parameter ranges
(PIN estimation windows and MLE setup, funding-rate annualization, ASVI standardization
windows, SUE computation). Then ONE worked numerical example: a 10-day synthetic buy/sell
volume series — set up the PIN likelihood intuitively and approximate PIN; and a synthetic
funding-rate series — annualize it and compute the cash-and-carry P&L on a $10k position
over 24h with fees. Cite sources; mark illustrative parameters as examples.
```

### Q-SB10-2 — local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for (a) PIN estimation over 500 symbols (MLE compute
reality check), (b) a crypto pipeline: funding rates, open interest, liquidation feeds
for 20 perpetual contracts — data sources with indicative pricing (exchange APIs vs
aggregators), (c) a news/sentiment pipeline: machine-readable news with novelty scoring
— vendor options with indicative pricing (Benzinga, RavenPack academic, free tiers),
(d) ASVI/social sentiment from Google Trends + social APIs. Give: (1) data options with
indicative prices, (2) compute/RAM/storage per component, (3) engineering hours,
(4) buy-vs-build verdict per component — especially where licensing makes building
impossible (news redistribution) and where public crypto data is censored/lower-bound
(state this explicitly).
```

### Q-SB10-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) PIN — documented relation to spreads/returns and the honest
difficulty of estimating it in real time (Easley et al. critiques); (2) stealth trading
(Barclay–Warner) — documented informed-trade-size findings and modern relevance;
(3) crypto funding-rate reversal and liquidation cascades — documented returns and the
censored-data caveat; (4) ASVI (Da–Engelberg–Gao) — documented return predictability,
horizon, and decay since publication; (5) social sentiment — documented signal value vs
noise and manipulation risk; (6) PEAD intraday leg — documented magnitude and the
latency required to trade earnings drift. After-cost honesty and failure regimes.
```

---

---

# Strategy batches (Stages 101–200)

## TB1 — Flagship strategies (T001–T010)

### Q-TB1-1 — mechanics + worked example
```
For these three intraday strategies — (A) OFI + queue-imbalance directional scalping,
(B) RVOL-filtered opening-range breakout, (C) cointegration z-score pairs with OU
half-life exits — spell out COMPLETE mechanics: universe, session window, exact entry
trigger with example thresholds, exit rules (time stop / signal flip / stop-loss),
position sizing formula, and causal execution timing (signal at t → fill at t+1).
Then ONE worked numerical example per strategy on synthetic data: entry/exit prices,
share counts, spread+fee assumptions, and line-by-line gross/net P&L. Mark every
threshold as an illustrative example; cite the underlying papers.
```

### Q-TB1-2 — infra + local build + buy vs build
```
On a 128GB M5 Max Mac: what must run intraday to operate strategies A–C above
(feeds, compute loops, schedules)? Give throughput/RAM/storage estimates, engineering
hours to build each, and the buy-vs-build verdict with indicative pricing: retail
platforms (QuantConnect/Composer-style), professional data feeds, and precomputed
analytics — for a one-person paper-trading operation. Include a feed-outage safe-mode
plan for each strategy.
```

### Q-TB1-3 — success ratios, after-cost efficacy, failure modes
```
With citations: documented after-cost performance of (A) microstructure scalping on
OFI/queue signals for a non-colocated trader, (B) opening-range breakouts after costs
in modern markets, (C) equity pairs trading after the 2000s crowding (Do–Faff onward).
For each: reported Sharpe/hit-rate/bps-per-trade with market and period, capacity notes,
documented decay, and the specific regimes where it fails. Honest bottom line for a
small (≤$1M) paper operation.
```

---

## TB2 — Core reversal & momentum infrastructure (T011–T020)

### Q-TB2-1 — mechanics + worked example
```
For (A) short-term reversal timed at the bid–ask bounce, (B) jump-filtered overnight-gap
fade, (C) RSI-2/IBS extreme fade, (D) triple-barrier + meta-labeling overlay as a
position-sizing layer — give COMPLETE mechanics: entry/exit/sizing/risk-limits/cost
model with example thresholds, and ONE worked numerical example each on synthetic data
with line-by-line net P&L after spread+fees. For (D), show how the meta-label changes
position size on 5 synthetic primary-signal instances. Cite sources; mark thresholds
as examples.
```

### Q-TB2-2 — infra + local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for the data+compute behind TB2 strategies — daily
reversal screens over 3000 stocks, overnight-gap scanner with jump filter, RSI-2/IBS
intraday engine, and a triple-barrier/meta-labeling ML stack. Throughput, RAM, storage,
engineering hours per piece, cheapest adequate data with indicative pricing, and the
buy-vs-build verdict. Note specifically where bid–ask bounce contaminates reversal
backtests and how to build the defense (quote-midpoint accounting).
```

### Q-TB2-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) short-term reversal after costs — Jegadeesh/Lehmann magnitudes and
how much the bid–ask bounce explains; (2) overnight-gap fade after costs — studies
showing it going to zero/negative; (3) RSI-2/IBS Connors systems — documented drawdowns
and regime failures; (4) end-of-day drift and first-half-hour→last-half-hour momentum —
effect sizes and closability; (5) meta-labeling — honest assessment of what it adds.
After-cost honesty, capacity, decay, failure regimes.
```

---

## TB3 — Microstructure market-making & toxicity (T021–T030)

### Q-TB3-1 — mechanics + worked example
```
For (A) Avellaneda–Stoikov inventory-skew market making, (B) queue-imbalance posting with
toxicity cancel, (C) Hawkes-burst scalping — give COMPLETE mechanics: quoting/skew
formulas with example parameters (gamma, kappa), inventory limits, cancel/replace logic,
adverse-selection measurement, and fee/rebate modeling. Then ONE worked numerical example
each on a synthetic quote/trade tape: 10 quote updates — compute the A-S reservation price
and quotes at each step for (A); show the cancel trigger firing for (B); show burst
detection and signed entry/exit for (C) — with per-trade net P&L after fees/rebates.
Cite sources; mark parameters as examples.
```

### Q-TB3-2 — infra + local build + buy vs build
```
On a 128GB M5 Max Mac: what does it take to run market-making-style strategies honestly?
Cover: (1) minimum viable data (L1 vs MBO — what you LOSE without MBO, labeled
simulated-only), (2) tick-loop latency reality on a Mac (no colocation — quantify the
honest disadvantage in ms), (3) throughput/RAM for a 20-symbol quoting engine in Rust vs
Python, (4) engineering hours, (5) buy-vs-build: colocated/prop alternatives with
indicative costs vs local paper simulation — verdict for learning vs real deployment.
```

### Q-TB3-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) Avellaneda–Stoikov — documented performance and the inventory-risk
drawdowns; (2) queue-imbalance market making — documented fill-rate/adverse-selection
trade-offs (Gould–Bonart and follow-ups); (3) toxicity-gated quoting (VPIN/PIN) — does
gating measurably reduce adverse selection, with numbers; (4) the honest economics of
retail market making WITHOUT rebates/colocation — what the literature implies for a
remote Mac-based operation. Failure regimes: latency arbitrage against you, toxic flow,
inventory blowups.
```

---

## TB4 — Pairs & cross-sectional extensions (T031–T040)

### Q-TB4-1 — mechanics + worked example
```
For (A) distance pairs with zero-crossing quality filter, (B) Kalman dynamic-hedge pairs
with imbalance-bar entry timing, (C) index futures cash-and-carry, (D) PCA eigenportfolio
residual reversal — give COMPLETE mechanics: pair formation, entry/exit z-thresholds
(examples), hedge-ratio computation, execution (borrow, dividends, corporate actions),
sizing and portfolio heat limits, cost model. Then ONE worked numerical example each on
synthetic data: 20-day spread path for (A)/(B) with trades marked and net P&L; a
cash-and-carry arithmetic example with borrow fee for (C); a 3-asset residual example
for (D). Cite sources; mark thresholds as examples.
```

### Q-TB4-2 — infra + local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for a production pairs operation — nightly pair
screening (distance + cointegration + copula) over 2000 stocks, daily Kalman hedge
updates, borrow/dividend/corporate-action adjustment pipeline, futures basis monitoring.
Data needs with indicative pricing (daily equity, borrow data — note borrow data cost!),
compute time for screens, RAM, engineering hours, and buy-vs-build verdict vs
prime-broker analytics or vendor stat-arb screens.
```

### Q-TB4-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) Gatev et al. pairs — original vs post-2000 decay numbers after costs;
(2) dynamic-hedge (Kalman) vs static pairs — documented improvement; (3) copula pairs —
documented edge over linear methods and model-risk caveats; (4) cash-and-carry —
documented yields, capital and borrow constraints for small accounts; (5) ETF/basket arb —
who captures it and the creation-unit minimum problem; (6) sector momentum + residual
reversal — documented results. After-cost honesty, capacity, crowding, failure regimes
(pair divergence blowups, correlation breaks).
```

---

## TB5 — Volatility & options-informed (T041–T050)

### Q-TB5-1 — mechanics + worked example
```
For (A) variance-risk-premium harvester (short delta-hedged straddle when IV rich vs HAR),
(B) GEX pin / dealer-positioning fade, (C) unusual-options-activity follower — give
COMPLETE mechanics: signal computation, entry/exit with example thresholds, delta-hedging
frequency and cost for (A), options-chain data handling, sizing (vega/vol targeting),
risk limits (event blackout, vol-spike stop). Then ONE worked numerical example each on
synthetic data: P&L walk for a 5-day short-straddle with daily delta hedging for (A);
a gamma-wall map and fade trade for (B); a sweep-follow equity entry for (C) — all with
spread+fee accounting. Cite sources; mark thresholds as examples.
```

### Q-TB5-2 — infra + local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for an options-informed intraday operation — full-chain
OI snapshots, IV surface + Greeks for 500 underlyings, GEX computation, UOA scan,
straddle-implied moves. (1) Data: OPRA full-chain indicative pricing tiers vs cheaper
alternatives (Cboe delayed) — and which strategies DIE without full-chain OI;
(2) compute: Greeks for a full chain in polars/numpy, snapshot storage/day;
(3) RAM/disk; (4) engineering hours; (5) buy-vs-build verdict — options analytics vendors
with indicative pricing vs self-build.
```

### Q-TB5-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) short variance-risk-premium — documented Sharpe/returns, the
longer-horizon evidence caveat, and short-vol blowup regimes (2018, 2020) with drawdown
numbers; (2) GEX/pinning — documented effect sizes; (3) unusual options activity →
equity direction — documented predictive power and data-quality caveats; (4) dispersion
trading — documented edge and correlation-break risk; (5) options-spread reality check —
typical effective spreads that must be in every cost model. After-cost honesty throughout.
```

---

## TB6 — Statistical / ML & regime (T051–T060)

### Q-TB6-1 — mechanics + worked example
```
For (A) HMM regime-switching allocator (momentum book vs reversal book), (B) DeepLOB +
feature-stack classifier as a trade trigger, (C) news-sentiment first-minute momentum —
give COMPLETE mechanics: model specification, training/validation with purged-CV and
embargo (for B), regime inference and allocation weights (for A), entry/exit/sizing with
example thresholds, latency budget for (B)/(C). Then ONE worked numerical example each:
5 synthetic regime posteriors driving allocation shifts for (A); a confusion-matrix →
position-sizing walk for (B) with 20 synthetic predictions; a news-event timeline trade
for (C) with slippage. Cite sources; mark thresholds as examples.
```

### Q-TB6-2 — infra + local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for (a) HMM/Kalman/ARMA regime library over 500
symbols, (b) training a DeepLOB-style model — honest training-time estimate on M5 Max
GPU, inference latency per prediction, and whether gradient-boosted trees on handcrafted
features are the sane default (cite documented comparisons), (c) a news-sentiment
reaction pipeline with novelty scoring. Data with indicative pricing (news licensing —
note redistribution limits), compute/RAM/storage, engineering hours, buy-vs-build verdict
per piece.
```

### Q-TB6-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) HMM regime-switching for intraday allocation — documented value-add
vs static blends; (2) DeepLOB-class models — documented prediction accuracy vs the
honest gap to after-cost tradable P&L; (3) handcrafted-feature GBM vs deep learning on
LOB data — documented comparisons; (4) news-sentiment strategies — documented half-lives
and the speed required; (5) the overfitting reality: what purged-CV + embargo actually
protects against and famous failures without it. After-cost honesty and failure regimes
(model decay, regime misclassification, news-feed latency).
```

---

## TB7 — Session patterns & auction (T061–T070)

### Q-TB7-1 — mechanics + worked example
```
For (A) initial-balance expansion trader, (B) VWAP-cross institutional follower with
RVOL confirmation, (C) MOC auction-pin trader — give COMPLETE mechanics: session
definitions (RTH, DST/half-day handling), level computation, entry/exit with example
thresholds, sizing, auction-order types (MOC/LOC) and cutoff times for (C), cost model
including auction spread. Then ONE worked numerical example each on synthetic intraday
bars: mark initial-balance levels and the expansion trade for (A); VWAP crosses with
entries/exits for (B); an imbalance-to-close timeline for (C) — with net P&L. Cite
sources; mark thresholds as examples.
```

### Q-TB7-2 — infra + local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for a session-pattern engine — 1-min bars for 500
symbols, VWAP/anchored-VWAP, initial-balance levels, auction-imbalance feeds (note: real
NYSE/Nasdaq imbalance feeds vs SIP approximations with indicative pricing), MOC order
support in the paper broker. Compute/RAM/storage, engineering hours, cheapest adequate
data with indicative pricing, buy-vs-build verdict.
```

### Q-TB7-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) initial-balance / first-hour breakout strategies — documented
after-cost results; (2) VWAP-cross continuation — is there documented edge or is it
mostly execution folklore; (3) closing-auction dynamics — documented dislocations and
who captures them (DMM/imbalance-prop vs outsiders); (4) end-of-day reversal vs drift —
which dominates and when; (5) auction-feed latency — why SIP approximations mislead.
After-cost honesty and failure regimes (trend days vs range days, half-days, FOMC days).
```

---

## TB8 — Alternative-data & attention (T071–T080)

### Q-TB8-1 — mechanics + worked example
```
For (A) news-novelty reversal, (B) crypto funding-rate reversal + liquidation-cascade
fade, (C) earnings-drift intraday leg on SUE — give COMPLETE mechanics: novelty scoring
procedure, funding-rate z-score construction and annualization, SUE computation and
sorting, entry/exit with example thresholds, sizing, session/exchange coverage (24/7
crypto vs RTH equities), cost model (funding payments for shorts in B). Then ONE worked
numerical example each on synthetic data with line-by-line net P&L. Cite sources; mark
thresholds as examples.
```

### Q-TB8-2 — infra + local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for (a) news ingestion + novelty scoring — vendor
options with indicative pricing and redistribution-license limits, (b) crypto pipeline:
funding/OI/liquidation for 20 perpetuals — exchange websocket vs aggregator, with the
explicit caveat that public liquidation data is censored/lower-bound, (c) ASVI/social
pipelines. Compute/RAM/storage, engineering hours, buy-vs-build verdict per piece, and
which pieces are impossible to build without a license.
```

### Q-TB8-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) news novelty vs staleness — documented reversal/drift magnitudes;
(2) crypto funding-rate contrarian — documented returns and the crowded-leverage regime
risk; (3) liquidation cascades — documented bounce magnitudes and data-censoring
honesty; (4) ASVI — Da–Engelberg–Gao documented predictability, horizon, and decay
since publication; (5) PEAD intraday leg — documented magnitude and required latency;
(6) social sentiment — signal vs manipulation/noise. After-cost honesty and failure
regimes throughout.
```

---

## TB9 — Infrastructure & execution (T081–T090)

### Q-TB9-1 — mechanics + worked example
```
For (A) adaptive bar-clock sampler (tick/volume/dollar/imbalance bar selection by
regime), (B) purged-CV strategy selector allocating across sub-strategies,
(C) OFI-paced participation (VWAP) execution algo — give COMPLETE mechanics:
decision rules with example thresholds, allocation/weighting formulas, participation
schedule construction, and how each plugs into a paper-trading broker. Then ONE worked
numerical example each: bar-type selection on 3 synthetic regimes for (A); allocation
weights from 5 synthetic purged-CV scores for (B); a 10-slice execution schedule with
OFI pacing adjustments and slippage accounting for (C). Cite sources; mark thresholds
as examples.
```

### Q-TB9-2 — infra + local build + buy vs build
```
On a 128GB M5 Max Mac: build cost for execution/infrastructure tooling — multi-clock
bar engine, venue-routing logic (with the honest SIP-vs-direct latency caveat),
participation/VWAP algos in the paper broker, purged-CV model-selection harness.
Throughput/RAM/storage, engineering hours, data needs with indicative pricing, and
buy-vs-build verdict vs EMS/Algo-wheel vendor products (indicative pricing) — with the
explicit statement that local paper simulation cannot validate latency-sensitive
routing (label simulated-only).
```

### Q-TB9-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) bar-clock choice — documented impact on strategy performance
(Easley–López de Prado–O'Hara volume-clock results); (2) purged-CV vs naive CV —
documented overfitting reduction; (3) execution algorithms — documented implementation
shortfall vs arrival price for VWAP/participation styles; (4) venue routing by
information share — documented price-discovery facts and why a remote trader mostly
cannot monetize them; (5) ensemble/meta-labeling overlays — honest value-add bounds.
Failure regimes: feed outages, stale kill-switches, regime misdetection.
```

---

## TB10 — Advanced hybrids & capstone (T091–T100)

### Q-TB10-1 — mechanics + worked example
```
For (A) multi-level book-pressure swing trader, (B) options-to-equity lead trader
(skew + signed flow → equity entries), (C) the grand 100-signal ensemble (T100) —
give COMPLETE mechanics: signal computation and combination logic (weights/voting/
stacking with example parameters), entry/exit/sizing/risk with example thresholds,
training protocol (purged-CV + embargo + triple-barrier labels) for (C), and the
honest statement of what the ensemble can and cannot add over its components. Then ONE
worked numerical example each on synthetic data: a 10-level book-pressure path with
trades for (A); a skew-shift → equity entry timeline for (B); a 5-signal stacking walk
with meta-label sizing for (C) — with net P&L. Cite sources; mark thresholds as examples.
```

### Q-TB10-2 — infra + local build + buy vs build
```
On a 128GB M5 Max Mac: full-stack build cost for running T091–T100 together — L2 depth
for book pressure, full-chain options for skew/flow, the ensemble training harness
(purged-CV, stacking, meta-labels) and intraday inference for all 100 signals. Give:
(1) total data bill with indicative pricing by feed, (2) peak RAM/disk (60-day lookback),
(3) training vs inference compute on M5 Max, (4) engineering hours by subsystem and
total, (5) buy-vs-build verdict for the whole stack — and the explicit crossover where
a small operation should NOT build (licensed data, colocation).
```

### Q-TB10-3 — success ratios, after-cost efficacy, failure modes
```
With citations: (1) multi-level book pressure vs touch-only — documented incremental
edge; (2) options-flow → equity lead — documented lead times and who captures them;
(3) large signal ensembles — documented evidence on whether stacking 100 weak signals
beats the best 5 (the diversification vs overfitting trade-off, with examples of
ensemble failures); (4) the meta-lesson: documented cases of complexity adding nothing
after costs. End with an honest bottom line for a one-person Mac-based paper operation:
which 5 of these 100 strategies deserve to be built first and why, with after-cost
reasoning.
```

---

## Question-source log template (paste into each batch folder)

```
Batch: SB1 | Date: YYYY-MM-DD | Bots used: Grok(web) / DeepSeek / Kimi
Q1 answered by: ___ | Q2 answered by: ___ | Q3 answered by: ___
Verifiable citations captured: ___
Unverified claims quarantined: ___
Notes: ___
```
