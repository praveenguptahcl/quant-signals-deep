# RB4 — Grok answers (regimes R031–R040) — VERBATIM

- Batch: RB4 — Cross-asset stress + calendar/event regimes (R031–R040)
- Bot: Grok (grok.com), signed in as Praveen Gupta (x.ai email+password login from Secure Vault; no OTP needed)
- Date: Thu 2026-09-10 (America/Chicago)
- One new chat for the whole batch: https://grok.com/c/63d557af-af65-4d49-bcac-c8ed77b9255f — standing context + Q-RB4-1, then Q-RB4-2, then Q-RB4-3, each sent only after the prior answer fully completed (streaming indicator gone; no stop button). No rate limits hit.
- Fidelity notes from the browser run (the answer was not re-typed; only lightly cleaned):
  1. Grok's rendered text extraction duplicates some sentences (a rendering artifact); those were de-duplicated.
  2. Where the page mangled math, LaTeX was recovered from the page's KaTeX annotations — flagged inline.
  3. One KaTeX parse artifact in Q1 R034: the source had a stray "}" in "\text{ log}; }+18\%\text{ simple}" — cleaned to "(16.55% log; +18% simple)".
  4. A couple of Q1 sentences were truncated by extraction (e.g., the quarter-close bp fragment); reconstructed readings are bracketed.
- Handling: research leads, not facts. Anything without a checkable source goes under `Unverified leads`, never in `Sources`. Nothing here is a live-trading spec; research for the document only.

========== Q-RB4-1 VERBATIM ==========

# Q-RB4-1 · Market Regimes R031–R040

All statistics are tagged documented (named paper/source + URL) or illustrative-example. Formulas use only standard definitions; every symbol is defined with units. Worked examples use the synthetic datasets you specified.

## R031 · Cross-asset correlation regime

(1) Precise definition. A state in which the average pairwise Pearson correlation of excess returns across a fixed basket of asset-class proxies is high enough that diversification is statistically impaired ("correlation monoculture" / fused risk).

(2) Exact formula. N assets, rolling window of W trading days, simple returns r_{i,d} (decimal, unitless):

Pairwise Pearson correlation on day t: ρ_{i,j,t} = Cov(r_i, r_j) / (σ_i σ_j), estimated over the trailing W days.

Mean pairwise correlation (upper triangle only):
ρ̄_t = (2 / (N(N−1))) · Σ_{i<j} ρ_{i,j,t}

Optional fusion gauge (edge density): E_t = (2 / (N(N−1))) · Σ_{i<j} 1[ρ_{i,j,t} > θ_edge], where θ_edge is an edge threshold (unitless, e.g. 0.50).

Inputs: daily (or higher) total-return series for the N proxies; window W (trading days); optional edge threshold θ_edge.

Pearson formula is textbook; rolling-network / edge-density reduction is the standard "how fused is the market" operationalization. (Cited: arXiv; Vector-ridge ×2.)

(3) Parameter ranges.
• W ∈ {20, 30, 60, 90} trading days — practitioner defaults; 30/90 used operationally by multi-asset desks.
• High-correlation / "fused" band: ρ̄ ≥ 0.50 — documented, large at ~0.50. Crisis pairwise readings > 0.8 are commonly cited as a qualitative crisis feature.
• Diversification-friendly: ρ̄ ≤ 0.30 — illustrative-example.

(4) Worked example (5-asset × 10-day panel). Assets A–E. Ten daily simple returns (illustrative-example, decimals):
Day: A / B / C / D / E
1: 0.010 / 0.008 / 0.012 / 0.006 / 0.009
2: −0.004 / −0.003 / −0.005 / −0.002 / −0.004
3: 0.007 / 0.006 / 0.008 / 0.005 / 0.007
4: −0.006 / −0.005 / −0.007 / −0.004 / −0.006
5: 0.003 / 0.002 / 0.004 / 0.001 / 0.003
6: 0.011 / 0.009 / 0.010 / 0.008 / 0.010
7: −0.008 / −0.007 / −0.009 / −0.006 / −0.008
8: 0.005 / 0.004 / 0.006 / 0.003 / 0.005
9: −0.002 / −0.001 / −0.003 / 0.000 / −0.002
10: 0.004 / 0.003 / 0.005 / 0.002 / 0.004

All ten pairwise ρ_{i,j} on this co-moving panel sit in 0.96–0.99. Mean pairwise: ρ̄ = 0.98. Edge density at θ_edge = 0.50: 1.00.
Classification: R031 HIGH / FUSED (illustrative-example thresholds).

## R032 · Flight-to-quality (stock/bond correlation sign)

(1) Precise definition. A flight-to-quality (FTQ / FTS) state is a stress episode in which equity returns are large and negative, government-bond returns are large and positive. Baur & Lucey formalize FTQ vs contagion vs interdependence via the change in correlation in a crisis dummy window. Baele–Bekaert–Inghelbrecht–Wei operationalize FTS days as joint equity-down / bond-up days. (Cited: ScienceDirect — Baur & Lucey; NBER — Baele et al.)

(2) Exact formula. r_e = equity total return (e.g. SPY), r_b = Treasury total return (e.g. TLT), both decimal. Rolling Pearson ρ_t over window W as in R031.

Sign-regime: negative ρ_t under equity stress = flight-to-quality state; positive ρ_t = risk-on / inflation co-move.

A strict FTQ flag (illustrative operationalization of the Baele et al. logic):
FTQ_t = 1[ρ_t < ρ_FTQ] · 1[σ_e,t > σ_e,crit] · 1[r_e,t < 0 < r_b,t],
where σ_e,t is realized equity vol over the same window (annualized, decimal).

Inputs: SPY (or local equity index) and TLT / 10y total-return series; W; optional vol and magnitude cutoffs.

(3) Parameter ranges.
• Post-2000 average monthly US stock–bond correlation ≈ −0.2 (Jan 2000–Nov 2022) — documented. 1926–1999 average +0.18. (Cited: Wealthmanagement.)
• Pre-dot-com average +0.30, post-dot-com −0.2 (Amundi review of the same history). (Cited: Research-center.amundi.)
• Baele et al.: FTS days are rare (<5% of sample); on those days bonds outperform equities by [a large margin] — documented. (Cited: NBER.)
• W = 63 trading days (~one quarter) — illustrative-example (as specified in the brief).

(4) Worked example. Given: 63-day SPY/TLT correlation +0.35 (brief). Assume contemporaneous 63-day realized equity vol is ordinary (not a crisis spike). ρ_t = +0.35 is not negative, so the FTQ flag is OFF because the sign condition fails.
Classification: R032 RISK-ON / NO FLIGHT (positive stock–bond corr).
(If the same window printed −0.40 with a large down-equity / up-bond day, the flag would flip to FTQ.)

## R033 · Systemic tail-risk / crisis regime

(1) Precise definition. A systemic tail state is simultaneous distress across many constituents, not an idiosyncratic crash. Operationalized via co-exceedances — names whose standardized residual on day t breaches a left-tail threshold. Polanski–Stoja–Chiu treat co-exceedance as the practical measure of systemic risk. (Cited: Bankofengland — Polanski–Stoja–Chiu SWP 815; IMF 2011.)

