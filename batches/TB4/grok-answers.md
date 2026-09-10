# TB4 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials (account: Praveen Gupta)
- Date: 2026-09-10
- Chat: https://grok.com/c/e51222a3-… (conversation for TB4)
- Batch: TB4 — Pairs & cross-sectional extensions (T031–T040)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim via page text extraction.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: wording, numbers, formulas, and citations preserved. Two passages are truncated on Grok's page itself — captured exactly as rendered.
- All thresholds and cost figures are illustrative examples, not estimated or recommended parameters. Nothing here is a live-trading spec.

---

## Q-TB4-1 — mechanics + worked example (verbatim)

"Thresholds below are *examples*, not optimal or universal. Costs, borrow, and heat limits are stylized but in the range used in the literature and practice."

### Shared execution plumbing (all four)

- Borrow / shorting. Hard-to-borrow names: locate first; fail if no inventory. Stock-loan fee is an explicit carry on the short leg, charged on *notional* at the lender's rate; GC ~25–50 bp, specials to 10%+.
- Dividends. Short pays the dividend to the lender on ex-date; long receives it. Cash-and-carry and pairs both treat the ex-date move as a cash flow, not price alpha.
- Corporate actions. Split-adjust both legs so the formation-period price path and the live hedge ratio stay consistent. Spin-offs and mergers usually force a pair exit — the "relationship" is no longer defined on the same entity.
- Cost model (example). Round-trip equity: 2–8 bp commission + 2–10 bp half-spread + 1–5 bp impact, plus stock-loan (e.g. 30 bp–5%+ annualized on the short) for the hold. Index futures: exchange + NFA + 0.25–1 tick slippage; financing is in the basis, not a separate equity cost. Net P&L examples below use *5 bp one-way* on notional per equity leg and an explicit borrow rate where a short is held overnight.
- Sizing / heat (example). Per-pair (or per-residual) risk budget: 0.25–1.0% of NAV at 2σ of the spread. Gross book: 200–400% of NAV. Heat: sum of open |z| × dollar-risk ≤ 4–8% NAV; hard cap on simultaneous open names (e.g. 20 pairs or 50 residual names). Stop: |z| > 4–6 (example) or time stop (end of trading window).

### (A) Distance pairs + zero-crossing quality filter

Sources. Gatev–Goetzmann–Rouwenhorst (GGR, RFS 2006): 12-month formation, SSD on dividend-reinvested prices normalized to 1, top-N pairs, trade 6 months, ±2σ open, zero-cross close. GGR used convergence at 0 rather than a fixed exit. The extension: rank candidates by *number of zero-crossings* of the formation spread (proxy for mean-reversion frequency); SSD is the tie-break; drop pairs with near-zero crosses (no reversion evidence). See Do–Faff and survey work on quality filters.

Pair formation. Universe: liquid names (price, ADV, borrowable). Often same GICS industry. Formation window 252 days (example). Cumulative total-return index P_i(t) normalized to 1 at window start for each name. SSD(A,B) = Σ_t (P^A_t − P^B_t)^2. Zero-cross count: number of times S_t = P^A_t − P^B_t changes sign. Rank by zero-crossings descending, then SSD ascending. Keep pairs with ≥6 zero-crosses (example). Select top 20.

Hedge ratio. Dollar-neutral 1:1 on normalized prices (GGR). In live dollars that is (P^B_0/P^A_0) shares of A per share of B, re-normalized at the start of the trading window. No rolling OLS.

Entry / exit (examples). Spread in the trading window is re-normalized to day-1 of that window. σ_formation = std of formation spread. Open short-spread if z_t = S_t/σ_formation ≥ +2 (example); open long-spread if z_t ≤ −2 (example). Close at the next zero-cross of S_t, or at end of the 6-month window, or a stop at |z| > 4 (example). One position at a time per pair.

Execution. Simultaneous marketable limits or mid-cross both legs. Short the outperformer (borrow). Accrue dividends. Force-close on merger/spin; adjust on splits.

#### Worked 20-day example (synthetic)

Formation (not shown): 9 zero-crosses, σ_formation = 0.020, SSD small → pair accepted. Trading-window normalized prices start at 1. Hedge = $1 long / $1 short. Notional per leg = $100k. Costs 5 bp/leg/turn.

| Day | S_t | z_t | Action | Position |
|-----|------|------|--------|----------|
| 1 | 0.000 | 0.00 | flat | flat |
| 2 | 0.018 | 0.90 | — | flat |
| 3 | 0.041 | 2.05 | OPEN short A / long B | short-spread |
| 4 | 0.048 | 2.40 | hold | short-spread |
| 5 | 0.033 | 1.65 | hold | short-spread |
| 6 | 0.012 | 0.60 | hold | short-spread |
| 7 | −0.004 | −0.20 | CLOSE (zero-cross) | flat |
| 8–10 | ~0 | — | — | flat |
| 11 | −0.039 | −1.95 | wait (not yet −2) | flat |
| 12 | −0.044 | −2.20 | OPEN long A / short B | long-spread |
| 13 | −0.028 | −1.40 | hold | long-spread |
| 14 | −0.010 | −0.50 | hold | long-spread |
| 15 | 0.003 | 0.15 | CLOSE | flat |
| 16–20 | small | — | — | flat |

