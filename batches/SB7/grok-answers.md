# SB7 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials
- Date: 2026-09-10
- Chat: https://grok.com/c/dd3d38ba-c34a-44fc-b28c-b7cc96301288
- Batch: SB7 — Pairs-trading machinery (S043, S044, S045, S047, S049, S050, S051, S052, S053, S054): OU half-life, Kalman dynamic hedge, copula pairs, variance-ratio/Hurst regime test, calendar spreads, cash-and-carry, ADR premium
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim via page text extraction.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: text extraction strips KaTeX math notation (formulas appear as plain-text fragments) and the DOM duplicates some phrases; each doubled phrase appears once below (the browser task confirmed the true Grok text has each phrase once). All numbers, citations, and worked steps are preserved as captured.

---

## Q-SB7-1 — formulas + worked example (verbatim)

Exact formulas first, then one fully worked numerical example. All windows, Q/R, copula families, and VR horizons below are illustrative practitioner ranges, not estimated optima.

(1) Ornstein–Uhlenbeck half-life from a spread

SDE (Elliott, Van Der Hoek & Malcolm 2005; standard OU):
- X_t = spread (price residual, log-price residual, or beta-hedged residual).
- mu = long-run mean.
- theta = speed of mean reversion (per unit time).
- sigma = diffusion volatility.
- W_t = Wiener process.

Continuous-time half-life (expected time to close half the gap to mu): H = ln(2)/theta. Stationary variance: sigma^2/(2*theta).

Discrete AR(1) / OLS estimator (equally spaced delta; most common in pairs work). Regress Delta X_t on X_{t-1}, or equivalently X_t in levels (in units of Delta). The continuous approximation coincides with the discrete when theta is defined as -ln(phi)/delta. Residual scale: sigma_eps of the regression; map to OU by sigma = sigma_eps*sqrt(2*theta/(1-exp(-2*theta*delta))). Need phi < 1 for stationary mean reversion.

Practical ranges (examples): Estimation window: 60–252 daily bars for equity pairs; 20–60 bars only as a diagnostic (high variance). Rolling re-estimation every 5–21 days is common.

Tradable half-life rules of thumb on daily bars: H < 5 = often microstructure; H 5–30 = the usual "tradeable" band; H 30–100 = slow/capital-heavy; H > 100 = unreliable or barely reverting.

Prefer Engle–Granger / Johansen cointegration first; estimate OU on the residual, not raw prices.

Sources: Uhlenbeck & Ornstein (1930); Elliott et al. (2005); Leung & Li, Optimal Mean Reversion Trading; Lo / standard AR(1) mapping used throughout pairs literature.

(2) Kalman-filter dynamic hedge ratio (state-space)

Observation (one asset on the other plus intercept): y_t = alpha_t + beta_t * x_t + eps_t, eps_t ~ N(0, R).

State (random-walk intercept and hedge ratio — the usual pairs specification): s_t = [alpha_t, beta_t]'; s_t = s_{t-1} + eta_t, eta_t ~ N(0, Q).

Observation matrix at t: H_t = [1, x_t]. Predict: s_{t|t-1} = s_{t-1|t-1}, P_{t|t-1} = P_{t-1|t-1} + Q. Update: innovation v_t = y_t - H_t s_{t|t-1} (innovation = spread); K_t = P_{t|t-1} H_t' / (H_t P_{t|t-1} H_t' + R); s_{t|t} = s_{t|t-1} + K_t v_t; P_{t|t} = (I - K_t H_t) P_{t|t-1}.

Trading spread / z-score uses s_t = y_t - alpha_{t|t} - beta_{t|t} x_t (or a rolling SD of the innovation).

Chan / Robot Wealth parameterization (example) for slowly evolving equity-pair (KO–PEP, country ETFs): Q = delta/(1-delta) * I (delta ~ 1e-3 to 1e-4), R depending on price scale (or set to residual variance from a burn-in OLS). Only the ratio Q/R is identified in practice. Larger Q/R → faster tracking, noisier hedge. Initialize beta from OLS on first 30–60 points; P0 = I or a large diagonal.

Sources: Kalman (1960); Chan, Algorithmic Trading (2013) ch. on Kalman pairs; QuantStart / Robot Wealth implementations.

(3) Copula pairs trading

Pipeline:
1. Marginals. From returns (or standardized residuals) estimate F_hat (empirical CDF / kernel / parametric). PIT: u_i = F_hat(r_i).
2. Fit C (IFM or canonical ML on PITs). Common families: Gaussian / Student-t (symmetric; t has tail dependence). Clayton (lower-tail / crash dependence). Gumbel (upper-tail). Frank (symmetric, no tail dependence). Choose by AIC/BIC or Vuong; often mapped from Kendall's tau.

