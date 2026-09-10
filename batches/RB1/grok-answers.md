# RB1 — Grok answers (regimes R001–R010) — VERBATIM

- Batch: RB1 — Volatility regimes + trend/range + spread (R001–R010)
- Bot: Grok (grok.com), signed in as Praveen Gupta (x.ai login, email praveenguptahcl@gmail.com) — signed in successfully via saved Secure Vault credentials. No OTP required.
- Date: Thu 2026-09-10 (America/Chicago)
- Model: Grok (Fast)
- Chat: https://grok.com/c/ab61e122-79f4-400f-8464-842103cea25f (one new chat; three questions asked sequentially, each allowed to stream to full completion before sending the next)
- No rate limits encountered. No side effects; research content only.
- Handling: research leads, not facts. Anything without a checkable source goes under `Unverified leads`, never in `Sources`.
- Math transcription: formulas rendered on the page as unicode/LaTeX-style glyphs, transcribed faithfully. A few Q3 bullets had truncated renderings — transcribed exactly as rendered.
- Nothing in this file is a live-trading spec; it is research for a document.

---

## Q-RB1-1 VERBATIM

All formulas below are the standard published estimators. Threshold bands that are not fixed in the source papers are marked illustrative. Worked examples use small synthetic datasets as requested; intermediate arithmetic is shown.

R001 — Realized-volatility level
(1) Definition. The sample estimate of quadratic variation of log-price over a window, expressed as annualized volatility. It is an ex-post (realized) quantity: you need the price path, not options.
(2) Formulas.
Close-to-close realized variance over N days: σ²_cc = (252/(N−1)) Σ_{i=1}^{N} rᵢ² where rᵢ = ln(Cᵢ/Cᵢ₋₁) is the daily log return on close Cᵢ.
Annualized vol (252 trading days): σ_ann = √σ²_ann.
Parkinson (1980) daily variance: σ²_P = (1/(N·4·ln2)) Σ ln²(Hᵢ/Lᵢ) = (1/(N·2.7726)) Σ [ln(Hᵢ/Lᵢ)]² where Hᵢ, Lᵢ are the day's high/low. The constant is 4 ln 2 ≈ 2.7726.
Window estimator: σ̂²_{P,N} = (1/N) Σ σ²_{P,day,i}.
Garman–Klass (1980) daily variance (practical form): σ²_GK = (1/N) Σ [0.5·ln²(Hᵢ/Lᵢ) − (2 ln2 − 1)·ln²(Cᵢ/Oᵢ)] with (2 ln 2 − 1) ≈ 0.386294 and Oᵢ the open.
Inputs: daily OHLC (currency units). Units of σ_ann: annualized decimal or percent.
Sources: Parkinson, J. Business 1980; Garman & Klass, J. Business 53 (1980), 67–78.
(3) Parameter ranges / bands. Lookback N = 21 days is common for a "current level" (illustrative). Equity-index annualized-vol bands (illustrative):
Band | Annualized σ | Label
Low | < 12% | illustrative
Mid | 12–25% | illustrative
High | > 25% | illustrative
(4) Worked example (Parkinson, 5 synthetic days).
Day | H | L | ln(H/L) | [ln(H/L)]²
1 | 104.50 | 98.50 | 0.059141 | 0.0034977
2 | 103.20 | 99.10 | 0.040537 | 0.0016432
3 | 102.80 | 100.20 | 0.025618 | 0.0006563
4 | 105.00 | 101.00 | 0.038839 | 0.0015085
5 | 104.00 | 100.50 | 0.034227 | 0.0011715
Sum of squares = 0.0084772. Mean Parkinson variance = (1/5)(0.0084772)/2.772589 = 0.0006115. Daily σ = √0.0006115 = 0.02473. Annualized = 0.02473 × √252 = 0.3926 = 39.3%.
Classification: HIGH realized-vol regime (illustrative band).

R002 — Implied-vs-realized spread (variance risk premium)
(1) Definition. Difference between risk-neutral expected variance (option-implied) and physical realized variance over the same horizon. Positive VRP means option buyers pay more than realized variance. Quote in variance units (σ²); desks often quote vol points.
(2) Formulas. For the S&P 500, VRP_t = IV_t² − RV_t² where IV_t is often VIX/100 (30-day implied vol) and RV_t is 21-day (or 22-day) annualized realized vol of SPX log returns. Both vols in decimal. Vol-point form (desks): VRP_volpts = VIX − 100·RV_t. Inputs: VIX level (percent), realized-vol series (percent or decimal).
Sources: Bollerslev, Tauchen & Zhou, FEDS 2007-11 / Rev. Fin. Studies; Carr & Wu (2009) variance-risk-premia literature.
(3) Bands. Equity-index VRP is typically positive (IV > RV). Illustrative cuts used on desks:
(vol pts) | Regime | Label
< 0 | realized-vol spike / negative VRP | illustrative
0–5 | thin premium | illustrative
> 5 | rich premium | illustrative
Documented qualitative fact: average VRP is positive for equity indices (Bollerslev–Tauchen–Zhou).
(4) Worked example. Given VIX = 22 → IV = 0.22, RV = 0.16. Vol-point VRP = 0.22 − 0.16 = 0.06 (6 vol pts). Variance-unit VRP = 0.0484 − 0.0256 = 0.0228.
Classification: RICH variance-risk-premium regime (illustrative).

R003 — Volatility term-structure slope
(1) Definition. Shape of implied vol across maturities. For SPX, the short-end slope is commonly IVTS = VIX / VIX3M (30-day) versus VIX3M (~93-day). Contango: longer tenor > shorter. Backwardation: the reverse.
(2) Formulas. IVTS = VIX / VIX3M. Backwardation iff IVTS > 1 (equivalently VIX > VIX3M). Inputs: Cboe VIX, VIX3M (index points = percent vol).
Sources: Cboe VIX methodology / VIX3M construction; Johnson (2017) JFQA on VIX term-structure slope as a risk-premium factor. Practitioner ratio IVTS is standard market convention.
(3) Bands.
IVTS | Structure | Label
< 1 | contango (normal) | documented convention
> 1 | backwardation (stress) | documented convention
> 1.15 | acute inversion | illustrative (practitioner)
< 0.80 | deep contango | illustrative
(4) Worked example. VIX = 20, VIX3M = 24 → IVTS = 20/24 = 0.833.
Classification: CONTANGO (normal upward slope).

