# TB3 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials (account: Praveen Gupta)
- Date: 2026-09-10
- Chat: https://grok.com/c/bc53c0e0-ea77-4eb8-b849-6b6444731051
- Batch: TB3 — Microstructure market-making & toxicity (T021–T030)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim via page text extraction.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: wording, numbers, formulas, and citations preserved. Link chips (e.g. [Tandfonline]) are the citation labels as displayed on the page; full URLs were not expanded in the UI. Grok's Q3 contains two mid-sentence truncations — captured exactly as rendered.
- All numeric parameters are illustrative examples, not estimated or recommended values. Nothing here is a live-trading spec.

---

## Q-TB3-1 — mechanics + worked example (verbatim)

"All parameters below are examples for a worked tape, not fitted or recommended production values. Formulas follow the cited papers; opinionated choices (rebates, thresholds) are marked as examples."

Shared tape convention: one tick = 0.01, unit size = 1 share, mid S_t in dollars. Maker rebate 0.0020 per share, taker fee 0.0030 per share (maker-taker style, illustrative). Mark-to-market uses last mid. Horizon for A–S is T = 1.0 (normalized session); we treat the 10 updates as equally spaced with remaining time τ = T − t.

### (A) Avellaneda–Stoikov inventory-skew MM

Source. Avellaneda & Stoikov, "High-frequency trading in a limit order book," Quantitative Finance 8(3), 2008. Closed-form reservation + spread used in production wrappers (Hummingbot, standard HFT interview problem). [Tandfonline]

State. Mid S_t, signed inventory q (shares; + = long), remaining horizon τ = T − t, mid vol σ (price units per √time), risk aversion γ, fill-intensity decay κ.

Reservation price (indifference / inventory-adjusted fair value):
r(t,q) = S_t − q γ σ² τ
Long inventory (q > 0) pushes r below mid → ask becomes more aggressive, bid less. Short does the opposite.

Optimal total spread (asymptotic closed form):
δ* = (2/γ) ln(1 + γ/κ) + γσ²(T − t)
Half-spread δ = δ*/2. Quotes centered on r, not on mid:
p^a = r + δ, p^b = r − δ.

Example parameters (A). γ = 0.1, κ = 1.5, σ = 0.02 (per unit time), T = 1.0, hard inventory limit Q_max = 100. Liquidity term: (2/γ)ln(1 + γ/κ) = 1.289. Inventory-risk term at τ: 0.0004 · 10 (tiny vs the liquidity term on this scale; skew still comes from the −qγσ²τ shift in r). In tick terms we will also apply a practical tick rounding after computing raw r ± δ.

Inventory limits. Soft via γ; hard: if q ≥ Q_max pull bid; if q ≤ −Q_max pull ask. Optional terminal liquidation penalty already encoded in r.

Cancel / replace. Recompute r, δ on every mid/inventory change. Replace if new bid/ask differs from resting by ≥ 1 tick, or if inventory hits cap. No separate toxicity filter in vanilla A–S (that is strategy B).

Adverse selection. Not explicit. A–S only prices σ². Post-fill mark-to-market of the filled side vs next mid is the usual ex-post AS diagnostic (see example P&L).

Fees. Maker fill: cash ±p plus rebate 0.0020. Unfilled quotes earn nothing. Terminal mark of leftover q at last mid.

#### Worked tape (A) — 10 quote updates

Example params as above. Start q = 0. We use δ = 0.645 (half of δ* at this κ, σ). Quotes rounded to 0.01. Fills assumed when trade price hits our quote (synthetic).

| # | t | mid | q before | τ | r | bid / ask | event | q after | cash Δ (incl. rebate) |
| 1 | 0.0 | 100.00 | 0 | 1.00 | 100.000 | 99.36 / 100.64 | no fill | 0 | 0 |
| 2 | 0.1 | 100.02 | 0 | 0.90 | 100.020 | 99.38 / 100.66 | sell 1 @ 100.66 (our ask lift) | −1 | |
| 3 | 0.2 | 100.01 | −1 | 0.80 | 100.010+0.000032 | 99.37 / 100.65 | no fill | −1 | 0 |
| 4 | 0.3 | 99.98 | −1 | 0.70 | 99.980+0.000028 | 99.34 / 100.62 | buy 1 @ 99.34 (our bid hit) | 0 | |
| 5 | 0.4 | 100.00 | 0 | 0.60 | 100.000 | 99.36 / 100.64 | no fill | 0 | 0 |
| 6 | 0.5 | 100.05 | 0 | 0.50 | 100.050 | 99.41 / 100.69 | sell 1 @ 100.69 | −1 | |
| 7 | 0.6 | 100.08 | −1 | 0.40 | 100.080+0.000016 | 99.44 / 100.72 | no fill | −1 | 0 |
| 8 | 0.7 | 100.06 | −1 | 0.30 | 100.060+0.000012 | 99.42 / 100.70 | buy 1 @ 99.42 | 0 | |
| 9 | 0.8 | 100.04 | 0 | 0.20 | 100.040 | 99.40 / 100.68 | no fill | 0 | 0 |
| 10 | 0.9 | 100.03 | 0 | 0.10 | 100.030 | 99.39 / 100.67 | no fill | 0 | 0 |

