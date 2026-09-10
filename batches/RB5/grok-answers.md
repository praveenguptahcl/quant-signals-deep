# RB5 — Grok answers (regimes R041–R050) — VERBATIM

- Batch: RB5 — Session/intraday + structural regimes (R041–R050)
- Bot: Grok (grok.com), signed in as Praveen Gupta (saved x.ai login; no OTP needed)
- Date: Thu 2026-09-10 (America/Chicago)
- Model mode: "Fast" (as shown in the model select; task did not specify a thinking mode)
- One new chat: https://grok.com/c/093fa18c-afab-47fe-a4f5-a268dfdae0cf (title "Market Regimes: Definitions, Formulas & Examples") — Q-RB5-1, then Q-RB5-2, then Q-RB5-3, each sent only after the prior answer fully completed (streaming indicator gone). No rate limits hit.
- Fidelity notes from the browser run (the answer was not re-typed; only lightly cleaned):
  1. Duplicated extraction artifacts deduped; formulas transcribed in the linear notation Grok rendered, every symbol as it appeared.
  2. Where the page truncated a tolerance/word in A2 (a few tolerance numbers in the verification table and two or three sentence fragments), it is flagged inline as [truncated on page] rather than invented.
  3. The in-text citation chips (Bsic, Papers.ssrn, Luldplan, Sec, ScienceDirect, Databento, Polygon, Nyse, etc.) appear as rendered.
  4. Answer 1 carries a "74 sources" link button and Answer 2 a "28 sources" button in the chat.
- Execution notes: sign-in — saved-session restore on first attempt returned "hydrated" but grok.com still showed signed-out; navigating back to grok.com after accounts.x.ai confirmed "Welcome, Praveen" — signed in as Praveen Gupta. Cookie banner: rejected optional cookies. A1 took ~2m34s of generation, A2 ~1m25s, A3 ~10s. Nothing was submitted, bought, or changed — research only.
- Handling: research leads, not facts. Anything without a checkable source goes under `Unverified leads`, never in `Sources`. Nothing here is a live-trading spec; research for the document only.

=== Q-RB5-1 VERBATIM ===

# Market Regimes R041–R050

Scope. Each regime is a measurable market state that changes the conditional efficacy of trading signals. Every number below is tagged documented (with a citable source) or illustrative estimate. Formulas are exact; every symbol is defined with units.

Notation used throughout. Time is calendar trading days unless noted. Returns are simple unless stated log. Prices are official listing-market prints unless stated otherwise.

## R041 — Overnight-gap dominance regime

(1) Precise definition
The market is in an overnight-gap dominance regime when a material fraction of close-to-close return variance (and, separately, of mean return) is realized in the overnight close-to-open interval rather than in the open-to-close session. The classical empirical fact is that, in U.S. equities, a large share of the equity premium has accrued overnight while average intraday returns have been near zero or negative. [Bsic]

(2) Exact calculation
For security i on day t:
r_i,t^ON = O_i,t / C_i,t-1 − 1,  r_i,t^ID = C_i,t / O_i,t − 1,  r_i,t^CC = C_i,t / C_i,t-1 − 1
where O_i,t = official open, C_i,t = official close (currency units). Identity: (1+r_CC) = (1+r_ON)(1+r_ID).
Variance share over a window of T days (sample second moments, no demeaning required for a pure variance decomposition of the additive log-return version; for simple returns use the usual variance):
ON_share_i = Var(r_i^ON) / (Var(r_i^ON) + Var(r_i^ID))
Units: dimensionless in [0,1].
Inputs: daily official open and close (listing exchange). Optional: dividends/splits so that C and O are split-adjusted consistently.
A related documented fact: roughly two-thirds of a typical 24-hour U.S. equity variance realizes intraday and one-third overnight — so ON_share near 1/3 is the long-run variance baseline, not the mean-return baseline. [Bsic]

(3) Typical ranges / thresholds
| Band | ON_share | Label |
| Intraday-dominant | <0.30 | illustrative (sits near the documented ~1/3 variance split) |
| Balanced | 0.30–0.45 | illustrative |
| Overnight-dominant (variance) | >0.45 | illustrative |
| Overnight premium dominance | E[r^ON]≫E[r^ID], often E[r^ID]≤0 | documented pattern for U.S. indices/ETFs (e.g. Cooper et al. 2008 lineage; SPY overnight vs day split) [Robertbilling] |
Do not treat the mean-return overnight puzzle as a variance-share threshold; they are different objects.

(4) Worked example (synthetic 10-day panel)
| Day | r_ON | r_ID |
| 1 | +0.006 | −0.002 |
| 2 | +0.004 | +0.001 |
| 3 | −0.003 | −0.004 |
| 4 | +0.008 | −0.001 |
| 5 | +0.002 | +0.003 |
| 6 | +0.007 | −0.003 |
| 7 | −0.001 | +0.002 |
| 8 | +0.005 | −0.002 |
| 9 | +0.003 | +0.000 |
| 10 | +0.004 | −0.001 |
Sample means: r̄_ON = 0.0035, r̄_ID = −0.0007.
Sum of squared deviations from own mean:
• ON SSD = 8.05×10^−5, Var̂_ON = 8.05×10^−5 / 9 = 8.944×10^−6
• ID SSD = 4.81×10^−5, Var̂_ID = 5.344×10^−6
• ON_share = 8.944×10^−6 / (8.944×10^−6 + 5.344×10^−6) = 0.626
Classification: overnight-dominant on variance (illustrative band >0.45) and overnight-premium state (positive ON mean, negative ID mean). Fade-the-gap / fade-intraday rules are more relevant than "hold through the day" rules in this state.
Formula source lineage: overnight vs intraday return split is standard (Cooper, Cliff, Gulen 2008 and subsequent work). Variance-share construction is the usual two-component decomposition; the ~1/3 overnight variance fact is stated in the overnight-drift literature. [Bsic]

## R042 — Time-of-day liquidity U-shape regime

(1) Precise definition
Intraday volume and quoted spreads of exchange-listed equities are U-shaped: high at the open, low midday, high again into the close. The regime is the current clock-time bucket relative to that seasonal profile, because signal-to-noise and implementation cost are state-dependent. U-shape in volume and spreads on NASDAQ names is documented on TAQ 2000–2021. [Papers.ssrn]

(2) Exact calculation
Partition regular hours into B clock buckets (e.g. 5-minute bars). For name i, bucket b, lookback of L days:
V̄_i(b) = (1/L) Σ_{ℓ=1}^L V_i,t−ℓ(b),  S̄_i(b) = (1/L) Σ_{ℓ=1}^L s_i,t−ℓ(b)
s_i,t(b) = (A_i,t(b) − B_i,t(b)) / M_i,t(b),  M = (1/2)(A+B)
Units: V = shares (or notional $); s = dimensionless relative spread.
Seasonal intensity: U_i(b) = V̄_i(b) / [(1/B) Σ_{b'} V̄_i(b')]
State map (illustrative clock cuts for U.S. cash equities, ET):
• OPEN: 09:30–10:00
• MID: 11:30–14:00
• CLOSE: 15:30–16:00
Inputs: TAQ/SIP trades and NBBO quotes, time-stamped, regular hours only.

(3) Typical ranges
| State | U(b) volume | Relative spread vs midday | Label |
| OPEN | U≳1.5–3 | spreads elevated vs midday | qualitatively documented U-shape; numeric multiples illustrative |
| MID | U≈0.5–0.9 | tightest spreads | illustrative |
| CLOSE | U≳1.5–3 | spreads rise again | documented direction [Papers.ssrn] |
Calendar-time volatility also looks U-shaped; some work argues that is partly an aggregation artifact and that trade-time volatility falls through the day. Treat volume/spread U-shape as the liquidity regime; do not automatically equate it to a volatility regime. [ScienceDirect]

