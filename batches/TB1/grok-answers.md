# TB1 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials (account: Praveen Gupta)
- Date: 2026-09-10
- Chat: https://grok.com/c/a92535b0-124a-4326-8fb3-63022d5b19d8
- Batch: TB1 — Flagship strategies (T001–T010)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim via page text extraction.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: LaTeX-rendering duplication de-duplicated; bracketed notes are the browser task's own capture notes, not Grok's text. Note: Q-TB1-3 as asked ended mid-sentence ("capacity notes,") — Grok answered all requested dimensions anyway.
- All numeric thresholds are illustrative examples, not estimated or claimed-optimal parameters. Nothing here is a live-trading spec.

---

## Q-TB1-1 — mechanics + worked example (verbatim)

### Shared execution convention (all three)

Causal timing: any signal is computed from information available at the close of bar t (or snapshot t). Orders are eligible only at the open of bar t+1 (or next snapshot). No same-bar fill.

Cost model used in the examples (illustrative):
• Round-trip commission: $0.005 per share each way ($0.01 RT per share)
• Spread cost: pay half-spread on entry and half-spread on exit (aggressive take)
• No slippage beyond that, no rebate, no borrow fee except where noted

Position sizing (common dollar-risk form): N = ⌊R / |P_entry − P_stop|⌋ where R is a fixed dollar risk budget per trade (examples use $200). For the pairs book, R is applied to the spread P&L, not to each leg independently.

### (A) OFI + queue-imbalance directional scalping

Papers. Order-flow imbalance and linear short-horizon impact: Cont, Kukanov & Stoikov, *The Price Impact of Order Book Events*, Journal of Financial Econometrics (2014). Queue imbalance as a one-tick-ahead mid-move classifier: Gould & Bonart, *Queue Imbalance as a One-Tick-Ahead Price Predictor in a Limit Order Book*, Market Microstructure and Liquidity (2015). Related LOB dynamics: Cont, Stoikov & Talreja (2010).

#### Universe
Liquid large-tick names where the touch is informative: e.g. top-of-book Nasdaq large-caps / liquid ETFs with one-tick or two-tick spreads and deep queues (SPY, QQQ, AAPL-class). Exclude names whose median spread > 3 ticks or whose L1 depth is unstable.

#### Session window
Regular session only. 09:45–15:45 ET. Skip the first 15 minutes (auction/unstable book) and last 15 minutes (imbalance/close effects). Flat at 15:45 ET.

#### Signals (computed at snapshot t)
Queue imbalance (Gould–Bonart): I_t = (q_b − q_a) / (q_b + q_a) ∈ [−1, 1], computed on L1 displayed size at the touch.
OFI over a short window of events Δ (example: last 100 events): OFI_t = Σ_events (Δq^b − Δq^a) with the usual event rules: bid-size increase or ask-size decrease ⇒ positive flow; opposite ⇒ negative.
Then z-score against a rolling baseline: z_t^OFI = (OFI_t − μ_OFI) / σ_OFI (examples: μ, σ from trailing 15 minutes, causal).

Illustrative entry (long) at close of t, fill at open of t+1:
• I_t ≥ +0.60 and z_t^OFI ≥ +1.5 (illustrative example thresholds)
• mid has not already jumped more than 1 tick in the last 5 s (avoid chasing)
• no existing position
Short mirrors: I_t ≤ −0.60 and z ≤ −1.5. Intended edge is a one-to-few-tick mid move, not a trend.

#### Exits
1. Signal flip: z_t^OFI crosses through 0 or I_t drops below 0.25 (illustrative).
2. Time stop: N bars after fill (e.g. 8 seconds on 1s bars, or 8 events).
3. Stop-loss: −2 ticks against entry mid (illustrative).
4. Target: +1 tick mid (take when mid prints through). First of these four fires. Flat at 15:45 ET.

#### Sizing
Risk R = $200. Stop is 2 ticks. If tick = $0.01, risk per share = $0.02, N = 10,000 shares (cap by ADV / max notional). Cap example: N ≤ min(0.5% of 1-min ADV, $250k notional) — illustrative example caps.

#### Causal fill
Signal at snapshot t ⇒ marketable order at the open of t+1 (hit ask to buy, hit bid to sell).

#### Worked synthetic example (long scalp)
Synthetic L1 at t:
• bid 8,000 × 100.00, ask 100.01 × 2,000 → I_t = 0.60 (passes)
• OFI z_t^OFI = +1.8 (passes)
• mid = 100.005; t+1 open fill (buy): pay ask 100.01 → outlay 10,000 × 100.01 = 1,000,100

Assume mid ticks up; at exit bar we sell at bid 100.02 (1-tick winner on the quoted market; mid went 100.005 → 100.025).

| Line | Calc | $ |
| Gross proceeds | 10,000 × (100.02 − 100.01) | +100.00 |
| Entry half-spread already in fill (paid ask vs mid 100.005) | embedded | (in gross) |
| Exit half-spread (sold bid vs mid 100.025) | embedded | (in gross) |
| Commission RT | 10,000 × 0.01 | −100.00 |
| Net | 100.00 − 100.00 | 0.00 |

