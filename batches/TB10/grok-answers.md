# TB10 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials (account: Praveen Gupta)
- Date: 2026-09-10
- Chat: https://grok.com/c/f453cc53-8cba-4235-b3e1-c39281101e49
- Batch: TB10 — Advanced hybrids & capstone (T091–T100)
- Status: **COMPLETE** — all three questions asked one at a time in one chat, full answers captured verbatim. Session died twice mid-stream; re-signed in via Secure Vault and resumed the same chat each time. Formulas restored from the page's exact KaTeX source where plain-text extraction rendered math as spaced Unicode. Arithmetic preserved as generated; QC flags appended.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- All thresholds and dollar figures are illustrative examples.
- Nothing here is a live-trading spec.
- **SIMULATED_ONLY** on routing/colo: book-pressure alpha at seconds can live on a Mac; microsecond-level book pressure cannot.

---

## Q-TB10-1 — mechanics + worked example (verbatim)

"All thresholds below are **examples**, not claimed optima. Live books, options surfaces, and 100-signal stacks will not match these numbers. The formulas are the standard ones in the microstructure and financial-ML literature."

### (A) Multi-level book-pressure swing trader

"### Signal computation

At snapshot \(t\), for levels \(l=1,\ldots,L\) (example \(L=10\)):

$$\mathrm{OBI}_{l,t}=\frac{V^{\mathrm{bid}}_{l,t}-V^{\mathrm{ask}}_{l,t}}{V^{\mathrm{bid}}_{l,t}+V^{\mathrm{ask}}_{l,t}+\varepsilon}$$

Decay-weighted multi-level pressure (static shape):

$$P_t=\sum_{l=1}^{L} w_l\,\mathrm{OBI}_{l,t},\qquad w_l=\frac{e^{-\lambda(l-1)}}{\sum_{k}e^{-\lambda(k-1)}}$$

Example: \(\lambda=0.35\) so level-1 gets ~30% of the weight, level-10 ~2%.

Dynamic multi-level order-flow imbalance (MLOFI / Cont-style OFI), per level, between events \(\tau_{n-1}\) and \(\tau_n\):

$$\Delta W^l(\tau_n)=\begin{cases}
q^l_b(\tau_n) & p^l_b(\tau_n)>p^l_b(\tau_{n-1})\\
q^l_b(\tau_n)-q^l_b(\tau_{n-1}) & p^l_b=p^l_b\text{ previous}\\
-q^l_b(\tau_{n-1}) & p^l_b\text{ fell}
\end{cases}$$

and analogously \(\Delta V^l\) on the ask. Then

$$\mathrm{OFI}^l_{\tau_n}=\Delta W^l-\Delta V^l,\qquad
\mathrm{IOFI}_t=\mathbf{1}^\top\mathrm{PCA}_1(\mathrm{OFI}^{1:L}_t)$$

or a simple weighted sum of \(\mathrm{OFI}^l\). Multi-level OFI has higher contemporaneous \(R^2\) for mid-price change than top-of-book alone; forecasting power at minutes is weaker and regime-dependent."

"**Swing filter (not HFT):**
- Sample books every \(\Delta=30\) s–2 min (example: 60 s).
- Smooth: \(P^*_t=\mathrm{EMA}_{20}(P_t)\).
- Persistence: require \(\mathrm{sign}(P^*)\) unchanged for \(K=8\) samples (~8 min).
- Spread guard: block if relative spread \(> s_{\max}\) (example 8 bps large-cap, 25 bps mid-cap).
- Refill penalty: if depth on the thin side recovers \(>50\%\) within 2 samples, cut \(\mid P^* \mid\) by half (flicker / spoof filter)."

"### Combination (A is a single-family stack, not 100 signals)

Example blend inside A only: \(S^A_t = 0.55\,z(P^*_t) + 0.35\,z(\mathrm{IOFI}^*_t) + 0.10\,z(\mathrm{trade\text{-}OBI}_t)\) where \(z\) is rolling 2-hour z-score, clipped to \([-3, 3]\). Trade-OBI is signed executed volume over the same window (less sensitive to fleeting quotes)."

"### Entry / exit / sizing / risk (examples)

| Rule | Example threshold |
|---|---|
| Enter long | \(S_A > +1.25\) and persistence \(K\) met and spread OK |
| Enter short | \(S_A < -1.25\) (mirror) |
| Scale-in | add 0.5× if \(S_A\) extends another +0.75 without adverse mid move > 0.4 \(\sigma_{5m}\) |
| Profit take | +1.25 × \(\sigma_{20}\) (ATR-style, 20-bar) |
| Stop | \(-0.85 \times \sigma_{20}\) or mid crosses VWAP against you by 0.5 \(\sigma\) |
| Time stop | 45–90 min or end of session (swing, not overnight unless basis exists) |
| Size | \(q=\frac{r\cdot\mathrm{equity}}{\mathrm{stop\,distance}}\cdot\min(1, [\text{formula continues; extraction truncated}])\) |
| Max book impact | cap \(q\) at 8% of displayed size on first 3 opposite levels |
| Kill | 2 consecutive stops same session, or realized spread + fees > expected move |

This is a minutes-to-hours swing on persistent book shape, not a queue-position scalper."

### (B) Options-to-equity lead trader (skew + signed flow → equity)

"### Signal computation

1. **Skew (public surface).** Xing–Zhang–Zhao style: \(\mathrm{Skew}_t = \mathrm{IV}_{25\Delta,T}^{\text{OTM put}} - \mathrm{IV}_{50\Delta,T}^{\text{ATM call}}\). Example tenor \(T = 30\) calendar days, interpolated. High skew = richer downside protection = historically associated with lower subsequent equity returns (informed hedging / crash demand). Flattening skew (puts cheapening vs calls) is the bullish lead.
Also track 25Δ risk-reversal and a glassnode-style integrated up-variance minus down-variance if the full surface is available.