(4) Worked example (5-minute seasonal profile, one name)
Synthetic 5-min relative volume U(b) and relative spread s(b) (midday-normalized):
| Clock (ET) | U(b) | s(b) (bps) | State |
| 09:35 | 2.40 | 8.5 | OPEN |
| 09:55 | 1.80 | 6.0 | OPEN |
| 12:00 | 0.65 | 2.2 | MID |
| 13:00 | 0.70 | 2.0 | MID |
| 15:40 | 1.90 | 4.8 | CLOSE |
| 15:55 | 2.60 | 5.5 | CLOSE |
At 12:00: U=0.65, s=2.2 bps → MID liquidity regime. At 15:55: U=2.60, s=5.5 bps → CLOSE liquidity regime.
Signal implication: mean-reversion / spread-capture capacity is highest MID; impact of a given notional is highest OPEN/CLOSE.
Source: Hua, Kong, Wang (2024) on NASDAQ U-shape in volume and spreads. [Papers.ssrn]

## R043 — Closing-auction imbalance regime

(1) Precise definition
The listing exchange publishes a net MOC/LOC imbalance into the close. The regime is the standardized size and persistence of that imbalance relative to typical auction volume. Large persistent buy (sell) imbalances are associated with positive (negative) last-15-minute and close-print drift; offset/absorbed imbalances are weaker. NYSE first publishes an indicative MOC imbalance at 15:45 ET. [Mathandmarkets]

(2) Exact calculation
At announcement time τ (e.g. 15:50):
OI_i,t = Buy_i,t − Sell_i,t (shares)
x_i,t = OI_i,t / ADV_i,t,  ImbPct_i,t = OI_i,t / AuctionVol_ī
Standardized score (desk convention; not a statute):
ImbZ_i,t = (OI_i,t − μ̂_OI,i) / σ̂_OI,i
Units: x = fraction of ADV (dimensionless); ImbZ = standard deviations.
Fade-vs-follow rule (illustrative policy, not a published law):
• Follow if |ImbZ| ≥ 2 and imbalance is not shrinking in successive prints.
• Fade / stand down if price has already moved ≥ k bps toward the imbalance and matched qty is catching up (absorption).
Price-impact literature often uses a square-root specification λ·sign(x)·|x|^{1/2}. [Researchgate]
Inputs: exchange imbalance feed (NYSE/Nasdaq auction messages), ADV (e.g. 10-day), historical auction volume.

(3) Typical ranges
| |ImbZ| | Read | Label |
| <1 | noise | illustrative |
| 1–2 | watch | illustrative |
| ≥2–3 | actionable flow | illustrative (user example uses +3.2) |
| Event days (rebalance / month-end) | auction can be a large share of daily volume | documented qualitatively (close often ~10–15% of daily volume, much more on rebalance days) [Luxalgo]

(4) Worked example
Given: ImbZ = +3.2. Suppose μ̂_OI = 0, σ̂_OI = 250,000 shares. Then OI = 3.2 × 250,000 = +800,000 shares (buy). If 10-day ADV = 8,000,000, x = 800,000/8,000,000 = 0.10 (10% of ADV). If typical close auction = 1,200,000 shares, ImbPct = 800,000/1,200,000 = 0.667.
Classification: extreme buy-imbalance regime. Default rule in the user specification: follow into the cross (not fade), unless subsequent prints show the imbalance collapsing.
Sources: exchange auction mechanics; OI definition and |x|^{1/2} impact in auction-impact papers. [Researchgate]

## R044 — Market concentration regime (HHI)

(1) Precise definition
The investable universe (index or book) is concentrated when a small number of names dominate capitalization weights. Standard measure: Herfindahl–Hirschman Index of weights. Effective number of stocks is 1/HHI (decimal weights) or 10,000/HHI (percent weights). [Nasdaq]

(2) Exact calculation
Let w_i be index weight as a decimal (Σ_i w_i = 1):
HHI_dec = Σ_{i=1}^N w_i^2,  N_eff = 1/HHI_dec
Percent-point convention (antitrust scale 0–10,000):
HHI_% = Σ_{i=1}^N (100·w_i)^2 = 10,000·HHI_dec
Concentration ratio: CR10 = Σ_{i ∈ top 10} w_i
Inputs: point-in-time index weights (or portfolio weights).

(3) Typical ranges
Antitrust (DOJ/FTC 2023, industry HHI in percent-point units): <1,000 unconcentrated; 1,000–1,800 moderate; >1,800 highly concentrated. Documented for product markets, not equity indices. [Ryanoconnellfinance]
Equity-index HHI (decimal): equal-weight S&P 500 would have HHI = 1/500 = 0.002 (N_eff = 500). Reported S&P 500 HHI in percent-point / alternative scaling has been cited around the high-100s in 2024 commentary (not the 0–10,000 industry scale — authors sometimes report Σ(100w_i)^2/100 or similar). Use CR10 as the operational band. [Axios]
| CR10 | Regime | Label |
| <0.25 | diversified large-cap | illustrative |
| 0.25–0.35 | elevated | illustrative; some practitioner notes flag CR10 > 0.35 as heavy top-10 dominance |
| ≥0.38 | concentrated | illustrative (user example) |

(4) Worked example
Given: top-10 index weight = 38% so CR10 = 0.38.
Illustrative top-10 decimals: 0.070, 0.055, 0.045, 0.040, 0.035, 0.032, 0.028, 0.026, 0.025, 0.024 (sum 0.380). Remaining 490 names share 0.620, approx w = 0.001265 each.
HHI_top10 = 0.070^2 + ⋯ + 0.024^2 = 0.016984
HHI_tail = 490 × (0.001265)^2 ≈ 0.000784
HHI_dec ≈ 0.01777, N_eff ≈ 56.3
Classification: concentrated-index regime (CR10 = 0.38, N_eff ≈ 56 in a 500-name index). Factor and single-name residuals are more fragile; index-level signals are mega-cap signals.
Sources: HHI definition (Investopedia / DOJ convention); index-concentration use. [Investopedia]

## R045 — Dispersion regime

(1) Precise definition
Cross-sectional return dispersion (CSV) is the cross-sectional standard deviation (or variance) of name-level returns in a universe at a date. High dispersion = more room for stock-selection / relative-value signals; low dispersion = crowding into the market factor. CSV also forecasts subsequent market volatility in HAR-type models. [Onlinelibrary.wiley]

(2) Exact calculation
Universe of N names, period-t returns r_i,t:
r̄_t = (1/N) Σ_{i=1}^N r_i,t,  CSV_t = √[(1/(N−1)) Σ_{i=1}^N (r_i,t − r̄_t)^2]
Equal-weight by default; cap-weight if the object is index residual risk.
Units: same as r (e.g. decimal per day).
Inputs: aligned total returns for a fixed universe (watch survivorship).

(3) Typical ranges
No universal cut. Operationalize by trailing percentile of CSV_t.
| Percentile of own history | Regime | Label |
| <25th | compression | illustrative |
| 25–75 | normal | illustrative |
| >75th | high dispersion | illustrative; high-CSV months are when active selection historically pays more |

(4) Worked example (10-name panel, one day)
Returns (%): +2.1, +1.4, +0.8, +0.3, +0.1, −0.2, −0.5, −0.9, −1.4, −2.2
r̄ = −0.05%.
Deviations: 2.15, 1.45, 0.85, 0.35, 0.15, −0.15, −0.45, −0.85, −1.35, −2.15.
SSD = 15.685.
CSV = √(15.685/9) = √1.7428 = 1.320%.
If the 75th percentile of this name-set's 252-day CSV history is 1.10% (illustrative), then 1.320 > 1.10 → high-dispersion regime. Long-short residual signals are on; pair-trading residual vol is high.
Sources: Niu et al. (2023) CSV as volatility predictor; Stivers / Connolly–Stivers line on dispersion and momentum. [Onlinelibrary.wiley]

