# TB7 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials (account: Praveen Gupta)
- Date: 2026-09-10
- Chat: https://grok.com/c/a92535b0-124a-4326-8fb3-63022d5b19d8 ("Intraday Trading Strategies Mechanics and Examples")
- Batch: TB7 — Session patterns & auction (T061–T070)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim. A mid-session sign-in expiry was recovered via the saved x.ai login; no credentials invented.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: text extraction duplicated adjacent phrases (streaming echo) — de-duplicated. A few short words were dropped by extraction and restored only where sentence logic unambiguously requires them, marked `[brackets]`; other clipped fragments marked `[clipped]`. **IMPORTANT:** an earlier text extraction of the Q1 answer rendered a DIFFERENT worked-example variant (same topics, different numbers — detailed in QC note 2). The currently rendered text below is the authoritative capture; the earlier variant is flagged for transparency. All thresholds are illustrative examples.
- Nothing here is a live-trading spec.

---

## Q-TB7-1 — mechanics + worked example (verbatim)

"All times are US Eastern. Thresholds marked illustrative. Causal rule: signal on bar t close → eligible fill on bar t+1 open, except auction orders which rest until the close print."

### Shared session calendar

"RTH (equities and ES/NQ cash-hours overlay): 09:30–16:00 ET on full days.
DST: exchange clocks stay on ET. Your box must use America/New_York, not local PDT/MDT. A Mac in San Jose that stamps Pacific will mis-cut IB and miss every MOC deadline.
Half days (NYSE Group 2026): close 13:00 ET on Fri 27 Nov 2026 (day after Thanksgiving) and Thu 24 Dec 2026 (Christmas Eve). Independence Day 2026 is observed Fri 3 Jul — full close, not a half day. All MOC/LOC/IB windows shift back with the scheduled close (NYSE: freeze starts 10 minutes before the early close → 12:50 ET). Brokers often cut 1–2 minutes earlier.
Holidays 2026 (full close): 1 Jan, 19 Jan, 16 Feb, 3 Apr, 25 May, 19 Jun, 3 Jul, 7 Sep, 26 Nov, 25 Dec. Do not trade A/B/C on those dates."

### (A) Initial-balance expansion

"Sources. IB = first two 30-minute TPO periods (A+B) in Steidlmayer Market Profile (CBOT, public 1985); day-type / range extension in Dalton, Jones & Dalton, Mind Over Markets (1990). Related open-range breakout mechanics: Crabel (1990). Not a peer-reviewed alpha paper."

"Session / level — For cash equities and ES/NQ RTH overlay:
• IB window = 09:30:00–10:29:59.999 ET
• IBH_d = max H in the window, IBL_d = min L, IBR_d = IBH − IBL
• Freeze both levels at 10:30. Do not update.
Half day: still first 60 minutes from 09:30 (09:30–10:30). Session is short; skip A if you require a 1R target that will not fit before 13:00.
Narrow vs wide IB (illustrative): compare IBR_d to the 10-day median IB range. Narrow if IBR_d < 0.75 × median. Expansion trades only on narrow IBs."

"Entry (illustrative) — After 10:30, on 5-minute bars:
• Long: bar t closes above IBH and bar volume ≥ 1.2 × that slot's 20-day median and IB was narrow. Fill = open of t+1.
• Short: symmetric below IBL.
• One trade per name per day. No fade-back-inside entries in this spec."

"Exit
1. Stop: opposite IB edge (long stop = IBL), or 0.25×IBR back inside IB (tighter; example uses 0.25×IBR).
2. Target: 1.0×IBR beyond the broken edge (classic 'normal variation' ~2× IB total range).
3. Time: flatten 15:55 ET (12:55 on half days).
4. Failure: close back inside IB after entry → exit next open."

"Sizing: N = ⌊ R / |P_entry − P_stop| ⌋. Example R = $200."

"Cost model: Commission $0.005/share/side. Spread: pay half-spread each way (example 2¢ wide → 1¢/side). No auction."

**Worked example (synthetic 5-min bars, equity XYZ)**
"IB window prints (high/low): 09:30 50.20/49.95; 09:35 50.28/50.02; …; 10:25 50.35/50.10.
IBH = 50.40, IBL = 49.90, IBR = 0.50. 10-day median IBR = 0.80 → narrow (0.50 < 0.75×0.80).
10:40–10:45 bar closes 50.46 on 1.4× slot RVOL. Fill 10:45 open: 50.48 (pay ask).
Tight stop = 50.40 − 0.25 × 0.50 = 50.275. Risk/share = 50.48 − 50.275 = 0.205. N = ⌊200 / 0.205⌋ = 975.
Target = 50.40 + 0.50 = 50.90. Assume target hits; sell 50.89.
Gross: 975 × (50.89 − 50.48) = +399.75. Commission RT: 975 × 0.01 = −9.75. Net: +390.00.
If it failed and stopped at 50.27: gross 975 × (50.27 − 50.48) = −$204.75, commission −$9.75, net −$214.50."

### (B) VWAP-cross institutional follower + RVOL