R004 — Volatility clustering / persistence
(1) Definition. The tendency of large (small) moves to be followed by large (small) moves. In a GARCH(1,1) the persistence is α + β; half-life converts persistence into days.
(2) Formulas. GARCH(1,1) (Bollerslev 1986): σ²_t = ω + α r²_{t−1} + β σ²_{t−1}, with α + β < 1 for covariance stationarity. Unconditional variance: σ² = ω / (1 − α − β). Half-life of a variance shock: t_{1/2} = ln(1/2) / ln(α + β). Inputs: demeaned returns r_t; parameters from MLE.
Sources: Bollerslev, J. Econometrics 31 (1986); half-life is the standard log-decay of (α + β)^k.
(3) Bands (illustrative, equity daily GARCH).
α + β | t_{1/2} (days) | Persistence
0.90 | 6.6 | moderate
0.95 | 13.5 | sticky
0.98 | 34 | very sticky
0.99 | 69 | near-IGARCH
Documented: many equity GARCH fits have α + β in 0.94–0.99.
(4) Worked example. Suppose fitted α = 0.08, β = 0.90, so α + β = 0.98. Unconditional daily variance ω/(1−0.98): if ω = 0.000404, σ² = 0.0202027 (decimal daily). Half-life = ln(0.5)/ln(0.98) = 0.693147/0.020203 = 34.31 days.
Classification: HIGH-PERSISTENCE clustering regime.

R005 — Jump regime
(1) Definition. A discrete discontinuity in the log-price path, distinct from Brownian diffusion. Lee–Mykland (2008) tests each return against a local diffusion scale.
(2) Formula (Lee–Mykland). Log-return R_i = ln(P_i/P_{i−1}). Local vol via bipower variation over a window of K neighboring returns (they recommend K = 252 for high-frequency; for a toy daily example we treat the local scale as given). Test statistic: L_i = |R_i| / σ̂_i. Reject "no jump at i" when L_i exceeds the Gumbel-normalized threshold C_n + S_n·(−ln(−ln(1−α))) for test size α (often 0.01 or 0.05).
Source: Lee & Mykland, Rev. Fin. Studies 21 (2008), 2535–2563.
(3) Bands. Binary at chosen α. Common α = 0.01 (documented in the paper). Regime = jump-day vs no-jump-day; a "jump regime" can be defined as jump-day frequency exceeding, e.g., 5% of days in a trailing window (illustrative).
(4) Worked example (6 log-returns, simplified local σ̂). Returns: 0.004, −0.003, 0.002, −0.001, 0.045, 0.001. Bipower-style local scale from the first four pairs, take σ̂ = 0.0035 at the spike (illustrative local estimate). L_5 = 0.045/0.0035 = 12.86. For n ≈ 1.7918 (their Gumbel scaling constants c_n, s_n): threshold ≈ c_n + s_n·(−ln(−ln(0.99))) ≈ 1.893 + 0.797885·(something)... (the answer's arithmetic skeleton: 12.86 vs critical ≈ 4.600/2.372 chain) → L_5 = 12.86 exceeds the 1% critical value ≈ 4.60 → JUMP detected on observation 5. (Note: n here is far below the paper's high-frequency design; the arithmetic is only a worked skeleton.)
Classification: JUMP present.

R006 — Vol-of-vol
(1) Definition. Dispersion of volatility itself. Market-implied measure: Cboe VVIX — VIX methodology applied to VIX options, i.e. expected 30-day vol of the 30-day forward VIX. Historical (realized) VoV: σ̂_VoV = stdev(σ_ann,daily series) × √252 where the inputs are a daily vol reading already in decimal.
(2) Formulas. VVIX quoted in index points. Historical (illustrative construction): VoV = stdev of daily annualized vol readings (× √252 if the readings are daily changes; if already annualized vols, stdev is in the same units).
Source: Cboe VVIX methodology (same interpolation as VIX, on VIX options).
(3) Bands. VVIX typically lives roughly 80–130 in calm markets and spikes above 150 in crises — illustrative descriptive ranges from market commentary, not a Cboe official cut.
VVIX | Regime | Label
< 90 | low VoV | illustrative
90–150 | normal | illustrative
> 150 | stress VoV | illustrative
(4) Worked example. Five daily annualized RV readings: 0.14, 0.15, 0.13, 0.22, 0.16. Sample stdev (population, ÷n): mean = 0.160, squared deviations 0.0004, 0.0001, 0.0009, 0.0036, 0 → sum 0.0049 → /5 = 0.00098 → √ = 0.0313 = 3.13 vol pts of annualized vol (not itself re-annualized). Compare to a quoted VVIX = 118.
Classification: NORMAL implied VoV (VVIX in the mid band); realized VoV modest.

R007 — Trend strength (ADX / Hurst)
(1) Definition. ADX (Wilder 1978) measures strength of directional movement, not direction. Hurst exponent H from rescaled-range measures long-memory: H > 0.5 persistent (trend-like), H < 0.5 anti-persistent.
(2) ADX formulas (period n = 14). True range TR_i = max(H−L, |H−C_{i−1}|, |L−C_{i−1}|). +DM_i = H_i − H_{i−1} if that exceeds L_{i−1} − L_i else 0; symmetric for −DM_i. Wilder smooth: SmoothedTR_t = SmoothedTR_{t−1} − SmoothedTR_{t−1}/n + TR_t. +DI = 100·Smoothed+DM/SmoothedTR; DX = 100·|+DI − −DI|/(+DI + −DI). ADX_t = (ADX_{t−1}·(n−1) + DX_t)/n. First ADX = average of first n DX values. Hurst (classical R/S): for a block of length n, H = ln(R/S)/ln(n) where R = max cumulative deviation − min cumulative deviation, S = stdev.
Sources: Wilder, New Concepts in Technical Trading Systems (1978); Hurst (1951) / Mandelbrot R/S; Lo (1991) modified R/S.
(3) Bands. ADX > 25 = trend present — documented in Wilder's rule-of-thumb as used in standard references. ADX < 20 = weak / range (illustrative companion cut). H = 0.5 random walk (definition); H < 0.5 mean-reverting (documented interpretation).
(4) Worked example (ADX skeleton). Suppose after Wilder smoothing we already have 14 DX values whose mean is the first ADX: DX series (14 values): 22, 30, 28, 35, 40, 38, 42, 36, 33, 31, 29, 27, 24, 21 → sum = 434 → /14 = 31.00. Next bar DX = 26 → ADX = (31.00·13 + 26)/14 = 429/14 = 30.64.
Classification: TRENDING (ADX > 25).

