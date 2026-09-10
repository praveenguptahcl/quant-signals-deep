# SB3 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials
- Date: 2026-09-10
- Batch: SB3 — Pairs foundations + validation/ML layer + news (S049, S050, S056, S079, S081, S085, S086, S088, S091, S094)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.

---

## Q-SB3-1 — formulas + worked example (verbatim)

This chapter is written so every statistic is tagged as either **documented** (paper + venue) or **illustrative** (constructed for the numerical example). No paper titles, URLs, or empirical numbers are invented.

---

## 1. Gatev–Goetzmann–Rouwenhorst (GGR) distance pairs

**Source (documented).** Gatev, E., Goetzmann, W. N., and Rouwenhorst, K. G. (2006), "Pairs Trading: Performance of a Relative-Value Arbitrage Rule," *Review of Financial Studies* 19(3), 797–827. Earlier version: NBER Working Paper 7032 (1999). They use CRSP daily data 1962–2002 and report average annualized excess returns of up to about 11% on self-financing portfolios of top pairs (documented in the abstract of the 2006 RFS paper).

### Procedure

Let P_{i,t} be the **cumulative total-return index** of stock i (dividends reinvested). GGR work in *normalized price space*, not raw prices.

**Formation window** of length T_F trading days (documented baseline: **12 months**).

1. Normalize each series to 1 at the first day of formation:
   P̃_{i,t} = P_{i,t} / P_{i,t_0}, t ∈ [t_0, t_0+T_F].
2. For every unordered pair (i,j), compute the **sum of squared deviations** (SSD / Euclidean squared distance):
   D_{ij} = Σ_{t=t_0}^{t_0+T_F} (P̃_{i,t} − P̃_{j,t})².
3. Rank pairs by D_{ij} ascending. Trade the top N pairs (documented: **top 20**).

**Trading window** of length T_T (documented baseline: **6 months** immediately after formation). Re-normalize both legs to 1 at the *first day of the trading window*. Define the trading-period spread
S_t = P̃_{i,t}^{trade} − P̃_{j,t}^{trade}.
Let σ_F be the sample standard deviation of the *formation-period* normalized-price difference (same pair, same normalization convention as formation).

**Rule (documented):**
- **Open** a dollar-neutral position when |S_t| > 2σ_F.
- If S_t > 2σ_F: short i, long j (equal dollars).
- If S_t < −2σ_F: long i, short j.
- **Close** when S_t crosses 0 (convergence), at delisting, or at the end of the 6-month trading window — whichever comes first.
- No stop-loss in the original paper; positions that never converge simply expire at T_T.

Two portfolio constructions are documented: *committed capital* (equal weight on all selected pairs whether open or not) and *fully invested* (equal weight only on currently open pairs).

### Practical parameter ranges (mix of documented + industry practice)

| Parameter | Documented GGR | Common practice (illustrative ranges used in later replications) |
| --------- | -------------- | ---------------------------------------------------------------- |
| Formation | 12 months | 6–12 months |
| Trading | 6 months | 3–6 months |
| Entry | 2σ_F | 1.5–2.5σ |
| Exit | convergence / end of window | same, or a small band ±0.5σ |
| Universe | liquid CRSP names | sector-restricted, min price / min ADV filters |

Do and Faff (2010) and later replications keep the 12/6 calendar and the 2σ rule; they are not restated here as new statistics.

---

## 2. Engle–Granger cointegration + z-score pairs

**Sources (documented).**
- Engle, R. F. and Granger, C. W. J. (1987), "Co-Integration and Error Correction: Representation, Estimation, and Testing," *Econometrica* 55(2), 251–276. Two-step residual-based test.
- Trading overlay (z-score thresholds, rolling windows) is **not** in Engle–Granger 1987; it is subsequent practitioner convention. Thresholds below are labeled **illustrative** unless a specific later paper is cited.

### Procedure

Let x_t, y_t be (usually log) prices, assumed I(1).

**Step 1 — cointegrating regression (OLS).** y_t = α + βx_t + u_t. β is the **hedge ratio**: 1 unit of y is hedged with β units of x. Spread s_t = y_t − α − βx_t is the residual (some implementations drop α and use s_t = y_t − βx_t).

**Step 2 — residual stationarity.** Run ADF (or the Engle–Granger critical values, which are stricter than the Dickey–Fuller critical values because β is estimated) on u_t. Reject a unit root ⇒ treat the pair as cointegrated over that window. A common operational gate is a p-value cutoff of 0.05 on a rolling window of 252 trading days — that cutoff is **illustrative convention**, not a number from Engle–Granger 1987.

