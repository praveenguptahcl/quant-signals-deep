# SB8 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials
- Date: 2026-09-10
- Chat: https://grok.com/c/42f77e5f-bb8f-4d23-9e72-70a2a940e864
- Batch: SB8 — Volatility & options-informed (S064, S065, S067, S068, S069, S070, S071, S072, S073, S074)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim via page text extraction.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: formulas rendered as math on the page are reproduced in standard notation; DOM-echo duplication (sentences repeated 2–3x) collapsed to one; content otherwise verbatim. Citations appear on the page as labeled source chips, not full URLs.

---

## Q-SB8-1 — formulas + worked example (verbatim)

Exact formulas below. Parameters marked example are typical market practice, not unique "correct" values.

### 1. Realized variance and bipower variation (jump-robust)

Let r_{t,i} = log P_{t,i} − log P_{t,i−1} be equally spaced log returns on day t, i = 1,…,M.

**Realized variance** (quadratic variation estimator, includes jumps): RV_t = sum_{i=1..M} r_{t,i}^2.

**Realized bipower variation** (Barndorff-Nielsen–Shephard; consistent for integrated variance under rare jumps): BV_t = mu_1^{-2} sum_{i=2..M} |r_{t,i}| |r_{t,i−1}|, mu_1 = E|Z| = sqrt(2/pi), mu_1^{-2} = pi/2.

So the working formula is: BV_t = (pi/2) sum_{i=2..M} |r_{t,i}| |r_{t,i−1}|.

Finite-sample scale (often used; example): BV_t^{adj} = (pi/2)·(M/(M−1)) sum_{i=2..M} |r_{t,i}| |r_{t,i−1}|.

Skip-k version (more jump-robust at the cost of efficiency; example k=1): BV_t^{(k)} = (pi/2) sum_{i=k+2..M} |r_{t,i}| |r_{t,i−1−k}|.

Jump contribution (non-negative part): max(RV_t − BV_t, 0).

**Practical ranges (examples)**
- Sampling: 5-min calendar time is the workhorse for liquid equity index (Andersen–Bollerslev–Diebold–Labys; Huang–Tauchen). 1-min + noise-robust methods (pre-averaging, kernel RV) on tick data. Sparse 15–30 min if microstructure is severe.
- Session: cash equities typically 09:30–16:00 ET ⇒ M ≈ 78 five-minute bins (overnight often added separately as one squared return).
- Units: leave as variance over the day, or annualize x252 (or x252xM if you first averaged per-bin). Do not mix conventions.

Sources: Barndorff-Nielsen & Shephard (2004), J. Financial Econometrics; Huang & Tauchen (2005).

### 2. Intraday GARCH(1,1)

Two common objects are not the same.

**A. Plain GARCH(1,1) on a high-frequency return series** (same recurrence as daily GARCH; Engle 1982 / Bollerslev 1986):
r_{t,i} = mu + sigma_{t,i} eps_{t,i}, eps_{t,i} iid(0,1),
sigma_{t,i}^2 = omega + alpha r_{t,i−1}^2 + beta sigma_{t,i−1}^2,
with omega > 0, alpha >= 0, beta >= 0, alpha+beta < 1. Unconditional variance omega/(1−alpha−beta). Persistence alpha+beta rises toward 1 as sampling frequency rises (temporal aggregation).

**B. Multiplicative component GARCH** (Engle–Sokalska HF-MC-GARCH; designed specification for 5- or 10-min equity returns):
r_{t,i} = sqrt(h_t s_i q_{t,i}) eps_{t,i},
q_{t,i} = omega + alpha r_{t,i−1}^2/(h_t s_{i−1}) + beta q_{t,i−1},
- h_t: daily variance (e.g. daily GARCH or HAR on RV),
- s_i: deterministic diurnal factor, s_i >= 0 (or average r^2 by clock bin),
- q_{t,i}: stochastic intradaily GARCH with E[q_{t,i}] = 1.

**Practical ranges (examples)**
- Frequency: 5–15 min for liquid names; 1 min only after deseasonalizing and noise handling.
- Estimation window: rolling 20–60 trading days of intraday observations, or expanding from 1,000 bins.
- Typical fitted numbers on 5-min equity (illustrative, not universal): alpha in [0.05, 0.20], beta in [0.70, 0.93], alpha+beta ≈ 0.90–0.99. Constrain alpha+beta < 1.
- Mean mu: often set to 0 intraday.
- s_i: U-shape; estimate by bin averages over >= 60 days.

Sources: Bollerslev (1986); Engle & Sokalska (2005), "High Frequency Multiplicative Component GARCH."

### 3. Variance risk premium (implied vs realized)

Population definition (Bollerslev–Tauchen–Zhou): VRP_{t,t+tau} = E_t^Q[∫_t^{t+tau} sigma_s^2 ds] − E_t^P[∫_t^{t+tau} sigma_s^2 ds].

Tradable / empirical proxies:
1. Ex-post (most common, fully observable at t+tau): VRP_t^{xp} = IV_{t,t+tau} − RV_{t,t+tau}.
2. Ex-ante (needs a P-forecast): VRP_t^{xa} = IV_{t,t+tau} − Ehat_t^P[RV_{t,t+tau}].