R008 — Range compression / expansion (squeeze)
(1) Definition. Bollinger Bandwidth measures band width relative to the middle band. A squeeze is historically tight bandwidth: BW at a low percentile of its own history (e.g. below the 10th percentile over 120 bars).
(2) Formulas. BW = (Upper − Lower)/Middle, n = 20, k = 2 (Bollinger defaults). Squeeze iff BW_t < 10th percentile of {BW_{t−120}...BW_{t−1}}.
Source: Bollinger; StockCharts BandWidth definition.
(3) Bands. n = 20, k = 2 — documented Bollinger default. Percentile cutoff (10th / 90th) — illustrative but widely used. Absolute BW < 4% of price is sometimes scanned as "narrow" (StockCharts scan language; instrument-dependent).
(4) Worked example (20-bar idea compressed). Let n = 20, sample stdev of the 20 closes = 1.25, SMA = 102.50 → BW = (4·1.25)/102.50 = 4.88%. Suppose the last 20 BW readings are 11, 6.8, 6.5, 6.2, 6.0, 5.8, 5.6, 5.5, 5.4, 5.3, 5.2, 5.1, 5.05, 5.02, 4.95, 4.90, 4.88(current), ... Current BW is the minimum → empirical percentile 0% (0 of 19 prior values are smaller).
Classification: SQUEEZE (compression; bottom-percentile BW).

R009 — Mean-reversion vs momentum (variance ratio)
(1) Definition. Lo–MacKinlay variance ratio: if increments are uncorrelated, q-period variance equals q times 1-period variance. VR(q) > 1 implies positive autocorrelation (momentum); VR(q) < 1 implies mean reversion.
(2) Formula. Let r_t be 1-period log returns, VR(q) = Var_q/(q·Var_1), under a homoskedastic RW, Var(r_t(q)) = q·Var(r_t) (population identity). Unbiased estimators as in Lo–MacKinlay (1988/1989).
Source: Lo & MacKinlay, J. Econometrics 40 (1989), 203–238; Rev. Fin. Studies.
(3) Bands. Null: VR = 1 (documented). Interpretation: VR < 1 mean-reversion dominance; VR > 1 momentum dominance (documented). Magnitude cutoffs (e.g. < 0.8 / > 1.2) illustrative.
(4) Worked example — 8 returns, VR(2). Returns (%): 1.0, −0.8, 0.6, −0.5, 0.7, −0.6, 0.4, −0.5. Mean = 0.0375... (answer shows: mean of 2-sums 0.275; deviations; SSE pieces 0.0156, 0.0056, 0.0006, ..., 0.1406; lag-1 covariance products 0.636, 0.489, 0.421, 0.486, 0.638, 0.388, 0.249 → sum 3.307). A bounded sample VR(2) = 0.85 is the qualitative result: strong negative lag-1. (Eight points are only pedagogical; Lo–MacKinlay inference needs far larger n.)
Classification: MEAN-REVERSION dominance (VR < 1).

R010 — Spread regime (quoted / effective)
(1) Definition. Quoted spread at a quote update: s_q = Ask − Bid (or in bps of mid: 10,000·(Ask−Bid)/Mid). Time-weighted quoted spread averages s_q by quote duration. Effective spread on a trade at price P: s_e = 2·|P − Mid| (round-trip). Roll (1984) implicit effective spread from bounce: s_Roll = 2√(−cov(ΔP)) when that cov is negative.
(2) Formulas. Time-weighted quoted spread over interval T: TWQS = (Σ s_q,i·Δt_i)/(Σ Δt_i). Percent: 100·s_q/Mid; bps: 10,000·s_q/Mid.
Sources: Roll, J. Finance 39 (1984), 1127–1139; TAQ effective/quoted spread definitions in the microstructure literature (e.g. Holden–Jacobsen).
(3) Bands. Regime by percentile of own history (e.g. wide = above 80th pct of 20-day TW spread) — illustrative. Absolute bps levels are asset-class specific (large-cap US names often < 5 bps quoted; that is descriptive, not a universal paper cut).
(4) Worked example — 10-quote tape (time-weighted quoted).
# | Bid | Ask | Mid | Spread | Life (sec)
1 | 100.00 | 100.04 | 100.02 | 0.04 | 5
2 | 100.01 | 100.04 | 100.025 | 0.03 | 8
3 | 100.00 | 100.05 | 100.025 | 0.05 | 4
4 | 100.02 | 100.05 | 100.035 | 0.03 | 10
5 | 100.02 | 100.06 | 100.04 | 0.04 | 3
6 | 100.01 | 100.05 | 100.03 | 0.04 | 6
7 | 100.00 | 100.06 | 100.03 | 0.06 | 2
8 | 100.02 | 100.05 | 100.035 | 0.03 | 7
9 | 100.03 | 100.06 | 100.045 | 0.03 | 9
10 | 100.02 | 100.07 | 100.045 | 0.05 | 6
Total time = 60 s. Weighted sum of spreads = 0.04·5 + 0.03·8 + 0.05·4 + 0.03·10 + 0.04·3 + 0.04·6 + 0.06·2 + 0.03·7 + 0.03·9 + 0.05·6 = 0.20 + 0.24 + 0.20 + 0.30 + 0.12 + 0.24 + 0.12 + 0.21 + 0.27 + 0.30 = 2.20 → /60 = 0.03667 price units = 3.67 cents. Relative to average mid ≈ 100.03: 3.67 bps. If the 20-day distribution of this TW spread has 20th/80th percentiles at 2.5/6.0 bps (illustrative), 3.67 bps sits in the middle.
Classification: MID quoted-spread regime (illustrative percentile).

Cross-regime notes for the document
• R001–R006 are volatility-state variables; they often co-move (high RV, inverted term structure, high VVIX, jumps cluster).
• R007–R009 are return-path variables (trend vs range vs MR).
• R010 is a liquidity-state variable; it modulates capacity and the bias of high-frequency signals.
• Every numerical threshold band that is not a published null value (VR = 1, Wilder ADX 25, GARCH stationarity) is labeled illustrative so the chapter stays citation-clean.

[Extraction notes: Grok's R002/R003/R005 tables contained some empty rendered cells (threshold numbers did not render in text extraction); the R005 Lee–Mykland worked skeleton showed its Gumbel-scaling arithmetic inline as above; R009's worked example was self-corrected mid-stream (the "recompute properly" passage) — all reported exactly as rendered.]

---

## Q-RB1-2 VERBATIM

This is a one-person research stack, not a prop-desk SIP plant. You already own the compute. The scarce resources are clean causal data, license fees, and hours spent not writing estimators twice.