3. Conditional-probability trigger (Liew & Wu 2013; Botha 2013): mispricing index MI_{1|2} = P(U1 <= u1 | U2 = u2) = dC/du2; MI_{2|1} = dC/du1. Closed forms (examples): Gaussian MI via conditional normal CDF; Clayton MI_{2|1} = u2^{-theta-1} (u1^{-theta}+u2^{-theta}-1)^{-1-1/theta}.

Signal (illustrative thresholds 0.05 / 0.95): Long spread (long 1 / short 2) if MI_{1|2} < 0.05 and MI_{2|1} > 0.95; Short spread if the inequalities reverse. Exit when both MIs cross back through 0.5 (or a tighter band 0.4 / 0.6).

Practical ranges (examples): Fit window: 252–756 daily returns; refit monthly. Families: start with Student-t + Clayton + Gumbel and pick by AIC; Clayton if crash co-movement is the trade. Triggers: 0.05/0.95 aggressive; 0.10/0.90 more robust. Never treat MI as a physical probability under a misspecified copula.

Sources: Sklar (1959); Liew & Wu (2013), J. Derivatives & Hedge Funds; Hudson & Thames copula pairs notes.

(4) Variance-ratio / Hurst regime test

Let r_t (or log-return). Lo–MacKinlay (1988) variance ratio at horizon k: VR(k) = Var(r_t(k)) / (k * Var(r_t)), where r_t(k) is the k-period return. Overlapping, drift-adjusted estimator (standard textbook form).

Under a homoskedastic random walk, VR(k) = 1. (Use the heteroskedastic version in Lo–MacKinlay 1988 if variance is clustered.)

Interpretation: VR = 1: RW at that horizon. VR < 1: negative serial correlation / mean reversion. VR > 1: persistence / trend.

Link to Hurst. For a process with exponent H: VR(k) ~ k^{2H-1}; ln VR(k) / ln k = 2H - 1, so H = 0.5 + ln(VR)/(2 ln k). H < 0.5: anti-persistent / mean-reverting (pairs-friendly). H > 0.5: persistent (do not fade). R/S Hurst is a different estimator; do not mix the two numbers without saying so.

Practical horizons (examples): Daily equity: 16, 32. Weekly: 4, 8. Require n >> k at minimum; Lo–MacKinlay theory wants much more. Joint Chow–Denning test if you scan several k.

Sources: Lo & MacKinlay (1988, 1989); Campbell, Lo & MacKinlay, Econometrics of Financial Markets, ch. 2.

### Worked numerical example — all figures synthetic and illustrative

A. 20-observation spread — OU half-life by regression

Spread (20 obs): 1.20 0.95 0.88 0.50 0.62 0.30 0.45 0.10 0.22 0.05 0.15 -0.20 0.35 -0.18 0.40 -0.08 [-0.30 ...] (extraction dropped some minus signs; sufficient statistics below are exact and recover the values).

Regression pairs: lag x = X_{t-1}, response y = Delta X_t = X_t - X_{t-1}, n = 19.

Sufficient statistics: sum(x) = 3.87, sum(y) = -1.28, sum(x^2) = 4.5455, sum(xy) = -1.2165, sum(y^2) = 0.9994.

OLS normal equations (n=19) give: a_hat = -0.015554, b_hat = -0.254385. (Check via levels: phi_hat = 1 + b_hat = 0.745615.)

Long-run mean mu_hat = -a_hat/b_hat = 0.06114 (see QC note 1 — sign error in Grok; the numbers give -0.06114).

theta_hat = -ln(0.745615)/1 = 0.293545. H = ln(2)/0.293545 = 2.361 bars.

Residual RMSE ~0.199 (per-bar); implied OU sigma ~0.27.

Reading: a 2.4-bar half-life on this toy sample is fast (see the 5–30 bar daily rule of thumb above). On real daily pairs you would not trust 20 obs; this is only to show the algebra.

B. 10-observation price series — VR(2), VR(4), Hurst

Prices: 100.0 101.0 101.4 102.1 101.8 102.6 103.0 102.7 103.5 104.0.

One-period increments (9): 1.0 0.4 0.7 -0.3 0.8 0.4 -0.3 0.8 0.5; mean 0.4444; sum of squared deviations 1.7422; population variance 0.19358 (population form used here so every step is a raw second moment; the LM drift- and overlap-correction change the level slightly on n=10).

Horizon 2: Overlapping 2-period increments (8): 1.4 1.1 0.4 0.5 1.2 0.1 0.5 1.3. VR(2) = 0.545. H(2) = 0.5 + ln(0.545)/(2 ln 2) = 0.062.

Horizon 4: Overlapping 4-period increments (6): 2.1 1.6 1.6 0.9 1.4 1.3. VR(4) = 0.206. H(4) = 0.5 + ln(0.206)/(2 ln 4) = -0.071.

