# duck.ai answers — SB1 (bot: GPT-5.6 Luna via duck.ai, anonymous, 2026-09-10)
## Q-scout: Order-flow imbalance (OFI) deep dive — VERBATIM

> Model used web search during generation. Model explicitly flagged: parameter tables = "implementation conventions, not universal constants"; throughput = "engineering estimates rather than guaranteed benchmarks"; pricing = "indicative estimates, not published quotes"; RAM = "an estimate". Formulas, worked example, Polars code presented as documented/canonical.

### 1. Definition and formula
Order-flow imbalance measures the net pressure added to the best bid and best ask by limit-order submissions, cancellations, executions, and quote changes. Cont, Kukanov, and Stoikov's original formulation uses Level 1 quotes only: best bid price and size, and best ask price and size. Their central empirical result: short-horizon price changes approximately linear in OFI, price impact inversely related to available market depth. [arXiv 1011.6402, SSRN]

Notation (event n): b_n best-bid price; q_n^b size at best bid; a_n best-ask price; q_n^a size at best ask.
- e_n^b = q_n^b if b_n > b_{n-1}; = q_n^b − q_{n-1}^b if b_n = b_{n-1}; = −q_{n-1}^b if b_n < b_{n-1}
- e_n^a = −q_n^a if a_n < a_{n-1}; = −(q_n^a − q_{n-1}^a) if a_n = a_{n-1}; = q_{n-1}^a if a_n > a_{n-1}
- ΔOFI_n = e_n^b + e_n^a; OFI_k = Σ over interval.
- Predictive regression: Δm_k = α + β·OFI_k/D_k + ε_k, m_k mid-price, D_k depth scale (e.g. avg top-of-book depth). Normalization required — raw OFI not comparable across stocks/regimes.
- Typical params: depth L1 (extensions top 3/5/10); window 100ms/250ms/1s/5s or 50–1000 events; signal form raw/depth-normalized/z-score/percentile; horizon 100ms–seconds; calibration per-symbol, per-time-of-day, volatility/liquidity conditioned.
- Multi-level OFI ≠ original CKS measure (original = best-quote only).

### 2. Worked 10-event example (synthetic)
Initial book: b=100.00 q^b=10; a=101.00 q^a=8.
|Ev|bid|bq|ask|aq|e^b|e^a|incr|cum|
|1|100.00|12|101.00|8|+2|0|+2|2|
|2|100.00|12|101.00|5|0|+3|+3|5|
|3|99.00|7|101.00|5|−12|0|−12|−7|
|4|99.00|7|102.00|6|0|+5|+5|−2|
|5|100.00|4|102.00|6|+4|0|+4|2|
|6|100.00|4|102.00|10|0|−4|−4|−2|
|7|100.00|9|102.00|10|+5|0|+5|3|
|8|100.00|9|101.00|7|0|−7|−7|−4|
|9|101.00|6|101.00|7|+6|0|+6|2|
|10|101.00|6|103.00|5|0|+7|+7|9|
OFI over 10 events = +9 shares. Net positive = displayed demand strengthened vs supply; does NOT guarantee price rise (hidden liquidity, trades, latency, queue position, venues, news can overwhelm).

### 3. Strategies using OFI
- Market making: adverse-selection/inventory signal; reservation price r_t = m_t + γI_t + η·OFI_t; decide quote skew, widen/reduce quotes, shift quote center. Not sufficient alone for width (need spread, vol, queue position, fill time, fees/rebates).
- Short-horizon alpha: forecast next mid-price move, uptick/downtick prob, short-horizon returns, P(bid/ask consumed), spread transitions. Basic signal z_t = OFI_{t−W:t}/σ̂. Refinements: depth normalization, price-change vs size-change split, EWMA OFI, + queue imbalance QI_t=(q^b−q^a)/(q^b+q^a), spread/vol conditioning, session/news regimes, multi-venue OFI, fast decay. Usually one feature in a microstructure model, not standalone.
- Execution: passive vs aggressive choice; buy: +OFI → waiting riskier, −OFI → post passively; OFI burst → cross spread; informs venue selection, child-order timing, participation rate, pause on liquidity shock. Objective: spread cost + market impact + delay + adverse selection; OFI hits delay + adverse-selection terms.
- Does NOT solve: full book reconstruction, trade classification, queue-position estimation, venue latency, hidden liquidity, cost modeling, OOS validation. Gameable via fleeting quotes/cancellations/spoof-like behavior/fragmentation.