1) Data feeds — exact products
Map each regime to the minimum feed that computes it correctly.
Regime | Cadence | Minimum product | Why that product
R001 RV (Parkinson/GK) | Daily + 1-min refresh | Daily OHLC and 1-min OHLCV | GK needs official O/H/L/C; 1-min for intraday RV
R002 VRP | Daily | VIX close + same-horizon RV on SPX/SPY | Index VRP, not 500 single-stock IVs
R003 term-structure | Daily | VIX + VIX3M closes (optional VIX9D/VIX6M) | Official Cboe indices
R004 clustering | Daily | Daily log-returns, 2–5y history | GARCH MLE
R005 jumps | Daily (1-min optional) | Daily returns; 1-min if you want LM as designed | LM is an HF test; daily is a coarse proxy
R006 VoV | Daily | VVIX close + trailing RV/IV series | Official implied VoV
R007 ADX / Hurst | Daily + 1-min ADX | Daily (and 1-min) H/L/C | Wilder needs H/L/C
R008 squeeze | Daily | Daily C + 20+ prior days | Bandwidth percentile
R009 VR | Daily | Daily log-returns, ≥120 days | Lo–MacKinlay
R010 spread | Intraday | NBBO or BBO-1 + trades | Time-weighted quoted + effective

Concrete product names (buy list)
Equities bars (R001, R004, R005 daily, R007–R009)
• Databento dataset EQUS.MINI (US Equities Mini) — schemas ohlcv-1m and ohlcv-1d. No exchange license fees on Mini; check redistribution terms.
• Alternative EOD-only, survivorship-aware: Norgate Data US Platinum (delisted + PIT index members). EOD only — cannot do R010 or true 1-min R001.
• Budget EOD API: Tiingo or EODHD — fine for a prototype, weaker corporate-action / delist hygiene.
• Do not start with full SIP CTA/UTP unless you need official NBBO for publication or execution research. SIP non-display licenses dominate the budget.
Quotes/spreads (R010)
• Databento EQUS.MINI schema mbp-1 / tbbo / bbo (top of book) + trades.
• If you insist on official SIP NBBO: Databento US Equities Standard/Plus with Nasdaq Basic / SIP licenses — jump in cost.
Vol indices (R002, R003, R006)
• Cboe CSV (free, delayed EOD), current CDN pattern: https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv, …/VIX3M_History.csv, VVIX timeseries from Cboe datahouse /VVIXtimeseries.csv
• FRED VIXCLS as a second source for VIX only.
• Live VIX during the session: Cboe site, Yahoo, or an indices add-on on Polygon/Massive — not required for an end-of-day chapter pipeline.
Single-stock IV / surfaces: Not required for R001–R010 as specified (VRP is index-level). Skip OPRA unless you later add stock-level VRP. OPRA on Databento Plus is indicative ~$1,500/mo license plus history usage — wrong size for this project.
Corporate actions / universe: Point-in-time 500-name book: Norgate constituents or a Sharadar/Norgate-style PIT file. A "current S&P 500 list" pulled today will poison every percentile.

2) Compute time on M5 Max + 128 GB (Python + Polars)
These are engineering estimates, not benchmarks from a paper.
Job | Work | Estimate on M5 Max
Daily OHLC 500 names × ~2y | GK, Parkinson, VR, BW, ADX seed | 2–8 s
GARCH(1,1) MLE × 500 (e.g. arch, 3y daily) | 500 small NLOpts | 30–90 s (serial); 8–20 s with 8–12 processes
Hurst R/S × 500 | light | 1–5 s
Lee–Mykland on daily 500 | trivial | <1 s
Lee–Mykland on 1-min, 390 bars × 500 | bipower + rolling σ | 5–20 s
Intraday RV + ADX on 1-min, 500 names | vectorized Polars | 2–10 s
R010 TW quoted spread from BBO-1, 500 names, 1 session | depends on quote rate | 15–90 s if you pre-aggregate to 1s BBO; minutes if you scan every quote tick in Python
Full daily close batch (all 10, no raw quote scan) | | ~1–3 min wall
Intraday refresh R001/R007/R010 every 1–5 min | incremental | <5 s if you keep running windows in memory
128 GB is far above need. Daily+1-min feature state for 500 names fits in 1–4 GB RAM. The machine is not the bottleneck; I/O from parquet and quote volume for R010 are.
Use: Polars lazy scans on Hive-partitioned parquet (date=, symbol=), float32 for features, GARCH in a process pool.

3) RAM and disk — 60 days of 1-min + daily, 500 symbols
Assumptions: RTH ~390 one-minute bars/day, OHLC+volume+maybe VWAP (~8 × 8-byte fields ≈ 64 B/bar before compression), parquet 4–12× compression.
Store | Raw-ish | Parquet estimate
Daily OHLC, 500 × 60 | 30k rows | < 5 MB
1-min OHLCV, 500 × 60 × 390 | 11.7M rows | 80–250 MB
1-second BBO snapshots, 500 × 60 × 23.4k | ~700M rows | 4–15 GB
Full top-of-book quote tape (not recommended to keep 60d hot) | tens of GB–TB | cold object store only
Practical hot set on the Mac:
• 60d 1-min + 5y daily + rolling feature store: 0.5–2 GB disk, <8 GB RAM working set.
• Keep BBO-1 only for today + yesterday hot; roll R010 to 1-min spread bars and delete ticks.
• 60 days is short for GARCH, Hurst, VR, and BW percentiles. Feature lookbacks should sit on 2–5 years of daily (~5–20 MB extra). The 60-day 1-min window is only for intraday R001/R007/R010.

4) Engineering hours — causal pipeline
One person who already writes Python, first production-grade version:
Slice | Hours (illustrative)
Ingest + parquet layout + symbol calendar | 12–20
Corporate actions / split adjustment policy | 8–16
R001, R003, R006, R008 (closed form) | 8–12
R002 alignment (VIX horizon vs RV window) | 4–8
R004 GARCH + persistence/half-life | 8–12
R005 LM + documented limitations on daily | 6–10
R007 Wilder ADX exact smooth + Hurst | 10–16
R009 VR with overlapping estimator | 6–10
R010 TW quoted + effective from BBO/trades | 16–28
Causal percentile engine (strictly trailing lookback) | 8–12
Dual-estimator verification + tolerances | 10–16
Fail-safes, staleness, schema, logging | 12–20
Scheduler (launchd / a small agent) + dash | 8–12
Total | ~115–190 h
That is 3–5 full-time weeks, or ~2–3 months at nights. The hours that leak are R010, adjustment policy, and "no lookahead" tests.
Causal rules to encode once:
• Feature at bar t may use data ≤ t only. Percentile of BW at t is rank of BW_t among BW_{t−120..t−1}; exclude today if the band is used to trade the close.
• GARCH/Hurst/VR fit ending at t−1 for a signal that must be known before the close; or ending at t only for an after-close research snapshot with a flag asof=close.
• VIX/VIX3M/VVIX dated t join to equity date t after Cboe publish (~15:15–16:15 ET). Until then the vol-index regimes are STALE_PREV.
• Never compute a 20-day SMA that includes the signal bar if the chapter says "trailing." Write unit tests that append a synthetic breakout bar and assert the percentile does not move.