2. **Signed options flow (needs classification, not just OI).** \(\mathrm{SF}_t = \sum_{c \in C_t} s_c \cdot \mathrm{delta}_c \cdot \mathrm{vega}_c \cdot 1\{\text{customer aggressor}\}\). Sign convention (example): customer buy-call / sell-put ⇒ + equity-bullish; customer buy-put / sell-call ⇒ −. Weight by \(|\delta|\) so OTM lottery tickets do not dominate ATM hedges. Open interest alone is unsigned and is not a substitute.

3. **Combined lead score** \(S^B_t = \alpha\,z(-\Delta\mathrm{Skew}_{5d}) + (1-\alpha)\,z(\mathrm{SF}_{1d}/\mathrm{ADV}_{opt})\) — skew shift + signed flow. Example \(\alpha = 0.45\). Negative \(\Delta\mathrm{Skew}\) (flattening) is the long lead. Why it can lead equity: options absorb informed flow when stock borrow, short-sale constraints, or leverage make the listed stock the worse venue; the stock then catches up as dealers hedge Δ and as the public surface is observed. A large fraction of classical IV-spread / skew predictability collapses once high stock-borrow-fee names are excluded — so treat borrow fee as a confounder, not as free alpha."

"### Entry / exit / sizing / risk (examples)

| Rule | Example |
|---|---|
| Equity long | \(S_B > +1.1\) and 5d skew change < −1.5 vol points and 1d signed call-heavy flow > 1.5 × 20d mean |
| Equity short | mirror |
| Confirm | stock not already +2σ on the same day (avoid buying the hedge print) |
| Horizon | 2–10 sessions (literature effects are days–weeks, not ticks) |
| PT / SL | \(+1.8\,\sigma_{20d} / -1.1\,\sigma_{20d}\), or exit when skew mean-reverts 60% of the impulse |
| Size | vol-target 8–12% annualized on the name; cut 50% if borrow fee in top quintile |
| Hard filters | option ADV too thin, earnings inside 5 sessions (unless that is the thesis), inverted term structure (crash) |

You trade the equity, not the option, unless you explicitly want to harvest the surface itself (different book)."

### (C) Grand 100-signal ensemble (T100)

"### What the 100 are (taxonomy, not a magic list)

Example allocation, not a claim that 100 is optimal:
- 25 microstructure (OBI/MLOFI/OFI variants, trade imbalance, spread, refill)
- 20 options/lead (skew, RR, signed flow, IV–RV, term structure)
- 20 price/volume trend-rev (breakouts, residual momentum, VWAP distance)
- 15 cross-sectional / relative (sector residual, beta-neutral pair, ETF flow)
- 10 macro/regime (breadth, credit, FX, vol-of-vol)
- 10 calendar / microstructure calendar (open-drive, index rebalance windows)

Each base learner \(i\) emits a side \(d_{i,t} \in \{-1, 0, +1\}\) and a raw score \(s_{i,t}\)."

"### Combination logic (three layers; pick one in production)

**Layer 1 — robust vote (always on as a baseline)**: \(V_t = \sum_{i=1}^{100} \pi_i\,\mathrm{sign}(s_{i,t})\,1\{|s_{i,t}| > c_i\}\). Example: \(\pi_i \propto 1/\hat\sigma(\mathrm{PnL}_i)\) from purged OOS, renormalized; \(c_i = 0.8\). Enter if \(|V_t| \ge 18\) of 100 after gates (example).

**Layer 2 — stacking on OOS probabilities**: Train a meta-learner \(m\) on features \(x_t = (s_{1,t}, \ldots, s_{100,t}, \hat p_{1,t}, \ldots, \mathrm{regime}_t, \mathrm{cost}_t)\) using only purged out-of-fold base predictions (never in-sample scores). Meta output \(\hat p_t = \Pr(\text{triple-barrier success} \mid x_t)\). Final side = majority or best-primary; size \(\propto \hat p_t - \tau\).

**Layer 3 — meta-labeling (recommended over unconstrained stacking)**: Primary model(s) propose side. Meta-model is a binary classifier: take the bet or pass. Size = \(f(\hat p_{meta})\). This is López de Prado's split of direction vs whether/how much.
Example size map: \(\hat p < 0.55 \rightarrow 0\); \(0.55 \le \hat p < 0.65 \rightarrow 0.4\times\) unit; \(0.65 \le \hat p < 0.78 \rightarrow 1.0\times\); \(\hat p \ge 0.78 \rightarrow 1.4\times\), cap 1.6×."

"### Entry / exit / sizing / risk (examples)
- Trade only when vote and meta-label agree on side and \(\hat p \ge 0.58\).
- Portfolio: 6–15 concurrent names, gross \(\le 2.0\times\), net \(\le 0.6\times\), name risk 0.30% equity to stop.
- Correlation cap: if pairwise 20d return corr > 0.7, keep the higher-\(\hat p\) name.
- Daily loss kill −1.2% equity; weekly −2.5%.
- Cost model inside the label: subtract half-spread + 1–3 bps + borrow."

"### Training protocol for (C): purged CV + embargo + triple-barrier

**Labels (triple barrier).** For each event time \(t\) (signal fire):
- Upper barrier: \(p_t\exp(+u\cdot\sigma_t\tau)\) (example \(u = 1.25\))
- Lower barrier: \(p_t\exp(-d\cdot\sigma_t\tau)\) (example \(d = 0.90\))
- Vertical barrier: \(\tau = 2\) days (or 90 min for A-style, 8 days for B-style)
Label \(y \in \{+1, -1, 0\}\) = first barrier touched. For meta-labels, if primary side is \(d\), meta-label = 1 iff the barrier in direction \(d\) is touched first (successful take), else 0.

**Purged \(k\)-fold + embargo.** Standard \(k\)-fold leaks because a label at \(t\) uses prices on \([t, t+h]\).
1. Split time into \(k\) contiguous folds (example \(k = 5\)).
2. Purge: drop every training observation whose label interval overlaps any test label interval.
3. Embargo: also drop a fraction \(\varepsilon\) of the training sample immediately after each test block (example \(\varepsilon = 1\%–2\%\) of the series, or one vertical-barrier length).
4. Fit base models and the meta-learner only on the purged train set; score the test fold.
5. Optional: Combinatorial Purged CV to get a distribution of OOS paths instead of one walk-forward number.

