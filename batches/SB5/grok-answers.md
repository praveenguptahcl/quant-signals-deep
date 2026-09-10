# SB5 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials
- Date: 2026-09-10
- Batch: SB5 — Breakout & session-pattern family (S022, S023, S026, S028, S029, S030, S031, S033, S044, S045)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: math subscripts rendered in flattened form (e.g. DCH^U, ATR(N)); exact-duplicate sentence rendering artifacts de-duplicated. No wording, number, or cited source altered.

---

## Q-SB5-1 — formulas + worked example (verbatim)

All formulas below are the standard published definitions. Parameter ranges are those that appear in the documented sources or practitioner literature, labeled as documented or illustrative estimates. The 30-bar tape and all arithmetic on it are illustrative estimates constructed for this example — not market data.

## Notation used throughout

• Bar index i = 1..30. Each bar is a 5-minute OHLCV candle.
• O_i, H_i, L_i, C_i, V_i: open, high, low, close, volume.
• N: lookback in bars.
• When a breakout is defined, the channel is computed on completed prior bars so the current bar can actually pierce it.

## 1. Donchian breakout

Documented formula. Upper/lower bands are the highest high and lowest low over N bars. Richard Donchian's four-week rule is the 20-day version; the Turtle systems used 20-bar and 55-bar entries (documented: Luxalgo).

DCH_t^U(N) = max(H_{t-1}, ..., H_{t-N}), DCH_t^L(N) = min(L_{t-1}, ..., L_{t-N})

Two conventions exist: max over the N prior bars (inclusive of t-N, breakout-safe) vs inclusive overlay (band includes the current bar). Midline (optional): (DCH^U + DCH^L)/2. Signals (Turtle System 1 style): long if C_t > DCH_t^U (prior-20); short if C_t < DCH_t^L. System 1: enter on 20, exit on 10-bar reverse extreme. System 2: enter on 55, exit on 20-bar reverse. (Documented: Crosstrade)

Practical parameter ranges (documented):
• Entry lookbacks: N=20 (System 1 / four-week rule) and N=55 (System 2).
• Exit lookbacks: N=10 (with 20-entry) and N=20 (with 55-entry).
• Intraday: same N in bars (e.g. 20 × 5-min ≈ 100 minutes). No separate "official" 5-min N is documented; treat other values as illustrative.

## 2. Keltner-channel breakout

Two documented constructions.
Original (Keltner 1960): middle = 10-period SMA of typical price (H+L+C)/3, bands offset by the 10-period average of (H−L) (multiple 1). (Documented: Incrediblecharts)
Modern / Raschke form (what most platforms implement): middle = EMA(N) of close; upper/lower = middle ± m × ATR(N), where ATR is Wilder- or SMA/EMA-of-TR over N bars. Investopedia's write-up of the modern form is middle = EMA(20), bands at ±2×ATR (ATR length 10 or 20). Incredible Charts documents Raschke's popularized settings as 20-EMA, ATR(10), multiple 2.5. (Investopedia +1)