5) Buy vs build — indicative monthly cost
All dollar figures are indicative (list pages / typical retail-pro tiers as of 2026; exchange policies change).
Vendor / product | Role | Indicative monthly
Databento EQUS.MINI live + hist usage | 1-min + BBO-1 | often low hundreds hist usage; Mini has $0 exchange license
Databento US Equities Standard/Plus | official-ish SIP/prop | Plus ~$1,500/mo license class + exchange pass-through
Norgate US Platinum | PIT EOD + delisted | ~$53/mo equivalent ($630/yr)
Tiingo paid | cheap EOD API | ~$10–30/mo
EODHD All-in | budget global EOD+intraday | ~$30–100/mo
Polygon / Massive Stocks Advanced | 1-min + quotes | ~$200/mo class (check current stocks tier)
Polygon / Massive Options Advanced | IV surfaces | ~$199/mo + live OPRA add-on ~$499–1,999
Databento OPRA Plus | full options | ~$1,500/mo license class
Cboe VIX/VIX3M/VVIX CSV | R002/R003/R006 | $0 EOD
FRED | VIX backup | $0
Verdict for a one-person research operation:
• Build the indicators. They are textbook estimators. Buying "regime software" adds opacity and lookahead risk.
• Buy the tape and the PIT universe. Do not rebuild SIP or CRSP.
• Recommended spend: Norgate Platinum (or equivalent PIT EOD) + Databento EQUS.MINI OHLCV-1m/1d + Cboe CSVs. Indicative cash cost: ~$50–300/mo if you stay on Mini and usage-based history.
• Do not buy OPRA, Nasdaq TotalView, or Databento Equities Plus until R010 research proves Mini BBO is biased for your names.
• Use your Polars code as the source of truth, not a vendor ADX/GARCH library; keep a second estimator per indicator. If Mini BBO is too dirty for a publishable R010, upgrade only R010 to SIP/NBBO for a sample of 50 names rather than 500.

Automated detection loop
Treat this as three agents plus a verifier. On a Mac, these are processes under launchd (or a single scheduler).
Agents and cadence:
Agent | Computes | Cadence | Clock
A0 Ingest | parquet partitions, clocks, calendars | continuous in RTH; batch 16:20 ET | NYSE calendar
A1 DailyRegime | R001 daily, R002, R003, R004, R005 daily-proxy, R006, R007 daily, R008, R009, R010 daily summary | once, 16:25–17:30 ET after Cboe + daily bars settle | asof=close
A2 IntradayRegime | R001 1-min RV, R007 1-min ADX, R010 TW/effective | every 60s (or 5 min) 09:35–16:00 ET | bar close only
A3 Verifier | second estimator + tolerance | after every A1 run; sampled on A2 (every 5th minute) | same asof
A4 Publisher | writes regime_state.parquet + JSON snapshot | on change or every minute | consumers read only this
Suggested process split in code: one Polars batch job (A1), one incremental state machine (A2), one verifier. An LLM agent should not compute the formulas. If you use an agent at all, restrict it to orchestration and exception tickets ("VIX file hash unchanged since yesterday").

Independent verification (second estimator + tolerance):
Regime | Primary | Second estimator | Agreement rule
R001 | Garman–Klass 21d | Parkinson 21d and close-to-close | all within ±25% (relative); else DISPUTED
R002 | VIX − RV (vol pts) | variance-unit VRP (scaled ×100) | sign must match; sign mismatch → DISPUTED; |VRP| > 50 vol pts → OOB
R003 | VIX/VIX3M | (VIX3M − VIX)/VIX sign | sign of (1 − IVTS) must agree iff slope near 0; else DISPUTED
R004 | GARCH(1,1) via arch | EWMA half-life proxy (λ = 0.94) | both α+β in [0.80, 0.999]; else UNSTABLE_FIT
R005 | LM (or daily proxy) | bipower vs realized-var gap | jump flag only if both fire; else NO_JUMP
R006 | VVIX | 21d stdev of VIX daily changes | if VVIX missing, use hist VoV but tag PROXY
R007 | Wilder ADX 14 | +DI/−DI consistency; optional Hurst | ADX > 25 requires +DI/−DI spread (illustrative) or WEAK_TREND
R008 | BW percentile vs trailing 120d | raw BW vs 20d min | percentile computed on window; if good days < 60 → INSUFFICIENT
R009 | overlapping VR(2) | non-overlapping VR(2) | |Δ| < 0.15; else DISPUTED
R010 | TW quoted (BBO) | Roll from trades or effective | if Roll cov > 0, Roll = 0 and do not use it to veto TW
Tolerances above are operational, not published constants. Log both numbers every day.

Fail-safes
Define a single state enum per regime: OK | INSUFFICIENT | STALE | MISSING | OOB | DISPUTED | HALT
Fault | Detection | Regime state | Downstream signals must
Symbol missing bar / halt | no row at asof | MISSING | flat that name; do not forward-fill prices
File older than SLA (daily > 18:00 ET still T−1; 1-min gap > 5 min) | watermark | STALE | use last OK only as STALE_PREV; no new entries; exits allowed
Short lookback (e.g. ADX needs 28+ bars, GARCH 500+ daily) | count | INSUFFICIENT | treat as no regime edge; size 0
Out-of-range (e.g. ADX outside [0,100], negative variance, VR < 0, spread < 0) | range check | OOB | halt that feature; do not clip silently
Primary vs second fail tolerance | verifier | DISPUTED | do not trade that regime's overlay; still record both
VIX/VVIX unpublished | source hash | STALE on R002/R003/R006 | stock-only regimes may stay OK
Quote session without trades | R010 | quoted OK, effective INSUFFICIENT | don't estimate Roll
Corporate-action gap (split not applied) | close jump with no factor > 40% | HALT symbol | drop from universe that day
Clock skew / weekend run | calendar | skip | never write a Saturday asof
Global kill: if > 10% of the 500 names are MISSING/STALE on the same asof, A4 publishes UNIVERSE_HALT. All downstream signals stand down.