2-tick mid win with the same fills (sell 100.03) would be gross $200. That is why this sleeve only works if (i) you sometimes capture more than one tick, (ii) you get queue position / rebate, or (iii) costs fall. The baseline math here is break-even on a 1-tick scalp after $0.01/share RT fees on 10,000 shares.

### (B) RVOL-filtered opening-range breakout

Papers / sources. Classic ORB: Toby Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990). RVOL / "stocks in play" filter that materially changes ORB results: Zarattini, Barbon & Aziz, *A Profitable Day Trading Strategy for the U.S. Equity Market* (Swiss Finance Institute research; 5-minute ORB + relative opening volume, 2016–2023 sample). Volume-spike / "in play" literature: Gervais, Kaniel & Mingelgrin (2001) on high-volume return premiums.

#### Universe
US listed equities, example gates (illustrative, in the spirit of that paper):
• [first bullet text did not render — see QC note]
• 14-day ADV ≥ 1 million shares (illustrative)
• 14-day ATR ≥ $0.50 (illustrative; skip dead names)
• that morning's opening-range relative volume in the top cohort (example: OR RVOL ≥ 1.5× same-slot 20-day average, then keep top 20 names)
• Futures analogue: ES/NQ with session RVOL ≥ 1.3 (illustrative)

#### Session window
Example construction: 09:30–09:45 ET (15-minute OR). Signals allowed 09:45–15:30. Flatten 15:55.

#### Signals at bar t (5-minute bars)
Let H_OR, L_OR be the high/low of 09:30–09:45, frozen after 09:45. RVOL_OR = V_OR / median same-slot volume, last 20 sessions.
Long trigger (illustrative): first 5-minute bar t ≥ 09:45 whose close > H_OR and that bar's own RVOL ≥ 1.2× its 20-day same-slot median (illustrative). Short: close < L_OR with the same RVOL gates. One trade per name per day; no re-entry after a stop.

#### Exits
1. Stop-loss: opposite side of the OR (long stop L_OR). Alternative used in some ORB variants: 1× 14-period 5-min ATR; here we use OR invalidation.
2. Target: +1× OR range beyond the break level (illustrative 1R).
3. Time stop: still open at 15:55 ⇒ market on close.
4. No "signal flip" other than stop: once the range is broken, the level is done for the day.

#### Sizing
N = ⌊R / (P_entry − P_stop)⌋ for a long (R = $200).

#### Causal fill
Close of breakout bar t prints the signal ⇒ buy the open of bar t+1. Gap-through means fill at worse than the signal print — model that.

#### Worked synthetic example (long)
Name XYZ. OR 09:30–09:45: high 50.40, low 49.80; range 0.60 (passes RVOL gate). Bar 09:45–09:50 closes at 50.48, bar RVOL 1.6× (passes 1.2×). Fill at 09:50 open: 50.50 (gap through). R = $200. Risk/share = 50.50 − 49.80 = 0.70 → N = 285 shares. Target = 50.40 + 0.60 = 51.00. Assume target hits at 51.00 (we take the offer/bid: sell 50.99 after $0.01 spread).
Spread assumption: $0.02 wide; we paid $0.01 on entry vs mid and $0.01 on exit.

| Line | Calc | $ |
| Gross | 285 × (50.99 − 50.50) | 139.65 |
| Commission RT | 285 × 0.01 | −2.85 |
| Extra spread beyond mid-to-mid (already in 50.50/50.99 vs theoretical 50.49/51.00) | leftover ≈ 285 × 0.01 | (in gross) |
| Net (using actual fills 50.50 / 50.99) | 139.65 − 2.85 | 136.80 |

Stop-loss example: If instead price failed and stopped at L_OR = 49.80 (exit 49.79):
| Line | Calc | $ |
| Gross | 285 × (49.79 − 50.50) | −202.35 |
| Commission | 285 × 0.01 | −2.85 |
| Net | −202.35 − 2.85 | −205.20 |

That is slightly worse than the $200 budget because of gap-through entry and exit spread — the reason the risk formula should use expected fill, not the signal print.

### (C) Cointegration z-score pairs with OU half-life exits

Papers. Cointegration: Engle & Granger, *Co-integration and Error Correction*, Econometrica (1987). Empirical pairs: Gatev, Goetzmann & Rouwenhorst, *Pairs Trading: Performance of a Relative-Value Arbitrage Rule*, Review of Financial Studies (2006). Spread as OU / half-life for holding horizon: standard in Chan (*Algorithmic Trading*, 2013) and Leung & Li (*Optimal Mean Reversion Trading*). OU process: Uhlenbeck & Ornstein (1930).

#### Universe
Pre-selected pairs that pass, on a rolling formation window (example: 60 RTH days of 5-minute mid log-prices):
• Engle–Granger residual ADF rejects unit root at 5% (illustrative)
• hedge ratio β̂ from OLS: r_{A,t} = α + β r_{B,t} + ε_t (or log-prices)
• OU half-life of residual in intraday-tradable band: 10–90 minutes (illustrative)
• both legs liquid, borrowable, same listing session
Example pair: two same-sector liquid large-caps, or an ETF vs a tight basket. One pair in the worked example.

#### Session window
RTH 09:45–15:45. No new entries after 15:00. Formation uses prior days; z-score uses an intraday expanding or rolling window of the residual that does not include bar t (causal).