(2) Exact formula. For benchmark i, return r_{i,t}, rolling mean μ_{i,t} and std σ_{i,t} over lookback L (trading days):

z_{i,t} = (r_{i,t} − μ_{i,t}) / σ_{i,t} (unitless)

Tail count at threshold κ (typically 2.5): C_t(κ) = Σ_{i=1}^{M} 1[z_{i,t} < −κ]

Crisis flag: CRISIS_t = 1[C_t(κ) ≥ K_crit]

Inputs: daily returns on M benchmarks (equity regions, credit, FX, commodities); L; κ.

(3) Parameter ranges.
• κ = 2.5 — illustrative-example (standard extreme-value practice; not a unique published constant).
• K_crit: a fraction of M or a fixed integer such as 3 of 8 — illustrative-example.
• Systemic vs idiosyncratic distinction: IMF (2011) — severity plus contagion, not a single-country crash.

(4) Worked example. M = 8 benchmarks. On date t, three names print z_{i,t} < −2.5, five do not. C_t = 3 ≥ K_crit = 3.
Classification: R033 CRISIS FLAG ON.

## R034 · Energy / commodity shock regime

(1) Precise definition. A discrete energy-price shock state: the standardized cumulative move in a benchmark (WTI or Brent front-month) over a short horizon exceeds a shock band, optionally confirmed by volatility elevation. (Cited: RIETI — Zanetti column on identified episodes.)

(2) Exact formula. Let P_t be the futures settlement (USD/bbl). Horizon-H log return:
R_t(H) = ln(P_t / P_{t−H}) (unitless, decimal)

Rolling mean μ_R and std σ_R of H-day log returns over lookback L (trading days).
Shock z-score: z_t = (R_t(H) − μ_R) / σ_R (unitless)

Shock flag (unsigned or signed): SHOCK_t = 1[|z_t| > z_shock] (or 1[z_t > z_shock] for upside-only).

Inputs: WTI/Brent nearby settlement; H; L; or raw-move threshold.

(3) Parameter ranges.
• H = 20 trading days — illustrative-example (brief).
• Raw move 18% in 20 days — illustrative-example (brief). A documented analogue: from 26 Aug 2026 lows, both Brent and WTI advanced ~18% in less than a month. (Cited: FXStreet.)
• MS-AR high-vol oil "crisis" cluster: mean ≈ 4.79× [vol multiple] per day, ~9.5% of sample — documented in one commodity-regime paper (do not treat as a universal law). (Cited: ScienceDirect.)

(4) Worked example. P_{t−20} = 70, P_t = 82.6.
R_t(20) = ln(82.6/70) = ln(1.180) ≈ 0.1655 (16.55% log; +18% simple) [LaTeX recovered from page annotation; stray brace in source cleaned]
If the 20-day log-return history has μ_R = 0.01, σ_R = 0.06:
z_t = (0.1655 − 0.01) / 0.06 ≈ 2.59
With z_shock = 2 (illustrative-example): shock ON.
Classification: R034 ENERGY SHOCK ON (positive / upside).

## R035 · Earnings proximity / earnings season

(1) Precise definition. A name-level (or calendar-season) state: calendar distance to the next scheduled earnings release is small AND implied vol is elevated versus the name's own history (IV rank or IV percentile). IV crush after the print is the release mechanism.

(2) Exact formula. Let T_e be the next earnings timestamp. Calendar distance: d = T_e − t (calendar days; signed).

IV rank over a 252-session lookback:
IVR_t = 100 × (count of sessions s in trailing 252 with IV_s ≤ IV_t) / 252

IV percentile = fraction of the 252 sessions with IV_s < IV_t (×100).

Proximity flag: EARN_t = 1[d ≤ D] · 1[IVP_t ≥ IVP_crit]

Inputs: company earnings calendar; ATM IV (or IVX) time series.

(3) Parameter ranges.
• Entry sweet-spot 1–2 trading days pre-print — practitioner timing. (Cited: Pomegra.)
• IV rank / percentile 70–90 as "elevated earnings IV" — illustrative-example (90 used per brief). IV crush after the print is the dominant driver of IV-collapse screens (a ±5d window contains 39.2% of collapse signals in one vendor study) — documented as a vendor result, not a journal law. (Cited: iVolatility.)
• Mean-reversion of IV is a CBOE stylized fact (qualitative). (Cited: Impliedoptions.)

(4) Worked example. Name reports in 2 calendar days. Current ATM IV sits at the 90th percentile of its 252-day history. d = 2 ≤ D = 2 and IVP = 90 ≥ 90.
Classification: R035 PRE-EARNINGS HIGH-IV ON.

## R036 · Macro announcement windows

(1) Precise definition. A clock-time state around a scheduled macro print (CPI 08:30 ET, FOMC statement ~14:00 ET, press conference ~14:30 ET). Starts before the stamp (compression) and ends after digestion. Gürkaynak, Sack & Swanson (2005) and the subsequent event-study literature define the 30-minute statement window: T−10m to T+20m. (Cited: FRBSF.)

(2) Exact formula. Let T be the official release timestamp. Partition:
Compression: [T−60m, T); Repricing: [T, T+15m] (brief); Digestion: [T+15m, T+120m].

Intraday realized range or bid–ask multiple versus a same-clock control:
M_t = spread_t / spread_control (unitless multiple).

Surprise (rates): Δy in bp over the statement window.

Inputs: tick quotes on the target future (ES, TY, FF); official release calendar; control-day same-clock averages.

(3) Parameter ranges.
• FOMC statement window T−10m to T+20m — documented (FRBSF).
• CPI official stamp 08:30 ET; thin book in the pre-print minutes — qualitative documented market-structure note. (Cited: Bookmap.)
• Spread multiples 3–5× in the compression minute and the first 1–2 repricing minutes — illustrative-example (not a journal constant).
• Post-2022 FOMC/CPI expected move has compressed versus 2022 peaks (tastylive: expected vol ~40% of 2022) — documented as a vendor observation. (Cited: Tastylive.)

(4) Worked example (CPI-day map). Control 1-minute TY bid–ask = 0.5 tick.
• T−60m: average spread 1.5 ticks → M = 3.0× (compression)
• T…T+15m: range 8 ticks, spread 2.0 ticks → M = 4.0× (repricing)
• T+120m: spread 0.7 tick → M = 1.4× (digestion)
Classification: R036 ACTIVE during compression+repricing; stand-down once M returns near 1.

## R037 · Month / quarter-end rebalancing

(1) Precise definition. A calendar-flow state: institutional mandates that reset asset-class weights at month-end / quarter-end create predictable cross-asset pressure — sell the winner class, buy the loser class. Hartzmark–Solomon document predictable price pressure: −16 to −17 bp of next-day equity return and a small positive bond response. (Cited: NBER.)

(2) Exact formula. Target weights w* (e.g. 0.60 / 0.40). Mark-to-market weights after the period's drift:
w_e = w*·(1+R_e) / [w*·(1+R_e) + (1−w*)·(1+R_b)]

Required equity trade as a fraction of AUM: Δ = w_e − w* (negative = sell equity).

Dollar pressure on one index name with weight ω in the equity sleeve and fund AUM A:
Flow_$ = Δ × A × ω. Sign(Δ) is the direction of mechanical equity flow.