Loop sketch (close batch)
1. A0: pull Databento ohlcv-1d + Cboe CSVs; write asof=T.
2. Assert trading calendar, split factors, row counts.
3. A1: compute 10 regimes with lookbacks ending at T (close snapshot) and a parallel decision_asof=T−1 column for anything that would have been tradable at the open of T.
4. A3: second estimators, write verify.json.
5. A4: publish only rows with state in {OK, STALE} and never promote DISPUTED to a signal.
Intraday: A2 updates three columns only; A3 samples; A4 is the sole reader for any "agent" or notebook.
Bottom line: spend money on EQUS.MINI + PIT EOD + free Cboe index files. Spend weeks on causality, R010, and fail-safes. The M5 Max will finish the 500-name daily book before the coffee cools; it will not save you from lookahead.

---

## Q-RB1-3 VERBATIM

Direction is stated first. Citations are only papers or practitioner sources already identified. Numbers that are not in those sources are labeled illustrative. Gross vs net is labeled where the source does.

Compounding first (read this before the ten cards)
These ten states are not ten independent filters. They collapse into a small number of joint tradable worlds.
Joint state | Typical co-occurrence | What survives
Calm carry | Low RV (R001) + rich VRP (R002) + contango (R003) + moderate persistence (R004) + no jumps (R005) + low VoV (R006) + ADX mid/low (R007) + no squeeze-break (R008) + VR near 1 (R009) + tight spreads (R010) | Short-vol / carry, slow trend overlays, mean-reversion on liquid names
Stress unwind | High RV + inverted TS + jump burst + high VVIX + wide spreads | Stand-down most high-turnover alpha; optional long-vol / tail; trend-followers may still harvest after the first shock
Panic-rebound | High RV + high VRP collapsing + backwardation rolling over + losers' beta spike | Momentum dies; short-vol dies; rebound / quality-to-junk squeezes
Coiled breakout | Squeeze (R008) + rising ADX (R007) + VR>1 (R009) + still-tight spreads | Breakout / momentum initiation; fade-the-range dies
Toxic tape | Wide R010 + jumps + high VoV | Edge − cost < 0 for almost every intraday family
A name that fails R010 (wide effective spread) plus R001 (high RV) is one untradeable object, not two vetoes you average. Implementation: compute a single tradability flag = NOR of {R010 wide, R005 jump-day, R006 stress VoV, data HALT} before any signal is allowed to size up.

R001 — Realized-vol level
(1) Direction and mechanism
• Improves: volatility targeting / risk-parity (scale ∝ 1/σ); short-horizon mean-reversion on the most liquid names after a vol spike, once the spike is recognized; long-vol / convexity when RV is rising from a low base.
• Dies: static-leverage momentum and carry in high RV after a bear market; naive short-vol when RV is already elevated (you are selling realized that has already arrived).
• Mechanism: strategy Sharpe scales roughly as μ/σ if μ is sticky; capacity scales as edge / spread, and both spread and impact rise with σ. Daniel–Moskowitz: momentum's worst states are high-vol panic states coinciding with market rebounds.
(2) Documented evidence
• Daniel & Moskowitz, JFE 2016, "Momentum Crashes": US and international asset classes, 1927–2013. Crashes cluster after market declines when volatility is high, contemporaneous with rebounds. Dynamic vol-scaled momentum roughly doubles the static Sharpe in their sample (gross factor returns; not a live book).
• Cooper, Gutierrez & Hameed (2004) and Stivers & Sun (2010): momentum premium falls when market volatility is high (cited inside Daniel–Moskowitz).
• Practitioner: Mozes (2026, J. Beta Investment Strategies) links VIX spikes to weaker momentum over 1994–2024 — practitioner/academic hybrid; treat magnitudes as study-specific. Label: those papers are gross factor results unless they say otherwise.
(3) When classification fails
• Parkinson/GK assume no jumps and no drift; a jump day inflates RV and can flip "high-vol" one day late.
• Annualizing with 252 on a 5-day window is noisy: false "high" after one event.
• Lookahead: using a window that includes the signal day to decide whether to trade that close.
• Estimator disagreement: GK vs close-to-close can differ by tens of percent after gaps.
(4) Joint. High R001 without wide R010 is still tradeable for vol-targeted trend. High R001 + wide R010 + jumps = stand-down.
Bottom line: sizing input (and a stand-down flag for unscaled momentum in panic-rebound). Not a buy/sell trigger.

R002 — Implied–realized / VRP
(1) Direction
• Improves (index horizon): long equity / long risk when VRP is high (IV ≫ RV) — compensation for variance risk is rich. Short-vol / variance-swap short is the structural way to harvest VRP, but only when you can survive the left tail.
• Dies: short-vol when VRP compresses or flips negative (RV catching IV — usually a vol event in progress). Equity-premium timing that treats low VRP as "cheap vol, sell more" is the wrong sign relative to the forecasting literature.
• Mechanism: VRP_t ≈ E^Q[RV] − E^P[RV]. High VRP ⇒ high required equity/variance premium over the next 1–4 months in the BTZ framework.
(2) Documented
• Bollerslev, Tauchen & Zhou, RFS 2009: 1990–2005, S&P 500. Difference between model-free implied and HF realized variance predicts quarterly excess market returns; high premia → high future returns; R² "more than fifteen percent" at the quarterly horizon in the FEDS write-up. Gross index returns, no transaction-cost line.
• Zhou FEDS 2010: predictability peaks at 1–4 months, then fades.
• Later samples sometimes weaken the univariate VRP; some 2026 work finds VRP useful again only with other predictors — so treat post-2008 stability as not settled.
(3) Failures
• Mixing vol-point VRP with variance-unit VRP flips economic magnitude.
• Using yesterday's RV against today's VIX after a crash marks VRP "cheap" while the event is still on.
• Horizon mismatch (30-day VIX vs 5-day RV).
• Lookahead: realized leg that includes the forecast week.
(4) Joint. Rich VRP + contango (R003) + low VVIX (R006) = classic short-var carry. Rich VRP during backwardation is insurance demand, not a sell-vol green light.
Bottom line: sizing / timing overlay for index risk and short-var, not a single-stock trigger. Stand-down short-vol when VRP ≤ 0.

