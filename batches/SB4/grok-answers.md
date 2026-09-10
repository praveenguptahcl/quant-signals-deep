# SB4 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials
- Date: 2026-09-10
- Batch: SB4 — Order-flow estimation toolkit (S002, S005, S007, S010, S012, S015, S017, S018, S020, S047)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim via Grok's "Copy response" markdown export.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: a handful of fragments could not be captured verbatim and are marked `[brackets]` in the original capture notes below; nothing was fabricated. One inconsistency in Grok's own Q1 arithmetic is preserved as-is and flagged `[sic]`.

---

## Q-SB4-1 — formulas + worked example (verbatim)

All formulas below are taken from the cited papers. The 12-trade tape and the arithmetic on it are **illustrative**; they are not empirical estimates.

---

## 1. Multi-level and integrated OFI (Cont–Cucuringu–Zhang)

**Best-level increment (Cont, Kukanov & Stoikov, *JFQA* 2014).**

Between consecutive book snapshots n−1 and n,

e_n^b = +q_n^b if P_n^b > P_{n−1}^b; +q_n^b − q_{n−1}^b if P_n^b = P_{n−1}^b; −q_{n−1}^b if P_n^b < P_{n−1}^b

e_n^a = −q_n^a if P_n^a < P_{n−1}^a; −(q_n^a − q_{n−1}^a) if P_n^a = P_{n−1}^a; +q_{n−1}^a if P_n^a > P_{n−1}^a

OFI_n^(1) = e_n^b + e_n^a.

Positive = net buying pressure at the touch. Interval OFI is the sum of increments over events in (t−h,t].

**Level-m OFI (Cont, Cucuringu & Zhang, *Quantitative Finance* 23(10), 2023; arXiv:2112.13213).**

Apply the same increment rule to the m-th bid and ask queues. Over a window of length h,

OFI_{i,t}^{m,h} = Σ_{n=N(t−h)+1}^{N(t)} (OF_{i,n}^{m,b} − OF_{i,n}^{m,a}).

Normalize by average depth across the first M levels:

ofi_{i,t}^{m,h} = OFI_{i,t}^{m,h} / Q_{i,t}^{M,h},

Q_{i,t}^{M,h} = (1/M) Σ_{m=1}^{M} (1/(2ΔN(t))) Σ_n (q_{i,n}^{m,b} + q_{i,n}^{m,a}).

CCZ use **M=10** (top ten levels) as the working multi-level vector

ofi_{i,t}(h) = (ofi_{i,t}^{1,h}, …, ofi_{i,t}^{10,h})^T.

**Integrated OFI (same paper).**

Let w_1 be the first principal-component loading of the multi-level OFI vector (they report that PC1 accounts for **>89%** of cross-level variance). Then

ofi_{i,t}^{I,h} = w_1^T ofi_{i,t}(h) / ‖w_1‖_1.

Contemporaneous impact regression:

r_{i,t}^{(h)} = α_i + β_i ofi_{i,t}^{I,h} + ε_{i,t}.

**Practical ranges (documented).**

- Levels: M=10 in CCZ; best-level alone already carries most of the signal, adding depth raises contemporaneous R² (CCZ; practitioner summaries of that paper quote ~71% at the best level vs ~87% at ten levels — treat those percentages as **from that study**, not universal).
- Window h: event-time or clock-time buckets from tens of milliseconds to a few seconds in equity LOB work; CKS 2014 used event buckets.
- Sign: + = buying pressure.

---

## 2. Lee–Ready and Bulk Volume Classification

**Lee–Ready (Lee & Ready, *Journal of Finance* 46(2), 1991).**

1. **Quote rule.** Let m_t = (P_t^b+P_t^a)/2 be the prevailing mid (LR originally recommended a **5-second lag** of quotes vs. trades because of recording delays on 1990s NYSE tapes; modern TAQ practice often uses contemporaneous NBBO).
- P_t > m_t → buyer-initiated (s_t=+1)
- P_t < m_t → seller-initiated (s_t=−1)
2. **Tick rule** if P_t=m_t: compare P_t to the last *different* trade price P_{t*}. Uptick/zero-uptick → buy; downtick/zero-downtick → sell.

Signed volume of the trade: x_t = s_t v_t.