#### Signals at bar t
Spread: s_t = ln P_A − β̂ ln P_B (or linear residual). Fit discrete OU on the formation residual: Δs_t = a + b s_{t−1} + e_t, κ = −ln(1+b)/Δt, t_{1/2} = ln 2 / κ.
Illustrative entry:
• short the spread if z_t ≥ +2.0 (short A, long B)
• long the spread if z_t ≤ −2.0

#### Exits
1. Mean reversion: z_t crosses ±0.25 toward zero.
2. OU time stop: hold no longer than 2 × t_{1/2} (example: half-life 20 min → max 40 min).
3. Stop-loss: z_t reaches 3.5 against the position (illustrative; relationship may have broken).
4. Session flatten 15:45.

#### Sizing
Dollar risk on the spread: if stop is s_stop dollars of spread per 1 share of A (and β̂ of B), N_A = ⌊R / s_stop⌋, N_B = round(β̂ N_A). Dollar-neutral variant: set notionals so N_A P_A = N_B P_B and convert stop to that unit; the example uses the residual-risk form.

#### Causal fill
z_t from mids at close of t; lift/hit both legs at open of t+1.

#### Worked synthetic example (short the spread)
Mids at signal bar t: P_A = 80.00, P_B = 40.00, β̂ = 1.80, but rolling μ̂ = −0.40, σ̂ = 0.20. Wait — use a consistent residual. Set: s_t = +0.50, μ̂ = 0, σ̂ = 0.25 ⇒ z_t = +2.0 (entry). Prices consistent with that residual: P_A = 80.40. Stop at z = 3.5 ⇒ s_stop = 0.875. Risk per 1 share A: 0.875 − 0.50 = 0.375. N_A = ⌊200/0.375⌋ = 533. N_B = round(1.80 × 533) = 959. t+1 open fills (pay the spread on both legs): Short A at 80.41 (bid/ask 80.40/80.42, we sell the bid). Long B at 40.01. Assume half-life [value did not render] min; after 12 minutes z_t hits 0.25. Exit mids: Cover A at 80.01, sell B at 39.99. Borrow: ignore (or 5 bps would round down to zero on one day).

P&L by leg:
| Leg | Shares | Entry | Exit | Gross $ |
| A short | 533 | 80.41 | 80.01 | 533 × 0.40 = 213.20 |
| B long | 959 | 40.01 | 39.99 | 959 × (−0.02) = −19.18 |
| Gross | | | | 194.02 |
| Commission 4 fills | (533+959) × 2 × 0.005 | | | −14.92 |
| Net | | | | 179.10 |

Line-by-line economic read:
• Most of the money is the A-leg mean reversion ($213).
• The hedge B is almost flat (−$19) because β̂ was the cointegrating offset, not the alpha.
• Four-way fees eat ~$15.
• If instead z_t ran to 3.5 and we stopped: spread loss ~$200 plus the same ~$15 fees and extra spread — net about −$220.

### Honest constraints (so these do not get treated as "complete alpha")
• Cont et al. document a contemporaneous OFI–mid relation with high R²; Gould–Bonart document next-tick direction predictability, stronger on large-tick names. Neither paper hands you a net-of-fees scalable strategy.
• Unfiltered ORB is weak; the Zarattini–Barbon–Aziz result is that RVOL / stocks-in-play selection is doing most of the work, and published figures are not a promise that 1.5× / 15-minute / top-20 still work.
• GGR (2006) is a daily distance method on a 1962–2002 sample; Engle–Granger + OU half-life is the modern specification, but β̂ is unstable intraday, and two-leg costs dominate short half-lives. Half-life is a clock for the time stop, not a guaranteed exit price.
• If you want these three encoded as AlphaForge specs (signal schema, fill model, cost ledger, no look-ahead), say the word.

---

## Q-TB1-2 — infra + local build + buy vs build (verbatim)

The M5 Max is not the constraint. 128 GB / 614 GB/s will idle through A–C if you keep universes small and do not rebuild a full-tape MBO book. The constraint is what the feed actually is, plus exchange license language for anything resembling TotalView. Paper-trading does not waive Nasdaq non-display fees if you consume a proprietary depth feed.

Machine context: 18-core CPU, up to 40-core GPU, 128 GB unified, ~614 GB/s. Trading loops here are CPU + network, not GPU. Leave the GPU for overnight research / local models.

### What must be running while the cash session is open
Think in four processes, not three strategies.

| Process | Hours (ET) | Job |
| Clock / calendar | 04:00–20:00 | NYSE calendar, early close, halt flags, DST. Kill switch if clock skew > 50 ms vs NTP. |
| Feed ingest | 09:15–16:05 | WebSocket or normalized MBP/MBO → ring buffers. Heartbeat watchdog every 1–2 s. |
| Feature / signal loops | strategy-specific | Causal features only; signal stamped at bar/snapshot t, order intent queued for t+1. |
| Paper broker + ledger | session | Fills, fees, positions, flatten-at-close. Persist every event to disk. |

Shared services (always on during RTH): reference data (splits, halt, LULD), risk caps, structured logs (JSONL), Prometheus-style counters. Do not keep a 70B LLM in the hot path. Inference on this box is for post-session review.