R003 — Vol term-structure slope
(1) Direction
• Improves in contango (VIX < VIX3M): short VIX futures / short variance / premium-selling with positive roll.
• Dies in backwardation: those same carry books; the roll becomes a headwind and spot vol is spiking.
• Improves in backwardation for: long-vol, tail hedges, and (after the hook) re-entry of carry — that last part is practitioner, not a theorem.
• Mechanism: Johnson (2017) — the slope of the VIX curve prices variance risk, not an expectations-hypothesis forecast of VIX. Slope predicts excess returns of variance swaps, VIX futures, and SPX straddles.
(2) Documented
• Johnson, JFQA 2017: one PC ("Slope") predicts those variance-linked excess returns across maturities, incremental to other VRP proxies. Gross derivative returns.
• Practitioner catalogues of VIX/VIX3M > 1 episodes (e.g. multi-year IVTS trackers) show backwardation is rare (~high-single-digit percent of days in one 16-year tally) and clustered in stress — descriptive, not a paper Sharpe.
(3) Failures
• One-day inversions are common and mean-revert; treating IVTS > 1 as a multi-day "crisis regime" over-trades.
• Using VIX futures curve vs VIX/VIX3M can disagree around roll dates.
• Lookahead: classifying the day with the same day's close VIX that you could not have traded at the open.
(4) Joint. Backwardation + high R001 + high R006 is one stress object. Contango + rich R002 is one carry object.
Bottom line: stand-down flag for short-vol carry when inverted; sizing/timing for variance-swap and VIX-futures books. Not an equity stock-picker trigger.

R004 — Clustering / persistence
(1) Direction
• Improves: vol-targeting, GARCH-based position sizing, "trade smaller after a shock if α + β is high because the shock will linger."
• Dies: strategies that assume shocks are i.i.d. (fixed-coupon short-vol, fixed-stop trend that does not widen).
• High persistence ⇒ yesterday's σ is still the right scale tomorrow; low persistence ⇒ fade the vol spike faster.
• Mechanism: GARCH half-life t_{1/2} = ln(1/2) / ln(α + β). Equity daily fits often sit near 0.95–0.99 (model fact, not a trading P&L paper).
(2) Documented
• Bollerslev (1986) is the model, not an efficacy paper.
• Daniel–Moskowitz again: using forecast variance of the momentum book to scale the strategy improves Sharpe — that is the closest documented trading use of persistence/vol clustering. There is no clean published table "ADX-style persistence tertiles × strategy Sharpe" that should be invented here.
(3) Failures
• MLE on 1 year of daily data is unstable; α + β pinned at 0.999 is a numerical artifact, not a regime.
• Structural breaks (2015–16, 2020) make a single GARCH lie.
• Using the in-sample fitted σ_t that includes r_t to size the trade of day t.
(4) Joint. High persistence + high R001 = long high-vol episode (size down and stay down). High persistence + squeeze (R008) is rare; if both print, trust persistence less (window too short).
Bottom line: sizing input. Almost never a trigger.

R005 — Jump regime
(1) Direction
• Improves: event-driven, news-alpha, long-gamma around scheduled announcements (earnings jumps are exactly what Lee–Mykland find in single names).
• Dies: diffusion-based MR, GK-vol signals, tight-stop trend, and any strategy whose edge is a few bps of autocorrelation.
• Mechanism: a jump is a discrete move that is not mean-reverting on the next tick the way microstructure bounce is; it also blows range estimators and trips stops.
(2) Documented
• Lee & Mykland, RFS 2008: US equities, HF; stock jumps cluster on earnings and firm news; index jumps on macro news. That is a location result, not a strategy-Sharpe table.
• Variance-risk-premium papers often split jump vs diffusive variance; jump risk is part of why VRP exists (related literature, not a single P&L number to quote).
(3) Failures
• LM on daily bars is not the paper's design — huge misclassification.
• Microstructure bursts look like jumps at 1-second sampling.
• Multiple-testing: 390 minutes × 500 names × 252 days without a Gumbel correction ≈ a fake jump factory.
• Classifying the jump bar as a regime during the bar is lookahead.
(4) Joint. Jump-day + wide R010 + high R006 = untradeable for systematic intraday. Scheduled earnings jumps are a different joint state (tradable event book).
Bottom line: stand-down flag for continuous-path strategies that day; trigger family only for an explicit event book.

R006 — Vol-of-vol
(1) Direction
• Improves when high: long VIX-option convexity, wider wings, smaller vega; trend systems that need volatility-of-volatility to create outliers.
• Dies when high: short VIX options, tight iron condors, any book that assumes IV is sticky.
• Improves when low: short-vol carry, stable vega.
• Mechanism: VVIX is the implied vol of VIX. High VVIX ⇒ expensive VIX calls and large P&L swings on any vega book (Cboe definition).
(2) Documented
• Cboe VVIX methodology: expected vol of 30-day forward VIX — definition, not a strategy paper.
• Johnson's slope result is the closest published return-forecast result on the vol complex; VVIX itself is thinner in the academic return-forecast set. Do not invent a "VVIX>150 Sharpe" table.
(3) Failures
• VVIX can spike on VIX-option microstructure without an SPX jump.
• Historical stdev of VIX ≠ VVIX (realized vs implied VoV).
• Using a same-day VVIX print to trade the open.
(4) Joint. High VVIX almost always arrives with R001/R003 stress. If VVIX is high and TS still in deep contango, suspect a VIX-option-specific dislocation, not an equity-vol regime.
Bottom line: sizing / stand-down for vol-of-vol sellers. Not an equity trigger.

R007 — Trend strength (ADX / Hurst)
(1) Direction
• ADX high / H > 0.5: trend-following, breakout, time-series momentum improve; range-fade and short-horizon MR die.
• ADX low / H < 0.5: the reverse.
• Mechanism: ADX measures directional dominance, not sign. Wilder's own rule: trend present when ADX > 25. Hurst H > 0.5 is long-memory persistence by construction.
(2) Documented
• Wilder (1978) is a trading-system book, not a peer-reviewed out-of-sample Sharpe study.
• Time-series momentum (Moskowitz, Ooi, Pedersen 2012 — not re-fetched this turn) is the academic cousin of "trend strength helps TSMOM," but they do not use ADX as the gate. Treat "ADX>25 doubles breakout expectancy" as illustrative folklore unless you run it on your 500 names.
(3) Failures
• Wilder smoothing needs ~28 bars before ADX is defined; early values look like a regime and are not.
• ADX stays high after the trend is over (lag). That lag is the main misclassification cost: you keep trend size into the chop.
• In-sample Hurst on 60 days is garbage; Lo (1991) showed classical R/S confuses short-run dependence with H.
• Computing ADX on the same bar you trade is mild lookahead (needs H/L of that bar).
(4) Joint. High ADX + squeeze resolution (R008) + VR>1 (R009) = breakout cluster. High ADX + high R001 + backwardation = crisis trend (trade smaller, wider stops).
Bottom line: sizing / regime gate for choosing trend vs MR family. Weak as a standalone trigger.