## R046 — Factor-crowding regime

(1) Precise definition
A factor (here: momentum) is crowded when (a) its own realized volatility is elevated and (b) the factor has already delivered a large trailing return, so the characteristic portfolio is extended. Daniel & Moskowitz (2016) document that momentum strategies have rare, violent crashes, concentrated after market declines and contemporaneous with market rebounds, when loser betas spike. Crowding is a conjectured amplifier of those crashes (Lou–Polk comomentum; Barroso–Edelen–Karehnke). [Spinup-000d1a-wp-offload-media.amazonaws]

(2) Exact calculation
Let f_t be the daily momentum factor return (WML). Trailing realized vol over W days:
σ̂_t^fac = √[(252/W) Σ_{k=0}^{W−1} (f_t−k − f̄_t,W)^2] (annualized, 1/day units inside)
Percentile rank of σ̂_t^fac in its own history: P_σ,t.
Trailing standardized factor return over H days:
Z_t^ret = (Σ_{k=1}^H f_t−k) / (σ̂_t^fac √(H/252))
Crowding flag (desk rule matching the prompt): P_σ,t ≥ 85 and Z_t^ret ≥ +2.2.
Optional documented cousin: Lou–Polk comomentum = average pairwise residual correlation inside the winner and loser legs.
Inputs: daily factor returns (e.g. Ken French WML); optionally constituent books for comomentum.

(3) Typical ranges
Momentum crashes themselves are documented (1932, 2009: losers +163% vs winners +8% over Mar–May 2009 in Daniel–Moskowitz). The 85th-percentile vol × +2.2σ trailing-return flag is illustrative (user-specified), not a threshold in Daniel–Moskowitz. [Etf]
Daniel–Moskowitz forecastable crash state: prior bear market + high market vol + subsequent rebound — documented.

(4) Worked example
Given: momentum-factor vol at its 85th percentile, trailing return = +2.2σ. Both crowding-flag legs fire.
Classification: crowded-momentum regime. Per Daniel–Moskowitz, do not treat this as a reason to add to WML; it is a reason to cut gross / flatten the short-loser leg into rebound states. Cite Daniel & Moskowitz, Journal of Financial Economics (2016), "Momentum Crashes." [Spinup-000d1a-wp-offload-media.amazonaws]

## R047 — News-flow intensity / novelty regime

(1) Precise definition
Two separate coordinates:
1. Intensity — count (or dollar-relevant count) of firm-tagged articles in a window vs that firm's own median.
2. Novelty — semantic distance of today's article embedding from the firm's recent news centroid.
Stale / repeated narratives are associated with weaker (or faded) reactions; Tetlock (2011) is the classic "old news" reference. Embedding cosine is a modern operationalization, not Tetlock's original measure. [Nber]

(2) Exact calculation
Let n_i,t = article count for name i on day t. ñ_i = median(n_i,t−252:t−1). Intensity_i,t = n_i,t / ñ_i
Let e_i,t be the (L2-normalized) embedding of today's news bundle, c_i,t the trailing-10-day centroid of daily embeddings:
c_i,t = (Σ_{k=1}^{10} e_i,t−k) / ‖Σ_{k=1}^{10} e_i,t−k‖,  novelty_i,t = 1 − cos(e_i,t, c_i,t)
cos(u,v) = u^T v (already unit vectors)
Units: intensity dimensionless; novelty in [0,2] theoretically, typically [0,1] for related text.
Inputs: timestamped tagged news + a frozen embedding model. No look-ahead in the centroid.

(3) Typical ranges
| Intensity | Novelty | Read | Label |
| ≈1× median | high (≳0.3) | genuine news | illustrative |
| 4× median | 0.12 | high flow, low novelty → stale-news fade | illustrative (user spec) |
| high × high | information shock | do not fade | illustrative |

(4) Worked example
Given: intensity = 4× median, novelty = 0.12. That means cos(e, c) = 1 − 0.12 = 0.88 — today's bundle is aligned with the last 10 days.
Classification: high-intensity / low-novelty (stale-news) regime. Setup: fade the headline-driven continuation; the flow is repetition, not a new state.
Sources: stale-news underreaction/overreaction literature (Tetlock 2011); cosine novelty is a standard embedding construction, here used as an illustrative statistic.

## R048 — Halt / Limit-Up-Limit-Down proximity regime

(1) Precise definition
NMS stocks trade inside LULD price bands around a five-minute reference price. If the NBO equals the lower band or the NBB equals the upper band for 15 seconds, the name enters a Limit State; if it does not exit, the primary listing exchange declares a 5-minute Trading Pause. Bands double after 15:35 ET. [Luldplan]

