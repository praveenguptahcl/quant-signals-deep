# TB2 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials (account: Praveen Gupta)
- Date: 2026-09-10
- Chat: https://grok.com/c/032430e3-32b7-4aad-b6aa-430013df0179
- Batch: TB2 — Core reversal & momentum infrastructure (T011–T020)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim via page text extraction.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: spacing normalized from page rendering; wording, numbers, and citations preserved. Bracketed notes are the browser task's own capture notes, not Grok's text. Grok's Q3 response ends mid-sentence ("…is a surviving but small,") — that is how the page showed it.
- All numeric thresholds below are illustrative examples, not estimated or claimed-optimal parameters. Nothing here is a live-trading spec.

---

## Q-TB2-1 — mechanics + worked example (verbatim)

"All four are mean-reversion / quality-filter overlays, not trend systems. Thresholds below are examples only — they must be re-estimated on your instrument, session, and cost regime. Edges in short-horizon reversal are small; costs decide."

### Shared cost model used in every example
• Half-spread paid on entry and exit (round-trip spread).
• Commission: $0.005/share + $0.50/ticket (example).
• No borrow fee (assume long-only or liquid short).
• Fill = mid ± half-spread. Slippage extra only if noted.

### (A) Short-term reversal timed at the bid–ask bounce

Idea. Liquidity-shock reversals: a sell-initiated print that hits the bid, then the book replenishes and mid ticks back. You buy into the bounce.

Example thresholds (illustrative)
• Universe: liquid names, spread ≤ 5 bps, ADV ≥ $50M.
• Signal bar: 1-second or 100-ms L2.
• Bounce trigger: mid drops ≥ 8 bps in ≤ 2 s; last print is on the bid; bid size after print ≥ 1.5× pre-print bid size (replenish).
• Entry: buy at the offer (or mid+1 tick) once bounce candle prints higher mid.
• Exit: first of (i) mid recovers 60–80% of the impulse, (ii) +4 s time stop, (iii) mid makes a new extreme.
• Size: risk $200 per name; stop = impulse low − 1 tick.
• Risk limits: max 3 concurrent names; daily stop −0.8R aggregate; quoted spread > 1.5× the 20-session median → veto (example).

Worked synthetic example
Stock XYZ. Mid $50.00, bid 49.99 / ask 50.01 (spread $0.02).
t=0: aggressive sell, mid → $49.96 (impulse −8 bps). Bid replenishes 2k → 4k.
t=1.1s: mid $49.97, last print lift.

| Step | Price | Side | Shares | Cash | Notes |
| Entry | 49.98 (ask after 1-tick improve) | Buy | 1,000 | −49,980 | half-spread paid vs mid 49.97 |
| Commission in | — | — | — | −5.50 | 1000×0.005 + 0.50 |
| Exit (80% bounce of 4¢ impulse) | 49.992 | Sell | 1,000 | +49,992 | mid ~49.993, sell bid 49.992 |
| Commission out | — | — | — | −5.50 | |
| Gross P&L | | | | +12.00 | 1,000 × $0.012 |
| Costs | | | | −11.00 + implicit remaining 1¢ of spread on exit already in fill | |
| Net P&L | | | | +$1.00 | ~2 bps on notional after costs |

"If bounce fails and stop hits 49.95: net ≈ −$35 (stop + two commissions + spread). Edge only exists if bounce probability × payoff beats the guaranteed spread/commission."

### (B) Jump-filtered overnight-gap fade

Idea. Small, non-informational overnight gaps often mean-revert in the cash session (CO–OC / gap-fill literature); jump-sized gaps are continuation candidates and get filtered out.

Example thresholds
• Gap = (open − prior close) / prior close; ATR20.
• Trade only gaps ≤ 0.40×ATR20. Skip if overnight range > 2.5× median (jump filter, example).
• No earnings, no after-hours volume > 30% of 20-day ADV.
• Entry: 09:35–09:45 if first 5-min bar does not extend the gap by > 0.15×ATR.
• Side: short gap-up / long gap-down.
• Target: 50–100% fill toward prior close.
• Stop: gap extreme ± 0.35×ATR.
• Time stop: 11:30 if unfilled.
• Size: 0.25% of equity risked to stop.
• Limits: 1 name per sector; skip if VIX > 28 (example regime cut).