P&L (gross of costs). Trade 1: entered 0.041, exited 0.004. Dollar-neutral $100k/leg → spread P&L 100,000 × (0.041 + 0.004) = +$4,500. Trade 2: entered 0.044, exited 0.003 → 100,000 × 0.047 = +$4,700. Gross = +$9,200. Costs: 2 opens + 2 closes × 2 legs × 5 bp × $100k = 8 × $50 = −$400. Net ≈ +$8,800 on $200k committed capital over 20 days (illustrative only).

### (B) Kalman dynamic-hedge pairs + imbalance-bar entry

Sources. State-space / Kalman hedge ratio: treat β_t as a random-walk state, observe P^B_t = α_t + β_t P^A_t + ε_t. Standard in QuantStart, Palomar's *Portfolio Optimization*, and live pair engines. Imbalance bars (Easley–López de Prado–O'Hara / tick-rule dollar imbalance): sample when signed-volume accumulates beyond a threshold rather than by clock.

Pair formation. Same liquidity + cointegration (Engle–Granger or Johansen) screen as a cointegration pairs book. Kalman does *not* replace the formation test; it only updates β. Observation P^B_t = α_t + β_t P^A_t + ε_t. Typical example: β_0 = P^B_0/P^A_0. Spread traded: S_t = P^B_t − β_t P^A_t (some desks also subtract α_t). Recursive z: innovation / √F_t, or a 60-bar rolling z of S_t.

Entry / exit (examples). Enter when |z| ≥ 2 (example) *and* the current imbalance bar has just closed (so you do not chase a half-formed flow). Exit when |z| ≤ 0.5 (example) or β_t jumps more than a tolerance (relationship break). Re-hedge the live position whenever Δβ exceeds one tick-value of risk.

Execution. On the imbalance-bar close: lift the offer / hit the bid on both legs in β-neutral size. Borrow the short. Dividends as in (A). If β drifts, trade a delta-hedge clip on the independent leg.

#### Worked 20-day example (synthetic)

Daily bars stand in for imbalance bars (one "complete" bar per day). Y starts at 50, X at 80. Kalman β drifts 1.58 → 1.64. Rolling σ = 0.80 (price units). Notional: short $100k of Y vs long 1×β of X (~$100k × β/β? keep $100k on Y).

| Day | S_t | z_t | β_t | Action |
|-----|------|------|------|--------|
| 1 | 0.2 | 0.25 | 1.58 | — |
| 2 | 1.1 | 1.38 | 1.59 | — |
| 3 | 1.7 | 2.13 | 1.59 | OPEN short Y / long βX (imb-bar close) |
| 4 | 1.9 | 2.38 | 1.60 | hold; tiny β rehedge |
| 5 | 1.2 | 1.50 | 1.60 | — |
| 6 | 0.5 | 0.63 | 1.61 | — |
| 7 | 0.3 | 0.38 | 1.61 | CLOSE ($[truncated in render]) |
| 8–11 | ~0 | — | 1.62 | — |
| 12 | −1.8 | −2.25 | 1.63 | OPEN long Y / short βX |
| 13 | −1.4 | −1.75 | 1.63 | — |
| 14 | −0.6 | −0.75 | 1.64 | — |
| 15 | −0.2 | −0.25 | 1.64 | CLOSE |
| 16–20 | noise | — | 1.64 | — |

P&L. Trade 1: +1.4 in spread-points against the short-spread. On $100k Y (~1,250 sh Y, ~1,980 sh X): ≈ +$1,750, plus a small β-rehedge P&L (~$40). Trade 2: −1.6 in favor of the long-spread → ≈ +$2,000. Gross ≈ +$3,790. Costs: 2 RT × 2 legs × 5 bp × ~$100k + 1 small rehedge ≈ −$220. Net ≈ +$3,570.

### (C) Index futures cash-and-carry

Sources. Textbook cost-of-carry: F_fair = S e^{(r−q)T} with discrete dividends subtracted PV'd. Cash-and-carry: buy basket (or ETF), finance, short rich futures.

"Pair" formation. Not a stock pair. The two legs are (i) the replicating cash basket / ETF and (ii) the listed index future. Monitor basis = F_market − F_fair net of a haircut for execution + borrow + tracking: enter only if basis > costs + basis-risk buffer (example buffer: 5–15 index points on ES, or 8–20 bp of spot).

Hedge ratio. Contracts = cash notional / (F × multiplier), so dollar beta ≈ 1. ETF substitute: use ETF NAV and published creation basket; residual tracking error is part of the haircut.

Entry / exit (examples). Enter cash-and-carry if F_mkt − F_fair > buffer. Unwind at expiry (cash settlement vs sell basket) or when the richness collapses inside costs. No z-score; this is a basis vs fair trigger.

Execution. Cash-and-carry: borrow cash (GC / SOFR + spread), buy basket (or create ETF), sell futures. Collect dividends; finance accrual is the carry. Pay stock-borrow if you used a short ETF instead of a long basket. Reverse: locate the basket, short it, invest cash, buy futures. Corporate actions inside the index are handled by the futures' own adjustment rules; the cash basket tracks the index.

#### Worked arithmetic example (synthetic)

Spot index S = 5,000. Multiplier $50 (ES-like). T = 90/365 = 0.2466 yr. Financing r = 5.00%. Dividend yield q = 1.4%. Stock-borrow on the cash ETF used as basket proxy: none (you are *long* the ETF here, so borrow = 0 on the long; we put borrow on a *reverse* variant below).

Fair (continuous): F_fair = 5000 × e^{(0.05 − 0.014)×0.2466} = 5000 × e^{0.00888} = 5,044.5. Market future F_mkt = 5,062 → richness = 17.5 pts.