IV is model-free implied variance (Carr–Madan / Britten-Jones–Neuberger / VIX construction), not a single Black–Scholes ATM vol squared:
IV_{t,T} = (2 e^{r tau}/tau)(∫_0^F P(K)/K^2 dK + ∫_F^inf C(K)/K^2 dK) (or the discrete VIX strip),
with tau = (T−t)/365 (VIX uses 365; realized often 252 — state the convention).

A widely used 1-month proxy: VRP_t = VIX_t^2/12 − RV_{t−21,t} or VIX_t^2/12 − Ehat_t[RV_{t,t+21}]. (VIX is annualized vol in percent; VIX^2/12 ≈ monthly variance in percent-squared.)

**Practical ranges (examples)**
- Horizon: 1 month (21 trading days / 30 calendar) is the BTZ default.
- RV: 5-min + overnight, 21-day sum.
- P-forecast: HAR-RV, AR(22) on daily RV, or trailing 21-day RV (naive).
- IV interpolation: cubic spline or linear in strike / log-strike on listed puts below F and calls above F; truncate wings and use VIX-style weights.
- Sign: equity VRP is typically positive (IV > subsequent RV).

Sources: Bollerslev, Tauchen & Zhou (2009), RFS; CBOE VIX white paper; Carr–Madan (1998).

### 4. 25-delta risk reversal

Market quote (FX convention; same algebra used on equity/crypto smiles): R_25 = sigma_{25D call} − sigma_{25D put}. Units: volatility points (e.g. 0.012 = 1.2 vol points). Sign: R_25 < 0 => 25D put richer than 25D call (downside skew). Some vendors flip the sign — always label "call minus put."

Delta-to-strike (Black–Scholes, spot delta, no premium adjustment; example): Delta_call = e^{−q tau} N(d_1) = +0.25; Delta_put = e^{−q tau} (N(d_1) − 1) = −0.25; d_1 = [ln(S/K) + (r − q + sigma^2/2) tau] / (sigma sqrt(tau)). Solve K_25c and K_25p using each wing's own sigma(K) (fixed-point). Forward-delta and premium-adjusted delta are the FX variants.

Companion 25D butterfly / strangle: BF_25 = (sigma_{25c} + sigma_{25p})/2 − sigma_ATM.
Inversion: sigma_{25c} = sigma_ATM + R_25/2 + BF_25; sigma_{25p} = sigma_ATM − R_25/2 + BF_25.

**Practical ranges (examples)**
- Target: 25D (10D for far wings).
- Interpolation: linear in delta or in strike between the two listed strikes that bracket ±0.25; do not extrapolate thin wings.
- Delta type: equity index usually spot delta, q = dividend yield; FX G10 1Y often spot delta, longer-dated / EM premium-adjusted.
- Tenors: 1W, 1M, 3M, 6M, 1Y.

Sources: Clark, Foreign Exchange Option Pricing; standard FX broker pages.

### 5. Gamma exposure (GEX) per strike

Black–Scholes unit gamma (per share, per $1 spot move): Gamma = n(d_1)/(S sigma sqrt(tau)), n(x) = (1/sqrt(2 pi)) e^{−x^2/2}. Calls and puts with the same K, tau, sigma have the same Gamma.

SpotGamma / SqueezeMetrics-style dollar GEX per 1% spot move (the usual dashboard unit):
GEX_K^{call} = +Gamma_K^{call} OI_K^{call} M S^2 0.01,
GEX_K^{put} = −Gamma_K^{put} OI_K^{put} M S^2 0.01,
GEX_K = GEX_K^{call} + GEX_K^{put},
GEX_total = sum_K GEX_K.
M = 100 for standard equity options. The S^2 x 0.01 converts share-gamma into dollars of delta change for a 1% move.

Sign convention: customers net long options => dealers short both wings => call GEX +, put GEX −. This is an assumption; public OI does not identify the dealer side. SqueezeMetrics SPX version sometimes signs puts from a collar prior.

Per-$1 (not per-1%) variant drops the 0.01 and one power of S.

**Practical ranges (examples)**
- Universe: all listed strikes and expiries, or 0–45 DTE only.
- Gamma: exchange Greek if available; else BSM with mid IV, r = SOFR, q = implied yield.
- Near expiry: floor tau at 1/365 or use American/binomial Gamma.
- Report both per-strike bars and net GEX; the zero of the cumulative profile is the "gamma flip."

Sources: SpotGamma methodology notes; SqueezeMetrics GEX definition.

### Worked numerical example (synthetic; every term shown)

**A. Twelve 5-minute log returns — RV and BV**

Example returns (dimensionless; think of them as x10^−4 if you want realistic 5-min scale — algebra is identical):
r = (0.40, −0.20, 0.10, 0.30, −0.50, 0.20, 0.10, −0.30, 0.80, −0.10, 0.20, 0.15).
Squares: 0.1600, 0.0400, 0.0100, 0.0900, 0.2500, 0.0400, 0.0100, 0.0900, 0.6400, 0.0100, 0.0400, 0.0225.
RV = sum r_i^2 = 1.4025.