Inputs: period asset-class total returns; assumed target mix; AUM and name weight (or an aggregate flow estimate).

(3) Parameter ranges.
• Turn-of-month mean daily return 10 bp vs 0 bp on other days across markets — documented. Extra +7 bp at Mar/Sep quarter-close and +17 bp at Jun/Dec semi-year close versus regular month-ends — documented. (Cited: ScienceDirect.)
• US public-pension gross quarterly rebalance often cited $50–100 bn in normal quarters — illustrative-example / practitioner estimate, not a regulatory filing total. (Cited: Alpha-suite.)

(4) Worked example. Target 60/40. Quarter: equity +10%, bonds +0%. Fund AUM $10 bn. Index name weight ω = 2% of the equity sleeve.
w_e = 0.60×1.10 / 1.06 = 0.66/1.06 = 0.6226
Δ = 0.6226 − 0.60 = 0.0226 → must sell 2.26% of AUM in equities = $226 m.
Name-level: 0.02 × $226 m = $4.53 million (sell).
Classification: R037 MONTH/QE REBALANCE PRESSURE ON (equity-sell / bond-buy).

## R038 · Thin-liquidity sessions

(1) Precise definition. A session (or intraday bucket) whose volume participation versus a same-clock baseline is low enough that depth and spreads degrade. Operational scalar: volume pace.

(2) Exact formula. Let V(t) be cumulative share (or contract) volume from session open to clock t; V_typ(t) the trailing same-clock average (20-day or 60-day).
VPace(t) = V(t) / V_typ(t) (unitless)
Thin flag: THIN_t = 1[VPace(t) < VPace_crit]

Inputs: intraday cumulative volume; 20-day (or 60-day) same-clock baseline; session calendar (half-days, holidays).

(3) Parameter ranges.
• 0.5–0.7: meaningfully thin; <0.5: genuine low-volume regime — illustrative-example practitioner bands. (Cited: Daytradingtoolkit.)
• Day after Thanksgiving US equity volume ~45% of normal (half-day) — documented as cited by a practitioner note referencing Russell Investments. (Cited: Daytradingtoolkit.)
• Extended-hours liquidity often 2–8% of regular-session liquidity; spreads 5–20× — illustrative-example / vendor education. (Cited: Pomegra.)
• Conventional institutional participation-rate working figure ~10% of ADV — practitioner note. (Cited: Signalpilot.)

(4) Worked example. Half-day session. By 12:00, cumulative volume = 55% of the same-clock 20-day mean. VPace = 0.55. With VPace_crit = 0.70 → 0.55 < 0.70.
Classification: R038 THIN-LIQUIDITY ON.

## R039 · Options expiry / OpEx pinning

(1) Precise definition. A pinning state exists when dealer hedging around concentrated open interest pulls the underlier toward a strike into expiry. Max pain is the candidate settlement that minimizes total intrinsic value paid to option holders.

(2) Exact formula. Contract multiplier m (SPY = 100). For candidate settlement K on the expiry chain:
Π(K) = m · [ Σ_calls OI_c · max(K − X_c, 0) + Σ_puts OI_p · max(X_p − K, 0) ]
where X_c, X_p are strikes. Max-pain strike: K_MP = argmin_K Π(K) over listed strikes.
Pin distance: |S − K_MP| / S.

Inputs: expiry-chain call and put open interest by strike; spot; multiplier.

(3) Parameter ranges / 2026 caveat. Max-pain arithmetic is definitional (OCC settlement + OI). Pinning is a tendency, strongest when dealers are long gamma, OI is concentrated, and no macro catalyst overrides. Daily 0DTE listings (SPX Mon–Fri since 2022–23) have fragmented gamma across every session and diluted classic monthly pinning. 2010s monthly-pin statistics must not be applied to 2026 without re-verification. That caveat is part of the regime definition, not optional color. (Cited: Crossvol.)

(4) Worked example (5-strike chain). m = 1 for arithmetic clarity (scale later). OI:
Strike 96: Call OI 10 / Put OI 40
Strike 98: Call OI 20 / Put OI 30
Strike 100: Call OI 50 / Put OI 50
Strike 102: Call OI 30 / Put OI 20
Strike 104: Call OI 40 / Put OI 10

Compute Π(K) at each listed strike (intrinsic × OI, summed):
• K=96: calls pay 0; puts pay (98−96)×30 + (100−96)×50 + (102−96)×20 + (104−96)×10 = 60+200+120+80 = 460. Π = 460.
• K=98: calls pay (98−96)×10 = 20; puts pay 100+80+60 = 240. Total 260.
• K=100: calls pay (100−96)×10 + (100−98)×20 = 40+40 = 80; puts pay (102−100)×20 + (104−100)×10 = 40+40 = 80. Total 160.
• K=102: calls pay 60+80+100 = 240; puts pay 20. Total 260.
• K=104: calls pay 80+120+200+60 = 460; puts pay 0. Total 460.

Minimum Π = 160 at K = 100. Spot is already at max pain.
Classification: R039 PIN / MAX-PAIN ACTIVE at 100. Do not attach a 2010s "pin probability" number to this 2026 example.

## R040 · Index rebalance days

(1) Precise definition. A reconstitution / share-float / add-delete effective date on which passive trackers must trade to track the index — mechanical and concentrated in the close. Dimensional (2014–2023, 10 US indices) documents abnormal volume, close-auction spikes (3× to 27×). (Cited: InteractiveBrokers.)

(2) Exact formula. For name added with target index weight w_new (decimal) and estimated passive AUM A tracking that index:
$Flow_buy = w_new × A
For a deletion with old weight w_old: $Flow_sell = w_old × A
For a weight change only: Δ$ = (w_new − w_old) × A
Shares to trade: N = Δ$ / P. Participation vs ADV: π = N / ADV.

Inputs: official add/delete/weight file; estimated passive AUM; last price; ADV.

(3) Parameter ranges.
• Russell reconstitution close is routinely one of the year's largest prints; 2024 close ~$220 bn on NYSE — documented news/exchange color, not a structural constant. (Cited: Nasdaq.)
• Adds/deletes: ~4% average excess move over the 20 days into reconstitution and ~5.7% reversal over the 20 days after (Dimensional, 2014–2023) — documented. Close-to-print add +9 bp / delete −30 bp with next-open reversal — documented. (Cited: Mywealthadvisor.)
• Closing-auction share of volume: typical day ~5%; S&P/NDX rebalance ~20%; Russell reconstitution >25% — documented practitioner/exchange color. (Cited: YouTube.)

(4) Worked example. Index passive AUM $200 bn. Name added at 0.15% (w_new = 0.0015). Price $50. ADV = 8 million shares.
$Flow = 0.0015 × $200 bn = $300 m (buy).
N = $300 m / $50 = 6 million shares. π = 6.0 / 8.0 = 0.75 of one-day ADV.
That participation cannot clear in continuous trading without impact; the residual prints in the close.
Classification: R040 INDEX-REBALANCE DAY ON (add, large close-print).