Cash-and-carry (long cash, short future). Buy $10,000,000 of ETF / basket at 5,000. Contracts = 10,000,000 / (5062 × 50) = 39.51 → 40 contracts.

Financing 90d: 10,000,000 × 0.05 × 90/365 = $123,288. Dividends received: 10,000,000 × 0.014 × 90/365 = $34,521. Net carry paid = $88,767.

Convergence arithmetic (8.9 index pts of the 17.5 are locked by carry math; the rest is the 5,000→expiry index move, common to both legs; wait — scale: 10mm / 5000 = 2,000 index units; 2,000 × 8.9 × $1? Better in dollars:)

At expiry assume S_T = 5,080 (cash-settled). ETF P&L: 10,000,000 × 80/5000 = $160,000 + dividends $34,521. Futures P&L: short 40 × $50 × (5080−5062) = −$36,000. Financing −$123,288. Net = 160,000 + 34,521 − 36,000 − 123,288 = +$35,233. That is the locked richness: 17.5 pts × $50 × 40 = $35,000, plus a 0.5-pt contract-rounding residual. Costs (2 bp cash + 0.5 tick futures) ≈ −$3,000. Net ≈ +$32k on $10mm, 90 days.

Same trade with an explicit borrow fee (reverse cash-and-carry, futures cheap). Suppose instead F_mkt = 5,028 vs fair 5,044.5 (cheap 16.5 pts). Short $10mm ETF, pay borrow 0.80%: 10,000,000 × 0.008 × 90/365 = $19,726. You *receive* financing on the short-sale proceeds at 5%. Net: locked cheapness minus borrow. Carry received, dividends you *owe*, futures/cash convergence as above → gross lock ≈ $35k − $19.7k = $15.3k before execution costs. Borrow can kill reverse C&C when the special is rich.

### (D) PCA eigenportfolio residual reversal

Sources. Avellaneda–Lee, "Statistical Arbitrage in the U.S. Equities Market," *Quantitative Finance* 2010. PCA on the correlation matrix of returns; first K eigenportfolios are factors; residual of each name vs those factors is an OU process; trade the *s-score*. Example thresholds from the paper / ArbitrageLab: open |s| > 1.25, close |s| < 0.50, minimum half-life ~8.4 (half-life ≲ 30 days). Window: 252d correlation, 60d residual.

"Pair" formation. There is no pair. Universe of N names.
1. Rolling correlation matrix, eigendecompose. Keep K PCs (example: 15, or enough for ~50–55% variance).
2. Eigenportfolio k: weights w^k = v^k / Σ_i v^k_i (weights sum to 1).
3. For each stock i, OLS R_{i,t} = α_i + Σ_k β^k_i F^k_t + ε_{i,t} on the last 60 days.
4. Fit OU to ε_{i,t}: dε = −κ ε dt + σ dW. Require half-life ln2/κ ≲ 30d and κ large enough.

Hedge ratio. The trade is stock vs its eigenportfolio hedge: short β^k_i units of dollar weights w^k_i on each eigenportfolio k (implemented as the corresponding basket of the N names). Net market / PC exposure ≈ 0.

Entry / exit (examples, Avellaneda–Lee). Open long residual if s < −1.25; close long if s > −0.50. Open short residual if s > +1.25; close short if s < +0.75 (paper uses a slightly asymmetric close). Size: equal residual-risk (or equal dollar) across open names; heat cap on sum of open |s|.

Execution. Simultaneous stock + hedge-basket (or swap the basket for futures + sector ETFs as a practical factor proxy). Borrow shorts; corporate actions hit both sides through total returns.

#### Worked 3-asset residual example (synthetic)

Assets A, B, C. One factor (the first PC ≈ equal-risk market).

Standardized returns over a 60-day window, one-factor betas:

| Asset | β vs PC1 | latest residual ε | OU mean | OU σ | s-score |
|-------|-----------|-------------------|---------|------|---------|
| A | 1.10 | −0.042 | 0.000 | 0.028 | −1.50 |
| B | 0.95 | +0.008 | 0.001 | 0.025 | +0.28 |
| C | 0.90 | +0.038 | 0.000 | 0.026 | +1.46 |

Rules (examples): A triggers long residual (|−1.50| > 1.25); C triggers short residual (+1.46 > 1.25); B flat.

Trade (unit residual risk). Long $1 of A, short β_A = 1.10 units of the eigenportfolio. Short $1 of C, long β_C = 0.90 units. Net eigenportfolio ≈ −1.10 + 0.90 = −0.20 (small; optionally flatten). In 3-asset space the eigenportfolio is roughly equal-weight. Suppose equal, w = (1/3, 1/3, 1/3). Then:
- Long-A book: +1.00 A, −0.367 each of A/B/C.
- Short-C book: −1.00 C, +0.300 each of A/B/C.
- Combined: +0.933 A, −0.067 B, −1.067 C (almost A vs C, B residual hedge).

Next-day idiosyncratic moves: ε_A reverts from −0.042 to −0.010 (+3.2 bp extra vs factor); ε_C from +0.038 to +0.012 (−2.6 bp). On $1m per residual: +$3,200 on A, +$2,600 on C, residual B bleed −$100. Gross ≈ +$5,700. Costs: 6 name-sleeves × 5 bp × ~$0.3–1.0m average ≈ −$1,200. Net ≈ +$4,500 for one-day convergence of two residuals (illustrative).

### Sources (primary)