"Sources. VWAP as institutional benchmark: Berkowitz, Logue & Noser, The Total Cost of Transactions on the NYSE (JF, 1988); Madhavan, VWAP Strategies (trading literature). RVOL as participation filter: same 'stocks in play' idea as Zarattini–Barbon–Aziz (2024), applied here to a VWAP reclaim rather than ORB. Thresholds are not from those papers as a packaged system."

"Session / level — Session VWAP from RTH prints only (09:30 onward): VWAP_t = Σ_{i ∈ [09:30, t]} P_i Q_i / Σ Q_i. Use trade-price × size, not mid. Reset each day. Premarket volume out. RVOL (illustrative): current 5-min volume / median same clock-slot volume over 20 sessions. Half day: VWAP still starts 09:30; flatten 12:50."

"Entry (illustrative) — Need [a] regime, not a single tick poke.
• Long: 5-min bar closes above VWAP and prior bar was at or below VWAP (cross up) and that bar's RVOL ≥ 1.5 and price > VWAP by at least 2¢ (or 0.05×ATR, example) so you are not chopping the line.
• Short: cross down, same RVOL.
• Optional: only first cross after 10:00 (skip open noise) and no new entries after 15:30."

"Exit
1. Signal flip: opposite close across VWAP with RVOL ≥ 1.2.
2. Stop: 1.0× 14-bar 5-min ATR beyond the VWAP side you just left (example).
3. Time: 15:55 flatten.
4. Giveback: if MAE exceeds 1R, scratch."

"Sizing: Same dollar-risk formula vs the ATR stop.
Cost model: Same $0.005/share/side + half-spread. Institutional 'follow' is still a taker unless you work a limit; example assumes take."

**Worked example — Synthetic 5-min (price close, VWAP, RVOL):**
"10:25 — 80.10 / 80.18 / 0.9 — below
10:30 — 80.22 / 80.19 / 1.8 — cross up
10:35 — 80.24 / 80.20 / 1.1 — fill open 80.25
11:40 — 80.55 / 80.28 / 0.8 — hold
14:10 — 80.20 / 80.31 / 1.6 — close back below → exit next open 80.18
ATR stop at entry = 80.25 − 0.40 = 79.85. Risk/share = $0.40. N = ⌊200 / 0.40⌋ = 500.
Gross: 500 × (80.18 − 80.25) = −35.00. Commission: 500 × 0.01 = −5.00. Net: −40.00.
Same rules, winner path: exit 80.70 instead. Gross: 500 × (80.70 − 80.25) = +225.00. Commission −5.00. Net +220.00.
The example is meant to show the cross is not an edge by itself; RVOL confirmation still leaves you with a ~50/50 path unless the follow-through exists. Berkowitz et al. document VWAP as a cost benchmark, not a forecast."

### (C) MOC auction-pin

"Idea. Published on-close imbalance pulls the last minutes of continuous trade and the close print toward the indicative match; you trade with a large, persistent imbalance and exit in the auction (or fade a late collapse of the imbalance — this spec is with-imbalance, pin-to-close).
Sources. Exchange rulebooks, not an alpha paper: NYSE auctions / Rule 7.35B / Pillar imbalance spec; Nasdaq Equity 4 Closing Cross / trader FAQs. Academic backdrop on close concentration: Cushing & Madhavan (2000); later auction-design papers (Comerton-Forde & Putniņš and successors). Do not treat those as a guaranteed pin-trade Sharpe."

**Cutoffs (full session):**
- "Imbalance feed starts: NYSE 15:50, then ~1s; Nasdaq EOII 15:50 every 10s; OII 15:55 every 1s.
- MOC enter/cancel freely: NYSE until 15:50; Nasdaq cancel/modify until 15:50; MOC entry until 15:55.
- After freeze: NYSE offsetting MOC/LOC only vs published significant imbalance; Nasdaq no new MOC after 15:55.
- LOC: NYSE until 15:50; offsetting after; Nasdaq until 15:58 (late LOC reprice rules apply).
- IO / closing offset: NYSE venue-specific; Nasdaq IO until 16:00.
- D-order (floor): NYSE modify until 15:59:50; Nasdaq n/a.
- Auction: 16:00 both.
Broker cutoff is earlier than the exchange. Paper-trade the exchange clock; live you must hit the broker's 15:45–15:48 class deadline.
Half day (close 13:00): shift −3h. NYSE freeze 12:50. Nasdaq: EOII 12:50, MOC off 12:55, LOC off 12:58, cross 13:00."

**Level / signal (illustrative) — From the imbalance feed:**
"• I_t = paired vs imbalance shares (NYSE Total/Market Imbalance; Nasdaq NOII Near/Far/Paired)
• P̂_t = indicative match / reference
• M_t = continuous mid
Enter with the imbalance only if, at 15:52 (example):
• |I| ≥ 5% of 20-day ADV or ≥ 50,000 shares (example)
• sign(I) stable vs 15:50 print (no flip)
• |P̂ − M| ≥ 5 bps (there is something to pin toward)
• not a halt / LULD limit state
Two implementations:
1. Continuous lean (15:52–15:58): buy the bid side if buy imbalance; stop if imbalance flips or shrinks 50%.
2. Auction exit: cover/flatten with offsetting MOC (NYSE after 15:50 only if you are shrinking the published imbalance) or LOC at P̂ ± 10 bps (example). If you are adding to the imbalance after 15:50 on NYSE, the order rejects. Retail cannot send NYSE D-orders."