### 4. Local compute on M5 Max 128GB (engineering estimates)
- Throughput: Polars vectorized 1–10M events/s; single-process Python loop 0.1–1M/s; Rust 5–30M+/s; real-time one liquid stock typically <100k events/s; several hundred symbols feasible batched.
- Stack: Python+Polars for research (parquet → sort by exchange sequence → lagged cols → conditional e_bid/e_ask → bucket). Rust for ingestion/normalization (decoder, sequence validator, Arrow/Parquet out); hybrid = Rust ingest + Polars analyze.
- RAM for 1 day L1, 1 liquid stock (2–10M quote updates): compact binary 40–80B/event → ~320MB @5M×64B; Parquet 100–500MB; Arrow 0.3–1GB; Polars intermediate 1–4GB; full direct-feed recon 2–10GB. 128GB abundant; partition by symbol/day/venue, lazy scans.
- Feed-handling caveats: dedupe quote msgs, corrections, crossed/locked, odd lots, auction/halt msgs, stale venue quotes; use exchange sequence numbers; SIP ≠ direct-feed view.

### 5. Buy vs build (indicative, NOT quotes)
- Retail/API providers: free–$50–300/mo basic; higher tiers hundreds+.
- Institutional normalized vendors: ~$500–10,000+/mo negotiated.
- Direct-feed specialists (TotalView/OpenBook): exchange + vendor fees, often thousands–tens of thousands/mo commercial.
- Academic/research vendors: project/license-based, hundreds–many thousands.
- Cloud marketplaces: ~$10–100+/TB storage; licensing dominates.
- 10-point purchasing checklist: sequence numbers? snapshots vs deltas? odd lots? corrections/cancels? SIP vs direct? timestamp source? reproducible books? commercial/non-display rights? venue coverage? queue-state reconstructable?
- Build-yourself burden = exchange licensing + ops (decode, heartbeats, gaps, halts, auctions, persistence, replay/audit), not the Mac.
- VERDICT: first OFI project → BUY normalized historical L1/L2 sample; implement OFI in Python/Polars; validate on inspected sequences; Rust only if throughput/correctness/latency demands; direct feeds only after signal survives realistic fees/latency/queue/market-impact. Paper establishes OFI as short-horizon explanatory variable, NOT that naïve OFI rule is profitable after fragmentation/costs/latency/competition.

Sources cited by model: arXiv 1011.6402 "The Price Impact of Order Book Events"; SSRN page.

---

## Q-SB1-1: Formulas + worked 10-event example — VERBATIM

### 1. Cont–Kukanov–Stoikov OFI
For quote event n: best bid price/size P_n^b, Q_n^b; best ask P_n^a, Q_n^a.
e_n = 1{P_n^b ≥ P_{n−1}^b}·Q_n^b − 1{P_n^b ≤ P_{n−1}^b}·Q_{n−1}^b − 1{P_n^a ≤ P_{n−1}^a}·Q_n^a + 1{P_n^a ≥ P_{n−1}^a}·Q_{n−1}^a
OFI_k = Σ_{n∈k} e_n. Positive OFI = displayed demand increased vs supply. Source: Cont, Kukanov, Stoikov, "The Price Impact of Order Book Events" (ssrn.com).
Parameter conventions (ILLUSTRATIVE, not documented standards): event-time 10–100 quote events; time-bar ~100ms–5min; common start: 50 events or 1-min bar; event-time preferred for illiquid names.

### 2. Best-level queue imbalance
I_n = (Q_n^b − Q_n^a)/(Q_n^b + Q_n^a) ∈ [−1,1]. "Standard top-of-book queue-imbalance statistic… closely related to the best-level supply–demand imbalance used in Cont, Kukanov, and Stoikov's order-book-event framework." (ssrn.com)
Practical smoothing (illustrative): instantaneous; 10–100 updates event-time; 100ms–1min time-bar; multi-level = first 3–10 levels (no longer the strict best-level measure).

### 3. Stoikov microprice
μ_n = (P_n^a·Q_n^b + P_n^b·Q_n^a)/(Q_n^b + Q_n^a) = m_n + (s_n/2)·I_n, with m_n midprice, s_n spread. Intuition: larger bid queue → next-price move likely up → microprice toward ask. Stoikov defines microprice generally as conditional expected future price; displayed-size formula = practical one-level estimator. Source: Stoikov, "The Micro-Price: A High Frequency Estimator of Future Prices" (ssrn.com). No lookback (recomputed per quote update); smoothed illustrative: 10–50 events or 100ms–1min.

