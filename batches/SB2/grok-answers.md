# SB2 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials (fresh email+password sign-in; Cloudflare human-check completed)
- Date: 2026-09-10
- Batch: SB2 — Cost/vol infrastructure + session patterns (S011, S013, S021, S027, S032, S042, S043, S063, S066, S083)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.

---

## Q-SB2-1 — formulas + worked example (verbatim)

All formulas below follow the original published definitions. Parameter choices and every numerical example use illustrative synthetic data constructed only for this chapter; they are not market observations.

1. Amihud illiquidity ratio
Source (documented). Yakov Amihud, "Illiquidity and Stock Returns: Cross-Section and Time-Series Effects," Journal of Financial Markets 5 (2002): 31–56. The construction is the average daily price impact per dollar of volume. Practitioners often scale by 10^6 so the number is readable; Amihud used that scaling in the original tables.
Formula. For stock i over a window of D days with usable data,
ILLIQ_i = (1/D) Σ_{t=1}^{D} |r_{i,t}| / DVOL_{i,t},
ILLIQ_i^{(6)} = 10^6 · ILLIQ_i
where
• r_{i,t} = (P_{i,t} − P_{i,t−1}) / P_{i,t−1} is the simple close-to-close return,
• DVOL_{i,t} = P_{i,t} × V_{i,t} is dollar volume (close times shares traded),
• days with zero volume are dropped.
Practical ranges (documented practice, not a theorem). Annual windows (D ≈ 250) are Amihud's original frequency; monthly and quarterly averages are also standard. Daily ratios are extremely small, so the 10^6 scale is the usual reporting convention.
Worked example (illustrative 10-day OHLCV). Synthetic closes and share volumes (prices in dollars, volume in shares):
Day | Close P_t | Volume V_t | r_t | DVOL_t = P_t·V_t | |r_t| / DVOL_t
0 | 100.00 | — | — | — | —
1 | 101.20 | 1,200,000 | 0.012000 | 121,440,000 | 9.8814 × 10^−11
2 | 100.40 | 980,000 | −0.007905 | 98,392,000 | 8.0342 × 10^−11
3 | 102.10 | 1,450,000 | 0.016932 | 148,045,000 | 1.1437 × 10^−10
4 | 101.80 | 1,100,000 | −0.002938 | 111,980,000 | 2.6237 × 10^−11
5 | 103.50 | 1,600,000 | 0.016699 | 165,600,000 | 1.0084 × 10^−10
6 | 102.20 | 900,000 | −0.012560 | 91,980,000 | 1.3655 × 10^−10
7 | 104.00 | 1,350,000 | 0.017613 | 140,400,000 | 1.2545 × 10^−10
8 | 103.10 | 1,050,000 | −0.008654 | 108,255,000 | 7.9941 × 10^−11
9 | 105.40 | 1,700,000 | 0.022308 | 179,180,000 | 1.2449 × 10^−10
10 | 104.70 | 1,250,000 | −0.006641 | 130,875,000 | 5.0743 × 10^−11
Sum of the 10 daily ratios = 9.1953 × 10^−10. ILLIQ = 9.1953 × 10^−11. Scaled: ILLIQ^{(6)} = 9.1953 × 10^−5.
Interpretation of this toy number: about 9.2 × 10^−5 percent price move per million dollars of volume — a liquid name on this sample. Real-market magnitudes differ by asset class and should be taken from the paper or a replication, not from this table.
[Capture note: the answer's stated Amihud sum (9.1953 × 10^−10) differs slightly from what its own table rows sum to (9.3778 × 10^−10); reproduced above exactly as rendered.]

2. Corwin–Schultz high–low spread estimator
Source (documented). Shane A. Corwin and Paul Schultz, "A Simple Way to Estimate Bid-Ask Spreads from Daily High and Low Prices," Journal of Finance 67, no. 2 (2012): 719–760. DOI: 10.1111/j.1540-6261.2012.01729.x.
The high–low range mixes variance (which scales with time) and the spread (which does not). Two overlapping windows identify both.
Formulas (pair of consecutive days t and t+1).
β = [ln(H_t / L_t)]² + [ln(H_{t+1} / L_{t+1})]²
γ = [ln(H_{t,t+1} / L_{t,t+1})]², H_{t,t+1} = max(H_t, H_{t+1}), L_{t,t+1} = min(L_t, L_{t+1})
α = (√(2β) − √β) / (3 − 2√2) − √(γ / (3 − 2√2))
S = 2(e^α − 1) / (1 + e^α)
S is the estimated proportional bid–ask spread. Negative draws are common on quiet pairs; the paper's SAS code and most replications set S ← max(S, 0) when a non-negative estimator is required.
Practical ranges. One estimate per overlapping two-day pair; then average over a month or a year. Overnight adjustments (when the next-day high/low must be "brought back" across a large close-to-open gap) are described in the paper's appendix; they are omitted here.
Worked example (illustrative; first two days of a 10-day high–low series).
Day 1: High 102.40, Low 99.80. Day 2: High 101.90, Low 99.20.
ln(H_1 / L_1) = ln(102.40 / 99.80) = ln(1.026052) = 0.025718
ln(H_2 / L_2) = ln(101.90 / 99.20) = ln(1.027218) = 0.026854
β = 0.025718² + 0.026854² = 0.0006614 + 0.0007211 = 0.0013825
Two-day high = 102.40, two-day low = 99.20: ln(102.40 / 99.20) = ln(1.032258) = 0.031749, γ = 0.0010080
Constant k = 3 − 2√2 = 0.171573.
√(2β) = √0.0027650 = 0.052583, √β = 0.037182
(√(2β) − √β) / k = 0.015401 / 0.171573 = 0.089763
√(γ / k) = √0.005874 = 0.076643
α = 0.089763 − 0.076643 = 0.013120
e^α = 1.013206, S = 2(0.013206) / 2.013206 = 0.01312
So the pair-(1,2) spread estimate is 1.312%. Repeating the same algebra on each overlapping pair and averaging (with optional floor at zero) gives the sample Corwin–Schultz series. The remaining eight days of highs/lows would be processed identically; they are omitted here only to keep the arithmetic visible.

3. Crabel opening-range breakout (ORB)
Source (documented). Toby Crabel, Day Trading with Short Term Price Patterns and Opening Range Breakout (Tradest Press, 1990). The book defines the opening range as the high and low of a short window after the cash open and treats a trade through that high or low as the breakout. Common documented window lengths in later practice are 5, 15, 30, and 60 minutes; Crabel's own studies used short opening intervals (often discussed as the first 10–30 minutes). NR4 / NR7 (narrowest range of the last 4 or 7 daily bars) are the contraction filters he paired with ORB.
There is no single closed-form "Crabel equation." The operational definition is:
Let the session open at t_0. Fix a window length m minutes (illustrative choice below: m = 30).
ORH = max_{t ∈ [t_0, t_0 + m]} H_t, ORL = min_{t ∈ [t_0, t_0 + m]} L_t
Trigger (stop-style, as in the book's ORB):
• long if price trades ≥ ORH after the window closes,
• short if price trades ≤ ORL after the window closes.
Optional stretch (later practitioner variant, not required by the 1990 text): enter at ORH + k·R̄ where R̄ is an n-day average range and k is a fraction such as 0.8. Crabel later described a percentage-of-average-range entry as a simplification.
Worked example (illustrative 30-minute opening window on 5-minute bars). Six bars, 09:30–10:00 (US cash equity open convention used only as a clock label).
Bar end 09:35: High 50.40, Low 50.05, Close 50.22
09:40: 50.55, 50.18, 50.50
09:45: 50.48, 50.12, 50.20
09:50: 50.62, 50.28, 50.58
09:55: 50.70, 50.35, 50.66
10:00: 50.58, 50.30, 50.42
ORH = max(50.40, 50.55, 50.48, 50.62, 50.70, 50.58) = 50.70
ORL = min(50.05, 50.18, 50.12, 50.28, 50.35, 50.30) = 50.05
Range width = 0.65.
Post-window 5-minute bars (illustrative continuation):
10:05: High 50.68, Low 50.40, Close 50.61 — still inside
10:10: High 50.81, Low 50.55, Close 50.78 — high 50.81 ≥ 50.70 → long ORB trigger
First trigger time: 10:10 bar. A stop-entry implementation fills at 50.70 (or at the trade that first prints through 50.70). A close-through rule would wait for a bar close above 50.70; here the 10:10 close 50.78 also qualifies.
No claim is made that this window or fill convention matches any particular Crabel table; m = 30 is an illustrative modern default.

4. RSI-2 mean reversion (Connors)
Sources (documented).
• J. Welles Wilder Jr., New Concepts in Technical Trading Systems (Trend Research, 1978) — original RSI.
• Larry Connors and Cesar Alvarez, Short Term Trading Strategies That Work (TradingMarkets, 2008) and Connors' later notes: 2-period RSI, buy when RSI-2 < 10 (tighter: < 5) only if price is above the 200-day SMA; exit when close > 5-day SMA. Sell-side mirror uses 90 / 95 and price below the 200-day SMA.
Wilder RSI with lookback n = 2.
Δ_t = C_t − C_{t−1}, G_t = max(Δ_t, 0), L_t = max(−Δ_t, 0)
Seed (first n changes): Ḡ_n = (1/n) Σ G, L̄_n = (1/n) Σ L. Then Wilder smoothing: Ḡ_t = ((n−1)Ḡ_{t−1} + G_t) / n, L̄_t = ((n−1)L̄_{t−1} + L_t) / n
RS_t = Ḡ_t / L̄_t, RSI_t = 100 − 100 / (1 + RS_t)
If L̄_t = 0 and Ḡ_t > 0, RSI = 100.
Practical parameters (Connors, documented as his tested set). n = 2; long threshold 10 or 5; short threshold 90 or 95; trend filter SMA-200; exit SMA-5. Those thresholds are Connors' research choices, not part of Wilder's definition.
Worked example (illustrative 10 closes; compute RSI-2 at the last bar).
Closes: C = [100.00, 101.50, 100.80, 102.20, 101.40, 100.60, 99.50, 100.10, 99.20, 98.40, 99.00] (11 prices → 10 changes; last value is the evaluation close.)
Changes Δ: +1.50, −0.70, +1.40, −0.80, −0.80, −1.10, +0.60, −0.90, −0.80, +0.60
Gains G: 1.50, 0, 1.40, 0, 0, 0, 0.60, 0, 0, 0.60
Losses L: 0, 0.70, 0, 0.80, 0.80, 1.10, 0, 0.90, 0.80, 0
Seed on first 2 changes: Ḡ_2 = (1.50 + 0) / 2 = 0.75, L̄_2 = (0 + 0.70) / 2 = 0.35.
Wilder updates (n = 2, so each step is 0.5 × prev + 0.5 × new):
t | G | L | Ḡ | L̄ | RS | RSI-2
2 | 0 | 0.70 | 0.7500 | 0.3500 | 2.1429 | 68.18
3 | 1.40 | 0 | 1.0750 | 0.1750 | 6.1429 | 86.00
4 | 0 | 0.80 | 0.5375 | 0.4875 | 1.1026 | 52.44
5 | 0 | 0.80 | 0.2688 | 0.6438 | 0.4175 | 29.45
6 | 0 | 1.10 | 0.1344 | 0.8719 | 0.1541 | 13.35
7 | 0.60 | 0 | 0.3672 | 0.4359 | 0.8424 | 45.72
8 | 0 | 0.90 | 0.1836 | 0.6680 | 0.2749 | 21.56
9 | 0 | 0.80 | 0.0918 | 0.7340 | 0.1251 | 11.12
10 | 0.60 | 0 | 0.3459 | 0.3670 | 0.9425 | 48.52
At bar 9, RSI-2 = 11.12, which is not below the illustrative Connors long threshold of 10. At bar 6 it was 13.35, also above 10. On this path the strict < 10 long signal never fires; a < 15 researcher threshold would have fired at bar 6 and bar 9. That is the point of showing the arithmetic: the 2-period oscillator reaches the teens quickly, but Connors' published 5 / 10 cutoffs are rare by design.
SMA-200 and SMA-5 cannot be computed from 10 closes; they are applied on a longer price history in any live rule.

5. HAR realized-volatility forecast (Corsi)
Source (documented). Fulvio Corsi, "A Simple Approximate Long-Memory Model of Realized Volatility," Journal of Financial Econometrics 7, no. 2 (2009): 174–196. DOI: 10.1093/jjfinec/nbp001.
Daily realized variance RV_t is the sum of squared intraday returns over day t. The three-component HAR is
RV_{t+1} = β_0 + β_d RV_t + β_w RV_t^{(w)} + β_m RV_t^{(m)} + ε_{t+1}
RV_t^{(w)} = (1/5) Σ_{i=0}^{4} RV_{t−i}, RV_t^{(m)} = (1/22) Σ_{i=0}^{21} RV_{t−i}
(Corsi also writes the model in realized volatility √RV or in logs; the linear-in-RV OLS form above is the textbook specification reproduced in the highfrequency R package help.)
Practical ranges. Daily / weekly (5) / monthly (22 trading days) is the canonical triple. Estimation is OLS on a rolling or expanding sample of several years. One-day-ahead RV̂_{t+1} is the fitted right-hand side.
Worked example (illustrative 22-day RV series; coefficients are also illustrative).
Daily RV_t (variance units, e.g. squared log-return sums; not annualized vol):
0.000121, 0.000098, 0.000142, 0.000110, 0.000087, 0.000156, 0.000134, 0.000101, 0.000119, 0.000163, 0.000148, 0.000092, 0.000125, 0.000171, 0.000139, 0.000108, 0.000094, 0.000127, 0.000155, 0.000118, 0.000103, 0.000144
Last day is t = 22: RV_t = 0.000144.
Weekly component (last 5 days: 0.000127, 0.000155, 0.000118, 0.000103, 0.000144):
RV_t^{(w)} = (0.000127 + 0.000155 + 0.000118 + 0.000103 + 0.000144) / 5 = 0.0001294
Monthly component (all 22 values): Sum = 0.000121 + 0.000098 + ⋯ + 0.000144 = 0.002755.
RV_t^{(m)} = 0.002755 / 22 = 0.00012523
Illustrative OLS coefficients (a plausible HAR shape, not estimated from these 22 points — 22 observations cannot identify four coefficients stably; live work uses years of RV):
β_0 = 0.000020, β_d = 0.35, β_w = 0.30, β_m = 0.25
One-day-ahead forecast:
RV̂_{t+1} = 0.000020 + 0.35 × 0.000144 + 0.30 × 0.0001294 + 0.25 × 0.00012523
= 0.000020 + 0.00005040 + 0.00003882 + 0.00003131 = 0.00014053
Implied 1-day realized-vol forecast √0.00014053 ≈ 0.01185 (about 1.185% daily). Annualization × √252 would be an extra convention and is not part of Corsi's one-day HAR equation.
To estimate β for real work, regress RV_{s+1} on {1, RV_s, RV_s^{(w)}, RV_s^{(m)}} for s in a multi-year sample; then plug the latest components into the fitted line exactly as above.

Label summary
Object | Status
Amihud (2002) ILLIQ definition and 10^6 scale | documented
Corwin–Schultz (2012) β, γ, α, S | documented
Crabel (1990) OR high/low + NR4/NR7 filters; 5/15/30/60-min windows in later practice | documented book + later practice
Wilder RSI; Connors 2 / 5–10 / 90–95 / SMA-200 / SMA-5 | documented
Corsi (2009) HAR daily–weekly–monthly | documented
All OHLCV, 5-min bars, 10 closes, 22 RV values, and the HAR β vector | illustrative estimates only

---

## Q-SB2-2 — local build + buy vs build (verbatim)

Assumption: overnight research batch after the cash close, not a live SIP scanner. On that assumption the M5 Max is wildly over-provisioned; data quality and corporate-actions hygiene dominate cost, not RAM or cores.

All dollar figures below are vendor list prices as of mid-2026, individual / non-redistribution use. Verify on the vendor site before you pay — these plans move.

1. Cheapest adequate data
Two constraints from the feature list:
• Amihud and RVOL need consolidated dollar volume, not IEX-only prints. IEX is ~2–3% of tape; using it for DVOL systematically understates volume and inflates ILLIQ, especially off the mega-caps.
• Tick / volume / dollar / imbalance bars cannot be built from 1-minute OHLCV. Those clocks need trades (and imbalance bars need auction/imbalance messages). 1-minute data only gives time bars plus crude "volume-bucket" approximations.

Recommended buy (research-grade, post-close)
Layer | Vendor / plan | Indicative $$ | What you actually get | Fit
Daily OHLCV + adj + splits/divs | Tiingo Power | $30/mo ($300/yr) | Composite EOD, 30+ yr, splits/divs, 10k req/hr | Best cheap daily tape for Amihud / RSI-2 / HAR on daily RV
1-min bars, full universe | Massive/Polygon Stocks Starter | $29/mo | Unlimited REST + flat files, 15-min delayed, minute aggs, ~5 yr hist, all US tickers | Adequate for Corwin, range-RV, RVOL, IBS, ORB after 16:15 ET
Optional upgrade | Polygon Developer | $79/mo | Same delay, plus trades + second aggs, 10 yr | Needed if you later build true volume/dollar bars
Optional live SIP | Polygon Advanced or Alpaca Algo Trader Plus | $199 / $99 | Full CTA+UTP | Only if the pipeline becomes same-session

Cheapest adequate stack for this chapter: ~$59/mo (Tiingo $30 + Polygon Starter $29). Polygon Starter alone can also supply daily bars; Tiingo is the cheaper, cleaner EOD/corporate-action cross-check.

Do not use as the Amihud volume source: Alpaca free IEX, Tiingo IEX intraday, HF Data Library post-Mar-2022 (IEX). Fine for prototyping RSI-2; wrong for price-impact.

One-time history dump alternative: FirstRate Data sells split-adjusted 1-min history as a bulk file (not a streaming API). Useful for a 10–20 year backfill; you still need a cheap daily vendor going forward.

Databento: metered historical OHLCV-1m is often cheap for a one-shot backfill; live Standard is $199/mo — overkill for a nightly 500-name batch.

Precomputed analytics (Amihud, HAR, Corwin) from vendors: skip. No serious vendor sells your exact window/scaling/overnight-adjustment choices, and the formulas are a few dozen lines of Polars.

2. Expected compute — nightly refresh, Polars on M5 Max
Universe math (RTH only, 6.5 h = 390 minutes):
• 500 names × 390 bars × 1 new day ≈ 195k new 1-min rows/day
• Feature set on that increment: group-by symbol, a few rolling windows (22 / 252), one 2-day pair for Corwin, one OLS or expanding HAR.

Illustrative timings on an M-series 128 GB machine (order-of-magnitude, not a benchmark paper):
Step | Bound | Illustrative wall time
Pull 500 daily bars + 500×390 minute bars (Polygon flat file or batched REST) | network | 1–8 min (flat file is the fast path)
Decode Parquet → Polars | disk/CPU | < 10 s
Daily features (Amihud day-ratio, RSI-2, IBS, RVOL, Corwin pair, HAR components) | CPU | 2–15 s
Intraday RV = (Σ r²_{t,i}) per symbol-day from 1-min log returns | CPU | 1–5 s
Rebuild 60-day panel joins + write Parquet | disk | 5–20 s
Total compute after data is local | | well under 1 minute
Total including download | | ~5–15 minutes typical

HAR OLS on a 2–5 year daily RV panel for 500 names is still seconds in Polars/numpy; you are not fitting 500 separate high-frequency models.

The M5 Max does not change this story. A $600 Mini would also finish the batch before you pour coffee. The 128 GB is insurance for joining 60 days of minutes in RAM, not a requirement.

3. RAM and disk — 60 days of 1-min bars, 500 symbols
Row count
• RTH only: 500 × 60 × 390 = 11.7 million bars
• Session 4:00–20:00 ET (16 h): 500 × 60 × 960 = 28.8 million bars

Disk (illustrative, zstd Parquet, partitioned by date or symbol)
Schema | RTH 60d | Extended 60d
1-min OHLCV + trade count (7–8 cols) | ~200–400 MB | ~0.5–1.0 GB
Same + VWAP + dollar volume | ~300–600 MB | ~0.8–1.5 GB
Daily feature store (500 × 60, wide) | < 20 MB | same

Raw CSV would be 5–8× larger; do not store CSV.

RAM
Unpacked Arrow/Polars for 12M rows × ~10 numeric columns is on the order of 0.7–2 GB. Even the 29M-row extended panel is ~2–5 GB. You can hold the whole 60-day cube, a second copy for joins, and a 5-year daily panel simultaneously and still have ~110 GB free.

Tick / information bars (if you later buy trades): 500 liquid names × 60 days of SIP prints is tens of GB, not hundreds, if you keep only trades not quotes. Quotes/MBP are a different product and will blow past "cheap."

4. Engineering hours (one experienced Python/Polars person)
Milestone | Illustrative hours
Vendor auth, symbol master, split/div calendar, survivorship list of 500 | 8–16
Ingest + Parquet lake (daily + 1-min, partitioned, idempotent nightly job) | 12–20
Feature lib: Amihud, Corwin–Schultz (incl. overnight high/low adjust), RSI-2, IBS, RVOL, Parkinson/GK/RS range-vol, 1-min RV, HAR-RV 1-day | 16–28
Tests vs the worked numerical examples from the previous chapter + a handful of known tickers | 8–12
Scheduler, data-quality gates (zero volume, halted minutes, unadjusted jumps), docs | 8–12
v1 research pipeline (no tick bars, no live) | ~50–90 h
True volume / dollar / imbalance bars from trades + auction imbalance | +40–80 h and a $79–$199 data tier
Point-in-time membership, delistings, CRSP-style PERMNO mapping | +20–40 h (or buy Norgate)

A "weekend hack" that ignores adjustments will look done in 15 hours and then silently corrupt Amihud and HAR at every split.

5. Buy vs build
Buy the bars. Build the analytics. Do not buy precomputed factors.
Piece | Verdict | Why
Daily OHLCV + adjustments | Buy (Tiingo $30 or Polygon daily) | Adjustment mistakes dominate any "edge" in ILLIQ / HAR
1-minute OHLCV | Buy (Polygon Starter $29) | Rebuilding a SIP minute tape is not a home project
Trades / second bars | Buy only when you start information-clock bars | Polygon Developer $79 or Databento metered
Amihud, Corwin, RSI-2, IBS, RVOL, range-RV, HAR | Build | Formulas are public; your lookbacks and overnight conventions will not match any vendor pack
Tick / volume / dollar / imbalance bars | Build from purchased trades, do not fake them from 1-min | 1-min resampling is not an information clock
Polygon/Tiingo/Alpaca "technical indicators" endpoints | Ignore | Black-box RSI/SMA; you already specified Wilder/Connors math
Live SIP ($99–$199) | Do not buy yet | Nightly research does not need it; add when a signal must fire before 16:00

Do not build: exchange connectivity, SIP entitlement, quote tape, or your own corporate-action engine in v1.

Architecture that matches the hardware
vendor REST/flat files → ~/data/eq/{daily,min1}/date=YYYY-MM-DD/*.parquet (60-day hot + yearly cold) → polars lazy scans, partitioned → features/daily.parquet (ILLIQ, CS spread, RSI2, IBS, RVOL, RV, HAR hat) + features/intraday.parquet (OR levels, 1-min RV pieces)

Run the job at 16:20 ET (Polygon Starter is 15-minute delayed, so the last RTH bar is complete). Keep 60 days of minutes on the internal SSD; roll older minutes to an external disk or delete. Daily history is tiny — keep 10+ years.

M5 Max-specific notes
• Polars on Apple Silicon is fine; you do not need ROCm or a GPU for this workload.
• Store Parquet, not Arrow IPC, on disk. Scan lazy.
• Do not put the lake in iCloud Desktop.
• 128 GB means you can debug by materializing the full 60-day frame. That is a luxury, not a design requirement.

Bottom line: spend ~$60/month and ~2 weeks of focused engineering for a correct daily+1-min research lake on 500 names. The Mac is not the bottleneck. Consolidated volume and split hygiene are. Information-clock bars are a second project and a second data SKU.

---

## Q-SB2-3 — success ratios, after-cost efficacy, failure modes (verbatim)

Every number below is taken from a named paper, book, or replication that states the sample. Practitioner blogs are labeled as such. Nothing here is a live trading recommendation.

1. Opening-range breakout
Crabel's own results — gross, futures, 1978–1986-ish
Crabel's 1990 book and the Stocks & Commodities articles that preceded it report percentage profitable and gross dollars, not Sharpe after slippage. Typical published pattern:
• T-bonds, entry 16 ticks off the open after ID/NR4-type setups: high win rate, win/loss 2.34 : 1, 1978–1986.
• Across NR4 tests: "in 15 of 16 comparisons, ORB days following NR4s have a higher percentage of winning trades than the control"; win rates clustered 60–70%, never above 70% in those tables; exit same-day close; no commission.
• Pattern frequency ~once every 8–10 sessions.
These are before costs. Pit-era tick sizes and pit liquidity are not 2020s electronic spreads.
Crabel himself later wrote that the raw open-plus-fraction-of-range rule decayed as evening sessions and 24-hour structure removed close-to-open pressure, and that a century-scale equally-weighted futures test of a stripped ORB (enter at 0.8 × 10-day average range, exit next open, no stops) shows falling dollars-per-contract and Sharpe.

Academic / quasi-academic after-cost work
Zarattini & Aziz, "Can Day Trading Really Be Profitable?" (SSRN; US stocks 2016–2023). Commission modeled at $0.0035/share. Unfiltered 5-minute ORB on a broad stock set: +29% total, Sharpe 0.48, hit ratio 41.4% — after that commission, not a stand-alone edge vs SPX. A "stocks in play" + relative-volume overlay: +1,637% total, Sharpe 2.81, hit 48.4%, max DD 12%. That second number is after stated commission, on a highly selected 20-name book, 2016–2023 only. Capacity and borrow/locate are not in the paper.

Later replications (label carefully)
Study | Market / period | Costs? | Result | Status
Tick-stream NQ 5-min, 2019–2026, train/holdout | NQ futures | $4.50 + 2 ticks | 15-min ORB ride-to-EOD or 2R target positive train and holdout, thin PF ~1.1; fade loses; fixed-tiny-target "81% WR" ≈ coin flip after costs | Practitioner, documented method
QuantifiedStrategies SPX/NQ/GC/SI/CL | Indices & futures | Not a journal paper | Unfiltered ORB "doesn't work very well anymore"; best SPX variant ~0.04%/trade | Practitioner
Iron Hall | NDX ETF vs 120 S&P names | Before costs | Index long-break ~57.5% at 1R; 120 stocks 50.1% | Practitioner
Crypto 12-mo BTC/ETH | Spot | 5 bp/side | PF 0.65–0.80, net negative | Practitioner

When it breaks
• Unfiltered, every-name, every-day ORB after modern equity or futures costs.
• Single-stock universe without a volume/"in play" filter (Zarattini base case; Iron Hall 120-name test).
• Tight fixed targets that convert a trend-day payoff into a high-WR coin flip once slippage is on the breakout tick.
• Markets without a concentrated cash open (crypto 24h tests go red).
• Post-1980s futures structure if you keep 1986 bond-pit parameters (Crabel's own later writing).
Tradable remainder (documented, not guaranteed): index/futures trend-day ORB with a volume or NR filter, let winners run to the close, size small enough that 1–2 ticks of slippage do not erase a ~1.1 PF. That is a thin after-cost edge in a few replications, not the 1980s table.

2. RSI-2 and IBS (Connors-style mean reversion)
What Connors published — gross, US stocks/ETFs, mostly 1993–2008 window in the book
Short Term Trading Strategies That Work (Connors & Alvarez, 2008): RSI(2) on S&P names above the 200-day MA. Documented 5-day forward returns by threshold (book tables, no costs in the published grid):
RSI(2) | Avg 5-day return (uptrend names)
< 2 | +0.92%
< 5 | +0.68%
< 10 | +0.48%
< 25 | +0.22%
> 90 / > 95 | −0.21% / −0.34%
Headline strategy stats in the same literature: win rates ~73–75%, hold 3–5 days, Connors explicitly against stops (stops cut the right tail of the rebound). Those are before spread and borrow.

Independent / longer-sample replications (mixed cost treatment)
Source | Rules / market | Costs | Headline | Drawdown regime
QuantifiedStrategies RSI-2 on QQQ | Connors-style | Typically gross in their tables | 321 trades, +0.9%/trade, WR 71%, PF 2.1, CAGR 10.7%, time-in-mkt 18%, max DD 23% vs B&H 82% | DD in crisis/trendless tapes; 2011-type shocks
Same shop, RSI-2 SPY | similar | gross | CAGR ~9%, max DD 34%, invested 28% | 34% DD is the binding constraint
QQQ-constituent 4-slot book, ~20y | RSI-2 + 200-dma | not a journal | WR 64%, PF 1.45, CAGR 17.8%, max DD 29%, Sharpe ~1.1 | Losers larger than winners (−3.0% vs +2.3%)
ConnorsRSI (3,2,100) book tables | shorts and longs | gross | Top variants WR ~75–79%, avg hold a few days to ~10 | Sample-selected "top 20 variations"

IBS — documented research paper
Pagonidis, "The IBS Effect: Mean Reversion in Equity ETFs" (2013). Equity index ETFs, early 1990s onward. IBS = (C − L)/(H − L). Next-session return: IBS < 0.20 → +0.35%; IBS > 0.80 → −0.13%. Effect described as persistent through that sample.
Kinlay's 1999–2016 illustration of the same rule on SPY/EWS: CAGR on the order of 13% (SPY) and much higher on EWS ignoring costs; he notes returns diminished and turned negative in 2015–2016 YTD.
QuantifiedStrategies IBS-on-SPY style tests (practitioner, often gross): WR ~68–75%, avg trade 0.4–0.8%, max DD ~20–26%. QQQ usually stronger than SPY.
One 2006–2026 SPY test that does put $0.01/share commission + $0.01 slippage on an IBS<0.3 / exit-above-prior-high rule: WR 75%, PF 2.02, CAGR 7.75%, max DD 15%, time-in-market 21%. That is after a small-cost assumption, on one liquid ETF.

When it breaks
• Below the 200-day MA / bear regimes. Connors' own filter exists because unfiltered RSI-2 buys falling knives. 2008 and 2022-style trends produce the documented 20–35% strategy DDs.
• Single names and small caps after costs. 75% WR on SPY does not transfer to a 500-name book once the spread is 5–20 bp and you pay the close-to-open gap.
• Stops. Connors' tests said stops hurt; if risk limits force stops, published hit rates are not the live ones.
• Crowding / post-2015 ETF mean reversion fade (Kinlay on IBS; several later samples show flatter recent equity curves).
• Short side without a downtrend filter: published short RSI-2 stats are weaker and borrow-cost unstated.
After-cost summary: On SPY/QQQ, a 1–2 day hold, entry at the close, exit next day or on a 5-day SMA, can survive retail ETF spreads. The published 0.5–0.9% average winner is gross; after 2–5 bp round-trip the residual is still positive on the index ETFs in several long samples, and not demonstrated for a 500-stock scanner.

3. HAR vs GARCH for vol forecasting
This is a forecast-accuracy literature, not a trading P&L literature. Costs appear only if you trade variance.

Documented ranking
Corsi (2009), HAR-RV, Journal of Financial Econometrics: additive daily / weekly / monthly realized-vol components; designed as a simple long-memory approximation. Out-of-sample forecasting is the paper's claim to fame.
Mastro (2014), SSRN, SPX / FTSE / DAX / Nikkei, Sep 2009–Jun 2014: HAR-RV beats ARCH-family models on every index and horizon tested; log-HAR preferred. The comparison is RV forecast error, not option P&L.
Aganin (Russian market MCS study): HAR-RV family (esp. log-HAR) statistically dominates GARCH and ARFIMA on 1-day-ahead RV for 10 MOEX names via Hansen MCS.
Clements & Preve, "A Practical Guide to Harnessing the HAR Volatility Model": HAR is the workhorse; WLS / robust estimation and transforms beat plain OLS HAR, and those simple fixes also beat some HARQ variants on SPX + 26 NYSE names.
Khan (SSRN 2026), SPX RV 2004–2025, test 2022–2025: horse race of GARCH / EGARCH / GJR / HAR / trees. Full test sample: no model wins Diebold–Mariano (ensemble QLIKE 0.3431 vs GJR 0.3447, p = 0.90). 2022: GARCH family wins (EGARCH QLIKE 0.2346). 2023–25: trees lead, HAR last. So HAR is not unconditionally best in every window.
Zhong et al. (2026), ~5,000 China A-shares, 2023–25: HAR-RV first or second every year; a foundation-model forecaster is 2.4–2.6× worse MAE. HAR still beats fancy alternatives here.

What "accuracy gain" means
Typical documented pattern (qualitative, across papers): for 1-day-ahead realized variance of liquid indices, HAR (or log-HAR / HAR-jumps) reduces QLIKE/MSE versus GARCH(1,1) because GARCH is fit to squared daily returns, not to RV. That is a measurement advantage as much as a model advantage. At multi-week horizons the gap shrinks; in regime shifts (2022-type) parametric GARCH can adapt faster than a 30-feature tree or a stale HAR.
None of these papers convert the QLIKE gap into after-cost VIX or variance-swap P&L. Do not treat "HAR beats GARCH" as a vol-selling backtest.

When it breaks
• Forecasting implied vol / option prices (some Bitcoin work finds GARCH closer to IV than HAR).
• Samples where the RV proxy is noisy (too-fine sampling without noise-robust RV).
• 2022-style inflation-shock windows in at least one recent SPX horse race.
• Using HAR coefficients estimated on 22 days (identification failure) — the literature uses years of daily RV.

4. End-of-day / last-hour effects
There are three different documented effects. Mixing them is how people invent a free lunch.

A. Market intraday momentum (index level) — Gao, Liu, Zhou
"Market Intraday Momentum," Journal of Financial Economics 2018. SPY 1993–2013. First half-hour return (from prior close) predicts last half-hour return. Predictive R² 1.6%; with the 12th half-hour added, 2.6%; high-vol days 3.3%. Also found in 10 other liquid ETFs. Authors argue economic gains in a timing rule.
That paper's timing exercise is not a full microstructure-cost study of trading the 15:30–16:00 window through the close auction.

B. Cross-sectional end-of-day reversal — Baltussen, Da, Soebhag
Working paper (2024/25, Notre Dame PDF). Individual stocks: rank on return from prior close to 15:30. Losers beat winners in 15:30–16:00 by about 0.24% per day on a long-short decile book. Distinct from market-level intraday momentum; mostly buyers lifting losers. Not explained by liquidity or gamma hedge in their tests. Present in rolling 3-year windows and in size/liquidity splits.
Cost label: the 24 bp is a long-short mid-to-mid (or last-trade) academic return, not a fill in the closing auction. Implementing it means trading a 100–200 name book into the most crowded 30 minutes of the day.

C. Overnight drift and its fade — NY Fed
Boyarchenko, Larsen, Whelan: overnight rebound after closing imbalance, concentrated around 02:00–03:00 ET when Europe opens. NY Fed 2026 update: the 2:00–3:00 window that had been ~3.7% annualized is ~0 since 2021. Channel: std. dev. of last-hour relative signed volume fell from 6.5% to 2.9%. Volatility and dealer capacity measures little changed. Prediction: if close-imbalance dispersion returns, the drift should return.

Is last-hour drift tradable after the closing-auction spread?
Documented facts that cut against naive implementation:
• The close is an auction. MOC/LOC and published imbalances move the print; a marketable order in the last minutes is not the academic 15:30–16:00 mid return.
• EOD reversal is cross-sectional and crowded (indexers, MOC). Capacity is the open question the working paper does not settle with live fills.
• Overnight drift already faded in the post-2021 sample the NY Fed published.
• Index intraday momentum is one trade per day in SPY; the last-half-hour spread on SPY is small, so a timing overlay (stay long/flat last 30 minutes) is closer to tradable than a 200-name loser-basket into the auction.

When it breaks
• Treating Gao–Liu–Zhou (index continuation) as Baltussen–Da–Soebhag (stock reversal) — they have opposite signs.
• Paying the close auction on the full loser decile.
• Assuming the 1993–2013 first-half → last-half R² is a 2026 live Sharpe.
• Overnight-drift harvest after 2021 without evidence that imbalance dispersion has widened again.

Cross-strategy cheat sheet
Strategy | Best documented habitat | Typical published WR / effect | After documented costs? | Breaks when
ORB | Index futures / "in play" stocks, trend day | Unfiltered WR ~40–50%; filtered higher | Zarattini overlay yes (0.35¢/sh); raw ORB often no | No volume filter; 24h tape; tight targets
RSI-2 | SPY/QQQ above 200-dma | WR ~70–75%, +0.5–0.9%/trade gross | ETF: probably; 500-stock book: unproven | Bear market, stops, single-name spreads
IBS | Equity index ETFs | Next-day +35 bp if IBS<0.2 (Pagonidis) | Same as RSI-2 | 2015–16 fade in some series; illiquids
HAR vs GARCH | 1-day-ahead RV of liquid indices | HAR usually lower QLIKE than GARCH(1,1) | N/A (forecast metric) | Implied-vol target; 2022-type breaks; tiny samples
Last-hour | Index timing (momentum) vs stock L/S (reversal) | R² 1.6–2.6% (index); 24 bp/day L/S (stocks) | Index overlay maybe; stock L/S through auction not shown | Mixing the two effects; faded overnight drift

For the 500-name pipeline: treat RSI-2/IBS on the index overlay and HAR as a vol forecast as the parts with the cleanest paper trail. Treat unfiltered ORB and last-30-minute stock reversal as research hypotheses that need your own after-auction cost model, not as settled edges.