**Step 3 — z-score of the spread.** Over a lookback L: z_t = (s_t − s̄_L)/σ_L. Some implementations freeze β on the **formation** sample (closer in spirit to GGR) rather than rolling.

**Trading rule (illustrative practitioner defaults):**
- Enter short-spread if z_t > z_in (typically z_in = 2), long β of x, short 1 of y.
- Enter long-spread if z_t < −z_in.
- Exit when |z_t| < z_out (often z_out = 0), or on a time stop, or on a stop at |z_t| = 4.

### Practical ranges (illustrative unless noted)

| Item | Typical range |
| ---- | ------------- |
| Formation / coint test window | 6–24 months; 12 months common |
| Rolling z lookback | 20–60 days (intraday: 30–120 bars) |
| z_in | 1.5–2.5 |
| z_out | 0–0.5 |
| Stop | 3–4 σ |
| Max hold | 10–60 days (or half-life of OU fit on s_t) |

Johansen's system estimator is an alternative to Engle–Granger when more than two legs are traded or when you want to test the cointegration rank.

---

## 3. Two-state Gaussian HMM for (intra)day regimes

**Source (documented).** Hamilton, J. D. (1989), "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle," *Econometrica* 57(2), 357–384. Discrete-state Markov-switching model with Gaussian (or Gaussian-like) emissions; EM estimation. Applying it to equity bars is a later use of the same model class, not Hamilton's original GNP application.

### Model

Hidden state s_t ∈ {1,2} is a first-order Markov chain with transition matrix A_{ij} = P(s_{t+1} = j | s_t = i) and initial distribution π. Emissions (almost always **log-returns**, not prices): r_t | s_t = k ~ N(μ_k, σ_k²).

For a multivariate bar (return, realized vol, spread change) use a diagonal or full covariance Σ_k.

**Estimation:** Baum–Welch (EM). **Decoding:** Viterbi path or filtered posteriors γ_t(k) = P(s_t = k | r_{1:t}).

Use in a pairs book (illustrative design, not in Hamilton 1989):
- Fit on a rolling window of returns of the **spread** or of a market factor.
- Trade the GGR / EG pair **only in the low-vol state** (the state with smaller σ_k), or scale size by P(calm).
- Refit periodically (e.g. weekly) or use an expanding window with a floor on T_min so states do not flip every bar.

Practical ranges (illustrative):
- States: 2 (calm / turbulent). 3+ is common but identification gets messy on short samples.
- Window: 500–2000 bars for 2-state univariate; more if multivariate.
- Persistence: fitted A_ii on daily equity returns is often > 0.95 (documented qualitative fact across many Hamilton-style papers; specific matrices vary by sample).
- Intraday: fit on 1-min or 5-min log-returns of the spread or of the index; do **not** fit on raw prices.

---

## 4. Triple-barrier labeling

**Source (documented).** López de Prado, M. (2018), *Advances in Financial Machine Learning*, Wiley, Chapter 3.

For an event at time t_0 with price P_0 and a volatility estimate σ̂ (e.g. EWMA or rolling std of returns):
- Upper (profit-take): P_0(1 + k_PT·σ̂)
- Lower (stop): P_0(1 − k_SL·σ̂)
- Vertical (max hold): timestamp t_0 + T

Path P_t is scanned. Label: +1 if upper touched first, −1 if lower touched first, 0 if vertical touched first (or both horizontal missed).

For **sided** labels (you know the side from your primary model — you already chose long or short), the two horizontal barriers can be asymmetric and the label is {0, 1} ("bet failed / bet succeeded") — meta-labeling, same chapter.

Practical ranges (illustrative; AFML does not mandate a single tuple):
- Barrier width: 1–3 × daily σ̂; tighter on higher-frequency bars.
- T: 1–10 days for daily pairs; or a multiple of the estimated OU half-life of the spread.
- σ̂: 20–50 day EWMA of returns, or a volume-clock realized-vol.

The label's **span** [t_0, t_1] where t_1 is the first-touch time. That span is what purging uses.

---

## 5. Purged and embargoed cross-validation

**Source (documented).** López de Prado (2018), *Advances in Financial Machine Learning*, Chapter 7 (Purged K-Fold / combinatorial purged CV).

Standard K-fold assumes i.i.d. rows. A triple-barrier label at t_0 uses information up to t_1. If a training event's [t_0, t_1] overlaps a test event's [t_0, t_1], the train set has seen the test outcome.

**Purge.** Drop from the **train** set every event i whose information interval overlaps any test event j's interval [t_{0,j}, t_{1,j}].