### Worked 10-event synthetic tape (illustrative numbers, NOT market data). e_1 = 0 (no prior quote).
|Ev|Bid|Qb|Ask|Qa|e_n|Cum OFI|I_n|μ_n|
|1|99|10|101|12|0|—|−2/22=−0.0909|2198/22=99.9091|
|2|99|12|101|10|12−10−10+12=4|—|2/22=0.0909|2202/22=100.0909|
|3|100|8|101|10|8−0−10+10=8|12|−2/18=−0.1111|1818/18=101.0000|
|4|100|9|102|7|9−8−0+10=11|23|2/16=0.1250|1618/16=101.1250|
|5|100|6|102|9|MODEL SAID 6−9−9+9=−3 — SEE CORRECTION|20|−3/15=−0.2000|1512/15=100.8000|
|6|99|11|102|8|0−6−8+9=−5|15|3/19=0.1579|1914/19=100.7368|
|7|99|13|101|15|MODEL SAID 13−11−15+8=−5 — SEE CORRECTION|10|−2/28=−0.0714|2798/28=99.9286|
|8|100|5|101|14|5−0−14+15=6|16|−9/19=−0.4737|1905/19=100.2632|
|9|100|7|101|11|7−5−11+14=5|21|−4/18=−0.2222|1807/18=100.3889|
|10|100|4|102|8|4−7−0+11=8|29|−4/12=−0.3333|1208/12=100.6667|

**[OPERATOR VERIFICATION — arithmetic hand-checked, 2 model errors found and corrected:]**
- Event 5: correct e_5 = 6 − 9 − 9 + 7 = −5 (model used Q_4^a=9 instead of true 7, giving −3).
- Event 7: correct e_7 = 13 − 11 − 15 + 0 = −13 (P_7^a=101 ≥ P_6^a=102 is FALSE so ask price-effect term = 0; model wrongly added +8, giving −5).
- All other e_n, I_n, μ_n check out. CORRECT cumulative OFI: 0, 4, 12, 23, 18, 13, 0, 6, 11, 19 → **correct final OFI_{1:10} = 19 (model said 29). USE 19.**
- Model's own interpretation (valid): "The positive total indicates net displayed buying pressure under this OFI convention, even though the instantaneous queue imbalance becomes negative at several later events. OFI measures changes in displayed liquidity across events, whereas queue imbalance and microprice describe the current book state."

## Q-SB1-2: Data feed, throughput, RAM, hours, buy-vs-build — VERBATIM (key content)

**Feed:** L1 signals need consolidated BBO; venue-level depth/OFI needs direct feeds or normalized depth. Minimum for queue imbalance / 1-level microprice / quoted, effective, realized spread / trade-based VPIN: timestamped bid/ask px+size, timestamped trades w/ price/size/condition codes, symbol master, session/halt metadata, ideally exchange timestamps. Recommended: **Databento US Equities Mini (normalized MBP-1/BBO + trades)** — "proprietary blend of top-of-book direct feeds". Alternatives: Nasdaq Basic w/ NLS Plus (BBO + Nasdaq/TRF trades, NOT full national book), Polygon/Massive WS, dxFeed Nasdaq Basic, IEX TOPS (IEX only), SIP CTA/UTP for NBBO view. "You do not need Nasdaq TotalView merely to calculate one-level imbalance or microprice." MBP-1 enough for I, 1-level microprice, top-of-book OFI, quoted/effective/realized spread, VPIN. Need MBP-10/MBO/direct for: multi-level depth imbalance, queue evolution, adds/cancels/execs split, venue OFI, queue-position modeling, book reconstruction. "Databento lists Nasdaq TotalView-ITCH as a full Nasdaq order-book product and identifies MBP-10 and MBO as depth formats." TotalView = Nasdaq venue feed, not consolidated national book.
Hierarchy: consolidated microprice/QI → SIP/NBBO-style L1 or Databento Mini MBP-1/BBO; effective/realized spread → L1 quotes + consolidated trades; VPIN → consolidated trades; Nasdaq-venue OFI → TotalView-ITCH/MBP-10/MBO; cross-venue depth → multiple direct venue feeds; full reconstruction → MBO + venue sequence numbers.
Spread decomposition: Effective spread_t = 2·d_t·(P_t − M_t), d_t=±1 trade direction; Realized spread_{t,h} = 2·d_t·(P_t − M_{t+h}); quoted S_t = ask−bid. Need quotes AND trades; exclude/classify odd lots, auctions, corrected, out-of-sequence, halted prints.

