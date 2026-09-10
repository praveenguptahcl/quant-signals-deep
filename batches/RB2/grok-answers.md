# RB2 — Grok answers (regimes R011–R020) — VERBATIM

- Batch: RB2 — Liquidity/microstructure + funding/positioning (R011–R020)
- Bot: Grok (grok.com), signed in as Praveen Gupta (praveenguptahcl@gmail.com) via x.ai email login using the saved Secure Vault credential — no OTP needed
- Date: Thu 2026-09-10 (America/Chicago)
- Chat: https://grok.com/c/934591fc-fcfd-428b-80c7-73637cdb24ab (one new chat; three questions asked sequentially, each answer waited until the streaming indicator stopped)
- Handling: research leads, not facts. Anything without a checkable source goes under `Unverified leads`, never in `Sources`.
- Transcription note (math): Grok renders formulas as math spans; the page's text extraction drops some glyphs (subscripts, division bars, multiplication symbols). Formulas below are transcribed into LaTeX from the rendered formulas — every symbol, number, and word preserved as shown on the page. Where extraction duplicated a sentence (extraction artifact), it is shown once. In Q2's verification table the page's LaTeX for R011's second estimator was mangled as "Ratio $$\sum \Delta P" / "$\Delta P$"; it is a ΣΔP/Σq (|ΔP|/|q|-style) ratio estimator, flagged in place. One internal arithmetic inconsistency in Grok's R020 worked example is flagged in place (Grok's own stated figures kept intact).
- Nothing in this file is a live-trading spec; it is research for a document.

---

## Q-RB2-1 VERBATIM

# Market-regime batch R011–R020

Every number below is tagged documented (paper / official methodology) or illustrative-example (synthetic tape used only to show arithmetic). No paper titles, URLs, or statistics are invented. Formulas exact with all symbols defined.

## R011 — Depth / liquidity-provision (book depth, Kyle's λ)

(1) Precise definition. Kyle's λ is the market maker's linear price-impact coefficient: the change in transaction price per signed net order flow. High λ = thin book / fragile liquidity provision; low λ = deep provision. Theoretically: in Kyle (1985)'s single-auction equilibrium the market maker sets price p = μ + λy where y is net order flow. Empirically λ is the OLS slope of price change on signed volume.

