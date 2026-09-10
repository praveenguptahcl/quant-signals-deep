# RB3 — Grok answers (regimes R021–R030) — VERBATIM

- Batch: RB3 — Liquidity/microstructure/funding/positioning/macro regimes (R021–R030)
- Bot: Grok (grok.com), signed in as Praveen Gupta (x.ai email login praveenguptahcl@gmail.com, Secure Vault saved credentials; no OTP was required)
- Date: Thu 2026-09-10 (America/Chicago)
- One new Grok chat: https://grok.com/c/80e95ca6-36ce-41d5-b940-814d1eed75a9 — the three questions were asked sequentially, each answer fully completed (streaming finished) before the next was sent. No rate-limit skip occurred.
- Fidelity notes from the browser run: captured via Grok's "Copy response" → paste → full-text read, preserving exact LaTeX with its \(...\) / \[...\] delimiters recovered from the message source. UI chrome (Copy/Save buttons, editor widget labels, citation pills, chat input placeholder) excluded — only Grok's authored content is reproduced. Nothing is a live-trading spec; research material for the document only. No external side effects (no purchases, posts, or account changes).
- Handling: research leads, not facts. Anything without a checkable source goes under `Unverified leads`, never in `Sources`. Nothing here is a live-trading spec; research for the document only.

Convention used throughout Grok's answer: Every number is tagged documented (with a real source) or illustrative-example. Formulas are exact; every symbol is defined with units. Public crypto liquidation prints are treated as reported_* lower bounds (exchange streams are rate-limited).