- Gatev, Goetzmann, Rouwenhorst, "Pairs Trading: Performance of a Relative-Value Arbitrage Rule," RFS 2006.
- Do & Faff / survey literature on zero-crossing as a formation quality filter.
- Kalman hedge-ratio pairs: state-space OLS (QuantStart; Palomar ch. 15.6).
- Cost-of-carry / cash-and-carry: standard index-futures no-arbitrage (CFA / futures texts).
- Avellaneda & Lee, "Statistical Arbitrage in the U.S. Equities Market," *Quantitative Finance* 2010 (PCA residuals, s-score thresholds).

"All z / s thresholds, cuts, 5 bp costs, and 20-day paths are *examples on synthetic data*, not live parameters."

---

## Q-TB4-2 — infra + local build + buy vs build (verbatim)

"A 128GB M5 Max is *enough compute* for this book if it stays *daily / EOD*, not tick. The budget is dominated by *borrow data + corporate-action hygiene + engineering time*, not the Mac."

### 1. What "production" actually is on this box

| Job | Cadence | What it does |
|-----|---------|--------------|
| Universe + corp-action adjust | Nightly after 18:00 ET | Split/div/spin maps, PERMNO-style IDs, total-return series |
| Pair screen | Nightly | Distance + EG/Johansen + copula on ~2,000 names |
| Kalman book | Daily close (or hourly if you later add bars) | Update on the live 20–80 pairs |
| Borrow / HTB / locates | Daily 16:30–18:30 ET | Fee, utilization, availability → veto or resize |
| Div / specials calendar | Daily | Ex-date P&L and fair-spread shift |
| Futures basis | Intraday snapshot is enough at first | ES/NQ (or the index you carry) vs ETF + SOFR + forecast divs |
| Risk / heat | Continuous, cheap | Open z, gross, borrow $ |

"This is a *research + signal + risk* machine. Execution, locates, and official P&L live at the prime / EMS."

### 2. Data stack and indicative pricing (2026)

"All figures are *order-of-magnitude commercial quotes*, not a bid. Academic WRDS/CRSP is usually *not* licensable for a live book."

#### Must-have

| Feed | Why | Indicative $ / year | Notes |
|------|-----|---------------------|-------|
| Survivorship-free US EOD + total return + splits/divs | Formation + P&L | $2k–$15k | Norgate / Sharadar-class EOD is the cheap correct choice. Tiingo commercial ~$0.5–1k is usable for prototypes, not production |
| Point-in-time GICS / sector | Industry distance filter | often bundled | Don't screen 2,000 names without industry |
| Corporate actions + dividend forecasts | Adjust + cash-and-carry | $1k–$8k standalone, or inside EOD vendor | Specials and spin-offs are where homemade adjusters silently blow up |
| Index futures EOD + SOFR / GC | Basis | $0–$3k | CME delayed + FRED SOFR is enough to monitor. Live ES tape is extra |
| ETF creation basket / official index div points | Cash-and-carry fair | $0–$5k | SPY/IVV holdings + index dividend points |

#### The expensive line: borrow

"This is the item people under-budget."

| Source | What you get | Indicative $ / year | Fit |
|--------|--------------|---------------------|-----|
| Your prime's stock-loan file | Your fee, inventory, recalls | $0 incremental if you already pay PB | Best for live trading. Bad for historical research and for names you don't yet short |
| IBKR SL availability (retail scrape / IBorrowDesk-class) | One broker's indicative fee | $0 | Fine as a veto flag, not a cost model |
| Ortex / Fintel-class | SI + some borrow | $2k–$15k | Research-grade, not a locate |
| Markit / S&P Securities Finance, FIS Astec, DataLend | Indicative + average fee, utilization, inventory, 15y history | $30k–$150k+ | This is the real research dataset. Quotes are relationship- and contributor-status dependent. "Borrow data cost!" — yes, this is the six-figure line item if you want history |

"Plan the book as if institutional borrow history is $50k–$100k/yr *unless* you accept PB-only live fees and no serious HTB backtest. That single feed can exceed every other line combined."

#### Nice-to-have, not day-1

| Feed | $ / year |
|------|----------|
| Minute bars (imbalance-bar research) | $2k–$25k (Databento Standard–Plus territory) |
| Bloomberg / Refinitiv terminal | $20k–$32k per seat — buy only if you need DIVS + FA + a human desk |
| Barra / Axioma risk model | $150k–$600k+ entry — overkill for a 20–80 pair book |

Year-1 data cash outlay (realistic bands):
- Lean live book (EOD + PB borrow + public futures): *$5k–$20k*
- Research-grade book (EOD + corp-act + Markit/Astec/DataLend): *$50k–$130k*
- Same + minute bars + terminal: *$80k–$170k*

### 3. Does 128GB M5 Max actually hold the screen?

"Yes for daily 2,000 names. Bandwidth is ~460–614 GB/s; 18 CPU cores; unified 128GB. The constraint is *algorithmic pair count*, not RAM."

Universe after liquidity / price / borrowable filters: ~2,000 → ~2 million unordered pairs. You *never* cointegrate all of them.

Sane pipeline (this is what should run at 19:00):
1. Liquidity + industry buckets (e.g. 24 GICS industries × ~80 names).
2. Distance / correlation pre-rank inside bucket → keep ~20–50k candidates.
3. Engle–Granger or Johansen on those only.
4. Copula (Clayton/SJC on ranks or residuals) on the survivors (~1–5k).
5. Zero-cross / half-life / β-stability gates → 50–200 tradeable pairs.
6. Kalman only on the *live* book (20–80 pairs), not the universe.