### Per-strategy runtime

#### (A) OFI + queue imbalance — the only "hot" loop
Feed required (honest): L1 NBBO is not enough for Cont–Kukanov–Stoikov OFI. You need event-level size changes at the touch (at minimum MBP-1 / TBBO with exchange timestamps), preferably Nasdaq TotalView MBO or MBP-10 on a short list of large-tick names. SIP quotes smear multiple venues and hide cancel/add identity.

Intraday processes:
1. Incremental book (or touch-only state) per symbol.
2. Event window aggregator: OFI over Δ (example 100–500 ms or last N events).
3. I_t = (q_b − q_a) / (q_b + q_a) on every book update.
4. Rolling μ, σ of OFI (EWMA, causal).
5. Signal → enqueue marketable paper order for next snapshot.
6. Time-stop / flip / 2-tick stop manager on a 10–50 ms timer.

Universe for a one-person paper book: 5–20 names, not the tape.

Throughput (order-of-magnitude, Nasdaq-listed liquid names):
• Touch events: 1k–20k/s per busy name at the open; 100–2k/s midday.
• 10-name book: peak ~50–100k events/s, average far lower.
• CPU: 1–2 P-cores if you parse a normalized API (Databento-style). 4–8 cores if you parse raw ITCH yourself.
• RAM: 200–800 MB hot state for 10 names MBP-1; 2–8 GB if you keep a few minutes of MBO for replay.
• Disk: 5–30 GB/day if you record MBO for those names; 0.5–2 GB/day if you persist only features + decisions.

Safe-mode on feed outage:
• Missed heartbeat > 2 s or gap in sequence numbers → flatten A immediately, freeze new entries, tag session DEGRADED.
• Do not interpolate OFI. A stale book is a false I_t.
• Resume only after a full snapshot rebuild + 30 s of clean sequence.
• If only SIP L1 remains: A is off. B and C may continue.

#### (B) RVOL-filtered 15-minute ORB
Feed required: SIP or equivalent trades + 1-second or 5-minute OHLCV + official session clock. Auction imbalance is useful but not mandatory for the spec we wrote.

Intraday processes:
1. 09:25: load 20-day same-slot volume medians (precomputed overnight).
2. 09:30–09:45: accumulate OR high/low/volume per candidate (example 200–500 names after cheap ADV/price/ATR gates).
3. 09:45: freeze OR, compute RVOL_OR, rank, keep top 20.
4. 09:45–15:30: on each 5-minute close, test break + bar RVOL; signal → fill at next bar open.
5. 15:55: flatten.

Throughput: trivial. 500 names × 5-min bars is ~6k bars/day. 1-second bars for RVOL confirmation: ~2M bars/day across 500 names — still nothing for this Mac.
• RAM: 100–400 MB
• Disk: 50–300 MB/day of bars + decisions
• CPU: one core, bursty at 09:45

Safe-mode:
• If the open print or first 15 minutes of volume is incomplete for a name → exclude that name for the day (do not invent OR).
• If the whole tape stalls before 09:45 → no B trades that day.
• If feed dies after entry: keep the resting paper stop at L_OR / H_OR using last valid quote; if quotes also die → flatten at last trade and mark UNTRUSTED_FLAT.
• Early-close calendar miss is a real bug: bake NYSE holidays into the clock process.

#### (C) Cointegration z-score + OU half-life
Feed required: clean 1-minute or 5-minute mids (trades+quotes) for a handful of pairs. Depth not required. Need borrow flags only if you ever go live; paper can stub them.

Intraday processes:
1. Overnight / 09:00: load frozen (α̂, β̂), ADF pass/fail, κ̂, t_{1/2}. Do not re-estimate β on the live bar.
2. RTH: update residual s_t, causal rolling μ̂, σ̂, z_t.
3. Entry at |z| ≥ 2; exits: z → 0, 2 × t_{1/2}, or |z| ≥ 3.5.
4. Two-leg paper orders submitted together; if one leg rejects, cancel the other (leg-risk kill).

Throughput: tens of pairs × 1-minute bars. Noise.
• RAM: 50–200 MB + whatever history you keep for the rolling z (keep 1–2 sessions in RAM).
• Disk: 10–50 MB/day
• CPU: idle

Safe-mode:
• One leg missing quotes > 5 s → flatten both legs.
• Halt on either name → flatten.
• t_{1/2} or β refresh is not an intraday job; if overnight job failed, C stays dark.
• Spread computation must use the same vendor timestamps on both legs; mixed SIP vs prop feeds will fake cointegration.

### Daily schedule (one box)
| ET | What |
| 07:30 | Health: disk, NTP, feed auth, yesterday's ledger checksum |
| 08:00–09:15 | Warm reference data, load OR volume medians, load pair betas |
| 09:15 | Connect feeds, subscribe, snapshot books |
| 09:30–09:45 | B: build OR. A: optional warmup, no trades until 09:45 |
| 09:45–15:45 | A+C live; B live after OR freeze |
| 15:45–15:55 | A/C flatten; B last exits |
| 16:05 | Disconnect, compact logs |
| 16:30–18:00 | Research batch: rebuild features, OU fit, RVOL medians for T+1 |
| Weekend | Full replay tests, license/usage report |