Interpretation (illustrative, n=10 is far too short for inference). Both variance ratios are < 1 and both implied H values are < 0.5: the path is anti-persistent / mean-reverting at these horizons, i.e. the regime a pairs book wants. Negative H is a finite-sample artifact (VR cannot be trusted once k is a large fraction of n); in production you would report VR and the Lo–MacKinlay z and refuse to quote H from n=10.

Implementation notes that bite in production: OU half-life and VR/H answer different questions (parametric speed vs nonparametric serial-correlation horizon). Kalman does not replace a cointegration test. Copula MIs are copula-specific — a Clayton 0.05 is not a Gaussian 0.05. Freeze the copula family, windows, and triggers as a choice, and freeze them before looking at PnL.

---

## Q-SB7-2 — local build + buy vs build (verbatim)

On a 128 GB M5 Max this stack is compute-cheap and data-expensive. The machine (18 CPU cores: 6 performance + 12 efficiency, 40-core GPU, 614 GB/s unified memory on the 40-core SKU) will idle through daily-bar OU / Kalman / Johansen / copula work. What you pay for is clean history, futures curves, borrow, and FX — not FLOPs.

All dollar figures below are indicative 2026 list / street ranges, not quotes. Professional vs non-pro status and redistribution rights move futures and SIP prices by 5–10x.

### 1. Data needed and indicative pricing

- Daily US equity + ETFs, survivorship-free, PIT index members: Norgate Platinum/Diamond; Sharadar via Nasdaq Data Link; Massive (ex-Polygon) EOD + delistings. Indie/research tier: $360–$800/yr Norgate; Massive stocks starter ~$29/mo (delayed); Tiingo Power ~$30/mo / commercial ~$50/mo. Desk/professional tier: CRSP/Compustat via WRDS or Bloomberg: quote, typically $15k–$50k+/yr.
- Intraday (only if you later go intra-day pairs): Massive Advanced SIP; Databento usage. ~$199/mo SIP; Databento $50–$300/mo light use. Direct SIP / B-PIPE: tens of k$/yr.
- Futures settlements + curve (calendar + cash-and-carry): CME DataMine EOD settlements / continuous series; IBKR delayed or NP L1. DataMine continuous history on the order of $320–$800/mo or ~$19k complete-history SKU for all-asset continuous; IBKR NP L1 ~$10–15/exchange/mo. Pro L1 ~$100–135/exchange/mo; all four CME Group venues ~$400–540/mo display. Direct MDP: thousands/mo.
- FX for ADR and carry: Tiingo / Oanda / ECB + USD crosses; official WM/Refinitiv 16:00 London fix if you mark books. $0–$50/mo. WM/Refinitiv fix + LSEG: seat / enterprise.
- Securities borrow / HTB / locate — the silent killer. Public "short interest biweekly" is not a locate feed. FINRA biweekly SI: free but stale. DataLend / IHS Markit / S3 / prime-broker locate API: $10k–$50k+/yr typical; often bundled with a PB relationship.
- ADR listing map + home-market close: Local close (LSE/TSE/HKEX) + US close + FX. Dual-listed EOD from Norgate/EODHD/Massive +$0–$300/yr extra venues. Bloomberg ADR function / LSEG: seat.
- Corporate actions, dividends, specials: required for cash-and-carry and ADR premium. Bundled in Norgate/Sharadar. Compustat / Bloomberg at desk tier.

Working research budget (solo, daily bars, no live SIP, no institutional borrow): ~$1.0k–$2.5k/year (Norgate Platinum $630 + Tiingo/Massive + IBKR NP futures L1 on 2–4 venues + FX).

Working desk budget (pro futures, official settlements, usable borrow): ~$15k–$60k/yr data alone, dominated by borrow + CME pro + a terminal or LSEG feed.

Do not use Yahoo/adjusted-close-only for (a)–(c). You need delistings, split/div point-in-time, and a frozen as-of universe or every cointegration screen is in-sample fiction.

### 2. Compute on this Mac (numpy / polars / statsmodels)

Assumptions: 500 pre-filtered candidates (not C(3000,2)), 5y daily, ~1,260 bars, refresh after US close.