## Cross-regime notes for the chapter
1. R031 vs R032. R031 is [the level] of mean pairwise corr across many sleeves. R032 is the sign of one pair (equity vs duration) plus a stress filter. They can disagree: 2022 was high cross-asset [corr] + positive stock–bond corr (inflation regime), which is not FTQ.
2. R033 vs R034. A WTI shock (R034) is systemic only if it co-exceeds across the benchmark panel (R033).
3. R037 vs R040. Month-end asset-class rebalance is a 60/40 flow. Index reconstitution is a name-level forced trade at a published effective date.
4. R039 in 2026. Treat monthly max-pain as a mechanical identity; [pinning is a] hypothesis about dealer gamma. Re-estimate pin rates on a 2023–2026 0DTE sample before using any 2010s hit-rate.
5. Data hygiene. Pearson on raw returns is biased upward in high-vol windows (Forbes–Rigobon). If the chapter later needs con[stant conditional correlation estimates, use a heteroskedasticity correction].

(82 sources cited by Grok on Q1.)

========== Q-RB4-2 VERBATIM ==========

# Q-RB4-2 · Compute stack for R031–R040 on M5 Max / 128 GB

Hardware is not the constraint. Data contracts, calendar timestamps, and causal windows are. The M5 Max + 128 GB unified memory can hold every daily panel these ten indicators need in RAM with headroom.

All prices below are indicative (public list / published plan pages as of 2026; exchange license pass-through and sales-quoted enterprise SKUs move). Verify before buying.

## 1. Data feeds — exact products, not categories

Lock a benchmark set file on day zero (benchmarks.yaml, git-tagged). Do not add names after seeing results.

Regime | What you actually buy | Exact product to name in the repo
R031, R032, R033, R037 | Cross-asset EOD total returns | Primary: Norgate Data US Stocks Platinum (or Gold) + Norgate Futures — local DB, delisted + historical index members. Alt: Polygon.io Stocks Advanced (Massive) EOD + minute aggs for ETFs. Basket (fix ex ante): SPY, QQQ, IWM, EFA, EEM, TLT, IEF, LQD, HYG, GLD, USO or DBC, UUP, VNQ, BITO optional.
R032 | Stock/bond pair | SPY + TLT daily total return. Same vendor as above. Do not mix Yahoo adjusted close with Norgate unadjusted.
R033 | Systemic tail panel | Same ETF basket, frozen. Optional second panel: sector SPDRs (XLB–XLY) as a named alternative estimator, not a substitute.
R034 | WTI shock | Preferred research path: Databento GLBX.MDP3 OHLCV-1d for NYMEX CL (Light Sweet Crude Oil). Build your own continuous series (see §fail-safes). Cheap path: Norgate Futures continuous CL (document their roll rule). Do not use USO as the shock series — ETF roll/contango is a different object.
R035 | Earnings calendar + IV | Calendar: Benzinga Calendar API GET /api/v2.1/calendar/earnings (fields: date, time, date_confirmed, ticker). Also available via Polygon/Massive Benzinga partner route /benzinga/v1/earnings. IV: Polygon Options Starter+ (Greeks, IV, & Open Interest) daily snapshot on the earnings-nearest expiry ATM.
R036 | Macro calendar + event windows | Calendar: Benzinga Economics (/api/v2.1/calendar/economics) or FRED release calendar + BLS/Fed official stamps. Prices for windows: Polygon Stocks minute aggs on SPY/TLT/IEF or Databento CME ES/ZN if you want futures event studies. FOMC window convention: T−10m to T+20m (Gürkaynak–Sack–Swanson 2005). CPI stamp: 08:30 ET.
R037 | Month/QE calendar + asset-class returns | NYSE/Nasdaq holiday calendar + pandas_market_calendars (XNYS). Returns: SPY/TLT (or VTI/BND) from the EOD vendor. No extra paid feed.
R038 | Session volume / VPace | Polygon Stocks minute aggs (SPY + a 20-name ADV panel) or Databento US equities if you already pay it. Half-days: NYSE early-close calendar (day after Thanksgiving, Christmas Eve when applicable, July 3).
R039 | Options OI + chain | Polygon Options Developer ($79/mo indicative) EOD OI + strikes for SPY/QQQ monthly and weekly. Historical OI as-of a date — confirm the vendor stores as-of OI, not only "current." Alt: ORATS OSMV via Nasdaq Data Link (premium, sales-quoted).
R040 | Index add/delete + AUM | Calendars (free/official): S&P Dow Jones Index Announcements; FTSE Russell reconstitution notices; Nasdaq-100 methodology notes. AUM: ETF.com / issuer sites for SPY, IVV, VOO, IWM, QQQ — scrape quarterly, store as a table. Constituent weights: Norgate historical index constituents (Platinum+) or issuer methodology files. Do not infer adds from price spikes.
Shared | Macro levels (optional overlays) | FRED API (free key): VIXCLS, DGS10, T10Y2Y, DCOILWTICO (WTI spot, not a substitute for CL futures).
Shared | Holidays / half-days | exchange_calendars or pandas_market_calendars XNYS + CME Globex energy calendar for CL.

Minimum paid stack for a one-person shop (indicative):
• Norgate US Platinum ~USD 630/yr + Futures ~USD 270/yr ≈ $75/mo equivalent. Windows-only local DB — on a Mac you run it in a small Parallels/UTM Windows VM or export ASCII nightly.
• Polygon Stocks + Options Developer ≈ $79–$199/mo depending on whether you need trades vs EOD OI.
• Benzinga calendars: typically bundled or partner-priced via Polygon; standalone Benzinga is sales-quoted (treat as $100–$300/mo indicative if bought direct).
• Databento CME Standard ≈ $199/mo (list as of Jun 2026 update) — only if you refuse Norgate continuous futures.
FRED is free. Index announcement PDFs are free. Holiday calendars are free.

## 2. Daily refresh compute time (Python + Polars, M5 Max)

These are engineering estimates on Apple Silicon, not benchmarks from a paper.

Job | Cadence | Wall time
Pull EOD ETFs + CL continuous (≤40 symbols, 5–20y stored, 1 day append) | after 18:00 ET | 10–40 s network + 1–3 s Polars
R031 mean pairwise + edge density, N ≤ 20, W = 60 | daily | <100 ms
R032 SPY–TLT 63-day corr | daily | <20 ms
R033 z-scores + tail count, M = 8 | daily | <50 ms
R034 20-day shock z | daily | <20 ms
R035 earnings join + IV rank on names reporting in ≤10 d | daily | 2–15 s (IV snapshot calls dominate)
R036 calendar ingest; no tick replay on the daily job | daily | 1–3 s
R037 month-end flag + 60/40 drift | daily | <20 ms
R038 VPace on SPY (+ optional 20 names), minute bars one session | daily | 2–8 s
R039 max-pain on SPY 5–30 strike monthly chain | daily, heavier on OpEx week | 0.5–3 s
R040 calendar join (no weight math unless announcement week) | daily | <1 s
Full daily DAG | — | 1–3 minutes typical; 5–10 minutes if Polygon is slow or you refresh 200-name IV

Intraday R036 window reconstruction (minute bars, one CPI/FOMC day) is a separate job: 5–30 s per event day, not part of the EOD loop.
128 GB is two orders of magnitude above need. A 20-asset × 5,000-day return matrix is ~1 MB.

