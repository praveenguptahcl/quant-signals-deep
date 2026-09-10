# 200-Stage Deep-Dive Plan — planner spec (v1)

**Goal.** One living document `~/workspace/quant-signals-deep/MASTER.md` containing 200 chapters:
Stages 1–100 = signal deep dives **S001–S100** (mapped 1:1 to signals 1–100 in
`~/workspace/quant-intraday-signals/top-100-quant-signals-report.md`).
Stages 101–200 = strategy deep dives **T001–T100** (each strategy composes ≥2 signals from that report).

**ID conventions (mandatory for all workers).**
- Signal *n* (report numbering 1–100) → chapter ID `S` + zero-padded 3 digits: signal 1 → `S001`, signal 100 → `S100`.
- Strategy *m* (T001–T100, defined below) → chapter ID `T001` … `T100`.
- Stage number: `k/200` with k = signal index (1–100) or 100 + strategy index (101–200).
- Chapter files land at `batches/<BATCH>/S###.md` / `batches/<BATCH>/T###.md`; images at
  `images/S###_example.png` / `images/T###_example.png`.
- Cross-references: signal chapters link to strategies with `T###`; strategy chapters link to
  signals with `S###`. IDs are stable — never renumber.

**Source of truth.** The report `~/workspace/quant-intraday-signals/top-100-quant-signals-report.md`
defines each signal's name, intuition, formula, data, horizon, citations, provenance tag
(`[D]` documented / `[SR]` standard reconstruction / `[D/SR]` hybrid). Every chapter must
carry its provenance tag forward and never upgrade `[SR]` to `[D]` without a real citation.

**Honesty rules (non-negotiable).**
1. Worked examples use synthetic data, watermarked `SYNTHETIC EXAMPLE`, and state this in text.
2. Never present backtest-looking numbers from a synthetic example as real performance.
3. Costs, spreads, fees are always modeled explicitly; "before-cost" claims are flagged as such.
4. Vendor prices are `indicative — verify before budgeting`.
5. Latency/queue-position effects simulated on SIP/L1 data are labeled `simulated only — requires MBO/ITCH`.
6. No fabricated paper IDs, URLs, or statistics. If a chatbot gives an unverifiable number, the chapter
   must say `unverified chatbot claim` or drop it.

---

## 1. Refined SIGNAL chapter template (S001–S100)

Each signal chapter MUST contain these 12 sections, in this order, with these minimum contents.
(Target length: 1,500–2,500 words + 2 visuals. Depth over brevity; no filler.)

### S1. One-line verdict
Table with 4 rows: **What it is** (≤25 words) | **When it works** | **When it dies** |
**Build-or-buy in one line**. Plus the provenance tag `[D]/[SR]/[D/SR]` and family letter.

### S2. How it works — plain human explanation
No jargon without a definition. Use a concrete market vignette (e.g. "9:47:03, AAPL bid 231.40 × 800 / ask 231.41 × 300…").
Explain *why* the effect should exist economically (adverse selection, inventory, behavioral, structural).
End with a 3-bullet "mental model" summary.

### S3. The math — exact formula
- Full formula in LaTeX with every symbol defined (units included).
- Parameter table: parameter | symbol | typical range | what happens if too small/large | default example value.
  Mark every default as `example — not an institutional standard`.
- Normalization choices (z-score vs raw vs rank), lookback windows, and the exact causal timing
  ("computed at event *t* using only data ≤ *t*; tradable no earlier than *t+1*").
- 2–3 named variants (e.g. for OFI: touch-only vs multi-level; event-time vs volume-time aggregation).

### S4. Worked example — step-by-step numbers (SYNTHETIC)
- A small synthetic tape/table (8–15 rows) with hand-computable numbers; show every intermediate step.
- State the random seed used to generate it (so a reader can reproduce it).
- The generated chart (`images/S###_example.png`) must be the *same* data plotted — numbers in text and chart must agree.
- A "what to notice" paragraph interpreting the example (and its limits — e.g. "this toy tape has no fees").

### S5. Strategies that use this signal
Bulleted list of T-numbers with one-line role each, e.g. `- T001 — primary entry trigger (direction); T021 — adverse-selection filter (veto)`.
Must cross-reference only strategies from the T001–T100 list below. Minimum 2, and at least one
where the signal is the *primary* trigger and (where sensible) one where it is a *filter/veto*.