- (a) OU half-life + Kalman beta: Per pair: one OLS on ~1,260 pts + Kalman 2-state update O(T). Milliseconds per pair. 500 pairs << 1 s if you vectorize the AR(1) in polars/numpy and loop Kalman in Numba or a thin Python loop. Daily refresh is a cron, not a cluster.
- (b) Copula backtester: PIT + one copula MLE per pair-window + path of dC/du. Fit is the cost (Clayton/Gumbel/t MLE). 500 pairs x rolling 1y windows x 4 families: seconds to a few minutes if you use scipy/statsmodels/copulas and process-pool over the 18 cores. Full 10y walk-forward with daily refits: minutes, not hours.
- (c) Johansen VECM screen: Bivariate Johansen is a handful of eigenproblems on T x 2. Baskets of k=3–5 are still tiny. Combinatorial explosion is the only risk. 500 named pairs: sub-second to a few seconds (statsmodels.tsa.vector_ar.vecm). If you ever do all pairs in a 400-name sector: C(400,2) = 79,800 Johansen runs — still tens of seconds to ~2 min on this CPU if you batch. Do not brute-force C(n,5). Pre-cluster by industry/PCA.
- (d) Calendar + cash-and-carry: Join curve (10–20 listed expiries) to cash, repo/borrow, dividends, FX. I/O and contract-spec logic, not linear algebra. Sub-second per product once the curve table is in memory.
- (e) ADR premium + FX: P_US − P_home × FX × ratio + overlay of borrow and tax. Trivial numerically. Hard part is corporate-action alignment and close timestamps (London 16:30 vs NY 16:00).

Stack that fits the machine: Parquet on disk → Polars lazy scan → NumPy/SciPy for the filters → statsmodels Johansen/VECM → hand-rolled 2-state Kalman (or filterpy / a 20-line predict/update) → one copula library. Skip PyTorch/GPU for this; daily-bar linear algebra does not use the 40-core GPU. Keep GPU for later agent/LLM work.

What will not fit a laptop workflow: tick-level copulas, full-universe minute bars, or live MDP options surfaces. That is Databento + a Linux box, not this Mac.

### 3. RAM and disk

- Unified RAM on this box 128 GB. Daily-bar research will use 2–8 GB resident. You could run the whole book in 16 GB; 128 GB is headroom for local LLMs sitting next to the research kernel, not a requirement for (a)–(e).
- 5y daily US listed+delisted OHLCV + actions (~20k ids): ~2–8 GB Parquet compressed. 20y same: ~10–25 GB.
- CME EOD settlements, all products, 15y, all expiries: ~5–20 GB depending on how many option strikes you keep. Futures-only curves are small.
- Intraday 1-min US + a few futures: 100 GB–1 TB+ — this is when the 2–8 TB SSD option starts to matter.
- Feature store (spreads, beta_t, z, MI, VR, H) for 500 pairs x 5y: <1 GB.
- Working recommendation: 2 TB SSD is enough for daily-bar + curves + 2–3 research clones. Keep a Time Machine / off-box Parquet replica; the research product is the feature store + code, not the raw dump.
- Peak RAM during an 80k-pair Johansen sweep with naive pandas copies can spike; stay in Polars + float32 + chunked pair lists and you will not notice 128 GB.

### 4. Engineering hours (one competent quant-engineer, not a platform team)

Hours are calendar-ish "done well enough to trade research, with tests," not a SaaS product.

- (a) OU HL + Kalman beta, 500 pairs, daily: 12–20 h first vertical slice (data join, OLS, Kalman, parquet out, a notebook); 40–70 h production-shaped (rolling refit, missing bars, corporate actions on the residual, z from s_t, pair-level config, unit tests vs a known KO–PEP path).
- (b) Copula backtester: 20–35 h slice (PIT → one family → MI trigger → simple PnL); 80–140 h production-shaped (4 families + AIC pick, walk-forward, costs/borrow, no-lookahead CDF, report pack). Copula numerical edge cases eat time.
- (c) Johansen / VECM screen: 10–18 h slice; 35–60 h production-shaped (rank, lag select, stability of beta across windows, basket constraints, multiple-testing / sector clusters).
- (d) Futures calendar + cash-and-carry monitor: 25–40 h slice (one product family, e.g. CL or ES, roll calendar, spread sheet); 80–150 h production-shaped (multi-product specs, settlement vs last, cheapest-to-deliver if bonds, dividend/repo, holiday clocks). Specs and rolls dwarf the math.
- (e) ADR premium + FX: 12–20 h for a static ratio table + FX; 40–80 h production-shaped (ratio changes, tax/withholding, home-market holidays, stale FX, borrow on both legs).
- Shared plumbing (universe, CA, costs, scheduler, dashboards): 60–120 h once, amortized.
- Total to a usable research system: ~300–550 h (roughly 8–14 focused weeks). Add 30–50% if you insist on a live IBKR execution loop with locate checks rather than a research monitor.

### 5. Buy vs build

