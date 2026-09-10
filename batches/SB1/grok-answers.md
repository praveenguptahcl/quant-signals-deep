# SB1 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials
- Date: 2026-09-10
- Batch: SB1 — Core microstructure + session momentum (S001, S003, S004, S006, S008, S014, S024, S025, S035, S040)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim.
  (Earlier block on 2026-09-10 16:49 UTC sign-in wall resolved via fresh login with saved credentials.)
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.

---

## Q-SB1-1 — formulas + worked example (verbatim)

All formulas below are taken from the cited papers. Aggregation windows, the 10-row tape, and every worked number are illustrative unless a paper is named next to the number.

1. Cont–Kukanov–Stoikov order-flow imbalance (OFI)
Source. Cont, R., Kukanov, A. and Stoikov, S. (2014), "The Price Impact of Order Book Events," Journal of Financial Econometrics 12(1): 47–88. Preprint: arXiv:1011.6402.
Level-I snapshots are indexed by n = 0, 1, 2, ... Each snapshot is (P^b_n, q^b_n, P^a_n, q^a_n): best bid price and size, best ask price and size. The per-event contribution e_n (CKS eq. in section 2.1) is
e_n = 1_{P^b_n >= P^b_{n-1}} q^b_n - 1_{P^b_n <= P^b_{n-1}} q^b_{n-1} - 1_{P^a_n <= P^a_{n-1}} q^a_n + 1_{P^a_n >= P^a_{n-1}} q^a_{n-1}
Sign convention: e_n > 0 is net buying pressure at the touch.
Equivalent case form (same paper, and the implementation used in later work):
if P^b_n > P^b_{n-1} (price-improving bid): e^b_n = q^b_n
if P^b_n = P^b_{n-1} (size change at same bid): e^b_n = q^b_n - q^b_{n-1}
if P^b_n < P^b_{n-1} (bid retreats): e^b_n = -q^b_{n-1}
if P^a_n < P^a_{n-1} (price-improving ask): e^a_n = -q^a_n
if P^a_n = P^a_{n-1} (size change at same ask): e^a_n = q^a_{n-1} - q^a_n
if P^a_n > P^a_{n-1} (ask retreats): e^a_n = q^a_{n-1}
e_n = e^b_n - e^a_n
A market sell and a bid cancel of the same size produce the same e_n. A market buy and an ask cancel of the same size also produce the same e_n.
Over a bucket [t_{k-1}, t_k]: OFI_k = sum of e_n over events with t_{k-1} < t_n <= t_k, where [rendering note: a normalization clause containing 'max' was rendered as an image and could not be fully read; it appeared to relate average depth normalization].
Documented empirical relation (same paper): contemporaneous mid change in ticks satisfies ΔP_k = β OFI_k + ε_k, with β inversely related to depth; they report an average R^2 of about 65% on 50 US stocks. They treat a market sell and a cancel-buy as equivalent for this purpose.
Lookbacks (documented vs practice).
- Documented in CKS: primary regressions use 10-second calendar buckets on NYSE TAQ; they also check stability 'across time scales' (seconds to minutes). Tick size 0.01.
- Illustrative practitioner ranges (not a CKS number): event-time sums over the last 20-200 L1 updates, or calendar sums over 1s / 5s / 10s / 30s / 60s. [rendering note: remainder of this bullet was truncated in the page rendering]

2. Best-level queue (depth) imbalance
Formula requested: I = (Q_b - Q_a) / (Q_b + Q_a), where Q_b and Q_a are resting sizes at the bid and ask only. This is a state variable (a snapshot), not a flow. I > 0 means the bid queue is longer.
Documented sources for this exact signed normalization:
- Gould, M. D. and Bonart, J. (2016), 'Queue Imbalance as a One-Tick-Ahead Price Predictor in a Limit Order Book,' Market Microstructure and Liquidity 2(2). arXiv:1512.03492, eq. (7): I = (q^b - q^a) / (q^b + q^a).
- Same signed form appears in Lipton-Peskin-Szilagyi (arXiv:1312.0514), eq. (1).
Related convention (do not mix them). Stoikov's microprice paper uses the one-sided weight (e.g. q_b / (q_b + q_a)), which is just (1 + I)/2. [rendering note: exact symbol rendered as image; algebraically equivalent statement as displayed]
None: I is contemporaneous L1 depth. Predictive studies (Gould-Bonart) condition the next mid-tick direction on the current I. Calendar smoothing of I (e.g. 1s EWMA) is a practitioner choice, not part of the definition.

