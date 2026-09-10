# TB8 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials (account: Praveen Gupta)
- Date: 2026-09-10
- Chat: https://grok.com/c/b7b5b48e-f456-459f-a919-e0f68eaf0fe3
- Batch: TB8 — Alternative-data & attention (T071–T080)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim. LaTeX formulas recovered from the page's math annotations; math fragments the page extraction dropped are marked `[...]` (extraction artifacts, not confirmed Grok errors).
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- All thresholds are illustrative examples.
- Nothing here is a live-trading spec.

---

## Q-TB8-1 — mechanics + worked example (verbatim)

"All thresholds below are examples for illustration, not recommended live parameters. Sources are cited where a construction is standard in the literature."

"Shared bookkeeping

| Item | Convention used in examples |
| Notional | Gross notional of the position |
| Size | Risk-budgeted fraction of NAV |
| Costs | Explicit in each P&L stack |
| Sign | Long = +1, short = −1 |"

### (A) News-novelty reversal

"Economic idea. After a large move on stale / redundant news, the move is more likely liquidity or attention-driven than a permanent repricing, so fade it. With fresh, novel news, do not fade (or fade with a much higher bar). This is the opposite of 'trade the headline.' Fresh news often should reprice; stale news often should not."

**Novelty scoring procedure (complete)**
"1. Corpus. For ticker i, collect all articles tagged to i in a rolling window of 30 calendar days (example 30)
2. Representation. Embed each article d as vector v_d (TF-IDF over unigrams+bigrams, or a sentence embedding). Drop boilerplate (earnings-calendar wires w[...])
3. Similarity. For a newly arriving article d*, s(d*) = max_{d∈C_{i,L}\{d*}} cos(v_{d*}, v_d)
4. Novelty score (unit interval, higher = more new): N(d*) = 1 − s(d*). If several articles land in the same burst (same 15-min bin), take N = min_k N(d_k) — least novel piece in the burst is the conservative score (a reprint of an already-known fact should not look novel)
5. Event filter. Keep only events with:
   • |r_{i,t}| over a short window (example: 15-min or 1-hour return from first print) above a volatility-scaled bar: |r| > k·σ_{i,20d}^{intraday} with example k = 2.5
   • minimum liquidity (example: ADV > $20mm, spread < 20 bp)
6. Reversal eligibility. Fade only if novelty is low: N(d*) < N_fade (example N_fade = 0.35). High novelty (N > 0.70, example) is a hard no-fade (or a momentum overlay, which is a different strategy). This 'absolute news magnitude without trusting signed sentiment, used as a filter on a weak-close / [...]'"

"Entry / exit (example thresholds)