### RAM / storage budget on 128 GB
| Use | RAM | Storage |
| OS + browsers + IDE | 8–16 GB | — |
| A ingest + books (10 names, MBP-1) | < 2 GB | 5–30 GB/day raw if recorded |
| B + C | < 1 GB | < 1 GB/day |
| Overnight research (pairs OLS, ADF on 60 days × 5-min) | 2–8 GB | 50–200 GB history if you keep 1–2 years of 1-min + selected MBO |
| Optional local LLM (do not colocate with A) | 40–80 GB | models on disk |
| Headroom | plenty | size the SSD for A recordings; that is the only large writer |

You will not hit 128 GB unless you record full-tape MBO or load a large model during RTH. Don't.

### Engineering hours (one person, paper-quality, not colo)
Assumes you already write Python comfortably and accept vendor-normalized data.

| Slice | Hours | Notes |
| Clock, logging, paper ledger, flatten | 20–40 | Do this once |
| Feed client + watchdog + replay | 30–60 | Vendor SDK vs raw ITCH is a 3× multiplier |
| A book + OFI + I + execution timing | 80–150 | Most of the real work; correctness of event rules |
| B OR + RVOL rank + 5-min state machine | 25–40 | Easy; universe hygiene is the time sink |
| C EG residual, OU half-life, two-leg FSM | 40–70 | Stats are short; pairing + halt/leg-risk is longer |
| Backtest alignment vs live (no look-ahead) | 40–80 | Where paper systems usually lie |
| Total greenfield | ~240–440 h | ~2–3 months part-time, or 6–8 focused weeks |

Raw ITCH parser + multi-venue book: add 150–300 h and still will not match a colocated firm. For paper, do not build that.

### Buy vs build (one-person paper operation)

#### Verdict in one line
• B and C: buy the platform + a cheap real-time bar/quote feed. Build only the signal code.
• A: buy a normalized depth/MBO API. Do not build ITCH. Do not use Composer. QuantConnect SIP will not honestly implement A.

#### Retail platforms
| | Fits A? | Fits B/C? | Indicative $ | Call |
| QuantConnect paper | No (SIP/equity stream, not event-level Nasdaq book) | Yes for B; weak-but-usable for C | Researcher ~$60/mo; live-capable tiers ~$120–$300/mo; US equity data bundled on their feed | Good paper host for B. C ok on minute bars. A would be cargo-cult. |
| Composer-style no-code | No | No (ORB/RVOL maybe as a toy; no pairs OU, no OFI) | typically ~$10–50/mo class | Skip |
| LEAN local + IB paper | Still no real OFI | B/C yes | IB paper free; market data subscriptions extra | Fine if you already have IB |

#### Professional / semi-pro feeds
| Feed | What you actually get | Indicative $ | Use for |
| Massive / Polygon Stocks Advanced | SIP real-time trades + quotes, seconds/minutes | ~$199/mo individual | B and C live paper. Not A. |
| Databento US Equities + Nasdaq TotalView | MBO / MBP-10 / TBBO, live in paid plans | Plan ~$1.5k–$4k/mo class plus Nasdaq license pass-through (TotalView often ~$1.6k firm + per-user; non-display/professional) | A, and research replay. Overkill for paper P&L theater. |
| Databento "Mini" / free-license venues | thinner tape, $0 exchange license | much cheaper | Not a substitute for Nasdaq touch OFI on AAPL/QQQ |
| IBKR market data | bundled quotes for paper | tens–low hundreds / mo if you already have IB | B/C only |

Exchange licenses are the surprise bill. Personal "non-professional" SIP is cheap. TotalView non-display for a trading model is professional, even if the account is paper. Confirm with the vendor before you subscribe; do not assume hobby pricing.

#### Precomputed analytics
Buy history, not "alpha."
• Databento historical MBP-1/MBO for A calibration: usage-based, often tens–low hundreds of $ for a few names × months, not thousands, if you stay tight.
• OR volume medians and pair half-lives: compute yourself overnight on this Mac (hours, not a product).
• Do not buy a $2k/mo "order-flow signal" SaaS for paper. You cannot audit their t → t+1 causality.

#### Recommended stack for this operation
Phase 0 (week 1–2), ~$200–400/mo
• Massive Advanced or QC paper + minute/second bars
• Implement B and C only
• Paper ledger on the Mac
• Verdict: this is the honest one-person setup

Phase 1 (if A is the research goal), ~$2k–6k/mo all-in
• Databento live TotalView (or MBP-1 if they can certify event sizes at the touch) + licenses
• 5–10 symbols only
• Record everything, compute OFI locally
• Still paper. Still not colo latency. Goal is statistical honesty, not capturing one tick live.

Do not build: matching engine, SIP consolidator, FPGA, GPU feature server.

### Feed-outage matrix (print this next to the desk)
| Failure | A | B | C |
| WS heartbeat miss > 2 s | Flatten, disable | Hold existing OR trade with stop; no new entries | Flatten both legs |
| Sequence gap / book tear | Rebuild snapshot or disable | n/a | n/a |
| Missing open auction / first 15 min volume | — | Skip name or skip day | — |
| Single-leg quote hole | — | — | Flatten pair |
| Vendor stale (timestamps stop advancing) | Disable | Disable new entries | Flatten |
| Local process crash | On restart: flat. Never recover a live paper position from RAM. Reload ledger from disk. | same | same |
| Clock skew | Halt all | Halt all | Halt all |