**Embargo.** Features are serially correlated, so even a **non-overlapping** train event immediately **after** a test fold can leak. After the last test timestamp, drop an additional embargo of length m observations (or an equivalent calendar gap), where m = ηT, T is sample length and η is a fraction.

**Documented / common η.** AFML discusses embargo as a **percentage of the sample**; implementations frequently use 1%–5%, or a multiple of the label horizon h. Treat any specific percent you ship as a **choice you disclose**, not a universal constant.

**Combinatorial purged CV (CPCV):** partition into K groups, take every combination of k groups as test, purge+embargo the rest, and recombine into multiple backtest **paths** φ. That yields a **distribution** of OOS statistics instead of one walk-forward number.

---

## 6. Worked numerical example (all figures illustrative)

### 6.1 Twenty synthetic daily closes

Two cointegrated names, X (cheap-beta leg) and Y. Constructed as X_t = 50 + 0.15t + u_t, Y_t = 5 + 1.20X_t + v_t, with a small stationary v_t so the EG residual is mean-reverting. Prices below are **synthetic**, not market data.

| t | X | Y |
|---|-------|-------|
| 1 | 50.10 | 65.05 |
| 2 | 50.28 | 65.41 |
| 3 | 50.41 | 65.38 |
| 4 | 50.55 | 65.82 |
| 5 | 50.72 | 65.71 |
| 6 | 50.90 | 66.21 |
| 7 | 51.05 | 66.08 |
| 8 | 51.22 | 66.55 |
| 9 | 51.38 | 66.42 |
| 10 | 51.50 | 66.95 |
| 11 | 51.68 | 66.80 |
| 12 | 51.81 | 67.28 |
| 13 | 51.95 | 67.12 |
| 14 | 52.12 | 67.62 |
| 15 | 52.25 | 67.48 |
| 16 | 52.40 | 67.95 |
| 17 | 52.58 | 67.81 |
| 18 | 52.70 | 68.30 |
| 19 | 52.88 | 68.15 |
| 20 | 53.00 | 68.62 |

### 6.2 Engle–Granger hedge ratio, spread, z-score

OLS of Y on X with intercept over t = 1..20 (illustrative closed-form / any standard OLS): β̂ = 1.198, α̂ = 5.07 (rounded; a no-intercept fit would give β̂ ≈ 1.20, slightly different). Spread s_t = Y_t − 5.07 − 1.198X_t.

Illustrative spreads and a **full-sample** σ_s = 0.22, z_t = s_t / 0.22:

| t | s_t | z_t |
|---|--------|--------|
| 1 | −0.04 | −0.18 |
| 2 | +0.08 | +0.36 |
| 3 | −0.11 | −0.50 |
| 4 | +0.19 | +0.86 |
| 5 | −0.12 | −0.55 |
| 6 | +0.18 | +0.82 |
| 7 | −0.12 | −0.55 |
| 8 | +0.16 | +0.73 |
| 9 | −0.15 | −0.68 |
| 10 | +0.20 | +0.91 |
| 11 | −0.14 | −0.64 |
| 12 | +0.17 | +0.77 |
| 13 | −0.16 | −0.73 |
| 14 | +0.12 | +0.55 |
| 15 | −0.20 | −0.91 |
| 16 | +0.11 | +0.50 |
| 17 | −0.22 | −1.00 |
| 18 | +0.13 | +0.59 |
| 19 | −0.21 | −0.95 |
| 20 | +0.09 | +0.41 |

On this short sample |z_t| never reaches a 2σ entry. That is expected: 20 points and a tightly constructed residual will not print a GGR/EG trigger. For the example we **force** an entry at t = 10 as a didactic position (illustrative), when Y is locally rich (s_10 = +0.20). A live system would wait for |z_t| ≥ 2 on a longer window.

GGR distance on the same 20 days (illustrative). Normalize both series to 1 at t = 1 (50.10 / 65.05). SSD is small relative to a random pair — the construction made them travel together — but with only one pair there is no cross-sectional rank to report.

### 6.3 One triple-barrier label

Position opened at t = 10: **short the spread** (short 1 Y, long β = 1.198 X), because s_10 is positive. Define the **spread-level** process as the traded instrument. Use:
- Barrier half-width: 0.20
- σ̂ = full-sample σ_s = 0.22 (live systems use a trailing vol)
- Barriers on the spread (short position: profit is **down**):
- Profit-take (for a short): 0.20 − 0.18 = 0.02
- Stop: 0.20 + 0.22 = 0.42
- Vertical: t = 10 + 5 = 15

Path of s_t after entry: s_11 = −0.14, so the profit-take at 0.02 is crossed between t = 10 and t = 11. First barrier touched = profit-take ⇒ label 1 (the short worked).

Label span: [10, 11].