Absolute products |r_i||r_{i−1}| for i = 2..12: (2) 0.080; (3) 0.020; (4) 0.030; (5) 0.150; (6) 0.100; (7) 0.020; (8) 0.030; (9) 0.240; (10) 0.080; (11) 0.020; (12) 0.030.
Sum of products = 0.800.
Unadjusted BN-S: BV = (pi/2) x 0.800 = 1.256637.
Finite-sample factor M/(M−1) = 12/11: BV^{adj} = (pi/2)·(12/11)·0.800 = 1.370877.
Implied jump piece (unadjusted): RV − BV = 1.4025 − 1.256637 = 0.145863 (the r_9 = 0.80 spike is what BV down-weights).
These 12 bins are a toy day (M = 12, not 78); do not annualize this toy number.

**B. Five-strike chain — per-strike GEX and total**

Example inputs (all made up; Gamma treated as given BSM gammas so the GEX algebra is isolated): Spot S = 100; Multiplier M = 100; Scale S^2 x 0.01 = 100; Combined factor M·S^2·0.01 = 10,000.

Inputs:
- K=96: Gamma_call 0.020 OI_call 200; Gamma_put 0.040 OI_put 800
- K=98: Gamma_call 0.035 OI_call 400; Gamma_put 0.038 OI_put 600
- K=100: Gamma_call 0.050 OI_call 700; Gamma_put 0.050 OI_put 700
- K=102: Gamma_call 0.038 OI_call 600; Gamma_put 0.035 OI_put 400
- K=104: Gamma_call 0.040 OI_call 800; Gamma_put 0.020 OI_put 200

Per side: GEX = ±Gamma x OI x 10,000:
- K=96: call +40,000; put −320,000; net −280,000
- K=98: call +140,000; put −228,000; net −88,000
- K=100: call +350,000; put −350,000; net 0
- K=102: call +228,000; put −140,000; net +88,000
- K=104: call +320,000; put −40,000; net +280,000
- Total: calls +1,078,000; puts −1,078,000; net 0.

Interpretation of this toy chain: symmetric OI/gamma around ATM => net GEX is zero; below spot the put wing dominates (negative GEX / dealer short-gamma if the sign convention holds).

Caveats that change the number if ignored:
- RV/BV: sampling grid, overnight, and whether you use plain or skip-k BV.
- GARCH: diurnal s_i vs raw HF-GARCH; alpha+beta is frequency-dependent.
- VRP: VIX uses 365-day and a specific strip; RV often 252-day 5-min — convert both to the same tenor and units.
- RR: delta convention (spot vs forward vs premium-adjusted) moves the quote.
- GEX: dealer-sign assumption and 1% vs $1 scaling dominate the published figure.

---

## Q-SB8-2 — local build + buy vs build (verbatim)

Indicative 2026 list prices. Exchange SIP fees change; treat every dollar figure as "verify before you wire." Personal/non-professional use is assumed unless noted.

### What actually has to exist

- (a) RV engine: 1-min OHLCV (+ overnight) for 500 underlyings -> Parkinson/Garman–Klass/Rogers–Satchell, RV, BV, HAR, GARCH.
- (b) Options analytics: Quotes + IV + volume on a usable chain -> Surface, ATM straddle move, 25D RR, PCR, unusual-volume scans.
- (c) GEX / dealer map: Every listed strike's OI + Gamma (or mid + sigma so you can compute Gamma) -> Per-strike GEX, net GEX, flip, walls.

**(c) cannot be built honestly without full-chain open interest.** Volume is not a substitute. OI is OCC-reported, once a day (~06:30 ET, prior session OI). Intraday "live OI" products are vendor reconstructions, not OPRA truth.

### 1. Data needed and indicative pricing

**Equities / 1-min bars (layer a):**
- Polygon/Massive Stocks Starter–Developer: 1-min + 15-min delayed, $29–$79/mo.
- Polygon/Massive Stocks Advanced: Real-time SIP, $199/mo + possible SIP pass-through on business plans.
- Databento US equities Standard: usage or $199-class plan, ~$199/mo all-in for personal.
- IBKR / broker dump: 1-min bars you already pay for, $0 incremental.
- FirstRate / Norgate / Sharadar EOD: research only, $30–$150/mo.
- 500 symbols x 390 regular-session 1-min bars x 252 days ≈ 49M bars/year. Trivial on disk (few GB parquet). Overnight must be appended as its own return or RV is biased. Buy this. Do not scrape.

**Options quotes, IV, OI (layers b + c)** — three cost regimes:
A. Exchange/SIP tax (OPRA) — you pay this in addition to the vendor if the product is live OPRA:
- Non-professional display: $1.25 / user / mo.
- Professional display: $31.50 / device / mo.
- Non-display (analytics, algos, GEX batch): $2,000 / category / mo.
- Redistribution: $1,500/mo or $650 query-only.
- Direct access / connectivity: $1,000 access + ~$4,500 Cboe OPRA port (example).
If the pipeline is a local research box on delayed or EOD data, you usually avoid the $2,000 non-display line. The moment it is a live trading/risk process on real-time OPRA, assume +$2,000/mo.