### S6. Data required — exact spec
Table: field | type | granularity | source tier (Tier 0–3 per report) | notes.
Collection method: named feed/API (e.g. Databento MBP-1, Polygon stocks v3), endpoint or schema sketch,
and a ≤20-line code sketch of the ingest loop (Python/polars or Rust pseudocode).
Storage estimate per symbol per day (cite `notes/cost-model.md` numbers).
Data-quality checklist: timestamp normalization, corporate actions, halts, DST/half-days, stale quotes.

### S7. Local build on M5 Max / 128GB
- Feasibility verdict: **trivial / feasible / heavy / infeasible-locally** with one-paragraph justification.
- Throughput estimate using `notes/cost-model.md` benchmarks: events/sec for ingest, signals/sec for compute,
  symbols sustainable in real time, and the bottleneck (CPU? memory bandwidth? I/O?).
- Stack options table: Python+polars | Rust | (kdb-style/DuckDB) — with when-to-pick-each.
- RAM footprint for 1 day and 60 days of the required data (apply cost-model rules of thumb).
- Engineering-time band in hours (use cost-model tiers) → convert to $ at $150/hr loaded cost, stated as estimate.
- What breaks first if you scale to 500 symbols or full OPRA.

### S8. Buy vs build
Table: vendor/option | what you get | indicative price | what buying gains | what buying loses.
Cover at minimum: Tier-0 free route, one Tier-1 retail vendor, one Tier-2 professional feed, and (where relevant)
the academic/institutional route. Verdict paragraph: **build if… / buy if…**, naming the crossover point
(e.g. "buy OPRA if you need full-chain OI; build the estimator if SIP NBBO suffices").

### S9. Success ratio / efficacy — documented evidence
- What peer-reviewed papers and practitioner sources actually report (Sharpe, hit rate, bps/trade),
  **always after-cost where available**; if only before-cost numbers exist, say so explicitly.
- Table: study/source | market & period | metric | before/after cost | caveat.
- Regimes where it fails (vol spikes, low-liquidity names, crowded periods) and any documented decay.
- Honest bottom line: "as a standalone trigger this is a ___ edge; as a filter it is ___".

### S10. Failure modes & pitfalls
Checklist of at least 6, each with a one-line mitigation: lookahead leakage, staleness/latency,
crowding/alpha decay, cost blowup (spread+fees+impact), regime breaks, overfitting/parameter mining,
data errors (bad ticks, splits), microstructure noise vs signal confusion.

### S11. Visuals
1. `![…](images/S###_example.png)` — matplotlib worked-example chart, watermarked `SYNTHETIC EXAMPLE`,
   per `notes/visual-spec.md` (style block mandatory).
