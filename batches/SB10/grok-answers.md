# SB10 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials (account: Praveen Gupta)
- Date: 2026-09-10
- Chat: https://grok.com/c/75849536-bf09-4609-b51e-2d1ce02c24c5
- Batch: SB10 — Hard microstructure + alt-data (S009, S019, S092, S093, S095, S096, S097, S098, S099, S100)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim via page text extraction.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: LaTeX-rendering duplication was de-duplicated; dropped math glyphs are noted; bracketed notes are the browser task's own capture notes, not Grok's text.

---

## Q-SB10-1 — formulas + worked example (verbatim)

### 1. PIN (Easley–O'Hara / EKOP–EHO)

Model (Easley, Kiefer, O'Hara, Paperman 1996; Easley, Hvidkjaer, O'Hara 2002).

Each day an information event arrives with probability α. Conditional on an event, it is bad news with probability δ (good news with 1−δ). Informed traders arrive as a Poisson process with intensity μ; uninformed buys and sells arrive with intensities εb and εs. Days are independent.

Daily likelihood of observing buyer-initiated trades B and seller-initiated trades S. Over T independent days the sample likelihood is the product. PIN is the unconditional share of informed flow:

PIN = αμ / (αμ + εb + εs). (If εb = εs = ε, this collapses to αμ/(αμ+2ε).)

Practical MLE setup (illustrative, not unique).
• Window: rolling or calendar blocks of 60 trading days is the classic EKOP recommendation for stable convergence; 30–90 days is common; 10 days is only for [illustration].
• Trade classification: Lee–Ready (quote midpoint + tick) or contemporaneous BBO; counts of trades, not dollar volume, in the original model.
• Factorization: maximize the EHO (2010) or Lin–Ke (2011) log-likelihood, not the raw product of factorials (overflow).
• Constraints: [parameters in (0,1) for α, δ; intensities positive; boundary-avoidance].
• Starts: grid / YZ (Yan–Zhang 2012) / EA (Ersan–Alici 2016) initial sets; multi-start required because the surface [is multimodal].
• Buys/sells construction: daily aggregates from tick data; overnight and opening prints often dropped.

### 2. Crypto funding-rate / basis cash-and-carry

Perp funding. On most venues (Binance-style 8h, or hourly venues scaled to an 8h basis):

F = clamp(P − I, −cap, +cap),

where P is the period-average premium index, I is a small interest component (often 0.01% per 8h), and cap is a clamp (often 0.05% per 8h). Positive F: longs pay shorts. Payment on notional N is F × N.

Simple annualization (illustrative convention): APR = mean(F) × (8760 / hours per settlement) — with 8h settlements, 1,095 periods/year. Example: [mean 0.01% per 8h →] APR = 0.00010 × 1095 = 0.1095 = 10.95%.

Cash-and-carry (long spot + short perp, equal notional). Over a hold of h hours with n settlements:

P&L = Σ F_j × N − fees (entry + exit) + basis captured − basis at unwind.

For a 24h hold with intended basis capture (or basis assumed unchanged), net is funding minus two-way fees. Typical fee [schedules assumed as examples].

### 3. Google Trends ASVI

Google SVI is already scaled 0–100 within the downloaded window. Abnormal search volume intensity for [ticker] (Da–Engelberg–Gao, "In Search of Attention" avoids [using raw SVI]):

ASVI_t = log(SVI_t) − log(median(SVI over prior 8 weeks)).

Illustrative windows:
• Weekly ticker SVI: 8 weeks (DEG original).
• Daily: 30–50 calendar days, or same-weekday median over 8–10 prior weeks (Drake et al. style) to kill weekday seasonality.

Alternative (level, not log): [ASVI = (SVI − median_52wk)/median_52wk — rendered as level alternative].

Query: ticker (preferred for stocks) or company name; geography = relevant market; category filter [optional].

### 4. PEAD / SUE sorts (intraday or announcement-window leg)

Time-series SUE (Foster–Olsen–Shevlin / Bernard–Thomas):

SUE = (EPS_q − EPS_{q−4}) / σ(Δ seasonal EPS),

where σ (and optional drift) is the std of seasonal differences over the prior 8–20 quarters. Bernard–Thomas often used a seasonal random walk.

Analyst SUE (Livnat–Mendenhall): (actual − consensus) / price [or scaled by forecast dispersion].