B. Vendor platforms:
- ThetaData Value / Standard / Pro: full US options, OI yes (EOD OCC via OI endpoint), Greeks: Standard 1st-order, Pro 2nd/3rd. $40 / $80 / $160/mo individual. Standard is the minimum honest GEX tier (bulk OI + chain snapshots).
- Polygon/Massive Options: full listed, OI yes on paid, Greeks yes on Starter+. $29 delayed / $79 / $199 real-time individual. Business delayed quotes $499; live full market $1,999.
- Databento OPRA Standard: full tape + history; OI in stats/EOD-style schemas. $199/mo + OPRA license. Plus $1,500, Unlimited $4,000. Full tick OPRA is terabytes/day — do not pull CMBP-1 onto a Mac.
- Cboe DataShop / LiveVol: Official Cboe + OPRA-derived, OI yes in EOD / 1-min quote files, "Calcs" add-on (Hanweck). LiveVol Pro platform $350–$420/mo + SIP. Historical SPX 1-min caps ~$2,200 without Calcs, ~$3,385 with Calcs for multi-year. Delayed Cboe APIs exist; delayed OPRA redistribution is the cheap compliance path.
- IBKR OPRA L1: snapshot/stream via TWS, OI on chain snapshots, broker Greeks (not research-grade). $1.50 non-pro / ~$33 pro. Fine for 20 names, miserable for 3,000 full chains.
- SpotGamma / SqueezeMetrics / Unusual Whales: derived GEX, not raw. $89–$299/mo retail; institutional $2k+/mo. You do not get full raw OI to rebuild their number.

C. Cheaper / delayed alternatives that still let you ship (b) and a daily (c):
1. 15-minute delayed OPRA via Polygon Starter ($29) or Cboe delayed APIs — surfaces, 25D RR, straddles, volume unusual-activity. GEX only as an EOD number the next morning.
2. ThetaData Standard ($80) + EOD OI bulk — best retail "I will compute my own GEX" stack. OI is yesterday's OCC print. That is what every honest retail GEX site uses at the open.
3. Cboe DataShop EOD option summary + Calcs — pay once for history, then a small daily file. Best for backtests, not a live tape.
4. Do not use Yahoo/CBOE HTML chains for 500 names. You will be wrong on OI and banned.

**Minimum honest monthly data budget:**
- Research, delayed, personal: Stocks $29 + Options $29–$80 => $60–$120/mo.
- Live quotes, personal, compute own GEX EOD: Theta Standard/Pro or Polygon Advanced => $160–$400/mo + $1.25 OPRA.
- Live non-display GEX during the session: any live OPRA vendor + $2,000 non-display => $2,200–$4,000+/mo.
- Institutional rebuild of SpotGamma: direct OPRA + OCC + proprietary dealer-sign model => $5k–$20k+/mo before people.

### 2. Compute and RAM on a 128 GB M5 Max

The Mac is not the bottleneck. The feed and the contract count are.

Universe sizes (order of magnitude, 2026): Listed US option contracts ~1.4–1.6M. Underlyings with listed options ~6–8k. SPX + SPXW full listed chain ~20k–40k contracts in a practical snapshot; keep 0–90 DTE + ±20–30% moneyness and you land ~8k–15k rows for a usable SPX GEX. SPY or QQQ full chain ~5k–12k. Single name (AAPL-class) ~1.5k–4k. 3,000 underlyings x average 800 contracts ≈ 2.4M rows.

Snapshot size (one moment): per contract, a research row (strike, expiry, cp, bid, ask, mid, iv, delta, gamma, vega, vol, OI, oi change) ≈ 120–200 bytes packed, ~400–800 bytes as a pandas row. SPX usable chain (12k rows): 2–4 MB packed, 8–15 MB pandas-ish. 500 liquid names, clipped chain: 200–500 MB packed, 0.8–2 GB pandas. 3,000 names, full listed: 0.5–1.5 GB packed, 2–8 GB pandas.

Greeks: analytic BSM Gamma is tens of ns per contract on M5. 2.4M contracts in well under a second if IV is already there. The expensive part is implying vol from mid on every row (American tree / binomial). Budget 5–30 s for 3,000 full chains if you roll your own; vendors already ship IV.

1-min RV engine for 500 symbols: 390 bars x 500 = 195k points/day. HAR + GARCH + BV is noise on this machine. Keep 5 years in parquet: ~20–40 GB disk, <4 GB RAM if you query by symbol.

What will blow 128 GB: subscribing to raw OPRA tick/CMBP-1 (several TB/day); holding 1-second NBBO for the whole listed complex in RAM; naive dict of Python objects per contract.

What fits easily: 1-min bars + EOD full-chain OI + 1-min or snapshot quotes on 500–3,000 names; intraday GEX refresh every 1–5 minutes on clipped chains (OI is stale anyway until tomorrow).

Use Apple Silicon: Polars + parquet on SSD; Numba/Rust for IV if you insist on DIY. MPS does not help GARCH or BSM much.

### 3. Engineering hours (one senior who already knows the formulas)

- Ingest 1-min bars, corporate actions, session calendar: 20–40 h.
- RV / range estimators / BV / jump flag: 15–25 h.
- HAR-RV: 8–15 h.
- Intraday GARCH + diurnal: 25–40 h.
- Chain normalize (OSI, AM vs PM exp, SPX vs SPXW, wraps): 40–80 h. This is where projects die.
- IV solver + surface (arb-free-ish, delta interpolation): 60–120 h. American exercise, dividends, bad mids.
- 25D RR, ATM straddle implied move: 15–25 h.
- Volume PCR + unusual-volume scanner: 20–40 h.
- GEX from full OI (SpotGamma-style formula only): 25–40 h. Easy once OI+Gamma exist.
- Dealer-sign / "true" positioning: 200–∞ h. Not identifiable from public OI.
- Production: jobs, data QA, symbol master, replay: 80–150 h.
- Total DIY research stack (a)+(b)+honest EOD GEX: ~300–550 h (~2–4 calendar months part-time).
- Live tape + 3,000 names + UI: +200–400 h.