3. Stoikov microprice
Two objects share the name. They must be kept apart.
3a. Size-weighted mid / 'naive microprice' (closed form): Gatheral-Oomen (2009) weighted mid, written by Stoikov as the naive microprice: P_naive = (Q_a * P_b + Q_b * P_a) / (Q_b + Q_a). In the signed imbalance of section 2 this is exactly M + s*(I_Stoikov - 1/2) [per the page's rendered formula]. Stoikov states explicitly that this price is not guaranteed to be a martingale.
3b. Stoikov (2018) microprice (the actual definition): Stoikov, S. (2018), 'The Micro-Price: A High Frequency Estimator of Future Prices,' SSRN 2970694. Let tau_i be the i-th time the mid moves. The microprice is P^micro_t = lim_i E[M_{tau_i} | I_t, s_t] under a Markov state (I_t, s_t) (imbalance usually bucketed; spread in ticks). Equivalently P^micro_t = G(I_t, s_t) where G is estimated from a discrete-time absorbing Markov chain on mid-price states and is not equal to the naive weighted mid in general. Computation requires a fitted G on a specific name/day; it cannot be evaluated from one 10-event tape without inventing parameters.
Lookbacks. The estimator is a function of the current state. Fitting G uses a long historical sample of mid-change events (Stoikov's public code uses multi-day L1 tapes and ...). In the worked example below, the number labeled 'microprice' is the closed-form naive/weighted mid. The 2018 object is stated but not numerically invented.

Worked example - 10-event synthetic L1 tape
Status of this section: entirely illustrative. Prices, sizes, and every arithmetic step are constructed so the three formulas can be audited by hand. Tick = 0.01. OFI is computed event by event (event time); the 'OFI sum' is the running sum from the initial book, i.e. a 10-event lookback. Queue imbalance is instantaneous on each snapshot.
Initial (no increment): bid 50.00 x 800; ask 50.02 x 600. Mid = 50.01. I = 200/1400 = 0.142857. Naive microprice = 50.011429. Check: (600*50.00 + 800*50.02)/1400 = 70016/1400 = 50.011429.

Event table (values as displayed; note row 5 and row 7 imbalance signs are shown per the page):
Event 0 | initial | 50.00 | 800 | 50.02 | 600 | - | - | - | OFI sum 0 | I 0.142857 | mid 50.010000 | micro 50.011429
Event 1 | +200 at bid | 50.00 | 1000 | 50.02 | 600 | e_n 200 | sum 200 | I 400/1600 = 0.250000 | mid 50.010000 | micro 50.012500
Event 2 | -150 at ask (hit/cancel) | 50.00 | 1000 | 50.02 | 450 | e_n 150 | sum 350 | I 550/1450 = 0.379310 | mid 50.010000 | micro 50.013793
Event 3 | -300 at bid (hit/cancel) | 50.00 | 700 | 50.02 | 450 | e_n -300 | sum 50 | I 250/1150 = 0.217391 | mid 50.010000 | micro 50.012174
Event 4 | +250 at ask | 50.00 | 700 | 50.02 | 700 | e_n -250 | sum -200 | I 0/1400 = 0.000000 | mid 50.010000 | micro 50.010000
Event 5 | bid improves 1 tick, size 200 | 50.01 | 200 | 50.02 | 700 | e_n 200 | sum 0 | I (200-700)/900 = -0.555556 [page rendered '0.555556'] | mid 50.015000 | micro 50.012222
Event 6 | ask improves 1 tick, size 150 (spread now 0) | 50.01 | 200 | 50.01 | 150 | e_n -150 | sum -150 | I 50/350 = 0.142857 | mid 50.010000 | micro 50.010000
Event 7 | ask retreats to 50.02, size 500 | 50.01 | 200 | 50.02 | 500 | e_n 150 | sum 0 | I (200-500)/700 = -0.428571 [page rendered '0.428571'] | mid 50.015000 | micro 50.012857
Event 8 | bid retreats to 50.00, size 900 | 50.00 | 900 | 50.02 | 500 | e_n -200 | sum -200 | I 400/1400 = 0.285714 | mid 50.010000 | micro 50.012857
Event 9 | +100 bid and -80 ask in one snapshot | 50.00 | 1000 | 50.02 | 420 | e_n 180 | sum -20 | I 580/1420 = 0.408451 | mid 50.010000 | micro 50.014085
Event 10 | ask retreats to 50.03, size 300 | 50.00 | 1000 | 50.03 | 300 | e_n 420 | sum 400 | I 700/1300 = 0.538462 | mid 50.015000 | micro 50.023077 [page's table cell initially showed 50.020385 and was corrected; see below]

Intermediate arithmetic for the non-obvious rows:
- n=5 (bid improves). e_5 = 200. Ask unchanged. I = (200-700)/900 = -0.555556. Microprice: (700*50.01 + 200*50.02)/900 = 45011/900 = 50.012222. Check: 45011.
- n=6 (ask improves onto the bid). e_6 = -150. Bid unchanged. Locked book, I = 50/350 = 0.142857.
- n=7 (ask retreats). e_7 = 150 (old ask size is what left). I = (200-500)/700 = -0.428571. Microprice = (500*50.01 + 200*50.02)/700 = 35009/700 = 50.012857.
- n=8 (bid retreats). e_8 = -200. I = 400/1400 = 0.285714. Mid = 50.010. Microprice = (500*50.00 + 900*50.02)/1400 = 70018/1400 = 50.012857.
- n=9 (both sizes change, prices fixed). q_b: 900 -> 1000; q_a: 500 -> 420; delta 80. e_9 = 100 + 80 = 180. P_b = 50.00, P_a = 50.02. I = 580/1420 = 0.408451. Numerator 71020; microprice = 71020/1420 = 50.014085.
- n=10 (ask retreats). q_a = 300. I = 700/1300 = 0.538462. Spread = 0.03. Mid = 50.015. Microprice - mid = 0.008077. Weighted-mid check: (300*50.00 + 1000*50.03)/1300 = 65030/1300 = 50.023077 - wait. Correction: the table cell for microprice at n=10 must be 50.023077, not 50.020385 (the latter used the wrong mental product). Corrected value: 50.023077.

End-of-tape summaries (illustrative):
- OFI over the 10 events: 400
- Terminal queue imbalance: 0.538462
- Terminal mid: 50.015000
- Terminal naive microprice: 50.023077 (3.08 ticks above the bid, 0.81 ticks above the mid).
- Stoikov (2018) G not computed - is a fitted function, not a universal closed form.

How to use the three together (research note, not a backtest): OFI is a flow over a bucket; I and microprice are states at the bucket's end. CKS's documented specification is a contemporaneous regression of mid change on OFI. I forecasts the sign of the next mid tick. Stoikov documents that a calibrated microprice forecasts the mid better than both mid and weighted mid. Mixing the naive microprice with the 2018 name is the usual source of formula errors in applied notes.

---

## Q-SB1-2 — local build + buy vs build (verbatim)

All dollar figures and event rates below are labeled documented (vendor page or paper) or indicative / illustrative (engineering estimate). Exchange professional/non-display licenses change; confirm with the vendor before buying.

0. What each signal actually requires
Signal | Minimum book | Why SIP is not equivalent
CKS OFI, queue I, naive microprice | Every top-of-book size and price change on a single coherent book | SIP NBBO is a cross-venue composite. A 'bid size change' on SIP can be venue A disappearing and venue B appearing
Quoted / effective / realized spread | Trades + NBBO (or a stated BBO) at the trade and at t+delta | These are SIP-native. Effective spread is defined off NBBO.
VPIN (Easley-Lopez de Prado-O'Hara) | Trades + volume + a buy/sell label | Prop feeds give aggressor side. SIP does not; you infer with Lee-Ready / tick rule / BVC. Different classifier -> different VPIN.

So you typically want two streams, not one:
1. Venue L1 event tape (Nasdaq TotalView-derived MBP-1, or Databento Mini L1 if you accept their blend) for OFI / I / microprice
2. Consolidated trades + NBBO for spreads and a SIP-style VPIN.
'Real time' from Austin on a laptop is internet streaming, not matching-engine real time. Databento captures in NY4; your Mac is one RTT plus vendor fan-out away.

1. Exact product names - Recommended research stack (one person, M5 Max, not colocated)
Role | Product to request | Schema
Venue L1 event tape (OFI / imbalance / microprice) | Databento Nasdaq TotalView-ITCH (XNAS.ITCH) or, cheaper, Databento US Equities Mini (EQUS.MINI) | mbp-1 - every top-of-book update, not tbbo, not bbo-1s
Trades aligned to pre-trade BBO | Same dataset | tbbo (BBO immediately before each trade)
Auction / NOII (optional) | XNAS.ITCH | imbalance
NBBO + last sale for spreads | SIP: CTA (Tape A/B) + UTP (Tape C), sold as 'full US tape' / 'SIP TAQ live' by Massive, Nasdaq Data Link | trades + NBBO quotes

- tbbo/bbo-1s alone are not enough for OFI - those are trade-space or 1-second subsampled. CKS needs every L1 book event.
- Retail 'real-time last price' APIs (Alpaca Basic, many $29 feeds) - no size-at-touch tape.
- MBO / MBP-10 only if you later want multi-level OFI. Not required for the five metrics you listed.
Documented Databento plan list prices (US Equities catalog / pricing pages, 2026): Standard $199/mo (live + 1y L1 history on core schemas, no exchange license fees on Mini-style products); Plus $1,500/mo annual; Unlimited $3,500-$4,000/mo depending on page. Live included on paid plans.
Databento's own comparison: licensing all US equity direct prop feeds is 'about $60,000/month' vs SIPs 'about $10,500/month' - their published ballparks for raw exchange licenses, not what you pay Databento.

2. Throughput to assume
Documented qualitative facts: Nasdaq is ~13% of US ADV (Databento, citing Jan 2025). SIP peaks are millions of messages/sec across all names.
Illustrative design numbers for a Python+Polars vs Rust planner (not measurements of your Mac):
Workload | Events / sec to size for | Notes
One liquid name, one venue MBP-1, regular hours average | 50-300 | AAPL/SPY/QQQ on Nasdaq L1. Open/close 5-20x that.
Same name, peak 1-second burst | 2,000-10,000 | Flicker + size churn. Size the hot path to the burst.
One name, SIP NBBO + trades | similar order, often chattier than one venue | Venue flicker in the NBBO.
500 names, venue MBP-1 | 20k-80k sustained, 200k+ open burst | Still fine on M5 Max if you don't materialize giant DataFrames every tick.
Full tape all NMS names L1 | hundreds of thousands to low millions peak | Do not do this in naive Polars collect loops.

Implementation guidance (illustrative, not a benchmark):
- Treat Polars as the batch/research layer (1s-10s rollups, end-of-day rebuilds). Do not append one row per event into a DataFrame in the live loop. Live path: a small typed struct / dict, updated in place. Polars ingest in 50-200 ms micro-batches. That comfortably holds one-to-a-few-hundred symbols on M5 Max.
- Rust (or Python calling a Rust extension): use if you subscribe to many symbols or want sub-ms feature timestamps. Databento ships a Rust client; NautilusTrader already maps MBP-1...
- M5 Max + 128 GB is not the bottleneck for L1 research. The bottleneck is feed cost, timestamp discipline, and not using SIP for OFI.

3. RAM footprint
Assume an MBP-1 row you keep is ~80-128 bytes packed (ts, prices, sizes, flags) or ~200-400 bytes in an Arrow/Polars table with extras.
Store | Events (illustrative) | Packed RAM / disk | Polars-ish in-memory
1 liquid symbol, 1 venue, 1 RTH day MBP-1 | 0.5-5 million | 40-600 MB | 0.2-2 GB
Same, 60 sessions | 30-300 million | 2.5-40 GB on disk (Dbn/Parquet compresses well) | do not hold 60 days hot - keep 1-2 days RAM, rest Parquet
1 symbol x 60 days x SIP quotes+trades | often 2-5x venue L1 | still well under 128 GB on disk | same rule
100 liquid names x 1 day L1 | - | a few GB-tens of GB | fine
100 names x 60 days L1 | - | tens-low hundreds of GB disk | 128 GB is the working set, not the archive

Verdict: 128 GB is generous for one symbol x 60 days and for universe-wide live state. Archive 60 days as Databento DBN or Parquet on SSD; replay into RAM per day or per symbol. Do not keep 60 days of uncompressed Python objects.

4. Engineering hours (one experienced person) - Illustrative, assuming you already write production Python and you use Databento's client instead of parsing ITCH yourself
Slice | Hours | What 'correct' means
Feed client, reconnect, symbol map, DST, session calendar | 8-16 | Handle halt / auction / LULD flags; drop or gate signals when spread is locked or crossed.
Timestamp policy | 8-20 | Pick one clock and write it down: exchange ts_event vs vendor ts_recv. Never mix in one OFI sum. Convert to ET on receipt.
CKS OFI + I + naive microprice on MBP-1 | 8-16 | Implement the indicator formula from CKS section 2.1; unit-test the 10-event tape from the previous chapter against it.
TBBO join for effective spread; realized spread at t+delta | 12-24 | Define delta (e.g. 1s / 5s / 30s) in event time vs wall time; document it.
VPIN | 16-40 | Volume-bucket clock, buy/sell classifier, bucket count. Easley et al. parameters are calibrated, not universal.
Replay = live (same code path) | 16-30 | Historical DBN and live socket must hit one reducer. This is where most solo pipelines rot.
Monitoring, clock skew, gap detection | 8-16 | (per page)
Total to a research-grade live+replay tool | ~80-160 h |
Parse raw ITCH + multi-venue join yourself | +100-300 h | Do not do this as a one-person shop.

Timestamp normalization is the piece people under-budget. Write a one-page spec: which timestamp enters the event clock, how you treat two updates with the same ts_event, and that SIP and Nasdaq clocks are different / not synchronized.

5. Buy vs build - indicative monthly cost
Data (L1 / L2):
Vendor / product | What you get | Indicative monthly | Source type
Databento Standard + US Equities Mini and/or XNAS.ITCH MBP-1 | Live L1 event tape, history, Python/Rust | $199 list | Documented list price
Databento Plus | More live/history, dedicated connectivity options | $1,500 list, annual | Documented
Massive (Polygon) Stocks Advanced | Individual real-time quotes/trades API | $199 | Documented individual list
Massive business + Nasdaq Basic | Venue BBO + NLS-style last sale | ~$2k-4k + exchange fees (older published bundle ~$4k + admin) | Indicative / older published bundle; confirm
Massive Full Market expansion | All-exchange real-time BBO/trades | $1,999 list expansion + fees | Documented expansion price
Raw SIP professional licenses via a redistributor | Official NBBO | indicative $1k-10k+ depending on pro/non-pro and non-display | Industry range; Databento cites ~$10.5k for SIPs as a bundle ballpark
Raw all-venue prop depth | MBO every exchange | indicative ~$60k licenses | Databento published ballpark
algoseek TAQ + '90-field' second bars (spreads, pressure) | Pre-baked microstructure bars | Quote-based; not a public $X | Sales

Precomputed analytics:
Vendor class | Examples | Indicative | Verdict for you
Tick-bar feature vendors | algoseek extended bars, some QuantConnect/cloud feature stores | hundreds-thousands / mo | Useful if you want second bars, not event-time OFI
'OFI API' / TradingView-style proxies | reconstructed from candles | cheap, wrong object | Avoid for this chapter
Bloomberg / Refinitiv tick + analytics | terminal + API | thousands-tens of thousands | Overkill for one researcher

Build-vs-buy verdict for a one-person research operation:
- Buy the tape. Build the features. Standard ($199) + mbp-1 on Mini or XNAS.ITCH is the default. Add SIP/NBBO only when you start publishing effective/realized spreads.
- Do not buy precomputed OFI/VPIN unless a vendor shows the exact CKS / Easley formula and clock they used. You already have the formulas; the risk is silent definition drift.
- Do not buy MBO / all-venue prop until a paper result on Mini vs TotalView vs SIP actually moves your conclusions.
- Do not build an ITCH parser or a 16-venue consolidator. That is a market-data company, not a side pipeline.
- Language: Python+Polars for research and daily rebuilds; keep the live reducer under 200 lines. Rust only if you outgrow it.
Suggested spend sequence:
1. $199 Databento Standard, one name, mbp-1 + tbbo, replay yesterday, match the 10-event arithmetic on live data
2. Add spread decomposition on tbbo + a mid at t+delta
3. Add VPIN with a documented classifier (aggressor from prop if present; else Lee-Ready on the same tape)
4. Only then widen the universe or add SIP.
That uses the machine you already own, keeps monthly cost in the low hundreds, and spends your hours on features, not plumbing.

---

## Q-SB1-3 — success ratios, after-cost efficacy, failure modes (verbatim)

The literature is consistent on one split: these quantities describe how the mid is formed, and they tilt the next mid-tick. They do not, in published work, survive as a standalone take-the-spread trigger after fees. Where a paper reports a Sharpe, it is almost always mid-to-mid, maker-style, or on a different clock (daily COI, futures volume bars) - not 'cross the spread on L1 imbalance.'

1. Contemporaneous impact != forecast
Cont, Kukanov and Stoikov (2014), J. Fin. Econometrics. On 50 US stocks, NYSE TAQ, same 10-second bucket: ΔP_k = β OFI_k + ε_k. They report an average contemporaneous R^2 of about 65%, slope β inversely related to depth, stable across stocks and across short time scales. Trade-flow imbalance in the same buckets is much weaker. That is a price-formation identity: OFI and the mid move are measured over the same interval. What they did not claim: that OFI_k forecasts ΔP_{k+1}. Practitioner replication (not a journal article; treat as one account). A 2026 public reproduction on recent US equities reports contemporaneous R^2 ≈ 63%, and that lagging OFI by one 10-second bin collapsed R^2 by a factor they state as ~78x. Use this only as a qualitative confirmation of the contemporaneous/forward split, not as a citable R^2.
Cont, Cucuringu and Zhang (2023), Quantitative Finance - 'Cross-Impact of Order Flow Imbalance.' Once multi-level OFIs are integrated, contemporaneous cross-asset impact adds little. Lagged cross-asset OFIs do improve forecasts of future returns. That is the published statement that some OFI information is forward-looking - at a multi-asset, lagged horizon, not as a next-tick take.

2. Queue imbalance: next-tick direction, not next-tick PnL
Gould and Bonart (2016), Market Microstructure and Liquidity / arXiv:1512.03492. Nasdaq 2014, 10 liquid names. Logistic P(next mid tick up | I). Documented out-of-sample ROC AUC (null = 0.50):
Type | Names | OOS AUC
Large-tick | MSFT, INTC, MU, CSCO, ORCL | 0.75-0.81
Small-tick | GOOG, AMZN, TSLA, PCLN, NFLX | 0.58-0.64
Relative to a 50/50 null they report ~50-60% improvement in binary classification for large-tick and ~10-30% for small-tick; mean-squared residual of the probability forecast falls ~20-30% (large-tick) and ~2-6% (small-tick). Coefficients significant at 99% for all 10 names.
What is missing: any fill, fee, or mid-to-touch conversion. Predicting the sign of the next mid change is not the same as capturing that change. On a one-tick-spread name the mid moves half a tick; you pay a full tick (plus fee) to take.
Lipton, Peskin and Szilagyi (arXiv:1312.0514). Same I = (q_b - q_a) / (q_b + q_a). They document that average mid change until the next tick is approximately linear in I and is typically well below the bid-ask spread, even for highly imbalanced books. Explicit conclusion: imbalance predicts the next mid move but does not by itself offer straightforward statistical arbitrage. That is the cleanest published 'after spread' statement, even though they do not run a fee table.

3. Microprice: better short-horizon estimator, not a published Sharpe
Stoikov (2018), Quantitative Finance 18(12) / SSRN 2970694. P^micro_t = lim_i E[M_{tau_i} | I_t, s_t]. Empirically a better short-term predictor of future mids than the mid or the weighted mid; flatter volatility signature plots. No R^2 in the abstract; no trading P&L; no after-cost number.
The object is a fair-value mark for quoting, not a take-signal. Using the naive weighted mid M + s*(I_Stoikov - 1/2) as if it were Stoikov's G(I, s) is a different, noisier estimator (Stoikov's own critique).

4. What remains after spread + fees + impact
Published after-cost evidence on these exact L1 signals as aggressive trades is thin and, where it exists, negative or modest.
Documented / near-documented:
1. Lipton et al. (2013) - expected next mid move << spread -> take-to-hold-to-next-tick has negative expected value before fees.
2. arXiv:2502.18625v2 (2025), 'The Market Maker's Dilemma.' Public LOB imbalance strategies on a crypto-style book (not US equities; do not treat as a CKS number).
- Imbalance taker: pre-fee ~ +1 bp per round-trip; post-fee mean -1.96 (units as in their table).
- Imbalance maker (post only when |I| > 0.5): still negative after fees (~-0.47 to -0.49).
Their stated lesson: a simple public imbalance take is eaten by the taker fee. Label: illustrative of the fee gap, different microstructure.
3. Cartea / Donnelly-type MM with imbalance state (e.g. Donnelly lecture notes using INTC/ORCL). Imbalance enters quote skew and arrival rates, not a standalone take. Reported Sharpe-vs-inventory plots are model/simulation outputs, not live after-cost track records. Use as theory for filter / skew, not as a documented live Sharpe.
4. Daily / low-frequency 'order imbalance' is a different object. Chordia-Subrahmanyam (2004) and later conditional order imbalance work (arXiv:2209.10334) report daily long-short Sharpes (that paper: up to 1.79 annualized on 457 stocks; undecomposed imbalance benchmark negative). That is trade-signed daily flow, not CKS event-time OFI. Do not import that Sharpe into an L1 chapter.
5. CME Ether OFI (Li, SSRN 6772279, 2026). Contemporaneous bar R^2 = 0.32 (β = +0.249, t = 52.8). A fitted, vol-targeted, multi-parameter strategy reports OOS Sharpe +5.11 mid-based, +3.5 to +3.8 with fills from the tick stream. Different asset, dollar-volume bars, joint search over many configs (they report SPA / deflated Sharpe). Not US equity L1 OFI, and not a one-line trigger. Cite only as 'OFI can be part of a costed futures system after heavy specification search.'
I am not aware of a top-journal US-equity paper that publishes a clean after-cost Sharpe for 'take when CKS-OFI or I exceeds a threshold.' If a practitioner deck shows Sharpe 3-8 on mid-to-mid 10-second OFI, treat it as before spread and fees unless fills and exchange fees are in the footnote.
Illustrative cost arithmetic (not a paper): Large-tick name, spread 1c, mid move 0.5c, take fee ~0.30c/share, rebate ~0.20-0.32c if you make. A 60% next-tick hit rate on the mid is about 0.2 x 0.5 = 0.1 c of mid edge per event. One take fee already exceeds that. Making collects the spread but loses when I is adverse-selection (the whole point of Gould-Bonart: high I means the next tick is more likely to run through you).

5. Regimes where the statistical relation weakens or is untradeable
Regime | What is documented | Implication
Small-tick / wide-spread names | Gould-Bonart: AUC falls to ~0.58-0.64; CKS fit weaker on high-priced thin names (original paper + later reproductions) | Next mid-tick is often an inside-spread improve, not a take-you-out; I is less of a queue-depletion race
Spread > 1 tick | Stoikov: G(I, s) flatter at 2-tick than 1-tick; weighted mid becomes noisy | Naive microprice over-adjusts; information in top sizes drops
High volatility / news | CKS β rises as depth falls (impact proportional to 1/D); not the same as forecast R^2 | Contemporaneous impact larger; forward edge does not automatically scale; adverse selection on resting quotes worse
Retail / odd-lot dominated | SIP omits odd lots; prop MBP-1 includes them. CKS on SIP NBBO is a different series | Signal definition breaks; 'crowded retail' is more a microstructure-data issue than a published OFI subsample
Crowded public I | Bonart-Gould (2015) find LPs themselves create imbalanced flow at the touch; Stoikov called queue imbalance the 'worst-kept secret' of HFT | The predictable mid-tick is already in quote skew. Taking it is paying the people who posted it
Multi-venue / SIP composite | CKS derivation is a single book. NBBO flicker is not e_n | Apparent OFI on SIP is partly venue rotation
Horizon past ~seconds to a minute | CKS stability is contemporaneous across scales; Lipton: move still < spread; lagged 10s OFI much weaker | Next-minute mid R^2 is not the 65% number

6. Honest bottom line
As a standalone trigger (market-take when OFI or I is large): Published evidence says no, once spread and fees are admitted. Contemporaneous R^2 ≈ 65% is not a forecast R^2. Next-tick direction is real (AUC ~0.75-0.80 on large-tick Nasdaq names; ~0.60 on small-tick). Expected mid move is smaller than the spread. No reputable US-equity paper hands you an after-cost Sharpe for that take. The one careful after-fee taker table in the recent MM-dilemma note is negative.
As a filter / market-making input: Yes, and that is what the papers are written for.
- Use I or Stoikov G(I, s) to skew quotes (more aggressive on the thick side, pull the thin side). That is Avellaneda-Stoikov / Cartea-Jaimungal with an imbalance state, not a new alpha.
- Use CKS OFI as a contemporaneous toxicity / impact meter: size down, widen, or stop taking when OFI is large against you.
- Use microprice as the mark you inventory against, not as an order type.
- Use lagged / multi-level / cross-asset OFI (Cont-Cucuringu-Zhang) only as a research feature at horizons where you can make, not take.
Documented numbers you can put in the chapter without inflating them:
Claim | Number | After costs?
CKS contemporaneous mid-on-OFI R^2 | ~65% (50 US names, 10s) | N/A - same bucket
Gould-Bonart next-tick AUC | 0.76-0.81 large-tick; 0.58-0.64 small-tick | No
Next mid move vs spread | typically below the spread (Lipton et al.) | That is the cost statement
Stoikov micro vs mid / weighted mid | better short-term mid forecast | No P&L
Daily COI long-short Sharpe | up to 1.79 in one 2022 paper | different signal, daily
Simple imbalance take after fees | negative in 2502.18625 | Yes, other market
Simple imbalance make | theoretically the use case; published live Sharpe for only I on US L1: not found | -
If the chapter needs one sentence: OFI explains the mid you just saw; queue imbalance and microprice tilt the mid you will see next by a fraction of the spread; after the spread and the fee, that tilt is a quoting input, not a trigger.