Sort / PEAD portfolio. Each quarter (or each announcement day in an event study), rank names into deciles (classic) or quintiles. Announcement / "intraday" leg is typically the CAR from close to close, or from pre-announcement midquote to the close of announcement day (or first 30–60 minutes if [intraday]). [Drift window] through [60] trading days; ~25–30% of the classic 60-day drift sits in the 3-day windows around the next three earnings dates. [Benchmark: market, size-matched, or FF]. Illustrative: NYSE/AMEX historically, now common-stock universe with [filters].

### Worked numerical example (synthetic; parameters marked as examples)

#### A. 10-day buy/sell series → PIN likelihood and an approximate PIN

Synthetic daily (B, S) (example only; far shorter than the usual 60-day window):
Day: 1: 40/38; 2: 42/41; 3: 90/35; 4: 38/40; 5: 36/88; 6: 41/39; 7: 85/33; 8: 40/42; 9: 37/80; 10: 43/40.

Intuition for the mixture. Most days look balanced around ~40/40 (uninformed Poisson baseline). Days 3 and 7 are buy-heavy; days 5 and 9 are sell-heavy. That is 4 "event-like" days out of 10 (α̂ = 0.4). Among event days, half look like good news, half bad (δ̂ = 0.5). Excess flow on event days is about 50 extra buys (or sells) (μ̂ ≈ 50/day). Plug into the PIN formula (equal-intensity version is close enough here):

PIN ≈ (0.4 × 50) / (0.4×50 + 2×40) = 20/100 = 0.20.

Likelihood sketch (one day, un-normalized). For a balanced day (B,S) = (40, 38) the no-event Poisson term dominates. For day 3 (90, 35) the good-news term dominates. Full MLE would maximize Σ log L_i (EHO factorization) from several starts; with this tiny sample you should not trust more than one significant figure.

#### B. Synthetic funding series → annualize and 24h cash-and-carry on $10k

Example series (8-hour settlements, rates in percent per period): 0.012, 0.010, 0.008 over one 24h (three prints). Mean 0.010% per 8h.

Annualization (simple APR, example convention): 0.00010 × 1095 = 0.1095 = 10.95% APR.
Compounded: (1.00010)^1095 − 1 ≈ 11.57% APY.

$10,000 (long spot, short perp; illustrative fees 4 bps taker each of 4 tickets = 16 bps round-trip if you open and close in 24h; many desks would use makers and not round-trip in a day).

Funding received in 24h (short earns positive funding): 10,000 × (0.00012 + 0.00010 + 0.00008) = $3.00.
Fees if you open and flatten in 24h at 4 bps/leg: 10,000 × 0.0004 × 4 = $16.
Assume entry basis 0 and unwind basis 0 (pure funding example): net = $3 − $16 = −$13.
If instead you keep the book open (fees already sunk on a longer hold), 24h contribution is $3 (3 bp), i.e. the 10.95% APR run-rate before other costs (borrow on spot, margin, basis drift). A 30-day hold at a flat 0.01%/8h with the same 16 bp round-trip would be $90 funding minus $16 = $74; simple net APR on [the position ~$74/$10,000 × 365/30].

### Sources (canonical)

PIN: Easley–O'Hara 1992; EKOP 1996 JF; EHO 2002; EHO 2010 JFQA factorization; Lin–Ke 2011. Funding: venue spec sheets (Binance/Hyperliquid-style premium + clamp) and [aggregator docs]. ASVI: Da–Engelberg–Gao "In Search of Attention". SUE/PEAD: Ball–Brown 1968; Foster–Olsen–Shevlin 1984; Bernard–Thomas 1989, 1990; Livnat–Mendenhall. All paths above are illustrative examples, not estimated from live data.

---

## Q-SB10-2 — local build + buy vs build (verbatim)

Assumptions for this costing: one 128 GB M5 Max, local-first, research/internal use (not a redistribution product); indicative 2025–2026 list / street ranges, not quotes. Recheck before you sign.

### Hardware envelope (the box you already have)