- Build (a)+(c) on Norgate + this Mac: You own the residual definition, windows, and research log. Matches how you already think about OU/Kalman/Johansen. Data ~$1–2k/yr + ~2–4 weeks of your time. **Verdict: Build.** This is the core edge-definition layer. Vendors will not let you change the exact OU regression or Kalman Q/R.
- Build (b) copula backtester: Pedagogy + one custom trigger. Live edge vs a well-specified distance/coint book is modest after costs. +3–6 weeks. **Verdict: Build a thin version** (Clayton + t + Gaussian, one trigger). Do not turn it into a copula research firm.
- Build (d) curve / carry monitor: Needs official settlements and contract specs. Easy to get rolls wrong. Data jumps; +4–8 weeks. **Verdict: Hybrid.** Pull settlements from IBKR/CME DataMine; implement the monitor yourself for the 5–15 products you care about. Do not rebuild a curve warehouse.
- Build (e) ADR premium: A spreadsheet with FX and ratios gets you 80%. The last 20% is CA and tax. 1–3 weeks for a watchlist of 20–40 ADRs. **Verdict: Build the watchlist.** Buy a terminal function only if this becomes a book.
- PairTrade Finder / similar retail pairs GUI: Pre-screened equity pairs, IBKR hook, 10y backtest, radar. Software license typically low thousands/yr ($1k–$5k class). **Verdict: Buy only as a second screen, never as the residual definition.** You cannot audit their cointegration window.
- QuantConnect / QuantRocket: Universe + lean engine + some pairs alphas; you still write the model. QC research free-ish; live/data extras. QR + Sharadar a few hundred to a few thousand/yr. **Verdict: Useful execution/research host, not a substitute** for (a)–(c) on local parquet you can diff.
- Prime-broker "pairs / stat-arb analytics": Pre-coint screens, factor-residual books, locate, portfolio margin. Bundled in a PB relationship; the real price is balances + commissions, not a SKU. **Verdict: Use the locate and risk, ignore their pair list as gospel.** Their screen is a starting universe, not your theta and H.
- Bloomberg / LSEG stat-arb + FA + ADR: Best ADR/FX/borrow adjacent data. ~$2k–$2.5k/mo/seat class. **Verdict: Buy a seat if (d)+(e) become production P&L.** Do not buy a seat to run Johansen on 500 names.

Recommended split:
- Build on the Mac: (a), (c), a small (b), local feature store, daily cron after 16:15 ET.
- Rent data, not software: Norgate (or Sharadar) + IBKR NP/pro futures + a cheap FX series.
- Buy the thing you cannot rebuild: borrow/locates (PB or DataLend) the moment you short real size; official CME settlements if carry P&L is real.
- Do not buy: a vendor "pairs analytics" box as the research system. You already specified exact OU / Kalman / copula / VR estimators; a black box cannot implement your Q = delta/(1-delta) I, your discrete half-life, or your Clayton MI threshold.

Year-1 cash picture (research, not a fund): Hardware already owned. Data $1k–$3k. Your time 300–550 h. Optional PairTrade Finder or QC as a sanity check $1k–$4k.
Year-1 cash picture (if (d)+(e) go live with locates): Add $15k–$60k data/borrow/terminal and another 150–250 h of specs and ops. The Mac still does not need an upgrade.

---

## Q-SB7-3 — success ratios, after-cost efficacy, failure modes (verbatim)

After-cost honesty first: classical distance pairs (Gatev–Goetzmann–Rouwenhorst) decayed from ~11% gross to roughly flat-to-negative after time-varying costs (Rad, Low & Faff 2016, covering 1962–2014): distance 91 bp/month pre-cost → 38 bp after costs; cointegration 85 bp → 33 bp; copula 43 bp → 5 bp. A 2026 walk-forward on EWA–EWC style pairs with 28 bp all-in per trade printed negative net Sharpe on all seven strategy branches, including the Kalman branch. A 7-exchange 2005–2024 z-score book printed negative CAGR on every exchange. These are not tricks of bad data: they are what happens when you hold the residual definition fixed and let costs move.

(1) OU half-life timing vs fixed-window z-score exits

What is documented. Modeling the spread as OU and using H = ln 2 / theta (theta the mean-reversion speed) does two different jobs: (i) selection — keep only pairs whose half-life sits in a tradable band; (ii) timing — set holding-time stops and, in Bertram (2010) / Leung–Li, optimal barriers as functions of theta, not fixed sigma. Avellaneda and Lee (2010) is the paper most often cited for "putting mean-reversion speed into the trade," and practitioners converge on <3 trading days on daily bars; H < 3 is treated as microstructure, H 60–100 as capital trapped in a drifting residual.

A Rice ETF-neighborhood study (formation 12m / trade 6m) keeps only H 5–25 days for the same reason: sub-3-day half-lives are invisible on daily bars after costs; long half-lives burn capital.

Documented failure of fixed windows when half-life is ignored. A 60-day z-score on TLT/IEF (half-life estimated ~473 days) produced Sharpe 0.25, CAGR 0.88%, 84 round-trips, after 5 bp/side — the window was measuring noise around a migrating level. That is precisely what a fixed window cannot see and a half-life gate would have blocked.