(If we had used a long-of-spread convention with symmetric dollar barriers on price, the arithmetic changes; the first-touch logic does not.)

### 6.4 Purging + embargo on 60 labeled events

**Setup (illustrative).** 60 events indexed e = 1, …, 60, event time τ_e (one per day, t_e = e). Every label has horizon h = 5, so event e uses information on calendar days [t_e, t_e + h].

Naive 70/30 chronological split:
- Train events 1..42
- Test events 43..60

**Overlap the naive split ignores.** Event 38 spans [38, 43], event 39 spans [39, 44], …, event 42 spans [42, 47]. Test event 43 spans [43, 48]. So train events 38–42 have label windows that intersect the test block. Those five events must be **purged** from train.

**Embargo.** Take m = 3 (η = 0.05 of T = 60, illustrative percent). Embargo sits **after** the test fold. Test ends at event 60; there is no later train fold in a single split, so the embargo **bites nothing** in this particular 1-split. It becomes material in K-fold: if fold 2 is test events 21–30, then train events 31, 32, 33 are embargoed.

After purge on this split:
- Train: 1..37 (42 minus 5 purged) — **37 events**
- Test: **18 events**
- Dropped: 38–42 (purge)

A 5-fold version on the same 60 events, each test fold 12 events, with η = 5%, typically drops **on the order of 5–8 train events per fold** to purge plus **3 embargo events after each test fold** that has a subsequent train segment. Exact counts depend on whether events are equally spaced; the rule, not the count, is the point — then a trailing gap of m after each test fold.

### Citation list (only works actually used)

1. Gatev, E., Goetzmann, W. N., Rouwenhorst, K. G. (2006). Pairs Trading: Performance of a Relative-Value Arbitrage Rule. *Review of Financial Studies* 19(3), 797–827.
   - https://doi.org/10.1093/rfs/hhj020
   - SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=141615
   - NBER WP 7032: https://www.nber.org/papers/w7032
2. Engle, R. F., Granger, C. W. J. (1987). Co-Integration and Error Correction: Representation, Estimation, and Testing. *Econometrica* 55(2), 251–276.
3. Hamilton, J. D. (1989). A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle. *Econometrica* 57(2), 357–384.
4. López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. Ch. 3 (triple-barrier), Ch. 7 (purged / embargoed / combinatorial CV).

Z-score thresholds, HMM-as-pairs-filter, and the 20-day synthetic tape are **illustrative**. The 11% GGR headline is **documented** in the 2006 RFS abstract; do not treat it as a live expected return.

---

## Q-SB3-2 — local build + buy vs build (verbatim)

A 128 GB M5 Max is **more than enough** for this stack if you stay on daily bars and do not try to ADF-test all ~2 million pairs. The constraint is data quality and engineering discipline, not the machine.

All dollar figures below are **list prices as of mid-2026 vendor pages** (tagged documented) or **illustrative engineering estimates** (tagged as such). Verify before buying.

## 1. Data needed and cheapest adequate vendors

Minimum schema for a GGR + Engle–Granger research tape

| Field | Why |
| ----- | --- |
| Unadjusted close + split/div factors, or a carefully built total-return index | GGR uses cumulative total return, dividends reinvested |
| Volume / ADV, listing exchange, share class | Liquidity and "tradeable" filters |
| Delist events + last price | Survivorship. Without this the distance screen is fiction |
| Point-in-time universe (index members or "listed that day") | Same reason |
| Sector / GICS (or SIC) | Cuts the bomb |
| Corporate-action calendar | Adjustment audit |

Intraday is **not** required for the pipeline you described. HMM-on-daily-returns of the spread or of SPY is enough as a regime filter.

**Cheapest adequate stacks (documented list prices)**

| Vendor | What you actually get | Price | Fit |
| ------ | --------------------- | ----- | --- |
| Norgate US Platinum | Daily back to 1990, delisted names, historical index constituents, fundamentals. Built for backtests. Windows-native DB; ASCII export | USD 630 (documented on norgatedata.com package table) | Best research EOD for this problem if you can live with a Win VM or exported CSV on the Mac. |
| Norgate US Gold | 20y listed-only, no delisteds | 12-mo USD 360 | Too cheap: survivorship bias. Do not use as the only tape. |
| Massive / Polygon Stocks Developer | 10y history, unlimited calls, flat files (day aggregates included on Starter+) | $79/mo documented on polygon.io/pricing (rebrand Massive). Individual-use license. | Fine for listed panel + cheap refresh. You must add a delist/constituent source or you are not doing GGR. |
| Massive Stocks Starter | 5y | $29/mo | Short for a 10y study. |
| Tiingo Power | EOD US + adj prices, history to 1960s for survivors | $30/mo / $300/yr documented on Tiingo's own comparison posts | Good adj-close API. Survivorship still on you. |
| QuantConnect Cloud US equities | Daily (and finer) in-cloud, security master, some corporate actions. Researcher-tier nodes are small | $12,000 for bulk daily — documented on a QC AlgoSeek dataset page; treat as "not retail" | Good for trading a shortlist, bad as the 2M-pair screener. |