| Step | Rule (examples) |
| Clock | RTH US equities only: 09:30–16:00 ET. No overnight hold unless explicitly allowed. |
| Trigger | First 15-min bar after the article timestamp with $$ [genuine omission: the trigger condition's math block is empty in the page source] |
| Side | Fade: short if r_{15m} > 0, long if r_{15m} < 0. |
| Entry | Next 1-min bar open after the trigger bar close (no same-bar fill). |
| Stop | 1.0× the trigger-bar range, beyond the extreme of the trigger bar. |
| Target | 50% retracement of the trigger move, or time stop at 15:55 ET, whichever first. |
| Hard kill | Any new article on the same name with N > 0.70 while in the trade → flatten. |"

"Sizing
Example: risk 0.25% of NAV to the stop. shares = 0.0025·NAV / |P_entry − P_stop|. Cap notional at [...] of ADV and [...]"

"Session / venue
US listed equities, primary listing, RTH only. News after 16:00 is scored overnight and may set up the next-day gap trade, not this intraday fade."

"Cost model
Round-trip: commission + half-spread + impact. Example: 1 bp comm + 8 bp half-spread + 5 bp impact [...] = 28 bp of notional."

**Worked synthetic example — (A)**
"NAV $10,000,000. Name XYZ, last $50.00, ADV large.
• 10:12 ET: wire hits. Cosine to nearest 30-day article 0.82 → N = 0.18 < 0.35. Eligible.
• 10:12–10:27 15-m bar: $50.00 → $51.40 (+2.80%). Trigger long-side overreaction → short.
• Entry 10:28 open: $51.35.
• Stop: trigger high $51.40 + 1.0× bar range $1.40 = $52.80.
• Risk per share $1.45. Shares = 0.0025 × 10^7 / 1.45 = 17,241. Notional ≈ $885,000.
• Target: 50% retrace of $51.40 → $50.00 = $50.70. Path (synthetic):
  1. 10:28 fill short 17,241 @ $51.35.
  2. 11:40 print $50.72 — target touched. Cover @ $50.72. Gross P&L: 17,241 × $0.63 = $10,861.83. Costs 28 bp × $885,000 = $2,478. Net P&L = $8,383.83 (8.4 bp of NAV). If instead a second wire at 11:05 had N = 0.81, the hard-kill would flatten earlier; that path is not taken here."

### (B) Crypto funding-rate reversal + liquidation-cascade fade

"Economic idea. Extreme positive funding + crowded longs → fade when price finally ticks down through clustered liquidation levels. Fade the exhaustion of that cascade, not the first tick. Extreme negative funding is the mirror. Crowded funding as a reversal signal, not a carry."

**Funding-rate z-score and annualization**
"Let f_t be the settled period funding rate actually settled (Binance-style: typically every 8 hours). Do not z-score mixed tenors without converting.
Annualization (8-hour venue): f_t^{ann} = f_t × 3 × 365 so +0.01% / 8h ≈ +10.95% ann., +0.05% / 8h ≈ +54.75% ann.
For hourly venues (Hyperliquid), f_ann = f_hourly × 24 × 365, on a rolling window (example: 168 hours = 7 days of hourly marks, or 21 eight-hour prints):
z_t = (f_t − f̄_{t−W:t−1}) / s_{t−W:t−1}
Use the period rate or the annualized rate consistently; the z-score is invariant to a constant scale. Example entry bar: |z| > 2.0.
Cross-sectional variant used in research: volume-weighted average funding across top-N perps, then z-scored over 168 hours."

**Cascade-fade confirmation (do not fade the first flush)**
"Require
1. |z| > 2.0 in the crowded direction (e.g. f > 0 = longs paying).
2. Price impulse against the crowd of at least example 60 minutes (BTC/ETH; larger for alts).
3. Liquidation / OI: one-sided liquidations of the crowded side, then an OI drop and liquidation rate rolling off (exhaustion), not accelerating.
4. Optional microstructure: CVD / delta divergence vs price at the local extreme. Enter after exhaustion, not into the waterfall. That is the 'fade the exhaustion / hunt' book, not 'ride the cascade'."

"Entry / exit (example thresholds)

| | Rule (examples) |
| Universe | BTC, ETH linear USDT perps, top-2 venues by OI (e.g. Binance + Bybit). |
| Session | 24/7. Funding clocks are UTC 00:00 / 08:00 / 16:00 on 8h venues. |
| Entry | First 5-min close after: z_f > +2, 60-m drop ≥ 2%, 15-m liquidation volume off ≥ 50% from its peak bin, OI ↓. Long the fade (crowded longs just flushed). Mirror for z_f < −2. |
| Stop | Beyond cascade extreme × 1.15, or 1.5% of price, whichever wider. |
| Exit | (i) funding z back inside ±0.5, or (ii) +1.5% price target, or (iii) 12 hours, whichever first. |"

"Sizing
Risk 0.50% NAV to stop, leverage on the perp low (ADL and insurance-fund risk rise in cascades)."

"Cost model — including funding payments
For a short
• Taker fee in + taker (or maker) fee out. Example 4 bp + 4 bp = 8 bp notional RT.
• Funding at each settlement, short receives (longs pay shorts), and pays when f < 0. Holding a short through one +0.05%/8h print on $1mm notional credits $500. Holding a short through −0.03% on $1mm notional debits $300. Funding is marked on the position that is open at the snapshot; opening one minute before settlement captures the full print.
• Impact: example 6 bp in a cascade book."

**Worked synthetic example — (B)**
"NAV $10,000,000. BTCUSDT perp.
• Window: 21 prior 8h prints, mean 0.008%, sd 0.012%.
• Live print 0.040% → z = (0.040 − 0.008)/0.012 = 2.67. Ann. = 0.040% × 3 × 365 = 43.8%.
• 14:10–15:05 UTC: BTC $68,000 → $66,400 (−2.35%). Long liquidations spike then drop 60% in the next 15-m bin; OI −4%.
• Fade long: 15:10 fill $66,450.
• Stop $65,450 (wider of 1.15× extreme and 1.5%). Risk/BTC = $1,000.
• BTC size = 0.005 × 10^7 / 1000 = 50 BTC. Notional = 50 × 66,450 = $3,322,500 = $3.32mm. Leverage on margin low. Path:
  1. 15:10 long 50 BTC @ $66,450.
  2. 16:00 UTC funding snapshot: 0.028%. Longs pay → we pay 0.00028 × 3,322,500 = $930.30.
  3. 18:40 price $67,400. Target +1.5% from $66,450 = $67,447. Fill exit $67,400. Price P&L: 50 × $950 = $47,500. Fees 8 bp × $3,322,500 = $2,658. Impact 6 bp × $3,322,500 = $1,994. Funding paid $930.30. Net P&L = $47,500 − $2,658 − $1,994 − $930.30 = $41,917.70 ≈ $41,918 (42 bp of NAV). (If this had been the short-the-crowd leg before the cascade, funding would have been a credit while held, and the price leg would have been the opposite sign.)"

### (C) Earnings-drift intraday leg on SUE

"Economic idea. PEAD is the multi-day drift after Standardized Unexpected Earnings. The intraday leg harvests the first RTH session (or the first few hours) of that drift after the print is public, rather than the multi-day tail."

**SUE computation and sorting**
"Two accepted numerators; pick one and keep it fixed.
A. Seasonal random-walk SUE (Foster et al.): SUE_{i,q} = (EPS_{i,q} − EPS_{i,q−4}) / σ({EPS_{i,q−j} − EPS_{i,q−4−j}}_{j=1..8})
B. Analyst SUE (common practitioner form): SUE_{i,q} = (EPS^{actual}_{i,q} − EPS^{consensus}_{i,q}) / σ(forecast errors over last 8 quarters)
Cross-section: on each announcement date, rank all names that printed in the last 24 hours with valid SUE into 10 deciles: top decile long, bottom decile short. Bernard–Thomas used deciles; some implementations use top 5%."

"Intraday filter (example): only trade if
• |SUE| > 2.0
• announcement is BMO (before open) or previous AMC already digested in the overnight print,
• first 15-m RTH direction agrees with SUE sign (drift, not fade)."

"Entry / exit (example thresholds)

| | Rule (examples) |
| Session | US RTH 09:30–16:00 ET only. |
| Entry | 09:45 ET (skip the opening auction and first 15-m discovery), marketable limit, side = sign(SUE) if the first-15m direction agrees. |
| Stop | −1.5× first-15m range, or −2.0% from entry. |
| Exit | 15:55 ET flatten, or +2.0% from entry, or VWAP-reversion of the open drive if SUE is only mid-quintile. |
| No overnight | This is the intraday leg only. |"

"Sizing
Risk 0.30% NAV to stop per name; max 8 names; max [...]% NAV gross in the book; ADV cap [...]"

"Cost model
Open: wider spreads. Example 15 bp half-spread + 5 bp comm + 8 bp impact each way → 56 bp RT on announcement-day names (costs are why PEAD papers that assume close-to-close overstate live P&L).
No funding. Hard-to-borrow on the short leg: example borrow [...]bp/252 bp per day; for a same-day short this is ~0 if borrowed and returned same session, else accrue one day."

**Worked synthetic example — (C)**
"NAV $10,000,000. One long name (the short leg is symmetric).
• EPS $1.42, consensus $1.18, σ_err $0.08.
• SUE = (1.42 − 1.18)/0.08 = 3.00 → top decile. BMO print.
• 09:30 open $40.00, 09:45 print $40.80 (+2.0%, same sign as SUE).
• Stop $39.60 (2% from entry). Risk/sh $1.20.
• Shares = 0.003 × 10^7 / 1.20 = 25,000. Notional $1,020,000. Path:
  1. 09:45 buy 25,000 @ $40.80.
  2. 14:10 high $41.55 (+1.84% from entry; target +2% not hit).
  3. 15:55 flatten $41.42. Gross: 25,000 × $0.62 = $15,500. RT costs 56 bp × $1,020,000 = $5,712. Borrow: $0 (intraday long). Net P&L = $15,500 − $5,712 = $9,788 (9.8 bp of NAV).
  A same-size short on a SUE = −3.2 name that drifted −1.1% on the day would add another ~$[...] net after the same cost stack (plus a few bp of borrow if the locate lasted into the close)."

"Coverage contrast

| | (A), (C) equities | (B) crypto perps |
| Hours | RTH 09:30–16:00 ET | 24/7, funding UTC |
| Event clock | Article timestamp / earnings timestamp | Funding snapshot + liq tape |
| Carry | Borrow on shorts only | Funding every 1h or 8h, first-order |
| Gap risk | Overnight if you break the RTH rule | Continuous; weekend is live |
| Venue | Primary listing + SIP | Named perp + backup venue for OI/funding |"

"Sources (constructions, not the example thresholds)
• SUE / PEAD: Foster, Olsen & Shevlin (1984); Bernard & Thomas (1989); practitioner writeups of the same constructions
• Funding period vs annualized (×3×365 on 8h venues) and settlement snapshot
• Funding extremes, crowded positioning, cascade vs exhaustion fade
• 168-hour funding z and cascade operationalization in applied crypto research
• News as a filter on reversal (do not fade fresh fundamental news)
• Announcement-day microstructure costs on SUE implementation
All example thresholds (0.35, stop multiples, 09:45 entry) are [not] optimized and will not transfer across names, venues, or regimes without a proper walk-forward."

---

## Q-TB8-2 — infra + local build + buy vs build (verbatim)

"All dollar figures are indicative 2026 street / published list, not quotes. Redistribution language is the usual vendor pattern; get it in writing before you cache."

"Machine assumption: M5 Max, 128 GB unified memory, local SSD + external NVMe. Unified memory is the binding constraint for embedding batches, not GPU [throughput]."

### (a) News ingestion + novelty scoring

**What you actually need**
"1. A timestamped, ticker-tagged firehose (headline + body or long snippet).
2. Local store (you cannot z-score novelty against a corpus you are not allowed to persist).
3. An embedding or TF-IDF index over a rolling 30-day per-name corpus (your novelty = 1 − max cosine).
4. Point-in-time entity linking so 'Apple' is AAPL, not fruit.
Item 4 plus premium wire full text is where licenses bite."

**Vendor ladder (indicative)**

| Source | What you get | Indicative $ | Persist / redistribute |
| NewsAPI.org Business / Advanced | Headlines + short desc, no full body on any plan | $449–$1,749/mo | Commercial use on paid; no full-text corpus to embed; archive window plan-capped. Not enough for novelty. |
| Newscatcher / NewsData / GNews / APITube | Broader web news, some full text on paid | $85–$1,300/mo | Usually internal use; redistribution extra; source mix is web, not DJ/PRN timestamp quality. |
| Benzinga API / Polygon news | Ticker-tagged financial news, WIIM, some full text | Retail UI $177–$347/mo; API is sales-quoted, typically mid four to low five figures/yr | Backtest/store often a separate license. Redistribute almost never on self-serve. |
| RTPR / wire-only | BW / PRN / GNW / AccessWire, 300 ms | $139/mo UI; API separate | Fine for event time; bodies are PR text you can usually store for internal models. Does not cover reporter-written news. |
| StreetAccount / MT Newswires | Desk-quality catalyst news | Sales, often $20k–/yr | Internal display; bulk ML store negotiated. |
| RavenPack (analytics, not raw DJ) | Relevance, novelty, sentiment, event taxonomy on 40k+ sources | Street chatter $50–$100k/yr research seat; WRDS academic is institutional. They already ship a novelty field. | Raw underlying DJ/WSJ text is not yours to republish. Analytics rows are licensed for internal signals; redistribution of scores is a different SKU. |
| Bloomberg B-PIPE / LSEG / FactSet news | Gold-standard timestamps + bodies | Terminal $24–$32k/user/yr; B-PIPE / news API commonly $200k+/yr plus exchange fees | Impossible to legally build an equivalent firehose. Redistribution is a separate enterprise contract; most funds never get it. |

"Impossible without a license
• Dow Jones Newswires, Bloomberg, Reuters, WSJ, FT, StreetAccount full text as a research archive.
• Any product that resells those bodies inside your own API, dataset, or 'novelty scores for third parties.'
• A point-in-time, legally clean premium novelty feature that matches RavenPack EVENT_SIMILARITY / novelty without either (i) licensing Raven[Pack ...]
You can build novelty without those wires on: SEC 8-Ks (free), EDGAR, official PR wires, and a web-news API — knowing the signal will miss the [...]"

**Compute / RAM / storage on 128 GB M5 Max**

| Piece | Footprint |
| Ingest daemon | Negligible CPU; 1–2 GB RSS |
| Rolling 30-day US-name corpus, 5k liquid names, 20 arts/name | 3–8M docs. Bodies stored as parquet + 384–768-d embeddings: 15–40 GB hot, 200–500 GB/yr if you keep history |
| Novelty scoring | Batch embed with mlx / PyTorch MPS. 768-d MiniLM or GTE-small: 8–16 GB working set. A 7B local embedder wants 24–40 GB. 128 GB is comfortable for 7B + FAISS/hnswlib in RAM |
| Latency | Local embed few ms/doc after warmup; the bottleneck is vendor API lag, not the Mac |

**Engineering hours**

| Task | Hours (one senior) |
| Vendor client, ticker map, dedupe, clock hygiene | 40–80 |
| Store + PIT embeddings + novelty job | 60–100 |
| Replay harness vs returns | 40–60 |
| Total build on top of a licensed feed | 150–240 h |
| Attempt to scrape premium wires yourself | Do not. Legal + ToS; also you will lose timestamp fidelity |

"Buy vs build

| Piece | Verdict |
| Premium wires + entity/novelty analytics | Buy RavenPack or Benzinga/StreetAccount + your own embedder |
| Novelty math (cosine vs rolling corpus) | Build (a weekend once text is legal to store) |
| Web-news prototype | Buy cheap API ($500–/yr), accept coverage holes |
| Redistributable research dataset | Buy a redistribution SKU or don't ship it |"

"Practical stack on this machine: Benzinga or Newscatcher for live + EDGAR/PR wires + local GTE embeddings. Add RavenPack only if you [...]"

### (b) Crypto pipeline: funding / OI / liquidations for 20 perps

"Universe example: BTC, ETH + 18 liquid alts, 1–2 venues each (Binance + Bybit or HL)."

"Exchange websocket vs aggregator

| Path | What you get | Cost | Eng hours | Failure mode |
| Native WS + REST (Binance wss://fstream.binance.com, Bybit v5, HL info) | Funding (mark + next), OI, force-order / liq stream where published | $0 data. Need API keys; some venues want KYC | 80–150 h for a durable 20-symbol supervisor (reconnect, seq gaps, symbol maps, 8h vs 1h tenor, USDT vs coin-margined) | You own schema drift and weekend disconnects |
| Aggregator (CoinGlass, Velo, Laevitas, CoinAPI, Tardis) | Normalized funding, OI, aggregated liqs, history | CoinGlass self-serve hobby→pro is typically low hundreds to low thousands $/mo (history depth gated by plan); CoinAPI $99+/mo; institutional Amberdata/Laevitas sales-quoted; Tardis good for historical ticks | 20–40 h to wrap one vendor | You inherit their gaps and their liq definition |"

"Buy-vs-build for 20 names: build the live WS yourself, buy history once. Twenty symbols is well inside one process on this Mac. Aggregators earn their fee at 200+ symbols or [...]"

"Explicit liquidation caveat (do not skip this)
Public 'liquidation' prints are a censored, lower-bound tape:
• Venues publish force-order / liquidation feed subsets, not every ADL, insurance-fund takeout, or internal cross.
• [Aggregators] sum what exchanges emit. Missing a venue or a hidden insurance event understates cascade size.
• Coin-margined vs linear, and 'liq notional vs liq count,' are not comparable without your own normalization.
• Research that treats CoinGlass liq USD as ground truth is using a lower bound with time-varying coverage.
• Funding and OI from the same venue's official REST are much closer to complete than liqs."

**Compute / RAM / storage (20 perps)**

| Stream | Rate (order of mag.) | Local store |
| Funding | 1–3 prints / 8h / name, plus predicted | Tiny. <1 GB/yr |
| OI | 1s–60s snapshots | 5–20 GB/yr if you keep 1s; <2 GB at 1m |
| Liq + trades (optional) | bursty | Trades for 20 perps can be 50–200 GB/yr; liq prints themselves are small |
| Process RSS | One asyncio supervisor | 0.5–2 GB |

"128 GB is irrelevant here. A 2 TB external SSD is the real budget item if you also keep trades."

"Engineering hours
• Live 20-perp funding + OI + forceOrder, two venues, parquet sink, z-score job: 100–160 h to something you would trust overnight.
• 20–40 h of venue-specific footguns (Binance funding cap, HL hourly vs Binance 8h, Bybit inverse)."

"Buy vs build

| Piece | Verdict |
| Live funding + OI, 20 names | Build on exchange WS |
| Multi-year aligned history | Buy Tardis / CoinAPI / CoinGlass export |
| Liquidation 'truth' | Neither. You can only buy or scrape a lower bound. Document it in the research note |
| Redistribution of exchange data | Exchange ToS usually allow internal research; resale of their tape is licensed. Aggregator TOS almost always forbid passing their liq feed to a third party |"

"Impossible without a license: selling a packaged '20-perp liquidation tape' built from an aggregator; any non-public book or insurance [data]."

### (c) ASVI / social pipelines

"ASVI (Da, Engelberg, Gao 2011) is abnormal Google Search Volume for a ticker/company name vs its own trailing mean, not Twitter sentiment. ASVI_t = log(SVI_t) − log(median(SVI_{t−8}, …, SVI_{t−1})) (exact window varies by paper; weekly SVI is the classic)."

"Search volume

| Path | Indicative $ | License / reality |
| Official Google Trends API (alpha, 2025+) | Google has been rolling an official API with consistent scaling (unlike the website's 0–100 rebase per query) | Terms will control commercial/trading use. Treat as must-read license, not free-for-alpha. History 5y, lag 2 days — not an intraday signal |
| SerpApi / SearchApi / DataForSEO scrape of Trends UI | $275–/mo for a few thousand queries | ToS of Google and the scraper. Fine for a research prototype; fragile for a production book. Sampling noise is well-known |
| pytrends | $0 | Breaks constantly; no SLA |
| Meltwater / Brandwatch 'search buzz' | $15–$120k/yr | Different object than SVI |"

"You cannot legally reconstruct official Google SVI at scale by scraping if you are a commercial desk and want to publish or resell it. Weekly ASVI for a 2k-name universe is a few thousand Trends calls/[week]."

"Social (X, StockTwits, Reddit)

| Path | Indicative $ | Limits |
| Official X API | Pay-per-read; trends alone can be $0.20 per 20-trend pull; full firehose is enterprise (tens of k$/mo) | Redistribution tightly controlled. Historical search is the expensive SKU. |
| Sorsa / SocialData-style proxies | $49–$199/mo for modest tweet volume | You are buying a grey reseller. Compliance and sudden death risk |
| StockTwits trending | Cheap wrapper APIs $30–$300/mo | Message-level firehose for research usually sales[-quoted] |
| Reddit official API | Tight free tier; commercial is paid | ToS ban many 'trading signal' scrapes of dumped dumps |
| Adanos-style sentiment APIs | $299–/mo | Pre-aggregated; you do not own raw text |"

**Compute / RAM / storage**

| Pipeline | On M5 Max 128 GB |
| Weekly ASVI, 2k names | Trivial. A CSV of weekly SVI is megabytes. Job is I/O to Google |
| X keyword stream, 20 cashtags | 10–50 GB/yr raw JSON if you keep text; embeddings another 2–3× |
| Local sentiment (8B classifier) | 16–32 GB resident; fine on 128 GB next to the news embedder |
| Full X firehose | Not a laptop problem. Don't |

"Engineering hours

| Pipeline | Hours |
| ASVI weekly job + name-disambiguation ('Ford', 'Meta') | 40–80 |
| Robust Trends client with quota/backoff | 20–40 |
| X cashtag sentiment for 20 names via official API | 60–100 + ongoing ToS watch |
| Production social listening platform | Do not build |"

"Buy vs build

| Piece | Verdict |
| ASVI itself | Build the formula, buy or officially API the SVI |
| Intraday social alpha | Buy a sentiment vendor or skip; official X at research scale is not a side-project price |
| Redistributable tweet corpus | Impossible without an X commercial + redistribution contract |"

"Impossible without a license
• Google Search Volume as a product you resell
• X/Twitter historical firehose and most cashtag streams at desk scale
• StockTwits full message history for redistribution
• Any 'ASVI dataset' that is just scraped Trends packaged for others"

"Roll-up on this Mac

| Workstream | Recurring $ (honest research desk) | One-time eng | RAM | Disk / yr | Buy vs build | Blocked without license |
| (a) News + novelty | Prototype –/yr; serious –/yr (see QC) | 150–240 h | 16–40 GB peak | 0.2–0.5 TB | Buy text, build cosine | DJ/BBG/Reuters bodies; RavenPack-class novelty as a product |
| (b) 20-perp derivs | $0 live; $0–$3k/yr history | 100–160 h | <2 GB | 0.01 TB (F+OI) to 0.2 TB (+trades) | Build live, buy history | Resale of venue/aggregator tape; true uncensored liqs |
| (c) ASVI + light social | $0.5k–$4k/yr Trends+proxy; official X is a step-function | 80–150 h | 16–32 GB if you embed | 0.01–0.05 TB | Build ASVI; don't build a social platform | Google SVI resale; X firehose |"

"What 128 GB changes: you can keep news embeddings, a 7–8B local encoder, and the crypto supervisor in RAM at once. It does not replace a single wire license."

"Recommended spend order if this is a personal / small-book research stack
1. Exchange WS for (b) — zero dollars, highest completeness for funding/OI.
2. EDGAR + one mid-tier financial news API for (a); compute novelty locally.
3. Official or semi-official Trends for weekly ASVI only (not intraday).
4. Stop before RavenPack / B-PIPE / X Enterprise unless the book is funded to five figures of data budget.
5. Do not treat public crypto liquidation USD or scraped Trends as an institutional data asset; one is censored, the other is resampled."

---

## Q-TB8-3 — success ratios, after-cost efficacy, failure modes (verbatim)

"Paper magnitudes below are gross unless noted. After-cost and failure-regime notes are the part that usually does not survive the abstract."

### 1. News novelty vs staleness

"Construction (canonical). Tetlock (2011, RFS): staleness = textual similarity of a story to the previous ten stories on the same firm. Returns s[...]; the stale-news day return negatively predicts the next week. Retail flow is heavier on stale stories; reversal is larger where retail participation is high.
Fedyk and Hodson (2023): reprints vs recombinations of old facts. An extra 10% of a firm's news being old predicts that ~14% of that day's move reverses the following week; an extra 10% of old news being recombinations rather than reprints adds ~17% more reversal. The recombination premium rose from ~5 bp (2001) to ~24 bp (2014) per 10% increment — machines reprint, humans still treat mash-ups as news.
Related: overnight jump days reverse in the next regular session (~1% long–short on jump extremes in a 2026 sample before costs; the one-month hold of the same sort loses [money]). That is overreaction, not PEAD.
Documented shape. Fade stale / recombined news after a large print; do not fade novel, high-attention, quantitative negative news (that is the underreaction / 'pure news' side[...]).
After-cost honesty. Tetlock-style weekly reversals are tens of bp. Announcement-day half-spreads on mid- and small-caps eat the same tens of bp. The edge that survives is concentrated in names where you can trade inside 10–15 bp RT and where you score staleness before the retail print hits. A 30-minute-late fade of a reprint is just providing exit liquidity.
Failure regimes.
• Novel fundamental news (guidance cut, fraud, M&A) — fade is shorting information.
• Macro common-factor days (CPI, FOMC) — 'stale firm news' is not the driver.
• Low-retail, high-institutional names — Tetlock's reversal channel is weaker.
• Recombination that contains a new sufficient statistic (Gilbert et al. LEI-style summaries) can look stale and still be priced."

### 2. Crypto funding-rate contrarian

"Two different trades are constantly conflated.
(i) Harvest the rate (cash-and-carry / delta-neutral). Kasinski (2025): fully collateralized BTC/ETH carry, ~10.6% ann., 1.5% vol in-sample — a funding premium, not a reversal. Independent of traditional factors in that paper. He, Manela, Ross, von Wachter (20[25]): [...] ~1.8 even at retail fees, higher for makers. Deviations comove and have shrunk as the market matured.
(ii) Fade extreme funding as a directional signal. Survivorship-free test on 6.1M settlements (three venues): z-scored funding deciles, 3-day swing, ~+8.9 bp/day net of 4 bp one-way (~+32% ann., Sharpe 1.42), max DD −40%, up six of seven calendar years, −38% in the bad year. Daily rebalance Sharpe is higher gross and dies faster as fees rise (breakeven ~13 bp one-way vs ~23 bp for the 3-day swing). Focal long and short legs are [...] spread [...] is the result. Brave New Coin (2023) on BitMEX-era data: R² of funding → next return is near zero; only the extreme tails show the reversal the folklore describes.
Funding itself is mean-reverting (OU half-life on BTC ~8h in practitioner fits) — that is predictability of funding, not of spot."

"After-cost honesty. Directional fade must pay taker + impact + adverse funding if you are on the crowded side through settlement. A +0.05%/8h rate on 3× leverage is ~0.15% of margin per settlement — days of that wipe a 1–2% target. [This is a] tail strategy with a −40% DD print already in a public replication.
Crowded-leverage regime risk (the thing the Sharpe hides).
• Positive funding + rising OI + thin book = long-liquidation cascade. Your short-the-crowd fade can be right on the signal and still get stopped through clustered liq levels.
• ADL and insurance-fund events (Oct 2025-scale tapes) can close the winning side. That is not in a z-score backtest.
• Venue failure / withdrawal halt kills the hedge leg of (i). CEX–DEX basis papers treat counterparty stress as worse than a price crash.
• Sample-period dependence: 2021–22 extremes dominate many Sharpes; quiet +0.01% regimes have almost no [edge]."

### 3. Liquidation cascades — bounce size and data honesty

"Public practitioner work (not a single canonical journal article) treats a cascade as: crowded side flushes, partial bounce once OI drops and funding resets. 'Fade exhaustion, not the first flush' is the only specification t[hat survives]. There is no clean academic magnitude analogous to Bernard–Thomas 4.2%. Treat 1–3% mean-reversion targets after a documented OI washout as example rules, not a published premium."

"Data-censoring honesty (non-negotiable).
• Exchange 'liquidation' streams are force-order subsets. ADL, insurance-fund, internal crosses, and some coin-margined events do not print.
• Aggregated USD liq (CoinGlass et al.) is a lower bound with time-varying venue coverage. A 2026 study of seven BTC cascades found no single price/leverage/order-flow warning that fired on all seven; one recurring pattern (tighter taker buy/sell variance) still overlapped ordinary days.
• Backtests that condition on 'liq USD > X' are conditioning on a censored, revised, vendor-defined series. Walk-forward on that series overfits the vendor's backfill."

"After-cost / failure.
• Entering during the waterfall: spread + impact can be 50–200 bp on alts; stops gap through.
• Entering after exhaustion: you miss the easy 2% and compete with every other fade bot.
• Failure regime = trend continuation after a true deleveraging (macro shock, exchange insolvency). The bounce is not owed to you.
• Never size as if the liq tape is complete."

### 4. ASVI — Da, Engelberg, Gao and the decay

"Paper. Journal of Finance 66(5), 2011. Russell 3000, weekly Google SVI, 2004–2008. ASVI_t = log(SVI_t) − log(median(SVI_{t−8}, …, SVI_{t−1})). Result: stocks with high ASVI this week outperform ~30+ bp characteristic-adjusted over the next two weeks, then reverse within the year. Retail-attention channel (Barber–Odean). Also maps onto IPO first-day pop / long-run underperformance.
A UK replication on 2004–2011 FTSE data recovers the same direction at smaller size (order ~12 bp next-week association in one thesis specification).
Horizon. The tradable object in the original paper is weekly → 2-week. Google Trends is not a same-day tape (website rebase; official API still lags ~2 days). Using ASVI as an intraday trigger is a different, unpublished strategy."

"Decay since publication.
• The sample is pre-smartphone, pre-Robinhood, pre-'Google the ticker' as a reflex. Attention is less [...].
• Name collision ('Ford', 'Apple', 'Meta') got worse.
• Once the paper is in every alt-data pitch deck, the 30 bp two-week print is the upper bound of the original sample, not a 2026 live expectation.
• Product-search SVI (In Search of Fundamentals, 2011 working paper) predicts revenue surprise more than SUE — a different, slower object."

"After-cost honesty. 30 bp / 2 weeks on a Russell 3000 name, after 10–20 bp RT and weekly rebalance, is a small-stock / high-idiosyncratic leftover. Value-weight the same sort and much of it vanishes — the usual attention-anomaly pattern."

"Failure regimes. Earnings week (SVI spikes because the print is today), ticker changes, product-name pollution, and any week the market itself is the attention event."

### 5. PEAD — and the intraday leg

"Multi-day PEAD (the published object). Bernard and Thomas (1989, 1990): top-minus-bottom SUE decile ~4.2% over 60 trading days (~2% each leg), ~18% annualized hedge in the original telling; half of the 60-day drift arrives after day 10. Still replicated across markets; weaker post-2010, more residual in small/illiquid names.
Costs eat the liquid names. Chordia, Goyal, Sadka, Sadka, Shivakumar (FAJ): long–short PEAD is 0.04%/month value-weight in the most liquid bucket vs 2.43%/month in the most illiquid; transaction costs account for 70–100% of paper profits on the hedge. Ng, Rusticus, Verdi-style implementation papers and later simulations: naive event-study overstates alpha once you rebalance like a fund and pay costs; some implementations find no multi-factor alpha after costs (1974–2007 simulation)."

"Battalio and Mendenhall: if you use actual announcement timestamps and actual quotes, a 1993–2002 hedge can still clear ~14%/yr after spreads — but that is not 'trade the close.' Using Compustat's date [understates?] the drift by ~2.7% per quarter; waiting until the next close understates it by ~1.1%. Latency to the first quote after the print is first-order."

"Intraday / announcement-window leg. Most of the information move is in [the first two] days; the first 1–5 minutes after a BMO/AMC print are headline parsers, 5–30 minutes are guidance/se[condary headlines ...], the gap and much of the stale-liquidity move. There is no Bernard–Thomas table for '+X% from 09:45 to 15:55 conditional on SUE.' Practitioner 4-day post-print quintile stats (e.g. ~+1.8% / −2.1% median on S&P names since 2000 in [some sample]) [are descriptive], not an intraday Sharpe.
Required latency. To capture announcement-window PEAD you need the print [in] a tradable quote before the book resets — seconds to low minutes, not a 09:45 rule. A same-day RTH 'drift leg' after a held [open is a] momentum continuation filter, with a much smaller published foundation."

"Failure regimes.
• Liquid large-caps after 2010 (costs ≈ paper alpha).
• Hard-to-borrow shorts on the low-SUE leg.
• 'Beat and lower guidance' — SUE sign ≠ drift sign.
• Crowded quant rebalance into month-end / earnings-season clustering."

### 6. Social sentiment — signal vs manipulation

"What has a paper behind it.
• Attention / message volume (not polarity) is the more durable object: Antweiler–Frank (Yahoo boards), StockTwits/Twitter volume [studies]: activity predicts short-horizon pressure, then reversal.
• Signed sentiment (bullish minus bearish) is weaker, unstable, and easy to game. Tetlock's WSJ 'Abreast of the Market' column is news tone, not social."

"Manipulation / noise (the live failure mode).
• Cashtag pump groups, reply-bot swarms, and paid influencer bursts are designed to look like ASVI/social spikes.
• Crypto Twitter and thin-alt StockTwits are closer to a coordination device than an attention residual.
• Vendor 'sentiment APIs' that emit a −1/+1 without raw text are not auditable; you cannot separate bo[ts from humans].
• After 2011, retail attention is faster and more crowded. The 2-week DEG window compressed; a lot of the print now happens the same day as the tweet, which you cannot trade on a daily bar without look-ahead if the tweet is the event."

"After-cost honesty. A social long–short that looks like 20–40 bp/week in a 2012–15 paper typically does not survive: (i) [...] the pump you would be buying [...]."

"Failure regimes. Coordinated pumps, earnings-week chatter that is just the press release, celebrity tweets on mega-ca[ps]."

"Cross-cut: what is still plausible on a single-name, after-cost book

| Signal | Published gross object | After cost, 2026-realistic | Main failure |
| Stale-news fade | Next-week reversal; Tetlock + Fedyk–Hodson recombination extra | Small; needs cheap names + fast staleness score | Fading novel news |
| Funding carry | ~10% ann. delta-neutral in one 2025 paper; high Sharpe in 2022 arb paper | Venue + funding-reset + liquidation of the hedge | Exchange/ADL/basis blowup |
| Funding directional fade | ~9 bp/day net in one public 3-day z-decile test; −40% DD | Tail strategy; fees kill daily rebalance | Cascade continues; quiet funding regime |
| Liq-cascade fade | No canonical % | Only after OI washout; tape is censored | Macro continuation; gapped stops |
| ASVI | ~30 bp / 2 weeks (2004–08 R3k) | Much less value-weight; weekly data | Name collision; post-publication crowding |
| PEAD 60-day | ~4.2% T-B / 60d (1989) | 70–100% of liquid-name paper profits are costs | Illiquidity is the residual |
| PEAD same-day RTH | Not in Bernard–Thomas | Latency race; 09:45 is late | Beat-and-lower; crowded open |
| Social polarity | Fragile | Usually noise + pump | Manipulation |"

"The only three objects in this list with both a named paper and a still-defensible after-cost story for a non-HFT desk are: (1) don't fade novel news / do fade documented reprints; (2) delta-neutral funding carry with hard venue limits; (3) PEAD only where spreads do not consume the 60-day 4%. Everything else is either a tail, a pre-2010 residual, or a tape you cannot trust."

---

## QC notes (orchestrator)

1. Arithmetic spot-checks (all consistent): (A) 17,241 × $0.63 = $10,861.83; 28 bp × $885,000 = $2,478; net $8,383.83 = 8.38 bp ≈ 8.4 bp ✓. (B) z = 2.67; annualized 43.8%; 50 × $950 = $47,500; fees $2,658; impact $1,994; funding $930.30; net $41,917.70 ≈ $41,918 = 41.9 bp ≈ 42 bp ✓. (C) SUE = 3.00; 25,000 × $0.62 = $15,500; 56 bp × $1,020,000 = $5,712; net $9,788 = 9.79 bp ≈ 9.8 bp ✓.
2. Genuine omission in Grok's Q1 answer (preserved): the (A) Trigger cell reads "First 15-min bar after the article timestamp with $$" — the trigger condition's math block is empty in the page source.
3. Math fragments the page's accessibility tree dropped are marked `[...]` (not guessed): Q1 (A) sizing "Cap notional at X% of ADV"; Q1 (C) sizing "max X% NAV gross", "ADV cap X"; Q1 (C) borrow-fee numerator "Xbp/252 per day"; Q1 (C) tail "~$X net"; Q2 roll-up (a) "Prototype –/yr; serious –/yr" (lone "15", likely $15k/yr serious tier); Q3 social after-cost clause fragment. Q1's "are [not] optimized" restored where page extraction dropped the negation.
4. No rate-limiting; all three answers were full-length single responses.
5. Key sourced claims are research leads, not verified facts: Foster–Olsen–Shevlin (1984) (SUE); Bernard & Thomas (1989) (PEAD ~4.2% over 60 days); Tetlock (2011) (stale news reversal); Fedyk & Hodson (2023) (old news 14% reversal per 10% increment, recombination +17%); Da–Engelberg–Gao (2011) (ASVI ~30+ bp next two weeks); Kasinski (2025) (crypto funding carry ~10.6% ann.); He–Manela–Ross–von Wachter (2025) (crypto basis Sharpe ~1.8); Chordia, Goyal, Sadka, Sadka & Shivakumar (PEAD costs 70–100% of liquid-name paper profits); Battalio & Mendenhall (announcement timestamps + actual quotes ~14%/yr after spreads); Antweiler & Frank (message-board volume); Brave New Coin (2023) (funding → next return R² near zero). Vendor prices: indicative — verify before budgeting.

---

## Source list (only papers actually used)

- Foster, G., Olsen, C. and Shevlin, T. (1984), "Earnings Releases, Anomalies, and the Behavior of Security Returns," Accounting Review (SUE).
- Bernard, V.L. and Thomas, J.K. (1989), "Post-Earnings-Announcement Drift," JAR; Bernard & Thomas (1990).
- Tetlock, P.C. (2011), "All the News That's Fit to Reprint," JF (stale news).
- Fedyk, A. and Hodson, J. (2023), "When Can the Market Identify Old News?" (reprints vs recombinations).
- Da, Z., Engelberg, J. and Gao, P. (2011), "In Search of Attention," JF (ASVI).
- Kasinski, T. (2025), crypto funding carry (fully collateralized BTC/ETH ~10.6% ann.).
- He, Z., Manela, A., Ross, S. and von Wachter, S. (2025), crypto basis arbitrage.
- Chordia, T., Goyal, A., Sadka, G., Sadka, R. and Shivakumar, L., "Liquidity and the Post-Earnings-Announcement Drift."
- Battalio, R. and Mendenhall, R., announcement timestamps and actual quotes (~14%/yr after spreads).
- Antweiler, W. and Frank, M.Z., internet message-board volume/returns.
- Brave New Coin (2023), funding-rate → next-return study (BitMEX era).
- Gilbert et al., LEI-style news summaries (sufficiency under recombination).
- Everything not attributed to one of the above — thresholds, cost figures, worked-example values — is illustrative.