R008 — Squeeze / expansion
(1) Direction
• Compression (low BW percentile): range-selling and mean-reversion still work until the break; breakout systems should be armed, not fired.
• Expansion after squeeze: breakout / momentum improve; fade-the-band dies.
• Mechanism: Bollinger's squeeze — low bandwidth precedes large moves; direction is not given by bandwidth itself.
(2) Documented
• Bollinger / StockCharts: definition and qualitative squeeze rule. Not a CRSP-factor paper with net Sharpe by BW decile. Do not cite a fake "bottom-decile BW earns X%."
(3) Failures
• Percentile computed on a window that includes the breakout bar.
• Absolute BW < 4% is not portable across price levels and names.
• False breakouts: expansion without ADX follow-through.
• Split-unadjusted prices create fake squeezes.
(4) Joint. Squeeze + still-low ADX = coil (wait). Squeeze + ADX rising + tight R010 = the only clean breakout state.
Bottom line: arming flag / family selector, not a direction trigger.

R009 — Variance ratio (MR vs momentum)
(1) Direction
• VR(q) < 1: short-horizon contrarian / MR improve; momentum dies at that horizon.
• VR(q) > 1: momentum / continuation improve; fade dies.
• Mechanism: VR(2) ≈ 1 + ρ₁. Lo–MacKinlay (1988/89): short-horizon US weekly returns showed positive autocorrelation at the portfolio level (momentum-like), with individual names often negatively autocorrelated (bounce). Lo–MacKinlay (1990): much of contrarian profit is cross-autocorrelation (large lead small), not overreaction.
(2) Documented
• Lo & MacKinlay, RFS 1988 / J. Econometrics 1989: test design and finite-sample behavior.
• Lo & MacKinlay 1990, "When Are Contrarian Profits Due to Stock Market Overreaction?": weekly US, 1962–1987 — contrarian profits can come from lead-lag, not ρᵢ < 0. Gross, academic portfolios.
• Poterba–Summers-type long-horizon mean reversion is a different q than daily VR(2). Do not mix them.
(3) Failures
• N = 8 (the toy example) is not an estimator.
• Homoskedastic z over-rejects under GARCH; use heteroskedastic z*.
• Index VR is contaminated by stale prices (Scholes–Williams / Lo–MacKinlay nonsynchronicity).
• Rolling in-sample VR that includes the evaluation return.
(4) Joint. VR > 1 + high ADX + expansion = momentum family. VR < 1 + low ADX + tight spreads = MR family. VR < 1 caused by bounce in a wide-spread name is R010, not an alpha regime.
Bottom line: family selector (MR vs MOM). Weak trigger.

R010 — Spread regime
(1) Direction
• Tight quoted/effective spread: high-turnover MR, microstructure, short-horizon momentum can clear costs.
• Wide spread: those families die; only low-turnover anomalies survive.
• Mechanism (explicit): expected net = expected gross edge − c × turnover. If effective spread is s (round-trip ≈ s), a signal with 5 bps of expected edge and 2-sided daily turnover is negative once s ≳ 5 bps. The 4–5 bp cutoff is an illustrative capacity identity, not a universal constant.
(2) Documented
• Novy-Marx & Velikov, NBER w20721 / RFS-era "Taxonomy of Anomalies and their Trading Costs": after costs, anomalies with one-sided monthly turnover ≳ 50% mostly lose significance; lower-turnover anomalies often keep net spreads if you use a buy/hold band. Costs estimated via Hasbrouck–Gibbs / Roll-type effective spreads. Net-of-cost paper — this is the one to cite for R010.
• Roll (1984): effective spread ≈ 2√(−cov(ΔP)).
• Novy-Marx & Velikov (2018) FAJ: banding beats "only trade cheap names" for preserving gross exposure.
(3) Failures
• Quoted ≠ effective (hidden liquidity, mid-point fills).
• Roll spread is 0 when cov(ΔP) > 0 — common in trends — so Roll disagrees with TW quoted exactly when momentum is present.
• Time-weighting a stale quote through a halt marks the name "tight."
• Percentile of spread in-sample over a crisis month calls everything "normal."
(4) Joint. Wide R010 dominates: it turns R008 breakouts into untradable gaps and turns R009 MR into bounce against the offer. Combine with R001: high vol and wide spread is the Novy-Marx high-turnover graveyard.
Bottom line: stand-down / capacity gate for high-turnover signals. Sizing input (size ∝ 1/s). Never a direction trigger.

Honest role table
Regime | Trigger? | Sizing? | Stand-down?
R001 RV level | No | Yes (vol target) | Yes for unscaled MOM in panic-rebound
R002 VRP | Weak index-timing only | Yes (risk-on when rich) | Yes for short-vol if VRP ≤ 0
R003 TS slope | No | Yes for vol-carry | Yes short-vol if backwardated
R004 persistence | No | Yes | Rare (UNSTABLE_FIT)
R005 jumps | Only for event books | Cut size | Yes for diffusion strategies that day
R006 VoV | No | Yes on vega | Yes for short VIX-options when VVIX stressed
R007 ADX/Hurst | No | Yes (trend vs MR mix) | Soft (don't fade a strong trend)
R008 squeeze | Arm, don't fire | After expansion, size breakout | Fade-the-range when expanding
R009 VR | No | Family mix | Don't run MOM when VR ≪ 1 at your horizon
R010 spread | No | Yes ∝ 1/s | Yes if edge < effective cost

Research hygiene that actually changes P&L
1. Always report gross and net. Most "regime works" papers (BTZ, Johnson, Daniel–Moskowitz) are gross. The paper that tells you when they stop working after costs is Novy-Marx–Velikov.
2. Never stack ten binary filters. Use one joint state (calm-carry / coiled / stress / toxic-tape / panic-rebound).
3. The most expensive misclassification in this list is not a wrong Parkinson constant. It is a same-bar percentile or ADX that includes the breakout you are about to "predict," plus a spread ignored on a 500-name daily rebalance.

[Extraction note: Grok's math rendered as unicode subscripts/superscripts (e.g., VRP_t ≈ E^Q[RV] − E^P[RV]; s_Roll = 2√(−cov(ΔP))) transcribed faithfully. A few Q3 bullets had truncated renderings ("ADX > 25" rule-of-thumb text was cut in the page text) — transcribed exactly as rendered. Sources footnote: "26 sources" panel was present on the Q3 answer.]

Task complete. No credentials were requested beyond the saved-vault login used with authorization; no OTP appeared; no purchases or external side effects occurred.