"Sizing: Cap notional to a fraction of published imbalance so you are not the print: N = min(⌊R/stop⌋, 0.02 × |I|). Example stop = 20 bps of last mid (continuous) or LOC miss (auction)."

"Cost model — auction
• MOC/LOC commission: same $0.005/share (IB-class) unless the broker has an auction ticket.
• Auction 'spread': you do not pay NBBO. Cost vs mid is NOCP − M_15:59 (for a buy, positive = premium paid to pin). Historical close-auction impact is often a few bps on liquid names, much more on imbalance days — that is the trade's variance.
• No half-spread on the MOC fill; there is one official close print.
• If you entered in continuous tape first, you pay continuous spread plus auction deviation on the exit."

**Worked example — NYSE-listed ABC, full day. ADV = 2.0M shares. Mid at 15:49 = $40.00.**
"15:50:00 — Buy imbalance 120,000, paired 800,000, indic. 40.08. MOC cutoff. You may still sell MOC to offset.
15:52:00 — Imbalance still buy 110,000, indic. 40.10, mid 40.04. Signal: buy-side pin. Buy 2,000 in continuous at 40.05 (ask). 2,000 = 1.8% of I, under 2% cap.
15:56:00 — Imbalance 100,000, indic. 40.12, mid 40.09. Hold.
15:58:00 — Still buy 95,000. Submit MOC sell 2,000 (offsetting — accepted).
16:00 — NOCP = 40.11. Sell 2,000 at 40.11.
Stop would have been 40.05 × 0.998 = 39.97 if imbalance flipped.
Gross: 2000 × (40.11 − 40.05) = +120.00. Commission 2 fills: 2000 × 0.01 = −20.00. Auction premium vs 15:59 mid 40.09: you sold 40.11 (you received +2¢ vs mid) — already in gross. Net: +100.00.
Failure path: 15:56 imbalance flips to sell 40,000, indic. 39.96. You abort: sell 2,000 in tape at 39.98, no MOC. Gross: 2000 × (39.98 − 40.05) = −140.00. Commission −20.00. Net −160.00.
Nasdaq analogue: you could have entered MOC buy until 15:55 if you wanted auction-only entry (no continuous leg). After 15:55 you cannot add MOC; you can still LOC until 15:58 or IO to offset."

"Cross-notes
• DST/half-day is the main operational killer for C. Wire the calendar to NYSE's published early-close list, then set freeze = close − 10 minutes (NYSE) and Nasdaq's −10/−5/−2 minute ladder.
• A is Market Profile / Crabel-family structure, not a cost-adjusted Sharpe study.
• B uses an institutional benchmark as if it were a signal; costs and chop around VWAP usually dominate unless RVOL is extreme.
• C is an exchange-microstructure trade. After 15:50 you are often only allowed to shrink NYSE imbalance. Pin P&L is NOCP − entry, and the close can gap through your LOC. Capacity is a sliver of the published imbalance, not ADV."

---

## Q-TB7-2 — infra + local build + buy vs build (verbatim)

"The Mac is fine. The bill is licenses + the auction object, not RAM."

**What "session-pattern engine" actually is**
"One process (or a small supervisor) that, for a 500-name universe, during RTH:
1. Ingests 1-minute OHLCV + last/VWAP ingredients (trades or already-aggregated bars).
2. Maintains session VWAP + anchored VWAP (anchors: RTH open, IB freeze 10:30, optional prior-day close).
3. Freezes IBH / IBL / IBR at 10:30.
4. From 15:50 (or 12:50 on half days) merges auction imbalance into the same symbol state.
5. Emits signals into a paper broker that understands MOC/LOC, venue cutoffs, and the official close print.
Bars + VWAP + IB are cheap. Imbalance + honest MOC paper fills are the product."

**Compute / RAM / storage on M5 Max 128 GB**

| Workload | Rate | CPU | RAM | Disk |
| 500 names × 1-min bars, RTH ~390 bars | ~500 msg/min; ~195k bars/day | < 5% of one P-core | 80–200 MB state | 15–40 MB/day parquet (OHLCV+VWAP+IB flags) |
| Same 500, second bars (optional RVOL) | ~500/s peak | 1 core comfortable | 0.3–0.8 GB if you keep the day | 0.4–1.2 GB/day |
| Session VWAP from trades (not pre-binned bars) | SIP trades ~2k/s tape-wide; 500 names is a slice | 1–2 cores | 0.5–1.5 GB running sums | trades log 2–8 GB/day if you persist raw |
| Anchored VWAP (3 anchors) | O(1) per bar | noise | +a few MB | fold into bar file |
| IB levels | one max/min pass 09:30–10:30 | noise | +a few MB | fold into bar file |
| Imbalance stream 15:50–16:00 | NYSE ~1 Hz/symbol when dirty; Nasdaq 0.1 Hz then 1 Hz | noise | 50–150 MB for 500 names × 10 min of snapshots | 20–80 MB/day if you keep every tick |
| Paper broker + ledger | tiny | tiny | 50 MB | 5–20 MB/day JSONL |
| Overnight replay 2y × 500 × 1-min | batch | 4–8 cores, minutes | 2–8 GB working set | ~15–40 GB hot history |