Round-trip P&L (two complete cycles, flat at end):
• Cycle 1: sold 100.66, bought 99.34 → spread 1.32 + two rebates 0.004 = 1.324.
• Cycle 2: sold 100.69, bought 99.42 → spread 1.27 + two rebates 0.004 = 1.274.
Net P&L after fees/rebates: +2.598 on 4 maker fills, +2.598. (Spreads are wide because example κ, σ were chosen to make the δ* term visible; live books use much smaller κ, σ in ticks.)

"Note: with γ = 0.1, σ = 0.02 the inventory qγσ²τ shift is sub-tick. To make skew visible on a 1-tick grid one either uses larger γ (e.g. 1.0 on a coarser price unit) or a larger σ; mechanism is unchanged: r moves against q."

### (B) Queue-imbalance posting with toxicity cancel

Sources / lineage. OFI / book-imbalance literature (Cont, Kukanov, Stoikov 2014 and descendants); production "post with the thick side, cancel on the flip" heuristics. [arXiv]

Signal. Top-of-book queue imbalance I = (Q_b − Q_a)/(Q_b + Q_a) (Q_b = displayed size at best bid, Q_a = displayed size at best ask). Positive I → more bid size → short-horizon up-drift on average.

Quoting rule (example).
• I > +0.30: post 1 lot at best bid (join bid queue); optional ask one tick behind or omit.
• I < −0.30: post 1 lot at best ask.
• |I| ≤ 0.30: stay out or post both one tick inside only if rebate > expected AS.
Size: 1 lot. Inventory cap ±2.

Toxicity / adverse-selection measure (example, two triggers; either fires a cancel).
1. Imbalance flip: resting on bid and I < I_tox = −0.20 (flow now sell-heavy).
2. VPIN-style / trade-sign toxicity Tox = |Σ signs|/N on a short window: let s_i ∈ {+1,−1} be Lee–Ready signs of last N = 4 prints. Toxicity Tox = |Σ s_i|/4. Cancel if Tox ≥ 0.80 and the dominant sign is against the resting side (e.g. resting bid, prints are mostly seller-initiated s = −1).
Optional third: mid moved ≥ 1 tick against the quote before a fill.

Cancel / replace. On every book update: recompute I, Tox. Cancel immediately if a trigger fires or q at cap. Re-post only if I again exceeds θ_post on the same side and no toxicity. No chase through the spread (maker-only).