M5 Max / 128 GB is not the bottleneck for any of these four components if you stay at research frequency. RAM: 128 GB is ample. PIN MLE is a few MB per symbol. Crypto WS + 20 symbols is tens–hundreds of MB. News [ingest is small]. CPU: PIN is scalar MLE, embarrassingly parallel across symbols. 500 names × multi-start fits in an evening. GPU / Neural Engine: unused for classic PIN. Useful only if you run local LLMs for novelty/sentiment. Disk: plan 0.5–2 TB working set year-1 if you keep tick/BBO for PIN classification + 1–2 years of perp WS + news JSON. Network: always-on WS for 20 perps is trivial. News WS is trivial. Google Trends polling is rate-limited, not [bandwidth-limited]. You do not need cloud compute for (a)–(d) at this scale. Cloud shows up as data egress / vendor SaaS, not as FLOPs.

### (a) PIN estimation — 500 symbols, MLE reality check

Data (the real cost), not the optimizer. PIN needs buyer- vs seller-initiated trade counts per day. That means tick + quote (Lee–Ready or equivalent), not EOD volume.

- Polygon stocks advanced / SIP-equivalent: trades + NBBO, good enough for Lee–Ready on US names — ~$200–$300/mo street for stocks+quotes; higher for full SIP + history.
- Databento EQUS / XNAS+XNYS: cheaper tick, excellent for research — ~$50–$250/mo depending on schemas + history.
- WRDS / TAQ (academic): gold-standard TAQ — $0 incremental if you already have a WRDS seat; otherwise institutional.
- FirstRate / Tick Data / Kibot: historical only — one-off $hundreds–low $k.

Compute on M5 Max (illustrative, EKOP/EHO, 60-day windows, 10–30 random/YZ starts, LK or EHO factorization):
• Per name, 60 days, 20 starts: ~0.2–3 s wall on one P-core for liquid names; mega-caps with huge trade counts need factorization or they overflow, not more RAM.
• 500 names, quarterly panel, 4 windows/year, 20 starts: ~15 min – 2 h end-to-end if you multiprocessing across performance cores. Memory: <2 GB for the estimator itself.
• Storage: daily (B,S) table is tiny (<50 MB/year for 500 names). The tick cache you classify from is 50–300 GB/year if you keep raw trades+NBBO; you can discard ticks after aggregation.

Engineering hours (example): 40–80 h if you reuse PINstimation/InfoTrad logic + a Lee–Ready classifier; 120–200 h if you write factorization yourself.

Buy vs build: Build the estimator. Buy (or WRDS) the tape. There is no serious PIN-as-a-service for 500 names that is cheaper than Databento + a weekend of code.

### (b) Crypto pipeline — funding, OI, liquidations — 20 perps

State this explicitly: Public exchange APIs are a lower bound, not a complete book. Funding and mark/index are usually public. Liquidation feeds are incomplete and venue-censored: Binance/Bybit/OKX publish some force-order / liquidation prints; they do not publish the full liquidation queue, hidden stops, or internal insurance-fund activity. Aggregator "liquidation" heatmaps are models + partial prints, not a census. OI is usually official per instrument but not always comparable across coin-margined vs stable-margined and not always tick-by-tick historically. Public crypto data is best-effort, not audit-grade.

- DIY exchange APIs (Binance, Bybit, OKX, Hyperliquid, …): Funding + OI: yes, free. Liqs: partial force-order streams. History: short and inconsistent. — $0 data + your IP/ban risk + engineering.
- CoinGlass API: funding, OI, liq history/heatmaps, multi-venue — hobbyist from ~$29/mo; serious history/API Standard–Pro ~$99–$299/mo; Enterprise custom. History depth is plan-capped (days–months at fine bars).
- Laevitas: perps + options Greeks; funding/OI/liqs — UI cheap; API often ~$500/mo Enterprise, or pay-per-call (~$0.001) on v2.
- Amberdata / Coin Metrics / Tardis: institutional normalized + deep history + S3 — ~$10k–$50k+/yr typical; Tardis mid-market for ticks.
- Coinalyze / Hyblock / Velo: trader-oriented liq/OI — $50–$300/mo.

Compute on M5 Max: 20 symbols × 3 venues × funding/OI/liq WS is <1 CPU core, <1 GB RAM. Storage: 5–30 GB/year if you keep 1s snapshots + liq prints; much more if you also store L2.

Engineering hours: Exchange-direct MVP (funding + OI + partial liqs, 3 venues): 25–50 h. Robust (reconnect, venue quirks, funding-interval normalization, basis vs spot, fee schedules): 80–150 h. Matching CoinGlass-style aggregated liq heatmaps yourself: don't; that's a product.