"Peak RTH footprint if you do it right (vendor 1-min + quotes + imbalance, no full tape): well under 4 GB. If you subscribe trades+quotes for 500 names and record them: plan 10–20 GB/day and a 2 TB disk for a year of research. Do not load a 70B model during 09:30–16:00. 128 GB is headroom for research after the close, not a requirement for this engine. Half-day / DST: one calendar table. Cost is engineering, not compute."

**Engineering hours (one person, paper-quality)**

| Slice | Hours | Why it varies |
| Session clock, NYSE calendar, half-day shift, DST | 12–20 | Get this wrong and C is junk |
| 1-min ingest, gap fill, halt/LULD flags | 20–35 | Vendor SDK vs DIY |
| Session VWAP + anchored VWAP (causal, RTH-only) | 12–20 | Off-by-one on first trade is the bug |
| IB freeze + narrow/wide classifier | 8–12 | Trivial once bars are clean |
| Signal bus + flatten-at-close | 15–25 | |
| Paper broker with MOC/LOC | 40–80 | Venue matrix, reject-if-adds-to-imbalance after freeze, LOC miss, NOCP as fill |
| Imbalance client + schema normalize (NYSE vs Nasdaq fields) | 25–50 | Two feeds, two clocks |
| Replay harness (no look-ahead on VWAP/IB) | 25–40 | |
| Ops: watchdog, ledger checksum, early-close test | 15–25 | |
| Total, bars+VWAP+IB only | ~90–150 h | |
| Total with real imbalance + MOC paper | ~170–310 h | ~5–8 focused weeks |

"Building a SIP 'synthetic imbalance' from tape (more buyers than sellers into the close) is another 20–40 h and is [not — negation dropped in text extraction; sentence logic and the following sentence require it] a substitute for NOII / NYSE Order Imbalances. Do not spend those hours if you care about strategy C."

**Real imbalance vs SIP approximation**

| Source | What you get | Good for | Not good for |
| NYSE / Arca / American Order Imbalances | Paired qty, total/market imbalance, reference / indicative, collars; ~1s from freeze | C on Tape A / Arca listings | Nasdaq names |
| Nasdaq NOII (TotalView or NOIView) | Paired, imbalance side, far/near/ref, cross type; 10s then 1s | C on Nasdaq listings | NYSE floor D-order interest |
| Massive / Polygon NOI WS | NYSE-listed NOI-style fields (imbalance, paired, book clearing px) | Cheap NYSE-listed paper C | Full Nasdaq NOII; not a license-free gift — add-on + NYSE access language |
| SIP trades+quotes only | Last, NBBO, volume; you can infer late-day drift | A and B | C. No paired qty, no official imbalance side, no freeze rules |

"Databento's own note: licensing imbalance-only NYSE feeds starts around $1k/mo; $7.5k+/mo non-display for full Integrated. Databento's 2026 pass-through table lists NYSE Order Imbalances ~$2,500/firm non-display, Arca ~$1,000, American ~$1,000. Nasdaq NOII lives inside TotalView (firm + per-user; TotalView commercial is $1.6k–$1.7k firm + ~$80/user class) or a thinner NOIView product. Confirm current NYSE category (display vs non-display) before you [subscribe — word clipped in extraction]."

"SIP approximation (indicative pricing you invent): e.g. last 10 minutes signed volume, or mid vs a rolling close VWAP. Useful as a regime flag ('this name is running into the close'). Useless for MOC offset logic, because the exchange will reject an order that adds to the published imbalance after 15:50 on NYSE. You cannot simulate that reject without the real feed."

**Cheapest adequate data (indicative, 2026)**
"Goal: one-person book, 500 symbols, strategies A+B live every day, C only if the feed is real."

"Tier 0 — A+B only (recommended first build):

| Item | $/mo | Notes |
| Massive Stocks Advanced (or equivalent SIP real-time + 1-min/second aggs) | ~$199 individual | 500 symbols, VWAP from minute or second bars, IB from minute highs/lows. Quotes if you want spread inputs |
| NYSE calendar | $0 | Scrape / static file |
| Total | ~$200 | Adequate for IB + VWAP-RVOL. Not C. |
QuantConnect paper at ~$60–$300 can host A+B if you accept their bar stream and write the features yourself. Still no honest NYSE+Nasdaq imbalance."

"Tier 1 — C on NYSE-listed names only:

| Item | $/mo |
| Massive Advanced | ~$199 |
| Imbalances Expansion (individual) | ~$49 (business add-on cited ~$399) |
| NYSE imbalance license (if they pass it through / require it) | $0–$2,500 depending on how they classify you |
Treat $250–$500/mo as the optimistic individual path and $2.5k+ if NYSE calls you non-display commercial. Ask Massive/NYSE in writing. The feed is NYSE-listed only, not Nasdaq NOII."

"Tier 2 — C on both primary listing venues (the only honest 'auction engine'):

| Item | $/mo class |
| Databento US Equities Plus (live + history convenience) | ~$1,500 plan |
| NYSE + Arca Order Imbalances licenses | ~$2,500 + $1,000 |
| Nasdaq TotalView (for NOII) | ~$1,700 firm + ~$80 user |
| Ballpark all-in | $5k–$8k/mo |
That is the cheapest adequate stack if C must be venue-correct. There is no $199 product that is TotalView NOII + NYSE imbalances."

"History for overnight fit: 1-min bars, 500 names, 2 years: typically tens to low hundreds of $ on Massive flat files or Databento usage — not the live-license problem. Imbalance history is a separate schema; budget a few hundred $ to backtest C, not thousands, if you keep the universe tight."

**Paper broker: MOC support (what to build vs buy)**
"Buy the host, build the auction object. QC / IB paper will take a MOC and give you the close print. They will [not — negation dropped in extraction; the listed items are all things a proper auction model must do] reliably:
• reject a NYSE MOC that adds to the 15:50 significant imbalance,
• distinguish LOC miss vs fill,
• apply Nasdaq late-LOC reprice,
• use NOCP rather than last tape print,
• shift cutoffs on 13:00 close days.
Build (40–80 h) a thin paper matching layer:
order(venue, type in {MKT, LMT, MOC, LOC}, side, qty, limit?, tif)
Rules to encode (full day):
• NYSE: no new/cancel MOC/LOC after 15:50 except offsetting and qty ≤ last_published_|I|
• Nasdaq: no MOC after 15:55; no LOC after 15:58; no cancel after 15:50 except error windows
• Fill MOC at official close; fill LOC only if NOCP is marketable vs limit
• Broker stub deadline = exchange − 2 minutes (optional realism)
• Half-day map: close − 10m / −5m / −2m
IBKR paper is the cheapest routing test if you already have IB; still overlay your own reject logic for research honesty."

**Buy vs build verdict**

| Piece | Verdict | Why |
| 1-min store, VWAP, AVWAP, IB | Build (~1–2 weeks) | Commodity math; buying a 'session platform' is slower than 100 lines + a calendar |
| Universe + calendar + half-day | Build | One file |
| SIP live bars/quotes | Buy Massive Advanced ~$199/mo | Cheapest adequate for A+B |
| QC/Composer as the engine | Don't | Composer cannot express IB freeze + MOC rules. QC is a host, not the auction model |
| NYSE+Nasdaq imbalance | Buy the feed, do not scrape the tape | SIP approximation cannot drive MOC offset logic |
| Full C on both tapes | Buy Databento + licenses (~$5–8k/mo) or narrow C to NYSE-listed + Massive NOI (~$250–$500/mo optimistic) | There is no honest middle |
| Paper MOC/LOC | Build the state machine; optionally buy IB paper for a second fill tape | |
| GPU / extra Mac | Don't buy | Idle |

"Practical sequence for a one-person desk:
1. $200/mo + ~120 h — ship A+B on 500 names. This is the whole engine except C.
2. Add NYSE NOI add-on and paper MOC only on Tape A. Accept that Nasdaq names are dark for C.
3. Only if C's paper ledger beats costs for a quarter, open the Databento/TotalView conversation. Until then, don't pay $5k+/mo to timestamp a feed you are not sized to trade.
Do not build: ITCH parser, D-order simulation, multi-venue auction combiner, or a GPU feature store. Those hours do not move A or B and do not make C real without the licenses."

---

## Q-TB7-3 — success ratios, after-cost efficacy, failure modes (verbatim)

"After-cost honesty first: most of what follows is documented price behavior. Very little of it is a published, capacity-aware Sharpe for an outsider with SIP data and retail fees."

### 1) Initial balance / first-hour breakout — after-cost record

"What is documented. Steidlmayer's IB (first two 30-minute TPOs) and Dalton's day-types are a taxonomy, not a P&L study. The closest tested objects are opening-range breakouts (5–60 min), which overlap IB only when the range is the first hour."

"Peer-reviewed / working-paper equity results (costs stated). Zarattini–Barbon–Aziz (US stocks 2016–2023) charge $0.0035/share: unfiltered 5-min ORB Sharpe 0.48, +3.2% IRR, hit 41%. RVOL top-20: Sharpe 2.81, +41.6% IRR, hit [~48%]. That is commission-only, not spread+impact. Unfiltered first-hour-style ORB loses to SPX. The filter is the result."

"Same group, QQQ 5-min ORB: Sharpe ~1.12 net of commission. Independent replication: gross ~$0.07/share; net dies at ~2.2 ¢/share slippage — inside a ~1 ¢ QQQ spread."