Compute time on M5 Max (EOD, vectorized NumPy/Polars + statsmodels / arch, 18 threads)

| Step | Wall clock (indicative) | RAM |
|------|------------------------|-----|
| Load 2,000 × 5y daily + adjust | 5–20 s | 2–6 GB |
| Industry SSD / corr pre-screen | 1–4 min | 8–20 GB |
| 20–50k EG tests | 5–20 min | 4–10 GB |
| Johansen on a few thousand | 5–15 min | similar |
| Copula MLE on 1–5k | 10–40 min | 4–8 GB |
| Kalman update 80 pairs × 1 day | < 1 s | trivial |
| Full Kalman rebuild 80 pairs × 2y | 10–60 s | < 1 GB |
| Basis + borrow join | seconds | tiny |

"Nightly batch: ~20–60 minutes, comfortably inside the close→open window. You will *not* fill 128GB unless you materialize the 2M-pair distance matrix as a dense float64 (that is ~32 GB plus copies — don't). Use blocked / industry-chunked distance. Minute-bar Kalman + copulas on 2,000 names does *not* belong on this machine as a nightly full universe job. That is a cloud burst or a much tighter candidate list."

### 4. Engineering hours (the other real cost)

"Assume one strong quant-engineer who already knows the strategies."

| Workstream | Hours | Notes |
|------------|-------|-------|
| Data lake: ingest, ID map, split/div adjust, delist | 80–160 | Highest defect rate if rushed |
| Distance + coint + copula screen + tests | 80–150 | Include unit tests against GGR / synthetic OU |
| Kalman live state + rehedge + z | 40–80 | Easy math, annoying state |
| Borrow / locate / HTB veto + cost in backtest | 40–80 | Join keys are messy |
| Corp-act + dividend event engine | 40–80 | |
| Futures fair-value + richness monitor | 20–40 | |
| Portfolio heat, stops, blotter, logging | 40–80 | |
| Paper → first live (EMS/FIX or IBKR/PB API) | 80–160 | Not on the Mac's critical path, but it's the book |
| Year-1 build | 420–830 h | ~3–5 months one person, or 6–10 weeks two people |
| Steady-state ops / year | 150–300 h | vendor breaks, symbol changes, new HTB regimes, parameter rot |

"At a fully loaded $150–250/h internal cost that is *$60k–$200k* to build and *$25k–$75k/yr* to keep. Hardware already owned (128GB M5 Max MBP/Studio): treat as *$0 incremental*. A Studio-class desk + UPS + local ZFS backup is a few thousand if you want the box always-on."

### 5. Year-1 total cost of ownership (build)

| | Lean live | Research-grade |
|---|---|---|
| Data | $8–20k | $60–130k |
| Eng hours (build) | $60–120k | $100–200k |
| Hardware incremental | $0–4k | $0–4k |
| EMS / PB / locates | existing relationship | existing |
| Year-1 | ~$70–150k | ~$160–330k |
| Year-2+ run-rate | $15–40k data + 0.2–0.4 FTE | $60–140k data + 0.3–0.5 FTE |

"Capacity of the book this stack can honestly support: *20–80 simultaneous pairs*, not a 500-name multi-strat."

### 6. Buy vs build

| Option | What you actually get | $ | Verdict for this operation |
|--------|----------------------|---|---------------------------|
| Build on the M5 Max | Your formation rules, your Kalman, your cost model, your IP | TCO above | Build the signal + cost engine. That is the edge. |
| Prime-broker pair / program-trade analytics | Basket locate, pair algo, TCA, some spread tools | bundled in PB ticket | Buy execution and locates. Do not buy the screen. PB tools optimize their flow, not GGR/Kalman/copula with your filters. |
| Vendor "stat-arb screens" (QuantConnect / retail pair scanners / some OMS modules) | Pre-ranked pairs, generic 2σ rules | $0–$20k | Fine for sanity checks. Not a production book: no PIT borrow, weak corp-act, no your-Kalman. |
| Barra / Axioma / Bloomberg PORT | Factor residual risk | $150k–$1M+ | Buy later if the book becomes a 300-name residual book (strategy D at scale). Not for 50 pairs. |
| Robot-Wealth / shared research APIs | Someone else's monthly universe | subscription | Useful as a second opinion, not as the production formation. |

- "Build the formation, Kalman, cost, heat on the Mac. The machine is not the bottleneck."
- "*Rent* (or take from PB): locates, live borrow for names you trade, EMS pair-legging, official P&L."
- "Buy institutional securities-finance data only if you need a historically honest HTB backtest. If you will only short GC names your PB already shows a live fee on, skip it."
- "Don't buy a risk-model suite or a Bloomberg seat 'for pairs.' A Sharadar/Norgate-class EOD file plus the PB stack is enough."
- "The decision that actually changes P&L is whether you pay five figures vs six for borrow history — not whether the screen runs in 12 minutes or 40 on the M5 Max."

---

## Q-TB4-3 — success ratios, after-cost efficacy, failure modes (verbatim)

"After-cost honesty first: several of these sleeves looked like 8–12% annualized in the original papers and are now either flat, cost-eaten, or reserved to balance-sheet owners. Numbers below are from the papers, not vendor decks."

### 1. Gatev distance pairs — original vs post-2000 after costs