Buy vs build: Funding + OI for 20 names: build on public APIs (free, good enough). Liquidations + multi-venue history + heatmaps: buy CoinGlass/Laevitas unless you enjoy incomplete data. Do not assume public crypto data is complete; it is a censored lower bound on true forced flow.

### (c) News / sentiment with novelty — licensing wall

State this explicitly: You generally cannot build a redistributable machine-readable newswire. Copyright + vendor contracts forbid scraping Reuters/Bloomberg/Dow Jones/PR wires and reselling text; internal commercial use of full text is often licensed. Novelty scores that are research-grade (RavenPack ESS) are the product; rebuilding them means licensing the corpus first.

- Benzinga Newsdesk / API: structured headlines, tickers, categories, WS; catalyst-oriented — street ~$399/mo entry for real Newsdesk/API; climbs to four figures with more feeds. AWS "basic news" free tier exists but is not the low-latency desk.
- RavenPack: entity, event, sentiment, novelty, relevance, 20y+ history — commercial ~$50k–$100k+/yr commonly quoted; academic via WRDS if your institution pays the WRDS bundle (you do not get a cheap retail SKU). Novelty is a first-class [feature].
- RavenPack / Bigdata.com token retrieval: pay-per-retrieved-token, not a full firehose — usage-based; good for agents, not a 500-name daily panel.
- Polygon / Tiingo / Marketaux news: bundled headlines — $30–$200/mo; tagging and novelty are weak.
- NewsAPI.org / GDELT / RSS: free–cheap — not a substitute for novelty-scored market news.
- Bloomberg / Refinitiv News Analytics: institutional — high five to six figures.

Compute: ingest is nothing. If you score novelty yourself (simhash / MinHash over 7–30 day headline window + embedding cosine vs last 90 days): <1 GB, minutes/day for 500 names. A local 7–32B LLM for stance is optional and will dominate CPU/ANE; budget 5–15 W continuous if you insist on on-box inference.

Engineering hours: Licensed feed → Postgres + ticker map + simple novelty: 30–60 h. Homegrown "RavenPack": not an hours problem; a rights problem.

Buy vs build: Buy the wire + novelty if you need research-grade event study. RavenPack (WRDS if you can) or Benzinga for catalyst speed. Build only the scorer on top of a licensed feed. Building the corpus by scraping is legally the wrong answer for anything you might publish, sell, or even keep in a company repo.

### (d) ASVI + social