Add 30% if this is a nights-and-weekends project. Symbol master + expiries + 0DTE is the real software, not the HAR regression.

### 4. Buy vs build, component by component

- 1-min bars: Buy. Commodity. $29–$199.
- RV, BV, range estimators, HAR: Build. ~40 lines once bars are clean. No vendor is better at your sampling choices.
- GARCH(1,1) / MC-GARCH: Build (or arch / rugarch). Don't buy a "vol engine" for this.
- Raw OPRA / chains / OI: Buy. You will not beat Theta/Polygon/Databento/Cboe on capture.
- IV + first-order Greeks: Buy if live / 3,000 names; build if 50 names research. Hanweck/LiveVol/Theta Greeks exist because American IV is a time sink.
- Surface + 25D RR + straddle move: Build on bought IV. Formula work; interpolation is yours.
- Volume unusual-activity: Build. Simple. Or buy Unusual Whales if you want their flow tags.
- EOD GEX from public OI: Build (cheap) or buy SpotGamma (if you want their sign model + UI). Math is the previous message. Data is OI+Gamma.
- Intraday dealer positioning / HIRO-class flow: Buy or don't claim it. Needs trade-side, not OI. Public OI cannot tell you who is long.
- Live full-chain scanner UI: Buy LiveVol / OptionStrat / similar unless the UI is the product. 150+ hours of undifferentiated toil.

**What cannot be honestly built without full-chain OI** (non-negotiable):
1. Per-strike GEX and net GEX — Gamma x OI x multiplier x S^2 x 0.01. Missing strikes bias the flip and the walls. ATM-only or "top 20 OI" GEX is a different statistic; do not label it GEX.
2. Call wall / put wall / gamma flip — they are the argmax of that sum.
3. Strike-level put/call OI ratio and OI-change unusual activity — volume unusual-activity is a different (valid) product; it is not positioning.
4. Any "dealers must buy $X into a 1% rally" number.
5. Term-structure of GEX (0DTE vs 30 DTE) — needs OI on those expiries, not just the front.

**What you can ship without full OI (quotes only):** ATM / 25D IV, risk reversal, butterfly, straddle implied move; volume PCR, volume unusual prints, sweep detectors (if you have trades); RV/BV/HAR/GARCH; a surface on quoted strikes (wings will be holes).

**What you still cannot ship even with full OI:** true dealer inventory sign. Public OI does not identify the holder. SpotGamma/SqueezeMetrics impose a model (customers long options, or collar prior, or flow inference). Replicating their number without their model is not a data problem.

**Recommended path on this Mac:**
- Phase 0 (week 1, ~$80–160/mo): ThetaData Standard or Polygon Options Developer + equity 1-min. Pull EOD OI bulk + snapshot mids for SPX/SPY/QQQ + 50 names. Build RV engine and one GEX notebook. Prove the pipeline.
- Phase 1 (research product): 500 underlyings, EOD GEX, delayed intraday quotes, HAR. Stay non-display-off. Data $100–$250/mo. Compute is free on the M5.
- Phase 2 (live): Only if you trade it. Budget OPRA professional + non-display or accept 15-minute delay. Do not pull full tick OPRA to Austin.
- Do not build: your own OPRA handler, your own American IV farm for 3,000 names, a SpotGamma clone you intend to sell (redistribution + model + compliance).
- Buy instead of building if your time is scarce: SpotGamma or equivalent for (c), LiveVol for (b), and write only (a) plus the 25D/straddle layer yourself. That is a weekend, not a quarter.

---

## Q-SB8-3 — success ratios, after-cost efficacy, failure modes (verbatim)

All five have some published signal. None of them is an intraday money machine after spreads. Horizon and costs are the whole story.

### 1. Variance risk premium → equity returns

What is documented. High model-free implied variance minus high-frequency realized variance predicts higher future index excess returns. Bollerslev–Tauchen–Zhou (2009, RFS): over 1990–2005, VRP explains >15% of the time-series variation in quarterly market excess returns; VRP + P/E pushes in-sample R² above 25%. High premium → high subsequent returns (compensation for variance risk, not a "vol is cheap, short it" rule). The result needs model-free IV (VIX-style strip), not ATM Black–Scholes, and intraday RV, not daily squared returns.

Follow-ups (Bollerslev–Xu–Zhou 2015 JOE; international panels) keep the same shape: inside-the-year, strongest around one quarter, weaker at one month, weak-to-absent at one day. A 2026 SPY sample still finds VRP adding at the quarterly horizon in multivariate specs; standalone monthly VRP is much softer.

Honest horizon note. The best evidence is weeks to a quarter, not an intraday or even next-open overlay. Using 5-minute VRP to fade a 10:15 AM SPX dip is not what the papers test.

How people trade it (and why P&L != R²).
- Long equity / short variance when VRP is high (the BTZ return prediction).
- Or harvest the premium directly: short variance (variance swaps, short VIX futures, short SPX vol). That is a different trade: you earn the average IV−RV gap and you blow up in 2008 / Feb 2018 / Mar 2020.