A 7-exchange 2005–2024 z-score book (40-day window, 2σ out, 60-day time stop, ~10 bp round-trip on four legs, half-life gate 5–60 days) still printed negative CAGR on every exchange (−0.9% US to −2.7% UK) despite 80–89% "convergence." Convergence to mu is a weak event; average trade was negative after costs.

One 2023–24 single-study comparison even had a naive rolling-z book beat an OU-calibrated book (Sharpe 0.78 vs 0.47) — OU is not a free lunch; misspecified theta plus a bad percentile rule underperforms a dumb z.

Failure regimes. Structural break in the cointegrating vector (the residual is no longer OU). Half-life estimated on 5–30 bars (you scratch every winner). Time-stop much longer than H while the mean has walked. Costs that are a large fraction of sigma_eq.

After-cost verdict. Half-life as a filter and a holding-time budget is the part with the cleanest evidence. Half-life as a replacement for a z-exit is theory-rich (Bertram) but empirically thinner: the documented wins are selection and time-stops, not magical exits.

(2) Kalman dynamic hedge vs static / rolling OLS

What is documented on the description side. Palomar's pairs chapter (EWA–EWC style examples) shows rolling 2y OLS beta whipping between ~0.6 and 1.2 while a random-walk-state Kalman stays in a tight band; the Kalman residual is smoother and reversion-timed. Palomar's gross cumulative wealth in that illustration goes ~0.6 (rolling OLS) vs ~2.0 (basic Kalman) vs ~3.2 (Kalman + HMM); and Palomar's own text calls the HMM-boosted equity "surprisingly good," i.e. an illustration, not an out-of-sample claim.

What is documented after costs. Two recent walk-forwards go the other way.
- Baskaran (SSRN 2026), seven strategy branches, 28 bp all-in/trade, ~2.3-day average Kalman hold: all branches negative net Sharpe. Static OLS fold-mean Sharpe 0.16 vs Kalman −2.08; OLS wins 12 of 14 folds. Kalman turnover +54% (932 vs 607 trades). Kalman does cut fold-mean max DD by ~71% (0.31 vs 1.07). Implied breakeven vs OLS is ~6–7 bp one-way. An HMM gate on top of Kalman cut trades 45% and DD another 30%, Sharpe still negative at 28 bp.
- A documented bank-pair case (static beta = 1.055 IS): Kalman net Sharpe +1.12 vs 0.53; OOS net +0.76 vs 1.50; 41 vs 78 trades. Better description, worse trade.

Practitioner reviews of the same literature: in-sample Kalman Sharpe +0.1 to +0.3 vs static OLS; OOS ≈ flat; the adaptive filter that looks "responsive" doubles/triples turnover and gives the edge back to the prime broker.

Failure regimes. Q calibrated on a quiet sample, then a 2020-style factor shock — Kalman chases the break and you re-hedge every bar instead of when |Delta beta| exceeds a dead-band. Using innovation variance R as if it were economic edge when R was set so small the spread has no amplitude left after 2–4 bp/leg.

After-cost verdict. Treat Kalman as a drawdown / tracking tool with a re-hedge dead-band and DMA-like costs, not as a Sharpe upgrade. If your all-in round-trip is 15–30 bp, static or slow-rolling beta wins on net.

(3) Copula pairs vs linear cointegration, and misspecification

Headline large-sample result — Rad, Low and Faff (2016), Quantitative Finance, US equities 1962–2014, time-varying costs: Distance 91 bp → 38 bp; Cointegration 85 bp → 33 bp; Copula 43 bp → 5 bp (monthly excess, pre-cost → after cost). Copula kept firing after 2009 when distance/coint opportunity counts collapsed, and lost less on unconverged trades / drawdowns. It was not the PnL winner. Cointegration was the turbulent-market winner in that sample.

Liew and Wu (2013) — small universe, short sample — reported the opposite: more trades, higher returns on copula (both pre- and after-cost, in their sample).

Misspecification is first-order. Clayton on a pair whose pain is upper-tail (squeeze), Gumbel on a crash-codependent pair, Gaussian with prices (non-stationary PITs) all produce a different MI path. Hudson & Thames' own note: change family among four and the trigger fires on different days; change the input from returns to raw prices and the model rots as one leg trends. Rad et al. explicitly used families chosen by goodness-of-fit.

Failure regimes. Non-convergent pairs (the Rad drag). Copula refit that uses the same window as the signal (lookahead).

After-cost verdict. Copula is a tail-aware overlay and a bear-market stabilizer, not a replacement for a cointegration residual. On a full CRSP-like universe after realistic costs it trails the linear methods on raw PnL.

(4) Index futures cash-and-carry and calendar spreads

Theory. Cost-of-carry: F = S e^{(r − q) T} (continuous). A calendar spread is the same identity between two maturities. Actionable mispricing is a no-arbitrage band, not a point: commissions, bid–ask on the basket or ETF, borrow/stock-loan on the cash leg, tracking error, and the dividend forecast error all sit inside the band.