(2) Exact calculation
Band_t^± = R_t ± R_t·π_t
R_t = reference price (arithmetic mean of eligible trades over the prior five minutes; yesterday's close at the open if needed).
π_t = percentage parameter:
• Documented Tier 1 (S&P 500 / Russell 1000 / selected ETPs), 09:30–15:35, prior close > $3: π = 5%.
• Tier 2, same price: π = 10%.
• $0.75–$3: 20%. Below $0.75: lesser of $0.15 or 75%. After 15:35: parameters double. [Cboe]
Proximity in return space:
d_t^up = (Band_t^+ − P_t) / (R_t π_t),  d_t^dn = (P_t − Band_t^−) / (R_t π_t)
so d ∈ [0,1] inside the band (0 = touching).
Volatility-normalized distance (user spec):
d_t^σ = min(Band_t^+ − P_t, P_t − Band_t^−) / σ̂_t^{5m}
Units: d^σ in standard deviations of 5-minute returns (price units in numerator and denominator).
Stand-down flag (illustrative): d^σ ≤ 0.8.
Inputs: SIP LULD reference/band fields (official) or reconstructed R_t, π_t; last sale.

(3) Typical ranges
Band widths themselves are documented in the LULD Plan. The 0.8σ stand-down is illustrative.

(4) Worked example
Tier-1 name, P = R = $100, π = 0.05, bands $95 / $105. 5-minute σ̂ = $2.50. Distance to nearest band = $5. d^σ = 5 / 2.50 = 2.0. That would not trip a 0.8σ flag.
Now move price to $97.00: distance to lower band = $2.00, d^σ = 2.00 / 2.50 = 0.80.
Classification: LULD-proximity stand-down regime at d^σ = 0.8. Do not add aggressive liquidity-taking; quote/volatility signals are contaminated by the hard constraint and halt optionality.
Sources: LULD Plan / Cboe LULD FAQ. [Luldplan]

## R049 — Short-sale restriction regime (Rule 201)

(1) Precise definition
SEC Rule 201 (Reg SHO circuit breaker): if a covered NMS stock declines 10% or more from the listing market's prior-day regular-hours close, the listing market flags it; then trading centers must not execute or display a short sale at or below the current NBB for the rest of that day and the next day (with specified exceptions / "short exempt"). The listing market — not a desk's own tape — is the official trigger source. [Sec]

(2) Exact calculation
Let C_i,t−1 = listing-market official close, regular hours, day t−1. Let P_i,u = last sale (listing market) at intraday time u.
Trigger arithmetic:
(P_i,u − C_i,t−1) / C_i,t−1 ≤ −0.10
Once the listing market disseminates the flag via the plan processor, SSR_i = 1 until the close of day t+1.
Inputs: official prior close; listing-market last sale; SIP SSR indicator (do not homebrew the flag for live compliance).

(3) Typical ranges
The threshold is exactly −10%. Not a statistical band. Documented in 17 CFR § 242.201. [Law.cornell]

(4) Worked example
Prior close C = $50.00. Trigger print P ≤ 50 × 0.90 = $45.00. If last sale prints $45.00, decline = (45−50)/50 = −10.00% → listing market should arm Rule 201. If last sale is $45.01, decline = −9.98% → not triggered.
Classification at $45.00: SSR-on regime for remainder of day t and all of day t+1. Short-side signals that require hitting the bid are structurally impaired; locate/price-test constraints bind.
Source: SEC Rule 201 FAQ and 17 CFR § 242.201. [Sec]

## R050 — Cross-venue / SIP-vs-direct divergence regime

(1) Precise definition
U.S. equities have two data planes:
• SIP (CTA/UTP): consolidated last sale + protected NBBO, after plan-processor sequencing.
• Direct / proprietary feeds: per-venue order-by-order or depth, emitted from the matching engine, typically arriving at colocated servers before the SIP NBBO updates.
Divergence is a state in which the direct-constructed BBO (or a synthetic NBBO built from simultaneous direct feeds) differs from the SIP NBBO, or in which SIP timestamps reorder events relative to exchange matching-engine times. Academic work using exchange timestamps finds SIP quote processing delays on the order of ~1,128 μs mean (Dow 30 sample) and frequent SIP-vs-direct NBBO dislocations, even though most SIP-priced trades still print when the two NBBOs match. [ScienceDirect]

(2) Exact calculation
Let Q_SIP(t) = (B_SIP, A_SIP) be the SIP NBBO at SIP timestamp t. Let Q_DIR(τ) be the NBBO reconstructed from all direct feeds using matching-engine timestamps τ, aligned on a common GPS clock.
ΔB(τ) = B_DIR(τ) − B_SIP(t(τ)),  DivRate = #{τ: Q_DIR ≠ Q_SIP} / #τ
Latency: L_quote = τ_SIP receive − τ_engine (microseconds)
Inputs that actually measure this: colocated direct feeds from every protected venue + hardware timestamping + SIP. TAQ/SIP alone cannot reconstruct Q_DIR.

(3) Typical ranges
| Object | Documented magnitude | Label |
| Mean SIP quote reporting gap (DJIA 30 sample) | 1,128 μs | documented in the microsecond-timestamp study |
| SIP trade reporting lag (same paper) | ∼24,255 μs mean | documented |
| Share of SIP-priced trades when SIP NBBO = direct NBBO | 97% (that sample) | documented |
| Desk "divergent if |ΔB| ≥ $0.01" | — | illustrative |

(4) Why a desk Mac without colocation cannot measure this
1. Path, not CPU. Direct-vs-SIP divergence is a race on the exchange-to-consumer path: matching-engine NIC → colo cage → microwave/fiber vs matching-engine → SIP processor (Mahwah/Carteret) → vendor → your laptop. A Mac in an office or home ISP sits tens of milliseconds behind both planes. You never observe Q_DIR(τ) at engine time.
2. You only see one delayed plane. Retail/vendor "real-time" is almost always SIP (or SIP-derived). Comparing "my screen" to "Yahoo/Bloomberg SIP" is SIP-vs-SIP-plus-vendor-lag, not SIP-vs-direct.
3. Clock domain. Without GPS/PTP timestamps at the venue edge, you cannot difference L_quote at microsecond resolution. NTP on a Mac is milliseconds.
4. Incomplete geography. Measuring a true direct NBBO requires all protected venues' proprietary feeds and colocation (or a vendor that already colocates and re-timestamps). One Nasdaq ITCH feed in a cloud VM is not a direct NBBO.
Honest labeling for any latency-sensitive backtest run on SIP/TAQ data: SIP-timestamp / consolidated-tape backtest — not a direct-feed or colocated simulation. Fill prices, queue priority, mid-as-of, and "would I have seen this quote?" are those of the SIP clock, which is systematically late relative to matching engines. Do not claim HFT, rebate-capture, mid-point fade, or intra-millisecond cross-venue arbitrage capacity. Label strategies as SIP-information-set strategies. If the signal horizon is seconds-to-hours, the bias is smaller; if the horizon is sub-second, the backtest is not identified.
Worked (illustrative) classification. Suppose a research tape shows SIP NBBO 100.00×100.01 while a colocated reconstruct (not available on the Mac) would have been 100.01×100.02 for 800 μs. That interval is a SIP-lag divergence event. On a Mac+SIP research stack the honest regime label is: unmeasurable; treat as SIP-only information set, divergence regime = N/A.
Sources: SIP vs direct latency microstructure; SEC/SIFMA policy that feeds are released together, not received together. [ScienceDirect]

Example classifications (summary)
| Regime | Example statistic | Final class |
| R041 | ON_share=0.626, r̄_ON>0>r̄_ID | Overnight-dominant |
| R042 | 12:00 U=0.65; 15:55 U=2.60 | MID / CLOSE U-shape states |
| R043 | ImbZ=+3.2 | Extreme buy-imbalance — follow (unless absorbed) |
| R044 | CR10=38%, N_eff≈56 | Concentrated index |
| R045 | CSV=1.32% > p75 | High dispersion |
| R046 | fac-vol p85 and +2.2σ trailing WML | Crowded momentum (crash-watch) |
| R047 | intensity 4×, novelty 0.12 | Stale-news fade |
| R048 | d^σ=0.8 | LULD stand-down |
| R049 | print at prior-close × 0.90 | Rule 201 SSR-on |
| R050 | desk Mac, SIP only | Not identified; label backtest SIP-information-set |

Research hygiene. Where a paper gives a qualitative shape (U-shape, overnight premium, momentum crashes, LULD percentages, Rule 201 −10%) I treated the shape/parameter as documented. Where the chapter needs a desk cutoff (ON_share >0.45, ImbZ +3.2, CR10 38%, novelty 0.12, 0.8σ LULD, 85th × 2.2σ crowding), that cutoff is illustrative unless a statute or plan text writes the number. Do not promote illustrative cutoffs to "the literature says."
[74 sources button]

=== Q-RB5-2 VERBATIM ===

# Computing R041–R050 on an M5 Max / 128 GB Mac

Constraint that governs the whole design. This machine is a research workstation, not a matching-engine peer. It can compute nine of the ten regimes as production-grade research states. R050 is a capability gate, not a missing library. Without colocated multi-venue MBO/ITCH plus a GPS/PTP clock, R050 is permanently UNKNOWN. Every latency-sensitive chapter carries the "simulated only — requires MBO/ITCH" label. Prices below are indicative as of vendor public pages in 2026. They are not quotes.

## 1. Data feeds — exact products, mapped to regimes
| Regime | What the estimator actually needs | Product to buy / scrape | Notes |
| R041 overnight share | Split- and dividend-adjusted official open and close; same adjustment vector on both | CRSP Daily Stock File (via WRDS) or Norgate Data / CSI Data adjusted unadjusted + factor file or Massive (ex-Polygon.io) Stocks Developer/Advanced + their corporate-actions endpoint [Polygon] | CRSP is the academic gold standard (delistings included). Massive lists corporate actions on every plan |
| R042 U-shape | 5-minute (or 1-minute) trade volume + NBBO mid/spread, regular hours only; exchange calendar with half-days tagged | Databento ohlcv-1m / tbbo on EQUS or venue feeds; or Massive minute aggregates + quotes on Advanced; or NYSE Daily TAQ (trades + NBBO) | Official TAQ: NYSE Daily TAQ ~$3,800/mo MRC commercial (indicative, NYSE price list). Academic TAQ is via WRDS at a steep discount you likely do not have as an individual [Nyse] |
| R043 close imbalance | Auction messages: NYSE Order Imbalance / Closing Imbalance, Nasdaq NOII | Databento XNAS.ITCH imbalance / statistics schemas; NYSE Integrated imbalance; not in SIP last-sale | SIP does not carry full NOII. Do not fake ImbZ from last-15-minute volume. |
| R044 HHI / CR10 | Point-in-time index weights | S&P Dow Jones S&P 500 weight file (licensed) or Bloomberg MEMB / PORT or reconstruct from CRSP msenames + msfshares outstanding × price on the as-of constituent list | Free "current top-10" web pages are not a backtest input. |
| R045 dispersion | Cross-section of total returns on an as-of universe | Same daily file as R041 + CRSP / Compustat Index Constituents or S&P historical membership | Survivorship is the adversary here. |
| R046 crowding | Daily WML (and optionally your own book) | Ken French Data Library F-F_Momentum_Factor_daily — free | Construction documented on the French site [Mba.tuck.dartmouth] |
| R047 news | Timestamped ticker-tagged articles + embeddings | Massive Ticker News (on stocks plans) and/or Benzinga News (Massive partner v2); RavenPack if you need research-grade novelty (institutional $) | Embed locally with a frozen model on the M5 Max. |
| R048 LULD / halt | Official bands + halt state | NYSE Daily TAQ Quote LULD + Trade LULD + CTA/UTP Admin; Databento status / LULD fields; Nasdaq Trader halt page + NYSE Trading Status as a second channel | Parse failures → halt. |
| R049 SSR | Official trigger, not homemade −10% | FINRA / Nasdaq Trader Reg SHO Threshold / Rule 201 short-sale restriction list (daily file); SIP short-sale restriction indicator | Listing market is the legal source. |
| R050 SIP vs direct | Direct MBO from all protected venues + SIP, colocated | Nasdaq TotalView-ITCH, NYSE Integrated, Cboe Depth, etc. Databento sources these; live multi-venue prop licensing is a different cost universe: ~$60k/mo exchange licenses cited by Databento as the raw prop-feed stack vs ~$10.5k/mo [Databento] | You cannot measure this on the Mac. |

Minimum viable one-person stack (research, not HFT):
1. Daily adjusted bars + actions: Massive Stocks Developer $79/mo indicative or Advanced $199/mo if you want real-time. [Polygon]
2. Intraday + imbalance + status: Databento US Equities Standard $199/mo indicative (live + limited L2/L3 history) or usage-based history from $0.40/GB. Plus is $1,500/mo indicative [Databento]
3. Factors: Ken French — $0.
4. Index weights: S&P license (often $500–$2,000+/mo indicative for a research-use weight file; get a quote) or CRSP reconstruction if you can get WRDS.
5. News: bundled in Massive; Benzinga add-on if you outgrow it.
6. SSR / halts: Nasdaq Trader + FINRA public files + Databento/TAQ status. $0–small.
7. R050: do not buy. Gate it.
Do not buy commercial Daily TAQ at $3,800/mo for a one-person book unless a paper requires official SIP mic[rostructure — truncated on page].

## 2. Daily refresh compute time (Python + Polars, M5 Max)
Assume universe ≈ S&P 500 + a 3,000-name research panel, 5 years warm, incremental daily job.
| Job | Cadence | Wall time on M5 Max (illustrative, measured-order) |
| Corporate-action apply + ON/ID split (R041) | after official close + CA file | 5–20 s |
| As-of membership + CSV / HHI (R044–R045) | after close + weight file | 10–40 s |
| French WML pull + vol percentile (R046) | daily, after French or 16:00 ET proxy | 1–3 s |
| 5-min seasonal update, full-day vs half-day profiles (R042) | 16:05 ET | 1–4 min (3k names × 78 bars) |
| Imbalance tape → ImbZ (R043) | 15:45–16:00 ET stream + 16:05 finalize | 10–30 s finalize |
| News count + embedding novelty (R047) | every 15–60 min, 16:10 rollup | 1–8 min (local embedding on 128 GB; batch 100–500 articles) |
| LULD / halt / SSR ingest (R048–R049) | continuous + 16:05 reconcile | seconds; I/O bound |
| R050 | never | N/A — gate |
End-of-day full refresh: typically 5–15 minutes after all files land. Intraday loop (R042 buckets, R043, R048, R049, R047): seconds to low minutes per tick of the scheduler. The M5 Max / 128 GB is not the bottleneck. File arrival and CA correctness are.

## 3. RAM and disk budgets
| Store | Warm (research) | Fat (optional) |
| Adjusted daily panel, 10y × 8k names, parquet | 0.5–2 GB | — |
| 1-minute bars, 2y × 3k names | 20–80 GB | — |
| 5-minute seasonal profiles + half-day twin | <1 GB | — |
| Auction messages, 2y | 2–10 GB | — |
| News text + embeddings (e.g. 1024-d float16) | 5–30 GB | — |
| LULD/status/SSR flags | <1 GB | — |
| Databento/ITCH MBO if you ever download a week "to look" | 100 GB–1 TB+ / week / venue | do not keep |
Polars lazy + streaming stays well under 32 GB for the daily job. 128 GB lets you embed news and hold [text truncated on page]; ~250 GB SSD for the research lake + [text truncated on page] if you keep two years of minutes. Do not archive raw ITCH on this box.

## 4. Engineering hours for a causal pipeline
One person who already writes Python, not a vendor integration team.
| Workstream | Hours (illustrative) |
| Lake layout, calendars, half-day flag, timezone (America/New_York) | 8–12 |
| Corporate-action engine + split adversary test | 16–24 |
| As-of membership (no survivorship) | 12–20 |
| R041–R046 estimators + unit tests | 20–30 |
| R042 dual seasonal profiles (regular vs half-day) | 8–12 |
| R043 imbalance parser + vendor schema diffs | 16–24 |
| R047 ingest + frozen embedder + centroid | 12–20 |
| R048/R049 official-list ingest + halt fail-safe | 12–16 |
| R050 capability gate + document stamp | 2–4 |
| Verification layer (second estimator, tolerances) | 16–24 |
| Scheduler, alerts, "do not trade" interlock | 8–12 |
| Total to v1 correct | ~130–200 hours |
That is 4–6 calendar weeks at 5 focused hours/day, or ~3 months part-time. Most of the risk is data semantics, not Polars.

## 5. Buy vs build (one-person research op)
| Piece | Buy | Build | Verdict |
| Adjusted daily + CA | Massive $79–$199/mo indicative or Norgate ~$50–$80/mo indicative | Parse SEC + Yahoo | Buy. Split errors destroy R041. |
| Intraday bars / status | Databento Standard $199/mo indicative | — | Buy. |
| Official TAQ | $3,800/mo indicative | — | Do not buy unless a referee demands SIP TAQ. |
| Imbalance / NOII | Databento ITCH/NYSE schemas (in the $199–$1,500 band) | — | Buy the messages; build ImbZ. |
| Index weights | S&P file (quote) or CRSP | Scrape Wikipedia | Buy or reconstruct from CRSP; never scrape. |
| WML | French library $0 | Rebuild 2×3 | Buy (free). Rebuild only as verifier. |
| News + novelty | Massive news + local embeddings | Full RavenPack | Buy text, build novelty. |
| SSR / LULD / halts | Public lists + Databento status | Home-made −10% | Buy the official flag; homemade is verifier only. |
| R050 direct vs SIP | Colo + multi-venue ITCH (~five-figure to six-figure / mo all-in indicative) | Impossible on a Mac | Do not buy. Gate UNKNOWN. |
Monthly cash for a correct R041–R049 research loop: about $280–$500 indicative (Massive Developer/Advanced + Databento Standard). Jump to $1.7k+ indicative if you add Databento Plus and a proper weight license. NYSE TAQ and prop-feed stacks are not coheren[t — truncated on page].

## Automated detection loop

Agents and cadence. Treat these as processes, not LLM personas. An LLM may narrate the dashboard; it must not [run — text truncated on page] the estimator.
| Agent | Owns | Cadence | Writes |
| ca_apply | Split/div/merge factors → adjusted O/C | 16:20 ET + 08:00 ET catch-up | bars_adj.parquet |
| reg_r041 | ON_share, ON/ID means | after ca_apply | r041.csv |
| cal_halfday | NYSE half-day calendar | weekly + holiday file | session_type |
| reg_r042 | U(b), s(b) two profiles: full and early_close | 16:10 ET; live bucket mark every 5 min 09:30–16:00 | r042_state |
| reg_r043 | ImbZ from imbalance msgs | 15:50, 15:55, 15:58, 16:05 final | r043_state |
| reg_r044 | HHI, CR10, N_eff on as-of weights | 17:00 ET or T+1 when file lands | r044_state |
| reg_r045 | CSV on as-of members only | after ca_apply + membership | r045_state |
| reg_r046 | French Mom vol percentile + trailing Z | 17:30 ET (or next AM if file lags) | r046_state |
| reg_r047 | intensity, novelty | 15 min intraday; 16:15 rollup | r047_state |
| reg_r048 | band distance, limit-state, pause | event-driven from status/LULD | r048_state |
| reg_r049 | official SSR bit | event-driven + 16:05 reconcile vs FINRA file | r049_state |
| gate_r050 | capability | boot + daily | r050 = UNKNOWN always on this host |
| verify_* | second estimator | after each reg_* | agree / HALT_PIPELINE |
| interlock | trading permission | continuous | allow_trade[name] |

Independent verification (second estimator + tolerance)
| Regime | Primary | Verifier | Agree if |
| R041 | Polars var of adj ON/ID | Recompute from unadjusted prices × CA factors rebuilt from the action file; and a planted 2-for-1 with unadjusted input must fail the primary if CA is skipped | tolerance shown on page as "0.01" (full criterion truncated); planted-split guard must fire |
| R042 | 5-min [estimator] | Rebuild from 1-min then resample | bucket state match; relative error [threshold truncated on page] |
| R043 | vendor Imb shares | Alternate venue message (Nasdaq NOII vs NYSE imbalance) or ADV-normalized | sign match; when both exist [tolerance shown as 0.3] |
| R044 | weight-file HHI | CRSP cap-weight reconstruction | [criterion truncated on page; page shows "10"] |
| R045 | equal-weight CSV on as-of list | cap-weight CSV on same list | rank correlation of names [≥, value shown 0.95]; membership count must equal official |
| R046 | French daily Mom | Local 2×3 WML on as-of NYSE breaks | corr of daily series over 60 days [threshold truncated]; flag agree on p85 and within 0.2 |
| R047 | count / cosine | Second embedder (different frozen model) or bag-of-words Jaccard novelty | intensity ratio within 10%; novelty [within 0.05] |
| R048 | TAQ/Databento LULD | Nasdaq halt RSS / listing-exchange status page | any disagreement → HALTED |
| R049 | SIP/official SSR flag | Homemade −10% | homemade may fire early; official flag is authority; if official = ON and homemade = OFF → trust official and log |
| R050 | — | — | no verifier. State is UNKNOWN. |

Fail-safes (explicit)
Corporate actions before any variance decomposition. Pipeline order is immutable: raw bars → action file → adj bars → R041/R045/R046 local books. Adversary test (CI, every build): inject an unadjusted 2-for-1 on day [t — truncated] (close 200 → next open 100 with no factor). Primary R041 must refuse to publish (CA_GUARD_FAIL). If ON_share still publishes, the job is red. Never compute [variance decomposition — truncated] on raw prices.
As-of index membership (R044/R045). Universe for day [t — truncated] = constituents with from <= t <= to. Additions enter on the effective date; leavers drop; dead names [stay — truncated] through their last member date. Computing 2026 CSV on the 2026 surviving S&P list is a pipeline error (SURVI[vorship — truncated]).
Halt-message parse failures (R048). If the LULD/status parser throws, checksum fails, or the feed is stale [>2 s — truncated] in a live loop: set halted = TRUE for that symbol (or market-wide if the channel is dead). Assume halted — never trade through. Resume only after two independent sources show TRADING.
R050 capability gate. gate_r050 on this Mac returns: [code block] R050_STATE = UNKNOWN, R050_REASON = NO_COLOCATION_NO_MULTI_VENUE_MBO. Any notebook, chapter, or backtest whose signal horizon is [sub- — truncated] second or that claims queue position, mid-fade vs NBBO race, or SIP-vs-direct arb [must — truncated] carry: simulated only — requires MBO/ITCH. The interlock must block live orders from any strategy tagged latency_sensitive while R050_STATE == UNKNOWN.
Half-days (R042). Maintain two seasonal tensors: profile[full] and profile[early_close]. NYSE early closes (1:00 PM ET: [dates truncated on page]) must not update the full-day U-shape and [must not — truncated] be scored against the 15:30–16:00 CLOSE bucket. On a half-day, CLOSE = last 30 minutes of [the — truncated] session. Mixing them silently inflates midday [truncated] and breaks the close state.
Other interlocks.
• R049 official ON → disable short-at-bid tactics.
• [R048] 0.8[σ — truncated] or limit-state → stand down.
• File not arrived by SLA (e.g. French file missing) → hold prior state and flag STALE, do not silently [roll forward — truncated].

What this Mac is for. It is the right box to run a causal, verified, nine-regime research plant at a few hundred dollars a month. It is the wrong box to measure R050. Treat that as an architectural fact, not a to-do.
[28 sources button]

=== Q-RB5-3 VERBATIM ===

# How R041–R050 change what works

How to read this. "Improves / dies" is conditional efficacy, not a promise of alpha. Evidence is tagged documented (study + market + window) or mechanism-only / illustrative. Costs are labeled when the source reports them. Annotation rule used below and prescribed for the 200 chapters: every efficacy sentence states direction. At most six regimes per chapter, sorted by impact. Prefer the most specific regime (R049 SSR beats R044 HHI when both are on). Slow states (R044, R046) are sizing / tilt / stand-down, not 5-minute triggers. Prefer the most specific regime (R049 SSR beats R044 HHI when both are on). Slow states (R044, R046) are sizing / tilt / stand-down, not 5-minute triggers.

## R041 — Overnight-gap dominance

(1) Direction and mechanism.
• Improves: overnight-hold, close-to-open continuation, "own the gap" index overlays; news-overnight event studies.
• Dies or is mis-measured: any intraday strategy whose backtest is marked to close-to-close. On overnight-dominated names the CC series contains gaps the strategy never traded — return-attribution mismatch. Intraday mean-reversion that looks good CC can be the offset of a positive overnight drift.
• Mechanism: average U.S. equity premium has accrued overnight while average open-to-close has been flat-to-negative; variance still realizes mostly intraday (~2/3), so you can have high daytime risk and low daytime premium.

(2) Evidence.
• Cooper / Cliff / Gulen lineage and later work: U.S. premium concentrated overnight; SPY-style splits (overnight compounding >> day session) appear in practitioner reconstructions — before-cost. After 2–10 bp round-trip per day the overnight edge can vanish.
• Markets: U.S. equities / ETFs; pattern also reported internationally with heterogeneity. Before-cost unless a paper states otherwise.

(3) When the label fails.
• Using raw (unadjusted) opens/closes around splits → fake "gaps."
• Official open ≠ first trade you could lift (auction vs continuous).
• Overnight premium is a slow structural fact, not a Tuesday trigger. A name with ON_share = 0.62 this month can still gap against you tomorrow.
• Structural: 24x5 ATS / overnight venues change where the "overnight" variance sits; a 2010 threshold on ON_share is not portable without re-estimation.

(4) Compounds. R041 + R042 OPEN = gap and wide spreads (gross-strong, net-weak). R041 + R047 high novelty overnight = do not fade the open. R041 + R048 near-band at the open = stand down.
Bottom line: factor tilt / attribution filter, not a trade trigger. Ban CC marking for intraday chapters.

## R042 — Time-of-day liquidity U-shape

(1) Direction and mechanism.
• OPEN (high U, wide s): auction/MOO, opening-drive, and news-reaction families improve on a gross basis; die net if sized like midday — edge minus ~2–3× midday spreads (order of magnitude; illustrative multiple, direction documented).
• MID (low U, tight s): spread-capture, pair residual mean-reversion, passive making improve; impact-sensitive size improves. Momentum ignition dies (no volume to lean on).
• CLOSE: MOC/LOC, imbalance-follow (R043) improve; last-hour "alpha" in a VWAP backtest is often benchmark-flow, not signal.
• Mechanism: concentrated trading at open/close; imperfect competition among liquidity providers lifts spreads when demand to trade is highest.

(2) Evidence.
NASDAQ TAQ 2000–2021: U-shape in volume and spreads, stronger for small caps and high-imbalance names. Spreads/volume, not a PnL after-cost strategy paper. Trade-time vs calendar-time: some estimates of vol/Kyle λ fall through the day once you stop over-aggregating busy clocks — so "U-shape volatility" can be a measurement artifact.

(3) When the label fails.
• Scoring a half-day on the full-session CLOSE bucket.
• Using calendar-time realized vol as if it were liquidity.
• Tick-size regimes (2016 Tick Size Pilot; 2026+ tick reforms if any) break spread seasonality levels — re-estimate profiles after any tick-rule change.
• Retail-composition shifts move the open imbalance; 2019–2021 profiles are not 2026 profiles.

Bottom line: sizing + cost filter. Never an alpha trigger by itself.

## R043 — Closing-auction imbalance

(1) Direction and mechanism.
• Large persistent signed imbalance: follow-into-the-cross families improve; fading a still-growing MOC buy dies (you are trading against benchmark flow).
• Imbalance that is being offset / price already ran: fade-the-extension into T+1 open can improve; chasing the last print dies.
• Mechanism: official close is the benchmark; passive and index flow is price-inelastic in the last minutes. Published OI is a noisy but public forecast of that print. Last-15-minute returns covary with MOC imbalance in practitioner tapes.

(2) Evidence.
Auction impact papers estimate λ on x = OI / ADV with square-root impact from first imbalance print to close — price-impact / cost-of-trading evidence, not a clean after-cost retail backtest. Month-end / rebalance days: auction share of volume jumps — documented qualitatively.

(3) When the label fails.
• Treating a 3:45 print as a 3:58 print (imbalance mean-reverts as offsetting LOC arrives).
• Applying NYSE mechanics to Nasdaq NOII (different message, different timing).
• Using ImbZ as an intraday 10:00 signal — it does not exist yet.
• 0DTE / dealer-hedge flow around 15:50 can swamp a modest imbalance; historical ImbZ thresholds from pre-0DTE years mis-rank names.

(4) Compounds. R042 CLOSE + R043 ImbZ ≫ 0 = follow; R043 large + R048 near-band = R048 wins (stand down into a band).
Bottom line: trade trigger in the last ~15–20 minutes only, with a fade-vs-follow rule tied to persistence. Otherwise stand-down for discretionary fades.

## R044 — Market concentration (HHI)

(1) Direction and mechanism.
• High CR10 / low N_eff: cap-weight index momentum, mega-cap factor, and "SPX = top-10" overlays improve as descriptions of the index. Equal-weight vs cap-weight spreads widen. Breadth oscillators die as index timing tools (index can rally on five names).
• Low concentration: stock-selection and sector-rotation improve; single-name risk is less index risk.
• Mechanism: index PnL is a weighted sum; as ∑ w_i² rises, idiosyncratic diversifies less. This is arithmetic, then empirics on 2020s mega-cap weights.

(2) Evidence.
Index HHI / effective-N commentary (S&P, Morgan Stanley GIC) documents multi-decade highs in U.S. large-cap concentration — descriptive, not an after-cost timing rule.

(3) When the label fails — Gate rule.
Concentration is a slow structural regime. Using "CR10 crossed 38% this morning" as an intraday trigger is a misuse. Thresholds from 1999–2000 are not 2024–2026 thresholds without restating weights, not just HHI units. Misclassification cost: shutting off all single-name books because the index is concentrated throws away residual alpha that lives in the other 490 names.

Bottom line: factor tilt / risk budget. Not a trade trigger. Gate rejects intraday triggers off R044.

## R045 — Dispersion

(1) Direction and mechanism.
• High CSV: pairs, stat-arb, stock-picking, active long-short improve. Pair PnL scales with idiosyncratic vol; low dispersion starves pairs.
• Low CSV: market-beta, index vol-selling, and crowded factor books dominate; residual strategies die on Sharpe (nothing to be right about).
• Mechanism: CSV is a predictor of subsequent market realized vol in HAR models and a known state variable for active-fund opportunity.

(2) Evidence.
• Niu et al. (2023): CSV adds forecast power for market RV, in- and out-of-sample; economic value for a mean–variance investor claimed — forecast paper, not a pairs after-cost blotter.
• Cremers–Petajisto-style / "When Opportunity Knocks": active outperformance concentrates in high-dispersion months — documented direction for active vs passive.

(3) When the label fails.
• Survivorship: computing CSV on today's survivors overstates historical dispersion in crash months (dead names were the left tail).
• Cap-weight vs equal-weight CSV answer different questions; mixing them flips the regime.
• A one-day CSV spike on an index rebalance day is mechanical, not opportunity.

Bottom line: sizing input for residual books. High CSV → scale pairs up (risk units), not "buy the index."

## R046 — Factor crowding (momentum)

(1) Direction and mechanism.
• Crowded WML (high factor vol + extended trailing return) in a non-panic tape: momentum still has a positive mean historically — crowding is not an automatic short-WML trigger.
• Crowded WML into a rebound after a bear market: momentum dies violently. Loser betas spike; the short leg is a leveraged call on the market. Fades of losers get run over.
• Mechanism: Daniel–Moskowitz option-like loser payoffs + correlated exits (comomentum). Same math as "negative GEX chasing" in the user's analogy: hedging/covering chases the rebound.

(2) Evidence.
Daniel & Moskowitz, JFE 2016, U.S. 1927–2013 and other assets: crashes forecastable from prior bear + high vol + rebound; Mar–May 2009 losers +163% vs winners +8% — before-cost factor returns. Lou–Polk comomentum and later crowding papers: formation-period crowding predicts worse subsequent path — documented direction, implementation details vary.

(3) When the label fails — Gate rule.
R046 is slow-to-medium. An 85th-percentile vol print is not an intraday flatten. Structural breaks: the set of institutions running 12-1 momentum changed after 2009 and after CTA crowding episodes; comomentum levels are not stationary. Misclassification: calling every high-vol momentum month a "crash state" chops the right tail that paid the premium.

Bottom line: stand-down / de-gross flag in panic+rebound only; otherwise sizing input. Gate rejects 5-minute triggers off R046.

## R047 — News intensity / novelty

(1) Direction and mechanism.
• High intensity × high novelty: event-momentum, gap-follow, earnings-style continuation improve; mean-reversion and stale-news fades die.
• High intensity × low novelty (e.g. 4× median, novelty 0.12): stale-news fade improves; chasing headlines dies. Investors incompletely discount repeated text (Tetlock "old news").
• Low intensity: news-alpha books starve; technicals dominate.

(2) Evidence.
Tetlock (2011) and the "old news" line: repeated stories have weaker (or wrongly signed) reactions — documented direction, U.S. equities, before-cost event returns. Newer embedding-novelty papers exist; do not cite a specific cosine cutoff as literature. Glasserman–Mamaysky-type work links news composition to the overnight vs intraday split — useful joint with R041, not a novelty formula.

(3) When the label fails.
• Wire duplicates counted as intensity (bot farms).
• Embedding model drift (un-frozen model → novelty non-stationary).
• Earnings date without text still has a scheduled jump — novelty can look low if previews saturated the centroid, yet the print is new.
• Overnight embargoed news hits R041, not the 10:00 centroid.

(4) Compounds. R041 ON-dom + R047 novel = follow the gap; R041 + R047 stale = fade after the open auction; R042 CLOSE + R043 ImbZ ≫ 0 = follow; R043 large + R048 near-band = R048 wins; R045 high CSV + R044 high CR10 = keep residual books alive in the 490.
Bottom line: trade trigger only at the extremes (true shock vs clearly stale). Otherwise a filter.

## R048 — LULD / halt proximity

(1) Direction and mechanism.
• Near band / limit-state / pause: all directional liquidity-taking dies. Breakout-follow into a band is buying a reflecting barrier; fade into a band can work until the 15-second clock expires and a halt prints against you.
• Mechanism: trades cannot occur outside bands; 15 s limit-state → 5-minute pause. Signals that assume a free mid are misspecified.

(2) Evidence.
The LULD Plan is the evidence — it is market structure, not a backtest. Band percentages are documented. After-cost strategy evidence is thin because you are not supposed to be trading the boundary for alpha.

(3) When the label fails.
• Reconstructing bands from last sale instead of the official reference (5-minute mean, 1% update rule, 15:35 doubling).
• Parse failure treated as "bands OK."
• Tier 1 vs Tier 2 mix-up (5% vs 10%) — systematic mis-distance.
• After 15:35 the band widens; a morning 0.8σ rule is wrong.

(4) Compounds. R041 ON-dom + R048 near-band at the open = stand down. R043 large + R048 near-band = R048 wins.
Bottom line: stand-down flag. No exceptions for "the signal is strong."

## R049 — Rule 201 SSR

(1) Direction and mechanism.
• SSR on: strategies that hit the bid on the short side die (price test: no short at or below NBB). Long-side dip-buying and locate-constrained squeeze continuation can improve mechanically (short supply is kinked).
• SSR off: short-sale microstructure back to normal.
• Mechanism: statute, not a factor model. Official listing-market flag, rest of day + next day.

(2) Evidence.
17 CFR § 242.201 and SEC FAQs — legal fact. Empirical papers on whether Rule 201 "worked" are mixed and not required to use the flag as a constraint.

(3) When the label fails.
• Homemade −10% from SIP last sale before the listing market disseminates — you will trade as if SSR is on when it is not (or the reverse).
• Applying SSR logic to ETFs/options overlays incorrectly.
• Overnight session: restrictions apply when an NBB is disseminated per the rule text — do not assume 24x5.

(4) Compounds. R049 SSR + R045 high CSV = short leg of pairs is constrained; pair books become asymmetric.
Bottom line: stand-down flag for aggressive shorts; constraint in the emulator. Not an alpha trigger.

## R050 — SIP vs direct divergence

(1) Direction and mechanism.
• If you actually observe divergence (you do not, on this Mac): mid-point / queue / cross-venue race strategies improve for the colocated book and die for the SIP book — the SIP trader is providing the edge.
• On SIP-only research: those strategy families are not identified. Apparent HFT alpha is timestamp fiction.
• Mechanism: SIP quote path ~1 ms behind engine time in documented samples; most trades still print when NBBOs match, so economic size of the arb is limited but the backtest lie is not.

(2) Evidence.
Microsecond-timestamp work on DJIA names: mean SIP quote lag ~1,128 μs; 97% of SIP-priced trades when the two NBBOs agree — documented microstructure, not a strategy Sharpe.

(3) When the label fails.
• Declaring "no divergence today" because two SIP vendors match.
• Using R050 as a daily regime toggle on a laptop.
• Structural: SIP latency fell after processor upgrades (median cited from hundreds of μs toward tens) — old dislocation rates are stale.

Bottom line: capability gate / chapter stamp, not a signal. State = UNKNOWN without MBO/ITCH colo. Stamp latency chapters simulated only — requires MBO/ITCH.

## How they compound (joint states)
Write compounds as ordered conjunctions, most specific first.
| Joint state | What happens to books |
| R041 ON-dom + R042 OPEN + R047 novel | Follow the gap gross; cut size for R042 spreads; do not fade. |
| R041 ON-dom + R047 stale | Gap is headline recycling — fade after the open auction, not CC. |
| R042 CLOSE + R043 ImbZ ≫ 0 | Follow; R042 costs are paid into the auction, not in continuous. |
| R043 large + R048 near-band | R048 wins. No follow into a band. |
| R045 high CSV + R044 high CR10 | Index is a mega-cap factor; pairs inside the 490 can still pay. Do not kill residual books just because CR10 is high. |
| R046 crowded WML + rebound + R045 high CSV | Crash-watch: losers bounce hardest — the residual book is the crash. De-gross WML shorts. |
| R049 SSR + R045 high CSV | Short leg of pairs is constrained; pair books become asymmetric. |
| Any + R050 UNKNOWN | Strip sub-second claims from the chapter. |

Priority when regimes conflict: R050 gate (identification) → R048 halt → R049 SSR → R043 auction (time-boxed) → R047 news extremes → R042 cost surface → R041 attribution → R045 sizing → R046 sizing → R044 tilt. That is why a chapter never lists all ten.

## Annotation discipline for the existing 200 chapters
1. Cap = 6 regimes, sorted by the priority list above, not by number.
2. Most-specific wins. "R049 SSR-on, therefore short-at-bid disabled" beats "R044 concentrated."
3. Every annotated line states direction:
   • Bad: "Also see R042."
   • Good: "R042 OPEN: this opening-drive backtest is gross-strong, net-weak — apply OPEN spread multiplier; do not use MID costs."
4. Type-tag each citation in the chapter header: trigger | sizing | tilt | stand-down | attribution | gate
5. Slow regimes (R044, R046, and the R041 premium itself) may appear only as tilt / sizing / stand-down. If a chapter fires a 5-minute order off CR10 or WML-p85, Gate rejects.
6. R050: if the chapter's horizon < 1 s or uses queue/NBBO races, mandatory footer: simulated only — requires MBO/ITCH. If horizon is minutes–days, omit R050.
7. Costs. If the source is before-cost, the annotation must say before-cost. Do not launder overnight-premium papers into after-cost OPEN scalps.
8. Half-days. Any R042 mention must say which profile (full vs early_close).

## Honest bottom line (one line each)
| Regime | Role |
| R041 | Attribution / tilt. Do not mark intraday strategies CC. Not a day trigger. |
| R042 | Sizing / cost surface. OPEN gross≠net. Half-day profile required. |
| R043 | Time-boxed trigger (last ~15 min), follow-vs-fade by persistence. |
| R044 | Factor tilt / risk budget. Gate: no intraday trigger. |
| R045 | Sizing input for residual / pairs. Low CSV starves them. |
| R046 | De-gross / stand-down only in panic+rebound; else sizing. Gate: no intraday trigger. |
| R047 | Filter + rare trigger (novel shock vs stale fade). |
| R048 | Stand-down flag. Parse fail = halted. |
| R049 | Stand-down / constraint on aggressive shorts. Official flag only. |
| R050 | Capability gate. On this desk: UNKNOWN. Stamp, don't estimate. |

=== END ===

Execution notes for parent: (1) Sign-in: saved-session restore on first attempt returned "hydrated" but the grok.com page still showed signed-out; navigating back to grok.com after accounts.x.ai confirmed "Welcome, Praveen" — signed in as Praveen Gupta. (2) Cookie banner: rejected optional cookies. (3) No rate limits encountered; all three responses completed fully. (4) A1 took ~2m34s of generation, A2 ~1m25s, A3 ~10s. (5) Minor truncation flags: a few tolerance numbers in A2's verification table and two or three sentence fragments were truncated in the page's own extraction; flagged inline rather than invented. (6) Model select showed "Fast" mode; task did not specify a thinking mode. (7) No purchases, submissions, or account changes made.