Fees. Same maker rebate 0.0020; if you ever take (you shouldn't in this spec) pay 0.0030.

#### Worked tape (B) — same 10 updates; cancel trigger fires

Synthetic book + prints. θ_post = 0.30.

| # | mid | Qb, Qa | I | action | resting | prints in window (sign) | Tox | trigger |
| 1 | 100.00 | 80, 40 | +0.33 | post bid @ 99.99 | bid 1 | — | — | — |
| 2 | 100.00 | 90, 35 | +0.44 | hold bid | bid | + + | low | — |
| 3 | 100.01 | 70, 50 | +0.17 | hold (still posted; below post but not tox) | bid | + + − | 0.33 | — |
| 4 | 100.01 | 40, 70 | −0.27 | CANCEL bid (I < I_tox) | flat | + − − − | 0.50 | imbalance flip |
| 5 | 100.00 | 30, 90 | −0.50 | post ask @ 100.01 | ask | − − − | 1.00 | tox high but with ask (sellers) → keep |
| 6 | 99.99 | 35, 80 | −0.39 | hold ask | ask | − − − + | 0.50 | — |
| 7 | 99.99 | 60, 55 | +0.04 | hold | ask | − + + | 0.20 | — |
| 8 | 100.00 | 85, 40 | +0.36 | CANCEL ask (I now bid-heavy, against ask) | flat | + + + | 1.00 | imbalance flip + tox |
| 9 | 100.02 | 90, 30 | +0.50 | post bid @ 100.01 | bid | + + | — | — |
| 10 | 100.02 | 95, 28 | +0.54 | fill bid (seller hits 100.01) | — | — | — | — |

Fills: one buy @ 100.01 maker. End mid 100.02.
Cash: −100.01 + 0.002 = −100.008. Mark of long 1 @ 100.02 = +100.02.
Net P&L after rebate: +0.012 (1 tick MTM + rebate). "The important event is not the P&L but step 4 and step 8: toxicity/imbalance cancel fired before a would-be adverse fill. Without the cancel at 4, the bid would have been hit into a falling book (I already −0.27 and going to −0.50)."

### (C) Hawkes-burst scalping

Sources. Hawkes intensity λ(t) = μ + Σ_{t_i < t} α e^{−β(t−t_i)} (Hawkes 1971); finance survey Bacry, Mastromatteo, Muzy 2015; burst detection Rambaldi, Filimonov, Lillo. [Ar5iv.labs.arxiv]

Model (univariate or signed pair; example is signed). Trade (or mid-change) point process. Conditional intensity λ(t) = μ + Σ_{t_i < t} α e^{−β(t−t_i)}.

Example parameters (C). μ = 0.8 events/s, α = 0.6, β = 2.0 (branching ratio n = α/β = 0.30 < 1, stationary). Burst if λ(t) ≥ λ_burst = 3.0 (about 3.75× baseline μ = 0.8; stationary λ̄ = μ/(1−n) = 1.14). Signed variant: maintain λ^+ (buyer-initiated) and λ^− (seller-initiated) with the same kernel. Score ψ = (λ^+ − λ^−)/(λ^+ + λ^−).

Entry / exit (example).
• Enter long (take the ask) when λ^+ + λ^− ≥ λ_burst and ψ > +0.4.
• Enter short (take the bid) when burst and ψ < −0.4.
• Exit when λ falls back below λ_burst, ψ flips through 0, or max hold 3 updates, or −2 ticks / +1 tick stop. Inventory limit: 1 lot, never pyramid.
This is a taker scalp inside a detected self-exciting burst, not a maker.

Fees. Taker both ways: 0.003 each fill.

Adverse selection. The burst filter is the AS control: you only take when intensity is clustered (momentum / informed cascade), and you flatten fast.

#### Worked tape (C) — burst detection + signed entry/exit

Updates treated as Δt = 0.1 s. We track a discrete intensity with the exponential kernel after each print. Signs: + = buy-initiated, − = sell-initiated. Start λ^± = μ = 0.8.

| # | mid | print sign | λ^+ | λ^− | λ | ψ | decision | pos | cash Δ (incl. fee) |
| 1 | 100.00 | + | 1.40 | 0.80 | 2.20 | +0.27 | wait | 0 | 0 |
| 2 | 100.01 | + | 1.89 | 0.65 | 2.54 | +0.49 | wait (λ < 3) | 0 | 0 |
| 3 | 100.02 | + | 2.29 | 0.54 | 2.83 | +0.62 | wait | 0 | 0 |
| 4 | 100.03 | + | 2.62 | 0.44 | 3.06 | +0.71 | ENTER LONG take ask 100.03 | +1 | |
| 5 | 100.04 | + | 2.89 | 0.36 | 3.25 | +0.78 | hold | +1 | 0 |
| 6 | 100.05 | + | 3.11 | 0.29 | 3.40 | +0.83 | hold | +1 | 0 |
| 7 | 100.05 | − | 2.55 | 0.84 | 3.39 | +0.50 | hold | +1 | 0 |
| 8 | 100.04 | − | 2.09 | 1.29 | 3.38 | +0.24 | hold (ψ decaying) | +1 | 0 |
| 9 | 100.03 | − | 1.71 | 1.65 | 3.36 | +0.02 | EXIT: take bid 100.03 | 0 | |
| 10 | 100.02 | − | 1.40 | 1.95 | 3.35 | −0.16 | flat | 0 | 0 |

Intensity recursion used (example, e^{−βΔt} = 0.819 this print): λ ← μ + (λ − μ)e^{−βΔt} + α·1_{this print}.
Per-trade net P&L: bought 100.03, sold 100.03, two taker fees 0.006 = −0.006 (scratch on price, lose fees). "That is the honest Hawkes-scalp outcome on a burst that mean-reverted inside the cluster. A profitable variant on this tape would have exited at step 6 (mid 100.05): +0.02 − 0.006 = +0.014. The rule as specified waited for ψ to die and scratched."
"If at step 4 we had instead seen a sell burst (ψ < −0.4), entry would be short at the bid, symmetric."

### Cross-strategy comparison on this tape

| | Style | Edge claimed | AS control | Fee posture | Example net on tape |
| A | maker, inventory utility | spread − inventory risk | skew + hard cap | collect rebate | +2.598 (wide example κ) |
| B | maker, microstructure signal | imbalance drift | cancel on flip / tox | collect rebate | +0.012 (1 fill, 2 cancels) |
| C | taker, point-process | self-excitation continuation | enter only in burst, exit on λ fade or ψ flip | pay taker both ways | −0.006 (scratch − fees) |

"Implementation notes that apply to all three. (1) Tick-snap and lot-size after the continuous formula. (2) Queue position is invisible in A–S and must be modeled. (3) σ, κ, α, β are estimated on rolling windows; treating them as constants is the paper approximation. (4) Fee/rebate and adverse-selection markouts should be part of the sim, not added later."

Primary citations. Avellaneda & Stoikov (2008), Quant. Finance; Cont–Kukanov–Stoikov OFI / imbalance tradition; Hawkes (1971) + Bacry–Mastromatteo–Muzy (2015) survey; Rambaldi–Filimonov–Lillo burst work. All thresholds, and fees above are examples for the synthetic 10-step tape.

---

## Q-TB3-2 — infra + local build + buy vs build (verbatim)

"Honest answer first: a 128 GB M5 Max is an excellent research, simulation, and post-trade forensics machine. It is not a market-making execution venue. The gap is not CPU or RAM. It is data completeness + physical latency + fill realism. Treat anything that posts live quotes from the Mac as a learning lab, not a P&L engine."

M5 Max facts that matter here: 18 CPU cores (6 super + 12 performance), up to 128 GB unified LPDDR5X, 460–614 GB/s memory bandwidth depending on 32- vs 40-core GPU SKU. That bandwidth is why 20-symbol MBO replay is comfortable; it does not change the speed of light to Aurora or Carteret. [Wikipedia]

### 1) Minimum viable data — L1 vs MBO

#### What L1 (MBP-1 / TBBO / SIP BBO) gives you
Best bid/ask price and aggregate size, last trade, maybe aggressor side if the vendor adds it.
Enough for:
• Avellaneda–Stoikov reservation math (mid, σ, inventory)
• Crude imbalance I = (Q_b − Q_a)/(Q_b + Q_a) at top only
• Hawkes on trade times / mid changes, not on book events

#### What you lose without MBO (label these simulated-only)

| Missing quantity | Why MM care | If you fake it |
| Per-order IDs and queue rank | Fill probability is "how many shares ahead," not "size at touch" | Any queue model is a prior, not a measurement |
| Add / cancel / modify at every level | Toxicity often shows as cancels in front of you before the print | You will not see the cancel cascade that picks you off |
| Hidden / iceberg replenish | Apparent size ≠ standing size | Overstate fill odds |
| Multi-level depth + walk | Sweep vs drip; impact after you fill | Adverse-selection mark is biased |
| Odd lots / venue-specific top (equities) | SIP L1 drops a large fraction of displayed interest | Equity imbalance is wrong |
| Matching-engine timestamps vs your clock | You cannot separate "stale book" from "slow Wi-Fi" | Latency research is contaminated |

Strategy mapping from the previous note:
• (A) A–S: L1 is formally enough for r and δ*. Fill simulation is not. Without MBO you must invent a fill rule (e.g. "trade through my price ⇒ fill"). That rule is simulated-only.
• (B) Queue-imbalance + toxicity cancel: L1 imbalance is a noisy proxy. True queue-imbalance + "am I still near the front?" requires MBO. Toxicity cancel on L1 is "imbalance flipped"; on MBO it is "size ahead vanished / same-price cancels spiked."
• (C) Hawkes-burst scalp: Trade-time Hawkes works on L1 trades. Book-event Hawkes (adds/cancels) needs MBO. Burst continuation after you take is still simulated unless you have the actual next events.

Minimum honest stack for learning MM:
• Historical MBO (or at least MBP-10) for a handful of liquid names — Databento-class schemas, not Yahoo/Polygon aggregates. [Databento]
• A deterministic replay engine: same event order as the tape, your orders inserted with an explicit queue model.
• Live L1 only as a dashboard, never as the fill truth.
"If the budget is 'L1 live + bars history,' stamp every backtest: SIMULATED-ONLY — no queue, no cancel cascade, optimistic fills."

### 2) Tick-loop latency on a Mac — no colocation

"Break the path. The Mac is rarely the bottleneck."

| Hop | Honest order of magnitude |
| Exchange matching engine → colo NIC (HFT) | 1–50 µs tick-to-wire in-shop |
| Colo public-cloud / vendor normalize (e.g. Databento internet p90 cited ~0.6 ms; cross-connect tens of µs) | 0.05–1 ms to their box, not yours [Databento] |
| Vendor → home (Austin / Bay Area → CME Aurora or NJ equity DCs) | Physics: ~15–40 ms one-way fiber coast/midwest; home last-mile + Wi-Fi + NAT adds jitter |
| Consumer ISP path (hops, bufferbloat) | Typical home RTT 40–120 ms, spikes to 200+ ms under load |
| macOS tick loop (user-space, not isolcpus, not kernel-bypass) | Parse + strategy + serialize: 50–500 µs well-written Rust; 0.5–5 ms Python + pandas per wake; GC/App Nap/thermal can add 10–50 ms tails |
| Broker/API (REST/WebSocket retail) | Often another 5–40 ms plus queueing |
| Exchange matching of your order vs colocated makers | They already canceled |

Quantified disadvantage vs a serious MM desk
• Desk tick-to-trade: ~1–50 µs (FPGA/C++ colo) to ~100–500 µs (software colo).
• Mac + home ISP + retail/FIX-over-internet: ~30–150 ms typical one-way-ish decision-to-ack, p99 much worse.
• Ratio: about 10³–10⁵× slower than the people you are quoting against.

What that means for the three strategies:
• (A)(B) posting: you are last in queue at any price the fast makers also want. When the book is about to roll, they cancel in microseconds; your cancel arrives tens of milliseconds later → systematic adverse selection. This is not a software bug.
• (C) Hawkes take: burst half-life is often 100–500 ms. A 50 ms delay still leaves some of a fat burst; a 150 ms delay + broker slip often does not. Edge, if any, is seconds-scale continuation, not microstructure.
"Jitter matters as much as median. A stable 40 ms is more usable than 15 ms that spikes to 200 ms when iCloud/Time Machine/Wi-Fi roam hits."
"Honest operating rule: do not post live two-sided quotes from this machine in any market where cancel-speed is the product. Use the Mac to decide slowly (seconds) and let a colocated or broker algo handle the wire — or don't go live."

### 3) Throughput / RAM — 20-symbol quoting engine, Rust vs Python

"20 liquid symbols is a small book problem. The M5 Max is overkill on compute; the constraint is event rate × copy overhead × GC."
Rough event rates (order of magnitude, busy session):
• L1 BBO+trades, 20 names: 10³–10⁵ msgs/s peak
• MBP-10: few× that
• MBO equities/futures liquid set: 10⁵–10⁶ msgs/s peak is plausible on a busy tape; 20 names is usually well below a full-universe firehose

RAM (128 GB is not the issue)

| Component | Ballpark resident |
| 20-symbol L1 live state | < 100 MB |
| 20-symbol MBO live books (hash by order ID) | 0.5–3 GB hot |
| Full-day MBO replay buffer / mmap | 10–80 GB depending on venue and how much you keep decoded |
| Feature store + Hawkes kernels + logs | another few GB |

"128 GB lets you keep multiple full sessions of MBO decoded in RAM plus a research notebook. That is the actual superpower: honest replay without streaming off SSD every tick."

Rust vs Python on this chip

| | Rust | Python |
| L1 20-symbol live loop | Comfortable on 1–2 cores; <100 µs/event easy | Fine if you stay in NumPy/Polars and don't touch pandas per tick |
| MBO replay 20 symbols | 10–50M events/s on one M5 super-core is realistic for a tight parser+book; full day in seconds–minutes | Pure Python book: often 10–100× slower; PyO3/polars/databento crate bindings close the gap for research |
| Tail latency | Predictable | GC + allocator + GIL (unless free-threaded 3.13+ and you are careful) |
| Quoting engine (cancel/replace state machine) | Right tool | Acceptable for offline sim; risky for a live 1 ms loop |

"Practical split that stays honest:
• Rust (or C++): decoder → order book → queue position → cancel/replace FSM
• Python: parameter search, Hawkes MLE, reports, notebooks
• Do not put the live tick loop in Jupyter."
"Unified memory helps Python more than on a dGPU box (no PCIe bounce), but it does not fix interpreter overhead."

### 4) Engineering hours (one experienced person, honest MM lab)

| Workstream | Hours | Notes |
| Data plumbing (Databento/similar → parquet/TDengine, clocks, symbology) | 40–80 | Most people undercount this |
| MBO book + queue model + fill simulator | 80–150 | This is the product |
| A–S + imbalance + Hawkes signal libs | 40–80 | Formulas are short; estimation + guards are not |
| Live L1 dashboard + paper router (no real posts) | 40–60 | |
| Backtest accounting (fees, rebates, markouts 1s/5s/30s) | 30–50 | Without markouts you will lie to yourself |
| Reliability: clock sync, kill switch, replay determinism tests | 30–50 | |
| Total to "I trust the simulator" | ~250–450 h | ~2–3 months full-time |
| Extra to "I might send a live order via a broker API" | +100–200 h | Still not colo MM |
| Extra to production colo MM | person-years + legal + vendor | Different job |

"Mac-specific tax: no Solarflare/Onload, no easy isolcpus culture, power assertions vs App Nap, ARM Homebrew wheels. Budget +15–20% vs a Linux workstation for the live path. Replay/research tax is near zero — ARM is fine."

### 5) Buy vs build — costs and verdict

"Indicative 2026-ish numbers, not quotes."

| Path | What you get | Indicative cost | Latency class | Honest use |
| Local Mac paper sim (MBO hist + L1 live view) | Learning, research, agent tooling | Machine you already own + data ~$50–500/mo depending on MBO volume | N/A (offline) / 40–150 ms if you peek live | Best ROI for learning |
| Retail broker API + home | Real fills, worst queue | Commissions; data often L1 | 50–200 ms | Discretionary / slow inventory only |
| Chicago/NJ proximity VPS | Better RTT to CME or equities | ~$80–400/mo VM | ~1–8 ms to engine neighborhood, not µs | Scalps measured in seconds, not queue races |
| Exchange colo rack + cross-connect + official feeds | Real MM | Rack ~$1.5k–5k+/mo per venue + market-data licenses that dwarf compute (equity depth licenses can be five figures/month) + FPGA/NIC | µs | Only if you have a seat, capital, and a measured edge |
| Join a prop / MM desk | Their colo, data, risk | Comp / profit share; you don't buy the rack | Desk-class | How almost all real MM skill is deployed |
| Crypto "MM on laptop" | Taker/maker on CEXes | Fees + inventory capital | 10–50 ms typical API | Possible small maker if you pick illiquid pairs and accept inventory risk — still not A–S-vs-Citadel |

"Prop 'evaluation' shops and NinjaTrader VPS stacks are not the same as a CME/Nasdaq MM desk. They buy you proximity for discretionary futures, not MBO queue priority." [Copilink]

#### Verdict

| Goal | Do this |
| Learn the mechanics honestly | 128 GB M5 Max + historical MBO + a Rust book + markout reports. Do not skip MBO and then claim queue strategy results. |
| Research / parameter fitting / multi-agent sims | This machine is better than a colo box (RAM, quiet, MLX/GPU for Hawkes/RL). |
| Live two-sided quoting in liquid futures/equities | Do not deploy from the Mac. Latency disadvantage is ~30–150 ms vs µs. You will be the inventory of last resort. |
| Live anything | Seconds-to-minutes inventory, wide quotes, or take-only burst trades after a VPS — and even then size tiny until markouts are green out of sample. |
| Career / real deployment | Build the lab on the Mac so you can talk MBO, markouts, and cancel logic; deploy only on someone else's colo (job or capitalized partnership). |

"One-line standard: use the M5 Max as a flight simulator with a full aerodynamic model (MBO). Do not confuse high-fidelity simulation on a fast laptop with being in the race. The 128 GB is for keeping the truth in memory — not for beating the matching engine."

---

## Q-TB3-3 — success ratios, after-cost efficacy, failure modes (verbatim)

"The literature's consistent message: these models manage a trade-off, they do not print money. Inventory control and toxicity gates buy smaller tails at the cost of mean P&L; without rebates and colocation the economics are negative on liquid lit books."

### (1) Avellaneda–Stoikov — documented performance and inventory-risk drawdowns

"Design, not an edge. A–S maximises expected exponential utility of terminal wealth. That is explicitly 'give up mean P&L to shrink inventory variance.' The 2008 tables: moving γ 0.01 → 0.10 → 0.50 sacrifices 0.86% / 6.35% / 48.76% of mean profit at the quoted parameter sets, while cutting terminal-inventory SD from ~8.7 to ~2.8 shares (shorter horizon) and from ~9.1 to ~1.9 (longer horizon). Profit-to-dispersion of the inventory strategy vs symmetric is roughly 1.5–2.1×, then fades at high γ as the spread becomes so wide that you stop trading. [Navnoorbawa.substack]"

"That is the intended regime: higher γ = fewer fills, flatter book, smaller inventory blow-ups, lower mean. Lower γ = A–S collapses toward a symmetric spread; inventory random-walks and P&L lurches on mid moves. Production caveat: the 2008 numbers are a stylised, fee-free, competition-free toy; live desks add toxicity, fees, queues, jumps. [Hftradingbook]"

"On real tapes the inventory term still helps tails, not Sharpe. Gašperov & Begušić (PLOS One, 2022) backtested genetically calibrated A–S ('Gen-AS') vs baselines and RL variants on 30 days of BTC-USD L2. Gen-AS had the lowest mean and SD of maximum drawdown among five models — that is the inventory-risk control working. The RL variants that were allowed to depart from risk-minimising quotes beat Gen-AS on Sharpe (24/30 days) and Sortino (25/30), at the price of occasional outlier drawdowns. Authors flag 'localised excessive risk-taking' as the concern. [Journals.plos]"

"A separate BTCUSDT perpetual study is harsher on vanilla A–S: on a historical holdout, A–S at γ = 0.1 and γ = 0.5 both printed about −28.7% annualised, Sharpe −2.63, max DD ~20.6%, worse than even a 0.1% fixed-spread rule on that tape. An adaptive, fee-aware variant with vol filters and a take-profit leg improved on this, but the vanilla form bleeds on crypto trend tapes. [ScienceDirect]"

"Failure regime (inventory blowup). A–S has no jump term. A gap through your bid while you are already long is exactly the state the linear r under-prices. Hard Q_max caps and a session-end liquidation penalty are the usual patches; they convert a continuous utility" [Grok's answer ends mid-sentence here on the page; captured exactly as rendered]

### (2) Queue-imbalance MM — fill rate vs adverse selection (Gould–Bonart and follow-ups)

"What Gould & Bonart actually showed. On 10 Nasdaq names, logistic fits of next mid-move on top-of-book imbalance beat a no-skill null: binary classification improves ~50–60% for large-tick stocks, ~10–30% for small-tick; probabilistic scores improve ~20–30% vs ~2–6%, local logits put R² ~0.8–0.9 on large-tick names, only ~0.1–0.3 on small-tick. Signal life is about the next one–two mid changes, then dead. [Papers.ssrn]"

"That is a one-tick directional result, not a maker P&L result. Follow-ups in the queue-race literature (e.g. impact / strategy-optimised extensions) study which queue depletes first when the spread is one tick; sampled just before a price change, simple logits can hit ~85% direction — and that number is not usable for posting, because if you can see it, so can everyone with a faster wire. [Ar5iv.labs.arxiv]"

"The fill-rate / AS trade-off when you actually post. A 2025 maker/taker study on imbalance strategies (with and without cancels) is the relevant P&L documentation: imbalance strategies were the most active and the worst after costs (mean return about −0.49 in their units); naive makers −0.43; imbalance makers without cancel −0.47; with cancel −0.49 — slightly worse mean, fewer trades (7333 vs 8851), longer holds. Cancels only catch slow adverse imbalance flips, not snipes."

"So the documented trade-off is:
• Thick side → higher chance the mid moves your way if you get filled on the passive side that is already thick
• That same thickness means you are back of queue. Fills arrive when the thick side is exhausted — often the start of the adverse move.
• Cancel when I flips → you give up the residual good fills and still miss snipes.
G–B is necessary to justify the signal. It is not sufficient to justify a remote posting engine."

### (3) Toxicity-gated quoting (PIN / VPIN) — does gating reduce AS, with numbers?

"Construction. PIN (Easley–Kiefer–O'Hara–Paperman) is the classic probability a trade is informed. VPIN (Easley–López de Prado–O'Hara, J. Financial Markets / RFS 2012) is the HF, volume-clock version: average absolute buy/sell-volume imbalance across equal-volume buckets. Original claim: VPIN hit the top decile (~90% CDF) by 11:56 on 6 May 2010 before the E-mini air pocket. [Microalphas]"

"Does gating help? The evidence is mixed and the incremental value is small once you control vol.
• ELO / patent materials treat VPIN as an early-warning for toxicity-induced liquidity holes. [Patents.google]
• Andersen & Bondarenko (2014) and the Kellogg summary of that fight: much of VPIN's 'forecast' is mechanical correlation with contemporaneous volume and volatility; on CME historical tape they could make the spike lag the crash depending on bucket alignment. Incremental power for future vol/stress after controlling those is weak. [Insight.kellogg.northwestern]
• Abad, Massot & Pascual (circuit-breaker study, ~6,740 halts, 45 stocks, 12 years): high VPIN rarely signals abnormal illiquidity and only occasionally precedes halt-sized moves. Toxic- vs non-toxic-labelled halts differ in realised spread, depth, and price impact — those gaps 'tend to vanish when we control for ex ante realised volatility.' [Scispace]
• Sensitivity papers: toxic-period flags move a lot with the trade-classification scheme (tick vs bulk-volume classification). [Tuprints.ulb.tu-darmstadt]
• Asset-pricing (not MM) result: a long high-VPIN / short low-VPIN book had ~0.18% monthly five-factor alpha (signed SVPIN ~0.29%, ~11% annualised BHAR) — VPIN is correlated with something priced, which is not the same as 'gating your quotes cuts markouts by X bps.' [Papers.ssrn]
• Microstructure-consistent behavioural fact: algo participation falls when VPIN is high (ATs pull back). That is the market already gating. A slow extra gate on a Mac is mostly copying a move the fast makers made tens of milliseconds ago. [Econ.queensu]"

"Practical number to take away. There is no clean published 'VPIN-on vs VPIN-off reduced 5-second markout by X bps on a posting desk.' The honest synthesis: VPIN/PIN-style gates reduce participation in high-vol windows (which cuts AS and also cuts the good flow that lives in those windows). After you condition on realised vol, the incremental AS reduction is small and specification-dependent. Use them as a regime switch (widen δ, cut size, pull one side), not as a tick-level cancel trigger."

### (4) Honest economics of retail MM without rebates or colocation

"Write the identity the microstructure books use:
E[P&L] = spread captured − adverse selection − inventory/jump q-risk − fees
On a lit, maker-taker book the rebate is often the only reason the first term survives the second. Remove rebate and sit 30–150 ms away from the engine and three things happen at once."

"You do not receive the good flow. Institutional retail-MM profitability (German RMM study): RMMs that purchase retail flow earn a gross Sharpe ~17.9, more than 2× proprietary firms on public LOBs; they would pay ~1.76 bps of volume (~60% of revenue) just for access to that flow; inventory half-life ~16 min vs ~42 min for public-book PTFs. The edge is flow quality (low AS) + internalisation, not quoting skill on the SIP. US PFOF is the same economics: wholesalers pay for uninformed, two-sided flow worth internalising. [Bundesbank +1]"

"Latency arbitrage is the tax on stale quotes. Budish–Cramton–Shim and the XTX anti-latency-arbitrage notes: any standing quote is an option against a fast taker; at 30–150 ms your option is picked off by whoever sees the signal first. [Datocms-assets]"

"Empirics on public-book makers without a structural rebate edge. The imbalance-maker study above is already net-negative after fees, with or without cancels. Crypto" [Grok's answer ends mid-sentence here on the page; captured exactly as rendered]

"What the literature implies for a remote Mac operation

| Term | Colo + rebate + flow filter | Home Mac, no rebate, lit book |
| Spread captured | ticks + rebate | ticks only, and you are last in queue so you capture the toxic tail of those ticks |
| Adverse selection | managed in µs; optional PFOF/internaliser filter | systematic: every stale quote is an ALA option written for free |
| Inventory | hedged across names/venues in the same rack | unhedgeable jumps over 50–150 ms |
| Fees | rebate ≥ fee on many venues | pay taker if you chase; earn $0 extra as maker |"

"Implication: expected P&L < 0 on liquid names unless (a) you are paid a rebate that exceeds expected markout, or (b) you only quote where flow is slow (illiquid names, wide crypto pairs), accepting inventory risk that A–S was designed to limit."

### Failure regimes (how the three strategies actually die)

"Latency arbitrage against you. A–S and imbalance posters rest at a price computed from a mid that is already old. Fast takers hit the stale quote; the mid then prints through it and your fill marks red within seconds."

"Toxic flow. PIN/VPIN gating helps only if the toxic episode is slow relative to your clock. Flash-crash-style and news-jump toxicity is a few hundred milliseconds of one-sided take. Andersen–Bondarenko's point stands: VPIN's incremental alarm once vol is known — and vol is already in A–S's σ. Result: you either stay up and get run over, or you gate on vol and earn nothing in the only hours with spread to harvest."

"Inventory blowups. A–S drawdowns in the BTC RL paper and the vanilla A–S holdout (max DD ~20% on that sample) are this regime: σ is mis-estimated through the jump, reservation skew is too small in ticks, hard cap is missing or too wide. Q_max prevents the blowup by refusing inventory — which is also how you give up 6–49% of mean profit in the 2008 tables. There is no parameter that buys both."

"Net for a 128 GB M5 Max lab. Use the papers as a risk taxonomy and a simulator spec (markouts at 1s/5s/30s, queue model, fee-on, rebate-off sensitivity). Do not treat published A–S Sharpe as portable. Mean P&L after AS and fees is the residual that goes to the fastest maker — not to the best formula."

---

## QC notes (orchestrator)

1. Q1(A): the "Inventory-risk term at τ" is rendered as "0.0004 · 10" — this does not parse (γσ²τ = 0.1 × 0.02² × τ = 0.00004τ); likely a KaTeX render artifact. Everything else in the A–S tape checks out: (2/γ)ln(1+γ/κ) = 1.289 ✓, half-spread 0.645 ✓, reservation shifts like 100.010+0.000032 match r = S_t − qγσ²τ ✓, and 1.324+1.274 = 2.598 ✓.
2. Q1(B): step 2 prints "+ +" give Tox = 1.00 by the stated formula, but the cell is labeled "low" — no cancel fires there anyway because the dominant sign is WITH the resting bid (rule requires against-side dominance), so the logic holds; the label is loose.
3. Q1(C): Hawkes recursion inconsistency — the stated recursion is λ ← μ + (λ−μ)e^{−βΔt} + α·1_{this print}. Steps 1–6 apply this to the printed side (e.g. step 2 λ^+ = 1.89 ✓) while the non-printed side decays without mean reversion (λ^−: 0.80 → 0.65 → 0.54, i.e. pure decay λe^{−βΔt}). Steps 7–10 instead use pure decay +α on the printed side (step 7 λ^− = 0.84 vs 0.982 under the stated recursion). ψ, entry (step 4: λ=3.06 ≥ 3.0, ψ=+0.71 > 0.4 ✓), and P&L (−0.006 ✓) are computed consistently off the displayed intensities. The step-9 exit is justified in text as "waited for ψ to die" (ψ=+0.02) rather than a stated rule trigger (λ was still 3.36 ≥ 3.0, ψ not yet through 0, and hold exceeded 3 updates).
4. Q2 sanity checks: the 10³–10⁵× disadvantage ratio follows from its own numbers (30 ms/30 µs = 10³; 150 ms/1 µs ≈ 10⁵ ✓); engineering-hour line items sum to ~260–470 h vs stated "~250–450 h" ✓.
5. Q3: two passages truncated on the page itself — the (1) failure-regime paragraph ends mid-sentence at "they convert a continuous utility", and the (4) "Empirics on public-book makers" paragraph ends at "Crypto". Captured exactly as rendered.
6. Key sourced claims are research leads, not verified facts: Avellaneda–Stoikov 2008; Cont–Kukanov–Stoikov OFI tradition; Hawkes 1971; Bacry–Mastromatteo–Muzy 2015 survey; Rambaldi–Filimonov–Lillo burst work; Gašperov & Begušić 2022 (Gen-AS, PLOS One); Gould & Bonart (imbalance logit R² ~0.8–0.9 large-tick); Easley–López de Prado–O'Hara VPIN (2012); Andersen & Bondarenko 2014 (VPIN critique); Abad–Massot–Pascual (6,740 halts, 45 stocks, 12 years); Budish–Cramton–Shim (latency arbitrage); German RMM study (Sharpe ~17.9, 1.76 bps flow cost). Vendor prices: indicative — verify before budgeting.

---

## Source list (only papers actually used)

- Avellaneda, M. and Stoikov, S. (2008), "High-frequency trading in a limit order book," Quantitative Finance 8(3).
- Cont, R., Kukanov, A. and Stoikov, S. (2014), "The Price Impact of Order Flow Imbalance: Tests of Additive and Linear Models."
- Hawkes, A.G. (1971), "Spectra of some self-exciting and mutually exciting point processes."
- Bacry, E., Mastromatteo, I. and Muzy, J.-F. (2015), "Hawkes processes in finance."
- Rambaldi, M., Filimonov, V. and Lillo, F. (2017), "Detection of intensity bursts using Hawkes processes: An application to high-frequency financial data."
- Gašperov, B. and Begušić, S. (2022), "Deep reinforcement learning for market making under a Hawkes process-based limit order book model," PLOS One.
- Gould, M.D. and Bonart, J. (2016), "Predicting market price movements from order imbalance."
- Easley, D., Kiefer, N.M., O'Hara, M. and Paperman, J.B. (1996), "Liquidity, Information, and Less-Frequently Traded Stocks" (PIN).
- Easley, D., López de Prado, M. and O'Hara, M. (2012), "Flow Toxicity and Liquidity in a High-frequency World."
- Andersen, T.G. and Bondarenko, O. (2014), "VPIN and the Flash Crash."
- Abad, D., Massot, M. and Pascual, R. (2018), "Evaluating VPIN as a trigger for single-stock circuit breakers."
- Budish, E., Cramton, P. and Shim, J. (2015), "The High-Frequency Trading Arms Race."
- Lou, D., Polk, C. and Skouras, S. (2019), "A Tug of War: Overnight vs. Intraday Expected Returns."
- Everything not attributed to one of the above — thresholds, cost figures, worked-example values — is illustrative.