**BVC (Easley, López de Prado & O'Hara, "Discerning Information from Trade Data," 2015; also ELO 2012 VPIN papers).**

Aggregate trades into equal-volume (or time) bars of size V. For bar τ with last price P_τ,

V̂_τ^B = V_τ · t_ν((P_τ−P_{τ−1})/σ_{ΔP}),  V̂_τ^S = V_τ − V̂_τ^B,

where t_ν is the Student-t CDF with ν degrees of freedom (ELO also allow a Gaussian CDF Φ). σ_{ΔP} is the rolling standard deviation of bar-to-bar price changes.

**Practical ranges (documented in ELO and follow-ups).**

- Volume bar V: a fraction of daily volume (studies sweep from ~0.1% to tens of percent of ADV); futures work often uses a few thousand contracts. Time bars from 1s to 5 min appear in accuracy studies (accuracy rises with bar length).
- Distribution: Student-t with **small ν** (ELO discuss ν around 0.1–0.25) vs. Normal; σ window tens to ~100 bars.
- Zero price change ⇒ 50/50 split.

---

## 3. Kyle's λ by regression

**Theory (Kyle, *Econometrica* 53(6), 1985).**

Market maker: p = μ + λy, with equilibrium λ = σ_v / (2σ_u) (σ_v: value uncertainty; σ_u: noise-trading std).

**Empirical slope (Hasbrouck 2009 *JF*; Goyenko, Holden & Trzcinka 2009 *JFE*).**

Over bins n (standard: **five-minute** intervals),

r_n = λ S_n + ε_n

(often no intercept, or with intercept). Two common S_n:
- signed volume Σ_k s_k v_k;
- signed square-root dollar volume S_n = Σ_k s_k √|d_k| (Goyenko et al. TAQ lambda).

OLS through the origin: λ̂ = Σ_n S_n r_n / Σ_n S_n².

**Practical windows:** monthly λ from all 5-minute bins in the month (Hasbrouck/GHT); or rolling hours/days of trade-level Δp_t = α + λ(s_t v_t) + u_t. Units: price per share (or return) per unit signed volume.

---

## 4. Roll implied spread

**Roll (*Journal of Finance* 39(4), 1984).**

If the only serial covariance in observed price changes comes from bounce of half-spread s/2,

Cov(Δp_t, Δp_{t+1}) = −s²/4  ⇒  s = 2√(−Cov(Δp_t, Δp_{t+1})),

provided the covariance is negative. On returns, s_% = 200√(−Cov(r_t, r_{t+1})).

If sample covariance is positive the estimator is undefined; common patches are s=0 or "N/A" (Harris 1990 discusses a signed version). Sample covariance uses the N−1 adjacent pairs of first differences.

---

## 5. Hawkes intensity for order flow

Univariate linear Hawkes (Hawkes 1971; finance: Bowsher; Bacry–Muzy; Filimonov–Sornette):

λ(t) = μ + ∫_0^{t−} φ(t−s) dN(s) = μ + Σ_{t_i<t} φ(t−t_i).

**Exponential kernel (most common parametric choice):**

φ(u) = α e^{−βu}, α,β>0, ‖φ‖_1 = α/β < 1

(branching ratio <1 for stationarity). Multivariate: λ(t) = μ + Φ ∗ (dN), with self- and cross-excitation kernels between buy/sell market orders, limits, and cancels.

**Power-law kernels** φ(u) ∝ (u_0+u)^{−(1+γ)} are also used; empirical decay near γ≈1.5 is reported in several LOB Hawkes calibrations (treat the exponent as study-specific).

**Practical ranges (illustrative of the literature, not a single paper's "the" values):**

- μ on the order of events per second for liquid names;
- β^{−1} from tens of milliseconds to a few seconds for high-frequency excitation; branching ratio often estimated 0.6–0.9 on equities/futures (near-critical). Fit by MLE on event times or OLS-type intensity regressions.

---

## Worked example (illustrative tape)

**Synthetic 12-trade tape.** Prices in dollars, sizes in shares. Quotes are the *prevailing* bid/ask at print (contemporaneous mid; no 5-second lag). [final clause of intro sentence truncated in capture]

| # | P | v | Bid | Ask | Mid |
|---|---|---|---|---|---|
| 1 | 100.02 | 100 | 100.00 | 100.02 | 100.01 |
| 2 | 100.00 | 200 | 100.00 | 100.02 | 100.01 |
| 3 | 100.01 | 100 | 100.00 | 100.02 | 100.01 |
| 4 | 100.03 | 200 | 100.01 | 100.03 | 100.02 |
| 5 | 100.02 | 100 | 100.01 | 100.03 | 100.02 |
| 6 | 100.04 | 200 | 100.02 | 100.04 | 100.03 |
| 7 | 100.03 | 100 | 100.02 | 100.04 | 100.03 |
| 8 | 100.03 | 200 | 100.02 | 100.04 | 100.03 |
| 9 | 100.01 | 200 | 100.00 | 100.02 | 100.01 |
| 10 | 100.00 | 100 | 100.00 | 100.02 | 100.01 |
| 11 | 100.02 | 200 | 100.00 | 100.02 | 100.01 |
| 12 | 100.01 | 100 | 100.00 | 100.02 | 100.01 |

Total volume = 1800. Three **volume bars of V=600**:
- Bar 1: trades 1–4 (vol 600), last price P_1=100.03
- Bar 2: trades 5–8 (vol 600), last price P_2=100.03
- Bar 3: trades 9–12 (vol 600), last price P_3=100.01

Initialize P_0=100.00 (illustrative open).

### Lee–Ready on each print

| # | P vs mid | Tick fallback | s | signed x=sv |
|---|---|---|---|---|
| 1 | 100.02>100.01 | — | +1 | +100 |
| 2 | 100.00<100.01 | — | −1 | −200 |
| 3 | at mid 100.01 | last different px 100.00 → uptick | +1 | +100 |
| 4 | 100.03>100.02 | — | +1 | +200 |
| 5 | at mid 100.02 | last different 100.03 → downtick | −1 | −100 |
| 6 | 100.04>100.03 | — | +1 | +200 |
| 7 | at mid 100.03 | last different 100.04 → downtick | −1 | −100 |
| 8 | at mid 100.03 | last different still 100.04 (zero-downtick) | −1 | −200 |
| 9 | at mid 100.01 | last different 100.03 → downtick | −1 | −200 |
| 10 | 100.00<100.01 | — | −1 | −100 |
| 11 | 100.02>100.01 | — | +1 | +200 |
| 12 | at mid 100.01 | last different 100.02 → downtick | −1 | −100 |

Net signed volume = +100−200+100+200−100+200−100−200−200−100+200−100 = −200.

### BVC on the three bars

Price changes: ΔP_1=100.03−100.00=+0.03, ΔP_2=100.03−100.03=0, ΔP_3=100.01−100.03=−0.02.

**Illustrative** σ_{ΔP}: sample std of {0.03, 0, −0.02}: mean = 0.00333, s² = [(0.02667)² + (−0.00333)² + (−0.02333)²]/2 = 0.0006333, σ_{ΔP} ≈ 0.0252 (**illustrative**, 3 points).

Use **standard normal** Φ here so the CDF is computable by hand from well-known values (ELO prefer Student-t; that would require a table).

- Bar 1: z=0.03/0.0252≈1.19, Φ(1.19)≈0.883: V̂^B=600×0.883=530, V̂^S=70
- Bar 2: z=0, Φ(0)=0.5: V̂^B=V̂^S=300
- Bar 3: z=−0.02/0.0252≈−0.79, Φ(−0.79)≈0.215: V̂^B=129, V̂^S=471

BVC net buy volume ≈ 530+300+129−70−300−471 = +118 (vs Lee–Ready tape net −200). The two classifiers need not agree: BVC only sees bar-end price changes.

### Roll spread from the 12-price series

First differences Δp_t (11 values):
Δp = −0.02, +0.01, +0.02, −0.01, +0.02, −0.01, 0.00, −0.02, −0.01, +0.02, −0.01.
[first line of the align block was reconstructed from the tape; arithmetically consistent with the pairs Grok lists]

Ten adjacent pairs. Sample means of the two lagged series (pairs 1–10 and 2–11): mean(Δp^(0)) = −0.004, mean(Δp^(1)) = −0.003.

[Quoted verbatim as captured; Grok wrote "Cross-product sum of demeaned pairs = +0.00070 (illustrative arithmetic)" — [sic] — which is arithmetically inconsistent with the raw-sum line that follows (−0.0008), which Grok then uses for the covariance computation. Preserved as-is.]

Pairs (Δ_t,Δ_{t+1}): (−0.02,0.01),(0.01,0.02),(0.02,−0.01),(−0.01,0.02),(0.02,−0.01),(−0.01,0),(0,−0.02),(−0.02,−0.01),(−0.01,0.02),(0.02,−0.01).

Raw Σ Δ_t Δ_{t+1} = −0.0002+0.0002−0.0002−0.0002−0.0002+0+0+0.0002−0.0002−0.0002 = −0.0008

Cov̂ = (1/10)Σ(Δ_t−Δ̄^(0))(Δ_{t+1}−Δ̄^(1)) ≈ (−0.0008)/10 − (−0.004)(−0.003) = −0.000080 − 0.000012 = −0.000092.

ŝ_Roll = 2√0.000092 = 2×0.00959 ≈ 0.0192 dollars (**illustrative**; about 1.9 ticks if the tick is 0.01). Percentage form is not needed at P≈100.

### Kyle λ from 10 observations, by hand

Use trades 3–12 as ten observations (each trade is one bin — **illustrative**, not the 5-minute convention). r_n = Δp_n (dollar change at that print), S_n = Lee–Ready signed size.

| n | S | Δp | SΔp | S² |
|---|---|---|---|---|
| 3 | +100 | +0.01 | 1.0 | 10 000 |
| 4 | +200 | +0.02 | 4.0 | 40 000 |
| 5 | −100 | −0.01 | 1.0 | 10 000 |
| 6 | +200 | +0.02 | 4.0 | 40 000 |
| 7 | −100 | −0.01 | 1.0 | 10 000 |
| 8 | −200 | 0.00 | 0.0 | 40 000 |
| 9 | −200 | −0.02 | 4.0 | 40 000 |
| 10 | −100 | −0.01 | 1.0 | 10 000 |
| 11 | +200 | +0.02 | 4.0 | 40 000 |
| 12 | −100 | −0.01 | 1.0 | 10 000 |

Σ SΔp = 21.0, Σ S² = 250 000.

Through-origin OLS: λ̂ = 21/250000 = 8.4×10^{−5} dollars per share of signed volume.

Interpretation on this tape: 1 000 shares of net buying would be associated with about 0.084 dollars of price change. **Illustrative only.**

### Source list (citable)

| Topic | Source |
| Best-level OFI increment | Cont, Kukanov, Stoikov, JFQA 2014 |
| Multi-level / integrated OFI, M=10, PCA | Cont, Cucuringu, Zhang, Quantitative Finance 23(10) 1373–1393 (2023); arXiv:2112.13213 |
| Lee–Ready | Lee & Ready, Journal of Finance 46(2) 733–746 (1991) |
| BVC | Easley, López de Prado, O'Hara, SSRN 1989555 (2015); ELO VPIN papers 2012 |
| Kyle theory | Kyle, Econometrica 53(6) 1315–1335 (1985) |
| Kyle regression, 5-min, volume | Hasbrouck, JF 2009; Goyenko, Holden, Trzcinka, JFE 92 (2009) |
| Roll spread | Roll, Journal of Finance 39(4) 1127–1139 (1984) |
| Hawkes intensity / exponential kernel | Hawkes (1971); survey applications in Bacry et al., Bowsher, Filimonov–Sornette |

No other statistics in this chapter should be treated as measured facts.

---

## Q-SB4-2 — local build + buy vs build (verbatim)

All dollar figures that are not from a published fee page are labeled **indicative**. Throughput and storage that are not measured on your box are **illustrative estimates** for 50 liquid names (SPY/QQQ/mega-cap + liquid single names), regular hours, one primary venue unless noted.

---

## 1. Required feeds and indicative pricing

| Need | Schema | What it actually contains | Honest for | Indicative cost |
| L2 depth pipeline | **MBP-10** (or MBO if you rebuild the book) | Every add/cancel/modify/trade that touches the **top 10 price levels**, with size **and order count** per level | Multi-level OFI, book pressure, Hawkes on book events | Databento US Equities **Plus $1,500/mo** or **Unlimited $4,000/mo** (documented plan list prices). Live L2 on equities is **Nasdaq TotalView-ITCH** in their catalog; MBP-10 history is **last 1 month** on cheaper tiers, **8+ years** only on Unlimited. Historical usage also billed from **~$0.40/GB**. Direct prop-feed stack they compare against: **~$60,000/mo** vs SIP **~$10,500/mo**. |
| L1 / trade pipeline | **MBP-1** or **TBBO** + trades | Top-of-book events + every print; TBBO gives quote **immediately before** the trade | Lee–Ready, BVC, Roll, Kyle, Huang–Stoll | Same Databento plans (L1 is included more generously: 12 mo–8+ yr depending on tier). Cheaper path: **EQUS.MINI** / SIP-like top-of-book — no MBP-10. |
| SIP only | CTA/UTP last sale + NBBO | Consolidated last sale + national BBO. **No depth, no odd-lot quotes on classic SIP, no exchange aggressor flag** | Degraded L1 signals only | Vendor wrap **~$1.1k–2.5k/mo** plus exchange SIP access/non-display. Ballpark professional SIP non-display+access often cited **~$3.5k–10.5k/mo** all-in. Display-only professional quotes are much cheaper ($66–$92/subscriber-class quotes). |

**Minimum honest mapping**

- L2 pipeline: **MBP-10 on the venue you model** (usually XNAS TotalView). Multi-venue depth is 5–10× data and license.
- L1 pipeline: **TBBO** (preferred for Lee–Ready) or SIP trades+NBBO.
- Do **not** buy MBP-10 if the only estimators are BVC/Roll/Kyle/Huang–Stoll.

---

## 2. Events/sec — assumptions (illustrative, 50 liquid names)

Documented backdrop: a full Nasdaq ITCH day was already **~4.2×10⁸ messages market-wide in 2011** (mean); modern days are higher. That is **not** per-symbol.

**Illustrative working set for 50 liquid US names, Nasdaq only, RTH:**

| | Per mega-cap (SPY/QQQ/AAPL-class) | Median of the 50 | 50-name aggregate |
| MBP-10 events / day | 0.8–3×10⁶ | 1.5–4×10⁵ | **~3–8×10⁷** |
| Mean events / sec (6.5h) | 35–130 | 6–17 | **1.3k–3.4k** |
| Burst (open/close, 100 ms) | 2–8k | 0.3–1.5k | **15–40k** |
| MBP-1 / TBBO events / day | ~15–40% of MBP-10 | similar ratio | **~1–3×10⁷** |
| Trades only / day | 2–8×10⁴ | 5–20×10³ | **~0.5–1.5×10⁶** |

**Can a 128 GB M5 Max keep up?**

| Stack | Full-depth (MBP-10) per symbol | 50-name live |
| **Python + Polars** (batch micro-batches 50–200 ms) | Comfortable at **mean**; Polars is columnar and fast on Apple Silicon. Live path is the problem: Python ingest + GIL + per-event Hawkes update. **Illustrative ceiling: 5–15k events/s end-to-end** if you batch; **<2–4k/s** if you do per-event Python Hawkes + 10-level OFI in a tight loop. | **Mean yes. Open/close bursts: no**, unless you drop to 50–200 ms snapshots and accept stale intensity. |
| **Rust** (or Rust ingest + Polars/Arrow for features) | Book apply + 10-level OFI increment is a few dozen ns–µs per event. Hawkes exponential kernel is O(1) per event with a decayed sufficient statistic. **Illustrative: 0.5–2M events/s/core** for apply+OFI; Hawkes multivariate still 10⁵–10⁶/s. | **Yes**, including bursts, on a few P-cores. M5 Max is not the bottleneck; **the WAN feed and Python runtime are.** |

Practical split on this box: **Rust (or C++) live book + OFI + Hawkes state; Polars for 1s/1m feature frames and the L1 regressions.** Python-only L2 live on 50 names is a research prototype, not a production clock.

---

## 3. RAM and disk (50 symbols)

**Record size (illustrative).** Databento DBN MBP-10 carries 10×(bid/ask px, sz, ct) plus header — treat **~200–280 bytes/event** uncompressed; DBN/zstd often **4–8×** smaller on disk. MBP-1 ~80–120 B. Trades ~40–60 B.

| Horizon | L2 MBP-10 (50 names) | L1 MBP-1 / TBBO | Trades only |
| **1 session, raw events** | **8–20 GB** uncompressed; **2–5 GB** compressed DBN/Parquet | 2–6 GB raw; 0.5–2 GB compressed | 0.05–0.2 GB |
| **1 session, in-RAM working set** | Live books (tiny) + 1–5 min ring of events + feature frames: **2–8 GB**. Full-day event buffer in RAM: **10–25 GB**. | **1–4 GB** | **<1 GB** |
| **60 sessions L2** | **120–300 GB** compressed if you keep every MBP-10 event; **0.5–2 TB** if you store uncompressed CSV. | 30–120 GB compressed | a few GB |
| **60 sessions of derived features only** (1s OFI/Hawkes/BVC bars) | **2–8 GB** Parquet | similar | similar |

**128 GB M5 Max verdict:**

- Live L2 on 50 names + a rolling **5–10 day** hot cache of compressed events: **fits**.
- **60 days of raw MBP-10 on internal SSD:** tight if you keep raw + features + OS + models. Budget an external NVMe (2–4 TB) for the 60-day L2 archive.
- 60 days of L1/trades: **fits easily**.

---

## 4. Engineering hours (illustrative, one strong engineer who already knows the estimators)

| Workstream | L2 depth pipeline | L1 / trade pipeline |
| Feed client, symbology, session/halt handling | 40–60 h | 20–30 h |
| Book apply (10-level) + snapshot recovery | 40–80 h | 8–15 h (BBO only) |
| Multi-level OFI + integrated OFI (PCA weights offline) | 25–40 h | — |
| Book-pressure features (imbalance, multi-level slope, replenishment) | 20–35 h | 8 h (L1 imbalance only) |
| Hawkes (exp kernel, buy/sell ± cancel; MLE offline, O(1) live) | 40–70 h | 15–25 h (trade-time Hawkes only) |
| BVC + Roll + Kyle + Huang–Stoll | 8 h (you get trades "for free") | **35–55 h** (classification, bars, regressions, HS system) |
| Bar alignment, clock vs volume time, persist, dashboards | 25–40 h | 20–30 h |
| Correctness tests vs Databento examples / known prints | 30–50 h | 15–25 h |
| **Total to a research-grade live loop** | **230–375 h** (~6–10 weeks) | **120–180 h** (~3–5 weeks) |
| Production hardening (reconnect, gap fill, audit) | +80–150 h | +40–80 h |

Huang–Stoll is the awkward L1 piece: you need signed trades, midpoints, and a small VAR/regression stack (three-way: adverse-selection η, inventory δ, order-processing 1−η−δ). It does **not** need depth.

---

## 5. Buy vs build, and where SIP is not honest

### Verdict

| | L2 pipeline | L1 pipeline |
| **Buy data** | Yes — Databento (or equivalent) **MBP-10 / TotalView**. Do not scrape SIP and pretend it is L2. | Yes — TBBO or SIP+NBBO is enough. |
| **Build signals** | Build. There is no credible off-the-shelf "integrated OFI + Hawkes intensity" product that matches CCZ/Hawkes definitions on your clock. | Build. BVC/Roll/Kyle/HS are a few hundred lines once the tape is clean. |
| **Buy a platform** | Only if you already pay for a full OMS/market-data stack (Databento + Nautilus/custom Rust is the cheap path on a Mac). | Same. |
| **On this Mac** | **Build L2 in Rust ingest + Polars features.** Python-only live L2 on 50 names will miss bursts. | **Python+Polars is enough.** |

**Cost shape (indicative, 12 months, research use, one non-display app):**

- L2 honest: **$18k–48k** Databento license + optional extra venue licenses + ~0.3–0.5 FTE engineering first year.
- L1 honest: **$6k–18k** (Mini / L1 plan or SIP wrap) + ~0.15–0.25 FTE.
- Direct multi-venue prop feeds: **~$60k/mo** — not justified for a 50-name research book on a Mac.

### SIP honesty matrix

| Signal | SIP / NBBO + last sale | Databento MBP-1 / TBBO (prop L1) | MBP-10 |
| Lee–Ready | Usable with known error (no aggressor, quote lag, odd lots hidden). Academic-grade, not HFT-grade. | Better (venue BBO, often aggressor on prop trades). | Best (same + depth context). |
| BVC | Honest enough — only needs price and volume bars. | Honest. | Honest (overkill). |
| Roll | Honest enough on the trade price series. | Honest. | Honest. |
| Kyle λ | Honest enough if you accept Lee–Ready signs and 1–5 min bins. | Better signs. | Better if you sign with book. |
| Huang–Stoll | Honest enough as a daily/hourly research decomposition on SIP prints+mids. Not a live inventory model. | Preferred. | Not required. |
| Best-level OFI | Degraded / simulated-only for trading. SIP NBBO is consolidated, lagged, and historically incomplete on odd lots. [truncated clause in capture] | Honest for level-1 CKS OFI on that venue. | Honest. |
| Multi-level / integrated OFI (CCZ, M=10) | Not computable. Simulated-only. | Not computable. | Required. |
| Book pressure (depth slope, queue deplete/replenish, multi-level imbalance) | Not computable. Simulated-only. | L1 pressure only. | Required. |
| Hawkes on book events (add/cancel intensity) | Not computable. Simulated-only. Trade-time Hawkes on SIP prints is a different, weaker object. | Trade + BBO-change Hawkes only. | Required for book-event Hawkes. |
| Hawkes on trade times only | Acceptable research proxy. | Better timestamps. | Better. |

**Label these simulated-only if the only feed is SIP:** multi-level OFI, integrated OFI, any depth-weighted book pressure, Hawkes kernels on adds/cancels, [final word truncated in capture]

### Bottom line for this machine

- **Build the L1 pipeline first** (TBBO or SIP): BVC, Roll, Kyle, Huang–Stoll, optional trade-Hawkes. Fits RAM, Python+Polars is fine, [final clause truncated in capture]
- **Add L2 only if the chapter's claim is depth:** then pay for **MBP-10 / TotalView**, write the book+OFI+Hawkes loop in **Rust**, keep 60 days of raw L2 on external NVMe, and never backtest those signals on SIP.

---

## Q-SB4-3 — success ratios, after-cost efficacy, failure modes (verbatim)

Numbers below are from the cited papers. Where a paper studies *contemporaneous fit* rather than a tradable forecast, that is labeled. After-cost claims that the papers themselves do not test are labeled as such.

---

## 1. Multi-level OFI vs touch-only OFI (out of sample)

**Xu, Gould & Howison**, *Market Microstructure and Liquidity* 4(3–4), 1950011 (2018); arXiv:1907.06230. Six Nasdaq names, linear map from the MLOFI vector to contemporaneous mid-change. Out-of-sample RMSE (ticks), M=10 vs level-1 OFI:

| | AMZN | TSLA | NFLX | ORCL | CSCO | MU |
| OFI (L1) RMSE | 9.72 | 5.35 | 2.03 | 0.25 | 0.19 | 0.22 |
| MLOFI Ridge | 8.05 | 4.53 | 1.41 | 0.08 | 0.05 | 0.08 |
| Ridge improvement vs L1 | **17%** | **15%** | **31%** | **68%** | **74%** | **64%** |

OLS also beats L1 (12–68%) but Ridge is uniformly better. They state that OOS RMSE falls **with each added level**. Large-tick names (ORCL/CSCO/MU) gain more than small-tick names (AMZN/TSLA). This is **contemporaneous explanation**, not a multi-horizon alpha test. Cross-validation in XGH does not keep strict time order — Cont–Cucuringu–Zhang (CCZ) flag that.

**CCZ** (*QF* 2023 / arXiv:2112.13213), many names, chronological OOS R² for contemporaneous returns:

PI[1] **64.64%** → PI[2] **75.81%** → PI[5] **82.05%** → PI[8] **83.16%**. Gains after ~8 levels are ~0 or negative (PI[9] 83.15, PI[10] 83.11). In-sample L1 is 71.16%, L10 89.38%. Integrated (PCA) OFI is their recommended compression.

**Kolm & Westray** (SSRN 4568641): Bayesian multilevel OFI, average OOS R² from **~55% (best level)** to **~80% (ten levels)**; Shapley attribution ~**19%** of OOS R² from deeper levels, ~**3.4%** from cross-section.

**After-cost / failure.** None of these papers trade the residual. The object is Δm_t = β·OFI_t+ε_t *in the same bucket*. That R² does not pay the spread. Failure regimes: (i) using SIP/NBBO as if it were venue L2 (not the XGH/CCZ object); (ii) OLS without shrinkage when levels are collinear (XGH: OLS OOS worse than Ridge); (iii) horizons beyond the contemporaneous bucket — CCZ find lagged cross-impact decays fast; (iv) adding levels 9–10 can *hurt* chronological OOS R² (CCZ table).

---

## 2. Lee–Ready vs BVC on modern data

**Lee–Ready accuracy (true initiator known).**

| Study | Market / era | Rate |
| Odders-White, *JFM* 2000 | NYSE TORQ | **85%** correctly classified; systematic errors at mid, small trades, large/active names. Quote rule alone misclassifies 9.1% and leaves 15.9% unclassified. |
| Finucane 2000 / Ellis–Michaely–O'Hara 2000 | TORQ / Nasdaq | ~**83%** / **81%** |
| Asquith–Oman–Safaya, *JFM* 2010 | 2005 shorts/longs | Trade-level misclassification **up to 31–32%** with contemporaneous quotes; **1-second quote lag** cuts that to **21–22%**. Daily signed volume still nets out. |
| Older "~85%" is 1990s TORQ. Modern electronic books are worse at the *trade* level, better once you aggregate. | | |

**BVC vs tick / LR.**

- **Easley, López de Prado & O'Hara**, *JFE* 120 (2016): on **futures**, tick rules and BVC are both "relatively good" at aggressor side; tick often wins on raw classification; **BVC tracks information proxies (e.g. Corwin–Schultz spread) better**. Highest BVC figures in the ELO line are in the **high 80s–mid 90s** on futures (one report: BVC 87.6% vs tick 86.4% on ES; oil BVC ~91.6%).
- **Chakrabarty, Pascual & Shkilko**, *JFM* 25 (2015), **US equities**: LR/tick **beat BVC** on aggressor accuracy. Switching TR→BVC raises misclassification **7.4–18.1%**; LR→BVC **10.3–19.0%**. Best BVC time bar ~1 hour: BVC **79.7%** of volume vs TR **90.8%**, LR **92.6%**. Equity BVC is **materially worse than ELO futures**. Order-imbalance accuracy for BVC: **13.9%** (ultra-short bars) to **76.6%** (optimized). For explaining returns/liquidity/costs, OI from TR/LR is **comparable** to BVC. TR/LR give better VPIN-style toxicity estimates in their tests.

**Limits.** LR needs a usable BBO and still fails at the mid and in quote storms. BVC needs a bar long enough that ΔP/σ is informative; on equities that bar is often **minutes to an hour**, so it is not a tick classifier. ELO's claim is about *information content of bulk flow*, not winning a horse race on aggressor flags in stocks.

**After-cost / failure.** Signing error attenuates Kyle λ and HS components toward zero (classical errors-in-variables). Failure: midpoint-heavy names, sub-second equity bars for BVC, SIP without odd lots, using BVC as if it were LR.

---

## 3. Kyle λ / Amihud as execution-cost predictors

**What is documented**

- **Goyenko, Holden & Trzcinka**, *JFE* 92 (2009): daily/monthly liquidity *proxies* horseraced against TAQ/Rule 605 **effective spread, realized spread, and 5-minute price impact**. **Amihud does well as a price-impact proxy**; newer effective-spread estimators win spread horseraces. They conclude low-frequency proxies are not a fiction — they **correlate with actual trading-cost benchmarks**. They do **not** report a desk-level R² of Amihud or λ on implementation shortfall of a live algo.
- **Hasbrouck** (*JF* 2009) and GHT construct TAQ λ as the slope of 5-minute return on signed √$ volume — a **high-frequency impact benchmark**, not a pre-trade slippage model.
- **Ranaldo et al. / realized Amihud** (*Management Science*, realized-illiquidity line): realized Amihud (RV/volume) **correlates strongly with Kyle λ** and with quoted/effective spread; classic daily Amihud correlates less. It predicts short-horizon *returns* via an illiquidity-premium channel, not fill slippage of a given parent order.
- **Metaorder impact** (Tóth–Bouchaud and follow-ups; *Phys. Rev. X* 2011 and industry TCA): realized impact of a parent is closer to **σ√(Q/V)** than to Kyle's linear λQ. Linear λ **overstates** cost of large, slow metaorders and **understates** the cost of very small, urgent clips in a thin book.

**After-cost framing.** Amihud/λ are useful **rankers** of names and days (which stock is expensive to trade). They are weak **calibrators** of the dollars you will pay on *this* child order. Pre-trade TCA that uses linear λ without a square-root (or power) schedule will mis-size participation.

**Failure regimes.** (i) Intraday urgency ≠ daily Amihud; (ii) hidden liquidity / mid-point / dark fills; (iii) days when volume and volatility jump together (Amihud can fall while impact rises); (iv) using unsigned volume in Amihud when the desk's flow is one-sided; (v) estimating λ on Lee–Ready noise.

---

## 4. Hawkes order-flow models and micro-price

**Documented edge (statistical, short horizon).**

- Hawkes is the standard model of **self/cross-exciting** book events; exponential kernels fit short memory, power-law kernels fit longer order-flow autocorrelation (Bacry–Muzy, Filimonov–Sornette, Bowsher).
- **Forecasting OFI / next event:** e.g. Hawkes with a sum-of-exponentials kernel **best among tested models** for near-term OFI distributions on NSE tick data (*Computational Economics* 2026).
- **Return-sign / next mid move:** Hawkes timing + a continuous-output-error / imbalance state beats Poisson and some bar models on **BTC** and similar HFT tapes; papers report higher sign accuracy and higher *simulated* PnL vs naive benchmarks (Cestari-style MHP–COE line; arXiv 2312.16190). These are **small-sample, often crypto or single-name**, with Monte Carlo on tens of scenarios — not a 500-name equity live book.
- Market-making **under** a Hawkes LOB (RL / impulse control) can show positive Sharpe **in simulation** with fees on the order of **0–1 bp** liquidation or limit fees up to ~**0.2–0.6%** in some crypto MM papers before strategies die. That is a **simulator result**, not a documented live equity edge after exchange+broker+SIP fees.

**Does it survive fees?** The literature does **not** contain a clean, multi-year, US-equity, after-cost statement of the form "Hawkes intensity ⇒ +X bp net." What is documented: (i) intensity forecasts the **next few events**, not the next 5 minutes of mid after you pay the spread twice; (ii) branching ratios near 1 make forecasts fragile out of sample; (iii) once you only trade when predicted edge > half-spread + fees, trade count collapses (explicit in several MM papers). Treat tradable Hawkes alpha as **unproven on lit US equities after cost**.

**Failure.** Kernel misspecification (exp vs power), non-stationarity at the open/close, using trade-time Hawkes as if it were book-event Hawkes, and any signal whose holding period is longer than kernel memory.

---

## 5. Retail / odd-lot flow: informativeness

**Odd lots are not "noise."**

- **O'Hara, Yao & Ye**, *JF* 69 (2014): odd lots omitted from classic TAQ/SIP. Median odd-lot share of trades **24%** (some names **≥60%**). Odd-lot trades contribute **~35% of price discovery**; trades of 100 shares another large slice. Informed traders use odd lots / small sizes. Omitting them **biases order imbalance and "retail sentiment."** Earlier SSRN draft: median missing trades **19%**, discovery contribution **~30%**, 100-share trades **~50%**.
- **Bartlett, McCrary & O'Hara**, *RFS* 2023: superior **odd-lot quotes inside the NBBO** are routine. Prop-feed traders who see them have a documented information advantage; an XGBoost on odd-lot quotes predicts future prices; SEC round-lot reform **reduces but does not remove** the inside market.
- **Upson & Johnson**, *Financial Review* 2017: ~**50%** of "odd-lot trades" are the resting size of a *larger* marketable order (Nasdaq reports by resting size). **Odd-lot marketable orders are not more informed** than round/mixed lots once you fix that bias. O'Hara–Yao–Ye overstate "odd-lot *orders*" informativeness if you count prints rather than parent orders.
- **Johnson / stealth-trading line:** aggressive odd-lot *orders* can be shreds of informed flow; not all odd lots are informed.
- **Boehmer, Jones, Zhang & Zhang**, *JF* 76 (2021): TRF sub-penny algorithm for **marketable retail**. Stocks with positive identified retail imbalance outperform negative by **~10 bp over the next week**. Persistence explains **< half**; residual is consistent with (not proof of) firm-level information. Later wholesaler-sample work (Battalio et al.) shows **BJZZ misclassifies a large share of institutional sub-penny TRF prints as retail** — treat the 10 bp as an **upper bound on a noisy proxy**.

**After-cost.** 10 bp / week on a long–short of *imbalance portfolios* is not the edge on a single odd-lot clip. Odd-lot *quotes* are informative for **who has the prop feed**; they are not a retail-flow alpha by themselves. SIP-only research that drops odd lots **understates discovery and mismeasures OFI/OI**.

**Failure.** Equating "odd lot" with "retail"; using BJZZ as ground truth; computing OFI on SIP without odd-lot quotes (the "inside market" is invisible); assuming odd-lot prints = odd-lot intent (Upson–Johnson).

---

## After-cost scoreboard (literature, not a backtest)

| Object | Documented statistical content | Pays the spread? | Main failure |
| MLOFI vs L1 OFI | Yes: XGH OOS RMSE **−15% to −74%**; CCZ OOS R² **65% → ~83%** by ~8 levels | Contemporaneous only | SIP depth, extra levels 9–10, trading the fit |
| LR vs BVC | LR/tick win **aggressor % on equities** (CPS 2015: LR **92.6%** vs BVC **79.7%** at best bar); BVC wins **info-proxy** link on futures (ELO) | Signing is an input, not a trade | Equity short bars; mid trades |
| Kyle / Amihud | Correlate with TAQ impact/spreads (GHT 2009); realized Amihud ≈ λ | Rank names; do not price a metaorder (square-root law) | Urgency, dark, one-sided flow |
| Hawkes | Event timing / short-horizon sign in specialized samples | Not documented net of US equity fees | Near-critical branching, horizon > memory |
| Odd lots / retail | **30–35%** of discovery in odd-lot *trades* (OYY); inside-NBBO quotes (BMO); BJZZ **~10 bp/week** (noisy) | Quote-feed advantage is real; print-level retail L/S is small and proxy-fragile | SIP omission; BJZZ contamination |

For the chapter: cite XGH Table 10 and CCZ Table 1 as the multi-level OOS facts; cite Odders-White / Asquith and Chakrabarty–Pascual–Shkilko as the classification facts; cite GHT as the liquidity-proxy fact and Bouchaud/Tóth as the reason λ is not your TCA; treat Hawkes as a **intensity model with unproven after-cost equity alpha**; treat odd lots as **informative quotes and mixed-informative prints**, invisible on classic SIP.
