# TB5 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials (account: Praveen Gupta)
- Date: 2026-09-10
- Chat: https://grok.com/c/2f556646-070f-4d88-b11e-73d312412c2d
- Batch: TB5 — Volatility & options-informed (T041–T050)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim via page text extraction.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: formulas recovered from the page's KaTeX MathML annotations. Inline words dropped by the page's text extraction are marked with `[brackets]`; they are page-rendering artifacts, not Grok omissions. Mid-sentence truncations are marked similarly. All thresholds are illustrative examples.
- Nothing here is a live-trading spec.

---

## Q-TB5-1 — mechanics + worked example (verbatim)

"This is a mechanics spec, not a recommendation. Every numeric threshold below is an **example** for illustration on liquid index/ETF names (SPX/SPY-class). Real books need live calibration, venue fees, and a hard event calendar. Sources at the end."

### Shared plumbing (all three)

**Options-chain handling**
- Universe: nearest two expiries with DTE in a window (example: 14–45 DTE for A; 0–7 DTE plus monthly for B; 7–45 DTE for C).
- Filter: bid > 0, ask > 0, spread/mid ≤ 8–12% (example), OI ≥ 200 or volume ≥ 50 on the day, no obviously stale NBBO.
- Mid = (bid+ask)/2. Trade at **worse of mid±½ spread** plus per-contract fee.
- Greeks: Black–Scholes or BSM with dividend yield + SOFR; recompute after every quote update.
- Corporate actions / early exercise: avoid single-stock American options for A; prefer SPX/XSP or European-style.
- Timestamp everything to the same clock as the hedge instrument (ES/SPY).

**Fee/spread accounting used in examples**
- Option round-trip: half-spread paid on entry + half-spread on exit + $0.65/contract commission each way (example retail-ish; institutional is lower).
- Stock/ETF hedge: $0.005/share + 1 bp slippage on notional (example).
- Futures hedge alternative: $1.25/side + 0.25 tick slippage.

**Risk limits (shared skeleton)**
- Event blackout: no new A or B entries 2 trading days before FOMC, CPI, NFP, OPEX if using 0DTE gamma; flatten A if DTE ≤ 5 into a scheduled binary event.
- Vol-spike stop (example): close A if VIX 1-day jump > +25% *or* 15-min realized vol > 2.5× HAR forecast.
- Name concentration: max 25% of vega budget in one underlier.
- Overnight gap: A is short gamma; size so a 3σ overnight move ≤ 2% of NAV.

### (A) Variance-risk-premium harvester

"**Short ATM (or 50Δ) straddle, delta-hedged, when IV is rich vs HAR**"

**Signal**
HAR-RV (Corsi 2009 style) on close-to-close or 5-min RV:
RV̂_{t,t+h} = β_0 + β_d·RV^{(d)}_t + β_w·RV^{(w)}_t + β_m·RV^{(m)}_t
with h matched to option tenor (e.g. 21 trading days).
IV input: ATM IV from the chosen expiry, or model-free IV.
Example richness:
VRP_t = IV_ATM − RV̂_HAR
Enter short if VRP_t ≥ +3 vol points **and** IV/RV̂ ≥ 1.15 (examples). Skip if IV rank > 80 (example regime gate — selling already-exploded vol is a different trade).

**Entry / exit**
- **Entry:** sell 1 ATM call + 1 ATM put, same expiry; immediately delta-hedge to |net Δ| ≤ 0.05.
- **Hold:** 5–10 sessions or to 7 DTE, whichever first (example).
- **Exit richness fade:** cover if VRP < +0.5 vol pt.
- **Hard stops (examples):** straddle mark-to-mid loss ≥ 1.5× credit received; or underlier move ≥ 1.75× implied move; or vol-spike rule above.

**Delta hedge**
- Frequency: **once daily at the cash close** is the academic default and what the worked example uses; desks often band-hedge (|Δ| > 0.10) or time-hedge every 30–60 min. More frequent hedging cuts residual Δ but **raises cost and can lock in realized variance**.
- Hedge instrument: SPY or ES; use option Δ from mid IV.
- Cost: each hedge pays spread + fee; that is a drag on the VRP.

"Approximate discrete P&L of a short delta-hedged option over one day (Carr–Wu / Bakshi–Kapadia intuition): you earn implied variance, you pay realized variance plus hedge friction. A short ATM straddle is a noisy local variance swap."

**Sizing (vega / vol targeting)**
Example: target **$1,000 vega** per unit.
ATM straddle vega ≈ 2 × S × √T × φ(d_1)/100 per contract.
Scale contracts N = vega_budget / vega_straddle.
Alternatively size so 1 vol-point adverse IV move = 0.5% NAV.

**Worked example A — 5-day short straddle, daily Δ-hedge (synthetic)**
Spot S_0=100. 21-DTE ATM straddle.
IV = 22%, HAR-RV = 16% → VRP = +6 pts → **enter** (example rule).
Call mid = put mid = 2.50 → straddle mid 5.00.
NBBO 4.90 / 5.10. Sell at **4.90**. Credit = **$490** per 1×1.
Commission 4 × $0.65 = $2.60 on the four option legs over life (open+close).
Initial Δ: call +0.52, put −0.48 → net short-straddle Δ ≈ **+0.04**.
Hedge: **short 4 shares** at 100 (round; example 1 contract = 100 shares).

Synthetic path (close prices): 100, 101.2, 100.4, 102.0, 101.0, 100.6.
Daily |return| modest → realized vol over 5 days ≈ 14% ann. < 22% IV.