Worked synthetic example
Prior close 100.00. Open 100.80 (+0.80%). ATR20 = 2.40 so gap = 0.33×ATR — not a jump, fade allowed.
09:40: price 100.72, no extension. Short 400 shares (stop 101.64 = open + 0.35×ATR).

| Step | Price | Side | Shares | Cash |
| Entry | 100.70 (bid) | Sell short | 400 | +40,280 |
| Comm in | | | | −2.50 |
| Target 75% fill (toward 100.00) | 100.20 | Buy cover | 400 | −40,080 |
| Comm out | | | | −2.50 |
| Gross | | | | +200.00 |
| Net P&L | | | | +$195.00 |

"Stop path: cover 101.66 → gross −384, net ≈ −$389."

### (C) RSI-2 / IBS extreme fade

(Connors-style): 2-period RSI extremes inside a slow trend filter. Classic published bands are far tighter than RSI(14): RSI-2 < 10 (example) then exit on recovery. Close near the low (IBS < 0.2) → long fade; near the high (IBS > 0.8) → short fade.

Combined example rules (daily, liquid ETF)
• Regime: close > 200-SMA for longs only.
• Entry (close): RSI-2 < 8 and IBS < 0.15.
• Exit (close): RSI-2 > 65 or IBS > 0.70 or +5 trading days.
• Stop: −1.8×ATR(10) from entry close (example).
• Size: 1.0% equity risk to stop.
• Limits: max 8 names; no add; skip if dollar volume < $20M that day.