Uniqueness / sample weights: overlapping events get weight \(1/c_t\) where \(c_t\) is concurrent label count (AFML ch. 4). Sequential bootstrap if you bag trees.
What you report: not a single Sharpe — the CPCV Sharpe distribution, deflated Sharpe, and turnover/cost sensitivity."

"### Honest statement: what T100 can and cannot add

**Can add**
- Variance reduction when components are imperfectly correlated (bagging-like).
- A gating function: meta-labeling can raise precision by refusing low-\(\hat p\) bets, which often improves net PnL even if gross hit-rate of primaries is mediocre.
- Regime routing: the stacker can learn 'use book-pressure in tight-spread hours, use skew after a vol shock.'
- Capacity allocation across heterogeneous horizons (A minutes, B days) if the meta features include horizon and cost.

**Cannot add**
- A new independent alpha source. Linear or shallow stacking of 100 weak, overlapping microstructure transforms does not create information that was not in the book, the tape, or the surface.
- Robustness to nonstationarity. When the data-generating process shifts (maker-taker change, closing auction redesign, zero-DTE options), the meta-learner overfits the old mixture.
- Escape from costs. 100 signals fire more often; without a ruthless meta-gate, capacity and fees eat the diversification.
- Statistical significance after multiple testing. 100 hypotheses require deflated Sharpe / DSR; most 'ensemble lift' in-sample is selection bias.
- Help when all components share one factor (e.g. all long-momentum in a squeeze). The vote becomes a leveraged single bet.

Rule of thumb: if the best 5–8 economically distinct families already have a stable purged-OOS edge after costs, T100's job is sizing and veto, not prediction. If those families have no edge, T100 will not invent one."

"### Worked synthetic examples (toy paths, not live edges)

Assumptions common to all three: equity $1,000,000; half-spread paid on entry and exit as stated; no borrow.

**(A) 10-level book-pressure path**
Mid starts at 100.00. \(\lambda = 0.35\), \(w \approx (0.30, 0.21, 0.15, 0.11, 0.07, 0.05, 0.04, 0.03, 0.02, 0.02)\). \(S_A\) entry ±1.25. Stop 0.85 σ, \(\sigma_{20} = 0.22\) pts so stop = 0.19. PT = 0.28. Risk \(r = 0.30\% \rightarrow \$3{,}000 / 0.19 \approx 15{,}800\) shares, capped to 12,000 by depth. Cost 1.5 ¢/share round-trip.

| t (min) | P (weighted OBI) | Persist | \(S_A\) | Action | Mid | Position |
|---|---|---|---|---|---|---|
| 0–7 | +0.12 → +0.41 | building | 0.6–1.1 | flat | 100.02 | 0 |
| 8 | +0.58 | 8 bars | +1.41 | BUY 12,000 @ 100.06 | 100.06 | +12k |
| 12 | +0.62 | | +1.50 | hold | 100.14 | |
| 18 | +0.21 | fading | +0.70 | hold | 100.21 | |
| 24 | −0.05 | | +0.10 | PT hit 100.34 | 100.34 | SELL 12,000 @ 100.33 |

Gross: \((100.33 − 100.06) \times 12{,}000 = \$3{,}240\). Costs: \(12{,}000 \times \$0.015 = \$180\). Net **+$3,060** (one swing). If at t=14 the book had flipped to \(S_A = −1.3\) before PT, stop at 99.87 would have been net −$2,460. Persistence + spread guard is what keeps A from taking that flip.

**(B) Skew-shift → equity entry timeline**
Name ADV $40m. 30d 25Δ put IV starts 28.0, ATM call IV 22.5 ⇒ Skew = 5.5 vol pts (slightly rich vs 20d mean 4.8).

| Day | 25Δ put IV | ATM call IV | Skew | ΔSkew 5d | Signed flow (Δ-wtd, $m) | \(S_B\) | Equity |
|---|---|---|---|---|---|---|---|
| −5 | 28.0 | 22.5 | 5.5 | 0 | +2 | 0.1 | 50.00 |
| −2 | 26.8 | 23.1 | 3.7 | −1.4 | +8 | 0.7 | 50.40 |
| 0 | 25.4 | 23.6 | 1.8 | −3.2 | +21 (2.4× mean) | +1.46 | 50.55 → BUY 8,000 sh @ 50.58 (vol-target; stop 1.1×\(\sigma_{20}\) = 1.32 → 49.26) |
| +2 | 25.1 | 23.8 | 1.3 | | +4 | 0.9 | 51.40 |
| +6 | 25.6 | 23.4 | 2.2 | mean-reverting | −3 | 0.2 | 52.10 PT zone |

Exit +6 at 52.08. Gross \((52.08 − 50.58) \times 8{,}000 = \$12{,}000\). Costs 2 ¢ + 3 bps slippage ≈ \$400. Net **+$11,600**. Counterfactual: same skew flatten but signed flow = −12m (dealer/call selling) would have held \(S_B < 0.6 \rightarrow\) no trade. That is the whole point of combining skew with signed flow.

**(C) 5-signal stacking walk + meta-label sizing (stand-in for T100)**
Five primaries, sides already proposed. Meta \(\hat p\) = calibrated success probability from purged OOS. Unit risk $2,500. Barriers \(u = 1.25\), \(d = 0.90\), \(\tau = 2\) d. Cost $80 per unit round-trip.