| Day | S | Net option Δ (short book) | Hedge shares (short +, meaning short stock) | Hedge trade | Hedge P&L vs prior S | Notes |
|---|---|---|---|---|---|---|
| 0 | 100.0 | +0.04 | +4 | short 4 @ 100 | — | entry |
| 1 | 101.2 | −0.18 | −18 | buy 22 @ 101.2 | 4×(100−101.2)= −4.80 | Δ flipped with spot up |
| 2 | 100.4 | +0.02 | +2 | sell 20 @ 100.4 | (−18)×(101.2−100.4)= +14.40 | |
| 3 | 102.0 | −0.28 | −28 | buy 30 @ 102.0 | 2×(100.4−102.0)= −3.20 | |
| 4 | 101.0 | −0.10 | −10 | sell 18 @ 101.0 | (−28)×(102.0−101.0)= +28.00 | |
| 5 | 100.6 | 0 (exit) | 0 | buy 10 @ 100.6 | (−10)×(101.0−100.6)= +4.00 | flatten |

Hedge P&L (share $) = −4.80+14.40−3.20+28.00+4.00 = **+$38.40**.
Hedge friction example: 100 shares traded × $0.005 + 1 bp on ~$10k notional turnover ≈ **$1.50**.
Net hedge ≈ **+$36.90**.

Options: cover straddle at mid 4.20 after 5 days of theta and lower RV; pay ask **4.28** (spread).
Option P&L = 490 − 428 − 2.60 = **+$59.40**.

**Total P&L ≈ 59.40 + 36.90 = +$96.30** on one 1-lot (~$1k initial margin-ish on SPY-scale; SPX would be 10×).
"Edge came from IV 22% vs path RV ~14%, minus spreads. A 4% gap day would have flipped the sign. That is the left tail the literature flags."

### (B) GEX pin / dealer-positioning fade

**Signal computation**
Per strike k, customer-signed gamma × OI × spot² scaling (vendor conventions differ — **do not mix vendors**):
GEX_k ≈ Γ_k · OI_k · S² · 0.01 · M
with M=100 for equity options.
**Dealer GEX** is typically **−customer GEX** if customers are net long options (standard assumption; wrong when customers are net short).
- **Call wall:** strike with max positive *dealer* call gamma.
- **Put wall:** strike with max put gamma concentration.
- **Flip / zero-gamma:** spot where net dealer GEX changes sign.
- Regime: net GEX > 0 → dealers buy dips / sell rips (fade, pin). Net GEX < 0 → do **not** fade.

**Entry / exit (positive-GEX fade — example)**
- Regime: net dealer GEX > 0 and spot above flip.
- Signal: spot tags call wall from below **and** 15-min momentum decelerates (example: last 15-min return < 30% of prior 15-min).
- Entry: short underlying or short call vertical into the wall.
- Target: mid of range or max-GEX strike (pin magnet).
- Stop: **through the wall by 0.4–0.6%** (example) — a clean break often *is* the flip.
- Time stop: flatten into the last 20 min if using 0DTE gamma (pin can release).

**Sizing**
Not vega-primary. Size by **dollar gamma you are fading** or by 0.5–1.0× average true range. Example: risk 0.4% NAV to the stop.

**Worked example B — gamma-wall map + fade (synthetic SPY-like)**
Spot **575.20**. Net dealer GEX **+1.8bn** (positive). Flip **568**.

| Strike | Dealer GEX ($mm / 1%) | Role |
|---|---|---|
| 565 | −420 | put wall |
| 570 | +180 | |
| 575 | +910 | max GEX / pin magnet |
| 580 | +640 | call wall |
| 585 | +210 | |

"Map: range thesis 570–580, magnet 575."
Trade: 11:40, spot prints 579.80 into the 580 call wall. Sell 200 SPY @ 579.75 (1 bp slip). Stop 583.20 (through wall). Target 575.40.
Next 4 hours: grind 579.8 → 577.1 → 575.6. Cover 200 @ 575.65.
Gross = 200 × 4.10 = $820.
Fees + 1 bp each way ≈ $23.
Net ≈ +$797.
"If spot had ripped to 583.4, stop loss ≈ 200 × 3.45 + fees ≈ −$710. The regime filter is the whole trade."

### (C) Unusual-options-activity follower (sweep → equity)

**Signal**
"Keep **single-leg, opening, aggressive** flow; discard most multi-leg and mid-prints." Example screen (all examples):
1. Sweep (multi-exchange, same second), not block.
2. Premium ≥ $250k (single-name) or $500k (mega-cap).
3. Fill at ask (calls) or bid (puts sold — weaker).
4. Volume / prior OI ≥ 3× (opening bias).
5. DTE 7–45; delta 0.25–0.45 (not 5Δ lottery).
6. Same-side repeat within 30 min raises conviction.
"Blocks are more often hedges; sweeps are urgency."