**Throughput (engineering estimates, M5 Max, NOT guarantees):** Python+Polars/Arrow vectorized batches: 100k–500k events/s sustained (comfortable 50k–200k); Python row-by-row: 10k–100k (comfortable 20k–50k); Rust + Arrow/Parquet: 500k–2M (comfortable 250k–1M); Rust optimized binary: 1M+ (comfortable 500k–2M). Planning envelope for one liquid US equity: 1k–10k L1 events/s active periods (rough). "The calculations themselves are cheap. Timestamp alignment and event ordering are the difficult parts." Use int64 ticks/sizes, int64 ns timestamps, sequence; fixed-point/float64 only at output; no Python dicts/objects in hot path. Arch: Rust/vendor decoder → Arrow/IPC or compact binary queue → Polars research → Parquet partitioned by date/symbol/feed.

**RAM/storage (planning assumption: 5M normalized L1 events/liquid symbol/day, illustrative):** ~48–96 bytes/event packed → 5M×64B ≈ 305 MiB/day. 1 day / 60 days: packed binary/Arrow 0.3–0.7GB / 18–42GB; in-memory Polars w/ metadata+temps 0.5–1.5GB / 30–90GB; compressed Parquet 0.1–0.4GB / 6–24GB; Python objects/pandas object-heavy 2–8+GB / 120–480+GB. 128GB holds: 1 day 1-symbol L1; weeks of compact L1; 60 days Parquet + working tables. Stream sessions, immutable Parquet partitions, rolling state in memory only.

**Engineering hours (solo, knows Python/Polars/microstructure):** vendor connect+capture 8–20; schema+Parquet writer 8–16; timestamp normalization 12–30; quote/trade as-of join 20–50; OFI/imbalance/microprice 8–16; VPIN 16–35; spread decomposition 20–45; sessions/halts/auctions/corrections/bad-data 25–60; replay tests+invariants 20–45; monitoring/reconnects/hardening 20–50. Totals: prototype 40–70h; research-grade 120–220h; production 250–450h. "The most underestimated work is not the formulas" — exchange vs vendor timestamps, dup/corrected trades, crossed/locked, quote-trade ordering, late/out-of-sequence, odd-lot/auction prints, DST/session calendar, symbol changes, reconnect gaps. Ship a per-session data-quality report (gaps, crossed/stale quotes, timestamp inversions, unmatched trades).

**Buy vs build (INDICATIVE monthly ranges, NOT quotes):** Databento US Equities Mini ~$100–500/mo small research; Databento TotalView-ITCH ~$300–2,000+/mo; Polygon/Massive ~$200–2,000+/mo; dxFeed Nasdaq Basic ~$100–500+/mo research; dxFeed TotalView ~$500–3,000+/mo; IQFeed ~$100–300/mo before entitlements; Alpaca free–low-hundreds (verify timestamps/coverage); direct exchange feeds commonly hundreds–several $k/mo PER VENUE before connectivity/pro fees — "usually excessive for a solo researcher". Precomputed analytics: no widely adopted cheap retail product covering OFI+imbalance+microprice+VPIN+spreads w/ proper joins; Bookmap ~$50–200+ individual (visualization, not research API); quant platforms ~$500–5,000/mo (bars/factors, not event-level); institutional analytics ~$2,000–20,000+/mo; custom vendor analytics often $5,000+/mo.
**VERDICT: hybrid — BUY normalized L1 trades+BBO; BUILD OFI/QI/microprice/VPIN/spreads yourself; store raw normalized events; add depth feed only after L1 proven insufficient; vendor precomputed analytics only as cross-check.** Default: Databento Mini MBP-1/BBO+trades; TotalView-ITCH only for Nasdaq-depth research; Polars for exploration; Rust only for many symbols/venues/depth.

## Q-SB1-3: Documented predictive power + after-cost reality — VERBATIM (key content)