"Index futures (practitioner tests with futures costs, not journal articles). A 7-year NQ test with $4.50 + 2 ticks finds tiny-target ORB ≈ coin flip; fade loses; 'break and hold to EOD / 2R' on the 15-min range is the only split that stays positive train and holdout (t ≈ 1.7–2.1, PF ~1.1). Thin trend-following [edge]."

"Descriptive structure, not edge: first hour of ES/NQ is ~25–28% of RTH volume and ~55–63% of the day's range. A 30-min OR on ES/NQ 'continues' to the close ~65–67% of days in one long descriptive sample — continuation rate ≠ after-cost expectancy, and 5-min ranges are almost always broken both ways (double break ~70%+)."

"Failure regimes for A
• Range / wide-IB days: first hour already printed the range; expansion entries are failed auctions (Dalton 'normal' day). F[ade — word clipped] the NQ result above.
• Trend / narrow-IB days: this is the only regime where 'let it run' has a documented sliver of edge.
• Half days: IB still 09:30–10:30 but you have ~2.5 h after freeze; 1R targets often do not complete; skip or fla[tten — word clipped].
• FOMC (14:00 ET): the day's range is often [wider than the] IB. First-hour breakouts get run over. Do not treat pre-FOMC IB as the day's auction.
There is [no] Steidlmayer-cited after-cost IB-expansion Sharpe in the academic record. Treat IB as a day-type switch, not a standalone system."

### 2) VWAP-cross continuation — edge or execution folklore?

"VWAP in the literature is an execution benchmark, not a directional forecast. Berkowitz–Logue–Noser (JF 1988); Madhavan, VWAP Strategies; Almgren–Chriss optimal execution. Institutions are measured against VWAP; they are not systematically 'buying the cross.'"

"What tests of the cross as a signal show.
• A large ES configuration sweep reports VWAP crossover: zero Bonferroni-significant results in ~75k tests. Mean-reversion around VWAP is where any statistical mass sat — the opposite of 'cross and follow.' Treat as one lab's mult[iple-testing result — clipped].
• Zarattini–Aziz-style 'always long above / short below VWAP' on QQQ (commission netted, $25k start) p[roves only a] session trend proxy (price vs a volume-weighted open-to-now mean), highly collinear with being long a bull tape, and con[centrated in the] first hours. Independent write-ups of similar rules find most P&L in 09:00–11:00 ET and losses into 15:00. That is not institutional 'following.'
• DAX futures 2014–2024: VWAP-plus-filters did not beat the index."

"Honest read. A VWAP cross with RVOL is a participation detector: institutions who must finish a buy program will often trade through VWAP and lift it. That can loo[k real] on trend days. On range days the line is a magnet (mean reversion), which is why the same indicator is sold as bo[th — clipped]."

"[Inside noise — clipped fragment.] Documented edge, if any, is in staying with session trend while price holds the correct side of VWAP, not in the print that tags the line."

"Failure: chop around VWAP at midday; FOMC/news spikes that gap across VWAP then revert; half days where VWAP [sample is thin — clipped]."

### 3) Closing-auction dislocations — who captures them

"Design, not a retail P&L. Hu & Murphy, Closing auctions: Nasdaq versus NYSE (JFE 2022): Nasdaq imbalance falls ~80% right after 15:50 dissemination as a homogeneous off-exchange LP set leans in. NYSE imbalance stays large until ~15:55, then drops when floor / D-orders enter the published book. Floor brokers and DMMs can place/modify closing interest later than the up[stairs public] (15:59:50); DMM auction liquidity is [not] in the public imbalance. Off-exchange LPs compete at a timing and information disadvantage on NYSE."

"Who is paid.
• DMM / floor: last-look flexibility, parity/priority at the close, obligation to offset residual imbalance and set the [auction print — clipped]; the [edge is in] the auction, not in a SIP-visible 15:52 scalp.
• Imbalance-prop / electronic offsetters on Nasdaq: they see NOII at 15:50 and the book shrinks immediately. That is the 'outsider' venue where a fast, [well-connected participant can still compete — clipped].
• Indexers / mutual funds: they are the demand; they pay the dislocation to hit NAV. Cushing & Madhavan (2000) is the classic on close clustering.
• Upstairs / SIP outsider with MOC after 15:50 on NYSE: you may only [offset — clipped]. If the pin already happened in the continuous tape because floor saw the book from mid-afternoon ([…] — clipped)."

"Dislocation size. Liquid names: close vs mid often a few bps on normal days; much larger on reconstitution / month-end / imbalance days. That premium is compensa[tion for — clipped] the move that the privileged interest already positioned for."

### 4) End-of-day reversal vs drift — which dominates, when

"These are different objects. Do not average them."