**Entry / exit**
- "Do **not** automatically buy the same option (you pay the sweep's impact)."
- Example follower: buy the [underlying — inline word dropped by page extraction] (or a tighter call spread) on a pullback of 0.2–0.5% within 30–90 minutes, only if the tape does not [show reversal — sentence truncated in page extraction].
- Stop: 1.0–1.5× ATR(14) or −1.2% (example).
- Target: 1.5–2.0R or time-stop 2–5 sessions (flow alpha decays).
- Blackout: earnings tomorrow → skip (you are buying someone else's event bet).

**Sizing**
Risk 0.5–1.0% NAV to the stop. Not vega-targeted unless you clone the option.

**Worked example C — sweep-follow equity (synthetic)**
Name XYZ, spot **84.20**. 10:17 ET: **2,400** of the 21-DTE **87.5 calls** swept across 5 exchanges **at the ask** **$1.85**, premium **$444k**, prior OI 410 → vol/OI ≈ 5.9. Delta ≈ 0.32. Passes example filters.
Follower: wait. 10:41 dip to **83.85**. [Buy] 800 shares @ **83.88** (1 bp).
[Stop] **82.90**. [Target] **86.20**.
Day 2 close **85.70**. [Sell] 800 @ **85.68**.
Gross = 800 × 1.80 = **$1,440**.
Stock fees + 1 bp rt ≈ [amount dropped by page extraction; implied ≈$17 from the net figure].
Net ≈ **+$1,423**.
"Risk if stopped: 800 × 0.98 + fees ≈ **−$800** (about 0.8R)." [arithmetic check: 800×0.98=784; 1,440/784≈1.84R — "0.8R" is likely Grok's typo for ~1.8R; preserved verbatim]
"If you had chased the same 87.5 calls at $1.95 after the sweep, mid later $2.05, exit $2.05 ask-side [sentence ends here in Grok's output — no concluding payoff given]."

### How the three differ

| | A VRP harvest | B GEX fade | C sweep follow |
|---|---|---|---|
| Edge | IV > expected RV | dealer hedge flow | inferred informed demand |
| Direction | none (Δ-hedged) | fade toward magnet | with the sweep |
| Main Greek | short vega / short γ | spot vs walls | equity delta |
| Death | jump + vol spike | fade in negative GEX | hedge flow / fake sweep |
| Data | IV surface + HAR RV | OI + Γ by strike | time & sales + side |

### Sources (methods, not performance claims)
- HAR / RV forecast: Corsi, "A Simple Approximate Long-Memory Model of Realized Volatility," JFEC 2009; HAR-IV extensions in practitioner vol work.
- VRP as IV − subsequent RV; short delta-hedged index straddles as the classic harvest; crash-conditio[n — truncated in page extraction]…
- GEX regime, call/put walls, flip, fade-only in positive gamma.
- Sweeps vs blocks; ask-side, vol/OI, premium filters.
- "Caveats: GEX sign is an assumption about who is long the options. UOA is not 'smart money' — it is often hedg[ed — truncated in page extraction]…"

---

## Q-TB5-2 — infra + local build + buy vs build (verbatim)

"This is a **solo-desk / research-prod** stack on one 128 GB M5 Max, not a colocated OPRA plant. Full-tick OPRA is several TB/day and is the wrong feed for this machine. You want **snapshot + trades**, not the SIP firehose."

### 0. What "500 underlyings, full chain" actually is

| Slice | Contracts (order of magnitude) |
|---|---|
| All listed US options | ~1.4–1.6M symbols |
| 500 liquid names, all listed expiries | ~200k–400k contracts |
| Same 500, front 4 expiries + weeklies on SPY/QQQ/IWM/SPX (what you actually need) | ~40k–80k |

"Intraday GEX / IV surface / straddle-implied move does **not** need every 2-year LEAP on a $8 name. Cap DTE (example: ≤ 60 for GEX, ≤ 45 for VRP, all weeklies on the 4 index products). That single filter is what makes the Mac viable."

"OI is not on OPRA. OPRA is NBBO + last sale. Open interest is OCC (official EOD) plus vendor 'intraday OI' estimates. GEX that updates every minute on 'live OI' is marketing; serious GEX is **EOD OI × live Γ**."

### 1. Data: OPRA full-chain vs cheaper paths

**License stack (pass-through, 2026)**

| Use | Typical fee | Notes |
|---|---|---|
| OPRA non-pro display | $1.25 / user / mo | Personal trading only |
| OPRA professional display | $31.50 / device / mo | Business use, FINRA/SEC affiliation, etc. |
| OPRA non-display (algo, risk, automated Greeks) | ~$2,000 / category / mo | This is the landmine. A scanner that computes GEX/UOA in code is non-display if you are commercial. |
| OPRA redistributor | $1,500 / mo (+ $650 query-only) | Only if you ship data to others |
| Indirect access (some vendors) | $600 / mo | Extra in some paths |

"If this is **your personal book on a Mac**, most retail vendors (ThetaData, IBKR) put you on non-pro or pro **display**. The moment you run unattended production signals for a firm, assume **non-display $2k**. Do not 'forget' that line."

**Practical feeds for this desk**

| Path | Sticker | Latency | Full chain 500 names | Trades for UOA | OI | Good for |
|---|---|---|---|---|---|---|
| ThetaData Standard/Pro | $80–$160/mo + OPRA entitlement | seconds–low seconds snapshots; ticks on Pro | Yes | Yes (Pro streams trades) | Vendor Greeks + OI fields | Best self-build raw input |
| Databento OPRA Standard-class | ~$199/mo product + OPRA license (personal $1.25; commercial $2k firm + users) | Real-time possible | Yes, but do not subscribe CMBP-1 ALL | Excellent trades | Definitions + stats; OI still OCC | Serious tape; overkill for Mac unless you filter hard |
| IBKR OPRA L1 | Non-pro ~$1.50; pro ~$32.75 | Snapshot / paced | Chain snapshots via API; not a research warehouse | Prints, not a flow scanner | EOD-ish | Cheap live NBBO while you trade |
| Cboe / OPRA 15-min delayed | Often $0–$40 retail delayed | 15 min | Yes | Delayed prints | EOD OI | Research, overnight HAR, not UOA follow |
| ORATS Live / Intraday | $299–$599/mo | Minutes | Chains + IV monies | Not a sweep tape | Yes | Surfaces already cooked |
| Unusual Whales / Cheddar / SpotGamma | $50–$299/mo UI; UW API from ~$625+/mo commercial | Live-ish | Pre-aggregated | Yes (their classification) | Their GEX | Buy analytics, don't own tape |

**Which strategies die without full-chain OI**

| Strategy | Dies without… | Survives on delayed / partial |
|---|---|---|
| (B) GEX pin / walls / flip | Strike-level OI on the whole relevant chain (at least all strikes near spot × front expiries). A 50-delta strip is not a wall map. | EOD OCC OI + live spot/IV is enough for daily walls. Intraday OI updates are nice-to-have, not the physics. 15-min delayed quotes are OK for walls if you only fade on 30–90 min horizons. |
| (A) VRP / HAR vs IV | ATM (or 50Δ) IV on the tenor you harvest — not the full million-line chain. | Delayed IV is fine for a daily/overnight harvest. Intraday VRP add-on needs live ATM IV, still not full chain. |
| Straddle-implied move | One expiry ATM call+put. | Delayed is fine pre-open; live needed only if you trade the open. |
| (C) UOA / sweep follow | Live (or < few second) trades + bid/ask side + multi-exchange routing. Delayed OPRA kills this. Full-chain quotes are secondary; you need the print tape, not every quote. OI is only for vol/OI opening test (can be prior-day OI). | |
| Dealer-positioning intraday HIRO-style | Live trades × delta | Delayed = dead |

"Short version:
- Full-chain OI **is mandatory for GEX**. It does **not** have to be real-time.
- Full-chain **live quotes** are mandatory only if you reprice the whole surface every minute.
- **UOA dies on Cboe delayed.** That is the one strategy that forces a live tape.
- **VRP + implied move** can live on delayed + EOD."

### 2. Compute on M5 Max (Polars / NumPy)

**Greeks for one snapshot**
"Keep DTE-capped book ≈ **60k contracts**. Vectorized BSM (IV via Newton / Halley, 4–8 iters):
- 60k IVs + Δ Γ Θ ν ρ in **~20–80 ms** on M5 Max if you stay in NumPy/Polars + Numba, mid price, no per-row Python.
- 400k contracts (uncapped): **~0.2–0.8 s**. Still fine at 1-minute cadence.
- Do **not** use scipy.optimize per contract.
- GEX for name i: GEX_k = Γ_k · OI_k · S² · 0.01 · 100 · dealer_sign. Aggregation is a Polars group_by(strike, expiry).sum() — milliseconds.
- UOA: consume **trades only** (~millions/day all-names; for 500 names, tens of k–low hundreds of k prints). Classify sweep if multi-exchange prints same strike/expiry within ~100–300 ms and aggressive vs NBBO. That is a streaming join, not a Greek problem.
- Straddle-implied move: move ≈ (C_ATM + P_ATM)/S or S × IV × √T [the √ radical was dropped by page extraction; the standard form is S × IV × √T]. Cheap."

**Cadence that fits the metal**

| Job | Cadence | CPU |
|---|---|---|
| Trade tape / UOA | continuous | 1–2 cores |
| Chain snapshot + IV/Greeks + GEX + surfaces | 30–60 s | burst < 1 s |
| HAR-RV (underlyings only) | 1–5 min | noise |
| Persist parquet | each snapshot | disk |

"You will not saturate a 16-core M5 Max. RAM and **feed discipline** are the constraints, not FLOPs."

**Snapshot storage / day**
Per contract snapshot row (compressed parquet, well typed): ~40–80 bytes.

| | Rows/day | Parquet / day | / month |
|---|---|---|---|
| 60k contracts × 1-min × 390 min | ~23M | ~1.2–2.0 GB | ~30–50 GB |
| 60k × 5-min | ~4.7M | ~250–400 MB | ~8–12 GB |
| Trades 500 names | highly variable | 0.3–1.5 GB | |
| Full OPRA CMBP-1 all names | — | terabytes | do not store on this Mac |

"Keep 20 trading days hot on SSD; ship older to cheap disk or object storage."

### 3. RAM / disk on 128 GB M5 Max

| Pool | Budget |
|---|---|
| OS + browser + IDE | 12–20 GB |
| Live 60k chain + Greeks (float64-ish) | 0.5–2 GB |
| 500 underlyings bars + HAR | < 0.5 GB |
| Trade ring buffer (session) | 1–3 GB |
| Polars peak during snapshot join | 8–16 GB |
| Safety | leave 40+ GB free so the kernel does not jetison your tape |

"128 GB is comfortable for the capped book. It is **not** comfortable if you materialize all-name 1-second NBBO."
"Disk: **2 TB SSD** is the right default (OS + 3–6 months of 1-min 500-name snapshots + trades). Full-tick OPRA does not belong here."
"Apple Silicon notes: Polars + NumPy are fine. Avoid GPU fantasies; options BSM is not a GPU problem at 60k rows. Unified memory helps the snapshot join."

### 4. Engineering hours (one strong engineer who already knows options)

| Block | Hours | What you actually ship |
|---|---|---|
| Feed client + reconnect + symbol universe + OCC OI ingest | 20–30 | Don't underestimate symbology and expiries |
| Snapshot scheduler + parquet lake | 10–15 | |
| Vectorized IV + Greeks + surfaces | 15–25 | IV failures, American vs European, dividends |
| GEX + walls + flip + pin map | 10–15 | Sign convention tests vs a vendor day |
| UOA classifier (sweep/block/side/vol-OI) | 20–35 | This is the fiddly one |
| VRP/HAR + straddle move + risk gates | 10–15 | |
| UI / alerts (terminal or Streamlit) | 15–25 | |
| Paper replay + reconciliation vs vendor | 20–30 | Where the hours hide |
| Total v1 that can trade-research | ~120–190 h | ~4–6 focused weeks |
| Harden to unattended prod (ops, calendars, corp actions) | +80–150 h | |

"If you have not written an options symbology layer before, add 40 hours."

### 5. Money: three realistic stacks

"Figures are **indicative 2026 list**; vendors change tiers. Exchange fees extra when you are professional / non-display."

**Stack S — Research + VRP + daily GEX (no live UOA)**

| Item | Monthly |
|---|---|
| ThetaData Value/Standard or delayed chain | $40–$80 |
| OCC EOD OI (often bundled) | $0–$20 |
| IBKR delayed/live for execution | $0–$35 |
| Total data | ~$50–$120 |
| Eng hours amortized (150 h × $150) / 24 mo | ~$940 |
| All-in year 1 | data ~$1k + labor ~$22k |

"Strategies alive: **A (daily), B (EOD walls, slow fade).** C dead."

**Stack T — Intraday self-build on the Mac (recommended if you build)**

| Item | Monthly |
|---|---|
| ThetaData Pro (trades + chain snapshots) | $160 |
| OPRA pro display if classified pro | $32 |
| Equities L1 | $0–$15 |
| Optional UW or Cheddar UI as truth tape | $50–$99 |
| Data | ~$210–$300 (personal/pro display) |
| If commercial non-display | +$2,000 |
| Storage already on the Mac | $0 |

"Year-1 cash: **~$3k data** (personal) or **~$27k** (non-display) + 150–250 eng hours. Strategies alive: A, B (EOD OI + live Γ), C (your classifier, worse than UW on day 1)."

**Stack U — Buy analytics, don't own the tape**

| Item | Monthly |
|---|---|
| SpotGamma mid/Alpha | $99–$299 |
| Unusual Whales Max + API | $120 UI; API $625+ if you code |
| ORATS live surface | $299–$599 |
| Typical combo people actually run | $250–$900 without writing a feed |

"No Mac cluster, no OPRA lawyer. You **cannot** change GEX sign convention, sweep definition, or harvest a custom VRP tenor without begging for an API."

**Buy vs build verdict**
"Buy the tape-adjacent analytics; build only the signal that is your edge."

| If your edge is… | Verdict |
|---|---|
| Watching GEX walls like SpotGamma | Buy SpotGamma ($99–$299). Reimplementing dealer-sign GEX to match them is 40 hours of arguing with OI. |
| Sweep-follow | Buy Unusual Whales or Cheddar for 90 days. Build your own classifier only after you can measure lift vs their labels. UW API for automation is the expensive part. |
| VRP vs HAR, vol targeting, your hedge policy | Build. Vendors do not sell your HAR gate. Data: ThetaData Standard/Pro + EOD OI. This is the only strategy that clearly pays for self-Greeks. |
| All three on one Mac, personal book | Hybrid: ThetaData Pro ($160) + UW Basic/Pro ($50–$75) + optional SpotGamma one month to calibrate walls. Skip Databento OPRA until you can prove you need sub-second NBBO. |
| Firm / non-display / multi-user | Budget $2k–$5k/mo data before a line of Python. Self-build still wins long-run only if the book is large enough to care about custom GEX. |

"Do not buy Databento full OPRA for this Mac. You will pay license + drown in CMBP-1 and still have to compute OI-GEX yourself. Databento is the right buy when you colocate or backtest years of prints, not when you snapshot 500 names on Apple Silicon."

"Hardware is not the cost. The 128 GB M5 Max is already the right box. The cost is (i) **OPRA classification,** (ii) 4–8 weeks of symbology/IV/OI hygiene, (iii) **UOA labeling quality.** Delayed Cboe is a valid $0–$80 research feed for A and overnight B. It is a **hard no** for C."

"**One-page recommended bill (personal, Austin desk, 500 names)**
- ThetaData Pro — $160/mo
- IBKR OPRA + equity for execution — ~$2–35/mo
- Unusual Whales Retail Pro (tape sanity + flow you didn't misclassify) — ~$75/mo
- 2 TB disk you already have
- ~150 hours to land VRP + GEX(EOD OI) + a crude sweep follower
- Revisit SpotGamma only if your wall map disagrees with price for two weeks

Year-1 incremental cash **~$3k** plus your time. That is the honest build. Adding commercial non-display or a 'real' OPRA plant jumps an order of magnitude and is not what this machine is for."

---

## Q-TB5-3 — success ratios, after-cost efficacy, failure modes (verbatim)

"After-cost honesty first: every 'Sharpe' below is a **sample statistic on a left-skewed payoff**. Sharpe overstates the trade. Use Calmar / expected shortfall. Spreads in §5 are not optional."

### 1. Short variance-risk-premium

**What is documented**
"Index IV exceeds subsequent realized vol on average. Carr–Wu and related work treat that gap as a **variance risk premium**: compensation for being short realized variance (and jumps), not a free lunch."

"Canonical implementations:
- delta-hedged ATM index straddles / variance-swap-like books.
- Collateralized **put-write** (Cboe PUT / WPUT): equity-like compound return, lower vol than SPX, still a short-vol left tail.
- Bondarenko (through 2018) on Cboe PUT vs SPX (long sample from 1986-class start): PUT Sharpe **0.65** [vs comparator label dropped by page extraction] **0.49**; PUT max DD **−32.7%** [vs comparator label dropped] **−50.9%** (2006–2018 window for the DD comparison with WPUT). WPUT max DD **−24.2%**. Those are **index put-writes**, not levered short straddles.
- 1-month ATM index straddles in Dew-Becker / Giglio-style samples: Sharpe on [the short side — inline word dropped] straddles around [value dropped by extraction] on S&P 500 at the short end — i.e. the [short — inline word dropped] side prints a high raw Sharpe in calm windows and then gives it back in crashes. Confidence bands ar[e wide — truncated in page extraction].
- A 2026 SSRN characterization is the right caveat: VRP is large and usually positive, but it is a **downside / crash-conditional** premium. Calm-year Sharpe can look like 6; the left tail is not diversifiable by 'vol targeting' alone."

**Horizon caveat**
"Zhou's review: VRP's **return-forecasting** power for equities/bonds/FX/credit peaks at a **few months** and dies at long horizons. That is predictability of **other** assets from the VRP, not a claim that a 5-year short-straddle Sharpe stays constant."
"Term-structure work (Aït-Sahalia–Karaman–Mancini): short-dated variance premia load hardest on **jump / crash fear**. Selling 1-week / 1-month variance is a different risk than selling 1-year variance."
"After cost: academic straddles often use mids. Half-spread + daily hedge friction on SPX ATM is small in **vol points** but large versus a 2–4 vol-point average VRP once you trade weeklies and skip event days. PUT/WPUT [are — inline word dropped] fully collateralized and only short one tail."

**Blow-up regimes (these are not the same product)**

| Episode | What broke | Documented damage |
|---|---|---|
| 5 Feb 2018 "Volmageddon" | Inverse VIX ETPs (XIV, SVXY), not cash-secured put-write | VIX +116% intraday (17 → ~37). XIV indicative NAV ~−90% to −96%; product terminated. Combined XIV+SVXY AUM ~$3–3.6bn → ~$135–150m. SVXY survived after a similar one-day wipe. |
| Feb–Mar 2020 | Short variance / short gamma into a jump | Realized variance exploded through implied. Levered short-vol and unhedged short straddles took the [hit — truncated in page extraction] |
| 2008 | Same mechanism, longer | Inverse VIX-style path: Sepp notes a ~−92% drawdown analog on short-VIX ETN path in the GFC, similar magnitude to XIV's one-day −96%. |

"Do not conflate: **daily-rebalanced short VIX futures** [carry — inline verb dropped] vol-of-vol + convexity + forced buy-in. **cash-secured short 1m ATM put** [is a different risk — clause dropped]. Delta-hedged short straddle = **local variance swap**. XIV dying **does not** prove PUT has a −90% day. It prove[s] that **leverage + short convexity + forced rebalance** is how short-vol actually kills you."
"Honest after-cost prior for a Mac-desk short ATM SPX straddle, daily hedge, no leverage: **modest positive expected P&L in vol points in non-crisis years; one 2018- or 2020-sized week can era[se years — truncated] of premia; Sharpe from a 2012–2017 window is not a capacity number.**"

### 2. GEX / pinning — effect sizes that exist in papers

"Single-stock expiration clustering (the cleanest result)
Ni–Pearson–Poteshman (JFE 2005), 1996–2002 optionable names: prices **cluster at strikes on expiration**. Lower bound: expiration-day returns of optionable stocks are altered by **≥ 16.5 bp** on average; [% of — inline fragment dropped] of optionable names affected that day; aggregate cap shift **~$9bn per expiration**. Mechanism: MM hedge rebalancing **and** some proprietary-desk stock trading. Non-optionable names do not cluster."

"That is [tens of bp — inline fragment dropped] of stock, not a 2% pin you can fade for free. After stock spread + borrow it is a **small, concentrated, expiration-Friday** [edge — inline word dropped]."

"Index futures pinning (older sample)
Golez–Jackwerth (JFE 2012): S&P 500 **futures pulled toward ATM** on serial futures-option expirations (pinning) and **pushed away** from the carry-adjusted ATM into SPX-option expiration (anti-cross-pinning). Notional shift **≥ $115m per expiration day**. Drivers: MM delta decay (charm) plus customer exercise / unwind — not a max-pain mysticism."

"Modern index caveat (needed for 0DTE)
Elms (SSRN 2026), SPY/ES 2016–2025, 1-minute, 2,294 days: **no pinning** in the post-weekly/0DTE sample. Highest-ATM-OI days show **~16% wider ranges**, consistent with **amplification** (short dealer gamma) not magnets. The 2005–2012 pin literature is not a 2026 0DTE playbook."

"After-cost read:
- Fade a **single-name** monthly pin: documented, small (tens of bp), crowded on the close.
- SPX 0DTE 'call wall' as if NPP 2005 still holds: **not supported** by the 2016–2025 test. Positive-GEX **compression** is a regime statement, not a 50 bp edge after ES ticks."

### 3. Unusual options activity → equity direction

"Gold-standard signed flow (not a Twitter sweep scanner)
**Pan–Poteshman (RFS 2006):** **buyer-initiated volume to open** new puts vs calls. Low put/call openers beat high put/call by **>40 bp next day** [and] **>1% over the next week** (1990–2001, proprietary Cboe open-buy data). Public volume does [not — inline word dropped] contain the same signal — the edge was in **non-public** 'open buy' classification. Predictability fades after about a week."
"That dataset is exactly what retail 'UOA' products try to approximate with Lee–Ready + vol/OI. They [can't match it — sentence truncated in page extraction]."

"Public UOA, recent sample
**Journal of Portfolio Management** (2026): OptionMetrics 2013–2023, strict volume/OI filters. Large prints **in general are not predictive**. Filtered UOA — especially **OTM, short-dated calls** — has significant abnormal equity returns. Puts weaker / sometimes wrong-way. **Profitability declined after 2020**: faster same-day reaction, less drift. Crowding."

"Related public-signal literature (not 'sweeps,' but same economic object):
- Cremers–Weinbaum IV spread: long-short **~64–66 bp / month** (pre-cost). Much of IV-spread / skew predictability shrinks if you drop **high stock-borrow-fee** names — part of the 'options predict stocks' zoo is **hard-to-borrow**, not informed flow.
- Ge et al. / OTM call volume: directionally consistent with PP 2006."

"Data-quality caveats that kill naive scanners
1. **Side:** sweep-at-ask ≠ new long. Multi-leg, delta-neutral packages, and dealer hedges print as 'calls bought'.
2. **Open vs close:** vol > OI is a noisy proxy; PP needed actual open-buy.
3. **Index vs single name:** SPX/SPY flow is hedges. Single-name OTM calls are where the papers find drift.
4. [Timing — list label dropped by extraction]: same-day gap-up is the residual; overnight follow is thinner.
5. **Costs:** you cannot buy the swept option at the pre-sweep mid. Equity follow still pays stock spread + gap ri[sk — truncated].
After-cost prior: **cross-sectional** daily sort on true open-buy put/call was a high-Sharpe academic strategy in 1990–2001. A 2026 '$250k [sweep — inline word dropped]…' [is a] degraded, crowded cousin. Budget **half or less** of the paper's 40 bp, then subtract the option or stock spread in §5. Many days the spread [eats — inline verb dropped] the 40 bp."

### 4. Dispersion (short index vol / long single-stock vol)

"Documented premium
**Driessen–Maenhout–Vilkov,** **Journal of Finance** 2009: correlation risk is priced. Implied correlation [exceeds — inline verb dropped] realized (~80% of months in their S&P 100 1996–2003 window). A frictionless dispersion book earns a **high alpha**. Follow-on IC vs RC: S&P 500 implied corr **~39.5%** vs realized **~32.5%** (DJ30: 46% vs 35.5%) — a large negative correlation risk premium. Index VRP is partly **this** correlation premium, not only single-name variance. Practitioner translation: **~2–3% per year** on a vega-neutral book in the classic sample."

"The sentence that matters for a cost model
Same paper: the premium **cannot be exploited with realistic trading frictions** — limits-to-arbitrage interpretation of why the price of correlation risk stays high."

"OptionMetrics-style timed IC–RC overlay (much later sample): passive 1m/3m vanilla dispersion Sharpe **0.14–0.60**; an IC–RC > 5% gate lifts Sharpe to **~0.93** and cuts max DD from **−7.6%/−10.5%** [to] **−5.3%** implementation — still a **low-vol, low-return** overlay, not XIV. Treat as vendor backtest, not JFE."

"Correlation-break risk
The short-index / long-stock book **loses when pairwise correlation jumps to 1** (2008, 2020, 2011, 2015–16 China, 2018Q4). That is the same week SPX puts explode and single-stock I[V spikes — truncated]… **crisis correlation**, which is why DMV find a premium [and] why frictions + crash weeks eat it."
"After-cost: 50–100 single-name option legs vs 1–2 SPX legs. Single-name ATM effective spreads (next section) can [be — inline word dropped] **1–3% of premium per turn**. A 2–3% **annual** correlation premium does not survive sloppy execution. Capacity is real but operationally ugly."

### 5. Options-spread reality check (put these in every model)

| Market | What papers / microstructure measure | Number to use |
|---|---|---|
| SPX 2014 (Ranaldo–Somogyi-type / index-option impact paper) | Effective spread | $0.59 or 1.69% of option value (all options). ATM effective ~1.59%; OTM effective ~2.65%; quoted half-spread much wider (3.27% / 6.33%) |
| Equity options (Muravyev–Pearson 2020, cited there) | Effective spread / option value | ~2.2% |
| Retail account tape (Barardehi–Bogousslavsky–Muravyev 2025) | Effective spread, signed | Options 1.07% vs stocks 0.07%. Quoted/conventional option effective 2.59%; retail limit orders cut realized cost ~60% |
| Liquid ETF ATM (SPY) | Quoted | 1–3 cents on a multi-dollar option — tight in dollars, still tens of bp of premium. |
| Single-name OTM / 5-Δ wings | Quoted | 6c on a 45c option ≈ 13% round-trip is a realistic iron-condor wing. |

"Rules for the three strategies
- (A) Short ATM SPX/SPY straddle: **~1.5–2% of premium** round-trip on the options **plus** futures/stock hedge costs. Do not use 1-tick fantasy on mid. Hedge costs dominate if you band-hedge [frequently — inline word dropped].
- (B) GEX fade in the underlying: stock/ES spread is cheap (**sub-bp to a few bp** […] surface [fragment] you used to **compute** GEX does not need to be traded. Cost is not why B fails; **regime error** [is — inline word dropped]).
- (C) Sweep follow in equity: stock effective **~7 bp** retail (table above). If you clone the option, pay **~1–3% of premium** and the sweep's own impact.
- Dispersion: **price** **every single-name leg** at 2% effective, not mid. That one line is why DMV say frictions kill the textbook alpha."

"**After-cost scoreboard (personal, not a product pitch)**

| Book | Paper / index edge (mid, old sample) | After realistic spreads + one crash decade | What actually dies |
|---|---|---|---|
| Short VRP, collateralized put-write | PUT Sharpe ~0.65, DD ~−33% | Still the most honest 'harvest'; DD is equity-like, not XIV-like | Selling levered variance or VIX ETPs |
| Short ATM straddle, Δ-hedged | High calm-sample Sharpe; long-straddle SR ~−0.9 | Edge is a few vol points minus 2% premium friction minus jump weeks | 2018/2020 un-gated |
| GEX / pin fade | 16.5 bp stock clustering (1996–2002); $115m futures shift (pre-2010) | Tiny vs costs if you trade options; futures fade possible on serial expiry in the old regime | Treating 0DTE walls as NPP pins |
| UOA → stock | 40 bp / 1% week (open-buy, 1990–2001) | Crowded after 2020; half the print is classification error | Delayed tape; index hedges |
| Dispersion | IC−RC ~7 corr-points; 2–3%/yr frictionless | DMV: frictions consume it; crash corr spike is the DD | 50-name wing spreads |"

"One sentence to put in the code comment: **mid-quote VRP and mid-quote dispersion Sharpes are not strategy Sharpes; XIV −96% and PUT −33% are t[he difference — truncated in page extraction].**"

---

## QC notes (orchestrator)

1. Page-extraction artifacts: several bolded/inline words were dropped by the accessibility text layer and are marked with `[brackets]`; a few mid-sentence truncations are marked similarly. The √ radical in the straddle-implied-move formula (S × IV × √T) was dropped by extraction and restored in a bracketed note.
2. Q1 example C: "Risk if stopped: 800 × 0.98 + fees ≈ −$800 (about 0.8R)" — 800×0.98 = 784; 1,440/784 ≈ 1.84R, so "0.8R" is likely Grok's typo for ~1.8R; preserved verbatim. The example's final sentence ("If you had chased the same 87.5 calls at $1.95 after the sweep, mid later $2.05, exit $2.05 ask-side") ends mid-thought with no concluding payoff.
3. Q1 example A arithmetic verified: hedge P&L +$38.40 ✓; friction $1.50 ✓; option P&L 490−428−2.60 = $59.40 ✓; total +$96.30 ✓. Example B: 200×4.10 = $820 ✓; stop 200×3.45+$fees ≈ −$710 ✓. Example C: premium 2,400×$1.85×100 = $444k ✓; vol/OI 2,400/410 ≈ 5.9 ✓; 800×1.80 = $1,440 ✓.
4. Q2: Stack S range "~$50–$120" vs components summing to $40–$135; Stack T "~$210–$300" vs $242–$306 including the optional UI line. Minor range mismatches. Labor amortization (150h×$150)/24 = $937.50 ≈ ~$940 ✓. "jetison" is Grok's typo for jettison — preserved.
5. Q3: several comparator labels dropped by extraction (Bondarenko PUT vs SPX Sharpe/DD labels; short-straddle Sharpe value and confidence-band wording).
6. Key sourced claims are research leads, not verified facts: Corsi 2009 (HAR-RV); Carr–Wu (variance risk premium); Bondarenko (PUT Sharpe 0.65, max DD −32.7%); Dew-Becker / Giglio (straddle samples); Aït-Sahalia–Karaman–Mancini (term structure); Ni–Pearson–Poteshman 2005 (≥16.5 bp expiration clustering); Golez–Jackwerth 2012 (≥$115m pinning shift); Elms 2026 (no pinning 2016–2025); Pan–Poteshman 2006 (>40 bp next day, >1% over a week); Cremers–Weinbaum (~64–66 bp/mo IV-spread); Driessen–Maenhout–Vilkov 2009 (IC−RC ~7 corr-points); Barardehi–Bogousslavsky–Muravyev 2025 (options effective spread 1.07% vs stocks 0.07%). Vendor prices: indicative — verify before budgeting.

---

## Source list (only papers actually used)

- Corsi, F. (2009), "A Simple Approximate Long-Memory Model of Realized Volatility," Journal of Financial Econometrics.
- Carr, P. and Wu, L. (2009), "Variance Risk Premiums," Review of Financial Studies.
- Bakshi, G. and Kapadia, N. (2003), "Delta-Hedged Gains and the Negative Market Volatility Risk Premium."
- Bondarenko, O. (2014/2018 update), "Why Are Put Options So Expensive?" (Cboe PUT Sharpe/DD figures).
- Dew-Becker, I. et al., variance-straddle samples.
- Giglio, S. et al., variance-premium samples.
- Zhou, G., VRP forecasting review.
- Aït-Sahalia, Y., Karaman, M. and Mancini, L. (2020), "The Term Structure of Variance Swaps."
- Ni, S., Pearson, N. and Poteshman, A. (2005), "Stock Price Clustering on Option Expiration Dates," JFE.
- Golez, B. and Jackwerth, J. (2012), "Pinning in the S&P 500 Futures," JFE.
- Elms, S. (2026), SPY/ES pinning 2016–2025.
- Pan, J. and Poteshman, A. (2006), "The Information in Option Volume for Future Stock Prices," RFS.
- Cremers, M. and Weinbaum, D. (2010), "Deviations from Put-Call Parity and Stock Return Predictability."
- Driessen, J., Maenhout, P. and Vilkov, G. (2009), "The Price of Correlation Risk," Journal of Finance.
- Barardehi, Y., Bogousslavsky, V. and Muravyev, D. (2025), retail options spreads.
- Everything not attributed to one of the above — thresholds, cost figures, worked-example values — is illustrative.