## 3. RAM and disk budgets

Store | Budget
Working RAM, daily DAG | 2–4 GB process; peak 8 GB if you also load minute bars for one session
Unified memory headroom | leave the rest to macOS / other agents
EOD parquet (40 symbols, 25y, OHLCV + adj) | 50–150 MB
Minute bars, SPY+TLT+IEF, 2y | 1–3 GB
Options EOD OI snapshots, SPY/QQQ only, 2y | 200 MB–1 GB
Earnings + econ + index calendars | <50 MB
CL futures all contracts + continuous, 15y daily | <100 MB
Disk total comfortable | 10 GB project (data/, warehouse/, logs)
Disk if you keep Databento tick "just in case" | tens to hundreds of GB — do not; buy ticks on demand

Schema: one Parquet dataset per feed, Hive-partitioned by date, written immutable. Indicators write a second table regimes/dt=YYYY-MM-DD/.

## 4. Engineering hours — causal pipeline (one person)

Phase | Hours (illustrative-example)
Feed adapters + secret store + retry | 12–16
benchmarks.yaml freeze + Adversary unit tests | 4–6
Calendar unification (earnings BMO/AMC, econ stamps, NYSE half-days, CME roll calendar) | 16–24
Indicator library (exact formulas from Q-RB4-1) + point-in-time joins | 16–20
Continuous CL roll (volume-crossover + Panama / ratio) + audit plot | 8–12
Dual estimators + agreement gates | 8–10
Fail-safes, outage flags, no-trade windows | 8–10
DAG (Prefect/Dagster or a cron + Makefile) + Slack/email | 8–12
Backfill 10y + recon against hand-computed fixtures | 12–16
Docs + runbook | 4–6
Total to "correct causal v1" | ~90–130 hours
Ongoing per month | 4–8 hours (broken calendars, corporate actions, vendor schema drift)

"Causal" here means: no future bars in rolling windows; earnings time decides whether the event belongs to session t or t+1; index adds use announcement-date knowledge set, not effective-date prices as if known earlier.

## 5. Buy vs build (one-person research)

Layer | Buy | Build | Verdict
EOD multi-asset + delistings | Norgate Platinum + Futures (~$75/mo equiv.) | Yahoo/Stooq scrapers | Buy Norgate. Survivorship and index members are the failure mode of DIY.
ETF minutes + options OI/IV | Polygon Options Developer $79/mo indicative; Advanced $199/mo if you want real-time | OPRA yourself | Buy Polygon. OPRA is not a one-person job.
CME CL | Norgate continuous or Databento CME Standard $199/mo indicative | Roll from free daily CL quotes | Build the roll on Norgate or a cheap CL daily; buy Databento only if you need minute event studies on oil.
Earnings + econ calendar | Benzinga (direct or Polygon partner) | Nasdaq IR pages / StreetInsider scrape | Buy calendar. Timestamp errors are silent and fatal for R035/R036.
Index reconstitution list | Official S&P / Russell / Nasdaq PDFs + a parser | Guess from volume | Build a thin parser on official notices. Do not buy a $2k/mo "event" product for ten names a quarter.
Holiday calendar | pandas_market_calendars | — | Use the library.
Indicator math | — | Your Polars code | Build. The formulas are short; a vendor "regime API" will not match your definitions.
Implied-corr / GEX platform | FlashAlpha-class tools, commercial WS from thousands/mo | Not needed for R031–R040 as specified | Do not buy. R031 is realized corr; R039 is max-pain on OI, not full GEX.

Stack verdict: Buy Norgate + Polygon Options Developer + Benzinga calendars. Skip Databento until you promote R036/R034 to tick-window research. Do not buy Bloomberg/Refinitiv for this set.
Indicative monthly burn: $80–$250. Above $400 you are over-buying.

## Automated detection loop

### Agents and cadence
Treat these as named jobs, whether they are cron scripts or LLM-wrapped tools. The computer is one Mac; isolation is process-level, not cluster-level.

Agent | Owns | Cadence | Clock
ingest.eod | ETF/index EOD, CL daily, FRED | Daily | 18:15 ET (equities settled; CL may still be in Globex evening session — use prior session settle for the daily flag, stamp asof_session)
ingest.calendars | Benzinga earnings + economics; S&P/Russell RSS/PDF drop | 07:00 ET and 16:30 ET | Dual pull catches AMC revisions
ingest.minutes | SPY/TLT/IEF minutes for today | 16:10 ET | R038 VPace; R036 only if today is a stamped event
ingest.options | SPY/QQQ OI + ATM IV | 16:20 ET | R035, R039
compute.R031_R034_R037 | Pure EOD math | After ingest.eod green | —
compute.R035_R039 | Earnings join + max pain | After calendars + options | —
compute.R036_R038 | Windows + VPace | After minutes | —
compute.R040 | Add/delete dollar flow if is_rebalance_window | After calendars | —
verify.* | Second estimator | Immediately after each compute | —
adversary.benchmarks | Hash of benchmarks.yaml vs last blessed commit | Daily | Fail the DAG if the file changed without a signed changelog
publish.regimes | Write regimes.parquet + JSON snapshot | After all verifies | —

No agent is allowed to read t+1 for a flag labeled t.

### Independent verification (second estimator + tolerance)

Indicator | Primary | Second estimator | Agreement rule
R031 | ρ̄ Polars Pearson, W = 60 | numpy corrcoef on the same window | |ρ̄1 − ρ̄2| ≤ 1×10⁻⁶ (numeric); regime band flip only if ρ̄ within 0.02 of a threshold → emit AMBER, not a flip
R032 sign | 63-day Pearson SPY–TLT | 63-day Spearman | Sign must match; if Pearson |ρ| < 0.10 emit UNIDENTIFIED, do not call FTQ
R033 tail count | z vs rolling mean/std, L = 60 | z vs rolling median / MAD | Crisis flag agrees, or differ by ≤ 1 name; else AMBER
R034 z energy | CL continuous, ratio-roll | CL continuous, Panama/additive roll | |z1 − z2| ≤ 0.25; raw 20-day simple return must agree within 1 pp
R035 | Benzinga time + Polygon IVP | Second calendar (Nasdaq earnings page or Polygon Benzinga duplicate) | Same session_bucket ∈ {BMO, AMC, UNKNOWN}; IVP within 5 percentile points
R035 | Benzinga time + Polygon IVP | Second calendar (Nasdaq earnings page or Polygon Benzinga duplicate) | Same session_bucket ∈ {BMO, AMC, UNKNOWN}; IVP within 5 percentile points
R036 | Benzinga/Fed stamp | Official BLS/Fed HTML stamp | Timestamps within 60 s; if calendar missing → fallback no-trade window (below)
R037 | Last XNYS session of month | date == MonthEnd mapped through holiday calendar | Exact match
R038 VPace | Polygon minutes / 20-day same-clock | Exchange daily volume × typical U-shape fraction | |VPace1 − VPace2| ≤ 0.08
R039 K_MP | Polygon OI chain | Recompute Π(K) in a second function (no shared code) | Same strike; if two strikes tie, emit both
R040 $ flow | Official add weight × stored AUM | Weight from Norgate constituent file × same AUM | Within 10% relative