Carr–Wu-type estimates of the variance premium are large (equity variance is expensive). That does not imply a high Sharpe after gaps and roll.

After-cost. Index variance is the cheap end of the complex. VIX futures / SPX weeklies: ATM spreads often 0.05–0.20 vol points on the liquid contract; still fatal if you scalp daily. Single-name VRP is not the BTZ result.

Failure regimes.
- Post-2010 / post-VIX-product era: predictability shrinks in several updates (still present at quarterly, not a 15% R² ATM).
- Using the wrong IV (BS ATM) or daily RV kills the result — BTZ say this explicitly.
- Crises: VRP explodes after the crash; the forecast is for subsequent positive equity returns, which is cold comfort if you were short vol into the gap.
- Overnight jumps are inside RV; they are not a 0DTE edge.

### 2. Straddle-implied move vs realized (event fades)

Construction. implied move ≈ (C_ATM + P_ATM)/S (or that quantity minus residual time value). Compare to |R| over the announcement window.

Documented containment / "hit rates." Across large event samples, the open (or close-to-open) after earnings lands inside the implied move on the order of ~70–75% of events — a bit above the 68% one-sigma Gaussian benchmark, i.e. implied earnings vol is on average rich. Option Alpha's ~1,500-event study: ~71% of next-day opens inside the expected move; IV crushed in ~90% of events, average crush ~20% of IV level. Pre-market prints contained more often (~81% at the open) than after-close prints (~64%).

That is a magnitude statement, not a direction statement. Per-name "beat rates" (realized > implied) vary wildly: mega-cap examples in 2026 vendor samples run from ~25% (NVDA) to ~80%+ (some healthcare/banks). A stock can be a huge mover and still close under its straddle.

Does fading the straddle make money? Mixed, and worse than the 70% headline.
- Unhedged short 3-DTE NVDA straddles into earnings since 2020: OptionStrat reports average loss ~69% — the right tail ate the crush.
- Conditioning on that ticker's last 8 quarters of realized/implied < 0.8 plus high IVR raises short-vol win rates into the high 50s / low 60s in vendor research; the complementary bucket (history > 1.2x) favors buying the straddle. These are not journal articles; treat as directional, not 63.4% gospel.
- Regimes flip: ORATS noted a 2026 earnings stretch where buyers of straddles were making ~45% while the prior 12-quarter average for that book was negative — implied was cheap relative to realized that season.

After-cost numbers (the part blogs skip). Earnings weeklies on single names: ATM straddle bid–ask of $0.20–$1.00+ on a $5–$40 straddle is routine (3–15% of mid; 10–25% on less liquid names). You sell the bid, buy the offer to cover. A "2% edge" in implied vs realized is often inside the spread. Index earnings-week SPX/SPY is tighter (pennies to dimes on weeklies) and is not the same trade as NVDA.

Failure regimes.
- Fat-tailed names (semis, unprofitable growth): mean containment with a 5x loser.
- Unhedged short delta into a gap.
- Announcement-time mismatch (AMC vs BMO).
- Selling when that ticker's own history already beats implied.
- Crowded "IV crush" seasons — 2026-style realized > implied.

### 3. Unusual options activity → stock direction

What the academic literature actually found (not Twitter screenshots). Classic signed-flow / informed-trading papers:
- Pan–Poteshman (2006) and successors: newly opened purchased puts/calls (not raw volume) predict next-week / next-month stock returns. The object is open-buy vs open-sell, which public OPRA does not flag.
- Cremers–Weinbaum (2010) call–put IV spread; Xing–Zhang–Zhao (2010) OTM-put vs ATM-call skew: both predict the cross-section over days to weeks.
- Johnson–So (2012) option-to-stock volume (O/S): high O/S precedes negative returns (informed shorting via puts/calls).
- OI-change papers (e.g. FMPM 2011): high delta-call/delta-put OI quintile outperformed the low quintile by ~52 bp over the following week in that sample.

A 2026 Journal of Portfolio Management study (OptionMetrics 2013–2023) is the honest modern update: strict UOA (extreme volume and OI vs recent history), especially OTM, short-dated calls, has significant positive abnormal returns; puts are weaker. Profitability has declined since 2020 — same-day reaction larger, post-event drift smaller (crowding). Large option trades in general are not predictive; the filter matters.

The open/close-flag problem. OPRA prints size, price, exchange, sometimes a sweep tag. It does not tell you: open vs close; buy vs sell (aggressor can be inferred from bid/ask; customer vs firm vs MM cannot); whether the print is one leg of a spread / roll / conversion.

Every retail "smart money call sweep" product is using a heuristic (ask-side + size + OI up next morning). OI prints once per day, T+1, prior-session. You cannot know at 11:02 AM whether today's 20k print opened a new long. That is why Pan–Poteshman needed CBOE Open/Close files (customer only). Without that tape, you are estimating.

Some of the published predictability is also entangled with stock-borrow / IV-spread mechanics, not "insiders bought calls." A 2025 JFE paper argues a chunk of IV-spread predictability is borrow-fee reflection.