2. Mermaid data-flow diagram (fenced ` ```mermaid `) per visual-spec template:
   `raw feed → ingest/normalize → feature compute → signal → downstream consumer`,
   with the data granularity labeled on each edge.

### S12. Sources
Minimum 3, each with title + author + year + URL (or arXiv ID). Prefer the report's citations first,
then add what the research found. Chatbot-provided claims without a checkable source go in a
separate `Unverified leads` sub-list, never mixed with real citations.

---

## 2. Refined STRATEGY chapter template (T001–T100)

Each strategy chapter MUST contain these 10 sections, in this order.
(Target length: 2,000–3,000 words + 2 visuals.)

### T1. One-line verdict
Table: **Style** (e.g. intraday stat-arb) | **Edge source** | **Typical holding period** |
**Capacity hint** | **Build-or-buy in one line**.

### T2. Full mechanics
- **Universe & session:** which symbols, session window (RTH only?), exclusions (halts, earnings days, low-ADV).
- **Entry rule:** exact trigger in terms of S-signals (thresholds marked `example`), causal timing (signal at *t* → earliest fill *t+1*).
- **Exit rule:** time stop, signal-flip, stop-loss, profit target — with example parameters.
- **Position sizing:** formula (vol-targeting, Kelly fraction, fixed notional), max per-name and portfolio heat.
- **Risk limits:** daily loss stop, max gross/net, kill-switch conditions.
- **Cost model:** spread assumption, fees, borrow, slippage function — applied to the worked example explicitly.
- **Order/execution sketch:** market vs limit, participation cap (e.g. ≤10% of visible depth), queue-position honesty note.

### T3. Signals it consumes
Table: signal `S###` | role (primary trigger / filter / veto / sizing / regime gate) | weight or logic
(e.g. "enter only if S001 z > 1.5 AND S008 < toxicity cap"). Include the combination logic in pseudocode
(≤25 lines). Every listed signal must exist in S001–S100.

### T4. Worked example — numbers + P&L (SYNTHETIC)
- A concrete scenario: symbol (use a fictional-but-plausible setup or a named large-cap with synthetic prices
  clearly labeled), entry/exit prices, share counts, fee schedule, resulting gross/net P&L walked line by line.
- Equity/P&L sketch chart (`images/T###_example.png`, watermarked `SYNTHETIC EXAMPLE`) of the same scenario.
- "Where the example is optimistic" paragraph (fills assumed, no partial fills, no latency).

### T5. Data & infra — what must run
Daily/intraday pipeline inventory: feeds, compute jobs, their schedule (pre-open, intraday loop, post-close),
storage growth per month. M5 Max feasibility verdict + throughput/RAM numbers (cite cost-model).
Failure plan: what happens if a feed drops mid-session (safe-mode behavior).

### T6. Buy vs build
Platforms and vendors: at minimum one retail platform (e.g. QuantConnect/Composer-style),
one professional venue/data option, indicative pricing, and the verdict with crossover logic.
If the strategy needs licensed alt-data or full OPRA, say so and price it.

### T7. Success-ratio evidence
Published Sharpe/returns/hit-rates with market, period, and before/after-cost labeling; capacity and
crowding notes; documented decay (with dates when known). Honest bottom line for a small
(≤$1M) paper operation vs an institutional desk.

### T8. Failure modes
Regime breaks, crowding, latency assumptions that don't hold on SIP, cost-model optimism,
overfit parameters, operational risks (stale kill-switch, feed outage). Each with mitigation.

### T9. Visuals
1. `![…](images/T###_example.png)` — matplotlib P&L/equity or trade-timeline chart, watermarked,
   per visual-spec.
2. Mermaid strategy-flow diagram: `data → signals → entry logic → sizing/risk → execution → P&L & monitoring`.

### T10. Sources
Same standard as S12 (≥3 checkable sources + separate unverified-leads list).

---

## 3. The 100 strategies (T001–T100)

Every strategy composes **2+ signals** from the report. `S###` = signal chapter ID (= report number, zero-padded).

### TB1 — Flagship strategies (Stages 101–110)
| ID | Name | One-liner | Signals |
|----|------|-----------|---------|
| T001 | OFI + Queue-Imbalance Directional Scalper | Tick-direction trades from touch order-flow imbalance confirmed by depth-queue imbalance. | S001, S003, S004 |
| T002 | Microprice Fair-Value Scalper | Trades toward the microprice-implied fair value with volume-delta confirmation and spread-decomposition cost gate. | S004, S006, S014 |
| T003 | VPIN-Gated Breakout Trader | Takes intraday breakouts only when order-flow toxicity is low; stands down when VPIN spikes. | S008, S021, S032 |
| T004 | VWAP-Deviation Mean-Reversion | Fades extreme distance from session VWAP, timed by queue imbalance, normalized by diurnal vol. | S040, S003, S067 |
| T005 | RVOL-Filtered Opening-Range Breakout | Crabel ORB entries confirmed by relative volume and gated by flow toxicity. | S021, S032, S008 |
| T006 | Intraday Trend + Vol-Regime Allocator | Rides intraday time-series momentum into the close, scaled by HMM vol regime. | S025, S027, S079 |
| T007 | Cointegration Z-Score Pairs | Classic Engle–Granger pairs with OU half-life exits and zero-crossing quality filter. | S050, S051, S053 |
| T008 | Kalman Dynamic-Hedge Pairs | Adaptive hedge-ratio pairs timed on imbalance-bar entries with resiliency exits. | S052, S083, S048 |
| T009 | ETF-vs-Basket Arbitrage | Creation/redemption arb on ETF–basket dislocations, confirmed by futures-spot lead-lag. | S056, S059, S014 |
| T010 | Variance-Risk-Premium Harvester | Delta-hedged short-vol positions when implied variance is rich vs HAR forecast. | S069, S066, S063 |

### TB2 — Core reversal & momentum infrastructure (Stages 111–120)
| ID | Name | One-liner | Signals |
|----|------|-----------|---------|
| T011 | Short-Term Reversal + Bounce Timing | Jegadeesh/Lehmann reversal entered at the touch to harvest the bid–ask bounce. | S035, S047, S014 |
| T012 | Jump-Filtered Overnight-Gap Fade | Fades overnight gaps only when no jump is detected; skips news-driven gaps (PEAD leg separate). | S036, S037, S100 |
| T013 | RSI-2 / IBS Extreme Fade | Connors-style oversold/overbought fade combining RSI-2 and internal bar strength. | S042, S043, S045 |
| T014 | Bollinger Reversal + Squeeze Exit | Fades band tags; covers into bandwidth-squeeze expansions and vol breakouts. | S041, S030, S076 |
| T015 | First-Half-Hour → Close Continuation | Heston-style intraday momentum: morning winners held into last-half-hour drift. | S026, S027, S046 |
| T016 | End-of-Day Drift Rider | Leans into last-hour drift confirmed by opening-auction imbalance read and spread estimate. | S027, S033, S013 |
| T017 | Scheduled Macro-Announcement Drift | Positions into scheduled releases; rides post-announcement drift with vol forecast sizing. | S034, S092, S066 |
| T018 | RVOL-Gated Gap-and-Go | Chases opening gaps only with institutional relative-volume and block-pressure footprints. | S023, S032, S094 |
| T019 | Donchian/Keltner Breakout + Vol Sizing | Dual-channel breakout entries sized by volatility-breakout regime. | S028, S029, S076 |
| T020 | Triple-Barrier + Meta-Labeling Overlay | Position-sizing and veto overlay: triple-barrier labels train a meta-model over any primary signal. | S085, S086, S088 |

### TB3 — Microstructure market-making & toxicity (Stages 121–130)
| ID | Name | One-liner | Signals |
|----|------|-----------|---------|
| T021 | Avellaneda–Stoikov Inventory Skew MM | Quotes skewed by inventory around a microprice/OFI fair value. | S089, S004, S001 |
| T022 | Queue-Imbalance Maker with Toxicity Cancel | Posts at the touch when queue imbalance favors the queue; cancels on OFI reversal or VPIN spike. | S003, S001, S008 |
| T023 | Hawkes Burst Scalper | Trades self-excitation bursts in order flow, signed by buy/sell intensity imbalance. | S017, S081, S018 |
| T024 | Informed-Size Tracker / Retail Fade | Follows stealth medium-size informed flow; fades retail/odd-lot flow. | S019, S020, S006 |
| T025 | Trade-Classification Trend Filter | Uses Lee–Ready/BVC signed imbalance to confirm or veto momentum entries. | S007, S025, S086 |
| T026 | Kyle-Lambda Participation Throttle | Sizes child orders from Kyle-lambda impact estimates with Amihud illiquidity caps. | S010, S011, S048 |
| T027 | Illiquidity Temporary-Impact Fade | Fades overextended moves in illiquid names, exiting on resiliency half-life. | S011, S048, S039 |
| T028 | Spread-Decomposition Router | Routes and holds based on quoted/effective/realized spread and adverse-selection component. | S014, S015, S012 |
| T029 | Spread-Estimate Edge Filter | Trades only when estimated effective spread (Roll / Corwin–Schultz) is below the edge. | S012, S013, S032 |
| T030 | Multi-Level OFI Weighted Predictor | Integrated OFI across 10 book levels as the directional trigger, VAR-confirmed. | S002, S005, S084 |

### TB4 — Pairs & cross-sectional extensions (Stages 131–140)
| ID | Name | One-liner | Signals |
|----|------|-----------|---------|
| T031 | Distance Pairs + Quality Filter | Gatev–Goetzmann–Rouwenhorst pairs gated by Do–Faff zero-crossing quality. | S049, S053, S050 |
| T032 | Copula Tail-Dependence Pairs | Trades extreme conditional-quantile divergences with purged-CV validation. | S054, S088, S051 |
| T033 | Johansen VECM Basket Arb | Multi-leg cointegrated baskets traded on error-correction speed. | S055, S080, S051 |
| T034 | Index Futures Cash-and-Carry | Basis convergence with borrow-fee and spread-cost checks. | S057, S098, S014 |
| T035 | Futures Calendar-Spread Carry | Harvests term-structure roll yield, timed by vol forecasts. | S058, S066, S063 |
| T036 | Cross-Asset Lead-Lag (Hayashi–Yoshida) | Trades the laggard from the leader's move with futures-spot confirmation. | S060, S059, S083 |
| T037 | ADR / Dual-Listed Premium Convergence | Fades FX-adjusted ADR premiums with lead-lag timing. | S061, S060, S014 |
| T038 | Sector Momentum + Idiosyncratic Fade | Long sector-momentum winners while fading idiosyncratic residual extremes. | S062, S039, S080 |
| T039 | ETF Creation/Redemption Flow Trader | Arbs ETF–basket discounts confirmed by block volume and relative volume. | S056, S094, S032 |
| T040 | PCA Eigenportfolio Residual Reversal | Statistical-factor residual mean reversion with AR-innovation timing. | S080, S039, S078 |

### TB5 — Volatility & options-informed (Stages 141–150)
| ID | Name | One-liner | Signals |
|----|------|-----------|---------|
| T041 | HAR Vol-Timing Overlay | Scales all intraday positions by HAR realized-vol forecasts. | S066, S067, S076 |
| T042 | Jump-Robust Vol Spike Trader | Trades bipower-variation / Lee–Mykland jump-filtered vol spikes. | S064, S065, S076 |
| T043 | GARCH Regime Filter | Activates momentum in low-GARCH-vol regimes, reversal in high-vol regimes. | S065, S079, S090 |
| T044 | Diurnal Deseasonalization Normalizer | Normalizes every signal by time-of-day vol seasonality before thresholding. | S067, S046, S083 |
| T045 | VIX Term-Structure Carry | Trades VIX futures curve shape against variance-risk-premium levels. | S068, S069, S066 |
| T046 | Straddle-Implied Move Fade | Fades overpriced event moves using unusual-options-activity confirmation. | S070, S073, S069 |
| T047 | Risk-Reversal Skew Momentum | Follows 25-delta risk-reversal skew shifts with options-flow confirmation. | S071, S072, S073 |
| T048 | Put/Call Ratio Contrarian | Fades extreme put/call readings with stretched-move and sentiment context. | S072, S097, S045 |
| T049 | Unusual Options Activity Follower | Follows signed options sweeps confirmed by equity RVOL and news sentiment. | S073, S094, S091 |
| T050 | GEX Pin / Dealer-Positioning Fade | Fades into gamma walls; rides pinning into expiry with implied-move context. | S074, S070, S076 |

### TB6 — Statistical / ML & regime (Stages 151–160)
| ID | Name | One-liner | Signals |
|----|------|-----------|---------|
| T051 | Kalman Fair-Value Trend | Local-level trend following with dynamic confidence from the Kalman filter. | S077, S078, S079 |
| T052 | AR/ARMA Innovation Trader | Trades forecast innovations (surprises), validated by trade–quote VAR. | S078, S084, S088 |
| T053 | HMM Regime-Switching Allocator | Switches between momentum and reversal books by hidden Markov state. | S079, S025, S035 |
| T054 | Hurst/Variance-Ratio Regime Toggle | Trend-following when Hurst > 0.5 regime detected; mean reversion otherwise. | S090, S025, S041 |
| T055 | DeepLOB + Feature-Stack Classifier | Deep learning on LOB sequences stacked with OFI and classical microstructure features. | S082, S083, S001 |
| T056 | Hasbrouck Trade–Quote VAR Predictor | Predicts quote revisions from the joint dynamics of trade signs and quotes. | S084, S007, S081 |
| T057 | Fractional-Differentiation Memory Trader | Trades fractionally-differenced series preserving long memory, AR-timed. | S087, S078, S090 |
| T058 | Dispersion Trader | Long single-stock realized vol vs short index vol, VRP-aware. | S075, S063, S069 |
| T059 | News-Sentiment First-Minute Momentum | Machine-readable news reaction momentum with volume confirmation. | S091, S092, S094 |
| T060 | Identified-News Drift Portfolio | Holds identified-news drifters; fades no-news drift, with earnings-drift context. | S092, S093, S100 |

### TB7 — Session patterns & auction (Stages 161–170)
| ID | Name | One-liner | Signals |
|----|------|-----------|---------|
| T061 | Initial-Balance Expansion Trader | Trades first-hour range breaks confirmed by squeeze and RVOL. | S022, S030, S032 |
| T062 | Streak Runner with Exhaustion Flip | Rides consecutive-bar streaks; flips to reversal on exhaustion signatures. | S031, S041, S008 |
| T063 | Stretched-Move Z-Score Fade | Fades multi-sigma intraday moves with resiliency-timed exits. | S045, S048, S014 |
| T064 | U-Shape Seasonality Timer | Concentrates risk in open/close seasonality windows, deseasonalized. | S046, S067, S027 |
| T065 | Open-Auction Imbalance Continuation | Follows opening-auction imbalance pressure with futures-spot confirmation. | S033, S094, S059 |
| T066 | VWAP-Cross Institutional Follower | Follows sustained VWAP crosses with RVOL confirmation; fades extreme deviations. | S024, S040, S032 |
| T067 | Anchored-VWAP Event Trader | Anchors VWAP at news/events; trades deviations with novelty context. | S024, S091, S093 |
| T068 | Scheduled-Event Vol Expansion | Positions for volatility expansion around scheduled events, implied-move aware. | S034, S076, S070 |
| T069 | Late-Day Reversal into Close | Fades last-30-minute overextensions using microstructure-reversal timing. | S027, S038, S041 |
| T070 | MOC Auction-Pin Trader | Trades market-on-close imbalance into the closing auction with GEX context. | S033, S027, S074 |

### TB8 — Alternative-data & attention (Stages 171–180)
| ID | Name | One-liner | Signals |
|----|------|-----------|---------|
| T071 | News-Novelty Reversal | Fades stale-news overreaction; follows novel-news drift. | S093, S097, S042 |
| T072 | Social-Sentiment Ignition Rider | Rides social-driven breakouts confirmed by RVOL and attention spikes. | S097, S032, S099 |
| T073 | ASVI Attention Reversal | Fades Google-Trends attention spikes with stretched-move timing. | S099, S045, S094 |
| T074 | Short-Interest Squeeze Rider | Momentum in high-borrow-fee, high-days-to-cover names with volume confirmation. | S098, S025, S094 |
| T075 | Crypto Funding-Rate Reversal | Fades crowded leverage extremes; basis-aware. | S095, S096, S069 |
| T076 | Liquidation-Cascade Fade | Buys crypto liquidation clusters with funding context. | S096, S095, S045 |
| T077 | Crypto Basis Cash-and-Carry | Funding/basis convergence with spread-cost accounting. | S095, S057, S014 |
| T078 | Earnings-Drift Intraday Leg | Trades the intraday leg of post-earnings-announcement drift on SUE. | S100, S025, S091 |
| T079 | Post-Announcement Vol Fade | Sells event volatility after realization, jump-robust measured. | S100, S070, S064 |
| T080 | Multi-Source Attention Composite | Blends ASVI, social sentiment, and news novelty into one attention factor. | S099, S097, S093 |

### TB9 — Infrastructure & execution (Stages 181–190)
| ID | Name | One-liner | Signals |
|----|------|-----------|---------|
| T081 | Adaptive Bar-Clock Sampler | Selects tick/volume/dollar/imbalance bars by regime for every downstream signal. | S083, S090, S067 |
| T082 | Information-Share Venue Router | Routes orders to the price-discovering venue; avoids toxic venues. | S016, S014, S008 |
| T083 | Retail-Flow Internalizer Fade | Provides liquidity fading retail/odd-lot imbalance, spread-decomposition priced. | S020, S015, S047 |
| T084 | Block-Trade Impact Reversion | Provides liquidity after block trades; exits on resiliency half-life. | S048, S094, S010 |
| T085 | Resiliency Market Maker | Quotes around LOB resiliency with Avellaneda–Stoikov inventory skew. | S048, S089, S004 |
| T086 | OFI-Paced Participation Tracker | VWAP/participation execution algo paced by OFI and RVOL. | S001, S032, S067 |
| T087 | Purged-CV Strategy Selector | Allocates across sub-strategies by purged/embargoed-CV rank with meta-labels. | S088, S086, S085 |
| T088 | Full-Stack Signal Ensemble | Blends all S001–S100 with meta-labeling and purged-CV validation. | S086, S082, S088 |
| T089 | Quote-Matcher (SIP-vs-Direct) | Micro-arbitrage on venue/SIP quote differences; requires co-located honesty label. | S016, S059, S014 |
| T090 | Overnight Inventory Carry Manager | Manages gap risk with jump filters, borrow awareness, and VIX term-structure context. | S037, S098, S068 |

### TB10 — Advanced hybrids & capstone (Stages 191–200)
| ID | Name | One-liner | Signals |
|----|------|-----------|---------|
| T091 | Multi-Level Book-Pressure Swing | 10-level static book-pressure swing positions with vol-breakout exits. | S005, S002, S076 |
| T092 | PIN-Gated Informed-Flow Avoidance | Stands down when PIN/toxicity is high; meta-labels the stand-down rule. | S009, S008, S086 |
| T093 | Options-to-Equity Lead Trader | Trades equity from options skew and signed flow with cross-asset lead-lag. | S071, S073, S060 |
| T094 | Squeeze Breakout (Options-Confirmed) | Bollinger squeeze breakouts confirmed by unusual options activity and vol expansion. | S030, S073, S076 |
| T095 | Dispersion + GEX Regime Switch | Runs dispersion only when dealer-gamma regime is supportive. | S075, S074, S068 |
| T096 | Kalman + HMM Adaptive Trend | Fair-value trend gated by HMM regime, AR-innovation timed. | S077, S079, S078 |
| T097 | Sub-Hour Microstructure Reversal Scalper | Tick-level mean reversion harvesting bid–ask bounce with spread estimates. | S038, S047, S012 |
| T098 | Jump-Validated Momentum Ignition | Momentum only on jump-validated moves (Lee–Mykland), RVOL confirmed. | S064, S025, S032 |
| T099 | ADR + Borrow Corporate Arb | Dual-listed premium convergence with borrow-fee and spread-cost accounting. | S061, S098, S014 |
| T100 | Grand Ensemble — 100 Signals, One Book | Capstone: all families blended with purged-CV, meta-labeling, and triple-barrier training. | S082, S086, S088 |

---

## 4. Batching plan — 20 batches × 10 chapters

Signals first (Stages 1–100), then strategies (Stages 101–200). Within each family, batches are
ordered by **practical importance**: most implementable / best-evidenced / most-used chapters first,
hardest-to-source or most-exotic chapters last. Batch IDs are stable: `SB1`…`SB10`, `TB1`…`TB10`.

### Signal batches (Stages 1–100)

| Batch | Stages | Chapters (in stage order) | Why this order |
|-------|--------|---------------------------|----------------|
| SB1 | 1–10 | S001 OFI, S003 queue imbalance, S004 microprice, S006 volume delta, S008 VPIN, S014 spread decomposition, S024 VWAP cross, S025 intraday TS momentum, S035 short-term reversal, S040 VWAP-deviation MR | The working core: every serious intraday book uses some of these; all implementable on L1/1-min data |
| SB2 | 11–20 | S011 Amihud, S013 Corwin–Schultz, S021 ORB, S027 EOD momentum, S032 RVOL breakout, S042 RSI-2, S043 IBS, S063 range RV, S066 HAR, S083 bar clocks | Core cost/vol infrastructure + the most-used session patterns |
| SB3 | 21–30 | S049 distance pairs, S050 EG z-score, S056 ETF/basket arb, S079 HMM regime, S081 Hawkes buy/sell, S085 triple-barrier, S086 meta-labeling, S088 purged CV, S091 news sentiment, S094 RVOL+blocks | Pairs foundations + the validation/ML layer every strategy chapter depends on + news |
| SB4 | 31–40 | S002 MLOFI, S005 book pressure, S007 trade classification, S010 Kyle lambda, S012 Roll spread, S015 Huang–Stoll, S017 Hawkes intensity, S018 sign autocorrelation, S020 retail/odd-lot, S047 bid–ask bounce | Order-flow estimation toolkit (L1/L2) |
| SB5 | 41–50 | S022 initial balance, S023 gap-and-go, S026 FH→LH momentum, S028 Donchian, S029 Keltner/Bollinger, S030 squeeze, S031 streaks, S033 auction imbalance, S044 stochastics, S045 stretched z-score | Breakout/session-pattern family |
| SB6 | 51–60 | S034 macro drift, S036 gap fade, S037 jump-filtered gap, S038 sub-hour reversal, S039 idiosyncratic reversal, S041 Bollinger reversal, S046 seasonality, S048 resiliency, S059 futures-spot lead-lag, S060 HY lead-lag | Mean-reversion family + lead-lag prediction |
| SB7 | 61–70 | S051 OU half-life, S052 Kalman hedge, S053 zero crossings, S054 copula, S055 Johansen, S057 cash-and-carry, S058 calendar spread, S061 ADR premium, S062 sector momentum, S090 VR/Hurst | Pairs & cross-sectional extensions + regime toggle |
| SB8 | 71–80 | S064 jump-robust RV, S065 GARCH, S067 diurnal vol, S068 VIX term, S069 VRP, S070 straddle move, S071 risk reversal, S072 put/call, S073 UOA, S074 GEX | Volatility & options-informed family |
| SB9 | 81–90 | S075 dispersion, S076 vol breakout, S077 Kalman fair value, S078 AR/ARMA, S080 PCA residual, S082 DeepLOB/ML, S084 Hasbrouck VAR, S087 fracdiff, S089 A-S skew, S016 info share | Stat/ML infrastructure + market-making skew |
| SB10 | 91–100 | S009 PIN, S019 stealth trading, S092 identified-news drift, S093 news novelty, S095 funding/basis, S096 OI/liquidations, S097 social sentiment, S098 short interest/borrow, S099 ASVI, S100 earnings drift | Hardest-to-estimate microstructure (PIN/stealth) + licensed alt-data family |

Coverage check: every integer 1–100 appears exactly once across SB1–SB10. (Verifier: `python3 -c`
over the lists.)

### Strategy batches (Stages 101–200)

| Batch | Stages | Chapters | Theme |
|-------|--------|----------|-------|
| TB1 | 101–110 | T001–T010 | Flagship strategies (the 10 a practitioner reads first) |
| TB2 | 111–120 | T011–T020 | Core reversal & momentum infrastructure |
| TB3 | 121–130 | T021–T030 | Microstructure market-making & toxicity |
| TB4 | 131–140 | T031–T040 | Pairs & cross-sectional extensions |
| TB5 | 141–150 | T041–T050 | Volatility & options-informed |
| TB6 | 151–160 | T051–T060 | Statistical / ML & regime |
| TB7 | 161–170 | T061–T070 | Session patterns & auction |
| TB8 | 171–180 | T071–T080 | Alternative-data & attention |
| TB9 | 181–190 | T081–T090 | Infrastructure & execution |
| TB10 | 191–200 | T091–T100 | Advanced hybrids & capstone (T100 = grand ensemble) |

### Execution order for the orchestrator
1. Research SB1 → write S001…S010 → review → merge (Stages 1–10). Then SB2, …, SB10.
2. Then TB1 → … → TB10 (Stages 101–200).
3. Never merge a batch until all 10 chapters pass reviewer QC (see `notes/merge-protocol.md`).
4. Failed chapters go to `batches/quarantine/` — batches merge with a `CHAPTER-DEFERRED` placeholder
   only after 2 failed re-research passes (never silently dropped).

---

## 5. Per-chapter research checklist (workers + reviewers)

### Research phase (per chapter)
- [ ] Read the report entry for this signal/strategy; note provenance tag and citations.
- [ ] Web-search the primary paper / canonical source; capture exact formula + parameter ranges.
- [ ] Ask the batch's 3 chatbot questions (`questions/chatbot-question-bank.md`); record answers with
      source labels (Grok / DeepSeek / Kimi); mark anything unverifiable as `unverified chatbot claim`.
- [ ] Collect ≥3 checkable sources (papers/docs with URLs or arXiv IDs).
- [ ] Find documented performance numbers (Sharpe / hit rate / bps per trade), labeled before/after cost.
- [ ] Find vendor/pricing data points; mark all `indicative — verify before budgeting`.
- [ ] Draft the worked example with a fixed random seed; verify hand-computed numbers.
- [ ] Verify every cross-referenced S###/T### exists in the plan's lists.

### Writing phase (per chapter)
- [ ] All template sections present, in order (12 for signals, 10 for strategies).
- [ ] Plain-language explanation defines every jargon term on first use.
- [ ] Formula in LaTeX; every symbol defined; parameter table complete; defaults marked `example`.
- [ ] Worked example: synthetic tape table + step-by-step numbers + seed stated + text/chart agreement.
- [ ] Data spec table complete; ingest code sketch ≤20 lines; storage/day cited from cost-model.
- [ ] Local-build section: feasibility verdict + throughput + RAM + engineering hours + stack table.
- [ ] Buy-vs-build table with ≥3 options + verdict paragraph with crossover logic.
- [ ] Success-ratio section: ≥2 documented evidence rows, after-cost labeled, honest bottom line.
- [ ] Failure modes: ≥6 items with mitigations.
- [ ] Exactly 2 visuals: PNG exists at `images/<ID>_example.png`, watermarked; mermaid fenced and labeled.
- [ ] Sources: ≥3 checkable + separate unverified-leads list.

### Review phase (per chapter) — see merge-protocol.md for the full gate
- [ ] No fabricated realism; synthetic labeled everywhere including chart watermark.
- [ ] No invented paper IDs/URLs/statistics; spot-check 2 citations resolve.
- [ ] Cross-refs valid; math renders; costs modeled; after-cost honesty present.

---

## 6. Provenance & difficulty quick-map (for scoping research effort)

- **Tier L (4–12 eng hrs):** most of B (21–34), C (35–48) on 1-min bars; S083 bars; S085/86/88 labels.
- **Tier M (20–60 eng hrs):** L1 event signals (S001, S003, S004, S006, S007, S008, S014);
  pairs D (49–62); vol estimators E (63–70); Kalman/HMM (S077, S079); GEX (S074).
- **Tier H (60–200 eng hrs):** L2/MBO (S002, S005, S016, S082); PIN (S009); full OPRA flow
  (S071–S073); licensed alt-data G (91–100); venue routing (T082/T089).
Workers: use these tiers for the S7/T5 engineering-time bands (details in `notes/cost-model.md`).