What is documented. Index-futures mispricing persists in raw form, more in emerging contracts (Nifty, IBOVESPA) than in ES; volume, OI, volatility and day-of-week patterns are documented. Mispricing clusters in the last ~10 sessions of the roll, i.e. exactly when everyone else is rolling. Commodity "roll yield" (BCOM TR minus spot) can be large over years — that is curve shape harvested by already-long commodity indexers, not a cash-and-carry residual you uniquely own.

Index futures are cheap to trade relative to the cash basket (Fleming et al.: futures costs on the order of 0.1x the stock-basket leg), so arbitrage funds and market-makers own this trade. Closing-auction vs futures close mismatches can even show up in fund NAVs — the industrial version of the same basis.

Who captures it, and why a small account does not.
- You need: stock-loan / box, the ability to short the expensive leg of a 500-name basket or a tight ETF, and portfolio margin.
- A small account pays: retail futures commissions + exchange fees, ETF spread, hard-to-borrow on single names, and FX drag — single-digit basis points of notional, episodically more around dividends, rolls, and auctions.
- Calendar spreads on the same venue look more accessible (one margin system, no cash borrow). What you are actually trading is roll congestion and curve-convexity, which is a different, also crowded, book (CTA rolls, commodity index rolls). Capacity is real; uniqueness is not.

Failure regimes. Dividend forecast error through an ex-date. ETF creation/redemption halt. Persistent backwardation/contango that you misread as a mispricing. Being the liquidity.

After-cost verdict. For a laptop book this is a monitor, not a yield. Institutions clip the band; you clip the bid–ask.

(5) ADR / dual-listed premium convergence

Documented premia. Gagnon and Karolyi: across hundreds of ADR–ordinary pairs, discounts up to ~87% and premia up to ~66%.

Documented half-lives. On liquid names, ESTAR/SETAR work on Mexican ADRs: deviations die fast — 14 of 21 pairs, half-life < 2 days; mean 3.1 days, median 1.1 days. Four illiquid names sat at >= 7 days. Issuance/cancel of ADRs is often T+0 to overnight, so the economic arbitrage horizon is hours-to-a-couple-of-sessions when convertibility is open.

Alsayed and McGroarty (high-frequency stock–ADR pairs, UK names): small, frequent opportunities net of stated trading costs, with asymmetric payoffs — shorting the ADR / long the ordinary was the better side in their sample (less chance of limit-up traps).

FX and convertibility frictions. The tradable residual is P_US − P_home × FX × ratio plus ADR fees, FX spread, stamp/tax, and the convertibility option. When capital controls bind, the premium becomes a dollar-exit option (crisis literature: Venezuelan-style ADR premia embed devaluation probabilities). That premium can hang around for months or years and never "converge" in your horizon.

Failure regimes. Ratio change / corporate action missed. Home holiday vs NY session. FX quoted at last mid while the underlying has moved. On liquid, fully convertible Level II/III ADRs the edge is intraday-to-2-day, eaten by FX+ADR fees unless you are in the arb seats. On controlled or illiquid names the "premium" is often a dollar-exit option premium, not a trade.

(6) Variance-ratio / Hurst as a regime toggle

What is documented as a filter, not a standalone alpha.
- Formation-window R/S Hurst on the spread, keep H < 0.20–0.50: in one ETF-neighborhood pipeline this dropped ~19% of ADF-cointegrated pairs as either too trending or too noisy, and the surviving book beat the unscreened one.
- Ramos-Requena et al. (Hurst vs distance/correlation): Hurst selection cut drawdown and beat distance for >= 10 pairs; with very few pairs it did not.
- Nasdaq-100 study (generalized Hurst vs corr vs coint): Hurst did not beat the index, was not better than correlation, better than cointegration in that design; results moved with pair-count and rebalance. That is the honest shape of the evidence.
- Crypto pairs: anti-persistent H associated with faster subsequent mean reversion (hours, in that market) across several co-movement metrics; profitable in-sample/out-of-sample in crypto 2024 papers — treat as market-specific, high-cost, high-overfit risk.
- Trend literature (DFA Hurst as a regime gate): high-H regimes favor long-short trend; low-H regimes favor doing less. That is the dual of the pairs use. Using one number for both books is the honest version.

VR at horizons 8–16 on the spread (not the legs) is the statistically cleaner toggle: VR with a heteroskedastic Lo–MacKinlay z is a test, H is a summary. They disagree on short samples; n = 20–60 examples are toys.

Failure regimes. H estimated on prices instead of the residual. H estimated inside the trading window (selection bias). H = 0.2 (noise) treated as "strong mean reversion." Using H as a trade signal rather than a veto. Changing estimator (R/S vs DFA vs GHE vs VR-implied H) flips the regime on the same pair.