Restart policy: positions are not stateful in memory. The ledger file is source of truth. After any crash you are flat unless the ledger says otherwise and the feed has been healthy for 30 s.

### What the M5 Max is actually good for here
Use it after 16:00: replay A's recorded events, grid half-lives, walk-forward Engle–Granger, and only then optionally a local model for journal text. During 09:30–16:00 the right picture is a quiet Python/Rust ingest, a few hundred MB of books, and a watchdog. If the fans spin at 10:12 ET, you put the LLM on the hot path and A is no longer causal.

---

## Q-TB1-3 — success ratios, after-cost efficacy, failure modes (verbatim)

Documented numbers only. Where a paper does not report Sharpe or bps-per-trade, that absence is stated. "After cost" means the study subtracted at least commissions; whether it also subtracted spread, impact, and short fees is called out separately.

### (A) OFI / queue-imbalance scalping — non-colocated

There is no peer-reviewed study that shows a non-colocated taker making money after fees on public OFI or queue imbalance. The canonical papers measure prediction, not net P&L.

| Source | Market / period | What they report | Costs in the study? |
| Cont, Kukanov & Stoikov (2014), J. Fin. Econometrics | 50 S&P 500 names, NYSE TAQ, Apr–Jun 2010 | Linear Δ mid = β ⋅ OFI; mean R² ≈ 65%. OFI beats trade imbalance (R² ≈ 32%). | No P&L, no fees. Contemporaneous impact, not a delayed fill. |
| Gould & Bonart (2015), Mkt Microstructure & Liquidity | 10 Nasdaq names | Next-mid direction: logistic fit; binary classification vs null improves ~50–60% on large-tick names, ~10–30% on small-tick. P(up \| I ≈ 1) ≈ 0.8–0.9 large-tick, 0.6–0.7 small-tick. | No trading rule, no costs. They explicitly study classification, not arbitrage. |
| Lipton, Pesavento & Sotiropoulos (2013) / related quote-imbalance work | Equities LOB | Expected mid move given imbalance is typically well below one spread. | Qualitative: "not a straightforward statistical arbitrage." |

The paper that does put fees on an imbalance taker. A 2025 microstructure study of maker vs taker imbalance rules finds the taker is profitable before fees (~+1 bp per round-trip) and unprofitable after the taker fee. Reported post-fee mean return on the imbalance-taker book: about −2.0 [unit not rendered — context implies bps] (same units as their table; holding time ~15 s; 18,927 trades). Maker variants are also negative after fees. Pre-fee edge dies in the fee.

Implication for a Mac / non-colo trader. Public I_t and OFI are visible to every colocated MM. The documented mid move is a fraction of the spread. A take-liquidity round trip on a 1-tick name is already ~1 tick of spread plus ~0.1–0.3 ¢/share fees — same order as the signal. Capacity of a taker OFI scalp is near zero once more than a few lots hit the touch; the literature's useful use of OFI is when not to get filled (adverse-selection filter for a maker), not a standalone directional book for someone 10–40 ms off-exchange. Sharpe / hit-rate / bps for non-colo A: not in the academic record as a positive after-cost number. Treat any backtest that fills at the mid on the signal bar as invalid.

### (B) Opening-range breakout after costs, modern tape

Two related papers from the same group, plus independent replication.

#### Unfiltered 5-minute ORB (US cash equities)

Zarattini, Barbon & Aziz, *A Profitable Day Trading Strategy for the U.S. Equity Market* (SSRN 4729284 / SFI WP; 2016–2023, >7,000 US stocks). Costs in the paper: $0.0035/share commission (IB Pro tiered, end-2023). Starting NAV $25,000. Not a full spread+impact model.

| Variant | Total return | IRR | Sharpe | Hit rate | Alpha | Beta |
| ORB base (no RVOL filter) | +29% | 3.2% | 0.48 | 41.4% | 3.3% | 0.01 |
| S&P 500 (same window) | +198% | 14.2% | 0.78 | 54.9% | — | 1.00 |

Unfiltered ORB loses to the index after their commission assumption. Hit rate < 50%.

#### RVOL / "stocks in play" filter (same paper, same cost)

Top 20 names by opening relative volume:
| Variant | Total net | IRR | Vol | Sharpe | Hit rate | Max DD | Alpha |
| ORB + Rel Vol | +1,637% | 41.6% | 14.8% | 2.81 | 48.4% | 12% | 35.8% |

Authors state the SIP filter benefit holds "even after considering transaction costs." Costs modeled = commission only. Capacity: 20 names/day, $25k notionally; they do not publish a capacity schedule. Live book of size would move the same names everyone else is scanning.

#### Same authors, QQQ-only 5-min ORB (SSRN 4416622, 2016–2023)

Commission netted. Reported Sharpe ~1.12, ~31% annualized, ~51/49 long/short, alpha vs QQQ ~33% net of commissions. Independent replication (same rules, 1,775 vs 1,795 trades) gets Sharpe 1.06 with zero slippage, gross edge $0.070/share. Net crosses zero at ~2.2 ¢/share slippage. With 2 ¢ entry / 4 ¢ stop slippage: Sharpe 0.23, t-stat 0.52. QQQ spread is ~1 ¢ — the published edge sits inside the spread.