| Event | Signals (side, raw) | Vote | Meta \(\hat p\) | Size | Outcome (barrier) | Gross | Net |
|---|---|---|---|---|---|---|---|
| 1 | A+1.4, B+0.6, C+0.2, D−0.4, E+1.1 | +3 | 0.71 | 1.0× long | upper | +$3,100 | +3020 |
| 2 | A+0.9, B−1.2, C−0.8, D−0.3, E+0.4 | −1 | 0.52 | 0 (pass) | would have hit lower | 0 | 0 (saved −$2,900) |
| 3 | A+1.6, B+1.3, C+1.1, D+0.9, E+0.7 | +5 | 0.81 | 1.4× long | vertical | +$1,400 / 1960 | +1848 |
| 4 | A−1.5, B−1.1, C+0.3, D−0.9, E−1.0 | −4 | 0.66 | 1.0× short | lower against you | −$2,250 | −2330 |
| 5 | A+0.4, B+1.8, C+1.2, D+0.2, E+0.5 | +3 | 0.61 | 0.4× long | upper | +$2,800 / 1120 | +1088 |

Net P&L of the walk: +$3,020 + 0 + 1,848 − 2,330 + 1,088 = **+$3,626**. Without the meta-gate, event 2 would have been a full short into a failed vote and event 5 would have been 1.0×; net would have been about +$1,300 on this path. The ensemble's only honest contribution here is not trading event 2 and down-sizing event 5. It did not invent a sixth source of edge.

**Sources (primary)**
- Cont, Cucuringu, Zhang — multi-level / integrated OFI and price impact.
- Xu, Gould, Howison and follow-ons — MLOFI construction.
- Xing, Zhang, Zhao (2010) — OTM-put vs ATM-call skew and equity returns.
- Pan & Poteshman and later signed-volume work — options flow leading the stock.
- López de Prado, Advances in Financial Machine Learning — triple-barrier labels, meta-labeling, purged k-fold, embargo, CPCV.

*If you want this encoded next as an AlphaForge primary+meta spec (event timestamps, uniqueness weights, and a CPCV harness), say which horizon mix (A-minutes / B-days) should be the default unit of risk.*"

---

## Q-TB10-2 — infra + local build + buy vs build (verbatim)

"All figures are indicative 2026 list / commonly quoted vendor prices, not a bid. Exchange non-display and colocation schedules change; treat every line as 'verify before you wire.' Hardware is a 128 GB M5 Max (18 CPU / up to 40 GPU, ~614 GB/s unified bandwidth on the 40-core SKU)."

"The stack only works on this laptop if you accept research-grade latency (home/office internet, reconstructed books, not matching-engine colocation). The moment you need licensed non-display on primary venue feeds plus a rack in NY4/NY5/CH4, the Mac is a research box, not the production path."

"**Scope you are actually buying**

| Layer | What T091–T100 need |
|---|---|
| Book pressure (A / several of T091–T100) | Top 10 levels MBP on a liquid venue (Nasdaq TotalView-derived MBP-10 is the usual research substitute). True multi-venue L2 is a different bill. |
| Skew + signed flow (B) | Full OPRA chain: quotes, trades, OI, a usable IV/Greek surface, aggressor or inferred signed prints. |
| Ensemble harness (C) | 60 trading-day hot store, purged-CV + embargo + triple-barrier labels, stacking / meta-label model, intraday inference of all 100 scores. |
| Universe (example) | 150–400 names for live inference; 2,000–4,000 for nightly CS; options only on the 150–400. }

Two commercial postures:
- Path R — research / single-operator on the Mac (Databento + Massive/Theta-class APIs; display or vendor-bundled license).
- Path P — production licensed (exchange access + non-display + OPRA professional/non-display + colo). This is where a small shop should not build."

"**(1) Total data bill, by feed**

*Path R — what a 128 GB M5 Max stack actually pays*

| Feed | Role | Indicative monthly | Notes |
|---|---|---|---|
| Databento US Equities | Standard (~$199) or Plus (~$1,500–$1,750) | $200–$1,750 | Live + hist L1; MBP-10 / MBO on included window. Unlimited Equities plan is ~$4,000/mo if you need years of L2/L3. Hist MBP-10/MBO on Standard/Plus is often last 1 month included; older L2 is usage (~$0.40/GB class). |
| Databento OPRA (same plan family) | Options L1 trades/quotes | usually inside the same plan + usage for deep hist | Full-tick OPRA history is the fat part of the disk, not the subscription line. |
| Massive (Polygon) Stocks Advanced | SIP-class stocks RT, easy REST/WS | $199 individual | Business stocks ~$1,999 if the use is commercial. |
| Massive Options Advanced | Chains, RT Greeks/IV, WS | $199 individual / Business options core + Full Market OPRA expansion $1,999 | Signed flow quality is only as good as trade flags. |
| ThetaData Pro-class | Raw OPRA ticks + Greeks | $40–$160 + OPRA pass-through | OPRA pro display ~$31.50/user; non-display systems ~$2,000/category. |
| Cboe LiveVol Pro (optional) | Surface / analytics you would otherwise build | $350–$420/user + data fees | Buy this before you write a surface engine. |
| IBKR / broker L2 add-ons | Sanity-check tape, not research store | $5–$150 | Fine for eyeballs; not a 60-day MBP-10 archive. |

*Path R cash outlay (realistic working set)*

| Configuration | Monthly | Year-1 (incl. 60-day hist pull) |
|---|---|---|
| Lean: Databento Standard + Massive stocks+options Advanced + Theta Value | $650–$900 | $9k–$13k |
| Comfortable research: Databento Plus + Massive Advanced pair + LiveVol or Theta Pro | $2,200–$2,800 | $28k–$38k |
| 'I want years of MBP-10/MBO on file' | Databento Equities Unlimited $4,000 + options hist usage | $50k–$80k year-1 |

One-time hist: 60 session-days of Nasdaq-derived MBP-10 on ~400 symbols is typically tens of GB, not terabytes (see disk). Full-tick OPRA on 400 underlyings × ~2–4k contracts × 60 days is the large pull — budget $500–$3,000 extra usage on first stand-up depending on schema (trades vs every quote).

*Path P — licensed production (do not put this on a laptop)* — Direct-feed list (one venue already ends the 'small shop' case):