(2) Exact formula.
Theoretical equilibrium (Kyle 1985):
λ = σ_v / (2σ_u)
- σ_v: std. dev. of the asset's terminal value (price units)
- σ_u: std. dev. of noise-trader quantity (shares or dollars)
Empirical estimator used in applications (OLS Kyle-λ regression; standard implementation of Kyle 1985's pricing rule):
ΔP_t = α + λ q_t + ε_t
λ̂ = Σ_t (q_t − q̄)(ΔP_t − ΔP̄) / Σ_t (q_t − q̄)²
- ΔP_t: price change over bar t (currency / share)
- q_t = s_t · v_t: signed volume; s_t = +1 buyer-initiated, −1 seller-initiated; v_t share or dollar volume
- Units of λ̂: currency per share (or per dollar of flow)
Data inputs: time-stamped prices and volumes plus a trade-sign rule (tick rule / Lee–Ready / true aggressor flag).
Source: Kyle, A. S. (1985), "Continuous Auctions and Insider Trading," Econometrica 53(6), 1315–1335. Empirical OLS form is the standard implementation of that pricing rule.

(3) Ranges / bands.
- Documented functional form only: λ > 0 in equilibrium.
- Illustrative-example bands (not from Kyle 1985): "deep" [names] in the lower third of a rolling cross-section; "stressed provision" in the upper third. Absolute cutoffs [require your own history; not universal].

(4) Worked example (10-bar synthetic OLS).

| Bar | ΔP ($) | q (signed shares) |
|-----|--------|-------------------|
| 1 | +0.04 | +200 |
| 2 | −0.02 | −80 |
| 3 | +0.06 | +350 |
| 4 | +0.01 | +40 |
| 5 | −0.05 | −220 |
| 6 | +0.03 | +150 |
| 7 | −0.01 | −30 |
| 8 | +0.08 | +400 |
| 9 | −0.03 | −160 |
| 10 | +0.02 | +90 |

q̄ = 74; ΔP̄ = 0.013. Numerator Σ(q_t − q̄)(ΔP_t − ΔP̄) = 74.86. Denominator Σ(q_t − q̄)² = 361,140. λ̂ = 74.86 / 361,140 ≈ 2.07×10⁻⁴ $/share per share of signed flow.
Classification (illustrative): relative to a hypothetical rolling median [value not shown], this tape is a high-λ / thin-provision regime.

## R012 — Price-impact / Amihud illiquidity

(1) Precise definition. Amihud ILLIQ is the average daily absolute return per dollar of trading volume — "the daily price response associated with one dollar of trading volume" (Amihud 2002).

(2) Exact formula (Amihud 2002, eq. 1; often scaled by 10⁶):
ILLIQ_iy = (1/D_iy) · Σ_{d=1}^{D_iy} |R_iyd| / VOLD_iyd  (sometimes reported as ×10⁶)
- R_iyd: simple return of stock i on day d of year y (dimensionless)
- VOLD_iyd: dollar volume that day (currency)
- D_iy: number of valid days
- Units of raw ILLIQ: 1 / currency (e.g. 1/$)
Data inputs: daily close-to-close (or open-to-close) returns and dollar volume. Zero-volume days are dropped.
Source: Amihud, Y. (2002), "Illiquidity and stock returns: cross-section and time-series effects," Journal of Financial Markets 5(1), 31–56.

(3) Ranges / bands.
- Documented: Amihud multiplies by 10⁶ for numerical convenience; no universal "illiquid" cutoff in the paper.
- Illustrative-example bands (researcher-chosen): low impact = bottom tercile of the cross-section that day; high impact = top tercile.

(4) Worked example (10 synthetic days).

| Day | |R| | Dollar volume |
|-----|------|----------------|
| 1 | 0.012 | 80,000,000 |
| 2 | 0.004 | 120,000,000 |
| 3 | 0.018 | [45,000,000 implied] |
| … | | |

Daily ratios (|R|/VOLD ×10⁶): 1.50, 0.333, 4.00, 0.737, 7.333, 1.286, 0.545, 3.750, 0.500, [10th value]. Mean raw ILLIQ = 2.018. Scaled: [2.018 ×10⁶ as shown on page].
Classification (illustrative): if the name's 60-day median scaled ILLIQ is [below this value], this window is a high-Amihud / high-impact regime.

## R013 — Abnormal volume / participation

(1) Precise definition. A volume-participation regime flags when contemporaneous volume is statistically large relative to a lookback baseline — a state of unusual participation, not a signed flow measure.

(2) Exact calculation (standard construction; no single canonical paper owns "abnormal volume"). Two common, fully specified variants:
z^V_t = (V_t − μ_{V,L}) / σ_{V,L}
Turnover_t = V_t / Float
- V_t: share volume on bar/day t
- μ_{V,L}, σ_{V,L}: mean and std. of V over lookback L (excluding current t)
- Float: publicly available shares
Data inputs: volume series plus float (or ADV) for the turnover form.
Source of the idea of volume as an information/participation state: classic event-study volume work (e.g. Beaver 1968 on volume around earnings) — the z-score / ADV ratio itself is an operational definition, not a copyrighted estimator. Label bands as illustrative unless you adopt a documented threshold.

(3) Ranges / bands. Illustrative-example: [z > 2] elevated; [z > 3] abnormal participation. Turnover bands are name-specific.

(4) Worked example. Lookback volumes (shares, 9 prior days): 1.1, 0.9, 1.0, 1.2, 0.8, 1.0, 1.1, 0.95, 1.05 (millions). μ = 1.011m [approx], sample σ = 0.119m. Today V_t = 1.45m → z = (1.45 − 1.011)/0.119 ≈ 3.69.
Classification (illustrative): z ≈ 3.69 > 3 ⇒ abnormal-volume / high-participation regime.

## R014 — Informed-flow toxicity (VPIN)

(1) Precise definition. VPIN (Volume-Synchronized Probability of Informed Trading) is the rolling average absolute buy–sell imbalance on a volume clock (equal-volume buckets), used as a high-frequency proxy for order-flow toxicity (Easley, López de Prado, O'Hara 2012).

(2) Exact formula.
VPIN = Σ_{τ=1}^{n} |V^B_τ − V^S_τ| / (n·V)
Bucket size V (shares). Over a window of n completed buckets.
Bulk volume classification (BVC) for unsigned tape:
V^B_τ = V_τ · Φ(ΔP_τ / σ_{ΔP});  V^S_τ = V_τ − V^B_τ
- Φ: standard normal CDF
- ΔP_τ: price change over bucket τ
- σ_{ΔP}: std. of bucket price changes
- for full buckets V_τ = V
Data inputs: trades (price, size) sufficient to fill equal-volume buckets; a rolling σ_{ΔP}.
Source: Easley, D., M. López de Prado, and M. O'Hara (2012), "Flow Toxicity and Liquidity in a High-Frequency World," Review of Financial Studies 25(5), 1457–1493. BVC developed in the same paper / companion work. Typical implementation parameters in that literature: on the order of 50 buckets per day and a 50-bucket window.

(3) Ranges / bands.
- Documented qualitative: high VPIN associated with subsequent short-horizon volatility in the 2012 paper.
- Illustrative-example bands: < 0.3 balanced; 0.3–0.5 elevated toxicity; > 0.5 toxic. (Do not treat these cutoffs as the paper's official thresholds.)

(4) Worked example (6-bucket tape, BVC). Each bucket V = 10,000 shares; σ_{ΔP} = 0.20 (given).

| Bucket | ΔP | ΔP/σ | Φ | V^B | V^S | |V^B−V^S| |
|--------|------|--------|--------|-------|-------|---------|
| 1 | +0.30 | 1.50 | 0.9332 | 9,332 | 668 | 8,664 |
| 2 | −0.10 | −0.50 | 0.3085 | 3,085 | 6,915 | 3,830 |
| 3 | +0.05 | 0.25 | 0.5987 | 5,987 | 4,013 | 1,974 |
| 4 | −0.40 | −2.00 | 0.0228 | 228 | 9,772 | 9,544 |
| 5 | +0.20 | 1.00 | 0.8413 | 8,413 | 1,587 | 6,826 |
| 6 | 0.00 | 0.00 | 0.5000 | 5,000 | 5,000 | 0 |

Σ |V^B − V^S| = 30,838. VPIN = 30,838 / (n·V) = 30,838 / (6 × 10,000) = 0.514.
Classification (illustrative): VPIN = 0.514 > 0.5 ⇒ toxic / high-VPIN regime.

## R015 — Tick-constraint regime

(1) Precise definition. A name is tick-constrained when the quoted NBBO spread is pinned at the minimum tick size for a large fraction of the session.

(2) Exact calculation.
TickBind_T = (1/T) · Σ_{t=1}^{T} 1{Ask_t − Bid_t = τ}
- τ: minimum tick (USD 0.01 for most NMS stocks under Reg NMS Rule 612)
- T: number of quote snapshots
- Optionally: relative tick τ / S_mid
Data inputs: NBBO (or BBO) quote tape with bid, ask, timestamps.
Source of the regime concept: O'Hara, M. and Z. Zhong (2019), "Relative Tick Size and the Trading Environment," Review of Asset Pricing Studies 9(1), 47–90 (tick-constrained vs unconstrained environments). Industry definition of "tick-constrained" typically adds the relative-tick / bind-fraction qualifiers.

(3) Ranges / bands.
- Documented qualitative: large relative tick + bind fraction near 1 ⇒ constrained.
- Illustrative-example: < 0.3 unconstrained; 0.3–0.7 intermittently constrained; > 0.7 tick-constrained. Optimal quoted width of ~1.5–4 ticks is a market-design finding discussed in exchange research, not a trading-signal threshold.

(4) Worked example (10-quote tape), τ = $0.01. Spreads (cents): 1, 1, 2, 1, 1, 1, 3, 1, 1, 2. Count equals 1 tick: quotes 1,2,4,5,6,8,9 → 7 of 10. TickBind = 0.70.
Classification (illustrative): 0.70 ⇒ [at/above the 0.7 boundary] tick-constrained regime (illustrative).

## R016 — Fragmentation / off-exchange share

(1) Precise definition. Off-exchange share is consolidated volume reported to FINRA TRFs (ATS/dark + wholesaler internalization) as a fraction of consolidated volume. It is not equal to "dark-pool share": ATS-only volume is a subset, published with lag in FINRA ATS transparency files.

(2) Exact formula.
OfEx_t = V^{TRF}_t / (V^{TRF}_t + V^{lit}_t)
ATS-only (lagged): ATS share_w = V^{ATS}_w / V^{consol}_w
- V^{TRF}_t: shares printed off-exchange (FINRA facility / sale-condition "D" style prints)
- V^{lit}_t: exchange-printed shares
Data inputs: consolidated tape with venue / TRF flags; weekly FINRA ATS file for the ATS split.
Source: FINRA ATS / TRF reporting methodology (official). Market-structure descriptions consistently separate off-exchange (~40–45% of US equity volume in recent commentary) from ATS-only (~mid-teens). Those percentages are documented as recent-market descriptions, not timeless constants.

(3) Ranges / bands.
- Documented recent-market shape (descriptive, not a law): off-exchange often ~40–50% in liquid names.
- Illustrative-example regime bands for a single name vs its own 60-day median: > +10 pp = high-fragmentation day; < −10 pp = unusually lit.

(4) Worked example. Lit 32.0m shares, TRF 28.0m. OfEx = 28.0 / (28.0 + 32.0) = 0.467. If the name's 60-day median is 40%, this session is a high off-exchange / fragmented [day] (vs own median).

## R017 — Funding-stress (SOFR–OIS)

(1) Precise definition. Dollar funding-stress regime: dislocation between secured overnight funding (SOFR, NY Fed volume-weighted median of eligible Treasury repo) and a policy/term benchmark (IORB, Fed funds target, or same-tenor SOFR-OIS).

(2) Exact formula (spot overnight stress).
S_t = SOFR_t − R^{bench}_t
Common benches: IORB; midpoint or lower bound of the Fed funds target; a same-tenor SOFR-OIS rate. Quote in basis points (1 bp = 0.01 percentage points).
SOFR itself (NY Fed): volume-weighted median of eligible Treasury repo, with a specified trim of the tails [extraction abbreviated the trim detail]. Compute S as official SOFR (NY Fed) minus the chosen benchmark fix.
Sources: Federal Reserve Bank of New York, "Additional Information about Reference Rates" (SOFR methodology).
- Documented: SOFR is a transaction median, not a "stress number" by itself.
- [Illustrative bands:] ~[0–5] bp calm; 5–15 bp elevated; [>15] bp funding-stress (choose bands from the history of your chosen bench, not from a universal table).

(4) Worked example. SOFR = 5.32%, IORB = 5.15% → S = 0.17 pp = 17 bp.
Classification (illustrative vs a 5 bp calm band): [17 bp > 15 bp ⇒] funding-stress regime.

## R018 — Equity positioning / crowding

(1) Precise definition. Crowding is concentrated directional ownership relative to the name's capacity to intermediate an exit.

(2) Exact formulas (standard market definitions).
SI%Float = shares short / public float
DTC = shares short / ADV_30
Days-ADV style crowding (institutional literature): DaysADV = institutional shares held / ADV
Data inputs: FINRA / exchange short-interest file, float, 30-day ADV; 13F holdings for Days-ADV.
Source: FINRA short-interest reporting. Days-ADV / activity-ratio crowding: Conlon–Cotter–Jain and related institutional crowding work.

(3) Ranges / bands. Industry rules of thumb (treat as documented market convention, not a journal cutoff): SI% float under ~5% light; 10–20% heavy; DTC < 1 easy cover; DTC > 5 covering is impactful. Use as conventions.

(4) Worked example. Short 12.0m shares, float 80.0m, ADV30 = 2.5m. SI%Float = 12.0/80.0 = 15.0%. DTC = 12/2.5 = 4.8 days.
Classification (illustrative convention): 15.0% SI with DTC 4.8 ⇒ crowded short / elevated unwind-risk regime.

## R019 — Crypto funding-rate regime

(1) Precise definition. Perpetual-futures funding is a periodic payment between longs and shorts that anchors the perp to spot. The regime is the level (and persistence) of that rate, usually read in annualized terms.

(2) Exact payment and annualization. Payment on a settlement: Payment = f_Δ × Notional
- f_Δ: funding rate for interval Δ (e.g. 8 hours), dimensionless
- Notional: mark-price × contracts (quote currency)
Venue-style 8-hour construction (common Binance-type skeleton; confirm per venue docs): f_8h = Premium + clamp(I − Premium, −0.05%, +0.05%), with interest component I often 0.01% per 8h.
Simple (non-compounded) annualization with 3 settlements/day, 365 days: f_an = f_8h × 3 × 365. (0.01% × 3 × 365 = 10.95% — documented arithmetic used across exchange primers.)
Data inputs: venue funding prints, settlement frequency, position notional.
Sources: exchange funding specifications (Binance / Coinbase Institutional primer / CF Benchmarks funding-rate methodology).
- Documented convention: many venues pin a floor/baseline near +0.01% / 8h (~+11% ann.).
- Illustrative-example: [within a few % ann.] balanced; 20–50% crowded one-way; [>50% ann.] extreme funding regime.

(4) Worked example (as specified). Three 8-hour rates on $10,000 notional: 0.020%, 0.015%, 0.025%.
Payments: 0.00020 × 10,000 = $2.00; 0.00015 × 10,000 = $1.50; 0.00025 × 10,000 = $2.50. Day total = $6.00 = 0.060% of notional. Mean 8h rate = 0.020%. Annualized (simple): 0.00020 × 3 × 365 = 0.219 = 21.9%.
Classification (illustrative): 21.9% ann. ⇒ moderately elevated long-pays-short funding [regime].

## R020 — Options gamma positioning (GEX)

(1) Precise definition. A GEX proxy aggregates contract gamma × open interest into an estimate of dealer dollar-delta that must be re-hedged for a 1% spot move, under an assumed sign convention (typically: dealers long customer-sold calls, short customer-bought puts).
Explicit limitation (required): this proxy assumes dealer positioning and requires the full chain's OI. Open interest records that a contract exists; it never reveals who is long or short. Inverted customer flow (e.g. aggressive call buying) can flip the true sign.

(2) Exact proxy formula (SpotGamma-style dollar GEX per 1% move).
GEX_{k,j} = s_j · Γ_{k,j} · OI_{k,j} · 100 · S² · 0.01
- Γ_{k,j}: per-share gamma of contract (strike k, call/put j)
- OI_{k,j}: open interest
- 100: shares per equity option
- S: spot
- × 0.01: converts share-gamma into dollars of delta for a 1% move
- s_j = +1 for calls, −1 for puts under the standard dealer convention
NetGEX = Σ_{k,j} GEX_{k,j}. BS gamma: Γ = n(d1)/(S·σ√T).
Data inputs: full option chain (all strikes/expiries you intend to include): Γ or IVs + rates + time for BS gamma, OI, spot. Incomplete chain ⇒ incomplete proxy.
Sources: industry GEX methodology (SpotGamma convention as written in public explainers); same algebra appears in dealer-hedging literature.

(3) Ranges / bands. Sign is the regime: NetGEX > 0 long-gamma / pinning; NetGEX < 0 short-gamma / amplifying. Illustrative-example magnitude bands must be in dollars for that underlier (SPX notionals are not stock notionals). No universal dollar cutoff is documented.

(4) Worked example (5-strike synthetic chain). S = 100. Then [factor] 100² × 0.01 [= 100]. One expiry. Standard signs: calls +, puts −.

| Strike | Type | Γ | OI | raw | signed GEX |
|--------|------|------|-------|--------|------------|
| 96 | P | 0.04 | 2,000 | 800,000 | −800,000 |
| 98 | P | 0.07 | 3,500 | 2,450,000 | −2,450,000 |
| 100 | C | 0.08 | 4,000 | 3,200,000 | +3,200,000 |
| 100 | P | 0.08 | 3,000 | 2,400,000 | −2,400,000 |
| 102 | C | 0.06 | 2,500 | 1,500,000 | +1,500,000 |
| 104 | C | 0.03 | 1,500 | 450,000 | +450,000 |

(raw = Γ × OI × 100; signed GEX per the page as shown.)
NetGEX … i.e. +$0.50 million of dealer delta per 1% spot move under the assumed book.
Classification: mild long-gamma / pinning proxy regime — not observed dealer inventory.

[VERIFICATION FLAG: Grok's own figures as shown give raw signed net = −800,000 − 2,450,000 + 3,200,000 − 2,400,000 + 1,500,000 + 450,000 = −$0.5M raw, and with S = 100 the formula's ×S²×0.01 factor (= 100) would make NetGEX ≈ −$50M, not "+$0.50 million." This internal inconsistency is in Grok's answer, reproduced verbatim as requested.]

### Cross-regime note for the document
R011–R012 are price-impact cousins (flow-on-price vs |return|/dollar-volume). R014 is toxicity on a volume clock, not the same as impact. R015 is a grid constraint, not depth. R016 is venue mix. R017 and R019 are funding states in rates vs crypto perps. R018 and R020 are positioning proxies; both can be crowded while remaining silent on the true holder of the risk.

---

## Q-RB2-2 VERBATIM

# Compute stack for R011–R020 on one M5 Max / 128 GB

Universe: ~500 US names + BTC/ETH perps. Cadence: daily research refresh (not a live market-making loop). Hardware is already sunk cost; the binding constraint is licensed data + causal correctness, not FLOPs.
All vendor prices below are indicative (public list / published plan pages as of mid–late 2026). Exchange license add-ons, professional-use surcharges, and redistribution fees are the usual gotchas.

## (1) Data feeds — exact products by regime

| Regime | Minimum correct feed | Do not substitute |
|--------|---------------------|-------------------|
| R011 Kyle λ | Signed flow + ΔP. Prefer Databento trades + mbp-1 on a direct prop dataset (e.g. XNAS.ITCH Nasdaq TotalView, or Databento US Equities consolidated-from-prop). Aggressor side from prop trade flags or quote-rule Lee–Ready. | SIP CTA/UTP last-sale without reliable side. Do not infer λ from OHLCV alone except as a degraded ratio estimator, separately labeled. |
| R012 Amihud | Daily |R|/dollar volume from your daily-bar vendor of choice. | |
| R013 abnormal volume | Same daily (or 1-minute) volume + float. Float: Massive reference / Nasdaq Trader / Compustat-lite. | ADV computed on raw share count with no float. |
| R014 VPIN | Trades with price + size, bucketed in volume time. Same Databento trades as R011. BVC does not need Lee–Ready if you use ΔP/σ over the bucket. | Minute bars only (wrong clock). |
| R015 tick-bind | Time-weighted NBBO width. Databento mbp-1 / cbbo / tbbo. Tick size from Databento definitions or SEC tick-pilot / listing-exchange tick table. | Daily OHLC "low–high." |
| R016 off-exchange | Intraday: SIP/prop tape sale conditions → TRF prints vs lit. Databento US Equities includes ATS prints in the consolidated feed [but does not expose] named-pool IDs in real time. Named ATS share: FINRA OTC / ATS Transparency weekly files (otctransparency.finra.org, machine download). | Calling TRF% "dark pool %." |
| R017 SOFR–OIS | NY Fed Markets Data API (keyless): SOFR, EFFR, OBFR, BGCR, TGCR, SOFR averages. Bench: FRED (IORB, Fed target bounds) and/or a mid from a rates vendor if you need term OIS (CME / Databento CME if you already pay CME). | LIBOR leftovers. |
| R018 crowding | FINRA short interest (biweekly, lagged) + float + ADV. Optional daily securities-lending proxy (S3 / Ortex / IHS Markit — institutional). CFTC COT TFF via publicreporting.cftc.gov SODA (free, Friday for prior Tuesday). | Using short volume (daily FINRA short-sale file) as if it were short interest. |
| R019 crypto funding | Venue APIs, not a composite fantasy: Binance USD-M GET /fapi/v1/fundingRate + premium index; Bybit /v5/market/funding/history; OKX funding-rate history. Keep per-venue series. Mark price + OI from the same venue. | Coingecko "average funding" without venue tags. |
| R020 GEX proxy | Full chain OI + IV/Greeks + spot. Practical one-person stack: Massive Options chain snapshot (/v3/snapshot/options/{ul}) — greeks, IV, OI. Research-grade ticks: Databento OPRA.PILLAR CMBP-1 / trades (OI still needs OCC/OPRA statistics or Massive OI). | 1–2 strikes or volume-as-OI. |

Reference / corporate actions (shared): split/div/float calendar — Massive reference or Databento definitions. Without it, Amihud and Kyle level comparisons break across splits.
Documented lags (do not "fix" them): FINRA ATS weekly: ~2 weeks for NMS Tier 1, ~4 weeks Tier 2/OTC (FINRA). Short interest: ~8 trading-day publication lag (FINRA cycle). CFTC COT: Tuesday positions, Friday publish.

## (2) Daily refresh time (Python + Polars, M5 Max)

These are engineering estimates for a correct daily batch after data is already on NVMe, not including first-time history download.

| Job | Work | Wall clock (illustrative) |
|-----|------|---------------------------|
| Ingest + partition previous session (500 names, trades + mbp-1 top, 1 venue or DBEQ) | scan parquet, cast, sort | 8–25 min |
| R011 Kyle OLS (1-min or 5-min bars, 500 names) | Polars group-by + tiny lstsq | 1–3 min |
| R012–R013 daily | trivial | <30 s |
| R014 VPIN (50 buckets/day × 50-bucket window) | volume clock + Φ | 2–8 min |
| R015 tick-bind on mbp-1 subsample (1s BBO) | time-weight | 3–10 min |
| R016 TRF vs lit from sale conditions | group-by flag | 1–4 min |
| R017 SOFR pull | HTTP | seconds |
| R018 SI / DTC / COT | join + lag tag | seconds–1 min |
| R019 2 perps × 2–3 venues | HTTP | seconds–1 min |
| R020 GEX 500 chains (snapshot greeks, not ticking OPRA) | 500 REST/flat files | 5–20 min |
| Second estimators + QA report | | 3–8 min |
| Total daily refresh | | ~25–80 min typical; 2–3 h if you rebuild VPIN + Kyle from raw trades every day with no incremental cache |

Apple Silicon note: Polars + Arrow is fine on M5 unified memory. Bottleneck is decode + shuffle of tick parquet, not matmul. Keep files snappy/zstd parquet, partitioned date=/symbol=. Avoid pandas for the tick path.
First-time backfill (1 year ticks, 500 names, one L1 schema) is a multi-hour to overnight download + convert, dominated by vendor I/O and disk, not CPU.

## (3) RAM and disk

RAM (128 GB is comfortable if you never load the full-tape day for all 500 names at once).

| Working set | Budget |
|-------------|--------|
| Polars scan of one date × 500 names, trades only | 8–20 GB |
| Same + mbp-1 top-of-book | 15–40 GB |
| Naive "read all ticks into RAM" | can exceed 128 GB — don't |
| Options chain snapshots 500 names | 2–8 GB |
| Headroom for two estimators + browser | leave 32 GB |

Rule: stream by date then by symbol batches of 50.
Disk (illustrative, compressed parquet):

| Store | 1 year | 5 years |
|-------|--------|---------|
| Daily OHLCV + reference, 500 names | ~1–3 GB | ~5–15 GB |
| Trades (L1) 500 liquid names | 0.4–1.5 TB | 2–8 TB |
| mbp-1 / 1s BBO 500 names | 0.3–1.0 TB | 1.5–5 TB |
| Options EOD chain + OI/greeks (not OPRA ticks) | 20–80 GB | 100–400 GB |
| OPRA full ticks (if you buy it) | multi-TB / year — usually out of scope for one-person daily GEX | |
| Crypto funding + marks | <1 GB | <5 GB |
| Feature store (indicators, vintages) | 5–20 GB | 20–80 GB |

Practical disk for this project: 2 TB internal + 4 TB external if you keep 1 year of L1 + full daily/EOD history. Going to multi-year L2/MBO is a different machine room.

## (4) Engineering hours (one person, correct causal pipeline)

Causal means: no same-bar future volume in VPIN buckets that close after the decision time; FINRA/SI publication timestamp, not event timestamp; GEX uses prior session OI (OI is T+1 OCC-style) unless the vendor documents intra-day OI.

| Phase | Hours (illustrative) |
|-------|---------------------|
| Contracts, vendor QA, schema maps, calendar | 15–25 |
| Lake layout, ingest, adjustments | 25–40 |
| R011–R015 microstructure jobs + unit tests on synthetic tapes | 40–60 |
| R016 TRF flags + FINRA vintage joiner | 15–25 |
| R017–R019 (easy if APIs stay up) | 8–15 |
| R020 GEX + strike filters + "<5 liquid strikes" gate | 15–25 |
| Dual estimators, tolerances, fail-safes, dashboards | 25–40 |
| Paper-ready documentation of vintages | 10–15 |
| Total to v1 research-grade | ~150–250 hours |
| Ongoing: vendor breaks, symbol changes, QA | 3–6 h/week |

Skipping dual estimators and vintage tags can cut hours in half and make the document unusable.

## (5) Buy vs build — indicative monthly $ and verdict

| Piece | Build | Buy (indicative list) | Verdict for one researcher |
|-------|-------|----------------------|---------------------------|
| US L1 trades + BBO | You cannot "build" the tape | Databento US Equities Standard ~$199/mo (live + 1y L1 in-plan; extra history usage-based). Plus/Unlimited ~$1,500–$4,000/mo. Direct Nasdaq TotalView real-time is a different license tier. | Buy Databento Standard (or usage-based history only if batch-only). |
| Daily bars / float / SI-friendly fundamentals | Possible from free scraps, dirty | Massive Stocks Starter/Developer ~$29–$79/mo (indicative, individual) | Buy cheap or use Databento OHLCV-1d if already subscribed. |
| Options OI + greeks EOD | Rebuild BS + hunt OCC OI | Massive Options Starter/Developer ~$29–$79/mo; Advanced ~$199/mo. Business ~$1,999/mo. Databento OPRA Plus ~$1,500/mo (indicative). Cboe DataShop historical windows are project-priced (caps exist). | Buy Massive Options Developer for GEX proxy. Do not buy full OPRA ticks unless you need microstructure on options. |
| FINRA ATS / short interest | Download + parse | FINRA site; professional bulk may need a subscription (confirm current FINRA fee schedule — often modest) | Build the parser, pay FINRA if required. |
| SOFR / FRED / CFTC | Trivial | Free official APIs | Build (50 lines + retry). |
| Crypto funding | Trivial | Venue APIs free; aggregators optional | Build multi-venue, no vendor. |
| Lending crowding (daily) | Cannot replicate | Ortex / S3 / Markit: typically high hundreds to low thousands $/mo (indicative; quote) | Skip for v1; use lagged FINRA SI + DTC. |
| "Regime platform" SaaS | — | Nasdaq / Bloomberg / SqueezeMetrics-type GEX products: institutional, often $1k–$5k+/mo (indicative) | Do not buy for 10 homemade definitions. |

One-person stack (indicative cash cost): Databento Equities Standard ~$200 + Massive Options ~$80 + Massive Stocks if needed + FINRA if any = $250–$400/mo. Jump to Databento Plus + OPRA Plus only if you redistribute or need deep history on-plan (~$3k/mo).
Verdict: Buy the tape and the options snapshot. Build every estimator, vintage store, and QA loop. Do not buy a black-box "regime API." Do not build your own SIP consolidator.

## Automated detection loop

Treat this as a batch DAG (Prefect/Dagster/launchd), not a chat agent "deciding" λ. Agents are orchestrators + checkers.

### Cadence and owner

| Indicator | Compute agent | Cadence | Decision time (causal) |
|-----------|--------------|---------|------------------------|
| R011, R014, R015 | agent.micro — Polars jobs on yesterday's session 09:30–16:00 ET | T+0 evening after tape sealed (~17:30–20:00 ET) | Features dated session D, usable before D+1 open |
| R012, R013 | agent.daily | T+0 evening (or T+1 06:00 if you wait for official volume) | Session D |
| R016 tape split (TRF vs lit) | agent.micro | T+0 evening | Session D |
| R016 named ATS | agent.finra | Weekly, when file appears | Feature date = week-of-activity; asof date = publication date (T+~14d Tier 1) |
| R017 | agent.rates | Weekdays ~08:30 ET after NY Fed print (SOFR is T+1 publish for value date — use NY Fed calendar) | Stamp both value_date and print_date |
| R018 SI | agent.finra_si | Twice monthly on FINRA release | si_asof ≠ si_published |
| R018 COT | agent.cftc | Friday 15:30 ET | Tuesday snapshot, Friday vintage |
| R019 | agent.crypto | Every funding print (8h or 1h) + daily summarize | Venue clock |
| R020 | agent.gex | T+0 after Massive/OCC OI settles (often T+1 morning for official OI) | Document OI vintage |

A thin agent.qa runs after each compute agent and writes qa/{date}/{regime}.json.

### Independent verification (second estimator + tolerance)

| Regime | Primary | Second estimator | Agreement rule (illustrative; tune on your tape) |
|--------|---------|-----------------|--------------------------------------------------|
| R011 | OLS λ on 5-min signed volume | [Page's LaTeX rendering mangled here — shown as "Ratio $$\sum \Delta P" / "$\Delta P$":] ΣΔP/Σq (|ΔP|/|q|-style) ratio estimator | [agreement rule text not captured in the extracted cells] |
| R012 | Amihud close-to-close | Amihud open-to-close (Barardehi et al. critique) | Rank corr across 500 names > 0.8 or flag |
| R013 | z vs 20d mean | z vs 20d median; turnover vs float | Same tercile for ≥90% of names |
| R014 | BVC + Normal Φ, 50×50 | BVC + Student-t or tick-rule imbalance VPIN | [difference] < 0.08 else flag |
| R015 | 1s BBO bind fraction | Trade-time bind (spread at last print) | abs diff < 0.10 |
| R016 | TRF share from tape | 1 − lit share from venue IDs | abs diff < 2 pp |
| R017 | NY Fed JSON | FRED SOFR series | abs diff < 0.5 bp |
| R018 | SI% float | DTC; optional COT for index | SI file hash + share count vs prior release Δ reasonableness |
| R019 | Venue A 8h rate | Same timestamp from venue status endpoint; annualization two ways (3×365 vs 365/Δ) | rate match 1e-6; notional payment identity |
| R020 | Massive greeks × OI × 100 × S² × 0.01 | Recompute Γ from vendor IV with BS; drop expiries >30d and rerun | NetGEX sign match; relative gap < 25% or name gated |

Failed agreement → status DISPUTED, indicator not written to the "tradable features" table.

### Fail-safes you asked to cover

L1/L2 unavailable / SIP-only temptation
- If mbp-1 or prop trades are missing: do not infer depth or λ from SIP last-sale + "implied size."
- Write R011=NULL, R015=NULL, depth_source=UNAVAILABLE.
- R012/R013 may still run from official daily volume.
- Log NO_SIP_DEPTH_INFERENCE=1 as a hard rule in agent.micro.

FINRA staleness (~2 weeks)
- Every ATS/SI row carries activity_week, published_ts, lag_bdays.
- Research joins use merge_asof(published_ts).
- A dashboard that plots ATS% on calendar day D without the vintage ribbon is a pipeline bug.
- Tier 2 names: expect ~4-week lag; separate tier field.

Crypto exchange API outages
- Fan-in ≥2 venues. If Binance 5xx: use Bybit/OKX and mark coverage=PARTIAL.
- If all venues fail for a window: last good rate with stale_hours; if stale_hours > 16 (two missed 8h prints), R019=NULL with the stale-hours annotation [page text truncated here — exact null-reason wording not captured; the rule shown is: two missed 8h prints ⇒ null the funding indicator].
- Never fill funding with 0.01% "default interest" unless the venue formula says the clamp produced that rate — and then still tag it CLAMP_DEFAULT.

Single-name GEX with <5 liquid strikes
- Liquid strike rule (illustrative, document it): OI ≥ 100 [contracts]; bid-ask / mid < 20%; both sides present.
- If countable liquid strikes < 5: R020=NULL, reason THIN_CHAIN.
- Do not emit a net GEX from 2 meme strikes.
- Index ETFs (SPY/QQQ) will almost never hit this gate; single names will, often.

Other required fail-safes
- Clock: all equity jobs in America/New_York; crypto in venue TZ + UTC store.
- Corporate actions: halt R011/R012 level comparisons across unadjusted splits.
- Partial universe: job succeeds if ≥95% of 500 names complete; else RUN_INCOMPLETE.
- Disk watermark: stop ingest at 90% volume.
- Determinism: store code_git_sha, data_manifest_hash, params.json with every run.

### Minimal "done" definition
A day is publishable when: tape + options snapshot + SOFR print are present; dual estimators agree in tolerance; FINRA fields carry as-of published [vintage tags]; thin GEX names are nulled; no SIP-invented book. Until then the feature store row stays PROVISIONAL.

---

## Q-RB2-3 VERBATIM

# How R011–R020 modulate strategy efficacy

Cost labeling used below: gross = before spreads/fees/impact; net = after those costs when the paper reports them. If a paper is silent on costs, it is labeled gross / costs not reported. No invented multiples, paper titles, or sample stats.

## R011 — Depth / Kyle λ

(1) Direction and mechanism. High λ means each unit of signed flow moves price more (Kyle 1985 linear pricing rule p = μ + λy).
- Dies / degrades: large aggressive entries, TWAP that is still a non-trivial fraction of depth, statistical-arbitrage that assumes mid is resilient, passive size that must be pulled when adverse selection rises with λ.
- Survives / improves (relatively): small clips, liquidity-taking only when edge ≫ λ·size, maker strategies that widen with λ rather than quote the old spread.
Mechanism: expected impact cost ≈ λ × signed size; capacity of any signal is O(1/λ).

(2) Documented evidence. Kyle (1985), Econometrica — theory, not a trading P&L study. Empirical Kyle-λ regressions are used throughout microstructure (e.g. monthly firm-level OLS of ΔP on signed volume). Hasbrouck-style variance decompositions treat λ as the information component of the quote. Gross / structural. There is no single "high-λ kills momentum by X%" table in Kyle (1985).

(3) When classification fails. Unsigned volume × sign(return) is not order flow. SIP-only last sale without aggressor side mis-estimates q. OLS on 10 noisy bars is unidentified. Split days without adjustment look like λ spikes. Estimator disagreement (OLS vs |ΔP|/|q| ratio) is common on quiet days — treat λ as undefined, not zero.

(4) Compounds with. High λ + high VPIN (R014) = impact and adverse selection. High λ + tick-bind (R015) = you pay a full tick and move the book. High λ + high Amihud (R012) should agree; if they disagree, data problem.
Bottom line: sizing input and stand-down for size. Not a direction trigger.

## R012 — Amihud illiquidity

(1) Direction and mechanism. High ILLIQ = large |return| per dollar traded (Amihud 2002).
- Improves (gross, long-horizon): holding illiquid names if you are the long-horizon clientele in Amihud–Mendelson (1986) — you earn an illiquidity premium.
- Dies (net, short-horizon): daily/weekly long–short that must turnover the high-ILLIQ leg (Novy-Marx / Velikov-type cost critiques of anomalies generally: many "premia" shrink after costs; apply that logic here even when a paper is about another anomaly).
Mechanism: required return rises with expected trading cost; realized strategy return falls with actual turnover × cost.

(2) Documented evidence. Amihud (2002), J. Financial Markets — expected market illiquidity forecasts ex ante stock excess return; unexpected illiquidity associated with contemporaneous negative returns. US daily CRSP-style sample in that paper. Gross daily ratios; implementation costs of a traded ILLIQ portfolio not the paper's object. Amihud–Mendelson (1986), JFE — spread-based clientele theory. Pástor–Stambaugh (2003) and the 2019 Critical Finance Review replications: market-wide liquidity risk premium, with sharp liquidity drops in 2008 — related family, not identical to firm ILLIQ.

(3) Failures. Overnight |R| with RTH-only volume inflates ILLIQ (Barardehi, Bernhardt, Ruchti, Weidenmier, RAPS — "Night and Day of Amihud"). Zero-volume days, penny names, and unadjusted splits. Cross-sectional ranks are stabler than raw levels.
Bottom line: sizing / universe filter for high-turnover systems; not a standalone long-illiquid trigger after costs.

## R013 — Abnormal volume / participation

(1) Direction and mechanism. Volume is a participation state, not a sign.
- Improves: event-driven and information-release strategies (earnings, index adds) where volume is the event; VWAP/POV algos that scale with capacity.
- Dies: mean-reversion that assumed "volume = climax = reversal" without a signed-flow overlay; breakout systems that treat all volume spikes as continuation.
Mechanism: high volume can be either information arrival or mechanical rebalancing (Beaver 1968 volume-around-earnings is the classic information-volume link — gross association, not a strategy backtest).

(2) Documented evidence. Beaver (1968) and the event-study volume literature: volume rises around information events. Index-reconstitution work (e.g. documented S&P add/delete price-pressure and poor close-print execution) shows scheduled volume can be costly for passive/mechanical flow — net costs discussed in practitioner reconstitution studies; academic add-effect papers vary in cost treatment. Do not cite a universal "z>2 ⇒ +X bp alpha."

(3) Failures. Lookahead if z uses a window that includes today. Open/close auction volume is a different process than continuous session. Crypto "volume" on some venues is wash-prone — label reported_volume.
Bottom line: context flag. Combine with R011/R014 for direction; never a solo trigger.

## R014 — VPIN toxicity

(1) Direction and mechanism. High VPIN = one-sided informed (or informed-looking) flow in volume time. Market makers who keep quoting are adversely selected (Easley, López de Prado, O'Hara 2012).
- Dies: passive fill-the-book market making, rebate capture, tight-spread pinging.
- Improves (defensively): widen / pull quotes; switch from make to take only with a short-horizon directional edge; volatility-breakout after toxicity resolves, not during.
Mechanism: toxicity → MM withdrawal / wider markets → subsequent short-horizon volatility. The 2012 paper's object is toxicity-induced volatility, not a numbered "spreads ×2–3" law. Do not treat "2–3× spreads" as documented.

(2) Documented evidence. Easley, López de Prado, O'Hara (2012), RFS 25(5): VPIN construction, BVC, application to high-frequency toxicity. Companion Flash Crash microstructure piece (Easley, López de Prado, O'Hara 2011, Journal of Portfolio Management): VPIN on E-mini elevated in the hours before the 6 May 2010 crash — documented precedent for a toxicity warning, not a controlled strategy test. Gross / event study, not after-cost MM P&L. Subsequent literature debates VPIN's robustness (parameter sensitivity, classification); treat out-of-sample claims as contested.

(3) Failures. Wrong bucket size; clock-time bars instead of volume buckets; BVC vs tick-rule disagreement; using VPIN as a directional long/short (it is unsigned toxicity). Lookahead if buckets that close after the decision time are included.
Bottom line: stand-down flag for passive liquidity provision. Not a directional trigger.

## R015 — Tick constraint

(1) Direction and mechanism. Bind fraction near 1: the grid, not the economics, sets the inside quote (O'Hara and Zhong 2019). Queue priority and undercutting dominate.
- Improves: queue-position / maker-rebate strategies on constrained names if you can hold the queue; mid-point / dark / periodic auctions that skip the tick.
- Dies: penny-jumping, "improve by one tick" taker logic when one tick is the whole spread; signals that assume continuous prices.
- Heterogeneous: widening the tick hurt names that were already tight and helped very wide-spread names (Tick Size Pilot).

(2) Documented evidence. O'Hara and Zhong (2019), RAPS — relative tick changes HFT MM behavior and depth in constrained vs unconstrained environments. SEC Tick Size Pilot (started 3 Oct 2016): Chung et al. and others — quoted/effective spreads up for small orders on treated small-caps (costs rose for takers; gross spreads, i.e. the cost measure itself). Barardehi, Dixon, Liu, Lohr (SEC DERA / 2022 working paper): TSP harmed quality for stocks with quoted spreads ≲ 9–10¢ and improved it for spreads ≳ 15¢. Nasdaq market-structure notes: constrained names cluster at 1-tick NBBO.

(3) Failures. Using daily high–low as spread. Ignoring odd-lot / sub-penny midpoints. Regime flips when price crosses $1 / listing-tick thresholds. Pilot results do not transfer 1-for-1 to mega-caps that were never in the pilot.
Bottom line: microstructure routing / make-vs-take switch, not an alpha trigger.

## R016 — Fragmentation / off-exchange share

(1) Direction and mechanism. High off-exchange share = more of the tape is internalized or ATS-crossed, so displayed depth is a worse map of true liquidity.
- Dies: strategies that only read the lit book for "size at touch"; naive impact models calibrated on lit prints.
- Improves: midpoint / conditional / SOR that can access wholesaler or ATS liquidity; block-aware execution.
Mechanism: information and size migrate off-display; lit λ can look worse than all-in cost (or vice versa).

(2) Documented evidence. FINRA ATS/OTC transparency methodology and lag schedule (Tier 1 weekly ~2 weeks, Tier 2/OTC ~4 weeks) — documented operational fact, not a return study. CFA Institute / SEC market-structure descriptions of dark + internalization as a large slice of consolidated volume. Recent tape measurements of off-exchange share of volume in liquid names often sit in the ~40–50% range — descriptive, gross, not alpha. Academic dark-pool papers generally find mixed effects on lit spreads (cream-skimming vs dark-improves-total-welfare); do not claim a single signed alpha.

(3) Failures. Calling TRF volume "dark pool." Using the weekly ATS file as if it were session D (lookahead / stale vintage). Retail internalization inflates off-ex % without institutional intent.
Bottom line: execution / routing input. Stand-down on lit-only impact models when OffEx is extreme vs the name's own history.

## R017 — Funding-stress (SOFR–OIS / SOFR–IORB)

(1) Direction and mechanism. SOFR rich to the policy / OIS bench = secured overnight funding is scarce or dealer balance sheets are tight.
- Dies: leverage-intensive relative value, basis trades that roll repo, high-turnover stat-arb that implicitly funds overnight.
- Improves (as a risk-off filter): cut gross exposure; favor unlevered cash-equity signals.
Mechanism: Brunnermeier–Pedersen market liquidity and funding liquidity (2008, RFS) — funding stress tightens haircuts → fire-sale spirals → market liquidity dries (connects R017 to R011/R012). OFR FSI documentation explicitly moved stress legs onto SOFR products post-LIBOR.

(2) Documented evidence. NY Fed SOFR methodology (transaction median of Treasury repo). Brunnermeier and Pedersen (2008) — theory + crisis narrative, not a SOFR-OIS backtest (SOFR did not exist in 2008; LIBOR–OIS was the stress gauge then). Sep 2019 US repo spike and Mar 2020 dash-for-cash are documented funding-stress episodes in official and academic accounts. Do not invent a "SOFR–OIS > X bp ⇒ momentum Sharpe falls by Y" number.

(3) Failures. Mixing value date and publication date (SOFR is published T+1). Using SOFR level instead of a spread. Treating a 2 bp wrinkle as 2019-style stress.
Bottom line: stand-down / de-lever flag for funded strategies. Not a directional equity trigger.

## R018 — Equity positioning / crowding

(1) Direction and mechanism. Crowded longs: exits hit a small door (Days-ADV). Crowded shorts: squeeze / DTC risk.
- Dies: generic momentum implementation when the book is crowded — especially the short leg of WML after a market panic, when losers rebound (Daniel and Moskowitz 2016).
- Improves: crash-timing overlays on momentum (Daniel–Moskowitz: crashes cluster after lagged market declines, high vol, contemporaneous rebound); squeeze-aware short placement.
Mechanism: synchronized exit + option-like loser beta in panics; Lou–Polk comomentum (pairwise residual correlation inside the momentum book) as a crowding proxy that forecasts subsequent crash severity (documented research line; treat magnitudes as paper-specific).

(2) Documented evidence. Daniel and Moskowitz (2016), JFE, "Momentum crashes" — US and international/asset-class WML; worst months after two-year market decline, in months the market rises; 1932–39 and 2009–13 highlighted drawdowns. Gross factor returns (CRSP-style), not live-net-of-borrow. Barroso and Santa-Clara (2015), JFE — momentum risk scaling. Stein (2009) and Barroso–Edelen–Karehnke crowding/tail-risk work — crowding can induce crash risk when traders are myopic. Short-interest predictability: Asquith–Pathak–Ritter / Desai et al. / Rapach–Ringgenberg–Zhou line — high SI associated with low subsequent gross returns (informed shorts), costs of borrow often not fully netted.

(3) Failures. Biweekly SI used as if live. Short volume ≠ short interest. Vendor "crowded score" 0–100 is proprietary. 13F is 45-day stale. Squeeze narratives without DTC and borrow are folklore.
Bottom line: sizing and stand-down on the crowded implementation, especially momentum shorts after a panic. Not "fade every high SI name."

## R019 — Crypto funding-rate

(1) Direction and mechanism. Positive period funding: longs pay shorts. Persistent rich perp = crowded long leverage.
- Improves: cash-and-carry (long spot / short perp) that harvests funding; reducing naked longs when carry is a large fraction of expected move.
- Dies: high-leverage trend longs that ignore carry; treating 0.01%/8h as "zero."
Mechanism: funding is a direct P&L line (rate × notional per interval). Coinbase Institutional primer: OI-weighted BTC funding positive a large majority of the time across CEXs in their two-year window — descriptive; they also note association between changes in funding and subsequent price trends (chart-level, not a published after-cost Sharpe).

(2) Documented evidence. Venue specs (Binance-style premium + clamp + 0.01%/8h interest). Annualization 0.01% × 3 × 365 = 10.95% — arithmetic identity. Academic pricing: perpetual as funded contract (e.g. He, Jia, et al. / arXiv perpetual-futures pricing). Strategy evidence is thinner than equity-factor literature; label harvest-funding results as venue-P&L identities plus whatever sample you run yourself.

(3) Failures. Aggregator "average funding" without venue (use reported_funding_{venue}). Public liquidation dashboards are lower bounds (not all venues, not all sizes) — label reported_liqs. 1h vs 8h display units. API outage filled with the 0.01% pin.
Bottom line: carry overlay and sizing. Extreme persistent funding is a crowding flag, not an automatic fade.

## R020 — GEX proxy

(1) Direction and mechanism. Under the assumed dealer book: positive net GEX → dealers sell rallies / buy dips → realized vol compressed, mean-reversion helped, trend/breakout hurt. Negative net GEX → amplifying hedge flow → trend helped, short-vol / pin trades hurt. Pinning at high-OI strikes near expiry is the same hedge loop.
- Improves in +GEX (if assumption holds): fade, iron-fly / pin, realized-vol short.
- Improves in −GEX: breakout, long gamma, wider stops.
- Dies if the sign convention is wrong: every conclusion flips.

(2) Documented evidence. Ni, Pearson, and Poteshman (2005) — expiration-day stock prices cluster at high-OI strikes, consistent with hedge-related pinning (gross price-level study). Dealer-hedging mechanics are standard MM theory; GEX-as-traded-signal papers are mostly practitioner. Gamma-squeeze episodes (e.g. 2021 single-name call buying) are case studies, not a controlled 500-name net-of-cost test. State the assumption in every table.

(3) Failures. OI ≠ dealer inventory (hard failure). <5 liquid strikes. Using same-day OI before it is published (lookahead). Mixing 0DTE and 6-month OI without tenor weights. Customer call-buying regimes invert the sign.
Bottom line: vol-regime / sizing overlay, gated on chain quality. Never a direction trigger from GEX alone.

## Joint compounding (how to stack, not multiply folklore)

Think in layers, not a 10-way interaction term you cannot identify.
1. Funding layer (R017, R019) sets admissible leverage. If funding is stressed, shrink everything that assumes cheap balance sheet — including crowded momentum (R018) and high-λ takers (R011).
2. Toxicity + impact layer (R014, R011, R012) sets whether you may be passive. High VPIN + high λ: stand down MM; take liquidity only with a short-horizon edge that still clears λ·size.
3. Grid + venue layer (R015, R016) sets how you trade, not whether the signal exists. Constrained + high off-ex: reroute, do not rerank the alpha book using lit depth.
4. Positioning layer (R018, R020) sets crash and vol shape. Crowded WML + negative GEX + rebound-from-panic is the documented momentum-crash shape (Daniel–Moskowitz anatomy + hedge-flow amplifier). Crowded WML + positive GEX can still crash if the short-leg beta flip dominates; GEX does not repeal 2009.
5. Participation (R013) is an intensity knob on 1–4: same signal, more of the crowd is in the tape.
Disagreement rules: R011 vs R012 should comove; if not, drop both for that name-day. R016 ATS file must not overwrite same-day TRF. R020 null if thin chain. R018 SI must carry publication lag into any "compound" score.

### Honest one-liners

| Regime | Use as |
|--------|--------|
| R011 λ | Sizing / stand-down for size |
| R012 Amihud | Universe / turnover filter; premium is gross and slow |
| R013 volume | Context only |
| R014 VPIN | Stand-down for passive MM |
| R015 tick-bind | Make/take and routing |
| R016 off-ex | Execution map; vintage-tag ATS |
| R017 SOFR stress | De-lever / stand-down funded books |
| R018 crowding | Size and crash overlay, especially WML shorts |
| R019 funding | Carry overlay; reported_* only |
| R020 GEX | Vol-regime overlay, assumption-tagged; not a trigger |

---

End of batch RB2 capture. All three answers were obtained from a single signed-in chat session (grok.com, account Praveen Gupta), asked sequentially with full completion waits between questions; no question was skipped and no rate-limit blocked the run.