Caveat stack for B
• Headline Sharpe 2.81 is commission-only, on a publication-sample RVOL sort, $25k compounding, no market-impact, no borrow, no PDT-constraint binding.
• Hit rate stays ~48% even in the good variant — expectancy is in the right tail of RVOL days, not in win rate.
• Unfiltered modern ORB after a cheap commission is Sharpe < 1 and underperforms SPX.
• ETF-only replications are fragile to a few cents of slippage and to post-publication windows.

### (C) Equity pairs after crowding (Do–Faff onward)

Baseline before the crowding papers: Gatev, Goetzmann & Rouwenhorst (2006), US 1962–2002, daily distance pairs. ~11% annualized excess on top-pair portfolios; they argue profits exceed a conservative cost estimate and use a one-day wait to blunt bid-ask bounce. That is the pre-crowding benchmark, not the current one.

#### Do & Faff — profitability decay (gross)

*Does Simple Pairs Trading Still Work?*, FAJ (2010). Top-20 pairs, delayed entry, monthly excess on employed capital:
| Period | Mean monthly excess |
| 1962–1988 | 0.86% |
| 1989–2002 | 0.37% |
| 2003–2009 | 0.24% |

Still positive in crises (2000–02, 2007–09). Costs not fully subtracted here.

#### Do & Faff (2012) — the after-cost paper

*Are Pairs Trading Profits Robust to Trading Costs?*, J. Financial Research. US 1963–2009. Costs: commissions + market impact + short-sale fees (one-way friction 0.81% in 1963–88, 0.33% in 1989–2009; shorting ~1% annualized prorated).

| Object | Number |
| Baseline 20-pair hedge after friction | unprofitable |
| 29 "refined" variants, net monthly | −0.07% to +0.35%, average +0.12% |
| Best intra-industry four, net monthly | +0.29% (~3.5% annualized) |
| Same four, largest 30% of stocks | +0.19%/mo |
| Risk-adjusted, well-matched industry pairs | ~30 bps/month |
| Large-cap implementation | ~24 bps/month alpha |
| Post-2002 | "largely unprofitable" for both pairs and industry reversal |

That is the crowding result: GGR-style ~90 bps/month gross compresses to ~19–38 bps/month net in the synthesis literature, then to indistinguishable from zero after 2002 on the plain rule.

#### After 2009 (replications)

Independent GGR replication through 2020: post-GFC monthly excess 0.04–0.07%, not significant, before full costs. Equity curve "mostly flat after 2009."

#### Cointegration vs distance, with time-varying costs

Rad, Low & Faff (2016 working paper; US 1962–2014):
| Method | Gross monthly excess | Net of time-varying costs |
| Distance | 91 bps | 38 bps |
| Cointegration | 85 bps | 33 bps |
| Copula | 43 bps | 5 bps |

From 2009, distance and cointegration trade frequency collapses; copula frequency holds up but net is already ~5 bps/month over the full sample. Alphas vs standard factors remain positive in-sample; liquidity factor loads negative (you are paid for providing liquidity / being crowded).

#### Jacobs & Weber (2015)

34 countries, 2000–2013: ~8–9% annualized gross event-time / three-factor alpha for the average country — gross, attention- and limits-to-arbitrage-dependent, stronger on obscure pairs. Not a net-of-cost capacity statement for liquid US names.

Capacity. GGR/Do–Faff books are 20 pairs, six-month holding, daily rebalance. That is a slow, low-Sharpe, low-capacity relative-value sleeve — not an intraday OU book. Intraday half-life exits multiply two-leg costs; those papers do not validate that design after fees.

### Cross-walk for a one-person paper book

| Sleeve | Best documented after-cost figure | What that figure omitted | Non-colo / retail translation |
| A | Taker imbalance: pre-fee ~+1 bp RT, post-fee negative | Colo queue position, maker rebates | Do not expect a SIP or home-Mac taker Sharpe. Use OFI as a no-trade filter, if at all. |
| B | Unfiltered ORB: Sharpe 0.48, +3.2% IRR after 0.35 ¢/share. Filtered top-20 RVOL: Sharpe 2.81, +41.6% IRR, hit 48% — same commission. QQQ-only edge dies at ~2 ¢/share slippage. | Spread, impact, capacity of the RVOL sort | Commission-only Sharpe is not executable Sharpe. Filter is the strategy; ORB alone is not. |
| C | Best industry pairs: ~30 bps/month net (1963–2009), ~24 bps on large caps; plain rule dead after 2002; 2009–2020 replications ~0–7 bps/month gross. Cointegration net ~33 bps/month over 1962–2014, then opportunity scarcity. | Intraday holding, two-leg simultaneous fills | Daily GGR is the evidence set. Intraday OU pairs are an extra cost layer the crowding papers never blessed. |

None of these papers is a live allocation memo. The honest reading: A is a prediction result that fees consume; B's published Sharpe is real only under a tight RVOL sort and thin cost model; C's after-cost edge was already a few tens of bps per month a decade ago and has been crowded toward zero in liquid US names since the early 2000s.