| Item | Indicative monthly |
|---|---|
| NYSE Arca Integrated — access | $3,200 |
| NYSE Arca Integrated — non-display per category | $11,300 (cat 3 cap $33,900) |
| NYSE Integrated — non-display | $22,400/category |
| Nasdaq TotalView access + non-display | same order of magnitude (low–mid five figures all-in once you add non-display) |
| OPRA professional display | $31.50/user |
| OPRA non-display | ~$2,000/category, stacks |
| OPRA vendor / direct access | $1,000–$1,500 + circuits |
| Cross-connect + 10 Gb in NY4/NY5 | $1k–$4k port + $1k–$3k cabinet slice (retail remote cage is more) |
| FPGA/feed-handler box (not a Mac) | capex $8k–$40k |

Path P floor for 'real L2 on one primary + OPRA non-display' is ~$15k–$40k/month before people. Multi-venue books + three non-display categories is a $50k–$150k/month market-data department, not a side project."

"**(2) Peak RAM and disk — 60-day lookback on 128 GB M5 Max**

Assumptions: 400 underlyings live; 10-level MBP snapshots at 100–200 ms or event MBP-10 compressed; options: 400 names × 2,500 contracts average, quotes conflated to 100–500 ms for the surface, full prints kept.

| Store | Hot RAM (inference) | Disk (60 session-days, compressed parquet/dbn) |
|---|---|---|
| Equity MBP-10 / reconstructed 10-level books | 8–18 GB working set (400 names × 10×2 × rolling state + feature cache) | 40–120 GB |
| Equity trades + BBO 1s/100ms | 2–4 GB | 15–40 GB |
| Options quotes conflated + Greeks surface | 20–45 GB if you keep the live surface in unified memory | 250–700 GB |
| Options full prints (signed-flow) | 4–8 GB rolling | 80–200 GB |
| Feature matrix T091–T100, 60d, 400 names, 1-min bars | 6–12 GB | 20–50 GB |
| Triple-barrier label store + oof preds + CPCV folds | 4–10 GB during train | 30–80 GB |
| OS + Python + models (LightGBM/XGB + small MLP) | 8–12 GB | 20 GB |
| Peak simultaneous | ~70–95 GB if you train while the live surface is up | 450 GB–1.2 TB |
| Safe layout on this machine | Keep live surface + books in RAM; park 60d OPRA quotes on external NVMe / 4 TB internal | 1–2 TB usable is the right internal SSD |

128 GB is enough for Path R if you do not hold unconflated OPRA quotes for 400 names in RAM and you do not train a wide neural stacker on the full tick matrix in one shot. It is not enough for 'load 60 days of raw OPRA + MBO into a dataframe.' Shard by date and symbol; use memory-mapped parquet/dbn.
Thermal note: a 16-inch M5 Max will sustain all-day LightGBM + live WS; a 14-inch will throttle if you train CPCV overnight on battery or a closed clamshell with poor airflow."

"**(3) Training vs inference compute on M5 Max**

| Workload | What runs | Wall time on M5 Max (order of magnitude) | Bound |
|---|---|---|---|
| Nightly feature build, 400 names × 100 signals × 60d @ 1-min | Polars/pandas + numba | 25–90 min | CPU + SSD |
| Triple-barrier + uniqueness weights | vectorized path scan | 10–40 min | CPU |
| Purged 5-fold + embargo, 20 LightGBM primaries | 18 threads | 45–180 min | CPU |
| Meta-labeler (binary, ~50 features) | 1 model | 5–20 min | CPU |
| CPCV (many combinatorial paths) | same models × 20–50 paths | overnight (4–12 h) | CPU; cancel if you also want the machine next morning |
| Wide MLP stacker on GPU (MPS) | optional | 20–90 min | GPU/unified; rarely worth it vs trees |
| Live inference, 100 signals, 400 names, 1s–5s | 20–150 ms per cycle if features are incremental | RAM bandwidth, not FLOPs |
| Live options surface refresh (400 names) | IV solve on changed strikes | 200 ms–2 s if you warm-start; 5–20 s cold | CPU |

The M5 Max is asymmetric: inference and tree training are comfortable; the constraint is data movement and the options surface, not 100 LightGBMs. Do not put a 7B LLM in the loop on the same 128 GB while the surface is resident.
Duty cycle that fits: live inference all session; feature + label + meta refit after the close; CPCV on weekends only."

"**(4) Engineering hours by subsystem**

One senior person who already knows microstructure + AFML (your case). Hours are calendar engineering, not 'AI wrote the notebook.'

| Subsystem | Build to 'honest research' | Build to 'supervised paper / tiny live' | Comment |
|---|---|---|---|
| Ingest + license/account hygiene | 20–40 | 40–80 | Vendor quirks, symbol mapping, corporate actions |
| L2 book reconstructor (MBP-10 → 10-level OBI/MLOFI) | 40–80 | 80–150 | Snapshot/delta correctness is the whole game |
| Options chain + IV/skew + signed flow | 60–120 | 150–280 | Surface, expiries, deliverables, open/close prints |
| Feature store (100 signals, point-in-time) | 50–90 | 120–200 | PIT and as-of joins eat months if sloppy |
| Triple-barrier + purge/embargo + CPCV harness | 40–70 | 80–140 | López de Prado is short to code, long to trust |
| Stacker / meta-label + calibration | 30–50 | 60–100 | Calibration plots or it is fiction |
| Live inference + kill switches + cost model | 40–80 | 100–180 | The unglamorous half of PnL |
| Data QA, leak tests, monitoring | 30–60 | 80–150 | Where ensembles die |
| Total | 310–590 h | 710–1,280 h |

At a loaded $150–$250/h (or your opportunity cost as SEL):
- Research stack: $50k–$120k of time
- Tiny-live stack: $120k–$280k of time
Plus 0.2–0.4 FTE ongoing (feed breaks, OPRA symbology, roll, vendor invoice fights)."

"**(5) Buy vs build — and the explicit 'do not build' crossover**

**Buy**
- Data plane: Databento (equities L2/L3 + OPRA hist) + one options API (Massive Advanced or Theta). Do not write a SIP decoder.
- Surface / GEX / dealer-flow dashboard: LiveVol or a positioning product if B-signals are the scarce skill. Building a production IV surface from OPRA ticks is a year.
- Execution / EMS: broker API. You will not beat IBKR/Tasty/DAS on a Mac.