**Short answer:** "The literature documents real short-horizon predictability, especially for the next mid-price change, but it does not establish that a naïve long/short strategy based on OFI, queue imbalance, or microprice remains profitable after paying the spread, fees, adverse selection, latency, and market impact. The strongest documented result is not 'OFI predicts tradable returns.' It is: short-interval mid-price change ≈ depth-dependent coefficient × contemporaneous OFI."
- CKS: 50 US stocks, NYSE TAQ; Δprice ≈ linear in best-level OFI, coeff ∝ 1/depth; robust across stocks/seasonality/horizons (ssrn.com). Average in-sample explanatory **R² ≈ 65%** for short-interval mid-price changes on OFI (alphaxiv.org). CAREFUL: OFI accumulated over the SAME interval being explained → contemporaneous/explanatory, NOT known at interval start; no spread/commission/fee/latency/queue/adverse-selection/impact included. Leakage-free spec: Δm_{t,t+h} = α + β·OFI_{t−L,t} + ε — different experiment; do NOT transfer the 65%.
- Practitioner replication (dm13450.github.io): OFI sum explains interval's realized move but can't be a live signal if it includes post-decision events; standalone strategy had **poor Sharpe**, "not attractive as a self-contained trading signal". Practitioner account, crypto data, not peer-reviewed.
- Queue imbalance (Gould & Bonart, 10 liquid Nasdaq, 2014, LOBSTER, logistic on next mid-price direction): statistically significant all 10; **out-of-sample ROC-AUC ≈ 0.70–0.80 large-tick, 0.60–0.65 small-tick** (arXiv). ROC-AUC ≠ hit rate ≠ return ≠ P&L ≠ Sharpe ≠ after-cost profitability. Structural reason: predicted move often ≤ half-spread/one tick; aggressive round trip ≈ full spread + fees + slippage → significant classifier can have negative net expectancy. Cartea et al. use it in limit-order MM algos, not as directional MO trigger.
- Microprice: conditional-price/MM/execution object; NO robust universal standalone equity Sharpe or net bps-per-trade in source literature. Evidence via better next-move probs, quote placement, execution, reduced adverse selection.
- Horizon: strongest at next price-change / next few events; decays as horizon extends. 5-min imbalance regressions can be significant with tiny exploitable returns. LOB-prediction survey (MDPI): very high classification accuracies do NOT establish consistent active-trading profitability; "even state-of-the-art models do not guarantee consistent profits once the question is changed from prediction to executable trading."
- After costs: **no single accepted published benchmark** of form "OFI → X bps/trade, Y Sharpe after US equity spread/fees/impact". Literature reports R², significance, ROC-AUC, calibration, simulated MM performance, or pre-cost returns — not interchangeable. Net decomposition: E[Π_net] = E[forecast move] − spread − fees/rebates − slippage − impact − adverse selection. Aggressive entry+exit needs ≥ round-trip spread + fees + slippage + impact of forecast edge.
- Failure regimes: (1) High-vol/news — book stale/vanishes, spreads widen, depth collapses, bursts, informed MOs dominate, multi-tick gaps; Fed Board evidence: large directional imbalance especially price-amplifying when liquidity thin + vol elevated → use OFI jointly with depth+spread. Signal can be directionally right but too late. (2) Wide spreads — midpoint moves without executable profit; crossing consumes microprice edge; wide spread may = adverse selection/jump risk. (3) Small-tick/retail-dominated — AUC 0.60–0.65; displayed size less informative, hidden/midpoint liquidity, odd lots/off-exchange distort, NBBO ≠ price-discovery venue. (4) Crowded — incorporated faster, passive orders picked off, best queue less informative; edge shifts to latency/queue priority/execution. (5) Stale/manipulated/low-quality books — SIP-delayed vs direct, unnormalized venue timestamps, locked/crossed, quote-condition changes, instant-cancel displayed orders; OFI very sensitive to event-reconstruction correctness.
- **Bottom line:** standalone aggressive trigger = usually weak (expected move < cost to obtain it). As filter/MM input = defensible: OFI for adverse-selection/directional pressure, QI+microprice to skew quotes, widen/cancel when vol+spread rise, condition on depth/spread/intensity/latency, cross-vs-rest-vs-delay decisions, evaluate on executable fills + queue position not midpoint returns. Honest prior for solo US-equity op: "Predictive at the midprice level; difficult to monetize as a standalone taker signal; valuable as a conditional execution and market-making feature." Label every Sharpe/bps number before-cost / after-commissions-only / after-full-modeling — unlabeled numbers are not comparable.