| Phenomenon | Object | Direction | When it shows | Status |
| Cross-sectional EOD reversal | Last ~30 min relative returns of individual stocks | Prior intraday winners underperform into the close | Robust across 3-year windows, size/liquidity cuts (Da et al. 2025 working paper) | Strong cross-section fact; links to Heston–Korajczyk–Sadka (2010) same-interval seasonality / short-horizon reversal pileup [— "short the index at 15:30" is not the trade]. |
| Overnight vs intraday 'tug of war' | Close-to-open vs open-to-close | Overnight continuation / clientele; many anomalies earn only overnight or only intraday | Lou–Polk–Skouras (JFE 2019); Bogousslavsky–Muravyev | Index levels often made money overnight for decades; intraday was flat-to-negative. Hard to trade the overnight leg without paying the close and the open. |
| Futures 'overnight drift' 02:00–03:00 ET | ES-type contract as Europe opens | Positive drift pre-2021 (~3.7% annualized in that hour) | Boyarchenko–Larsen–Whelan (RFS 2023) | Faded toward zero in 2021–25; authors attribute it to compressed close-imbalance dispersion (std of EOD residual signed volume 6.5% → 2.9%), i.e. algos leave less inventory for the Europe-open [drift]. |

"Which dominates for a session engine
• Name-level, last half hour: reversal (cross-section) is the academic fact — fade winners, not the index.
• Index futures into Europe's open: [drift was] the fact; post-2020 it is not.
• Trend day vs range day: EOD reversal is a range / inventory story (MMs and funds flattening). On a one-way trend day the last 30 minutes extend. Condition on IB day-type / realized trend; unconditioned 'always fade 15:30' fights index drift an[d loses — clipped].
• Month-end, quad witching, reconstitution: auction (imbalance) dominates reversal.
• FOMC 14:00: the 'end of day' economically starts at 14:00; last-30-min stats estimated on quiet days do not appl[y — clipped].
After-cost: HKS-style and EOD-reversal papers often use midpoints or conservative delays; two-leg 500-name rebalance at 15:45 is a cost monster. Capacity is in the cross-section of less-crowded names, not SPY."

### 5) Auction-feed latency — why SIP approximations mislead

"What the official feeds are. NYSE Order Imbalances / Pillar: paired, total/market imbalance, reference, indicative, collars; D-or[ders enter the] published imbalance only in the last 10 minutes; DMM auction liquidity never publishes. Nasdaq NOII on TotalView/NOIView: paired, imbalance side, far/near/ref; 10-second then 1-second. T[otalView is] proprietary. SIP (CTA/UTP) carries last sale + NBBO, not NOII and not NYSE paired qty."

"Why a SIP 'synthetic imbalance' lies
1. Wrong quantity. Tape signed volume ≠ MOC/LOC book. Hidden LOC, floor D-interest, and IO orders do not print as trade[s — clipped].
2. Wrong time. Nasdaq public imbalance collapses in seconds after 15:50; NYSE public book is stale relative to floo[r — clipped].
3. Wrong constraint. [The exchange] rejects MOC/LOC that add to the published significant imbalance. A SIP model that says 'buy more' will submit orders the matc[hing engine rejects — clipped].
4. Wrong price. Indicative/near price is an auction-clearing hypothesis including non-displayed interest. SIP mid is [not that — clipped], not last-minus-VWAP.
5. Latency ladder. Colo proprietary feed → vendor normalized API (Databento/Massive) → SIP last → your 1-min bar. Each [hop is a] filtered, delayed residual. Hu–Murphy's Nasdaq 80% shrink is the professional book reacting to NOII, not to the SIP print."

"Massive/Polygon NOI [is a] NYSE-listed imbalance product, not Nasdaq NOII and not a SIP hack. Using it on QQQ (Nasdaq-listed) as if it were [NOII is a category error — sentence truncated in extraction]."

**Failure-regime card (A/B/C together)**

| Regime | A (IB expansion) | B (VWAP follow) | C (auction pin) |
| Narrow IB, trend day | Only plausible A regime | VWAP-hold continuation can look real | Imbalance often with the trend; pin may already be in the tape |
| Wide IB, range day | Failed expansions; stop-heavy | VWAP magnet; crosses chop | Reversal / inventory; fade relative, don't pin the index |
| Half day | Short runway after 10:30 | Thin VWAP sample | Must shift cutoffs −3h; most retail stacks forget and submit dead MOCs |
| FOMC 14:00 | Pre-14:00 IB is not the day | VWAP reset in all but name | Auction is a second event; 15:50 book is news-contaminated |
| Month-end / rebalance | Noise | Noise | Imbalance is the story; outsiders pay unless offsetting with a real feed |
| Post-2020 index | Unchanged structurally | Unchanged | Close-imbalance dispersion down → less overnight-drift residue, tighter pins, less leftover for late offsetters |

"After-cost one-liners. A: unfiltered first-hour breakout is weak after a cheap commission; any published Sharpe is a RVOL/trend-day subset. B: VWAP-cross-as-entry is folklore; VWAP-as-benchmark and VWAP-as-session-trend-filter are real but not the same trade. C: dislocations exist; DMM/floor and Nasdaq NOII offsetters are in the book that sets the print; SIP-timed outsiders are usually providing the liquidity those desks want."