"Original (GGR 2006), CRSP 1962–2002. Self-financing top-20 pairs, 12m formation / 6m trade, 2σ open, close at zero-cross or window end. Annualized excess returns up to ~11% on committed capital before a conservative cost haircut; authors argued profits survived those costs. One-day delayed execution already in the design."

"Decay (Do–Faff 2010, FAJ; sample through mid-2009). Same rule, employed-capital monthly excess, top-20, 1-day delay, before full modern costs:
| Period | Mean monthly excess |
|--------|---------------------|
| 1962–1988 | 0.86% |
| 1989–2002 | 0.37% (~GGR's 0.38%) |
| 2003–2009 | 0.24% |

That is a ~70% drop from the first era to the last. Do–Faff attribute ~70% of the drop to worse convergence (pairs that used to be substitutes stop being substitutes), not just 'more hedge funds.' Non-convergent pairs rose from ~26% (pre-1989) to ~42% (2003–08); multiple-round-trip pairs fell from ~42% to ~21%."

"After costs (Do–Faff 2012, JFR). Commissions + impact + short fees, 1963–2009: baseline GGR is largely unprofitable after 2002. Industry + zero-cross filters leave about 30 bp/month risk-adjusted on the best-matched industry pairs over the full sample — and both pairs and short-term industry reversal are 'largely unprofitable after 2002.'"

"Later replication through 2020 (independent GGR/Do–Faff clone): post-2009 equity curve mostly flat even before costs; pandemic spike did not restore significance."

"Capacity / crowding / failure. Capacity is the liquid mid-cap same-industry book, not mega-cap (spreads too tight) and not micro-cap (borrow + impact). Crowding shows up as more non-convergence, not as a simple 'HF dummy.' Failure regimes: structural breaks (merger, spin, index add/delete, one-leg bankruptcy), 2007-style unwind where every residual-reversion book dumps the same longs, and any week when short-loan specials jump. The strategy still spikes in prolonged stress (2000–02, 2007–09) when substitution breaks and then snaps back — that is the remaining economic rationale, not a 11% annuity."

### 2. Kalman / dynamic hedge vs static pairs

"There is no GGR-scale CRSP paper that says 'Kalman adds X Sharpe after costs on 2,000 names.' What exists is mixed, and the honest papers are not kind to turnover."

- "Palomar (*Portfolio Optimization* §15.6), EWA–EWC style examples: Kalman spreads look more stationary; gross equity and drawdowns beat 2-year rolling OLS. He flags the catch: if process-noise Q is too large, spread variance collapses and edge dies in costs."
- "Baskaran (SSRN 2026), walk-forward, 28 bp RT costs, ~2.3-day Kalman holds: all branches negative net Sharpe. Static OLS fold-mean Sharpe −0.16 vs Kalman −2.08 (OLS wins 12/14 folds). Kalman turnover +54% (932 vs 607 trades). Kalman does cut max DD ~71% (−0.31% vs −1.07%). Cost breakeven they estimate: 6–7 bp one-way. HMM gate cuts trades 45% and DD another 30%."
- "Practitioner OOS on a cointegrated bank pair (same z-rule, full RT costs on both legs): static net OOS Sharpe +0.76 (41 trades) vs Kalman −1.50 (78 trades). Better description, worse trade."

"Documented 'improvement' is risk, not return. Kalman reduces stale-β blow-ups when the relationship drifts. It does not have a clean after-cost return premium once holds shrink to a few days. Model risk: δ/Q, R selection is in-sample overfitting; a twitchy β is a commission pump."

"Capacity / failure. Same pair universe as distance/coint. Failure: β jump on a corp-act you didn't catch; filter lag in a gap; over-trading through a special. Use Kalman as a hedge and stop, not as a reason to cut the hold from 10 days to 2."

### 3. Copula pairs — edge vs linear methods, and model risk

"Two literatures talk past each other."

"Small / selected samples (Liew–Wu 2013; Xie–Liew–Wu–Zou 2016): copulas (Clayton / Gumbel / Student-t) produce more signals and higher backtest P&L than distance or cointegration on a handful of pairs / 89 utilities, because they drop the linear-Gaussian assumption and use tail / mispricing-index rules."

"Market-wide, costed comparison — Rad–Low–Faff 2016, US CRSP 1962–2014, time-varying costs:
| Method | Gross mo. excess | Net mo. excess |
|--------|------------------|----------------|
| Distance | 91 bp | 38 bp |
| Cointegration | 85 bp | 33 bp |
| Copula | 43 bp | 5 bp |

So on the full US tape, copula loses to linear methods after costs. Authors note: from 2009, distance/coint opportunity count collapses; copula trade frequency stays steadier; copula hurts less on non-convergent trades and in downturns (tail dependence is the point). Mixed-copula work on S&P names (Silva et al. 2023) later claims mixed-copula beats distance on that narrower universe, with and without costs — a different sample and a different copula recipe."

"Model-risk caveats (this is the operational fact). Family choice (Clayton vs t vs SJC vs mixture), AND vs OR open/close, CMPI reset, and rolling-window refits all move the trade set. Rad-style results say the extra parameters buy drawdown shape, not a bigger net mean, once you pay for the extra opens. Copula does not fix a bad pair; it just times a bad pair with more confidence."

"Capacity / failure. Same as other pair books, plus estimation fragility on short windows and regime shifts in tail dependence (2015–16, COVID open, 2022 rates). Crowding is lower than vanilla 2σ distance because fewer desks run the same copula; that is not the same as 'more alpha.'"

### 4. Cash-and-carry (equity index and the cousin Treasury basis)

"Textbook: F_fair = S e^{(r−q)T}. Trade only the gap versus your financing and your borrow, not SOFR minus index yield."

"Documented economics. Hazelkorn–Moskowitz–Vasudevan-type work on the equity futures–cash basis: the gap is a financing/borrow wedge plus demand for futures vs cash. They estimate a ~5–6% annual premium attached to persistent imbalances, and simple basis-timing / cross-sectional basis strategies with Sharpe ~0.6–0.9 in futures (lower in cash). Dealer futures inventory is the other side. This is not a small-account 20 bp lock that you scale to $10mm without a GC book."

"Capital and borrow constraints for small accounts — these are binding, not footnotes.
- Cash-and-carry needs cash or portfolio margin to buy the basket/ETF and futures margin on the short. Reverse C&C needs a locate on the whole basket or the ETF.
- Creation of a true index basket is a dealer job (500 names, cash-in-lieu, official settlement). A small account substitutes SPY/IVV + ES, and then pays ETF spread + tracking + borrow on the ETF if reversed.
- Stock-loan on the ETF or on residual names can be 80–200+ bp and wipes a 15-point richness on a 90-day future (see the arithmetic in the previous note).
- Balance-sheet / repo is the institutional constraint. The 2020 Treasury basis unwind is the cautionary analogue: 10–20× levered cash-futures books were run off when repo and PB limits snapped; equity C&C is the same machine at lower leverage."

"Who earns it. Index-arb desks at dealers, APs who already own the basket, and multi-strat funds with cheap GC. A 128GB-Mac book monitors richness and only lifts when the gap exceeds retail all-in costs (often 8–20+ index points on ES after two-sided ETF spread). Capacity at that threshold is tiny; inside 2–5 points the tape belongs to the dealers."

"Failure. Dividend forecast error into expiry, wrong funding rate (SOFR ≠ your PB), hard-to-borrow names inside the basket, and any day futures and cash gap because everyone wants the same hedge (March 2020)."

### 5. ETF / basket arb — who captures it, creation-unit problem

"Mechanism. Authorized participants create when the ETF is rich vs the basket (deliver stocks, take ETF shares, sell ETF) and redeem when cheap. Creation units are typically 25k–100k shares (SPY historically 50k; many funds 10k–50k). That is $2–$30mm+ of notional per print on a large US equity ETF, plus a fixed create/redeem fee."

"Who captures it. APs and wholesale market-makers (banks + the Optiver / Jane Street / Citadel Securities class). They cross both the ETF spread and the basket spread, then flatten in the primary market overnight. Secondary-market traders without AP status can only do a risky long-ETF / short-basket (or vice versa) and hope an AP closes the gap — you eat borrow and overnight tracking. Empirical work treats AP primary-market flow as the force that removes the mispricing; it is not a residual you harvest from a cash account."

"Creation-unit minimum problem for a small book. You cannot create 47 shares of SPY. You either:
- trade the secondary market and compete with the AP's bid/ask (edge after costs ≈ 0 on liquid US equity ETFs most days), or
- do a partial basket and wear residual risk that is larger than the premium."

"Premia on liquid US equity ETFs are usually basis points, inside the two-sided cost of a 500-name basket. Dislocations that do pay (March 2020 bond ETFs, international funds in a holiday, thin thematic ETFs) are either AP-only or come with gap risk that is not 'arb.'"

"Capacity. Unlimited in theory on liquid underlyings (primary market manufactures shares). In practice the constraint is AP balance sheet and locate, not your Mac. A non-AP account's honest capacity on this sleeve is near zero."

### 6. Sector momentum + residual reversal

"Two different signals, often stacked."

"Residual reversal (Avellaneda–Lee 2010). PCA or sector-ETF residual → OU → s-score. After 5 bp-style costs:
| Sleeve | Period | After-cost Sharpe |
|--------|--------|-------------------|
| PCA | 1997–2007 | 1.44 |
| PCA | 2003–2007 | 1.1 |
| Sector ETF residuals | 1997–2007 | 1.1 |
| ETF residuals + volume/trading-time | 2003–2007 | 1.51 |

They document the Aug 2007 quant unwind in the same paper (with Khandani–Lo): crowded residual-reversion books lost together when everyone de-levered. Later student replications on 2013–16 S&P names get Sharpe ~0.6 with ~50% of gross eaten by 5 bp costs and survivorship holes. Combining AL s-scores with Black–Litterman (ALBL, 2001–2010) raised net Sharpe from 0.84 → 1.23 in one study — still a 2000s sample."

"Sector / industry momentum is the opposite sign at a higher frequency horizon: Grinblatt–Titman / Moskowitz–Grinblatt industry momentum — last 6–12 month industry winners continue. It is a cross-section of industries, not a pair. Empirically it is more robust than single-stock momentum after costs because you trade ~20–50 industry portfolios or sector ETFs instead of 2,000 names. It fails in sharp rotations (Mar 2009, Nov 2020, 2022 factor flip) and when used as a residual-reversion hedge that is itself crowded."

"How desks combine them (the honest version). Long/short residual book orthogonalized to sector momentum (or to the first PC + a 12-1 industry momentum factor) so you are not accidentally short last quarter's winning industry. Avellaneda's own ETF-residual book is already a sector-neutral residual reversal; adding momentum of the sector as a separate overlay is a second bet."

"Capacity / crowding / failure. Residual reversal capacity is the liquid US mid/large book, tens to low hundreds of millions before impact if you insist on 5 bp. Crowding is the binding risk: Aug 2007, Q1 2018 vol, Mar 2020. Failure regimes: factor-model miss (too few PCs → residual is still market; too many PCs → you trade noise and pay costs — Avellaneda notes 75% variance cutoffs lose money), borrow spikes on the short residual names, and any week when 'idiosyncratic' is actually an unmodeled factor (meme, meme-adjacent retail, China ADR, AI-basket)."

### Cross-sleeve after-cost scorecard (use this, not the original abstracts)

| Sleeve | After-cost status in the literature | Capacity for a small PB book | Main failure |
|--------|--------------------------------------|------------------------------|--------------|
| GGR distance | Real pre-1990; ~30 bp/mo only with industry+zero-cross over long samples; flat after ~2002–09 once costs are honest | $10–50mm if you stay GC, same-industry | Non-convergence, 2007 unwind |
| Kalman vs static | Risk improvement; return often worse after costs unless one-way ≤6–7 bp | Same as pairs | Over-trading, β jumps |
| Copula | Full-tape net ~5 bp/mo (Rad); selected-sample papers look better | Same as pairs | Family / threshold overfitting |
| Equity C&C | Dealers + funds with GC; 5–6% "premium" is a financing factor, not a retail lock | Small unless you are an AP/dealer | Funding, dividend miss, 2020-style basis blowout |
| ETF create/redeem | AP franchise | Effectively none without a unit | You are not an AP |
| Residual reversal | Sharpe 1.4 → 0.9 already inside the original paper; later samples lower | Low hundreds of $mm before you are the 2007 tape | Crowded de-lever, factor miss |

"The only sleeves that still have a plausible small-account after-cost role on a 128GB M5 Max are: tight, industry-filtered, low-turnover pairs (distance or slow Kalman, not copula-on-everything), residual reversal on a short list with a hard heat cap, and basis monitoring that you almost never trade. ETF primary-market arb and levered cash-and-carry are not that book."

---

## QC notes (orchestrator)

1. Q1(C): Grok's contract math is inconsistent — "Contracts = 10,000,000 / (5062 × 50) = 39.51" does not reconcile with the $10mm/5,000 = 40-contracts scale, and the parenthetical aside ("wait — scale: 10mm / 5000 = 2,000 index units; 2,000 × 8.9 × $1? Better in dollars:)") reads like internal deliberation leaked into the answer. The claimed "0.5-pt contract-rounding residual" doesn't reconcile with the P&L residual ($35,233 − $35,000 = $233 ≈ 0.117 pts on 40 contracts).
2. Q1(B): the day-7 table cell was truncated on the page ("CLOSE ($$") — captured exactly as rendered. Per-trade P&L inputs (+1.4 spread-points → ~$1,750 on 1,250 sh Y) asserted without intermediate price arithmetic.
3. Q1(D): arithmetic is consistent (3,200+2,600−100 = 5,700 gross; 5,700−1,200 = 4,500 net), but the −$100 "B bleed" has no derivation from the stated B residual (+0.008) or the −0.067 B combined weight.
4. Q3: "Baskaran (SSRN 2026)" is dated after the current date — citation plausibility needs verification before chapter adoption.
5. Key sourced claims are research leads, not verified facts: GGR 2006 (up to ~11% ann. excess); Do–Faff 2010 (0.86%→0.37%→0.24%/mo decay); Do–Faff 2012 (unprofitable after 2002); Rad–Low–Faff 2016 (copula net 5 bp/mo vs distance 38 bp/mo); Avellaneda–Lee 2010 (PCA residual after-cost Sharpe 1.44→0.9); Lou–Polk–Skouras 2019; Hazelkorn–Moskowitz–Vasudevan (basis premium ~5–6%); Grinblatt–Titman / Moskowitz–Grinblatt (industry momentum). Vendor prices: indicative — verify before budgeting.

---

## Source list (only papers actually used)

- Gatev, E., Goetzmann, W. and Rouwenhorst, G. (2006), "Pairs Trading: Performance of a Relative-Value Arbitrage Rule," Review of Financial Studies.
- Do, B. and Faff, R. (2010), "Does Simple Pairs Trading Still Work?" Financial Analysts Journal.
- Do, B. and Faff, R. (2012), "On the Performance of Varying Measures of Pairs Trading Strategy," Journal of Financial Research.
- Rad, H., Low, R.K.Y. and Faff, R. (2016), "The Profitability of Pairs Trading Strategies: Distance, Cointegration and Copula Methods," JBF.
- Liew, R. and Wu, Y. (2013), "Pairs trading: A copula approach."
- Xie, W., Liew, R.Q., Wu, Y. and Zou, A. (2016), "Pairs Trading with Copulas."
- Silva, C.L., et al. (2023), mixed-copula pairs on S&P names.
- Palomar, D.P. (2016), *Portfolio Optimization* (Kalman hedge ratios).
- Avellaneda, M. and Lee, J.-H. (2010), "Statistical Arbitrage in the U.S. Equities Market," Quantitative Finance.
- Khandani, A.E. and Lo, A.W. (2007), "What Happened to the Quants in August 2007?"
- Grinblatt, M. and Titman, S. (1989), "Mutual Fund Performance: An Analysis of Quarterly Portfolio Holdings."
- Moskowitz, T.J. and Grinblatt, M. (1999), "Do Industries Explain Momentum?" Journal of Finance.
- Everything not attributed to one of the above — thresholds, cost figures, worked-example values — is illustrative.