- Google Trends: no generally available official API as of 2026 (alpha exists, application-gated). pytrends is fragile / often dead. — $0 unofficial + ban risk.
- SerpApi Trends: reliable JSON — $25/mo (1k searches) → $75–$150/mo for a 500-ticker weekly panel (500 tickers × 4–5 pulls/mo ≈ 2–2.5k searches if you batch poorly; batch [well and it's less]).
- DataForSEO / Bright Data: cheaper per call — ~$0.002–$0.0027/task or $1.50/1k SERP; Bright Data free 5k/mo.
- Social — X: official X API — free/Basic almost useless for panel sentiment. Pro/Enterprise: hundreds to $5k+/mo. Scraping violates ToS.
- Social — Reddit / StockTwits / YouTube: official or firehose partners — Reddit API paid after 2023 squeeze; StockTwits commercial license. $0–$500/mo hobby; more for firehose.
- Brandwatch / Meltwater / Sprinklr: multi-social enterprise — ~$15k–$40k+/yr.

Compute: Trends + daily ASVI for 500 tickers is megabytes. Social firehose is the storage hog if you keep raw posts (tens of GB/month at "meme-stock + 20 perps" scope).

Engineering hours: Trends ASVI panel: 15–30 h on SerpApi; 60+ h fighting unofficial scrapers. Social MVP (Reddit + StockTwits + a few X lists): 40–80 h. Full social graph: buy.

Buy vs build: ASVI: buy a Trends reseller (SerpApi/DataForSEO), build the Da–Engelberg–Gao transform. Social: buy if it must be complete; build only narrow, ToS-compliant slices. X at panel scale is a license, not a scrape.

### Stack-level verdict (what to actually spend)

- PIN MLE, 500 names: $600–$3,600 tape (Databento/Polygon) or $0 on WRDS; 40–120 eng hours year-1; on this Mac: Easy; verdict: Build estimator, buy tape.
- 20-perp funding/OI: $0 exchange APIs; 25–80 h; Easy; verdict: Build.
- 20-perp liquidations + history: $350–$3,600 (CoinGlass/Laevitas) or $0 incomplete; 20 if buy, 150 if fake-build; Easy; verdict: Buy; public liqs are censored/partial.
- News + novelty: $5k–$20k Benzinga-class or $0–$100k RavenPack/WRDS; 30–60 h on a feed; Easy; verdict: Buy feed; do not scrape a newswire.
- ASVI: $300–$1,800 SerpApi-class; 15–30 h; Easy; verdict: Buy Trends API, build ASVI.
- Social sentiment: $0 narrow / $6k–$40k full; 40–80 h narrow; Easy until firehose; verdict: Build narrow, buy broad.

Year-1 cash box if you are disciplined (research, not a product): ~$2k [tape] ~$1–2k [crypto aggregators] ~$0.5–1k [Trends] + Benzinga-class news $8–12k; 150–300 engineering hours. Year-1 if you want RavenPack-grade novelty + complete social: add $50k–$100k+ and stop pretending that is a build.

Where build is impossible: full-text news redistribution and RavenPack-equivalent novelty without a corpus license.
Where "free public data" is a lie of omission: crypto liquidation completeness and, to a lesser degree, cross-venue OI comparability. Use public APIs as a lower bound, and say so in any research write-up.

---

## Q-SB10-3 — success ratios, after-cost efficacy, failure modes (verbatim)

Grok's stated process line: "I'll pull the core papers and recent replications so the return magnitudes, horizons, and failure regimes are cited rather than recalled."

### 1. PIN — spreads, returns, and why you cannot treat it as a live signal

What was claimed. In the EKOP/EHO structural model, PIN is the share of informed arrivals. Easley, Hvidkjaer and O'Hara (2002) reported that a 10-point PIN gap mapped to about 250 bp/year in average returns, and they interpreted that as priced information risk. PIN also lines up with wider spreads / higher adverse-selection in the original 1996 specialist-stock tests (high-PIN names look "toxic").

What survived. The spread / illiquidity association is the durable piece. Duarte and Young (2009) split PIN into an asymmetric-information component and a symmetric-order-flow / illiquidity component: only the illiquidity piece is priced; the information piece is not. Mohanram and Rajgopal (2009) replicate EHO (2002) in-sample and then show the return result is not robust to specification or period; PIN factor loadings do not predict returns and PIN does not line up with implied cost of capital. Lai, Ng and Zhang (international sample) find no PIN premium outside the original US window.

Identification failure. Duarte, Hu and Young (JFE 2020 / related work) show PIN and even AdjPIN cannot match the variance of buys and sells (PIN-implied variances ~orders of magnitude too small). The estimator then mis-labels turnover as "news days." Likelihood-ratio tests reject PIN in favor of AdjPIN for most firm-years, and even AdjPIN still understates volume variance. A mechanical turnover heuristic is about as good at "finding private information."

Real-time difficulty (honest).
• Needs days of classified B, S, classically ~60 trading days — it is a quarterly object, not a 9:35 print.
• MLE fails to converge on the most active names as trade counts explode; published PIN panels quietly drop a large market-cap share in later years.
• Factorization (EHO 2010, Lin–Ke 2011), start grids, and floating-point traps are operational, not cosmetic.
• Lee–Ready errors, odd-lot explosion post-decimalization, and HFT spoof the arrival process the 1990s Poisson mixture assumed.

After-cost / failure regimes. PIN is a research control and a liquidity covariate, not a tradable factor. Failure when: mega-cap / high-frequency order flow; you need a same-day number; you treat α̂μ̂ as "informed flow today." Costs of the tape dwarf the optimizer. Do not pay for PIN-as-alpha after Duarte–Young.

### 2. Stealth trading (Barclay–Warner) — size, then the size migrated

Documented finding. Barclay and Warner (1993, JFE): on NYSE tender-offer targets, medium-size prints (500–9,999 shares) account for ~93% of cumulative price change despite not dominating volume or trade count. Interpretation: informed traders split large intent into medium clips to hide from the specialist.

Chakravarty (2001) with NYSE audit trail: the medium-size price impact is almost entirely institutional. Later work (Hansch–Choe 2007 and the intraday stealth-trading literature) documents a regime break around decimalization (~2000–2001): informed flow migrates from medium to small as the tick and the cost of slicing fall. "Medium" in share space is no longer a stable camouflage once a 100-share clip is cheap.

Modern relevance. The economic hypothesis (hide in the crowd, don't dump a block) is intact. The implementation must move from share buckets to participation rate, child-order size vs ADV, and venue (dark / mid / periodic auction). Conditioning later return signals on "medium-size contrarian flow" still shows some pricing in 1993–2012 samples, but that is a different object than 1993 share bins.

After-cost / failure. Failure when you copy 500–9,999 share bins onto 2020s US tape (odd lots + slicing + auctions). Cost: you need tick data and a classifier; the signal is a description of who moved price, not a standalone long–short. After-cost edge is in execution design (don't print the block), not in a size-bucket factor.

### 3. Crypto funding-rate reversal and liquidation cascades

Funding as a premium you can harvest (carry), not a reversal clock. Delta-neutral cash-and-carry on BTC/ETH perps has been documented as a harvestable implied yield: one systematic fully collateralized implementation reports ~10.6% annualized with ~1.5% vol over its sample, low correlation to traditional factors — that is collecting funding, not fading it. That return is gross of borrow, margin, basis blow-outs, and exchange risk.

Reversal / cascade folklore vs evidence. Persistent extreme positive funding while spot stalls is widely used as a crowding / long-leverage warning; practitioner tallies (not a top-journal result) quote high conditional flush rates after multi-period funding > ~0.05%/8h. Historical episodes (e.g. Dec 2024-style flushes; the Oct 2025 cascade with ~$19bn OI wiped, majority longs) fit the mechanism: high funding + high OI + thin book → forced sells.

Cascades are real; "cascade alpha" mostly is not. Event studies that buy alts after BTC liquidation spikes often keep BTC beta. One careful decomposition finds post-cascade alt outperformance collapses once you hedge BTC (residual ~+1% with p ≈ 0.18). On-chain reconstruction of a large 2025 cascade finds subcritical branching inside the venue (λ̂ ≈ 0.1–0.2) and a large share of forced flow absorbed off-book by the backstop — the public print is not the full engine.

Censored-data caveat (state explicitly). CEX liquidation APIs are throttled / incomplete (one venue documented at one event per second). Counting fills instead of economic episodes inflates event counts ~2.7–3×, with the bias in the tail (top percentile can be tens of fills per episode). Heatmaps are models. Public liq series are a lower bound, biased toward what the venue chooses to show.

After-cost / failure. Carry works until funding flips, basis explodes, an exchange fails, or ADL hits the short. Fading high funding without a hedge is just short momentum. Cascade-chasing fails when you cannot see the book that actually absorbs, when you count fills as events, and when you pocket beta and call it alpha. Fees + funding interval mismatch + withdrawal haircuts eat short-horizon "reversal" trades.

### 4. ASVI (Da–Engelberg–Gao 2011)

Documented predictability. DEG (JF 2011): Google Search Volume Index on tickers is a direct attention measure. Abnormal SVI (ASVI) — log SVI minus log median of the prior 8 weeks — predicts higher returns over the next ~2 weeks, concentrated in smaller, less-covered names, then reverses over the year. That is a pressure-then-correction pattern, not a cash-flow discovery pattern. Retail attention, not smarter institutions, is the intended channel.

Horizon and decay. The economically interesting window is days to a couple of weeks, not a quarter. Post-publication: attention is now an industrial input (retail apps, payment for order flow, meme cycles). The direction (attention → contemporaneous and near-term price pressure, then giveback) still shows up in later attention papers; the easy long-only ASVI sort is weaker after 2011 as the anomaly was published, retail microstructure changed, and Trends itself is a renormalized 0–100 index with no official production API. Use ASVI as a conditioning variable (amplifies PEAD, IPO underpricing, news days), not as a standalone 500-name factory.

After-cost / failure. Failure on mega-caps, on names whose ticker is an English word, and when you ignore Google's window renormalization. Costs: data reseller + false tickers. After-cost the 2-week premium is small-name and capacity-constrained.

### 5. Social sentiment — signal, noise, and manipulation

What is documented.
• Contemporaneous polarity on StockTwits/X co-moves with returns; unconditional next-day predictability is weak or zero. Predictive content appears mainly on attention spikes (message-volume events), not on the average daily polarity.
• Separate sentiment vs attention: high sentiment often follows a run-up and then reverses ~20 days; high attention can continue a prior trend. Mixing the two is how retail dashboards lie to you.
• Pre-earnings StockTwits attention is optimistically biased, does not forecast fundamentals, produces ~50–60 bp of pre-announcement price pressure and a ~45 bp announcement reversal as intermediaries fade inventory.
• OTC / retail venues: positive posts → pop then month-scale reversal; negative posts often follow a decline (commentary, not forecast).

Manipulation risk. Pump groups, coordinated options + screenshot threads, and paid promo are first-order on small caps (GameStop-class and the 2024–26 meme recurrences). Platform labels ("92% bullish") are not risk-adjusted forecasts. Bots and copy-pasta inflate both volume and polarity.

After-cost / failure. Treat social as attention + crowding, fade extremes into earnings, do not run an unconditional polarity sort. Failure regimes: large-cap, high-analyst names; bot-inflated volume; any strategy that needs the raw firehose without a license. Capacity dies the moment the name is on CNBC.

### 6. PEAD — announcement/intraday leg vs the drift, and latency

Classic magnitudes. Bernard and Thomas (1989): high-minus-low SUE decile ~4.2% over the next 60 trading days (roughly 2% each side), positive in 41 of 48 quarters. About 25–30% of that drift sits in the 3-day windows around the next three quarterly prints, which is the "investors use a seasonal random walk" fingerprint (Bernard–Thomas 1990). Announcement-window (−1,+1) CARs in the extreme SUE deciles are on the order of a few percent, the part everyone sees.

What compressed. The jump at the print is now a milliseconds-to-minutes object in liquid names (HFT + holding-period returns into the open). Livnat–Mendenhall-style analyst SUE still beats seasonal-RW SUE. Recent long samples show the easy close-to-close PEAD shrinks, especially in large caps; some 2000–2025 event studies find only a ~1.3 pp Q5–Q1 gap at T+63 vs SPY after a next-day-close entry — the anomaly is not dead as a relative sort but it is not 1989. Text-based surprises (SUE.txt from calls) can still show larger subsequent drift than numeric SUE in 2010s samples.

Latency required.
• Print jump / "intraday leg": you need the number (or a high-quality whisper vs consensus), a mapped ticker, and the ability to trade in the first seconds to first minutes after the official release — or you are not trading that leg. After the first half-hour in mega-caps you are mostly noise plus spread.
• Drift leg: entry at T+1 close is what academic PEAD actually is. That is a capacity-friendly, low-frequency trade; costs are borrow on the short leg, not colocation.
• Mixing the two and applying HFT cost assumptions to a 60-day hold (or vice versa) is how backtests get dishonest.

After-cost / failure. Announcement-leg: eaten by spread, auction imbalance, and being late. Drift-leg: eaten by short borrow on losers, delisting, and large-cap disappearance. Failure when surprise is already in the pre-announcement run-up [or reversed by the next print].

### Cross-cutting after-cost honesty

| Signal | Gross story | After costs / publication | Dies when |
| PIN | 250 bp/yr, wider spreads | Premium was illiquidity; estimator misspecified | You need it live; mega-cap tape |
| Stealth size | Medium prints move price | Size bucket migrated to small/child orders | 1993 bins on modern tape |
| Funding carry | ~high-single / low-double digit vol-adjusted | Fees, borrow, exchange, basis gap | Funding flips, venue dies, ADL |
| Funding fade / liq cascade | Crowding then flush | Public liqs censored; leftover is often beta | You trust the heatmap |
| ASVI | +2-week pressure, later reversal | Smaller, ticker-quality, post-2011 decay | Large cap, bad ticker, renormalized Trends |
| Social polarity | Contemporaneous; event-conditional | Reversal after optimism; manipulation | Unconditional daily sort |
| PEAD jump | Few % in (−1,+1) extremes | Now a speed race | You enter after the auction |
| PEAD drift | ~4% / 60d historically | Compressed, still a relative sort | Large cap + expensive shorts |

None of these six is a "plug into the M5 Max and harvest" object. The ones that still pay after cost: slow PEAD as a sort, funding carry with tight risk limits, attention as a conditioner. The ones that look precise in code and lie in production are real-time PIN, share-bucket stealth, uncensored-looking liq tapes, unconditional social polarity.

---

## QC notes (orchestrator)

1. Q1 PIN worked example: Grok's own derivation is internally consistent — 4 event-like days out of 10 → α̂=0.4, δ̂=0.5, μ̂≈50/day, ε̂≈40 → PIN ≈ 20/100 = 0.20. Correct.
2. Q1 funding example: mean 0.010%/8h → 0.00010 × 1095 = 10.95% simple APR; (1.00010)^1095 − 1 ≈ 11.57% APY. Correct.
3. Q1 $10k cash-and-carry: funding 10,000 × (0.00012+0.00010+0.00008) = $3.00; fees 10,000 × 0.0004 × 4 = $16 → net −$13. Correct. 30-day at flat 0.01%/8h: 90 periods × $1 = $90 − $16 = $74. Correct.
4. Q1: the level-alternative ASVI formula and the level-alternative rendering were bracketed (capture note: formula appeared as rendered image in chat).
5. Q1: the PEAD bullet has several bracketed gaps where math rendered as images; the 24h example's final sentence was truncated mid-render.
6. Q2 SerpApi row: the "batch [well and it's less]" parenthetical was truncated mid-render.
7. Q2: the Laevitas pay-per-call row had a Coinstats link chip embedded mid-sentence — preserved as Grok displayed it.
8. Q3 intro: Grok's visible process line ("I'll pull the core papers…") was not part of the answer; included here only as context.
9. Key sourced claims are research leads, not verified facts: EHO 2002 (250 bp/yr for 10-point PIN gap); Duarte–Young 2009 (only illiquidity component priced); Mohanram–Rajgopal 2009 (EHO not robust); Duarte–Hu–Young 2020 (PIN mis-labels turnover); Barclay–Warner 1993 (~93% of price change in 500–9,999 share prints); Da–Engelberg–Gao 2011 (ASVI → +2 weeks then reversal); Bernard–Thomas 1989 (~4.2% PEAD decile spread); Livnat–Mendenhall (analyst SUE beats seasonal-RW). Vendor prices: indicative — verify before budgeting.

---

## Source list (only papers actually used)

- Easley, D. and O'Hara, M. (1992), "Time and the Process of Security Price Adjustment."
- Easley, D., Kiefer, N., O'Hara, M. and Paperman, J. (1996), "Liquidity, Information, and Less-Frequently Traded Stocks," Journal of Finance.
- Easley, D., Hvidkjaer, S. and O'Hara, M. (2002), "Is Information Risk a Determinant of Asset Returns?"
- Easley, D., Hvidkjaer, S. and O'Hara, M. (2010), "Factoring Information into Returns," Journal of Financial and Quantitative Analysis.
- Lin, H.-W. and Ke, W.-C. (2011), PIN factorization.
- Yan, Y. and Zhang, S. (2012), YZ starting sets for PIN.
- Ersan, O. and Alici, A. (2016), EA initial sets for PIN.
- Duarte, J. and Young, L. (2009), "Why is PIN Priced?"
- Mohanram, P. and Rajgopal, S. (2009), "Is PIN Priced? Risk, Mispricing and Value Relevant Information Content."
- Duarte, J., Hu, E. and Young, L. (2020), PIN identification failure.
- Barclay, M.J. and Warner, J.B. (1993), "Stealth Trading and Volatility," Journal of Financial Economics.
- Chakravarty, S. (2001), "Stealth Trading: Which Traders' Trades Move Stock Prices?"
- Da, Z., Engelberg, J. and Gao, P. (2011), "In Search of Attention," Journal of Finance.
- Ball, R. and Brown, P. (1968), "An Empirical Evaluation of Accounting Income Numbers," Journal of Accounting Research.
- Foster, G., Olsen, C. and Shevlin, T. (1984), "Earnings Releases, Anomalies, and the Behavior of Security Returns."
- Bernard, V.L. and Thomas, J.K. (1989), "Post-Earnings-Announcement Drift."
- Bernard, V.L. and Thomas, J.K. (1990), "Evidence That Stock Prices Do Not Fully Reflect the Implications of Current Earnings for Future Earnings."
- Livnat, J. and Mendenhall, R.R. (in-memory ref), analyst SUE.
- Everything not attributed to one of the above — parameter ranges, cost figures, worked-example values — is illustrative.