After-cost verdict. Documented value-add is as a gate: do not fade a spread with H > 0.5 at your holding horizon; do not run a trend overlay when H < 0.45. Standalone Hurst books on equities have not shown a robust after-cost edge over a competent cointegration book, and requiring VR/H agreement is the least self-deluding version.

Cross-cutting after-cost rules:
1. Gross-to-net is the strategy. Rad et al.: copula 43 bp → 5 bp. Baskaran: Kalman gross tracking advantage → negative Sharpe at 28 bp.
2. Turnover is a hidden parameter. OU z, copula 5/95 MI, and short OU half-lives all print tickets. Dead-bands, 2x half-life time stops, and DMA-like costs are the after-cost toolkit.
3. The failure that looks like alpha: a break in beta, convertibility, or curve regime that your model still calls "mean-reversion."
4. Small-account constraint is binding on (4) and (5), optional on (1)–(3),(6). Equity pairs after 5–15 bp/leg are a research problem. ES cash-and-carry and liquid ADR convert-arb are institutional books.

If you implement only one thing from the literature that repeatedly survives this filter: estimate half-life on a cointegrated residual, refuse to trade outside a 5–60 day band, size holding time ≈ H, and use VR/H only to veto. That is a smaller claim than any of the six headlines, and it is the one the papers actually support.

---

## QC notes (orchestrator)

1. Q-SB7-1 arithmetic inconsistency (preserved above): Grok prints "Long-run mean mu_hat = 0.06114" but with a_hat = -0.015554 and b_hat = -0.254385, mu_hat = -a_hat/b_hat = -0.06114 — the printed value has the wrong sign. The parenthetical "(slightly negative of the raw average; sampling noise)" is garbled since the raw spread average is positive. Everything else in the worked example checks out: OLS stats, phi_hat = 0.745615, theta_hat = 0.293545, H = 2.361 bars, VR(2) = 0.545 → H(2) = 0.062, VR(4) = 0.206 → H(4) = -0.071.
2. Extraction artifacts (not Grok errors): KaTeX math renders as plain-text fragments; several phrases repeat 2–3x because the DOM contains duplicate render layers (collapsed to one above); a few minus signs in the raw data lists were dropped by extraction, but the sufficient statistics are exact and recover the intended values.
3. Key sourced claims are research leads, not verified facts: Rad–Low–Faff 2016 (distance 91→38 bp, cointegration 85→33 bp, copula 43→5 bp); Baskaran (SSRN 2026) Kalman negative net Sharpe at 28 bp all-in; Bertram 2010 / Leung–Li optimal barriers; Avellaneda–Lee 2010; Gagnon–Karolyi ADR discounts to ~87% / premia to ~66%; Mexican ADR ESTAR/SETAR half-lives <2 days for 14 of 21 pairs; Alsayed–McGroarty UK ADR HF; Fleming et al. futures costs ~0.1x stock-basket leg. Verify independently before chapter adoption.
4. Vendor prices: indicative — verify before budgeting.

---

## Source list (only papers actually used)

- Uhlenbeck, G.E. and Ornstein, L.S. (1930), "On the Theory of the Brownian Motion," Physical Review.
- Elliott, R.J., Van Der Hoek, J. and Malcolm, W.P. (2005), "Pairs trading," Quantitative Finance.
- Leung, T. and Li, X., Optimal Mean Reversion Trading (World Scientific).
- Kalman, R.E. (1960), "A New Approach to Linear Filtering and Prediction Problems," J. Basic Engineering.
- Chan, E., Algorithmic Trading (Wiley, 2013) — Kalman pairs chapter.
- Sklar, A. (1959), "Fonctions de répartition à n dimensions et leurs marges."
- Liew, R.Q. and Wu, Y. (2013), "Pairs trading: A copula approach," J. Derivatives & Hedge Funds.
- Lo, A.W. and MacKinlay, A.C. (1988), "Stock Market Prices Do Not Follow Random Walks."
- Lo, A.W. and MacKinlay, A.C. (1989).
- Campbell, J.Y., Lo, A.W. and MacKinlay, A.C., The Econometrics of Financial Markets (Princeton).
- Bertram, W.K. (2010), "Analytic Solutions for Optimal Statistical Arbitrage Trading."
- Avellaneda, M. and Lee, J.-H. (2010), "Statistical arbitrage in the US equities market."
- Rad, H., Low, R.K.Y. and Faff, R. (2016), "The profitability of pairs trading strategies: distance, cointegration and copula methods," Quantitative Finance.
- Gagnon, L. and Karolyi, G.A. — ADR premium/discount cross-section.
- Everything not attributed to one of the above — parameter windows, thresholds, cost figures, worked-example values — is illustrative.