================================================================
Q-RB3-1 VERBATIM (Grok's full answer to Question 1)
================================================================

# Market-regime specification sheet

## R021–R030 (flow, squeeze, liquidation, rates, curve, surprises, credit, dollar, CB proximity)

**Convention used throughout.** Every number is tagged **documented** (with a real source) or **illustrative-example**. Formulas are exact; every symbol is defined with units. Public crypto liquidation prints are treated as **reported\_\*** lower bounds (exchange streams are rate-limited).

---

## R021 — Retail-flow dominance regime

### (1) Precise definition

A session (or trailing window) in which a **disproportionate share of executed trades and/or volume** is attributable to retail-sized or retail-routed flow (odd lots, wholesaler internalization, sub-penny TAQ prints), relative to that name's own history. The regime is a **modulator of signal efficacy**, not a signal: mean-reversion / microstructure alphas often strengthen when retail share is high; informed-flow signals weaken. Odd-lot *trade count* share is an imperfect proxy: MEMX documents that odd lots were **66% of industry trades** by Aug 2025 but "not a good way to gauge retail trading," because algos fragment and high prices mechanically create odd lots. O'Hara–Yao–Ye (JF 2014) document that in their sample the median odd-lot *trade* share was **24%**, with some names **≥60%**, and odd lots contributed **~35% of price discovery**.

### (2) Exact formulas and inputs

**Odd-lot trade share (count):**

\[
R^{\text{odd}}_t \;=\; \frac{N^{\text{odd}}_t}{N^{\text{all}}_t}
\]

- \(N^{\text{odd}}_t\): number of prints with size \(<100\) shares on day \(t\) (count, dimensionless).
- \(N^{\text{all}}_t\): all prints that day (count).
- Units of \(R^{\text{odd}}_t\): fraction in \([0,1]\).

**Odd-lot volume share (preferred complement):**

\[
V^{\text{odd}}_t \;=\; \frac{\sum_{i\in\text{odd}} q_{i,t}}{\sum_{i\in\text{all}} q_{i,t}}
\]

- \(q_{i,t}\): shares in print \(i\). Cboe: odd lots ~**54.8% of trades** vs a much smaller share of *volume* (about **10.7%** of share volume in the most liquid quintile).

**Retail-identified marketable imbalance (Boehmer-style, if TAQ subpenny available):**

\[
\text{MROIB}^{\text{vol}}_{i,t}
=\frac{\text{mrbvol}_{i,t}-\text{mrsvol}_{i,t}}{\text{mrbvol}_{i,t}+\text{mrsvol}_{i,t}}
\]

as in the Tsinghua/retail-flow tables (eqs. 1–4).

**Inputs:** SIP/TAQ prints (size, time, price); optional Rule 605 / wholesaler share (MEMX: retail wholesalers **34%** of volume, June 2025).

### (3) Parameter / threshold bands

| Band | \(R^{\text{odd}}\) (trade share) | Label |
| ------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Low / institutional-dominated | \(<0.35\) | illustrative-example (pre-2013 literature medians near 0.24) |
| Normal modern tape | \(0.45\)–\(0.60\) | documented: Cboe ~54.8% of trades (2021); MEMX path 57% (Jan 2023) → 66% (Aug 2025) |
| Elevated / candidate retail-dominance | \(>0.65\) *and* rising vs 20-day mean | illustrative-example (must be combined with volume share or wholesaler share; odd-lot count alone is contaminated) |

### (4) Worked example (synthetic 10-day odd-lot counts)

Odd-lot trade counts: \(120, 135, 140, 155, 148, 162, 170, 188, 195, 210\).

All-trade counts: \(280, 300, 310, 320, 305, 330, 340, 355, 360, 380\).

Day-10 share:

\[
R^{\text{odd}}_{10}=\frac{210}{380}=0.5526
\]

20-day (here 10-day) mean share \(=0.501\).

\(\Delta = 0.5526-0.501=+0.052\).

**Classification:** **Normal modern tape / not retail-dominance** (0.55 is inside the documented 0.45–0.60 industry band; no volume-share confirmation). Final label: **R021 = OFF (baseline microstructure, not retail-dominated).**

---

## R022 — Hard-to-borrow / short-squeeze regime

### (1) Precise definition

A name is in an HTB / squeeze-candidate state when **lendable supply is scarce relative to short demand**, so covering cannot occur at normal ADV without a material price impact. Best single predictor in the academic squeeze literature is **utilization** (shares on loan / shares available to lend): when utilization \(\ge 90\%\), an "all-lender squeeze" occurs about **once every 11 days** vs once every ~40 years when utilization \(\le 25\%\). Practitioner screens typically jointly require high days-to-cover, high borrow fee, and high short % of float.

### (2) Exact formulas

**Days-to-cover (short-interest ratio):**

\[
\text{DTC}_t \;=\; \frac{\text{SI}_t}{\text{ADV}_{t,W}}
\qquad\text{[trading days]}
\]

- \(\text{SI}_t\): shares sold short and not covered (shares). FINRA mid/end-month.
- \(\text{ADV}_{t,W}\): average daily volume over window \(W\) (usually 30 sessions), shares/day.
- \(t\): date.

\[
\text{Utilization} \;=\; \frac{\text{SharesOnLoan}}{\text{InventoryAvailableToLend}}
\qquad\text{[fraction; } \times 100 = \%\text{]}
\]

**Annualized borrow fee** \(f_t\) (decimal per year). Daily carry \(\approx f_t/360\).

**Illustrative composite scorecard** (weights *not* unique; Tapeboard publishes one commercial 0–100 mix of SI% float, fee, utilization, short-volume ratio):

\[
\text{Score}=100\cdot\left(0.35\,\tilde U+0.30\,\tilde f+0.20\,\widetilde{\text{DTC}}+0.15\,\widetilde{\text{SI\%}}\right)
\]

each \(\tilde x\) min–max normalized on the watchlist.

**Inputs:** FINRA short interest; exchange ADV; stock-loan file (IBKR / Markit / DataLend) for \(U, f\); float for SI%.

### (3) Threshold bands

| Metric | Band | Label |
| DTC | many desks watch \(>5\)–\(6\) days | documented practitioner rule of thumb |
| DTC | "very high" | documented vendor table |
| \(U\) | \(\ge 0.90\) squeeze-frequency jump | documented |
| \(f\) | GC / easy; \(10\)–\(25\%\) moderate HTB; \(25\)–\(40\%\) tight HTB; \(>40\%\) crowded | documented industry fee buckets |
| SI / float | \(>25\%\) "extremely shorted"; squeeze screens often pair float and DTC | documented screener rule |

### (4) Worked example (user numbers)

Given: \(f_t=12\%\) annualized, \(U=93\%\), \(\text{SI}_t/\text{ADV}=6\) days.

- Fee 12%: **moderately HTB** (10–25% band) — documented.
- Utilization: \(0.93\ge 0.90\) — documented high-frequency squeeze region.
- DTC 6: at the "start paying attention / high" practitioner cutoff.

**Classification:** **R022 = ON (squeeze-candidate / hard-to-borrow).** Short-covering flow can dominate residual signals; fade-the-break strategies have adverse selection.

---

## R023 — Liquidation-cascade regime (crypto)

### (1) Precise definition

A window in which **forced derivatives liquidations** run far above the name/market's own recent baseline and begin to **self-excite** (price move → margin breach → marketable close-out → further price move). Public aggregator 24h totals are **floors**: Binance-style streams cap at one event/second/symbol; published figures are often **3–5× too low**. On-chain fill reconstruction can *over*-count by fragmenting one economic episode into many fills (Hyperliquid factor ~**2.86**).

### (2) Exact formula

Let \(L^{\text{rep}}_t\) = reported\_* 24-hour notional liquidated (USD, lower bound).

\[
z^{\text{liq}}_t
=\frac{L^{\text{rep}}_t-\text{med}_{30}(L^{\text{rep}})}
{\text{MAD}_{30}(L^{\text{rep}})\cdot 1.4826}
\]

- \(\text{med}_{30}\): 30-day median of daily reported liquidations (USD).
- \(\text{MAD}_{30}\): median absolute deviation.
- 1.4826: consistency constant mapping MAD → \(\sigma\) under normality (standard robust-scale factor; methodological, not a market estimate).

Alternative (if a trailing SD is used):

\[
z^{\text{liq, alt}}_t
=\frac{L^{\text{rep}}_t-\mu_{30}(L^{\text{rep}})}{\sigma_{30}(L^{\text{rep}})}
\]

**Inputs:** Coinglass / exchange liquidation websocket (flag as reported\_*); OI, mark vs last, funding as context.

### (3) Threshold bands

| \(z^{\text{liq}}\) | State | Label |
| \(<2\) | ordinary flush | illustrative-example |
| \(2\)–\(5\) | elevated forced flow | illustrative-example |
| \(>5\) (and rising intra-day rate) | cascade-candidate | illustrative-example; Oct 2025 event showed liquidation rate jumping from $0.12B/h → $10.39B/h in the core 40 minutes (documented rate multiple, not a z cutoff) |

DeFi wave definition used in BIS work: a "wave" = liquidations clustered; 1,028 such waves in their sample. That is a *count* definition, not a USD z-score.

### (4) Worked example (user numbers)

\(L^{\text{rep}}_{24h}=\$480\text{M}\) vs 30-day median \(\$90\text{M}\).

Need a scale. **Illustrative-example** MAD: suppose the 30 reported daily prints cluster so \(\text{MAD}_{30}=\$25\text{M}\). Then

\[
z^{\text{liq}}=\frac{480-90}{25\times 1.4826}=\frac{390}{37.065}\approx 10.52.
\]

If instead one uses a raw ratio: \(480/90=5.33\)× median.

**Classification:** **R023 = ON (liquidation-cascade).** Treat reported\_* as a *lower bound*. Mean-reversion signals on perps are invalid until OI rebuilds and funding normalizes.

---

## R024 — Interest-rate level / direction regime

### (1) Precise definition

A discrete policy-path state implied by **30-day Fed Funds futures (ZQ / FF)** for the next FOMC: hike-priced, hold-priced, or cut-priced, optionally conditioned on the *level* of the target range. CME FedWatch converts the contract-implied average effective funds rate into a probability tree (25 bp steps, zero lower bound).

### (2) Exact calculation (CME binary building block)

For a meeting month, after isolating the meeting's contribution to the month-average:

\[
P(\text{hike of }+25\text{ bp})
=\frac{\text{EFFR}_{\text{implied, eom}}-\text{EFFR}_{\text{start}}}{0.25}
\]

- with \(P(\text{nohike})=1-P(\text{hike})\) in the one-step case; multi-meeting trees chain contracts. CME states the 25 bp increment and zero lower bound; effective date mechanics per meeting.
- Units: probability in \([0,1]\); rates in percent.
- \(\times 100\) = % (percent).

**Inputs:** CME 30-day FF futures strip; current FOMC target range; FOMC calendar.

### (3) Threshold bands

| Implied on next meeting | State | Label |
| \(P(\text{hold})\ge 0.80\) | anchored hold | documented practitioner readout of FedWatch |
| \(P(\text{hike})>0.60\) | hike-biased | illustrative-example cutoff for a 3-state machine |
| \(P(\text{cut})>0.60\) | cut-biased | illustrative-example |
| else | contested / two-sided | illustrative-example |

Level overlay (illustrative): funds target \(>5\%\) "restrictive-high"; \(<2\%\) "accommodative-low" — *not* a paper threshold.

### (4) Worked example

Fed funds futures imply **68% hike odds** for the next meeting (user).

\(0.68>0.60\) ⇒ **hike-biased**, hold/cut share \(0.32\).

**Classification:** **R024 = HIKE-BIASED (direction = tightening path).** Duration-sensitive and long-convexity signals should be conditioned down; USD and short-rate vol priced up.

---

## R025 — Yield-curve shape regime (2s10s)

### (1) Precise definition

State of the Treasury curve segment

\[
S^{2s10s}_t \;=\; y^{10\text{y}}_t - y^{2\text{y}}_t
\qquad\text{[decimal or bp]}
\]

plus the *joint* move in level and slope (bull/bear × steepener/flattener). FRED series **T10Y2Y**. A negative \(S\) is an inversion; the 2022–24 inversion reached about **−108 bp** (Jul 2023) and lasted **700** days — documented descriptive history, not a law.

### (2) Exact formulas

\[
S_t = y_{10,t}-y_{2,t},\quad S^{\text{bp}}_t=100\times(y_{10,t}-y_{2,t})\text{ if yields in percent, or }10^4\times\text{ if decimal.}
\]

Shape state (illustrative bands around zero):

- \(S<0\): **Inverted**.
- \(0\le S<50\) bp: **Flat** (illustrative).
- \(S\ge 50\) bp: **Normal/steep**.

Four dynamic regimes (standard market taxonomy, not a single paper's estimator): bull steepener = front rates ↓ faster than long; bear steepener = long rates ↑ faster; bull flattener = short rates ↓ faster; **bear flattener** = short rates ↑ faster than long.

**Inputs:** CMT 2y and 10y (H.15 / FRED DGS2, DGS10).

### (3) Threshold bands

| \(S\) (bp) | Shape | Label |
| \(<0\) | inverted | documented definition |
| \(0\)–\(250\) bp | typical positive range historically cited ~0 to +250 bp "normal" | documented descriptive range |
| \(\pm 50\) bp | flat (operational) | illustrative-example |

### (4) Worked example

\(y_{2y}=4.8\%\), \(y_{10y}=4.2\%\): \(S=4.2-4.8=-0.6\%=-60\) bp.

**Classification:** **R025 = INVERTED** (deep enough that "flat" does not apply). Curve-steepener carry is the structural bet; recession-lag timing is not.

---

## R026 — Inflation-surprise regime

### (1) Precise definition

A print-centered state in which the **CPI (or core CPI) release minus the pre-release consensus** is large versus that series' own trailing surprise volatility. Markets price the *gap*, not the level: a 3.5% print vs 3.5% consensus can be a non-event; the same 3.5% vs 3.2% is a shock.

### (2) Exact formula

\[
s_r = y_r - C_r
\]

\[
z^{\pi}_r=\frac{\text{CPI}^{\text{act}}_r-\text{CPI}^{\text{cons}}_r}{\sigma^{\pi}_{L}}
\]

- \(s_r\): surprise on release \(r\): YoY or MoM percent, *same convention* for actual and consensus.
- \(\sigma^{\pi}_{L}\): sample SD of \(s\) over trailing \(L\) (percent). User gives trailing \(\sigma\).
- \(r\): release index.

**Inputs:** BLS CPI; Bloomberg/Reuters survey median *before* 8:30 ET.

### (3) Threshold bands

| \(|z^{\pi}|\) | State | Label |
| \(<0.5\) | in-line | illustrative-example (maps to ~0.1 pp if \(\sigma=0.2\%\)) |
| \(0.5\)–\(1.5\) | moderate surprise | illustrative-example |
| \(>1.5\) | large surprise regime | illustrative-example |

Desk heuristics of 0.1 / 0.2 pp MoM core as fade vs trend-join thresholds exist in practitioner notes — *not* a journal cutoff.

### (4) Worked example

Actual 3.4%, consensus 3.1%, \(\sigma^{\pi}=0.2\%\):

\(s_r=3.4-3.1=0.3\) pp; \(z^{\pi}=0.3/0.2=1.5\).

**Classification:** **R026 = LARGE POSITIVE INFLATION SURPRISE** (at the 1.5 cutoff; \(z>0\), hawkish). Rate-sensitive longs and duration should be conditioned; USD typically bid on the print.

---

## R027 — Growth-surprise regime (economic surprise index)

### (1) Precise definition

A rolling score of whether **activity data have been beating or missing consensus**. The industry benchmark is the **Citigroup Economic Surprise Index (CESI)**: "weighted historical standard deviations of data surprises (actual releases vs Bloomberg survey median)" — Bloomberg description of Citi's definition. Sign convention: CESI \(>0\) ⇒ data on balance beating consensus.

### (2) Exact formula (public reconstruction)

Citi's exact weights and decay are proprietary. A faithful public clone is:

\[
\text{CESI}_t
=\sum_{k\in\mathcal{K}}
w_k\,
e^{-\lambda \Delta t_k}\,
\frac{x_{k}-c_{k}}{\sigma_k}
\]

- \(x_k, c_k\): actual and consensus for release \(k\) (native units).
- \(\sigma_k\): historical SD of that release's surprise (same units).
- \(w_k\): FX-impact weight (Citi; undocumented numerically here).
- \(\Delta t_k\): calendar days since release \(k\); \(\lambda\) sets memory (Citi uses a 3-month window).
- Units: CESI is quoted as an index number (often loosely labeled "percent" on chart services); treat as *dimensionless weighted z*.

Fed IFDP 1093 discusses the same "weighted historical SD + decay" construction.

**Inputs:** economic calendar (NFP, ISM, retail sales, claims, GDP…); Bloomberg medians; a weight scheme if cloning.

### (3) Threshold bands

| CESI (US) | State | Label |
| \(>0\) | net upside surprises | documented sign convention |
| \(|CESI|>50\) | large-surprise regime | illustrative-example (Yardeni charts routinely span about −160 to +300 historically; no official band) |
| crossing through 0 | regime flip | illustrative-example |

### (4) Worked example (3-release toy clone)

Releases still inside the decay window (illustrative equal weights \(w_k=1/3\), \(e^{-\lambda \Delta t}\approx 1\) for the snapshot):

| Release | \((x-c)/\sigma\) |
| NFP | \(+1.4\) |
| ISM mfg | \(+0.6\) |
| Retail sales | \(-0.2\) |

\(\text{CESI}_{\text{toy}}=(1.4+0.6-0.2)/3=0.60\). (This toy is *not* on Citi's published scale, which is a weighted running sum.)

If the live Citi US print were instead the MacroMicro reading **+18.5** (3 Sep 2026), sign is positive.

**Classification (toy):** **R027 = MILD UPSIDE GROWTH-SURPRISE.** Cyclical long-risk signals get a tailwind; if the official CESI is used, classify by *that* printed sign/level, not the toy.

---

## R028 — Credit-stress regime (HY OAS)

### (1) Precise definition

State of US high-yield credit risk priced by the **ICE BofA US High Yield Option-Adjusted Spread** (FRED **BAMLH0A0HYM2**): yield of the HY index over the Treasury curve after stripping embedded option value. Stress is a *level and speed* call: \(\text{OAS}_t\) plus \(\Delta_{20}\) (20-session change).

### (2) Exact formulas

\[
\Delta_{20}\text{OAS}_t = \text{OAS}_t - \text{OAS}_{t-20}
\qquad\text{[basis points]}
\]

\[
\text{speed}_t = \Delta_{20}\text{OAS}_t/20
\qquad\text{[bp/20 sessions]}
\]

Optional robust z on the change:

\[
z^{\text{OAS}}_t = \frac{\Delta_{20}\text{OAS}_t - \text{med}(\Delta_{20}\text{OAS})}{\text{MAD}(\Delta_{20}\text{OAS})\cdot 1.4826}
\]

**Inputs:** ICE BofA HY OAS daily (FRED).

### (3) Threshold bands (practitioner / descriptive — ranges differ by author)

| OAS level | Read-across | Label |
| \(<300\) bp | historically tight / complacency | documented across several 2026 desk notes |
| ~450–500 bp | long-run average neighborhood | documented (FRED-era averages cited ~450–500) |
| \(600\)–\(800\) bp | significant stress / recession-pricing zone | documented descriptive |
| \(>1000\) bp | crisis (GFC peak ~2182 bp; COVID ~1100) | documented event levels |
| \(\Delta_{20}>+50\) bp | fast-widening stress regardless of level | illustrative-example aligned with "pace matters more than level" |

### (4) Worked example

\(\text{OAS}_t=620\) bps, \(\Delta_{20}=+110\) bps.

- Level 620: **elevated / danger-adjacent** (above 600).
- Speed +110 bp in 20 days: **fast widening** (\(>+50\) illustrative line; would also clear any reasonable robust z).

**Classification:** **R028 = ON (credit-stress).** Equity residual and HY-carry signals should be risk-off conditioned; quality and liquidity premia typically outperform.

---

## R029 — Dollar regime (DXY)

### (1) Precise definition

Trend-and-location state of the ICE US Dollar Index: **50-day vs 200-day moving average** (golden/death cross taxonomy) plus where that configuration sits in its own multi-year distribution.

### (2) Exact formulas

Simple MAs:

\[
MA_{n,t}=\frac{1}{n}\sum_{i=0}^{n-1}P_{t-i}
\]

Spread:

\[
G_t = MA_{50,t}-MA_{200,t}
\qquad\text{[index points]}
\]

- \(G_t>0\): **bull-dollar**; \(G_t<0\): **bear-dollar**.

Location of \(G_t\) in a 5-year history:

\[
\pi_t = \frac{\text{rank}(G_t\text{ in trailing 5y})}{N}
\qquad\text{(empirical CDF / percentile)}
\]

**Inputs:** DXY daily close (ICE).

### (3) Threshold bands

| Condition | State | Label |
| \(G_t>0\) | 50d above 200d (uptrend / post-golden-cross) | documented TA definition |
| \(G_t<0\) | death-cross / downtrend | documented |
| \(\pi_t\ge 0.80\) | wide-and-strong dollar | illustrative-example (user's 80th-pct rule) |
| \(\pi_t\le 0.20\) | wide-and-weak dollar | illustrative-example |

### (4) Worked example

"DXY 50-day above 200-day at the **80th percentile** of its 5-year range." So \(G_t>0\), \(\pi_t=0.80\).

**Classification:** **R029 = STRONG-DOLLAR UPTREND.** EM FX, gold, and mega-cap growth betas that load negatively on DXY should be haircut; USD-cash and quality factors get a tailwind.

---

## R030 — Central-bank event proximity

### (1) Precise definition

A calendar state measuring how close cash/risk markets are to a **scheduled FOMC (or analogous G10 CB) announcement**, where (i) the pre-FOMC drift, (ii) volume dry-up, and (iii) post-announcement vol expansion are documented. Lucca–Moench (JF): equities drift up **+49 bp** in the 24 hours before scheduled FOMC, vs ~4 bp on a normal day. Neuhierl–Weber: directional drift visible out to **~25 days** when signed by the subsequent policy surprise. Zhu (BIS): volume *falls before*, *rises after*.

### (2) Exact formulas

Let \(T^*\) be announcement timestamp, \(t\) now.

\[
\tau = \frac{T^* - t}{\text{1 trading day}}
\qquad\text{[calendar or trading days; sign: }\tau>0\text{ is pre-event]}
\]

Window classification (operational, mixed documented windows + illustrative bins):

- \(\tau>25\): **far**.
- \(2<\tau\le 25\): **drift window** (Neuhierl–Weber ~25d signed-drift window).
- \(0.5<\tau\le 2\): **pre-announcement day** (close-to-close into 14:00 ET).
- \(-0.02<\tau\le 0.5\): **event / 30-min shock** window.
- \(\tau\le -0.02\): **post-digest**.

The 24h pre-window of Lucca–Moench is close-to-5 minutes before release. High-frequency policy shock: Kuttner / Bernanke–Kuttner / Gürkaynak–Sack–Swanson surprises from FF futures around the statement.

**Inputs:** FOMC calendar (unscheduled meetings handled separately); FF futures for the shock.

### (3) Threshold bands

| \(\tau\) | Regime slice | Label |
| 1 trading day pre | pre-FOMC puzzle window | documented 24h |
| 2–25 trading days pre | monetary-momentum window | documented |
| 30-minute statement window | identification window | documented high-frequency convention |
| 6-day VIX build | uncertainty build | documented search window in Hu–Pan–Wang lineage |

### (4) Worked example

Suppose today is 6 trading days before a scheduled FOMC (\(T^*\) = next Wednesday 14:00 ET). Then \(\tau = 6 \in (2, 25]\).

**Classification:** **R030 = DRIFT / PRE-FOMC PROXIMITY (not yet the 24h puzzle window).** Reduce initiation of short-gamma or event-blind mean-reversion; expected excess equity drift is signed only once FF-implied odds (R024) are attached. If instead \(\tau = 0.5\) day, upgrade to **PRE-ANNOUNCEMENT DAY**.

---

## Cross-regime use (for the chapter's methodology box)

These ten states are **conditioners**, not alpha. A minimal implementation is a binary or ternary flag per regime, then interact with the trading signal \(s\):

\[
s^{\text{cond}}_t = s_t\cdot \prod_{r\in\mathcal{R}}\bigl(1+\gamma_r(\mathbf{1}\{r\text{ ON}\}-p_r)\bigr)
\]

with \(\gamma_r\) estimated out-of-sample and \(p_r = \mathbb{E}[\mathbf{1}\{r\text{ ON}\}]\). Do not estimate \(\gamma_r\) on the same sample used to pick thresholds.

Data hygiene reminders already forced by the sources: odd-lot count ≠ retail; reported crypto liquidations are censored floors; CESI weights are proprietary; SI files lag; borrow fee is a snapshot not a market; 25 bp steps are the CME convention; FedWatch probabilities assume 25 bp steps and embed term premia.

================================================================
Q-RB3-2 VERBATIM (Grok's full answer to Question 2)
================================================================

# R021–R030 compute stack on one M5 Max / 128 GB machine

Hardware is not the constraint. **Data entitlements and causal vintage** are. Daily refresh of these ten flags is a small-data problem once you refuse to ingest full TAQ quotes.

All vendor prices below are **indicative** (list / published 2025–26 schedules or commonly quoted street ranges). They are not quotes.

## 1. Data feeds — exact products

| Regime | What you actually need | Exact product / series | Vintage / lag |
| --- | --- | --- | --- |
| R021 retail | Odd-lot trade flag + size; optional retail-ID | NYSE Daily TAQ – Trades (not Quotes). Size < 100 = odd lot. Optional: Boehmer–Jones–Zhang sub-penny off-exchange prints (same file, sale-condition + price grid). WRDS TAQ Daily (taqm_YYYY). Commercial list: Daily TAQ **$3,800/mo MRC** + 12 mo history included. Cheap proxy: tick-trade vendors (e.g. Polygon stocks, Databento EQUS, Strasmore) — SIP-complete, label as proxy. | T+1 file (~00:00 ET); WRDS lag ≈ 1 session. |
| R022 HTB / squeeze | SI, ADV, fee, utilization | FINRA Consolidated Short Interest (bi-monthly, ~T+8). ADV: SIP or CRSP/Yahoo/Polygon daily volume. Lending: **S&P Global / IHS Markit Securities Finance** (DataLend / "Buyside Instrument Feed", daily back to 2006: indicative fee, utilization). Street substitute: **IBKR Client Portal + TWS SLB** (fee, shortable qty) — **one-prime snapshot, not market-wide**. Fallback: **NYSE / Nasdaq Reg SHO Threshold List** (daily HTML/FTP). Cboe **US Equity Short Volume & Trades Report** **$750/mo internal**. | FINRA lagged to settlement date + T+8 publication; label available_ts = publish, not settlement. |
| R023 crypto liq. | 24h reported notional | CoinGlass API v4 /api/futures/liquidation/aggregated-history and …/exchange-list. Tag every field reported_\*. Hobbyist **~$29/mo** personal; Startup ~$299 first commercial tier. Cross-check: Binance/Bybit public liquidation streams (rate-limited). Optional on-chain: Hyperliquid. | Rate-limited to ~1 event/s/symbol; cross-check twice daily. |
| R024 rates path | FF futures + target | CME 30-Day Federal Funds futures (ZQ / SR3) via CME DataMine, Databento GLBX.MDP3, or IBKR. Target: FRED **DFEDTARL**, **DFEDTARU**. Effective: **DFF**. SOFR: **SOFRINDEX**. OIS level: no clean free FRED OIS; use **EFFR vs SOFR** or a paid USD OIS (LSEG/BBG). Probabilities: implement CME FedWatch tree yourself from ZQ; do not scrape the widget. | Futures T+0; target is a series level. |
| R025 2s10s | CMT 2y / 10y | FRED DGS2, DGS10 (H.15). Ready-made spread: T10Y2Y. | FRED H.15 published ~16:00–17:30 ET; T+0 after that. |
| R026 inflation surprise | Actual + pre-release consensus | Actual: BLS CPI-U NSA YoY / core — FRED CPIAUCSL is SA monthly index (wrong unit for a print surprise). Use **release-level** actual from BLS lockup time-series or a calendar vendor's actual. Consensus: Bloomberg **ECST**, LSEG, or a calendar API that stores **forecast as-of 08:29 ET**. | Freeze consensus at 08:30 ET; actuals at release. |
| R027 growth surprise | Multi-print surprises + weights | Same calendar vendor. Official Citi Economic Surprise Index is Bloomberg ticker family (e.g. CESIUSD Index) — **buy, don't clone** if you need the published number. A local weighted-z clone is fine if labeled CESI_clone. | 3-month decay window; sign must match official. |
| R028 credit | HY OAS | FRED BAMLH0A0HYM2 (ICE BofA US HY OAS, percent; ×100 = bp). Quality slices: BAMLH0A1HYBB, BAMLH0A2HYB, BAMLH0A3HYC. Pull via **ALFRED** if you need vintage. Note ICE has been shortening FRED history on some sister series. | FRED T+1 vs ICE close; note revision/lag. |
| R029 dollar | DXY level | ICE USDX / DXY is not a FRED series. FRED substitutes: DTWEXBGS (broad, goods+services), DTWEXM or DTWEXAFEGS. For true DXY: Yahoo DX-Y.NYB, IBKR DX, or ICE. | Daily; broad is T+1. |
| R030 CB proximity | calendars + clock | FOMC: federalreserve.gov calendar ICS + unscheduled-meeting flag. ECB/BOE/BOJ: official ICS. COT (if you want it): **Traders in Financial Futures**, weekly, published Friday for Tue close (**T+3**). | COT never enters a same-week Friday morning state. |

FRED IDs to wire (copy-paste): DGS2, DGS10, T10Y2Y, DFF, DFEDTARL, DFEDTARU, SOFR, SOFRINDEX, BAMLH0A0HYM2, DTWEXBGS, FEDFUNDS.

Use **ALFRED** (alfred.stlouisfed.org) not just FRED when a revision can change a past print.

Economic calendar + consensus (pick one):
- Institutional: Bloomberg ECST / BQL, LSEG Datastream + calendar (**indicative $1.5k–$2.5k/mo/seat** terminal; API extra).
- Research: Trading Economics API **indicative $89–$499/mo**.
- Lightweight: a calendar API that stores forecast frozen at T−1 (do not overwrite after the print).

## 2. Daily refresh time (Python + Polars, M5 Max)

Illustrative-example wall times on 128 GB unified, Polars + Arrow, after data is local:

| Job | Cadence | Wall clock |
| --- | --- | --- |
| FRED / ALFRED pull (~15 series) | 16:30 ET | < 5 s |
| DXY daily bar + 50/200 MA + 5y percentile | 16:30 ET | < 1 s |
| HY OAS Δ20 + bands | 16:30 ET | < 1 s |
| ZQ strip → FedWatch tree (next 3 meetings) | 16:15 + 18:00 ET | 1–3 s |
| Calendar surprises → R026/R027 | 08:31, 10:01 ET | < 1 s once print is in |
| CoinGlass 24h liq + 30d median/MAD | 00:05, 12:05 UTC | 2–10 s |
| FINRA SI merge + DTC (universe ~3k names) | twice monthly, day after file | 5–20 s |
| IBKR SLB snapshot (watchlist 500 names) | 09:35, 15:50 ET | 10–60 s (rate limits) |
| TAQ trades, one session, SIP-complete | T+1 ~00:00 ET file | minutes to tens of minutes if you scan all names; seconds if you pre-filter a 500-name panel and store only {date, ticker, n_odd, n_all, sh_odd, sh_vol} |
| Full TAQ quotes | do not | Daily TAQ quotes are the disk/CPU killer; R021 does not need them |

End-to-end daily refresh excluding raw TAQ ingest: ~1–3 minutes.

Including compact TAQ-trades reduction for a 500-name panel: ~10–30 minutes the first time you touch a new day file; subsequent days similar if you stream-aggregate.

M5 Max + 128 GB is overkill for the **indicators**. It is useful if you keep 2–3 years of reduced TAQ panels and a local Arrow lake.

## 3. RAM and disk budgets

| Store | Disk | RAM at runtime |
| --- | --- | --- |
| FRED/ALFRED + DXY + OAS + ZQ daily, 20y | < 200 MB | < 200 MB |
| Calendar + surprise history | < 100 MB | tiny |
| CoinGlass daily liq history | < 200 MB | tiny |
| FINRA SI + DTC panel, 10y × 4k names | ~200–500 MB parquet | < 1 GB |
| IBKR SLB daily snapshots, 500 names × 5y | < 100 MB | tiny |
| Reduced TAQ trades panel (500 names × 5y, daily aggregates only) | 5–20 GB | 2–8 GB peak |
| Raw Daily TAQ trades, one year, all names | hundreds of GB – low TB (WRDS taqm_2024 listed 7.71 TiB for that product year including quotes) | do not load |
| Working peak if you ever scan a raw trades file | stream; cap Polars at 16–32 GB | leave 32+ GB free for macOS + other agents |

Recommended disk envelope for this project: 50–100 GB SSD (reduced lake + raw last-5-sessions TAQ only). Do not land full quote tape.

## 4. Engineering hours (one person, correct causal pipeline)

| Workstream | Hours | Notes |
| --- | --- | --- |
| Lake layout, Parquet partitions, schema versions | 8–12 | asof_ts, observed_ts, vintage_id on every row |
| FRED/ALFRED + DXY + OAS + curve + SOFR | 6–10 | including holiday/NA handling |
| FedWatch tree from ZQ (test vs CME widget on 10 dates) | 12–20 | this is the fiddly one |
| Calendar vendor + 08:30 lock | 8–12 | freeze consensus; no overwrite |
| R026/R027 z and CESI_clone | 6–8 | |
| CoinGlass + reported_* + robust z | 4–6 | |
| FINRA SI ingest + DTC + lag tag | 8–12 | bi-monthly file quirks |
| IBKR SLB + Reg SHO fallback + low-confidence flag | 10–16 | |
| TAQ trades reducer → R021 (500-name panel) | 16–24 | if you buy Daily TAQ / WRDS |
| Verification suite (second estimator + tolerances) | 12–16 | |
| Orchestrator, calendars, fail-safes, Slack/email | 10–14 | |
| Paper-trail docs + unit fixtures | 6–8 | |
| Total | ~110–170 h | ~4–6 focused weeks, not a weekend |

If you skip SIP TAQ and use a tick-trade proxy + odd-lot heuristic, subtract ~20 h and accept a PROXY tag on R021.

## 5. Buy vs build (one-person research desk)

| Layer | Build | Buy | Indicative monthly | Verdict |
| --- | --- | --- | --- | --- |
| Macro official (FRED/ALFRED, BLS, Fed calendar) | Yes | — | $0 | Build |
| DXY | Yahoo/IBKR | ICE official | $0 vs ICE license | Build (label source) |
| HY OAS | FRED series | ICE direct | $0 | Build on FRED; know it's delayed vs ICE close |
| FF probabilities | Your tree | Bloomberg / CME FedWatch scrape | $0 vs terminal | Build the tree; spot-check the widget. Do not scrape as SoT |
| Calendar + consensus | Fragile scrape | Trading Economics / FXMacro / BBG | $25–$499 TE; $2k+ BBG seat | Buy a calendar with frozen forecast. Consensus is the hard part |
| CESI official | Cannot | Bloomberg CESIUSD | terminal | Buy if you cite Citi; else clone and label |
| Crypto liq | Exchange sockets | CoinGlass | $29–$299 | Buy CoinGlass Hobbyist/Startup; keep reported_* |
| Stock loan | IBKR only | Markit / DataLend / S3 Partners | IBKR $0 with account; Markit indicative $1k–$5k+/mo (not public list) | Build on IBKR + Reg SHO for a one-person book; buy Markit only if R022 is a product you sell |
| Short interest | FINRA file | Ortex / S3 | FINRA $0; Ortex indicative $200–$500+/mo | FINRA + lag tag; Ortex only if you need daily SI estimates |
| TAQ / odd lots | Reducer | NYSE Daily TAQ $3,800/mo or WRDS academic | $3,800 commercial | Do not buy Daily TAQ for a solo research doc. Use a $79–$249/mo tick warehouse (e.g. Strasmore-class) or Databento trades and mark R021 as PROXY. Revisit TAQ only if a paper requires SIP completeness |

**Desk verdict:** spend money on **(1) consensus calendar, (2) CoinGlass, (3) optional tick-trades**. Do not spend $3.8k/mo on Daily TAQ or a Bloomberg seat **just** for these ten flags. Total cash stack that is sufficient: **~$50–$400/mo**.

## Automated detection loop

### Agents and cadence

Treat each "agent" as a small process with a frozen input contract. One orchestrator (regime_orch) owns the board.

| Agent | Computes | Cadence (America/New_York) | Output |
| --- | --- | --- | --- |
| agent_fred | R024 level pieces, R025, R028, R029 FRED-dollar alt | 16:45 ET daily; retry 18:00 | parquet + vintage=FRED:{release_ts} |
| agent_dxy | R029 ICE DXY 50/200 + 5y pctl | 16:20 ET | |
| agent_zq | R024 hike/hold/cut tree | 16:15 and 18:00 ET; extra run 14:05 on FOMC day | |
| agent_calendar | ingest events; freeze forecast at 08:00 ET | 07:00 daily; poll 08:30:05–08:35 on CPI/NFP days | |
| agent_print | R026, R027 | first run ≥ official timestamp + 5 s; never before | flip allowed only if now >= release_ts |
| agent_liq | R023 | 00:10 and 12:10 UTC | reported_* |
| agent_si | R022 DTC / SI% | FINRA file days only (~1st/15th + lag) | asof=settlement_date, observed=file_pub_ts |
| agent_sleb | R022 fee + util | 09:35, 15:50 ET | source=IBKR |
| agent_regsho | fallback HTB list | 00:30 ET | |
| agent_taq | R021 | when T+1 trades file lands (~midnight–04:00) | daily aggregates only |
| agent_prox | R030 | every 15 min | tau trading days to next FOMC |
| agent_publish | regime board | only if verify PASS or FAIL-OPEN with flags | |

### Independent verification + agreement tolerance

| Regime | Estimator A | Estimator B | Tolerance |
| --- | --- | --- | --- |
| R021 | odd-lot trade share | odd-lot volume share + (if available) off-exchange sub-penny share | state must agree on {low, normal, elevated}; raw share within 5 pp |
| R022 | DTC from FINRA SI / 30d ADV | IBKR fee bucket + util; else Reg SHO membership | ON only if two of {DTC≥5, U≥0.90, f≥10%, Reg SHO}; if lending missing → LOW_CONFIDENCE never hard-ON |
| R023 | CoinGlass aggregated 24h | sum of Binance+Bybit public prints | ratio A/B in [0.3, 3.0] (censoring); z sign must match; else LOW_CONFIDENCE |
| R024 | your ZQ tree | CME FedWatch screenshot/API-of-record within 2 h | each bucket within 10 pp; direction (hike/hold/cut) must match |
| R025 | DGS10−DGS2 | T10Y2Y | ≤ 1 bp |
| R026 | Bloomberg/TE surprise | BLS actual − frozen consensus | exact match on actual; z within 0.05 |
| R027 | CESI_clone | official CESIUSD if entitled, else sign of 4-week surprise sum | sign must match; if no official, tag CLONE |
| R028 | BAMLH0A0HYM2 level+Δ20 | BAMLC0A0CM (IG OAS) direction | HY Δ20 sign vs IG Δ20; if opposite and |ΔHY|<20 bp → LOW_CONFIDENCE |
| R029 | DXY MA50−MA200 | DTWEXBGS same rule | trend sign should match; if diverge, flag DXY_VS_BROAD_DIVERGE (can happen) |
| R030 | Fed ICS | second copy of calendar (NY Fed / CME meeting date) | dates must be identical |

### Fail-safes

1. **No file, no flip.** If a feed is stale past SLA (FRED > 26 h, liq > 2 h, SLB > 1 session), hold last published state and flag.
2. **Release-day lock.** agent_print has a hard gate: if now < release_ts_et: raise LeakageError. Unit-test with a frozen clock.
3. **Consensus immutability.** forecast column is write-once. After 08:29:59 ET it is append-only. Revisions go to forecast_revised, not overwrite.
4. **T+1 / lagged vintage tags (mandatory columns):**
- observation_date — economic date the number refers to
- available_ts — first timestamp a causal agent could have seen it
- lag_reason ∈ {T0, T1_TAQ, FINRA_BI_MONTHLY, CFTC_WEEKLY, FRED_H15_4PM, ICE_CLOSE}
- FINRA SI used on date D must carry available_ts = file_publication, not the settlement date. COT never enters a same-week Friday morning state.
5. **Lending absent.** If agent_sleb fails: R022 = LOW_CONFIDENCE + Reg SHO boolean only. Log fallback=REG_SHO. Do not infer utilization from fee alone.
6. **TAQ late.** R021 stays PRIOR_SESSION until reducer finishes; do not use partial SIP.
7. **Kill switch.** If agent_verify fails two cycles, publish last good board with BOARD_FROZEN=1.
8. **All timestamps stored in UTC; gates evaluated in America/New_York with Fed holiday calendar.** DST tests included.

### Minimal publish record

```text
regime_id, state, score, confidence, observation_date, available_ts,
source, estimator_a, estimator_b, agreement, flags, published_ts
```

Example flags: REPORTED_LOWER_BOUND, IBKR_PRIME_ONLY, CESI_CLONE, PRE_PRINT_LOCKED, FINRA_LAG, REG_SHO_FALLBACK, PROXY, CLONE.

**Bottom line for this machine:** **buy a consensus calendar and CoinGlass; compute everything else in Polars off FRED + IBKR + a cheap tick-trade warehouse.**

================================================================
Q-RB3-3 VERBATIM (Grok's full answer to Question 3)
================================================================

# How R021–R030 change what works

Direction is stated as **improves / dies / flips sign**. Mechanisms are economic, not slogans. Evidence is tagged **documented** (named paper or well-known episode) or **illustrative**. Costs: if a study is pre-cost, it is labeled that way.

---

## R021 — Retail-flow dominance

**(1) Direction and mechanism.**

When retail/odd-lot share is elevated, **liquidity-provision and short-horizon mean-reversion on that name often improve**; **informed-order-flow / VPIN-style and institutional-imbalance signals weaken or flip**. Mechanism: a larger fraction of flow is uninformed or attention-driven, so adverse selection for the liquidity provider falls *unless* the name is also in a squeeze (R022) or a meme-cascade, in which retail is *directional* and MR dies. Odd-lot *count* share alone is a contaminated proxy (algos fragment; high prices create odd lots).

**(2) Documented evidence.**

O'Hara–Yao–Ye (JF 2014): odd lots were a large share of trades and contributed ~35% of price discovery — so "retail = noise" is **false as a blanket**. Later retail-ID work finds off-exchange retail can be *more* informed than off-exchange institutional flow on a volume-adjusted basis, and Robinhood-heavy days *reduce* that information content. MEMX: wholesalers ~34% of volume; odd-lot *trades* 66% of prints but a poor retail gauge. **Label:** microstructure papers are typically **pre-cost** at the SIP; live MR must subtract spread + rebate.

**(3) When classification fails.**

Using industry-wide odd-lot % as a *timing* switch misclassifies high-priced names and HFT-heavy names as "retail." Cost: you turn on MR in names where odd lots *are* the informed slice (O'Hara et al.). Fail if you skip volume-share and off-exchange flags.

**(4) Compounds with.**

R021 ∩ R022 = meme-squeeze (retail + HTB): MR **dies**, momentum-chase **improves until locate/fee breaks**. R021 ∩ R030 pre-FOMC: retail flow does not explain the index drift (that is a macro premium).

**Bottom line:** **sizing / filter**, not a trigger. Use as a name-level conditioner for MR vs momentum. Stand-down on MR if R022 is also ON.

---

## R022 — Hard-to-borrow / short-squeeze

**(1) Direction and mechanism.**

**Short-alpha dies mechanically** once fee + buy-in risk ≥ expected edge:

\[
\Pi_{\text{short}} \approx -r_{\text{stock}} - f\cdot\Delta t - \mathbf{1}_{\text{buy-in}}\cdot\text{slip} - \text{locate}
\]

Utilization \(\ge 90\%\) raises squeeze frequency from decades to days. **Long-momentum / squeeze-ride improves** on the same names; **stat-arb shorts and pair-trade short legs die**. Days-to-cover high means covering *is* the demand.

**(2) Documented evidence.**

Hard-to-borrow / high-fee names earn **low subsequent returns** (short-constraint literature; Desai et al. 2002 and the utilization paper above). Expected squeeze trading costs **29–37 bp/month** at fees \(\ge 25\%\), **56–73 bp** at utilization \(\ge 90\%\) — **after-cost relevant**. Practitioner DTC \(>5\)–\(6\) days is a watch band, not a law. GME 2021: SI can exceed float; DTC collapsed *during* the squeeze because ADV exploded — DTC used alone **fails in the event**.

**(3) When classification fails.**

FINRA SI is **bi-monthly + ~T+8**. Day-trading off last SI file is stale. IBKR fee ≠ prime-broker fee. Reg SHO list is a **lower-bound** HTB flag. Misclassification cost: shorting a 100%+ fee name "because residual is −2σ."

**(4) Compounds with.**

R022 ∩ R021 = squeeze-prone. R022 ∩ R023 analogue does not apply to US cash equity. R022 ∩ R028 wide OAS: crowded shorts in HY-beta names can squeeze *or* gap down — do not assume direction.

**Bottom line:** **stand-down flag for shorts**; **sizing cap** for any short book. Not a long trigger by itself (many HTB names just grind down).

---

## R023 — Crypto liquidation cascade

**(1) Direction and mechanism.**

**Mean-reversion on perps dies**; **momentum / liquidation-cascade follow-through improves** for the duration of forced flow. Mechanism: mark-price triggers create a **positive-feedback selling (or covering) schedule** that is not a willingness-to-trade demand curve. Basis and mark–spot gaps become the state variable, not residual value. After the flush, **MR and basis-convergence return**.

**(2) Documented evidence.**

Oct 2025 event: futures led; volume 22× baseline; mark undershot spot/futures (reflexive loop absent in cash equity). Public 24h totals are **floors** (3–5× undercount common). Liquidation *rate* in one cascade window: **$0.12B/h → $10.39B/h**. BIS DeFi work: liquidation waves transmit across venues (price impact + contagion). **Label:** event studies, not a live after-cost CTA backtest.

**(3) When classification fails.**

\(z\) on **reported\_\*** can miss the cascade (censoring) or fire on one-venue prints. Fill-count reconstruction **over-counts** episodes. Using a 30-day median when the last 30 days already include a cascade **raises the bar** and misses the next wave (look-ahead of the threshold).

**(4) Compounds with.**

R023 ∩ R029 strong-dollar / R024 hike-biased: USD stablecoin + funding stress amplifies long-liq cascades. R023 ∩ R030 FOMC: event vol + thin books.

**Bottom line:** **stand-down on fade-the-wick**; **trigger for risk-off / flatten leverage**. Re-enable MR only after OI and funding normalize (second test, not the z-score).

---

## R024 — Rate level / direction (FF path)

**(1) Direction and mechanism.**

Hike-biased path: **long duration dies**, **USD-long and short-duration / quality-equity improve**, growth-factor longs shrink via the discount-rate channel. Cut-biased: opposite. Hold-anchored (\(P>80\%\)): carry and vol-selling **improve** (event vol overpriced relative to a non-event). Mechanism: futures-implied path is the **mean of the risk-neutral distribution**, so it embeds premia — still the right *conditioning* variable for rate-sensitive books.

**(2) Documented evidence.**

CME FedWatch methodology is the market standard mapping ZQ → 25 bp tree. 2022: policy-tightening path coincided with **positive stock–bond correlation**, breaking 60/40's hedge (widely documented episode; correlation sign flip is a fact of that hiking cycle, not a single official "60/40 paper"). Pre-FOMC equity drift exists **regardless of hike vs cut** in Lucca–Moench (see R030) — so R024 **does not** own that 24h premium.

**(3) When classification fails.**

Treating 68% hike odds as "the Fed will hike" is a **category error** (probability ≠ event). Term premium in ZQ can move \(P\) with no policy news. Unscheduled moves and 50 bp steps violate the 25 bp tree. Misuse: flipping a 2s10s steepener on an intraday FedWatch tick.

**(4) Compounds with.**

R024 hike ∩ R026 hot CPI ∩ R025 inversion = **restrictive-and-getting-tighter** (bear flattener risk). R024 cut ∩ R028 OAS blowout = **emergency-ease** (bull steepener, credit long).

**Bottom line:** **factor tilt and duration overlay**, not a day-trade trigger. Size rate-sensitive books by \(P(\text{move})\) × 25 bp DV01, not by the headline.

---

## R025 — 2s10s shape

**(1) Direction and mechanism.**

**Inverted:** near-term policy tight vs long-run outlook → **bank NIMs / credit-creation fade**; **curve steepeners are the structural long**; **cyclical equity momentum less reliable** at long horizon (recession lag is long and noisy). **Bull steepener:** front end falls faster → **duration + risk-on often improve**. **Bear flattener:** hiking path → **risk-off for duration and housing-beta**. Mechanism: \(y_2\) ≈ expected funds path; \(y_{10}\) ≈ path + term premium + long-run growth/inflation.

**(2) Documented evidence.**

2s10s inversions preceded every modern US recession with a **long, inconsistent lag** — usable as **regime context, not a clock**. 2022–24 inversion peaked about **−108 bp** and lasted **>700 days** without a textbook immediate recession — the lag **failed as a timing tool**. Un-inversion / steepening into a slowdown is often the more coincident phase (descriptive market taxonomy).

**(3) When classification fails.**

**Gate: do not day-trade off inversion.** A single close of T10Y2Y below 0 is not a trigger. Slow indicator; misclassification cost is months of false "recession now." 3m10s and 2s10s can disagree; pick one ex ante.

**(4) Compounds with.**

R025 inverted ∩ R028 OAS \(>600\) bp ∩ R026 hot surprise = **stagflationary / tight-financial-conditions** bundle. R025 bull steepener ∩ R024 cut-biased = classic mid-cycle ease.

**Bottom line:** **factor tilt / stand-down on recession-clock strategies**. Never a same-day trigger.

---

## R026 — Inflation surprise

**(1) Direction and mechanism.**

Markets reprice **the gap**, not the CPI *level*. Hot surprise (\(z^{\pi}>0\) large): **duration dies**, **USD and real-yield-sensitive shorts improve**, long-duration equity / gold's rate-leg **hurt on impact**. Cold surprise: opposite. Mechanism: surprise revises the expected funds path (R024) within minutes; second-round is the curve and credit.

**(2) Documented evidence.**

Event-study on 2021–25 high-inflation regime: **CPI below consensus** produced large positive S&P abnormal returns (AR[0] ~0.88% in that paper's sample); upside CPI surprises produced negative ARs that were **weaker / less significant** — **asymmetric**. Practitioner: 0.1 vs 0.2 pp MoM core as fade vs join — **not** a journal law. **Label:** event-study **pre-cost**; live needs spread + 08:30 gap risk.

**(3) When classification fails.**

Using YoY when the tape trades **core MoM**; using a consensus that was **revised after** the lockup; mining \(\sigma\) window until \(z\) "fits." Headline vs core disagreement → LOW_CONFIDENCE, don't flip both ways.

**(4) Compounds with.**

R026 hot ∩ R025 inverted ∩ R028 widening = one **stagflationary state** (hike odds up, curve stays inverted or bear-flattens, credit starts to price growth damage). R026 cold ∩ R024 cut-biased = risk-on duration.

**Bottom line:** **event trigger** for the 08:30 window only; after the first hour it becomes a **tilt** into R024. Stand-down on pre-print positioning that assumes the number.

---

## R027 — Growth surprise (CESI / activity)

**(1) Direction and mechanism.**

Sustained **positive** surprises: **cyclical momentum and high-beta improve**; **defensive / long-vol / curve-steepener-as-recession-trade die**. Sustained **negative**: opposite. Mechanism: sequential surprises revise expected cash flows *and* the policy reaction function. A single NFP does not equal CESI; CESI is the **stock of surprises with decay**.

**(2) Documented evidence.**

Citi definition: weighted historical SDs of Bloomberg-median surprises, 3-month window, FX-impact weights, time decay. Sign: \(>0\) = beats. This is a **level of data-vs-forecast**, not a return study. Linking CESI to S&P direction in vendor notes is **descriptive**, not a documented edge after costs.

**(3) When classification fails.**

**Weights must be fixed ex ante.** Re-estimating FX-impact weights on the same sample is methodology mining. Official CESI is proprietary; a clone will drift. Using CESI as a *daily timing* switch ignores that it is a slow decaying sum — same Gate as credit/curve.

**(4) Compounds with.**

R027 weak ∩ R026 hot = **supply / stagflation** (activity misses, prices beat). R027 strong ∩ R026 hot = **demand**. R027 weak ∩ R028 wide = recession-credit bundle.

**Bottom line:** **factor tilt** (cyclical vs defensive). Not a trade trigger. Freeze weights; label clones.

---

## R028 — Credit stress (HY OAS)

**(1) Direction and mechanism.**

OAS blowout **kills high-beta equity mean-reversion and HY carry** via the **Merton channel**: equity is a junior claim; when the credit surplus shrinks, equity vol rises and jumps dominate, so "2σ extension fade" is picking up default-risk, not liquidity. **Quality / low-beta / TG treasuries improve** as a flight. Fast \(\Delta_{20}\) matters more than a high-but-stable level for *near-term* equity drawdowns. Tight OAS (\(<300\) bp): **carry improves**, crash risk is stored not absent.

**(2) Documented evidence.**

Descriptive 1997–2026 work: HY OAS trough led S&P peaks in major dislocations with median lead **~7 months** (range 1–13) — **slow**, not a day-trade. Crisis prints: GFC ~2182 bp, COVID ~1100 bp. Sub-300 bp = historically tight. **Label:** lead-lag is **documented descriptive**, not an after-cost trading rule.

**Classification:** — *(Grok did not mark a terminal classification on the worked example's R028 line in the extracted page; the regime call R028 = ON was established at the top of this section's worked example under Q-RB3-1.)*

**(3) When classification fails.**

**Gate: reject day-trading off OAS.** Using 620 bp as "sell tomorrow" ignores that 600–800 can persist. Thresholds differ by author (500 vs 600 vs 800). FRED series can lag ICE close. Misclassification cost: fading a Merton jump with an equity MR model.

**(4) Compounds with.**

R028 wide ∩ R025 inverted ∩ R026 hot = stagflation / tightening accident. R028 wide ∩ R024 cut-biased = policy-put setup (credit long *after* verification, not on the first +50 bp).

**Bottom line:** **stand-down / de-risk flag** for high-beta MR and HY carry when level is high *and* \(\Delta_{20}\) is large. **Tilt** to quality. Not a buy-the-dip trigger until widening *decelerates*.

---

## R029 — Dollar (DXY)

**(1) Direction and mechanism.**

Strong-dollar uptrend (50d > 200d, high percentile of the spread): **EM FX, gold's USD-leg, commodity-beta, and unhedged EAFE die**; **US quality / USD cash improve**. Mechanism: DXY is a weighted USD vs majors — it tightens global USD funding and revalues commodity revenues. Weak-dollar: opposite. Golden/death cross is a **trend filter**, not an alpha.

**(2) Documented evidence.**

Golden/death cross on DXY is standard TA; BofA descriptive note on post-cross hit rates in a 20–60 session window is **vendor statistics**, not a journal after-cost test. 2022 strong-dollar episode coincided with EM stress and commodity FX pain — **documented co-movement of that cycle**, not a trading system.

**(3) When classification fails.**

DXY vs **DTWEXBGS** (broad) can diverge (EM vs G10 mix). 50/200 is slow; whipsaws in ranges. Using 80th percentile of a 5-year \(G_t\) window that includes 2022's extreme **compresses** current readings.

**(4) Compounds with.**

R029 strong ∩ R024 hike-biased ∩ R026 hot = classic USD-bull bundle. R029 strong ∩ R023: crypto-dollar liquidity drain.

**Bottom line:** **factor tilt / FX hedge overlay**. Not a trigger. Size EM and gold as \(\beta_{\text{DXY}}\times G_t\) exposure, don't "sell DXY golden cross."

---

## R030 — Central-bank event proximity

**(1) Direction and mechanism.**

**Pre-FOMC 24h:** long equity index **improves unconditionally** in the Lucca–Moench sample (drift exists *whether* the decision is hawkish or dovish) — so this is an **event-premium**, not an R024 bet. **Volume dies into the event, jumps after.** **Short-gamma / vol-selling dies** in the 30-minute statement window; **breakout / news-reaction improves**. Mechanism: uncertainty resolution + discretionary liquidity traders staying out (asymmetric-info avoidance).

**(2) Documented evidence.**

Lucca–Moench: S&P **+49 bp** average in the 24h before scheduled FOMC vs ~4 bp ordinary day. Neuhierl–Weber: signed drift out to **~25 days** when conditioned on the *subsequent* surprise — **that** part is not tradeable without a policy forecast (look-ahead if you use the realized surprise). Pre-announcement quiet vol: older Bomfim-style result. **Label:** 24h drift is **documented pre-cost index**; implementation needs futures roll + gap at 14:00.

**(3) When classification fails.**

Applying the 24h drift to **single names**, crypto, or **unscheduled** meetings. Using the 25-day *signed* drift with the *ex-post* shock is leakage. Calendar errors (wrong date, silent meeting) = trading a non-event.

**(4) Compounds with.**

R030 pre-window ∩ R026 CPI week = stacked event risk (do not add CPI-direction bets into the FOMC drift). R030 ∩ R024 contested probabilities = fat statement tails.

**Bottom line:** **trade trigger** only for the **unconditional pre-FOMC index drift** (if you still believe the premium after costs). Everything else is a **stand-down flag** for short-gamma and a **sizing cut** 25 days → 1 day into the meeting.

---

## Joint compounding (use as a state vector, not 10 separate blogs)

Treat the live board as a small number of **macro states**:

| Bundle | Typical flags | What survives |
| ------------------------------------- | ------------------------------------------------------------- | -------------------------------------------------------------------- |
| **Stagflation / tightening accident** | R026 hot + R025 inverted + R028 widening + R024 hike-biased | USD, quality, short duration; **kill** 60/40, HY carry, high-beta MR |
| **Emergency ease** | R028 wide + R024 cut-biased + R025 bull steepener + R027 weak | Duration, eventual credit; **not** day-one HY long |
| **Meme microstructure** | R021 elevated + R022 ON | Squeeze-ride / stand-down shorts; **kill** name-level MR |
| **Crypto forced-flow** | R023 ON (+ R029 strong optional) | Flatten lev, no fade; wait for OI |
| **Event premium** | R030 24h pre-FOMC, R024 not required | Index long-drift only; **kill** short-gamma |
| **Complacent carry** | R028 tight + R024 hold + R029 quiet | Carry / vol-sell *sized*; crash risk stored |

2022 is the teaching year for the first row: hiking path + inflation surprises + rising yields produced **stock–bond correlation > 0**, so the 60/40 hedge **documented-failed** as a regime assumption (episode, not a trading rule).

---

## Honest role of each flag

| ID | Role |
| ---- | ------------------------------------------------------------------------------------- |
| R021 | Name-level **filter / sizing** for MR vs momentum |
| R022 | **Stand-down** for shorts; hard cap |
| R023 | **Stand-down** on fades; flatten |
| R024 | **Tilt** duration/USD; DV01 overlay |
| R025 | **Tilt** only; **Gate: no day-trade** |
| R026 | **Event trigger** at print; then folds into R024 |
| R027 | **Tilt** cyclical vs defensive; weights frozen |
| R028 | **Stand-down / de-risk** when level+speed both fire; **Gate: no day-trade** |
| R029 | **Tilt / hedge overlay** |
| R030 | **Trigger** only for documented pre-FOMC index drift; else **stand-down** short-gamma |

If a flag is slow (R025, R027, R028 level), it may change the *strategy menu* for weeks. If it is an event (R026, R030, R023), it changes the menu for hours. Do not mix those clocks.

---

END OF VERBATIM ANSWERS.

Notes on capture fidelity: (a) All three answers were produced by Grok in a single chat session in response to the exact question texts; no question was skipped or retried. (b) UI chrome from Grok's page (table "Copy/Save" buttons, "plain/Collapse/Copy" editor widget labels, citation pill labels, the chat input placeholder) was excluded — only Grok's authored content is reproduced above. (c) Math is reproduced in Grok's own LaTeX with its \(...\) / \[...\] delimiters, recovered from the message source. (d) Nothing here is a live-trading spec; per the task this is research material for a document. No external side effects were created (no purchases, posts, or account changes).