Failed verify → flag QUALITY=FAIL, do not overwrite yesterday's published regime.

### Fail-safes (the four you named, plus rolls)

Benchmark-set fixation (Adversary). benchmarks.yaml lists tickers, start dates, roll rules, and the date the set was frozen. CI hashes it. adversary.benchmarks fails the DAG if the hash changes without CHANGELOG + approved_by. Adding "just HYG because it spiked" is a hard error. A research branch may fork the file; production flags always read main.

Earnings timestamps (BMO vs AMC). Store announce_ts in America/New_York. Bucket:
• time <= 09:30 → BMO: first tradable session is that cash open. Overnight gap is tradable only if you model the open, not the previous close.
• time >= 16:00 or missing-but-AMC vendor flag → AMC: first tradable session is next cash session.
• Unknown → QUALITY=FAIL for that name; do not impute.
Close-to-close event returns do not demonstrate intraday tradability. Put that sentence in the R035/R036 report template. If the pipeline only has EOD bars, the published field is event_ret_c2c and a sibling tradable_session_ret that is null until minute data exists.

Calendar-feed outages. If Benzinga/econ pull fails twice:
1. Set calendar_source=FALLBACK.
2. Apply no-trade windows around known fixed stamps: CPI (usually ~8:30 ET, first half of month — use last year's day-of-month ±2 as a window, not a point); FOMC (pre-published Board calendar, stored locally); OpEx (3rd Friday + weekly Fridays); month-end last two XNYS sessions; Russell/S&P effective dates from a local CSV you typed from the last official notice.
3. Do not invent a print. Indicators that need the stamp go UNKNOWN.

Futures-roll handling (R034). Never splice raw CL1 Yahoo. Rules:
1. Store each dated contract (CLZ5, CLF6, …) as official settles.
2. Default continuous: volume-crossover roll — switch to next when next-month volume exceeds front for 2 consecutive sessions.
3. Adjustment: ratio (multiplicative) for return series used in z-scores; keep an unadjusted price series for "$ levels" plots.
4. Second estimator uses Panama (additive); agreement gate above.
5. FRED DCOILWTICO is a spot check only; a 5 pp 20-day divergence vs continuous CL raises ROLL_WARN.
6. Do not compute 20-day returns across an unadjusted roll gap.

Other gates worth wiring once.
• Vendor asof > computation asof → refuse.
• Half-day: R038 threshold still applies; R036 FOMC-on-half-day is rare — if calendars collide, R036 wins and R038 is tagged HALFDAY.
• R039: if OI snapshot timestamp is before the previous close, do not publish a pin flag.
• R040: dollar flow uses AUM as of last month-end, not same-day; same-day AUM is not knowable.

### What not to do on this machine
Do not stream OPRA. Do not keep CME tick history "because 128 GB." Do not let an LLM agent pick the ETF basket. Do not treat USO, ticker-level IV crush, or close-to-close earnings gaps as drop-in substitutes for the objects defined in Q-RB4-1.
The M5 Max job is a 2-minute Polars DAG and a calendar discipline problem. Spend the hours on timestamps and rolls, not on compute.

(27 sources cited by Grok on Q2.)

========== Q-RB4-3 VERBATIM ==========

# Q-RB4-3 · How R031–R040 modulate signal efficacy

Direction is stated as improves / dies / flips. Mechanisms are causal stories, not slogans. Evidence is tagged documented (paper, market, period, cost labeling) or illustrative. Classification failures are operational, not philosophical. Joint compounding is at the end of each regime and then as a matrix.

## R031 · Cross-asset correlation regime

(1) Direction and mechanism. When mean pairwise ρ̄ is high ("monoculture"), a single risk factor explains almost all return variance. Market-factor R² → 1, residual variance → 0, so idiosyncratic signals drown.
• Dies: single-name idiosyncratic alpha, pairs that assumed a stable residual, sector-rotation that is just [beta in disguise].
• Improves: index futures / ETF trend and momentum on the common factor; volatility-targeting that [sees] the corr spike; defensive overlay (puts, managed-futures crisis trend).
• Mechanism cost: stat-arb residual books look low-vol until the factor move is 4σ; then the book is a levered market [bet]. Portfolio vol identity (equal vol, equal weight): diversification at ρ̄ = 0.8 almost stops helping.

(2) Documented evidence. Crisis pairwise readings > 0.8 are a standard qualitative fact of 2008/2020 risk-asset blocs. Forbes–Rigobon (2002) is the warning that measured corr rises with vol even if the copula is unchanged — so part of "corr → 1" is a statistical artifact. [Vendor] illustrative vendor compilations, not a journal table; do not cite them as Bernard–Thomas-grade evidence. (Cited: Quantengines.)

(3) When classification fails. Short windows overstate ρ̄ in a one-week vol spike (Forbes–Rigobon). Including the same factor five times (SPY, QQQ, IWM, XLK, …) [double-counts it].

(4) Compounds with. R033 (tail co-exceedance usually [follows] the high-corr state). R032 can disagree: 2022 was high cross-asset [corr] + positive stock–bond corr (inflation), which is not flight-to-quality. R038 thin tape + high corr = g[aps].

Bottom line: sizing / stand-down for residual alpha; go-ahead for factor-trend. Not a single-name trigger.

## R032 · Flight-to-quality (stock/bond sign)

(1) Direction and mechanism. Negative ρ under equity stress means duration is a hedge, not a co-risk.
• Improves: 60/40 and risk-parity as hedges; long TLT / long ZN vs short ES; quality-minus-junk equity (flight inside the stock market).
• Dies: stock–bond momentum that assumed the 2010s negative-corr "Fed put"; levered 60/40 that is implicitly [short vol / short correlation].
• Flips: [positive ρ] (inflation / supply-shock regime), the "safe" sleeve adds [to] equity drawdown.

(2) Documented evidence. Baur and Lucey (2009/2010): FTQ is a sign change in crisis, distinct from contagion. Baele, Bekaert, Inghelbrecht, Wei: FTS days <5% of sample; bonds beat equities by [a wide margin] on those days — documented, event-day, not a strategy backtest after costs. US monthly stock–bond corr +0.18 (1926–1999) vs −0.2 (2000–Nov 2022) — documented. Amundi: pre-dot-com +0.30, post [−0.2]. These are correlation facts, not after-cost strategy IR.

(3) When classification fails. 63-day ρ = +0.35 (your example) is [not] FTQ; calling it "risk-on" is fine, calling it "no crisis" is not (inflation crises have [positive ρ]). Using bond yield change vs equity price without converting TLT to total return flips the sign. Cost of a false FTQ: y[ou size the hedge wrong].

(4) Compounds with. R034 energy shock often breaks FTQ (oil up, yields up, equities down → [positive] or chaotic [ρ]). R036 CPI/FOMC is when the sign [is] re-estimated in 30 minutes.

Bottom line: sizing input for the duration overlay. Trigger only with a concurrent equity-stress filter (R033 or vol). Stand-down the "bonds always hedg[e]" assumption when ρ is positive.

## R033 · Systemic tail / crisis

(1) Direction and mechanism. Many benchmarks breach 2.5σ the same day → the shock is common, not residual.
• Dies: carry (FX, credit, vol-selling), short-vol, mean-reversion that fades a "dip," liquidity-providing.
• Improves: convexity (long options), time-series momentum on indexes, quality/low-vol long–short, FTQ if R032 is [negative].
• [Mechanism:] leftover idiosyncratic signals become beta.

(2) Documented evidence. Systemic distress as co-exceedance — Polanski–Stoja–Chiu (BoE SWP 815). IMF (2011): systemic = severity plus contagion, not a one-country crash. These papers measure states, not a tradable after-cost strategy. The empirical fact that short-vol and carry blow up in cluster[ed tails is] illustrative unless you attach your own costed book.

(3) When classification fails. One oil print (R034) can trip three energy-heavy benchmarks and look "systemic" with [a] badly chosen [panel]. That is cherry-picking — Adversary's job. False ON: you dump carry at the lows. False [OFF: you hold carry into the crash. And] do not use open-to-close as the executable crisis return.

(4) Compounds with. Almost every other regime. R031 high corr is the slow version; R033 is the daily spike. R038 makes t[he crisis untradeable].

Bottom line: stand-down flag for short-vol / carry / fade-the-gap. Trigger for index-level convexity and trend. Never a single-name buy-the-dip trigger.

## R034 · Energy / commodity shock

(1) Direction and mechanism. A fast oil move is an inflation [or] growth shock. Mechanism: input-cost channel + discount-rate channel + positioning squeeze.
• Improves: energy long/short vs the move; commodity-trend; inflation-breakeven / short duration if the shock is [supply-driven].
• Dies: FTQ-as-default (R032), airline/consumer discretionary residual signals that ignore oil beta, vol-sel[ling into the shock].
• Flips: 60/40 from hedge to double-short when yields and oil rise together.

(2) Documented evidence. Geopolitical oil shocks: sharper price vs production, precautionary inventory, output losses on both importers and exporters (Zanetti / RIETI column on identified episodes). IMF ESR 2024: energy group h[as …]. [Treat the] journalist/practitioner [notes as such], not a costed journal strategy — label it that way. Your 18[%/20]d example is [illustrative].

(3) When classification fails. Wrong roll (unadjusted CL1 gap) fabricates a shock. USO ≠ CL. A demand shock (oil [up,] cyclicals up) is the opposite trade of a supply shock. Mis-tag cost: short duration into a growth sc[are].

(4) Compounds with. R032 (often kills FTQ). R036 (CPI prints after oil spikes). R031 (commodities correlate [with] equities in this state).

Bottom line: trigger for energy-relative and inflation-sleeve reallocation. Stand-down for default 60/40 hedge an[d carry]. Size off [the z-score], not off a news headline.

## R035 · Earnings proximity / season

(1) Direction and mechanism. Pre-event: IV is a priced lottery ticket; realized move is often inside the straddle. Post-event: un[derreaction] can still drift (PEAD).
• Pre-print, high IVP: short-vol structures improve [if] you can tolerate gap risk; breakouts die (false breaks as dealers fade). Long options [die] on crush even when direction is right.
• Post-print: [PEAD] improves for SUE-sorted books. Intraday "first print" scalps are a different object — close-to-close PEAD doe[s not] prove they are tradable.

(2) Documented evidence (label costs). Bernard–Thomas (1989, JAR): SUE decile long–short, ~60 trading days; they describe an implementable strategy with ~18% annualized before transaction costs in the first post-announcement quarter. Bernard–Thomas (1990, JAE): subsequent three-day windows around later earnings carry 25–30% of the drift. Ke–Ramalingegowda (200[5?]): 5.1% over three months after transaction costs (~22% annualized) on extreme SUE ownership-change books. IV crush frequency (~90% of events in one practitioner sample; ~20% IV contraction) is vendor/practitioner, not Bernard–Thomas. PEAD is [documented]; pre-earnings short-vol edge after costs is not settled in the same literature. (Cited: ScienceDirect +2.)

(3) When classification fails. Wrong time bucket (AMC treated as same-session) attributes the overnight gap to a session you could no[t trade] — [close-to-close returns] do not demonstrate intraday tradability. IV rank inflated by one spike ≠ rich vol. Small-cap PEAD is larger and more expensive to trade — before-cost ≠ after-cost.

(4) Compounds with. R038 half-day earnings. R036 if CPI and a mega-cap print collide. R039 if earnings land on OpEx (cru[sh vs pin]).

Bottom line:
• Pre-event high IVP: sizing input / optional short-vol trigger, never a directional trigger.
• Post-event SUE: documented drift trigger at multi-week horizon; stand-down for pretending the close-to-close gap was your fill.

## R036 · Macro announcement windows

(1) Direction and mechanism. T−60m compression: quotes pull, breaks are fake. T…T+15m [repricing]: highest genuine-information density of the month; inventory is dumped at whatever price. Digestion [: mean-reversion begins].
• [Compression:] breakout systems die; market-on-touch [orders] dies.
• Repricing window: event-driven rates/equity futures improve [if] you use limits and a pre-declared surprise model.
• Digestion: fade-the-spike sometimes improves; not a law.

(2) Documented evidence. Gürkaynak–Sack–Swanson (2005) and successors: 30-minute FOMC window (T−10m to T+20m) is the identification convention — documented event-study design, not a trading P&L. Lucca–Moench pre-FOMC drift is a related return regularity (pre-announcement), distinct from the post-print explosion. Savor–Wilson: announce[r returns are] inside the expected move even when the path is violent — vendor [note], useful as a warning that daily range ≠ tradable edge.

(3) When classification fails. Calendar outage → you treat a CPI open as a normal open. Market orders in the first 60 seconds fill at the worst print; 3–5× spread multiple is an illustrati[ve-example multiple]. Using the 08:29 last tick as "pre" and 08:31 mid as "post" on a 10-tick book is fiction. Half-day + [CPI is a special case].

(4) Compounds with. R032 (the window is when stock–bond sign is rewritten). R034 (oil in the CPI basket). R038 (pre-prin[t thin book]).

Bottom line: stand-down in compression; limit-only trigger in the 15–30 min window. Sizing: cut notionals 50–80% vs a normal open. Treat 3–5× spreads as a hard execution constraint.

## R037 · Month / quarter-end rebalancing

(1) Direction and mechanism. Mechanical "sell winners / buy laggards" at the asset-class level, plus pension cash raises.
• [Improves:] fade the sleeve that is overweight into the last sessions; TOTM (turn-of-month) long-equity after the turn.
• Dies: momentum held through the rebalance print without a flow adjustment; treating month-end as information.
• NBER w33554: 1σ calendar/threshold rebalance signal → −16 to −17 bp next-day equity [return], small +bond; calendar predictability strong at month-end, absent otherwise, stronger into quarter-end. They estimate current practices cost investors ~$16 bn/yr — documented market-level price pressure, not your after-cost book.
• Turn-of-month: mean daily return ~10 bp vs ~0 bp other days; extra at quarter and semi-year closes. Hartzmark–Solomon predictable dividend flow pressure (AER 2025 / NBER w30688) is a cousin, not the same signal. (Cited: NBER +1.)

(2) [see above — evidence integrated in (1)]

(3) When classification fails. Using calendar month-end on a Friday holiday (true close is Thursday). Assuming every month has the [same direction — e.g.,] buy-equity [when the signal says] rebalance, not sell. After-cost: 17 bp is the [gross] move; a single-name overlay with 20 bp spread does not get it.

(4) Compounds with. R040 if reconstitution = last Friday. R037 + R040: Two mechanical flows, same close — add the dollar pressures; do not double-count "edge."

Bottom line: sizing / calendar overlay, not a hero trigger. Lean against the mechanical sleeve into the last 1–2 sessions; do not confuse it with alpha.

## R038 · Thin-liquidity sessions

(1) Direction and mechanism. Same order meets less depth → more points of impact, more false breaks, more backtest fantasy.
• [Dies:] breakout, VWAP-assuming participation, any strategy whose edge is smaller than the half-day spread.
• Improves: nothing systematically except not trading and option structures that [harvest] the inflated range [if] you can get filled — usually you cannot.

(2) Documented evidence. Half-day volume ~45% of normal the day after Thanksgiving (practitioner citation of Russell Investme[nts]) — [documented via] vendor education, directionally right. There is [no] top-journal paper that says "VPace 0.55 ⇒ cut size 40%." That rule is illustrative engineering.

(3) When classification fails — this is the expensive one. Backtests that leave half-days in the sample flatter trend and mean-reversion alike: one thin print becomes a 2σ "signal." You must exclude or separately model NYSE early closes and the 24–31 Dec tape. Mis-tagging a normal lunch lull as R038 is harmless; missi[ng a real thin session is not].

(4) Compounds with. R036 pre-print. R039 last hour on a half-day OpEx. R040 close print on a short session (participatio[n math breaks]).

Bottom line: stand-down flag. If you must trade, size to participation, not to conviction. Backtest code: if halfday or VPace<0.55: [exclude / down-weight].

## R039 · OpEx / pinning

(1) Direction and mechanism. Dealer gamma around concentrated OI hedges [pulls the underlier] toward a strike into expiry (long-gamma dealers fade; short-gamma dealers chase). Max pain is the strike th[at minimizes payout] — mechanical identity, not a conspiracy.
• Improves (conditionally): fade-to-pin / short-gamma-into-positive-GEX when OI is concentrated, no macro catalyst, monthly expi[ry].
• Dies: overnight directional held through expiry "because max pain"; 2010s monthly-pin hit rates applied to [2026].
• [Note:] definition is tautological. Pinning as dealer hedge is standard microstructure narrative. There is no clean, after-cost, out-of-sample academic horse-race that says "max pain beats buy-and-h[old]."
• Daily SPX 0DTE since 2022–23 dilutes classic monthly pinning. Treat 2010s pin statistics as non-transferable without re-estimation.

(2) [Evidence:] OI snapshot stale; using weekly OI for a monthly pin; FOMC-on-Friday; computing max pain on five str[ikes is illustrative only].

(3) When classification fails. [Same as above — stale OI, wrong chain, catalyst override.]

(4) Compounds with. R036 (catalyst overrides pin). R038 (thin pin is a gap, not a drift). R040 (quad witch + reconstitut[ion]).

Bottom line: weak trigger at most, and only on monthly/quarterly expiry with fresh OI and no catalyst. Otherwise [stand down]. Re-verify pin rates on 2023–2026 data before allocating a dollar.

## R040 · Index rebalance days

(1) Direction and mechanism. Passive AUM must trade the official close. Adds are bought, deletes sold, regardless of news. Price [runs into] the print, reversal [after].
• [Improves:] pre-position the flow into the effective close if you can get out of the way of the auction; fade the post-close / next-open reversal (Dimensional's 10-second print + overnight reverse).
• [Dies:] treating the add as a fundamental upgrade the morning [after] the close; liquidity-providing [into] the close against $300 m of forced flow.

(2) Documented evidence (this is the cleanest "flow" literature in the batch). Dimensional, 10 US indices, 2014–2023: ~4% excess into reconstitution over 20 days, ~5.7% reversal over the next 20; close-auction volume 3× to 27× (Russell 2000 extreme). Intraday 2019–2023: adds +9 bp 16:00→close, reverse −13 bp by next open; deletes −30 bp [into close], +63 bp [reversal] — documented, high-frequency, US. Global 15-index update: 3.9% in / 4.4% out. These are average event studies, not after-cost live IR. Your [flow] arithmetic is the size of the [trade], not the edge. (Cited: Dimensional.)

(3) When classification fails. Trading a [style] migration (R2→R1) as a pure add. Using stale AUM. Assuming announcement-day drift is still available the morni[ng after]. [And] old once-a-year stats need a refresh.

(4) Compounds with. R037 (same Friday). R039 (triple/quad witch). R038 (if the close is a half-day). R031 (the add is a [factor exposure, not alpha]).

Bottom line: trigger for a documented, calendar-dated flow trade (pre-close with the tape, or fade the next-open reversal). Stand-down for "the committee likes this stock." Size to ADV participation, not to narrative.

## Joint compounding (how to read two flags at once)

Pair | What the combo means | What to do
R031 + R033 | True monoculture crash, not a noisy corr window | Residual books off; index convexity on
R032− + R033 | Classic FTQ | Duration overlay earns its keep
R032+ + R034 | Inflation / supply regime | Bonds are not a hedge; energy and short-duration matter
R035 + R036 | Information collision | Do not attribute the print to earnings or CPI without a window
R035 + R039 | Crush vs pin | Neither identity wins a priori — stand-down directional
R036 + R038 | Thin book + news | Limits only; first 60s untradeable
R037 + R040 | Two mechanical flows, same close | Add the dollar pressures; do not double-count "edge"
R038 + anything | Execution regime dominates signal regime | Size to VPace first
R039 + R036 | Catalyst > pin | Ignore max pain
All-on week (crisis + OpEx + month-end) | Identification is hopeless | Stand-down almost everything but hedges

A practical rule: execution regimes (R036, R038, R040 close) outrank signal regimes. If the tape cannot fill you, the alpha formula is commentary.

## Honest bottom line (one line each)

ID | Use as
R031 | Sizing / stand-down for idiosyncratic books; green light for factor-trend
R032 | Sizing input for the bond overlay; stand-down "bonds hedge" when sign is [+]
R033 | Stand-down for carry and short-vol; trigger for convexity/trend
R034 | Trigger for energy/inflation allocation; stand-down default FTQ
R035 | Pre: vol-sizing, not direction. Post: PEAD is documented at weeks–months, before/selective after costs; close-to-close ≠ fill
R036 | Stand-down in compression; limit-only trigger in the 15–30 min window
R037 | Calendar overlay / modest fade of the overweight sleeve — not a hero trade
R038 | Stand-down. Exclude half-days from backtests
R039 | Weak, conditional pin fade on monthly expiry only; do not import 2010s stats into 2026
R040 | Real flow trigger around official effective close + next-open reversal; size to ADV

If you can only wire three flags into production first: R033 (stand-down), R038 (stand-down), R040 (dated flow). Those three change P&L whether or not the rest of the chapter is ever coded.

(21 sources cited by Grok on Q3.)

========== END OF BATCH RB4 ==========
Nothing is a live-trading spec; research for the document only, as instructed.