**Build (on this Mac, Path R only)**
- Book-pressure features and MLOFI from already-normalized MBP-10.
- Triple-barrier, purged CV, meta-label, the 100-signal matrix, Arena-style honesty reports.
- Incremental inference and the cost model.
That split is the only version with a positive expected value for a one-person / two-person book.

**Verdict**

| Question | Answer |
|---|---|
| Can T091–T100 research + after-hours train + slow live inference run on a 128 GB M5 Max? | Yes, Path R, 60-day lookback, 150–400 names, conflated options. |
| Should you build the whole stack (feeds, surface, colo handler, ensemble)? | No. Buy feeds and the surface; build labels, CV, meta-gate, and features. |
| Year-1 cash (Path R comfortable) | Data $28k–$38k + machine you already own + $50k–$120k time. |
| Year-1 cash if you 'go institutional' | Data+colo $200k–$800k + a C++/FPGA hire. |

**Explicit crossover: a small operation should NOT build when any of these is true**
1. You need exchange-licensed non-display on a primary depth feed (Arca Integrated non-display alone is $11.3k/mo per category; NYSE Integrated $22.4k). That single line exceeds a serious research data budget.
2. You need colocation (matching-engine RTT, FPGA normalizer, A/B feeds). A Mac on residential or even a well-peered office circuit cannot be the book-pressure production sensor. Book-pressure alpha at seconds can live on the Mac; book-pressure alpha at microseconds cannot.
3. OPRA is used for automated trading / multi-process non-display and you are not prepared to file as such. Display-only pro fees (~$31.50) are a trap if the ensemble is a 'system.' Non-display categories stack.
4. You cannot show a purged-OOS, costed edge on Path R data first. If MBP-10 from Databento + Advanced options APIs do not produce a deflated Sharpe you would trade with your own money, buying TotalView + OPRA non-display will not create the edge. It will only make the same features more expensive and faster.
5. Headcount < 2 and AUM / personal risk capital cannot eat a $15k+/mo fixed data bill through a six-month dead period. Licensed feeds are a fixed cost; research APIs are cancellable.
Practical rule: stay on Path R until (a) a single family (A or B) has a CPCV Sharpe distribution you trust after 2–4 bps costs, and (b) capacity is limited by queue position / markout, not by feature research. Only then graduate one venue feed + one non-display category — and put that feed on a small Linux box in a cage, not on the M5 Max. Keep the Mac as the training / meta-label / Arena workstation.

*If you want a concrete shopping list next: Databento schema set (MBP-10 vs MBO), options vendor, and a 60-day disk budget for a 200-name vs 400-name universe.*"

---

## Q-TB10-3 — success ratios, after-cost efficacy, failure modes (verbatim)

"The documented pattern is consistent across these four literatures: depth and signed options flow add something over the naive one-number signal; a 100-signal stack usually does not, after costs and multiple testing. What follows is the evidence, then the five things worth building first on a Mac paper book."

"### (1) Multi-level book pressure vs touch-only

**What is documented.** Cont, Kukanov and Stoikov (2014) showed that top-of-book order-flow imbalance explains a large share of contemporaneous mid-price change (on the order of ~65% of variance in their setting). When they added a few deeper levels with OLS, the extra \(R^2\) was small. That is the 'touch is enough' folklore.
Xu, Gould and Howison (MLOFI) and Cont, Cucuringu and Zhang (multi-level / integrated OFI) revisited the same object with regularization and PCA across levels. Ridge on 10-level MLOFI cut out-of-sample RMSE 15–30% on small-tick names and 65–75% on large-tick names versus single-level OFI; coefficients on deep levels were significant once collinearity was handled. Integrated (PCA) OFI beat top-of-book for contemporaneous impact; multi-asset cross-impact added little contemporaneously once multi-level own-book OFI was in the model, but helped a bit for intraday forecasts.

**What that edge is — and is not.**
- It is mostly better measurement of the same pressure, not a new horizon. Top-of-book flickers; levels 2–10 describe absorbable depth. That helps seconds-to-minutes markout and swing filters (spread guards, refill penalties), not a daily alpha factory.
- Predictive power decays with horizon. Sub-second: touch dominates. Seconds: OFI / shallow MLOFI. Minutes: multi-level aggregates, weaker and conditional on replenishment failure.
- Incremental edge is largest on large-tick, thick-book names. On small-tick names the book is already noisy; 10 levels help less.
- You do not need MBO/queue position to harvest the documented MLOFI increment. MBP-10 is the object in these papers.

**After-cost reading for a Mac book.** The incremental \(R^2\) is real for explaining the mid. Converting it into net PnL requires holding through the same seconds the book is informative, paying spread, and not trading flicker. That is why persistence + spread guards matter more than adding levels 11–20."

"### (2) Options-flow → equity lead: times and who captures them

Three separate objects get lumped together. They have different clocks and different owners.

**A. Public surface (skew / smirk / IV spread).** Xing, Zhang and Zhao (2010): steepest OTM-put vs ATM-call smirks underperform the flattest by ~10.9% per year risk-adjusted; the gap is still there at 4–24 weeks (weaker after week 1, still ~6–7% over multi-week holds in their tables). High-skew names also post worse subsequent earnings surprises. Horizon is days to a quarter, not ticks.
Cremers–Weinbaum and Bali–Hovakimian: call-minus-put IV (volatility spread) predicts the other way (rich calls → higher stock returns). Later work notes a large part of IV-spread / skew predictability shrinks when high stock-borrow-fee names are dropped — the surface is partly a borrow-fee meter, not free alpha."

"**B. Signed, classified option volume (the actual 'flow lead').** Pan and Poteshman (2006), using CBOE open-buy volume that the public tape does not show: low put/call open-buy names beat high put/call by >40 bp the next day and >1% the next week; the effect fades after about a week. They split public vs non-public components and attribute the edge to non-public information of option traders, not to a slow stock market. Stronger on high-informed names and high-leverage contracts. Firm proprietary flow was not informative.
Follow-ons (e.g. signed O/S, Ge et al., Johnson–So): opening customer flow and OTM leverage matter; closing trades and MM/prop flow matter less. Embedded leverage is a main reason O/S predicts."