Signals: close (or high/low) beyond the band as volatility-adjusted breakout; alternatively fade touches in a range.
• EMA length N: commonly 20; typical cited span 15–40.
• ATR length: commonly 10 or 14 or 20; Raschke uses ATR(10).
• Multiplier m: 2 (Investopedia default); Raschke examples 2.0–2.5; some practitioners use up to 3. In the worked example the user-requested pair (20, 2×ATR) is used, with ATR also on 20 bars (explicitly marked illustrative where it differs from Raschke's ATR(10)).

## 3. Bollinger bandwidth squeeze

Bands (Bollinger): middle = SMA of close over N (default 20); upper/lower = middle ± m×σ, m=2. Bollinger specifies the population standard deviation (divide by N, not N−1). (Documented: Luxalgo) StockCharts writes the same as (upper − lower)/middle × 100 when quoting percent. (Chartschool.stockcharts)

Bandwidth: BW = (upper − lower) / middle = 2×m×σ / middle.

Squeeze definitions (documented):
• Bollinger: BW at its lowest value in ~125 periods ("about six months" on daily bars). He states the same logic applies on any timeframe, including 5-min. (YouTube)
• Normalized form ("%BandWidth"): stochastic-style rank of BW over an N-bar lookback; default N=125; 0 = squeeze, 1 = bulge. (Documented: Bollingerbands)
• Practitioner percentile variants: BBWP below 10% (sometimes 0%) as squeeze; above 90% as bulge. That 10/90 cut is a community convention on top of Bollinger's width formula, not a number from Bollinger. (Tradingview)
• Alternative TTM-style squeeze: both Bollinger bands inside the Keltner channel (not used in the numerical example).

Practical parameter ranges (documented): N=20, m=2; squeeze lookback ~125 bars on the BW series; percentile floors near the bottom decile are illustrative adaptations of that.

## 4. First-hour range / initial balance (IB)

Documented definition (Steidlmayer Market Profile): the IB is the high–low range of the first hour of the regular session, classically the first two 30-minute TPO letters (A and B). (Documented: Luxalgo) On 5-minute bars that is the first 12 bars after the RTH open.

IBH = max(H_1..H_12), IBL = min(L_1..L_12), IBR = IBH − IBL, where window = the IB window. After the window closes, IBH/IBL are frozen.

Range extension is any later trade above IBH or below IBL. Extension targets commonly plotted at IBH ± k×IBR with k = 0.5, 1.0, 1.5. (Documented: Luxalgo)
Session anchors (documented examples, ET): ES 09:30–10:30; CL 09:00–10:00; GC 08:20–09:20. (Documented: Marketstalkers)
There is no single published "expansion threshold" in Steidlmayer's original framework beyond "price trades outside the IB."

## 5. Stretched-move z-score

Documented identity. The ordinary z-score of a scalar x against a windowed mean and standard deviation:
z = (x − μ_N) / σ_N (or sample s). In price applications x is usually close (or close minus SMA), sometimes deviation from VWAP. (Documented: Ninjatrader)

Practical parameter ranges (practitioner, not a single canonical paper): lookbacks 10 / 20 / 30 bars; stretch flags often at |z| > 2 (and sometimes 2.5). Those cuts come from the Gaussian tail heuristic used in trading write-ups, not from a published theorem. (Documented: Fxnx)
In the example: N=20, population σ, evaluated at bar 30.

## Worked example — synthetic 30-bar 5-minute series

Status of these numbers: illustrative estimates. Invented path: modest first-hour two-sided trade, mid-session compression, then a late directional leg up. (Table: bars 1–30 OHLCV; opens ≈ prior close; bars 1–12 two-sided ~99.50–100.70; bars 13–24 compressing ~99.80–100.45; bars 25–30 rally to close 101.65 on rising volume.)

First hour = bars 1–12 (illustrative RTH open + 60 minutes on 5-min bars).

A. Donchian(20) at bar 30 — prior-20 convention
Window = bars 10 through 29 (exclude bar 30 so a breakout is well-defined).
• Highs in window: 100.60, 100.55, 100.45, 100.40, 100.35, 100.28, 100.22, 100.20, 100.18, 100.15, 100.12, 100.10, 100.08, 100.05, 100.15, 100.40, 100.70, 100.95, 101.20, 101.45 → max = 101.45
• Lows in window: 100.20, 100.15, 100.10, 100.15, 100.10, 100.05, 99.98, 99.95, 99.92, 99.90, 99.88, 99.85, 99.82, 99.80, 99.85, 100.00, 100.25, 100.50, 100.75, 101.00 → min = 99.80
DCH_30^U = 101.45, DCH_30^L = 99.80, mid = 100.625.
Bar-30 close 101.65 and high 101.80 both exceed 101.45 → prior-20 Donchian upside breakout. Inclusive overlay on bars 11–30 would give upper 101.80 (the current high is inside the band, so it cannot "break" itself).

B. Keltner(20, 2×ATR) at bar 30
True range TR_i = max(H_i, ...) [Wilder TR]. Thereafter ATR as 20-bar SMA of TR. TR values: 0.60, 0.50, 0.55, 0.55, 0.60, 0.55, 0.55, 0.55, 0.50, 0.40, 0.40, 0.35, 0.25, 0.25, 0.23, 0.24, 0.25, 0.25, 0.25, 0.45, 0.45, 0.45, 0.45, 0.45, 0.60 ...
ATR(20) at bar 30 as SMA of TR on bars 11–30 (illustrative; Raschke often uses ATR(10) and Wilder smoothing): 0.329.
EMA(20) of close. Seed at bar 20 with SMA of closes 1–20: 100.1275. k = 2/21 = 0.095238. Recursive updates: after bar 21: 100.110595; 22: 100.092443; 23: 100.074115; 24: 100.071819; 25: 100.093550; 26: 100.141784; 27: 100.209233; 28: 100.294068; 29: 100.389871; 30: 100.509883.
Upper = 100.509883 + 2×0.329 = 101.167883; Lower = 99.851883. Close 101.65 and high 101.80 are above the upper band → Keltner upside breakout at the requested (20, 2×ATR) settings (illustrative).

C. Bollinger bandwidth and squeeze rank at bar 30
Window = closes 11–30: 100.25, 100.30, 100.22, 100.18, 100.12, 100.08, 100.05, 100.02, 100.00, 99.98, 99.95, 99.92, 99.90, 100.05, 100.30, 100.60, 100.85, 101.10, 101.30, 101.65.
Mean = 100.341; population σ = 0.487246; bands: upper = 101.315493, lower = 99.366507; BW = (101.315493 − 99.366507)/100.341 = 0.019424 (1.942%).
Rolling BW on every 20-bar close window that exists in this short series (bars 20–30) — far shorter than Bollinger's documented ~125-bar squeeze lookback: end bar 20: 0.007004; 21: 0.007135; 22: 0.006824; 23: 0.006855; 24: 0.006855; 25: 0.006802 (narrowest in this stub); 26: 0.007353; 27: 0.009286; 28: 0.012224; 29: 0.015346; 30: 0.019424.
Among these 11 values, bar 30's 0.019424 is the maximum → illustrative percentile rank 100 (expansion / "bulge" side, not a squeeze). The squeeze candidate in this stub is bar 25 (0.006802). A production squeeze flag would compare BW to a much longer BW history (~125 bars per Bollinger), which this 30-bar toy series cannot supply.

D. Initial balance (first 12 bars) and expansion at bar 30
Bars 1..12: IBH = 100.70, IBL = 99.50, IBR = 1.20.
Bar-30 close 101.65 and high 101.80, both above IBH → upside range extension.
Distance above IBH: 0.95, i.e. 0.792 of one IBR (illustrative; not yet a 1× IBR extension target at 101.90).

E. Stretched-move z-score at bar 30
Same 20 closes as the Bollinger window, population σ: μ = 100.341, σ = 0.487246.
z = (101.65 − 100.341) / 0.487246 = 2.6865. (Sample s = 0.499904 gives z = 2.6185.) Either way |z| > 2, the conventional practitioner "stretch" cut (illustrative application of that cut).

## Compact readout at bar 30 (all figures illustrative except the formula citations)
| Object | Value | Read |
| Donchian(20) prior high / low | 101.45 / 99.80 | Close 101.65 breaks prior high |
| Keltner EMA20 / 2×ATR20 | 100.510 / ±0.658 → 101.168 / 99.852 | Close above upper band |
| BB(20,2) mid / BW | 100.341 / 1.942% | BW at local max of 11-point stub, not a squeeze |
| IBH / IBL / IBR | 100.70 / 99.50 / 1.20 | Upside extension, 0.79× IBR |
| z of close (pop. σ) | +2.69 | Stretched above +2 |

Implementation notes for the chapter. (1) Always state whether Donchian includes the current bar. (2) State ATR smoother (Wilder vs SMA) and its length. (3) State population vs sample σ for both BW and z. (4) Do not treat a 10-bar BW percentile on a 30-bar tape as Bollinger's 125-bar squeeze.

---

## Q-SB5-2 — local build + buy vs build (verbatim)

All dollar figures below are documented vendor/exchange list prices as of the cited pages (2026), or illustrative engineering estimates when labeled as such. Exchange non-display fees depend on how the firm is classified; a solo researcher may not owe every line item below, but should budget as if they do.

## What "full-session pattern engine" actually costs

Two different products are being mixed in the question:
1. Bar-derived patterns (Donchian, Keltner, Bollinger/squeeze, IB from first-hour highs/lows, streaks, z-scores). These need only 1-minute OHLCV plus a session clock.
2. Auction-imbalance reads (NYSE Order Imbalance / Nasdaq NOII paired qty, imbalance side, indicative price). These are proprietary exchange messages, not reconstructible from SIP 1-minute bars. That line item dominates cost if you want it live and commercial.
A 128 GB M5 Max is not the constraint. Data licensing and point-in-time correctness are.

## 1. Data feeds and indicative pricing

A. 1-minute bars (live + history) — documented
| Source | What you get | List price | Fit for this job |
| Massive (Polygon.io) Stocks Advanced | Real-time US stocks, minute + second aggregates, WebSocket AM.*, 20+ yr history, unlimited calls on individual-use license | $199 / month | Best cheap live 1-min SIP-style tape for 500 names. Individual-use license; commercial/redistribution is a different tier. (Polygon) |
| Massive Starter / Developer | Minute aggregates, 15-min delayed, 5–10 yr history | $29 / $79 / month | Fine for research backfill; not live RTH. (Qveris) |
| Databento US Equities, ohlcv-1m | Venue-accurate minute bars, PIT definitions, live on Standard/Plus/Unlimited | Usage-based $/GB, or subscription: US Equities Plus $1,500/mo + license fees, Unlimited $4,000/mo + licenses (annual contract on those tiers) | Correct choice if you need venue timestamps, official definitions, and the same vendor as imbalance. (Databento) |
| Databento US Equities Mini | No extra exchange license fees (personal and commercial) | Plan + Mini dataset | Cheaper if Mini coverage is enough; confirm schema includes 1-min OHLCV for your 500 names. (Databento) |
Minute aggregates does not replace an auction-imbalance feed. Minute aggregates are SIP-consolidated last-sale bars.

B. Auction imbalance — documented, and expensive
Imbalance is on prop feeds, not the SIP. Databento's equity product documents an imbalance schema (ref price, paired qty, total imbalance qty). Exchange / Databento license pass-throughs (commercial, most common Databento line items):
| Feed | Documented monthly license |
| NYSE Order Imbalances (Databento commercial non-display) | $2,500 / firm (Databento) |
| NYSE Arca Order Imbalances | $1,000 / firm |
| NYSE American Order Imbalances | $1,000 / firm |
| NYSE Order Imbalances direct from NYSE fee schedule | Access $500 + Non-Display Cat. 1/2 $2,000 each (Cat. 3 $2,000, cap $6,000) (Nyse) |
| Full NYSE Integrated (if you buy depth instead of imbalance-only) | Access $8,400 + Non-Display Cat. 1 $22,400 — not needed for imbalance-only. (Nyse) |
| Nasdaq TotalView-ITCH (Databento commercial) | $1,690 / firm + $84 / user (display or non-display); distribution higher. Required for live Nasdaq NOII-quality imbalance on Databento. |
Databento also documents that NYSE Order Imbalances as a restricted product starts around $1,000/mo vs $7,500+/mo for full Integrated non-display — the $1,000 figure is their product packaging note; the live-data license pass-through is the binding number. (Databento)
Older retail NOII display pricing ($15 non-pro / $76 pro) is an Investopedia description of Nasdaq's old display product, not a research feed. (-investopedia-com.translate)

C. Reference / PIT plumbing (usually forgotten, required)
• Point-in-time ticker map (renames, share class, listing venue). Polygon is ticker-centric; users must handle renames. Databento is symbol-centric with a documented symbology map. (GitHub)
• Session calendar (RTH 09:30–16:00 ET = 390 minutes, early closes). 2026 has 251 NYSE sessions. (Bloomberg)
• Corporate actions if you ever compare prices across days (not required for same-session Donchian/IB/streaks).

## Indicative monthly stack (three honest tiers)
| Tier | What you can compute | Documented cash cost |
| Research-delayed | All bar patterns, IB, z, squeeze, streaks on T+0 delayed or EOD | Massive Starter $29 |
| Live bars, no official imbalance | Same patterns live on 500 names | Massive Advanced $199 |
| Live bars + real auction imbalance (commercial) | Plus NOII / NYSE imbalance | Databento US Equities Plus $1,500 + NYSE imb $2,500 + Arca $1,000 + (optional American $1,000) + Nasdaq TV ~$1,690+ → roughly $6.5k–$8k/mo before you add a second venue you forgot. |
If the research op is individual / non-display-not-declared, stay on Massive $199 and omit live imbalance, or use Databento historical imbalance (usage-based GB) only in batch. Do not assume $199 includes exchange imbalance fees.

## 2. Compute load on a 128 GB M5 Max

Session arithmetic (documented inputs, illustrative products):
• RTH bars/symbol/day = 390. (Bloomberg)
• 500 symbols × 390 = 195,000 new 1-min bars per full session.
• Refresh cadence: 500 bars/minute (one closed bar per symbol).
• 60 calendar days ≈ 42–43 trading days (illustrative; 251/365 × 60 ≈ 41.3).
• Hot working set if you keep 60 RTH days resident: 8.4 million bars.

Polars throughput: there is no citable "Polars bars/sec on M5 Max" paper. Treat the following as an illustrative engineering bound, not a benchmark:
• Each minute you append 500 rows and run rolling max/min (Donchian), EMA+TR (Keltner), SMA+std (BB/z), plus streak and IB comparisons.
• Those are all O(window) vectorized reductions over ~8e6 rows or, better, O(1) incremental state per symbol (per minute).
• Even a naive full recompute of 8.4M rows in Polars on Apple Silicon is typically well under one second for this op mix (groupby + rolling on a few float columns). Incremental state is sub-millisecond.
• M5 Max unified memory is 128 GB at ~614 GB/s — bandwidth is two orders of magnitude above what 8.4M rows require. (Awesomeagents)

Verdict: real-time 1-minute refresh of 500 symbols is trivial on this machine. You will spend more time in WebSocket parse, parquet fsync, and UI than in indicator math. Do not buy a GPU for this. Keep features incremental (per-symbol ring buffers) so a missed minute is a 500-row repair, not a rebuild. Extended-hours (04:00–20:00) roughly 2.5× bar count vs RTH-only; still trivial.

## 3. RAM and disk for 60 days of 1-min bars

Row count (illustrative from documented session length):
| Universe | Session | Trading days (illustrative 43) | Bars |
| 500 names | RTH 390 min | 43 | ~8.4M |
| 500 names | 04:00–20:00 = 960 min | 43 | ~20.6M |

Bytes (illustrative encoding, not a vendor spec): Per bar store: symbol_id u16, ts i64, O,H,L,C,VWAP f32, volume u32, trades u32 ≈ 40–48 bytes raw. Parquet + zstd on OHLCV typically lands around 15–40 bytes/bar depending on price entropy.
| Store | RTH 60d | Ext-hours 60d |
| Uncompressed columnar | ~0.35–0.40 GB | ~0.85–1.0 GB |
| Parquet zstd (illustrative) | ~0.15–0.35 GB | ~0.4–0.8 GB |
| In-RAM Polars + feature columns (×3–5) | ~1–2 GB | ~3–5 GB |
| Plus live imbalance prints (open/close windows only) | tens of MB | tens of MB |

128 GB headroom: 60 days of 500 names is a rounding error. You could keep years of 1-min RTH for 500 names in RAM if you wanted (illustrative: 500 × 390 × 252 × 5 yr ≈ 246M bars × ~48 B ≈ 12 GB). SSD wear from naive per-minute full rewrites is the only storage issue — write a daily partitioned parquet (date=/symbol= or date= with a symbol column), append-only. Also persist: PIT symbol map, corporate-action log, session calendar, feature snapshot at each bar close.

## 4. Engineering hours (illustrative)

Assume one strong engineer who already knows Polars and the indicator definitions from your chapter.
| Workstream | Hours (illustrative) | Notes |
| Feed client + reconnect + bar alignment to ET minute close | 20–40 | Massive WS is easy; Databento live is cleaner timestamps |
| Store: partitioned parquet, idempotent append, late bar repair | 15–25 | This is where PIT dies if sloppy |
| Session calendar + IB freeze at 10:30 ET + early-close days | 10–15 | Must be clock-correct, not "first 12 bars of whatever arrived" |
| Feature lib: Donchian, Keltner (state EMA/ATR), BB/BW/percentile, z, streaks | 20–30 | Formulas you already specified |
| Squeeze rank vs 125-bar (or session-scaled) BW history | 8–12 | Don't fake 125 with 11 bars |
| Imbalance normalize NYSE vs Nasdaq field names | 20–40 | Only if you buy the feed; venue schemas differ. (Databento) |
| PIT ticker / listing-venue map + survivorship | 15–30 | Non-negotiable for a research book |
| Screener + alert layer + tests vs golden bars | 25–40 | |
| Total, bars-only live engine | ~110–190 h | ~3–5 weeks focused |
| + production imbalance + licenses + recon | +40–80 h and weeks of vendor paperwork | |

Add 30–50% if this must emit a research-grade event log (as-of time, revision of a bar, which feed). Ongoing: a few hours/month for vendor breakage, halt days, symbol adds, and early closes.

## 5. Buy vs build vs TradingView-style screeners

TradingView
Documented: no first-party market-data API for this; automation is webhooks on a paid plan. Ultimate is $199.95/mo (only tier professionals can buy). Pine Screener can scan large universes, including indices up to ~40k bars. (Matchmybroker)
Unusable as the research system of record. Reasons: you do not own the bar construction, you cannot prove point-in-time membership of the 500-name universe, you cannot freeze a feature convention (prior-bar Donchian, population σ, IB clock) in a repo. Fine as a visual sanity check, not as the engine.

Vendor "pattern APIs"
Massive exposes some canned technical indicators on their API. Those are convenience SMA/RSI-class endpoints, not your Donchian-20-prior-bar convention + session IB + 125-bar BW percentile + imbalance. You would still recompute everything locally to match the chapter. Not a substitute.

Verdict for a research operation that needs point-in-time correctness
Build the engine; buy the tape; do not buy the patterns.
| Decision | Recommendation |
| 1-min OHLCV | Buy Massive Advanced ($199) if individual/live SIP bars suffice; buy Databento if you need venue clocks and will also take imbalance. |
| Auction imbalance | Buy only if the chapter's "auction-imbalance reads" are first-class live signals. Budget low-to-mid four figures per month commercial, not $199. Historical-only imbalance via Databento usage is the sane research-first path. |
| Feature code | Build. Definitions (prior-bar Donchian, population σ, IB clock, BW lookback) are your IP and must be frozen in a repo with tests. |
| Screener UI | Build a 200-line Polars + small web/terminal, or pipe events into whatever you already use. TV is optional dressing. |
| Hardware | Keep the 128 GB M5 Max. It is oversized for 500×1-min. Spend money on licenses and calendar correctness, not compute. |

Minimum credible research stack (PIT, live bars, no official imbalance): $199/mo and 3–5 weeks to a tested feature store. Real-time 1-min refresh is computationally free.
Minimum credible stack that includes live NYSE+Nasdaq imbalance for a commercial research desk: plan $6k–$8k/mo all-in on documented list fees, plus contracting time. That is the line where "full-session pattern engine" becomes honest.
If the document only needs imbalance as a historical overlay on the close (not a live 15:50–16:00 state machine), pull Databento imbalance in batch after the session.

---

## Q-SB5-3 — success ratios, after-cost efficacy, failure modes (verbatim)

After-cost honesty first: almost every "edge" below is either regime-dependent, capacity-limited, or already a volatility-timing story rather than a directional one. Numbers are tagged as documented (paper/URL) or as practitioner samples that are not peer-reviewed.

## 1. Donchian / ATR-channel breakouts, especially intraday

What is documented. Classic Turtle rules are daily (20/10 and 55/20 Donchian) on futures, not a 1-minute equity book. The original rules sized by ATR ("N") and risked a fixed fraction of equity. Polson and Sokolov (2026) reconstruct the math (Kelly / volatility targeting) and warn that their simulated commodity results are idealized: independent trending markets; "real trading costs, delays, and price impact would lower them." (Papers.ssrn)

After-cost results that exist:
• Equities, daily, 179 US stocks, Apr 2018–Aug 2026 (practitioner study, not a journal): 20/20 beat buy-and-hold on 14/179 names with fees, 25/179 with zero fees. Most names made money in absolute terms (112/179 with fees) but lagged the drift of buy-and-hold. Fees moved the count; they did not flip the conclusion. (Guanalyser)
• S&P 500 constituents, Feb 1985–Oct 2014, 20-day Donchian with intraday fill at the channel (Cohen, Journal of Technical Analysis, CMT, 2016): high-breakouts are strong on the breakout day; low-breakouts catch up later. If you wait for the close of day 0, 20-day adjusted returns shrink to 0.294% (high breaks) vs 0.653% (low breaks). That is a holding-period mean, not a Sharpe after costs. (Cmtassociation)
• SAFEX futures Turtle-style systems (Swart 2016 thesis): in-sample did not consistently beat buy-and-hold; out-of-sample was better but "significant volatility" remained. (Academia)
• Soybean futures, 1980–2007 (Rayome, Journal of Finance Issues): best-case path $5,000 → $187,763 over 27 years (14.67% CAGR documented in the abstract). Stops/capital preservation, not the channel itself, are described as the binding ingredient. Single-market, pre-HFT sample. (Academia)
• Futures trend-following as a family (Baltas–Kosowski): CTA returns load on time-series momentum; capacity constraints are not statistically obvious at CTA scale. That is diversified futures, not 500-stock 1-minute Donchian. (Papers.ssrn)

Trend vs chop (the actual failure regime). Channel breakouts have a structural 35–45% win-rate shape: many small false breaks, few large trends. IFTA 2023 notes false-breakout / whipsaw as the binding failure mode and that Turtle-style rules need a trailing stop to stay solvent. Short-side Donchian in equity indices is the worst sleeve (one four-market practitioner test: shorts 24.4% win vs longs 42.6%). (Ifta)

Intraday specifically. There is no comparable peer-reviewed after-cost study of 1-minute or 5-minute Donchian/Keltner on 500 US stocks. Scaling daily Turtle logic to 1-minute multiplies trade count by ~390× per session. At even 1–2 bp round-trip on a liquid name, a system that fires a few times a day per name will eat a daily-style Sharpe. Failure regime: range days, lunch chop, and any session where channel width < 1 × ATR (practitioner filter, not a paper law).

Honest use. Treat Donchian/Keltner as a regime detector (are we outside a recent range / ATR envelope?) plus a futures-style overlay, not as an equity day-trading alpha. After costs, the documented residual is in slow, diversified, trending futures, not in intraday stock breakouts.

## 2. Bollinger squeeze → expansion

Bollinger's claim is a volatility-timing claim: BandWidth at a ~125-bar low precedes a rise in volatility; direction is given by the subsequent band break, not by the squeeze itself.

Documented directional tests:
• Lento, Gradojevic, Wright (Applied Financial Economics Letters, 2007): after transaction costs, standard BB rules do not beat buy-and-hold; a contrarian use of the bands does better. That is the opposite of "squeeze then go with the break." (Tandfonline)
• Leung (Massey PhD, 2015): BB "Squeeze" as Bollinger defined it had significant R_buy − R_sell in 9 of 14 markets in the pre-1983 sample; profitability decays after the method becomes public; it disappears in the S&P 500 and DJIA after 1983. Average R_buy − R_sell falls from 0.454% (pre-1983) to 0.002% in the last subsample. Consistent with self-destruction after publication. (Mro.massey)
• Bajgrowicz–Scaillet (2012) and Sullivan–Timmermann–White (1999) do not test the squeeze; they test channel/filter families. Using them to "prove the squeeze is dead" is a category error. What they do show: after multiple-testing and costs, data-mined technical rules as a class lose economic value. (Thefinsense)
• QuantifiedStrategies practitioner squeeze+breakout: "doesn't do particularly well for any asset… doesn't beat buy and hold." Not a journal. (Quantifiedstrategies)

What survives. A squeeze is a low-vol state. Options, vol-targeting, and "don't fade a break that starts from a 125-bar BW low" are coherent. A long/short directional squeeze-breakout book on equities does not have a documented after-cost edge in the post-1983 US sample. Failure regimes: false breaks out of a tight range (the usual chop), and any market where the squeeze has already been arbitraged (large-cap US after publication).

## 3. Gap-and-go vs gap-fade — base rates after costs

Define terms: fill = price trades the prior close; fade = close below (above) the open after a gap up (down); go = session extends the gap.

Index / futures (better samples):
• E-mini S&P, 2,167 gaps > 1 point, 1998–Apr 2008, fade with no stop, target prior close, flatten EOD: 72.6% hit fill or finish green. Profit factor was only marginal — the 27% that never fill are large. That is the after-cost warning even before spreads. (Forexfactory)
• NQ, 2,791 days, 2015–2025 (practitioner): 100% fill by close = 60.3% overall; 77.8% if gap < 0.3 × ATR; 8.2% if gap > 1.2 × ATR; 70.4% if the open is inside the prior day range vs ~44–47% if it opens outside. (Tradingstats)
• Same shop on timing: of gaps that do fill, ~51% of ES and ~61% of NQ fills are done by 30 minutes after the open. If you are trading gap-and-go, survival of the first 30 minutes without a fill is the documented tilt toward continuation. (Tradingstats)

Single-name / high-beta practitioner (not peer-reviewed): 3,463 gap-ups in QQQ/NVDA/TSLA/AMD/SMCI/COIN, 2022–2026: close-below-open is ~48–53% in every gap-size bucket (intraday direction is a coin flip). Full fill collapses with size: 44% for 0–0.5% gaps vs 8% above 6%. (Vortexcapitalgroup)

Academic overlay, not a gap-fill table: Lou–Polk–Skouras (JFE 2019) document a tug of war: firm-level overnight continuation and intraday reversal that lasts for years. Momentum-style premia accrue overnight; many other anomalies accrue intraday. That is the structural reason small overnight gaps mean-revert in cash hours and large news gaps do not. (ScienceDirect)

After-cost honesty.
• Small, no-news, inside-range gaps: fade base rate is high (70%+ fill in index futures). Edge dies if you use no stop — left tail of unfilled gaps dominates. Costs on a 10–20 bp stock gap can exceed expected fill if you pay the open spread.
• Large / catalyst / outside-range gaps: do not fade. Fill rates in the documented NQ bucket drop to single digits.
• Overnight drift itself (close-to-open) is large in US equities (French–Roll 1986; Lou–Polk–Skouras). Harvesting it by buying every close and selling every open is not free: Billing's 2015–2026 basket with 5 bp round trip already knocks SPY/QQQ/IWM overnight harvesting negative. (Robertbilling)

Failure regimes: Monday large gap-ups (higher same-day full-erase rate in one SPY practitioner cut), earnings/macro mornings, and any name where your size is the open.

## 4. First half-hour → last half-hour (Heston et al. and Gao et al.)

Two different facts are routinely conflated.

A. Cross-sectional, same clock time next days — Heston, Korajczyk, Sadka, Journal of Finance 2010. Returns continue at the same half-hour slot that is an exact multiple of one trading day, out to ≥40 days. Stronger in the first and last half-hour. Volume, imbalance, vol, and spreads show similar periodicity but do not explain the return pattern. Adjacent-interval reversal is mostly bid–ask bounce / liquidity lasting <1 hour. Economic claim: timing rebalance flow can save about one effective spread. That is a cost-reduction result more than a standalone alpha book. (Onlinelibrary.wiley)

B. Time-series, same day — Gao, Han, Li, Zhou, Journal of Financial Economics 2018 ("Market Intraday Momentum"). SPY, 1993–2013. First half-hour return measured from prior close (so it includes the overnight gap) predicts the last half-hour. Documented magnitudes:
• Predictive R² = 1.6% (first half-hour alone); 2.6% if you add the 12th half-hour.
• Timing on the sign of the first half-hour: 6.67% per annum, volatility 6.19%.
• Stronger on high-vol, high-volume, recession, and macro-news days. Also present in 10 other liquid ETFs. (ScienceDirect)

Replications: 12/16 developed markets significant in-sample (Li–Zhang–Zheng / Journal of Financial Markets 2021 style global study); China futures slopes 0.05–0.10 with R² around 1.8%. In China stocks, Zhang–Ma-type work attributes most of the signal to the overnight piece, not the 09:30–10:00 cash print. (ScienceDirect)

Tradability. Last-half-hour SPY/ES is liquid, so the Gao timing book is implementable for index products if you can short. Capacity is the close auction / MOC crowd, not a 500-name stock scanner. HKS is not "buy the first 30 minutes, hold to the last 30." It is "the same clock slot tends to rhyme across days," useful for when to execute a pre-existing portfolio, not a 30-minute momentum scalp.

Failure regimes. Quiet, low-volume, non-news days (Gao: effect shrinks). Post-sample decay is an open question; third-party recreations through 2026 on SPY-like series show a much lower live CAGR than the paper's timing numbers (one public reconstruction ~3.5% with a 0.45 Sharpe — not the paper, treat as a caution, not a citation of Gao). If your "first half-hour" excludes overnight, you are not running Gao's specification.

## 5. Open-auction imbalance continuation

What is documented.
• Chordia–Subrahmanyam, JFE 2004: daily signed imbalance is autocorrelated; lagged imbalance positively predicts same-stock daily returns (price pressure from split institutional flow). Strategy returns are statistically significant in 1988–1998 NYSE. This is daily, not the opening cross. (ScienceDirect)
• Challet–Gourianov, arXiv 1802.01921: US open/close indicative auction prices are strongly mean-reverting because the published imbalance is. Indicative price is sub-diffusive for 73% of names at the open and 93% at the close. Reaction of the final auction price to a single order is weaker at the open than at the close. Translation: the open imbalance wiggles; it is a noisier predictor than the close. (Ar5iv.labs.arxiv)
• Jegadeesh–Wu, JFQA 2026: opening auctions are illiquid; closing auctions have lower impact than continuous trading except in Nasdaq microcaps. Anomaly-style long/short costs using the cheaper venue: 17–41 bp annualized for some fundamental sorts. Direct implication: you generally do not want to express a small predicted edge in the open auction. (Researchgate)
• Close-window microstructure (Imperial MSc, 2025, NYSE vs Nasdaq last 10 minutes): venue-specific R² appears near D-Quote cutoff (~15:59) and Nasdaq NOII updates; not a licensed-journal result, but consistent with "only specialists with the feed and the right order type trade this." (Imperial)

Who can trade open imbalance.
| Constraint | Reality |
| Data | Open imbalance is prop-feed (NYSE Order Imbalances, Nasdaq opening cross / TotalView). SIP 1-minute bars do not contain it. |
| Latency | Indicative prints update on a seconds grid and mean-revert. A research laptop reading a 1-second snapshot is not racing the auction. |
| Venue | Must be in the listing-venue auction (or a broker that pipes there). MOO/LOO vs on-close types differ by exchange. |
| Capacity | Jegadeesh–Wu: the open is the expensive room. A 500-name book that "goes with imbalance" at 09:30 is paying the illiquid side. |
| Signal | Autocorrelation of daily imbalance (Chordia–Subrahmanyam) ≠ "the 09:28 NYSE reference price predicts 09:30–10:00." The latter is plausible but not given as a published after-cost Sharpe. |

Honest use. Close imbalance / MOC is the documented, lower-impact place to put flow. Open imbalance is a state variable for "how violent will the first prints be," not a retail-latency continuation trade. Failure regimes: cancel/replace storms that flip the indicative (Challet's mean-reversion), DMM D-Quotes on NYSE that are invisible until late, and any stock where your order is the imbalance.

## Cross-cutting after-cost map
| Idea | Documented directional edge after costs? | What actually survives | Dies when |
| Intraday Donchian/Keltner on stocks | Not in a peer-reviewed after-cost 1-min study | Daily/futures trend + ATR sizing; range-width filter | Chop, shorts in equity indices, high trade rate |
| Squeeze → directional breakout | US large-cap post-1983: no (Leung; Lento et al. favor fade of bands) | Vol expansion timing, options | Using squeeze as a side |
| Fade small inside-range gaps | High fill rate, modest expectancy once tails + costs | Size- and location-conditioned fades on ES/NQ | Large / news / outside-range gaps |
| Gap-and-go | Only after the first 30 min does not fill, and for large ATR gaps | Conditional continuation | Blindly buying every gap-up |
| HKS same-slot continuation | Yes as execution timing (~1 effective spread) | Schedule rebalances | Treating it as a 30-min scalp |
| Gao first→last half-hour | Yes on SPY/liquid ETFs, 1993–2013, R² 1.6–2.6%, timing ~6–7% vol ~6% | Index last-half-hour timing; include overnight in "first half-hour" | Quiet days; single-name capacity |
| Open auction imbalance | Daily imbalance predicts (2004); open auction itself is illiquid and indicative mean-reverts | Close auction / MOC; use open imb as risk state | Going with open imb as a latency-sensitive alpha |

For the research chapter: write these five as conditional state variables (trend/chop, compressed vol, gap size × location, clock-slot, auction state). The after-cost literature does not support wiring all five as unconditional 1-minute entries on 500 names.

---

## Tape reconstruction (orchestrator, 2026-09-10) — NOT Grok verbatim

Grok's Q-SB5-1 answer described a synthetic 30-bar tape and printed derived values but never printed the full OHLCV rows. The file `batches/SB5/ohlcv_30bar.csv` (this directory) reconstructs a self-consistent tape from the answer's printed anchors. **This tape is a reconstruction, not Grok's verbatim output.**

Anchors matched exactly:
- Closes bars 11–30 (20 printed values, e.g. bar-30 close 101.65)
- Highs/lows bars 10–29 (20 printed values each; Donchian upper 101.45 / lower 99.80)
- EMA(20) seed = SMA(closes 1–20) = 100.1275 (forced by construction)
- Bollinger BW at bar 30 = 0.019424, rolling stub values bar 20–30 reproduced
- IBH = 100.70 / IBL = 99.50 (bars 1–12), bar-30 upside extension 0.79× IBR
- Stretched-move z at bar 30 = +2.6865 (population σ)
- Bar-30 high 101.80 breaks both Donchian(20) and Keltner(20, 2×ATR) upper bands

Known deviations from Grok's printed internals (Grok's own arithmetic did not close):
1. ATR(20) on bars 11–30 (SMA of Wilder TR) = **0.334** from this tape vs Grok's printed 0.329. Grok's printed TR list was itself inconsistent (its bar-30 TR alone must be ≥ |101.80 − 101.30| = 0.50, which no 20-bar window averaging to 0.329 can contain).
2. EMA(20) at bar 30 = **100.4915** vs Grok's printed 100.509883. Grok's own chain was already inconsistent: its bar-21 value (100.110595) does not follow from its stated seed (100.1275) and bar-21 close (100.25), which give 100.1393. The reconstruction's EMA chain is exact given the seed and printed closes.
3. Closes/highs/lows for bars 1–9 and all opens/volumes are chosen (opens = prior close; volumes moderate early, compressing mid, rising into the bar 25–30 rally). Any tape satisfying the anchors is admissible; this one is valid (L ≤ min(O,C), H ≥ max(O,C) on every bar).