---

## QC notes (orchestrator)

1. Q1-(C) worked example: Grok wrote a visible false start it then corrected ("Wait — use a consistent residual"): initial sketch s_t = 80 − 1.80×40 − 8 = 0 with μ̂ = −0.40, σ̂ = 0.20, corrected to s_t = +0.50, μ̂ = 0, σ̂ = 0.25 ⇒ z_t = +2.0. However, with the implied linear spread form s = P_A − 1.8·P_B − 8, Grok's "consistent" price P_A = 80.40 yields s = 0.40, not the s_t = 0.50 used for the stop (0.875), risk (0.375), and share counts — an arithmetic inconsistency in the worked example.
2. Q1-(C) worked example: the half-life numeric value ("Assume half-life … min") did not render in text extraction; the exit-rule section separately gives "half-life 20 min → max 40 min" as the example.
3. Q1-(B) universe list: the first bullet's text did not render in either text extraction or the accessibility tree (context suggests a price gate, but that is unverified); not reconstructed.
4. Q1-(B) worked example: "Net (using actual fills 50.50 / 50.99): 139.65 − 2.85 = 136.80" — the "Extra spread beyond mid-to-mid… leftover ≈ 285 × 0.01" row is stated as embedded in gross, not additive; arithmetic checks out (285 × 0.49 = 139.65; minus 2.85 commission = 136.80).
5. Q1-(C) signals section: the OU-fit sentence had a garbled fragment in extraction; the discrete-OU formula Δs_t = a + b·s_{t−1} + e_t, κ = −ln(1+b)/Δt, t_{1/2} = ln 2/κ was captured intact.
6. Q2: minor extraction artifacts only (link-name fragments like "Quantt"/"Qveris" in table cells); all figures, prices, and tables captured.
7. Q3: "about −2.0 (same units as their table; holding time ~15 s; 18,927 trades)" — the unit did not render; surrounding context ("~+1 bp per round-trip" pre-fee) implies bps, but the unit is unverified.
8. Q3: the RVOL-filter result table header row rendered as raw markdown; reconstructed from the row values (+1,637% / 41.6% / 14.8% / 2.81 / 48.4% / 12% / 35.8%).
9. Q-TB1-3 as asked ended mid-sentence ("capacity notes,") — Grok nevertheless answered all requested dimensions (Sharpe/hit-rate/bps, market/period, capacity, cost caveats); no information was requested back.
10. Key sourced claims are research leads, not verified facts: Cont–Kukanov–Stoikov 2014 (OFI R² ≈ 65%); Gould–Bonart 2015 (P(up|I≈1) ≈ 0.8–0.9 large-tick); Zarattini–Barbon–Aziz (ORB+RelVol Sharpe 2.81, 2016–2023); GGR 2006 (~11% annualized pairs); Do–Faff 2010 (0.86% → 0.37% → 0.24%/mo decay); Do–Faff 2012 (plain pairs dead after 2002); Rad–Low–Faff 2016 (cointegration 85/33 bps gross/net). Vendor prices: indicative — verify before budgeting.

---

## Source list (only papers actually used)

- Cont, R., Kukanov, A. and Stoikov, S. (2014), "The Price Impact of Order Book Events," Journal of Financial Econometrics.
- Gould, M.D. and Bonart, J. (2015), "Queue Imbalance as a One-Tick-Ahead Price Predictor in a Limit Order Book," Market Microstructure and Liquidity.
- Cont, R., Stoikov, S. and Talreja, R. (2010), "A Stochastic Model for Order Book Dynamics."
- Crabel, T. (1990), *Day Trading with Short Term Price Patterns and Opening Range Breakout*.
- Zarattini, C., Barbon, A. and Aziz, A. (2016–2023 sample), "A Profitable Day Trading Strategy for the U.S. Equity Market," SSRN 4729284 / SFI WP.
- Gervais, S., Kaniel, R. and Mingelgrin, M. (2001), on high-volume return premiums.
- Engle, R.F. and Granger, C.W.J. (1987), "Co-integration and Error Correction," Econometrica.
- Gatev, E., Goetzmann, W.N. and Rouwenhorst, K.G. (2006), "Pairs Trading: Performance of a Relative-Value Arbitrage Rule," Review of Financial Studies.
- Chan, E. (*Algorithmic Trading*, 2013), OU spread.
- Leung, T. and Li, X. (*Optimal Mean Reversion Trading*), OU spread.
- Uhlenbeck, G.E. and Ornstein, L.S. (1930), Brownian motion / OU process.
- Do, B. and Faff, R. (2010), "Does Simple Pairs Trading Still Work?", Financial Analysts Journal.
- Do, B. and Faff, R. (2012), "Are Pairs Trading Profits Robust to Trading Costs?", Journal of Financial Research.
- Rad, H., Low, R.K.Y. and Faff, R. (2016), cointegration vs distance vs copula pairs with time-varying costs.
- Jacobs, H. and Weber, M. (2015), pairs trading in 34 countries.
- Lipton, A., Pesavento, U. and Sotiropoulos, M. (2013), quote imbalance.
- Everything not attributed to one of the above — thresholds, cost figures, worked-example values — is illustrative.