"**C. Who actually captures it.**

| Signal | Typical documented horizon | Who can see it | Who historically captured it |
|---|---|---|---|
| Open-buy put/call (PP 2006) | 1 day–1 week | CBOE classified volume; not raw OPRA | Researchers with that tape; desks that buy the classification |
| Public OPRA prints + inferred aggressor | noisier, shorter | Anyone with OPRA | Partial; inference error eats edge |
| Skew / smirk (XZZ) | weeks–months | Anyone with a surface | Slow cross-sectional longs/shorts; capacity-sensitive |
| IV spread | weeks | Public surface | Same, with borrow-fee confound |

Cao, Gempesaw and Simin (2018) document that measured informed trading in both stocks and options has declined, in line with weaker HF excess returns — the 1990s–2004 tape is not 2026 zero-DTE tape."

"**After-cost reading.** The cleanest lead in the literature used a dataset you will not have on a Mac. Public skew is slower, cheaper, and partly a short-sale-cost proxy. Inferring 'signed flow' from OPRA without open/close and customer flags is a different, weaker experiment. Do not write a 40 bp next-day number into a paper book that only has Massive/Theta prints."

"### (3) Large ensembles: does 100 beat the best 5?

**The statistical fact.** If you try \(N\) skill-less strategies and keep the max Sharpe, that max grows like \(\sqrt{2\log N}\). Bailey and López de Prado's False Strategy Theorem / Deflated Sharpe Ratio: with enough trials there is no raw Sharpe high enough to reject 'this is luck.' In a review corpus of ~92,500 fully costed strategies (crypto / US equity / FX), the single best in each asset class failed the multiple-testing null; deflated Sharpes on the winners were ~0.03 or ~0.
Bailey, Borwein, López de Prado and Zhu: with only five years of daily data, trying more than ~45 variations already makes SR ≥ 1 a plausible fluke. Hold-out does not fix this, because hold-out still assumes one test.
Aparicio and López de Prado: even Hansen's Model Confidence Set is not robust to multiple testing when SNR is typical of trading. 'Pick the best model from 100' is not a solved statistical problem in this noise regime.

**What stacking can do when it works.** Gu, Kelly and Xiu (2020) — the serious ML asset-pricing benchmark — get monthly OOS \(R^2\) around 0.4% for the best networks on a huge characteristic zoo. That is real, and tiny. It is also a monthly cross-section, not 100 microstructure transforms on one name. Meta-labeling (AFML) is the one ensemble pattern with a clean job: do not invent a 101st alpha; veto and size the primaries. That raises precision; it does not create information.

**Documented failure mode of '100 weak signals.'** The 100 are not 100 independent bets. Book OBI, MLOFI, trade OBI, depth slope, and micro-price are one factor with five names. Skew, RR, IV–RV, and put/call volume are another. A vote of 100 is often a leveraged vote of 5–8 families. When that shared factor dies (maker-taker change, zero-DTE, auction redesign), all 100 fail together. That is diversification theater, not diversification.

**Ensemble 'failures' in the relevant sense** (selection + costs, not a single famous blow-up):
- Academic factor zoos after costs and publication (McLean–Pontiff decay; Harvey, Liu, Zhu '…and the cross-section of expected returns'): most published characteristics do not survive multiple testing.
- The 92k-strategy DSR exercise: the in-sample champion is not a strategy.
- HFT / microstructure feature dumps: adding levels and windows improves in-sample \(R^2\) and dies OOS unless regularized (the OLS vs Ridge contrast in MLOFI is the small version of this).
Stacking 100 weak, correlated, same-horizon signals does not beat a cleaned best-5 after costs. Stacking economically distinct families with a meta-gate can beat any single family by trading less."

"### (4) Meta-lesson: complexity that added nothing after costs

Documented, not proverbial:
- Cont et al. 2014 vs later MLOFI: naively adding levels with OLS added almost nothing; complexity without the right estimator was noise. Ridge recovered the increment. Complexity ≠ information.
- Multi-asset cross-impact: extra terms did not help contemporaneous impact once multi-level own OFI was present. More model, same fit.
- Pan–Poteshman partition: the public piece of option volume was not the source of the lead. Building a more elaborate public-tape decoder does not recover the classified-tape result.
- IV-spread / skew after dropping high-fee names: a large fraction of the 'options lead' was borrow cost, not a surface oracle. Extra surface features would have fit the same confound.
- DSR / PBO: the winning specification in a 100-signal search is the complexity. After deflation it is often worth zero.
- Transaction costs in PP-style sorts: the newspaper version (62% per year) was pre-cost; even the authors said institutions might keep ~50% and everyone else much less. A retail Mac book paying 1–3 bps + spread on names that move 40 bp overnight does not own that paper.

The repeating mechanism: unregularized extra parameters fit microstructure noise or a fee; costs and a second sample remove them."

"## Honest bottom line for a one-person Mac paper book

Do not build T091–T100. Build five economically distinct, cheap-data, after-cost-plausible sleeves, then one meta-label veto. If those five have no purged-OOS edge after 2–4 bps, the other 95 will not grow one.

**Build first (in this order)**