Worked synthetic example (long)
QQQ-like. Close 480.00, H=483, L=478 → IBS = (480−478)/(483−478) = 0.40 (not extreme). Next day: H=4… [day-2 bar values truncated on the page; Grok's example then enters with entry close 474.60, RSI-2 < 8 and IBS < 0.15, entry at 474.62]
Equity $200k, ATR10 = 6.0, stop = 474.60 − 1.8×6 = 463.80, risk/share = $10.80 → size = 185 shares.

| Step | Price | Side | Shares | Cash |
| Entry (close + half-spread 2¢) | 474.62 | Buy | 185 | −87,804.70 |
| Comm in | | | | −1.425 |
| Exit 3 days later, C=479.40, IBS=0.72 | 479.38 | Sell | 185 | +88,685.30 |
| Comm out | | | | −1.425 |
| Gross | | | | +880.60 |
| Net P&L | | | | +$877.75 |

### (D) Triple-barrier + meta-labeling as a sizing layer

Primary model only chooses side. Triple-barrier labels the realized path. A second model predicts "bet succeeds" from features and scales size; it does not flip the side.

Triple-barrier (example). For a long signal at time t, volatility = 20-day ATR (or stdev of daily returns), upper = +2σ (profit take), lower = −1σ (stop), vertical = 10 bars. Label for meta-training: 1 if upper hit first, 0 otherwise (stop or time).

Sizing (example). Base risk 0.50% of equity. Multiplier = max(0, (p − 0.50)/0.25) so p=0.50 → flat, p=0.75 → full; cap. Hard cap 1.5% equity; veto if p < 0.55.

Five synthetic primary signals. Assume equity $200,000, base risk $1,000, stop distance $2.00 → base shares = 500 if p high enough.

| # | Primary side | Features (sketch) | Meta p | Size multiplier | Shares | Barrier outcome | Gross $ | Costs $ | Net $ |
| 1 | Long | quiet vol, IBS 0.12 | 0.82 | 0.64 | 320 | +2σ hit | +640 | 8 | +632 |
| 2 | Long | news spike, wide spread | 0.48 | 0 (veto) | 0 | would have −1σ | 0 | 0 | 0 |
| 3 | Short | RSI-2=94, trend down | 0.71 | 0.42 | 210 | time expiry −0.3σ | −63 | 7 | −70 |
| 4 | Long | gap-fade setup | 0.61 | 0.22 | 110 | +2σ | +220 | 6 | +214 |
| 5 | Short | crowded, high ADV | 0.90 | 0.80 | 400 | −1σ (adverse) | −800 | 8 | −808 |

"Without meta-labeling, cases 1–5 would all be 500 shares. Meta:
• kills #2 (avoids a full stop),
• shrinks #3 and #4,
• keeps #1 and #5 large.
Net of the five: +$632 −70 +214 −808 = −$32 vs a naïve equal-size book that would have taken the full #2 stop as well (worse). That is the intended gain: higher precision, variable bet size, not a new directional alpha."

Practical notes
• Mark every number above as a template, not a live parameter.
• Cost dominance: (A) dies first; (B)/(C) need cheap index products; (D) only helps if the primary already has edge.
• Combine, don't stack blindly: e.g. use (C) or (B) as the primary side, (D) only as the size overlay.

---

## Q-TB2-2 — infra + local build + buy vs build (verbatim)

"A 128 GB M5 Max (18-core CPU, up to 40-core GPU, 614 GB/s unified bandwidth on the top GPU config) is enough to research and paper-trade all four TB2 layers locally. It is not a co-located matching engine. The constraint is data quality and engineering time, not FLOPs."

### Machine budget (what 128 GB actually holds)
| Workload | Resident set (typical) | Fits? |
| 3,000 names × 20y daily OHLCV + factors | 2–4 GB parquet | Yes |
| Same universe × 1-min bars, 10y | 80–180 GB compressed / 250–400 GB raw | Tight; keep 5–7y hot, rest on external SSD |
| Overnight + 1-min open auction window only | 15–40 GB | Yes |
| RSI-2/IBS 1-min engine, rolling 60d | <8 GB | Yes |
| NBBO quotes for bounce defense (top 500 names, 2y, 1s CBBO) | 200–600 GB | No — stream/shard to 4–8 TB external NVMe |
| Triple-barrier labels + feature matrix (3k names, 10y daily events) | 10–30 GB | Yes |
| Meta-model train (LightGBM / small MLP, not a 70B LLM) | 8–20 GB | Yes |

"Throughput ballpark on M5 Max, Polars + Numba/MLX, not naive pandas:
• Daily cross-section 3,000 names: <2 s per date (screen + rank).
• 1-min IBS/RSI-2 over 3,000 names × 390 bars: ~20–60 s/day of history if vectorized; overnight batch of 10y ≈ a few hours first pass, minutes incremental.
• Triple-barrier first-touch on daily events: minutes per year of sample.
• Full quote-mid rebuild for 500 names × 1 year of 1s BBO: [minutes to hours], I/O bound.
Storage to buy: 2 TB internal + 8 TB Thunderbolt NVMe. Do not keep raw SIP quotes on the boot disk."

### Piece-by-piece cost

#### 1) Daily reversal screen — 3,000 stocks
Job: survivorship-safe universe, overnight + 1-day return, ADV, spread proxy, industry residual.
| Item | Cheapest adequate | Indicative $ |
| Data | Norgate US Platinum (delisteds + historical index members) or Massive/Polygon Stocks Developer $79/mo | Norgate Platinum ~$630/yr; Massive Developer $79/mo ($948/yr); $79/mo if you accept weaker delisting |
| Compute | Local, nightly | $0 incremental |
| Eng hours | Universe + point-in-time join + screen: 40–80 h; residual reversal + costs: +40 h | — |

"Throughput: one Mac core-night is overkill. Buy vs build: buy data, build the screen. Do not build a CRSP replica."

#### 2) Overnight-gap scanner + jump filter
Job: …, ATR, news/earnings flag, first 5–15 min extension, fill target.
| Item | Cheapest adequate | Indicative $ |
| Data | Daily OHLC plus official open + pre/post prints. Massive Advanced $199/mo (opens + trades) or FirstRate 1-min one-time dump | Massive Advanced ~$199/mo; FirstRate 1-min all-stocks historically often low hundreds–low thousands one-time (check current cart) |
| Earnings calendar | Nasdaq / Benzinga / TradingView calendar scrape is not PIT; Norgate extras or Polygon corporate actions included in Gold/Platinum or Advanced | |
| Eng hours | Scanner + filters: 30–50 h; auction-quality open: +20 h | — |

"Open price on vendor daily bars is often a [composite], not a quote midpoint. That is already a bounce problem (see last section)."

#### 3) RSI-2 / IBS "intraday" engine
True Connors RSI-2 is daily. An intraday engine is 1-min or 5-min IBS + 2-bar RSI on RTH bars.
| Item | Cheapest adequate | Indicative $ |
| Data | 1-min aggregates, 5–10y, ~3k names + ETFs. Massive Starter/Developer flat files or FirstRate 1-min | Massive $29–79/mo for bars; quotes not needed for IBS/RSI-2 itself |
| Compute | Vectorized over symbols in Polars; GPU optional | $0 |
| Eng hours | Indicators + session clock + exits: 25–40 h; production scheduler: +15 h | — |

"This piece is the cheapest compute and the least data-hungry. Do it first."

#### 4) Triple-barrier + meta-labeling stack
Job: CUSUM or primary-signal events → vol-scaled 3 barriers → binary meta-label → secondary classifier → P(success) → max(0, (p−0.5)/0.25) sizing. López de Prado AFML Ch. 3 & 10.
| Item | Cheapest adequate | Indicative $ |
| Data | Same as primary (daily or 1-min). Quotes only if you label on mid, not last. | Incremental $0 if bars already bought |
| ML | LightGBM / XGBoost / small sklearn; not an LLM | $0 local |
| Eng hours | Labeling engine + purged CV: 80–150 h; feature store + inference: +40–80 h; if you insist on tick-path barriers: +100 h and quote data | — |

"128 GB is plenty for tabular meta-models. Do not fine-tune a 70B model for this."

### Data stack recommendation (cheapest adequate)
Research stack that actually supports TB2 without lying to yourself:
1. Norgate Platinum (~$630/yr) — PIT universe, delisteds, index members. Mandatory for the 3,000-name daily screen.
2. Massive Stocks Advanced ($199/mo) — 1-min + trades + quotes when you need midpoints; 20y history on that tier.
3. Optional Databento — only if you need clean CBBO-1s / TBBO for bounce defense on a narrow universe. Standard includes last 12 months L1; older L1 is usage-priced. Full multi-year SIP-like quotes across 3k names [truncated on page].
"Year-1 cash (indicative): Hardware already owned + 8 TB disk ~$400–700 + data $2.5k–4k + your hours. Do not start with NYSE Daily TAQ. Quote files are ~38 GB/day uncompressed [in that] class; that is a firm feed, not a garage project."

### Engineering hours (realistic solo, production-grade research not a hedge fund)
| Piece | Hours |
| Shared: ingest, splits, calendar, corporate actions, parquet lake | 40–70 |
| Daily 3k screen | 40–80 |
| Gap + jump filter | 30–50 |
| RSI-2/IBS engine | 25–40 |
| Triple-barrier + meta + purged CV | 80–150 |
| Bounce-defense mid pipeline | 40–80 |
| Paper broker + risk limits + logging | 40–60 |
| Total | ~300–530 h |

"One focused quarter of nights/weekends if the data lake is done first. The ML stack is the long pole."

### Buy vs build verdict
| Layer | Verdict |
| Market data | Buy. Building a SIP is a career. |
| PIT universe / delisteds | Buy Norgate (or CRSP if you ever get academic access). |
| Feature math, screens, TB labels, meta-model | Build. This is the IP. |
| Execution / OMS | Buy a broker API (IBKR etc.); don't write a matching engine. |
| Quote-mid research subset | Buy sampled BBO (1s/1m CBBO), don't buy full quotes for 3,000 names. |
| LLM-as-alpha | Don't buy. Wrong tool. |

"Bottom line: On this Mac, build the research plant, rent the tape. Skip L2/L3. Cap quote history to liquid names and sampled mids."

### Where bid–ask bounce contaminates reversal backtests

"Short-horizon reversal estimated on transaction prices mixes three things:
1. Roll bounce — last sale flips bid↔ask. A downtick that is only 'last hit the bid' mean-reverts by half the spread with no alpha. Variance-ratio / lag-1 tests show this as a magnitude channel at lag 1, not a signed information channel.
2. Close-to-open and close-to-close using last sale embeds the closing print's side. Small-cap, wide-spread names look like monsters on paper.
3. Open print for gap fades is often an auction imbalance print, not a mid. Fading 'gaps' of 10–20 bps on a 20 bp spread is spread-paying theater.
Literature that takes reversal seriously either (a) uses quote midpoints, (b) skips the last minutes of the day, or (c) residualizes industry + shows the effect survives on mids. End-of-day reversal papers explicitly check TAQ mids vs trades for this reason."

Symptoms in your backtest
• Gross edge ≈ 0.5 × quoted spread on the names you trade.
• Edge vanishes after a $5 or $10 price filter and a 50 bps spread cap.
• Sharpe dies when you enter/exit at mid ± half-spread instead of last.
• Win rate stays high, average win ≈ 1 tick.

Defense: quote-midpoint accounting (build this)
Principle: signal and P&L live on different prices.
1. Signal price: quote midpoint. Optional: size-weighted microprice. Microprice is a better efficient-price proxy at short horizons.
2. Fill price = conservative executable. Long entry = ask (or mid + half-spread + 1 tick if you model queue miss). Never fill the backtest at last sale or at mid.
3. Implementation on the Mac (adequate, not TAQ-complete):
   • Store 1-second or 1-minute CBBO for the tradable subset (Russell 1000 / ADV filter), not 3,000 names of every quote update.
   • Align bars: mid_open, mid_close as last valid NBBO in the bar with both sides live and spread < k × median.
   • Drop locked/crossed, zero-size, LULD-hold, and odd-lot-only tops.
   • Daily screen: compute overnight return as 09:35 [mid-open] vs 15:55 [mid-close], not CRSP close/open. Skipping the first/last 5–15 minutes kills a lot of bounce and auction junk.
   • Report three P&L columns: mid-to-mid (diagnostic), mid-to-touch (research), touch-to-touch + fees (tradable).
4. Statistical gates before you trust a reversal:
   • Repeat the sort on mid returns; if t-stat collapses, it was bounce.
   • Cap spread; require price ≥ $5, ADV ≥ $20M (example).
   • Skip one bar after the signal (Lehmann / Lo–MacKinlay non-synch defense).
   • Cost model: half-spread + 0.5–1 tick + commission; if net Sharpe < 0.5 after that, there is no strategy.
5. What not to do:
   • Don't use Polygon "last" daily bars as if they were mids.
   • Don't train the meta-labeler on last-sale triple barriers then size live on NBBO. Label on the same mid path you will trade.
"That defense is the difference between a TB2 research book and a spread-harvesting illusion. Build it before you spend another 100 hours on the meta-model."

---

## Q-TB2-3 — success ratios, after-cost efficacy, failure modes (verbatim)

"Honest read of the literature: several of these edges are real as statistical patterns and weak or dead as stand-alone, costed, capacity-bearing strategies. Numbers below are from the papers, not vendor blogs."

### 1) Short-term reversal after costs, and how much is bid–ask bounce

Gross magnitudes (the originals)
• Jegadeesh (1990): monthly loser–winner spread ~2.49% per month (1934–1987), extreme deciles.
• Lehmann (1990): weekly winners/losers reverse the next week; he argued profits survive plausible costs and a spread correction, and interpreted them as liquidity-provision rents around large moves.
• Avramov–Chordia–Goyal (2006) restated the folklore as ~1.7% per week (Lehmann) and ~2.5% per month (Jegadeesh) gross.

How much is bounce
• Kaul–Nimalendran (1990), NASDAQ 1983–87: transaction-price reversals are mostly bid–ask measurement error. On bid-to-bid returns the short-horizon negative autocorrelation disappears and turns positive. They estimate about half of measured daily variance is bounce-induced.
• Jegadeesh–Titman (1995, "Short Horizon Reversals and the Bid-Ask Spread") attribute a large part of remaining short-horizon negative autocovariance to inventory / temporary price pressure, not behavioral overreaction.
• Heston–Korajczyk–Sadka (2010) separately: same-day half-hour reversal is liquidity imbalance lasting < 1 hour plus bounce; the next-day same-slot continuation is not explained by spreads.

After costs
• Avramov–Chordia–Goyal (2006): largest reversals sit in high-turnover, low-liquidity names. Contrarian profits < likely transaction costs. They treat the EMH "violation" as not egregious.
• de Groot–Huij–Zhou (2012): on a broad universe (incl. small caps) they replicate ACG — net of Keim–Madhavan-style costs the strategy is negative. Restrict to largest names and cut turnover (don't immediately exit a name that leaves the extreme decile): they claim +30 to +50 bp per week net. On Europe, even "smart" construction is much harder; broad-universe net is highly negative.
• Their own slides: 1,500-name book, 780% weekly turnover, gross ~93 bp/week, net ≈ −50 bp/week. Profit only after shrinking to top 100–500 and slashing turnover.

"Takeaway: bounce explains the daily last-sale version almost completely. A residual liquidity-provision liquidity-provision reversal in large caps can survive costs if turnover is crushed. A naïve 3,000-name daily screen does not." [note: 'liquidity-provision' appears duplicated in Grok's text]

### 2) Overnight-gap fade after costs — when it goes to zero/negative

"Distinguish three different objects people mix up:"

| Object | Gross pattern | After costs |
| Hold the close, skip the open (overnight premium) | Large and persistent (Lou–Polk–Skouras; index overnight vs intraday) | You still pay the open and the close. At ~5 bp RT/day many "own the night" baskets lose to buy-and-hold; at 10 bp they lose to cash. |
| Fade a small no-news gap back to prior close | Fill rate high only for tiny gaps. Example industry tape: full fill ~44% for 0–0.5% gaps, ~27% for 1–2%, ~8% above 6%. Intraday close-vs-open is ~50/50 regardless of gap size. | — |
| Fade every open | Coin flip + gap-extension left tail | Stops on 2–3% news gaps wipe the small-gap wins. |

"There is no Jegadeesh-class paper that says 'gap fade earns X% net.' What exists is:
• Fill probability collapses with gap size (so an unfiltered fade book is short a crash).
• Overnight continuation (the premium) is the opposite trade of a fade.
• Costed 'own overnight only' implementations go flat to negative at retail-to-pro friction.

Takeaway: unfiltered gap fade is not an academic anomaly that 'stopped working'; it was never shown to be a robust net edge. A jump-filtered, small-gap, no-catalyst fade can have a high win rate and still be zero after spread + the one unfilled 3% gap."

### 3) RSI-2 / IBS Connors systems — drawdowns and regime failure

"What Connors published (2008, Short Term Trading Strategies That Work): buy index/ETF when 2-period RSI < 5–10 and price > 200-SMA; exit on a short MA or RSI recovery; often no stop. High win rate, small average win."

Documented pain
• Independent RSI-2 evaluation (Ulrich / MarketSci replication era): max DD ≈ −15.7% in Oct 2008, trough in 5 days; other DDs of 7–9% that take months to recover. The system clumps losers.
• Later Connors-family tests (R3, multi-day-down): portfolio max DD ≈ −16% (Aug 2011); ~half the original ETF list worse in the subsequent 12 years. CAGR on a constrained SPY/QQQ book often mid-single digits with ~15% DD.
• "Holy Grail" replication on single-name / leveraged variants: one published walk-forward shows almost all of the 17.8% CAGR earned pre-2008; post-2008 the book loses to the benchmark, high turnover (~2 RT/day).
• IBS daily mean-reversion (QuantifiedStrategies-type tests): win rate ~68–76%, max DD often −13% to −26% depending on rules; works better in bear / high-vol regimes than in 2013–19 grind-up.

Regime failures (structural, not just "2008")
1. No-stop rule + a multi-day waterfall (2008, 2011, Feb 2018, Mar 2020 open) = the left tail Connors accepted.
2. 200-SMA long-only filter keeps you out of the best mean-reversion tape (crashes) or strands you if you drop the filter.
3. Trend years (2013–19, 2021, 2023–24): few RSI-2 < 5 events; opportunity cost vs buy-and-hold is the real "failure."
4. Applying daily Connors rules intraday on stocks imports bounce; that is not the published test.

"Takeaway: on liquid index products the pattern is not dead; it is a high-win, low-CAGR, 10–20% DD, high time-in-cash sleeve. It fails as a wealth engine and as a no-stop system in crashes."

### 4) End-of-day drift and first-half-hour → last-half-hour momentum

Cross-section, same clock time (Heston–Korajczyk–Sadka 2010)
Returns in a given half-hour continue in the same half-hour the next day, lags 13, 26, … half-hours, out to ~40 days. Strongest in the open slot (~11 bp) and close slot (~8+ bp); midday ~1.75 bp. Spreads / volume / OI do not explain the continuation. Adjacent half-hours reverse (bounce + transient liquidity). They argue timing rebalance flow can save about an effective spread.

Time-series, market (Gao–Han–Li–Zhou, "Market Intraday Momentum," 2018)
First half-hour return of SPY predicts the last half-hour. Predictive R² ≈ 1.6%; adding the 12th half-hour → R² ≈ 2.6%. Stronger on high-vol, high-volume, recession, and macro-news days. Also present in other liquid ETFs. Sample 1993–2013.

Overnight vs intraday split (Lou–Polk–Skouras 2019)
Firm-level overnight and intraday returns each continue for years and reverse across the close/open. Of 14 anomalies: momentum and short-term reversal earn their premia overnight; most other anomalies earn them intraday, often with the opposite sign in the other session. Overnight winner–loser 3-factor alpha 3.47%/month (t=16.8) overnight, and the opposite sign during the day.

End-of-day "drift" as arbitrage unwind (Bogousslavsky 2021)
A mispricing factor is positive through the day and poor in the last 30 minutes; size/illiquidity premia realize in the last half-hour. Interpretation: overnight margin / locate costs make arb flatten before the close. Effect larger in the second half of the sample. A 1% shock to expected overnight vol of the mispricing factor worsens the last-half-hour mispricing by ~26 bp.

Closability
• HKS same-slot continuation: tradable in principle if you trade the same 30-minute window, but capacity is flow-timed; you are racing institutional VWAP/MOC.
• Gao et al. first→last half-hour on SPY: one trade a day in the most liquid name; this is the closable piece, but the raw R² is small — after 1–2 ticks and missing the 15:45–16:00 auction you keep a fraction of the paper 1.6% R².
• Lou et al. overnight anomaly cannot be harvested by "buy close, sell open" at retail costs (see §2).
• Last-30-minute anomaly unwind is a reason not to lift offers into the close on crowded mean-reversion.

### 5) Meta-labeling — what it actually adds

"López de Prado (AFML 2018, Ch. 3): primary model picks side; secondary model predicts P(triple-barrier success) and sizes / vetoes. It is not a second alpha source."

Honest empirical picture
Daru Finance replication on a vanilla EMA-crossover primary, 42 instruments (crypto perps, US ETFs, FX):
• Profit factor lifts in 38/42; DSR in 39/42.
• Instruments with PF > 1: 12 → 24.
• 0/42 clear DSR > 0.95 after meta.
• Typical move: crypto PF 0.92 → 1.03, ETF PF 0.75 → 1.03, FX 0.85 → 0.94. Sharpe from deeply negative toward ~0.
• Their line: "precision filter, not an alpha source." It can take a cost-losing primary to break-even, not to a deflated Sharpe that survives multiple testing.

"That matches the theory: meta-labeling raises precision, cuts recall. Sharpe improves only if the kept bets still have a positive expected value net of costs. If the primary's edge was bounce or turnover, the secondary learns to veto some noise and still inherits a zero-mean residual."

What it is good for
• Kill trades in bad regimes (wide spread, news, high overnight vol).
• Map [p] into size instead of 0/1.
• Combine with purged/embargoed CV so you don't leak the barrier path.

What it is not
• A substitute for a mid-based, costed primary.
• A reason to run 3,000 names of last-sale reversal and "let the meta-model fix it."

One-line synthesis
"Bounce and cost eat classic last-sale reversal and blind gap fades. Connors RSI-2/IBS is a surviving but small," [Grok's response ends mid-sentence here on the page; nothing after it]

---

## QC notes (orchestrator)

1. Q1 (D) sizing-rule inconsistency: the text states "Multiplier = max(0, (p − 0.50)/0.25) so p=0.50 → flat, p=0.75 → full; cap" but the worked table's multipliers (0.64, 0.42, 0.22, 0.80 for p = 0.82, 0.71, 0.61, 0.90) exactly match (p−0.50)/0.50, not /0.25, and shares (320/210/110/400) are 500× those values. The veto (p<0.55) and the +$632 −70 +214 −808 = −$32 total are internally consistent.
2. Q1 (C): the day-2 synthetic bar's H/L/O values were truncated on the page ("Next day: H=4…"), but entry close (474.60 → entry 474.62) and all table arithmetic are consistent: 185×4.76=880.60 gross; 880.60−2.85=877.75 net.
3. Q1 (D): threshold formulas render without numeric σ values for upper/lower barriers ("Upper: (profit take)", "Lower: (stop)") — the 2σ/1σ values appear in the table outcomes instead.
4. Q2: engineering-hour subtotals sum to 295–530 h, rendered as "~300–530 h" — consistent.
5. Q2: some table cells (Job rows, earnings-calendar price, some verdict cells) were truncated in page rendering; captured text is verbatim to what was displayed.
6. Q3: the final "One-line synthesis" is cut off mid-sentence on the page itself ("…is a surviving but small,") — this is how Grok's response ended; nothing after it.
7. Q3 §2: the "Fade a small no-news gap back to prior close" table row has no "After costs" cell content (empty on the page).
8. Q3 §1 takeaway contains a duplicated token in Grok's text: "A residual liquidity-provision liquidity-provision reversal in large caps can survive costs…" — preserved verbatim.
9. Key sourced claims are research leads, not verified facts: Jegadeesh 1990 (2.49%/mo); Lehmann 1990 (weekly reversals); Avramov–Chordia–Goyal 2006 (contrarian profits < costs); Kaul–Nimalendran 1990 (bounce explains daily reversals); de Groot–Huij–Zhou 2012 (+30 to +50 bp/wk net, large-cap only); Heston–Korajczyk–Sadka 2010 (~11 bp open slot); Gao–Han–Li–Zhou 2018 (R² ≈ 1.6%); Lou–Polk–Skouras 2019 (overnight 3-factor alpha 3.47%/mo); Bogousslavsky 2021 (1% shock → ~26 bp mispricing); López de Prado AFML 2018 (triple-barrier, meta-labeling). Vendor prices: indicative — verify before budgeting.

---

## Source list (only papers actually used)

- Jegadeesh, N. (1990), "Evidence of Predictable Behavior of Security Returns," Journal of Finance.
- Lehmann, B.N. (1990), "Fads, Martingales, and Market Efficiency," Quarterly Journal of Economics.
- Kaul, G. and Nimalendran, M. (1990), "Price Reversals: Bid-Ask Errors or Market Overreaction?", Journal of Financial Economics.
- Jegadeesh, N. and Titman, S. (1995), "Short Horizon Reversals and the Bid-Ask Spread."
- Avramov, D., Chordia, T. and Goyal, A. (2006), "Liquidity and Autocorrelations in Individual Stock Returns."
- de Groot, W., Huij, J. and Zhou, W. (2012), "Another Look at Trading Costs and Short-Term Reversal Strategies."
- Heston, S.L., Korajczyk, R.A. and Sadka, R. (2010), "Intraday Patterns in Time-Series and Cross-Sectional Stock Returns."
- Gao, L., Han, Y., Li, S.Z. and Zhou, G. (2018), "Market Intraday Momentum."
- Lou, D., Polk, C. and Skouras, S. (2019), "A Tug of War: Overnight vs. Intraday Expected Returns."
- Bogousslavsky, V. (2021), "The Cross-Section of Intraday and Overnight Returns."
- López de Prado, M. (2018), *Advances in Financial Machine Learning*, Ch. 3 & 10 (triple-barrier labeling, meta-labeling).
- Everything not attributed to one of the above — thresholds, cost figures, worked-example values — is illustrative.