What I would actually buy for this Mac (illustrative recommendation): **Norgate Platinum** or **Massive Developer + a one-time dump of delisted/constituent history (Sharadar/Nasdaq Data Link style)**: **~$630–$950** first year. Do not spend on real-time.

Composer-style no-code products do not ship a 2,000-name point-in-time cointegration screen. Ignore them.

## 2. Runtime of the pairwise distance screen (~2M pairs)

**Scale (exact, not estimated)**: C(2000,2) = 1,999,000 pairs; 10y daily ≈ 2520 rows. One 252-day formation window on all pairs is the GGR unit of work.

**Linear algebra identity (use this, not a Python pair loop):** ‖a−b‖² = ‖a‖² + ‖b‖² − 2a·b. One window = one **matrix multiply** XᵀX plus an outer-sum of squared norms. FLOPs ≈ 2 × 2000² × 252 ≈ 2 × 10⁹.

**Illustrative wall times on a 128 GB M5 Max (Accelerate/numpy or Polars → numpy), not a published M5 benchmark:**

| Implementation | One 252-day window, 2k names | ~120 monthly walk-forward windows over 10y |
| -------------- | ---------------------------- | ------------------------------------------ |
| Naive Python for i<j on lists | 15–40 min | many hours (don't) |
| NumPy GEMM / X.T @ X float32, one window resident | 0.3–2 s | 1–5 min including IO and ranking |
| Same, float64 | ~2× | ~2–8 min |
| Polars only (no GEMM) | worse than numpy for this kernel | don't |

M5 Max unified bandwidth is advertised around **600 GB/s** (documented in 2026 M5 Max local-AI roundups). The kernel is bandwidth-light (~10 MB of input per window).

**Cointegration is the real CPU bill.** statsmodels coint on 252 points is **illustratively** 1–5 ms/pair. Blind 2M tests ≈ 0.5–3 hours and is statistically indefensible. Pipeline that does not waste the machine:
1. Sector (or correlation) block → keep ~50–200k pairs.
2. GGR distance top-K per sector (K=20–100).
3. EG/ADF only on a few thousand survivors.
4. That ADF pass: **illustratively 10–60 seconds**.

HMM 2-state Gaussian on one daily return series: seconds. On 2,000 series independently: **a few minutes**. Fit on the spread of the traded pair, or on SPY, not on 2M objects.

## 3. RAM on 128 GB

**Price panel**

| Object | Size (illustrative, order-of-magnitude) |
| ------ | --------------------------------------- |
| 2,000 × 2,520 float64 close | ~40 MB |
| + OHLC + volume + TR index | ~200–400 MB |
| Full Norgate-scale listed+delisted US daily over 20y, ~20k names | ~2–8 GB as a dense panel; less as parquet/arrow |
| One distance matrix float32 | 16 MB |
| 120 stacked distance matrices | ~2 GB if you persist them all |

You will not come close to 128 GB on daily data.

**sklearn / XGBoost meta-labeler**

AFML-style events on a pairs book: even an aggressive design is tens of thousands of events, tens of features. XGBoost histogram on that is hundreds of MB. sklearn PurgedKFold clones of the estimator peak around 2–4 GB. The only way you pressure 128 GB is if you (a) store minute bars for 2,000 names, or (b) keep 2M pair objects resident.

Leave 32–64 GB for whatever local LLM/agent stack you already run. This pipeline does not compete with it.

## 4. Engineering hours by component (illustrative, one competent Python quant, no team)

| Component | Hours | Notes |
| --------- | ----- | ----- |
| Vendor ingest, adjust, PIT universe, delist map, parquet store | 20–40 | This is the quality of the whole paper. Budget high. |
| GGR distance screen + ranking + 12/6 calendar | 8–16 | GEMM version is short; tests and plots take longer |
| EG hedge, ADF gate, z-score, half-life filter | 12–24 | Rolling-β leakage is the footgun |
| 2-state Gaussian HMM + regime gate | 8–16 | hmmlearn or a 50-line EM; validation is the work |
| Triple-barrier + meta-labels on the spread | 16–30 | Path scan, concurrency, uniqueness weights |
| Purged/embargoed CV + CPCV wrapper + XGB/sklearn | 20–40 | Easy to implement wrong; write tests on the 60-event toy from the last chapter |
| Transaction-cost / borrow / close-out engine | 16–30 | Without this the chapter is a signal study, not a strategy |
| Glue, dashboards, reproducibility | 15–25 | |
| **Total to a defensible research repo** | **~120–220 h** | ~1–3 months part-time |
| "Notebook that prints a Sharpe" | 20–40 h | Not the same object |

Mac-specific friction: Norgate wants Windows. Factor **4–8 h** for Parallels/UTM + export, or skip Norgate and accept a weaker tape.

## 5. Buy vs build, and precomputed pairs vendors

**Platforms**

| Option | What it saves | What it cannot do well | Cost |
| ------ | ------------- | ---------------------- | ---- |
| QuantConnect Cloud | Data, security master, execution semantics, a pairs alpha model already in LEAN | 2M-pair vectorized screen on an 8–16 GB research node; AFML purged CV as a first-class primitive; your custom stack | Free → Researcher on the order of tens–low hundreds $/mo depending on nodes (QC pricing page + 2026 reviews; exact SKU mix moves). Local full LEAN+data is not free. |
| LEAN open-source + your parquet | Event study + live later | You still write the screen | $0 engine + your data |
| Composer / no-code allocators | Nothing relevant | No PIT 2k-name cointegration research | Skip |
| Precomputed "pairs analytics" vendors | Almost none exist at this quality for US cash equities at retail. Academic replication kits (RPubs GGR walkthroughs, GitHub) are free but not PIT. | — | Don't pay for a distance matrix you can build in minutes |

**Verdict**
- **Build the research stack on the M5 Max.** Hardware is not the bottleneck. Daily panel + GEMM distance + shortlist ADF + HMM + triple-barrier + purged CV run in minutes.
- **Buy the tape, not the platform.** Norgate Platinum (survivorship) or Massive Developer (cheap listed history) + your own PIT layer.
- **Use QuantConnect later**, if at all, as an **execution/backtest wrapper for the 20 pairs that survive** — not as the screening computer. Cloud nodes are smaller than the machine you already own.
- **Do not buy a pairs-analytics SaaS.** There isn't a serious one at this price that replaces a 15-line X.T @ X.
- **Do not ADF 2 million pairs.** Distance (or sector + correlation) first. That single choice is the difference between a 2-minute job and a multi-hour one.
- One-year cash box (illustrative): **data $630–$950 + zero incremental compute + 150–200 hours of your time.** That is the honest cost of the stack.

---

## Q-SB3-3 — success ratios, after-cost efficacy, failure modes (verbatim)

After-cost numbers only where a paper actually states them. Everything else is labeled as qualitative or illustrative.

## 1. Distance pairs: GGR 1999/2006 vs crowding and costs

**Original claims (documented).** Gatev, Goetzmann and Rouwenhorst, NBER WP 7032 (1999): daily CRSP 1962–1997, top pairs by SSD of normalized prices. Abstract: average annualized excess returns of **up to 12%** on self-financing top-pair portfolios; profits "exceed a conservative estimate of transaction costs."

Same authors, **RFS** 19(3) 2006, sample extended to 2002: "up to **11%**" annualized excess. They still say profits typically beat conservative cost estimates.

**Decay before costs (documented).** Do and Faff, **FAJ** 66(4) 2010, same GGR rule, top-20 committed-capital portfolio, mean monthly excess:

| Window | Monthly excess |
| ------ | -------------- |
| 1962–1988 | 0.86% |
| 1989–2002 | 0.37% |
| 2003–2009 | 0.24% |

They attribute most of the drop not to "more hedge funds" alone but to **worse arbitrage risk** (divergence that does not converge), up to ~70% of the decline in their attribution. Exception: **2000–02** and **2007–09** turbulence, where gross profits rebound.

**After costs (documented).** *Journal of Financial Research* 35(2) 2012, US 1963–2009, commissions + market impact + short-loan fee (~1% annualized, prorated). Base GGR: **unprofitable after frictions**. Industry-refined pairs: risk-adjusted return of about **30 bp per month**; large-cap (top 30% by size) about **24 bp/month** alpha. Both pairs and industry-relative short-term reversal are "largely unprofitable after 2002."

One-way friction estimates in the working-paper / CXO summary of the same study: **0.81%** (1963–88) vs **0.33%** (1989–2009). Across 29 refinements, net monthly returns **−0.07% to +0.35%** (average […]); best four intra-industry books **0.29%/month** net (~3.5% annualized).

Rad, Low and Faff, *Quantitative Finance* 16(10) 2016, US 1962–2014, time-varying costs:

| Method | Gross monthly excess | Net monthly excess |
| ------ | -------------------- | ------------------ |
| Distance | 91 bp | 38 bp |
| Cointegration | 85 bp | 33 bp |
| Copula | 43 bp | 5 bp |

From 2009 on, distance and cointegration **trade-opportunity frequency falls sharply**. All three still print significant factor alphas in-sample; that is not a live capacity statement.

**Failure regimes.** Non-convergence (Do–Faff's main decay channel); one-day delayed execution (GGR themselves flag microstructure noise); crowding into the same top pairs.

## 2. Cointegration / z-score pairs, including intraday

**Daily, after costs (documented).** Rad–Low–Faff: cointegration **33 bp/month net** over 1962–2014, same cost schedule as above; opportunity count drops after 2009.

**Intraday, after costs — treat as sector-and-period specific, not a Sharpe you can port.**
- Liu, Chang, Geman, Yu, [journal] 17(1) 2017: "doubly mean-reverting" spreads, oil names, HF data. Abstract: annualized Sharpe **3.9** (Jun 2013–Apr 2015) and **7.2** (2008), "even accounting for transaction costs." Commodity-spike regime is part of the design.
- Stübinger and Endres, *Quantitative Finance* 18(10) 2018: jump-diffusion pairs, S&P oil, minute bars 1998–2015. **60.61% p.a.** and Sharpe **5.30 after transaction costs**.
- Stübinger and Bredthauer, 2017: S&P 500 minute bars 1998–2015, several rules; best reported Sharpe **8.14 after costs**, return **50.50% p.a.** They also write that **most algorithms show declining returns over time**. Cost assumption in related Erlangen work is often **5 bp per share per half-turn** (≈ **20 bp full-turn per pair**) (following Avellaneda–Lee 2010). That is a modeling choice, not exchange-fee truth in 2026.

**Honesty layer.** Those Sharpes are backtests on a small, highly related industry, often with one-bar execution delay. There is no documented live Sharpe for a 2,000-name EG z-score book on a retail stack. Theoretical papers (e.g. on optimal OU trading) show that if prices were tightly cointegrated with short-memory returns, Sharpes would be absurd (>10); the empirical record does not look like that.

**Failure regimes.** Cointegration break (Huang–Martin 2019: 32% of CFD pairs lost money; 94% of those losses tied to a break); frozen hedge ratios that stop tracking the spread.

## 3. ETF vs basket / iNAV

**Who captures it (documented mechanism).** Two layers (Ben-David, Franzoni, Moussawi and the AP literature):
1. **Authorized participants (primary market).** Create/redeem in **creation units**, most commonly **50,000 shares**. Creation/redemption fee documented in that literature as on the order of **$500–$3,000 per order** ($500 median / ~$1,047 mean per unit, typically **<1 bp** of a large unit — plus the AP pays the trading cost of assembling or dumping the basket.
2. **Secondary-market APs / lead market makers.** Long cheap side, short rich side (ETF vs basket, vs futures, vs a peer ETF), hedge through the day, flatten into the close. A non-AP cannot create or redeem. A small book can only do the **secondary** trade: ETF vs a subset of holdings, vs a liquid peer ETF, or vs the future. That is a noisy, residual trade.

**How wide is the gap? (documented)** Petajisto, **FAJ** 73(1) 2017, ~1,800 US ETFs, 2007–2014:
- Average premium **6 bp**, volatility **49 bp** (so a ~±96 bp band at 2σ, raw).
- Illiquid / international / HY / EM: averages **18–37 bp**, bands **100–200 bp** even after a stale-NAV peer adjustment.
- Premium half-life: **~half a day** for equities, **2–3 days** for non-Treasury bonds.
- Industry-wide "paid in premium/discount" on the order of **$40bn/year**, **~$20bn** after stale-NAV adjustment, vs ~**$6bn** then-year management fees. An active **premium-reversion** strategy in that paper earns "substantial" abnormal returns **before transaction costs** — he does not hand you a live after-cost Sharpe for a 50k-share-constrained book.

FactSet/industry summary for liquid US equity ETFs (ADV ≥ $250k, ex bond): median trailing 12-month […], mode **0.00%**. That is the band APs already compressed.

**What is left for a small operation.** On liquid US equity ETFs the residual after AP competition is **a few bp**, often inside your spread + impact + locate. Creation-unit minimums take you off the table as a primary player; what remains is harvesting the premium, i.e. being the other side of Petajisto's $20–40bn, which is a market-making P&L, not a directional signal. Miss one leg and you break the hedge.

## 4. Machine-readable news, first minute

**TV / human headline, timestamped (documented).** Busse and Green, **JFE** 65(3) 2002, CNBC Morning/Midday Call, market open:
- Prices move **within seconds** of first mention.
- Positive Midday reports: move **fully in about one minute** (one summary of their figure: **+41 bp** in that first minute vs t=0).
- Negative reports: slower, about **15 minutes** to incorporate (short-sale friction).
- Volume **doubles** in minute one.
- Traders who get filled **within 15 seconds** of first mention earn **small but significant** profits on positive Midday Calls — i.e. the edge is a latency edge, not a "read the story on the terminal" edge.

**Machine news analytics (documented, less of a tradable bp).** Groß-Klußmann and Hautsch, *Journal of Empirical Finance* 18(2) 2011, Reuters NewsScope, LSE, **20-second** bars: relevant/novel/signed firm news produce distinct moves in returns, vol, volume, **and spreads**. Relevance classification is required to beat noise. Sentiment has some predictability for the **subsequent** price path, **but profitability is deteriorated by the spread widening that arrives with the news.** That is the after-cost sentence in the abstract.

A 2026 lag-compression note on macro headlines (CPI median quote lag **450 ms → 120 ms** pre- vs post-LLM sample) is a different object — index ETF microstructure, not single-name first-minute alpha.

**Failure regimes.** Being second; paying the news-time spread; trading low-relevance items; assuming a multi-minute drift persists. Treat news as a **risk filter** (Do–Faff: news on divergence day changes pair outcomes), not a first-minute alpha you will capture from a laptop.

## 5. Triple-barrier + meta-labeling

**What de Prado actually claims (documented).** *Advances in Financial Machine Learning* (2018), Ch. 3: triple-barrier labels the **outcome** (PT / SL / vertical), not a fixed-horizon sign. Ch. 3 meta-labeling: primary model sets **side**; secondary binary model predicts **whether the bet succeeds** and thus can size. Purpose stated in the book and in Hudson & Thames' reprint of the argument: raise **precision** (and thus F1) by killing false positives; "**It is not its purpose to come up with a betting opportunity.**"

He does **not** publish a universal "meta-labeling adds X Sharpe." The documented claim is a **precision/F1 mechanism**, plus the strategy-risk template (Ch. 13 logic used later by Joubert et al.): meta-labeling helps when you already have a primary edge worth sizing.

**Independent check, not de Prado's number.** Daru Finance reproduction (42 instruments, EMA-crossover primary — a dumb primary on purpose): meta-labeling improves Sharpe in **38/42** and DSR in **39/42**, doubles the count with PF>1 (**12 → 24**), and moves some books from losing toward **break-even** — **0/42** reach clear DSR > 0.95. Their line: precision filter, **not an alpha source**.

**After-cost honesty.** Meta-labeling reduces turnover if it vetoes trades. That can help net P&L even when gross edge is thin (Do–Faff's 30 bp world). It cannot manufacture alpha.

**Failure regimes.** Leakage if labels are not purged/embargoed (AFML Ch. 7); training the meta-model on the same features without embargo discipline.

## Cross-cutting after-cost picture

| Sleeve | Documented net-ish result | Who still owns it | Dies when |
| ------ | ------------------------- | ----------------- | --------- |
| GGR daily distance | ~0 after 2002 on vanilla top-20; ~24–30 bp/month only on refined industry books through 2009 | Slow, cheap, patient books in stress | Crowding, non-convergence, costs of the early sample |
| Daily EG/z-score | 33 bp/month net 1962–2014; fewer trades after 2009 | Same, plus names that stay cointegrated | Breaks, frozen β |
| Intraday cointegration | Backtest Sharpes 3–8 in oil/S&P minute studies after stylized 5–20 bp costs | Specialized HF, one sector | Spreads, 2008-in-sample, declining later years |
| ETF–NAV | Average premium 6 bp; liquid US equity median 2 bp | APs and lead MMs | You are not an AP; unit size; stress de-pegs |
| First-minute news | Seconds-to-one-minute incorporation; 15-second edge was already the documented profit window in 2000 TV data; machine news widens the spread | Colocated parsers | Any research latency |
| Meta-label / triple barrier | Precision/F1 tool; reproductions show PF lift toward break-even, not a deflated Sharpe | Anyone with a real primary | No primary edge |

For the chapter: write GGR/Do–Faff as the **base rate**, Rad–Low–Faff as the **method horse-race after costs**, Petajisto as why ETF–basket is not a spare-bedroom trade, Busse–Green and Groß-Klußmann–Hautsch as a **risk event**, not a signal at daily frequency, and de Prado as a **sizer/filter** that does not replace a dead primary.