---

## QC notes (orchestrator)

1. Arithmetic checks (all verified): Q1 (A) 975 × 0.41 = +399.75; commission 9.75; net +390.00 ✓. Failure path 975 × (−0.21) = −204.75; net −214.50 ✓ (failure fill stated 50.27 vs stop 50.275 — 0.005 rounding, immaterial). Q1 (B) 500 × (−0.07) = −35.00; commission 5.00; net −40.00 ✓; winner 500 × 0.45 = +225.00; net +220.00 ✓. Q1 (C) 2000 × 0.06 = +120.00; commission 20.00; net +100.00 ✓; 2000/110000 = 1.8% of imbalance, under 2% cap ✓; failure 2000 × (−0.07) = −140.00; net −160.00 ✓. Q2 Tier 2: 1500 + 2500 + 1000 + 1700 + 80 ≈ $5.78k/mo, consistent with "$5k–$8k/mo" ✓.
2. **IMPORTANT — Q1 variant anomaly:** an earlier text extraction of the same Grok article (taken right after generation completed) returned a DIFFERENT rendering: (A) IBH 120.00/IBL 119.40/IBR 0.60, buy 100 @ 120.10, sell 100 @ 121.90, gross +180, costs 1.00 + 2.00 + 0.04, net +176.96; (B) buy 200 @ 80.10, sell 200 @ 80.60, gross +100, costs 2.00 + 2.00 + 0.08, net +95.92; (C) buy 500 MOC at indicative 50.60, fill 50.40, sell 50.40, gross −100, costs 5.00 + 5.00 + 0.20, net −110.20. The currently rendered article shows the XYZ/50.40/49.90 version captured verbatim above. No regenerate action was taken. The currently rendered text is treated as authoritative; the earlier variant existed — note its (A) example had its own internal inconsistency (exit 121.90 vs stated +1.0×IBR target of 120.60); its arithmetic (180 − 1 − 2 − 0.04 = 176.96) was internally consistent, as were (B) and (C).
3. Extraction artifacts: dropped short words restored only inside `[brackets]` where sentence logic unambiguously requires them; other clipped fragments marked `[clipped]`.
4. Citations rendered as named sources/provider labels with "25 / 16 / 32 sources" buttons; no raw URLs exposed in the text extraction.
5. Session note: the chat already contained three prior Q&A pairs from an earlier session on different strategies (OFI scalping, RVOL-ORB, cointegration pairs); treated as reference only; the three new questions were asked fresh.
6. Key sourced claims are research leads, not verified facts: Steidlmayer (Market Profile, CBOT 1985); Dalton, Jones & Dalton (1990); Crabel (1990); Berkowitz–Logue–Noser (1988); Zarattini–Barbon–Aziz (unfiltered 5-min ORB Sharpe 0.48, +3.2% IRR, hit 41%; RVOL top-20: Sharpe 2.81, +41.6% IRR, hit ~48% — commission-only); Hu & Murphy (2022) (Nasdaq imbalance −80% after 15:50 dissemination); Cushing & Madhavan (2000); Lou–Polk–Skouras (2019); Bogousslavsky–Muravyev (overnight/intraday); Boyarchenko–Larsen–Whelan (2023) (02:00–03:00 ET overnight drift ~3.7% ann pre-2021, faded 2021–25); Da et al. 2025 (cross-sectional EOD reversal); Heston–Korajczyk–Sadka (2010) (same-interval seasonality). Vendor prices: indicative — verify before budgeting.

---

## Source list (only papers actually used)

- Steidlmayer, J.P. (1985), Market Profile (CBOT).
- Dalton, J., Jones, E. and Dalton, R. (1990), Mind Over Markets.
- Crabel, T. (1990), Day Trading with Short Term Price Patterns.
- Berkowitz, S., Logue, D. and Noser, E. (1988), "The Total Cost of Transactions on the NYSE," Journal of Finance.
- Zarattini, G., Barbon, A. and Aziz, A. (2024), opening-range breakout studies (US stocks 2016–2023).
- Hu, E. and Murphy, D. (2022), "Closing auctions: Nasdaq versus NYSE," Journal of Financial Economics.
- Cushing, D. and Madhavan, A. (2000), "Stock Returns and Trading at the Close," Journal of Financial Markets.
- Lou, D., Polk, C. and Skouras, S. (2019), "A Tug of War: Overnight vs. Intraday Expected Returns," JFE.
- Boyarchenko, N., Larsen, L. and Whelan, K. (2023), "The Overnight Drift," Review of Financial Studies.
- Comerton-Forde, C. and Putniņš, T.J., auction-design papers (successors).
- Bogousslavsky, V. and Muravyev, D., overnight/intraday anomaly work.
- Da, Z. et al. (2025, working paper), cross-sectional end-of-day reversal.
- Heston, S.L., Korajczyk, R.A. and Sadka, R. (2010), "Intraday Patterns in Arbitrage Pricing," JF.
- Everything not attributed to one of the above — thresholds, cost figures, worked-example values — is illustrative.