After-cost. The signal is in OTM short-dated single-name options — exactly the wide-spread pit. Paying $0.05–$0.15 on a $0.40 contract is a 12–40% round-trip. Academic long–short equity portfolios (buy the stock, don't buy the call) survive better than trading the option that generated the print. If you chase the option, you often are the exit liquidity.

Failure regimes.
- Post-2020 crowding / same-day gap, no drift.
- Hedging flow (index puts, buy-writes, overwrites) misread as directional.
- Spreads and rolls tagged as "unusual calls."
- Illiquid names where one MM print is the whole volume.
- Using volume without next-morning OI confirmation.

### 4. GEX / pinning

Two different claims.
A. Expiration pinning (real, old, modest). Ni–Pearson–Poteshman (2005): stocks with listed options cluster at strikes on monthly expiration, consistent with MM delta-hedging. Avellaneda–Lipkin (2003) give the mechanics. Effect size is a clustering excess, not "it will close on the 450 call." It is about expiration day, high OI, individual names, not every 0DTE magnet.
B. Net GEX as a return / vol regime variable (real at daily–monthly; strike-local intraday is shaky). Soebhag (2023, J. Empirical Finance): stocks with high net gamma underperform stocks with low net gamma by about 10% annualized in a long–short; interpreted as hedge-rebalancing / risk compensation, not a pin. Needs full-chain OI x Gamma.

SqueezeMetrics-style narrative (in Market Tremors): 1-day SPX return dispersion rises when GEX crosses to negative; after a ≤ −2% day with GEX still >= 0, next-day bounce frequency ~56% with +0.87% average on up days — descriptive, not a trading system.

Gamma-squeeze event studies (AEA 2026 program paper): 669 candidate events 2019–2023, average ~5% CAR over the following month; meme subset much larger (~16–20% around initiation). That is identified squeeze episodes, not "GEX chart → buy."

Pre-registered cold water on strike-local walls. Popovici (2026): pre-registered, control-matched test of SPY intraday GEX "walls" vs rank 2–5 GEX strikes. Break-resistance, dwell/pin, vol dampening: top wall indistinguishable from other large-GEX strikes; result replicates in holdout. Consistent with gamma as a market-wide regime, not a magic strike.

Maurer (2026): dealer gamma adds overnight-gap forecast power vs HAR only in low-VIX regimes; in stress the HAR already has the information. Opposite of the "GEX matters most in crashes" sales pitch.

Full-chain OI is mandatory. GEX is sum Gamma x OI x 100 x S^2 x 0.01 with a dealer-sign assumption. Volume, "top 10 strikes," or ATM-only gamma is a different statistic. Public OI still does not identify who is long. Every published GEX number embeds that model.

After-cost. GEX is usually used to trade the underlying (ES, SPY), where spreads are tiny. The failure is false precision, not commissions. Trading the wall option itself re-introduces 5–15% spreads.

Failure regimes.
- 0DTE era: gamma dies at 4:00 PM; walls vanish; Popovici-style nulls.
- Assuming customer-long-options when the tape is buy-writes / overwriting.
- Using GEX as a directional forecast rather than a vol-of-vol / mean-reversion regime.
- Intraday "pin to 5640" as a limit order.

### 5. Put/call ratio as contrarian

Documented shape. Extreme equity put/call (retail-heavy) is a slow contrarian for the index. It is not a next-print signal.

iPresage's 2,100-day Cboe equity PCR vs SPX:
- 1-day forward: dead (top vs bottom quintile +2 bp, t = 0.38).
- 21-day forward: live — high-fear quintile +1.72% vs +0.83% low-fear, spread 89 bp, t = 2.31. Annualized ~21% vs ~10%.
- 63-day: fades (t = 1.44).
- Index PCR (SPX/SPY institutional hedges): no significant 21-day spread.

Wall Street Courier / Cboe history: sample mean equity PCR ~0.97 (2007–2022); ~5% tails below 0.72 (greed) and above 1.23 (fear). Extreme fear identified useful 30- and 60-day entries; sell signals from extreme greed were weaker.

Regime dependence.
- Works at percentile extremes, not at 0.85 vs 0.95.
- Equity PCR != index PCR. Hedging demand wrecks the index ratio as a contrarian.
- In a crash, PCR can stay high while price keeps falling (2008, COVID week 1). Contrarian too early is the failure mode.
- 0DTE / weekly boom shifted the raw level of the ratio; use percentile of a 20-day lookback, not a 1998 threshold.

After-cost. If you express it in SPY shares or ES, costs are negligible versus a 90 bp / 21-day effect. If you express it by selling the "too many calls," you pay option spreads and can be run over by the trend the sentiment is confirming, not fading.

Failure regimes.
- Using index PCR.
- Daily raw ratio.
- Mid-range readings.
- Fighting a Fed / geopolitical trend on day two of a PCR spike.

### After-cost cheat sheet (illustrative, not a quote)

- ES / SPY shares: ticks / 0.01 => negligible => VRP (equity), PCR, GEX regime survive.
- SPX/SPY weeklies ATM: 0.05–0.20 => ~0.5–3% => index short-vol, not single-name UOA.
- Liquid single-name weeklies: 0.10–0.40 => 3–10% => only large, persistent edges.
- OTM single-name "unusual": 0.05–0.20 on 0.20–0.80 => 10–40% => usually does not survive if you trade the option.
- Earnings ATM straddle, mid-cap: 5–15%+ of premium => containment stats != P&L.

Goyenko–Zhang: EOD option marks are systematically rich vs earlier-day prices because of closing demand — backtests that enter at the close on OptionMetrics mids overstate option-strategy returns by >100 bp per day/week in their comparison. Use that as a prior on any "we sold the close, mid-to-mid" earnings study.

### What to actually wire, given the evidence

- VRP: Horizon that matches papers = 1–3 months on index. Needs full-chain OI? No (IV strip + RV). Trade the option? Usually trade equity or listed vol, not 0DTE.
- Implied vs realized event: Event window; per-name history. Full-chain OI? No. Trade the option? Only if spread << historical gap.
- UOA: Days–weeks; decaying since 2020. OI change helps; open/close flags you don't have. Prefer the stock.
- GEX: Daily vol regime / monthly cross-section; not reliable intraday pins. Needs full-chain OI? Yes. Trade the underlying.
- PCR: ~2–4 weeks, equity ratio, extremes only. Full-chain OI? No. Trade the underlying.

The stack that is honest on a Mac with delayed/EOD data: HAR + VRP as a monthly overlay, equity PCR percentile as a 2–4 week overlay, EOD full-chain GEX as a regime flag, and earnings implied-vs-realized by ticker. The stack that is not honest: 5-minute VRP, "call sweep → buy the call," and "price will pin 5640 because GEX."

---

## QC notes (orchestrator)

1. Arithmetic verification (browser task checked term-by-term): RV = 1.4025 (sum of 12 squared returns); sum of |r_i||r_{i-1}| = 0.800; BV = (pi/2) x 0.800 = 1.256637; BV_adj = (pi/2) x (12/11) x 0.800 = 1.370877; jump piece = 1.4025 − 1.256637 = 0.145863. GEX per-strike nets (−280,000 / −88,000 / 0 / +88,000 / +280,000) sum to exactly 0; call-wing total = put-wing total = 1,078,000. **No arithmetic errors found** — this is the first batch with a fully clean worked example.
2. Extraction artifacts (not Grok errors): the page's text extraction duplicated sentences 2–3x (collapsed above); a few inline symbol names in the MC-GARCH subsection were dropped by the extractor and restored from standard notation.
3. Odd phrases reported exactly as rendered — look like Grok's own typos: "AMD-hours project", "AMD-SEL time", "Do not pull full tick OPRA to Austin". Flagged, not altered.
4. Citations: the UI exposes citations as labeled chips (Public.econ.duke, Papers.ssrn, Academic.oup, Quantpie, Flashalpha, Thetadata, Optionalpha, Earnings-watcher, Optionstrat, Ipresage, Orats, Researchgate, Pm-research, ScienceDirect, Dokumen, Aeaweb, Wallstreetcourier) rather than full URLs; source counts shown were Q1 "44 sources", Q2 "50 sources", Q3 "40 sources".
5. Key sourced claims are research leads, not verified facts: BTZ 2009 (VRP R² > 15% quarterly); Soebhag 2023 (high net gamma underperforms ~10% ann.); Ni–Pearson–Poteshman 2005 (expiry pinning); Popovici 2026 (pre-registered GEX-wall null); Goyenko–Zhang (EOD option marks rich, >100 bp/day overstatement); iPresage PCR 21-day spread 89 bp t=2.31. Vendor prices: indicative — verify before budgeting.
6. Notable Grok disclosure: GEX "cannot be built honestly without full-chain open interest"; dealer sign not identifiable from public OI; Popovici 2026 and Maurer 2026 cited as cold water on intraday GEX walls.

---

## Source list (only papers actually used)

- Barndorff-Nielsen, O.E. and Shephard, N. (2004), "Power and Bipower Variation with Stochastic Volatility and Jumps," J. Financial Econometrics.
- Huang, X. and Tauchen, G. (2005), "The Relative Contribution of Jumps to Total Price Variation."
- Bollerslev, T. (1986), "Generalized Autoregressive Conditional Heteroskedasticity," J. Econometrics.
- Engle, R.F. and Sokalska, M.E. (2005), "High Frequency Multiplicative Component GARCH."
- Bollerslev, T., Tauchen, G. and Zhou, H. (2009), "Expected Stock Returns and Variance Risk Premia," RFS.
- Carr, P. and Madan, D. (1998), "Towards a Theory of Volatility Trading."
- Carr, P. and Wu, L. — variance premium estimates.
- Pan, J. and Poteshman, A.M. (2006), "The Information in Option Volume for Future Stock Prices."
- Cremers, M. and Weinbaum, D. (2010), "Deviations from Put-Call Parity and Stock Return Predictability."
- Xing, Y., Zhang, X. and Zhao, R. (2010), "What Does the Individual Option Volatility Smirk Tell Us About Future Equity Returns?"
- Johnson, T.L. and So, E.C. (2012), "The Option to Stock Volume Ratio and Future Returns."
- Ni, S.X., Pearson, N.D. and Poteshman, A.M. (2005), "Stock Price Clustering on Option Expiration Dates."
- Avellaneda, M. and Lipkin, M. (2003), "A Market-Induced Mechanism for Stock Pinning."
- Soebhag, K. (2023), "Gamma Exposure," J. Empirical Finance.
- Bollerslev, T., Xu, L. and Zhou, H. (2015), JOE.
- Everything not attributed to one of the above — parameter ranges, vendor prices, worked-example values — is illustrative.