| # | Sleeve | Why it survives the evidence | After-cost reason it belongs on a Mac |
|---|---|---|---|
| 1 | 10-level book pressure, minutes-to-hours, persistence + spread/refill gates | MLOFI increment over touch is documented; horizon matches MBP-10, not colo. | Databento MBP-10; few trades; size capped by displayed depth. Costs kill HFT versions, not a 8–45 min swing with K-bar persistence. |
| 2 | Public 30d 25Δ skew / smirk, 5–20 day equity hold, borrow-fee filter | XZZ-style predictability is public, weeks-long, and you can see it. | No classified tape required. Drop top-quintile borrow. Slow turnover; capacity is the risk, not the laptop. |
| 3 | Public signed-ish options print imbalance (call minus put delta-weighted volume), 1–5 day hold | PP shows the idea; public prints are a noisy cousin, not the same series. Treat as confirmation of (2), not as 40 bp/day. | Advanced options API. If it does not add to skew after costs, delete it. Do not pretend you have open-buy customer flags. |
| 4 | One slow cross-sectional residual (earnings-to-skew, or IV–RV cheapness) at weekly rebalance | Ties smirk to the earnings-surprise channel XZZ actually found. | EOD + surface. Almost no intraday tax. If this fails, your surface is not informing anything real. |
| 5 | Meta-label / veto on the union of 1–4 — not a 5th alpha | AFML's only ensemble result that matches the DSR lesson: size and pass, don't invent. | Trees on purged labels fit in 128 GB RAM. This is where 'ensemble' is allowed to exist. |

Do not build first: raw 100-signal vote, MBO queue models, multi-venue cross-impact, neural stackers on ticks, dealer-GEX clones without a positioning feed, or anything that needs NYSE/Nasdaq non-display to exist. Those are Path P costs in search of a Path R result.

**Operating rule.** One purged-CV harness, triple-barrier labels, costs inside the label, deflated Sharpe on the family (four primaries + one meta), not on 100 variants. If the best family DSR is not convincing after a year of paper with real vendor data, stop. That is the documented lesson of the 92k-strategy exercise, not pessimism."

---

## QC notes (orchestrator)

1. Q1 sizing-formula cell was truncated in the captured page text (mid-formula at "...min(1,"); preserved with an explicit extraction-truncation marker rather than guessed.
2. Q1 exponential-decay weights w ≈ (0.30, 0.21, 0.15, 0.11, 0.07, 0.05, 0.04, 0.03, 0.02, 0.02) sum to 1.00 — consistent with λ=0.35 decay.
3. Q1 worked example (C), event 3: Gross 1960 = 1400 × 1.4 (1.4× size), Net 1848 = 1960 − 112 (1.4 × $80/unit); internally consistent. Event 1: Gross 3100 → Net 3020 ($80 cost) ✓. Event 4: −2250 → −2330 ($80 cost) ✓.
4. Q1 worked example (B): stop 1.1×σ20 with σ20 = 1.32 implies stop distance 1.452, i.e. 49.13 from entry 50.58; the table says 49.26 — minor inconsistency in the worked numbers as produced.
5. Q2 M5 Max hardware spec (18 CPU / 40 GPU / ~614 GB/s) is Grok's own claim (Wikipedia-cited); treat as unverified.
6. Q3: "Ridge on 10-level MLOFI cut out-of-sample RMSE 15–30% on small-tick names and 65–75% on large-tick names" — the 65–75% figure may be a mis-phrasing (possibly R² on large-tick names, consistent with Q1's R² framing); flagged, preserved verbatim.
7. Key sourced claims are research leads, not verified facts: Cont, Kukanov & Stoikov (2014) (OFI); Cont, Cucuringu & Zhang (multi-level/integrated OFI); Xu, Gould & Howison (MLOFI); Xing, Zhang & Zhao (2010) (skew smirk ~10.9%/yr; ~6–7% over multi-week holds); Pan & Poteshman (2006) (>40 bp next day, >1% next week on open-buy put/call); Cremers–Weinbaum and Bali–Hovakimian (volatility spread); Bailey & López de Prado (False Strategy Theorem / DSR); Bailey, Borwein, López de Prado & Zhu (~45 variations with 5y daily data makes SR ≥ 1 a plausible fluke); Gu, Kelly & Xiu (2020) (monthly OOS R² ~0.4% for best nets); McLean–Pontiff decay; Harvey, Liu & Zhu ("…and the cross-section of expected returns"); Cao, Gempesaw & Simin (2018) (decline in measured informed trading); López de Prado, AFML (triple-barrier, meta-labeling, purged k-fold, embargo, CPCV). Vendor prices: indicative — verify before budgeting.
8. Grok's closing offers (AlphaForge spec encoding; Databento shopping list) were declined by inaction — no further task spawned.

---

## Source list (only papers actually used)

- Cont, R., Kukanov, A. and Stoikov, S. (2014), "The Price Impact of Order Book Events," JF (OFI; top-of-book ~65% variance explained).
- Cont, R., Cucuringu, M. and Zhang, C., "Price Impact of Order Book Events: Multi-Level / Integrated OFI."
- Xu, K., Gould, M.D. and Howison, S.D., "Multi-Level Order Flow Imbalance" (MLOFI).
- Xing, Y., Zhang, X. and Zhao, R. (2010), "What Does Individual Option Volatility Smirk Tell Us About Future Equity Returns?" (smirk predictability ~10.9%/yr; ~6–7% over multi-week holds).
- Pan, J. and Poteshman, A.M. (2006), "The Information in Option Volume for Future Stock Prices," JF (>40 bp next day, >1% next week on open-buy put/call).
- Cremers, M. and Weinbaum, D.; Bali, T. and Hovakimian, A., volatility spread.
- Gu, S., Kelly, B. and Xiu, D. (2020), "Empirical Asset Pricing via Machine Learning," RFS (monthly OOS R² ~0.4% for best nets).
- McLean, R.D. and Pontiff, J., publication decay.
- Harvey, C.R., Liu, Y. and Zhu, H., "…and the Cross-Section of Expected Returns."
- Bailey, D.H. and López de Prado, M., False Strategy Theorem / Deflated Sharpe Ratio.
- Bailey, D.H., Borwein, J.M., López de Prado, M. and Zhu, Q.J. (fluke-SR thresholds).
- Aparicio, D. and López de Prado, M., Model Confidence Set vs multiple testing.
- Cao, S.S., Gempesaw, D. and Simin (2018), decline in measured informed trading.
- López de Prado, M. (2018), *Advances in Financial Machine Learning* (triple-barrier, meta-labeling, purged k-fold, embargo, CPCV).
- Everything not attributed to one of the above — thresholds, cost figures, worked-example values — is illustrative.
