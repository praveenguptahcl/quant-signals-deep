# TB6 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials (account: Praveen Gupta)
- Date: 2026-09-10
- Chat: https://grok.com/c/92412180-c1b0-4727-8415-b2a2c1ca62e7
- Batch: TB6 — Statistical / ML & regime (T051–T060)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim via Grok's "Copy response" + clipboard read-back. LaTeX formulas captured from Grok's markdown.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: a few rendering fragments were partially obscured in the accessibility tree; they are marked with `[brackets]`. All thresholds are illustrative examples.
- Nothing here is a live-trading spec.

---

## Q-TB6-1 — mechanics + worked example (verbatim)

"This is a **research specification**, not a live trading system. Thresholds, horizons, and dollar sizes below are **examples**. Live performance is not implied."

"Canonical sources: Hamilton (1989) regime-switching; Zhang, Zohren & Roberts, *DeepLOB*, IEEE TSP 2019 / arXiv:1808.03668; Zhang et al., *BDLOB* arXiv:1811.10041 (uncertainty for sizing); López de Prado, *Advances in Financial Machine Learning* (purged CV + embargo); Barroso & Santa-Clara (2015) vol-managed momentum; Bernard & Thomas (1989) PEAD; news-momentum underreaction literature (e.g. news-return drift)."

### Shared risk envelope (all three books)

- **Unit of risk**: target daily book vol σ⋆ (example: 8–12% ann. on the combined book).
- **Hard constraints**: max gross leverage L_max (example 1.5–2.0), max single-name risk, kill-switch on realized 1-min vol or inventory.
- "Books A/B/C are **orthogonal roles**: A allocates *between styles*; B is a *microstructure trigger* inside a style; C is an *event overlay*. Do not let B and C stack full size on the same name without a cap."

### (A) HMM regime-switching allocator

**Momentum book vs reversal book**

**Model specification**

**Hidden states** S_t ∈ {M, R} (momentum / reversal). "Optional 3rd state U (uncertain / high-vol crash) if you want a cash sleeve."

**Observation vector** x_t (daily or 30-min bars; example):

x_t = (r_t, σ̂_t², ρ̂_t^(1), ADX_t, H_t, ΔVIX_t)

- r_t: excess log return of the traded universe (or a liquid proxy, e.g. ES).
- σ̂_t²: 20-bar realized variance ("Turner–Startz–Nelson style: variance separates regimes better than mean").
- ρ̂_t^(1): lag-1 autocorrelation of returns (sign of serial dependence).
- ADX_14, Hurst H_t on a rolling window (example 64–128 bars).
- Optional cross-asset: VIX / HY OAS (Guidolin–Timmermann).

**Emission**: Gaussian or Student-t mixture
x_t | S_t = s ∼ N(μ_s, Σ_s)
or diagonal Student-t if fat tails matter.

**Transition** (time-homogeneous Markov):

A = [ a_MM  a_MR ; a_RM  a_RR ], a_ss' = P(S_{t+1}=s' | S_t=s).

"Expect high persistence (a_ss near 0.95–0.99 on daily data). Fit by Baum–Welch / EM on a long in-sample window; **never** use smoothed γ_t = P(S_t | x_{1:T}) for live allocation — that looks into the future. Live inference is the **forward filter** (α-recursion) only:

α_t(s) ∝ p(x_t | S_t=s) Σ_{s'} A_{s's} α_{t-1}(s'),
π_t(s) = α_t(s) / Σ_u α_t(u).

That is the posterior used for weights."

**Allocation weights**

"Let π_t^M = P(S_t=M | x_{1:t}), π_t^R = 1−π_t^M (two-state)."

**Soft blend** (preferred; avoids binary flips):

w_t^M = clip( (π_t^M − τ) / (1−2τ), 0, 1 ), w_t^R = 1 − w_t^M

"with dead-zone τ (example τ=0.55: if π^M∈[0.45,0.55] hold last weights or go 50/50 cash-reduced)."

"Then apply **vol targeting** on each sleeve (Moreira–Muir / Barroso–Santa-Clara):

λ_t^k = min( σ⋆_k / σ̂_{t,k}^{EWMA}, L_max ), k ∈ {M, R}.

Final notionals:

N_t^M = w_t^M λ_t^M V_t, N_t^R = w_t^R λ_t^R V_t."

"**Hysteresis** (example): require two consecutive bars with π^M > 0.65 to raise w^M by more than 20 points; three bars with π^M < 0.35 to flip the other way. Cuts whipsaw at turns."

**Entry / exit / sizing inside each book (examples)**

| Sleeve   | Signal (example)                               | Entry                                      | Exit                                        | Size                                                  |
| -------- | ---------------------------------------------- | ------------------------------------------ | ------------------------------------------- | ----------------------------------------------------- |
| Momentum | 20/60 breakout or TSMOM sign of 10-day return  | break + ADX>25                             | trailing 2.5 ATR or time stop 5–10 days     | λ^M × name risk parity                      |
| Reversal | z-score of residual vs 20-bar VWAP / Bollinger | |z|>2 *against* the stretch | mean-reversion to z=0.5 or 1.0 ATR stop | λ^R × smaller per-name cap (reversal tails) |

"Allocator does **not** pick names; it only scales the two pre-built books."

**Worked example (A) — 5 synthetic posteriors**

"Assume τ=0.55 dead-zone mapping, σ⋆_M=σ⋆_R=10% ann., both sleeves currently at σ̂=10% so λ=1, NAV V=10,000,000."

| t | π^M | raw map (π^M−τ)/(1−2τ) | after clip + hysteresis note                                           | w^M | w^R | N^M | N^R |
| - | ---- | ----------------------------- | ---------------------------------------------------------------------- | ---- | ---- | ---- | ---- |
| 1 | 0.82 | 2.70 → 1.00                   | already in M; stay                                                     | 1.00 | 0.00 | 10.0m | 0   |
| 2 | 0.61 | 0.60                          | soft mix                                                               | 0.60 | 0.40 | 6.0m | 4.0m |
| 3 | 0.48 | −0.70 → 0                     | **inside dead zone** — hold *previous* mix                             | 0.60 | 0.40 | 6.0m | 4.0m |
| 4 | 0.28 | −2.70 → 0                     | two-bar confirm not yet if you require 3 bars; *example* we allow soft | 0.00 | 1.00 | 0    | 10.0m |
| 5 | 0.12 | 0                             | confirmed R                                                            | 0.00 | 1.00 | 0    | 10.0m |

"Shift path: full momentum → 60/40 → **no trade at the muddy 0.48** → full reversal. The economically important bar is t=3: the filter refuses to churn."

### (B) DeepLOB + feature-stack classifier as trade trigger

**Model specification**

"**DeepLOB core** (Zhang et al. 2019): input tensor

X_t ∈ R^{T×40}, T=100

= last 100 LOB snapshots × (10 ask px, 10 ask sz, 10 bid px, 10 bid sz). Prices usually normalized as mid-relative; sizes log or z-scored per name.

Architecture (canonical):

1. Conv block over price/size 'spatial' levels (inception-style multi-horizon filters).
2. Inception module (parallel 1×2 / 1×3 / 1×5 temporal kernels).
3. LSTM over the resulting sequence.
4. Dense + softmax over K classes.

**Labels** (example, FI-2010 style mid-move):

m_t(h) = (p̄_{t,t+h} − p̄_{t−h,t}) / p̄_{t−h,t},

y_t = +1 if m_t(h) > θ; −1 if m_t(h) < −θ; 0 else.

Example: h=20 events (~tens of ms to a few seconds on liquid names), θ set to a high percentile of |m| so classes are not 90% 'flat'.

**Feature stack on top of DeepLOB embedding z_t** (concatenate, then a small MLP / GBDT):

- imbalance / OFI / micro-price slope
- signed volume, VPIN-like toxicity
- spread in ticks, depth at L1–L5
- clock features (time-of-day dummies)
- optional: HMM π_t^M from book A as a conditioning feature

**Head**: 3-way softmax (p⁻, p⁰, p⁺). For sizing, also keep **MC-dropout / BDLOB** posterior variance û_t (Zhang et al. 2018 Bayesian DeepLOB)."

**Training / validation: purged CV + embargo**

"Labels have a **horizon** h, so i.i.d. k-fold leaks. Follow López de Prado:

1. Attach to every sample a prediction time t_i and label-end time t_i+h (plus any triple-barrier exit time).
2. **Purge**: drop from the train fold every sample whose [t_i, t_i+h] overlaps a test sample's interval.
3. **Embargo**: after each test block, drop an additional fraction ε of the subsequent train samples (example ε=0.01–0.02 of the sample count, or 5–10× the label horizon in event time). Embargo kills serial correlation that would otherwise let train features 'see' test outcomes.
4. Prefer **Combinatorial Purged CV** (CPCV): N groups, k test groups per split, recombine into multiple backtest paths so you get a distribution of OOS scores, not one lucky path.

Walk-forward on calendar months is the production pattern; CPCV is for research selection. Do **not** shuffle events. Class imbalance → focal loss or class weights. Early-stop on purged validation log-loss / F1, not in-sample accuracy."

**Entry / exit / sizing (example thresholds)**

"Let c_t = max(p⁺, p⁻), side = sign(p⁺ − p⁻).

- **Enter** only if c_t ≥ c_min (example 0.55–0.60) **and** p⁰ < 0.40 **and** uncertainty û_t < u_max.
- **Skip** the flat class entirely as a trade.
- **Size**:

q_t = q_base · (c_t − c_min)/(1 − c_min) · 1/(1 + κ û_t) · min(1, s⋆/s_t)

Example: c_min=0.58, κ=4, s⋆=1.5 ticks.

- **Exit**: first of (i) horizon h (time stop), (ii) mid move +δ take / −δ stop (example δ=2–4 ticks), (iii) opposite class with c_t ≥ c_min, (iv) spread blow-out."

**Latency budget (B)**

| Stage                                           | Budget (example, colocated liquid name)                                                                     |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| LOB snapshot → normalize + stack                | 20–50 µs                                                                                                    |
| DeepLOB forward (GPU/FPGA or distilled student) | 100–400 µs                                                                                                  |
| Feature stack + gate                            | 20–50 µs                                                                                                    |
| Risk + order construct                          | 20–50 µs                                                                                                    |
| Wire to matching engine                         | venue RTT                                                                                                   |
| **Decision SLO**                                | **≤ 0.5–1.0 ms** tick-to-order in a serious setup; 5–20 ms is already 'slow trigger,' not queue-competitive |

"If you cannot hold ~1 ms, use DeepLOB as a **1–10 s regime/trigger** on subsampled books, not a queue-join signal. 'Deep LOB trading: half a second please' is the slower-market literature; cash US equities need the tighter budget."

**Worked example (B) — confusion matrix → sizing walk, 20 synthetic predictions**

"**OOS confusion (rows = true −/0/+, columns = pred):**

C = [4 1 1; 2 5 1; 1 1 4] (20 samples)

Precision_+ = 4/6 = 0.667, Precision_− = 4/7 ≈ 0.571, accuracy 13/20 = 0.65.

**Empirical edge used for sizing calibration (example):** treat precision as P(win | fire). With 1:1 tick target/stop, expected value per fired + trade ≈ 2·0.667−1 = 0.333 ticks *before costs*. After 0.6 tick round-trip, EV still positive on +; on − it is 2·0.571−1−0.6 = −0.46 — so the live gate should be **asymmetric**: higher c_min on shorts."

"**20 synthetic predictions and positions** (q_base=100 shares, c_min=0.58, ignore u_t for the walk):"

| #  | p⁻   | p⁰   | p⁺   | c    | fire? | side | size | note                                                |
| -- | ---- | ---- | ---- | ---- | ----- | ---- | ---- | --------------------------------------------------- |
| 1  | 0.10 | 0.20 | 0.70 | 0.70 | Y     | +    | 29   | (0.70−0.58)/0.42×100                                |
| 2  | 0.22 | 0.55 | 0.23 | 0.23 | N     |      | 0    | flat dominates                                      |
| 3  | 0.62 | 0.18 | 0.20 | 0.62 | Y     | −    | 10   | weak short; in prod raise c_min⁻                    |
| 4  | 0.15 | 0.25 | 0.60 | 0.60 | Y     | +    | 5    | barely over gate                                    |
| 5  | 0.08 | 0.12 | 0.80 | 0.80 | Y     | +    | 52   |                                                     |
| 6  | 0.40 | 0.40 | 0.20 | 0.40 | N     |      | 0    |                                                     |
| 7  | 0.70 | 0.15 | 0.15 | 0.70 | Y     | −    | 29   |                                                     |
| 8  | 0.33 | 0.34 | 0.33 | 0.34 | N     |      | 0    |                                                     |
| 9  | 0.12 | 0.28 | 0.60 | 0.60 | Y     | +    | 5    |                                                     |
| 10 | 0.55 | 0.30 | 0.15 | 0.55 | N     |      | 0    | under 0.58                                          |
| 11 | 0.05 | 0.10 | 0.85 | 0.85 | Y     | +    | 64   |                                                     |
| 12 | 0.25 | 0.50 | 0.25 | 0.25 | N     |      | 0    |                                                     |
| 13 | 0.18 | 0.22 | 0.60 | 0.60 | Y     | +    | 5    |                                                     |
| 14 | 0.66 | 0.20 | 0.14 | 0.66 | Y     | −    | 19   |                                                     |
| 15 | 0.30 | 0.45 | 0.25 | 0.30 | N     |      | 0    |                                                     |
| 16 | 0.11 | 0.19 | 0.70 | 0.70 | Y     | +    | 29   |                                                     |
| 17 | 0.48 | 0.40 | 0.12 | 0.48 | N     |      | 0    |                                                     |
| 18 | 0.09 | 0.16 | 0.75 | 0.75 | Y     | +    | 40   |                                                     |
| 19 | 0.58 | 0.22 | 0.20 | 0.58 | Y     | −    | 0*   | *size 0 if you apply the asymmetric short gate 0.62 |
| 20 | 0.20 | 0.60 | 0.20 | 0.20 | N     |      | 0    |                                                     |

"Fired 11 (or 10 with asymmetric short gate). Net inventory path is long-biased because the synthetic + confidences were stronger — matching the confusion-matrix precision gap. That is the point of the walk: **the matrix tells you the short gate must be tighter**."

### (C) News-sentiment first-minute momentum

**Mechanics**

"**Economic rationale**: prices jump on news but **underreact** on average; a news-momentum book that buys (sells) the first printed return after signed news continues for minutes to days (PEAD is the slow cousin; first-minute is the microstructure cousin). Non-news returns more often reverse."

"**Pipeline**

1. **Ingest** point-in-time wire (Dow Jones / Bloomberg / RavenPack / similar). Timestamp t_0 = exchange-sync arrival, not publication datetime.
2. **Score** s ∈ [−1, 1] with a frozen NLP head (no peeking at the same-day return). Gate on relevance and novelty (example: relevance ≥ 0.7, novelty = first mention in 24 h).
3. **Event filter** (examples): scheduled earnings/8-K/analyst with |s| ≥ 0.4; drop rumours with low source rank.
4. **First-minute return** (the signal, not the alpha you assume you already have):

r_1m = (P_{t_0+60s} − P_{t_0⁺}) / P_{t_0⁺}

Use mid or micro-price, not last trade, to limit bounce bias. Require sign(r_1m) = sign(s) (agreement) **or** trade the headline sign if the print is too thin — pick one rule and freeze it.

5. **Trade**: enter at t_0+60s **only if**
- |s| ≥ s_min (example 0.50)
- |r_1m| ≥ r_min (example 15 bp for large-cap, 40 bp mid)
- spread ≤ s⋆ ticks
- ADV participation cap (example 1–2% of 1-min volume)

6. **Hold**: 5–30 minutes (first-hour continuation) or to cash close for PEAD-style.
**Exit**: time stop; give-back of 50% of open profit; or opposite headline.

**Sizing**

q = q_base · |s| · min(1, |r_1m|/r_ref) · min(1, ADV/ADV_0)

with a hard notional cap. Slippage model: half-spread + impact ψσ√(q/V_1m) (example ψ=0.5–1.0)."

**Latency budget (C)**

"This is **not** a race to the first tick after the headline (that is a different, much more expensive business)."

| Stage                                                     | Budget (example)    |
| --------------------------------------------------------- | ------------------- |
| Wire parse + ticker map                                   | 5–50 ms             |
| Sentiment inference (cached tokenizer + small classifier) | 10–80 ms            |
| Wait for 60s clock + print quality                        | **structural 60 s** |
| Child-order to VWAP/POV over 10–30 s                      | seconds             |

"Decision SLO after t_0+60s: **< 100–200 ms** to first child is plenty; the edge is the *agreement filter*, not microseconds."

**Worked example (C) — news-event timeline with slippage**

"**Synthetic event**: large-cap XYZ, mid at news P_{t_0⁺}=100.00, spread 2 cents, ADV high."

| Clock             | Event                                                          | Price / state                                       |
| ----------------- | -------------------------------------------------------------- | --------------------------------------------------- |
| 09:41:00.000      | Wire: 'XYZ raises FY guide'                                    | s=+0.72 (pass s_min=0.50)                |
| 09:41:00–09:41:12 | Jump + burst                                                   | mid 100.00 → 100.28                                 |
| 09:42:00.000      | **Decision bar** r_1m=+28 bp ≥ 15 bp, sign matches s | mid 100.28, spread 3 c                              |
| 09:42:00.080      | Send buy, cap 20,000 sh, POV 15% of 1-min volume             |                                                     |
| Fill              | 8,000 @ 100.31, 7,000 @ 100.34, 5,000 @ 100.36           | **vwap 100.331**                                    |
| Arrival mid       | 100.28                                                         | **slippage = 5.1 bp** vs decision mid               |
| Half-spread paid  | ~1.5 bp                                                        | rest is impact / walk                               |
| 09:47:00          | +5 min mid 100.49                                              | MTM +15.9 bp vs fill                                |
| 09:52:00          | time stop (example 10 min) mid 100.41                          | exit vwap 100.398 (1.2 bp exit slip)                |
| **Round trip**    |                                                                | **+6.7 bp net** on 20k sh = **$1,340** before fees |

"PnL arithmetic:
(100.398−100.331)/100.331 ≈ 6.7 bp.
If you had chased at t_0+2s at 100.22 and faded back, you would have paid a worse entry *and* failed the agreement filter — that is why the spec waits a full minute."

### How the three pieces fit

- "**A** chooses the *climate* (how much momentum book vs reversal book).
- **B** is a *barometric trigger* that may only be allowed to fire inside the sleeve A has funded (e.g. DeepLOB longs only if w^M is high; fade triggers only if w^R is high).
- **C** is an *event overlay* with its own cap so a headline cannot double-count with a DeepLOB long.

All numeric gates above are **examples**. Recalibrate on purged/embargoed paths; publish the CPCV score distribution, not a single Sharpe."

**Q-TB6-1 citations (captured URLs)**
- Foxholm (regime detection / HMM forward filter): https://foxholm.com/q/concepts/regime-detection/
- GitHub hmm-regime-trader: https://github.com/az9713/hmm-regime-trader
- DeepLOB (arXiv:1808.03668): https://arxiv.org/abs/1808.03668
- BDLOB (arXiv:1811.10041): https://arxiv.org/abs/1811.10041
- QuantInsti (CV embargo purging CPCV): https://blog.quantinsti.com/cross-validation-embargo-purging-combinatorial/
- "Deep LOB trading: half a second please" (ScienceDirect ESWA 2022): https://www.sciencedirect.com/science/article/abs/pii/S0957417422019170
- Duke/IPL seminar paper (PEAD / news underreaction): https://ipl.econ.duke.edu/seminars/system/files/seminars/2516.pdf
- (Named-only citations in text: Hamilton 1989; Turner–Startz–Nelson; Guidolin–Timmermann; Moreira–Muir; Barroso & Santa-Clara 2015; Bernard & Thomas 1989; López de Prado AFML.)

---

## Q-TB6-2 — infra + local build + buy vs build (verbatim)

"Numbers below assume **one 128 GB M5 Max** (40-core GPU, ~16.6–20.5 TFLOPS FP32, **614 GB/s** unified memory), Python stack (PyTorch MPS / MLX where it works, NumPy + `hmmlearn` / `statsmodels` on CPU). They are **order-of-magnitude**, not quotes. Vendor prices are indicative; almost every institutional news/LOB contract is negotiated and **forbids redistribution**."

### Hardware reality on this box

| Resource      | What you actually have                                                                                                                          |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Unified RAM   | 128 GB shared by CPU + GPU. Comfortable for 500-name daily panels and DeepLOB batches. Tight if you keep months of L2 LOB in RAM *and* train.   |
| GPU           | Metal / MPS, not CUDA. Conv nets are fine. **CuDNN LSTM does not exist.** LSTM training on MPS is slower and occasionally numerically annoying. |
| Bandwidth     | 614 GB/s — good for feature matrices, not a substitute for an H100.                                                                             |
| Sustained TDP | Laptop ~80–100 W. Overnight training is fine; multi-week heat/fan is the constraint, not FLOPs.                                                 |
| Disk          | Budget **4–8 TB external NVMe** now. LOB + news history will eat it.                                                                            |

"This machine is a **research / inference workstation**, not a training cluster and not a colocated trigger box."

### (a) HMM / Kalman / ARMA regime library — 500 symbols

**What "complete" means**

"Per symbol (and optionally a market factor): 2–3 state Gaussian/Student HMM (Baum–Welch + **causal forward filter**), optional Kalman on vol/trend, ARMA/AR(1) residual, Hurst/ADX/realized-var features, parquet store, walk-forward refit job."

"Fit is **CPU + BLAS**, embarrassingly parallel across names. GPU does almost nothing useful here."

**Compute / RAM / storage**

| Item        | Indicative                                                                                                                                |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Fit cost    | ~0.2–2 s/name/day-bar HMM on 5–10y daily; 500 names **minutes**, not hours. Intraday 1-min: 10–50× that → **1–4 hours** for a full refit. |
| RAM         | Feature panel 500 × 2,500 days × 20 cols ≈ tens of MB. Intraday 1-min × 2y × 500 ≈ **20–80 GB parquet**; keep on disk, window into RAM.   |
| Storage     | Daily library **< 5 GB**. Intraday features **50–200 GB**. Raw ticks are a different product (see B).                                     |
| Nightly job | Refit weekly, filter every bar: trivial on 18 CPU cores.                                                                                  |

**Data**

"You do **not** need LOB for A. Adjusted daily/minute bars + VIX/HY OAS: Polygon / Databento / Tiingo / FirstRate, roughly **$50–500/mo** retail-ish; institutional exchange-fee pass-through if you go official SIP."

**Engineering hours**

| Work                                                     | Hours                                  |
| -------------------------------------------------------- | -------------------------------------- |
| Data contracts, survivorship, corporate actions          | 20–40                                  |
| HMM + Kalman + ARMA library, tests, no look-ahead filter | 40–80                                  |
| Walk-forward + purged evaluation harness                 | 20–40                                  |
| Production job, monitoring, hysteresis on weights        | 20–40                                  |
| **Total**                                                | **100–200 h (~1.5–3 engineer-months)** |

"Reuse `hmmlearn`, `statsmodels.tsa`, `filterpy`. Do not write EM from scratch."

**Buy vs build**

"There is no serious off-the-shelf '500-name momentum/reversal HMM allocator' worth a license. Vendor **regime labels as a data feed** (rarely cheap, rarely transparent). The library is small, causal inference is the whole product, and **Buy only** a clean price panel."

### (b) DeepLOB-style model on M5 Max

**Model size vs the machine**

"Canonical DeepLOB is **tiny**: (100 × 40) input, a few conv + inception + LSTM, **≪ 1M parameters**. Memory is not the problem."

**Data volume and MPS kernels**

"FI-2010 is a toy (5 names × 10 days, ~0.2 s event spacing). A serious book is **months–years of L1/L2 snapshots** at event or 50–100 ms. Zhang et al. used **one year LSE L2** for the real test, not FI-2010."

**Honest training-time estimate (M5 Max, PyTorch MPS)**

"Assumptions: batch 64–128, T=100, 3-class head, mixed fp16 where MPS allows."

| Dataset                              | Samples (order)  | Wall time on M5 Max        | Notes                              |
| ------------------------------------ | ---------------- | -------------------------- | ---------------------------------- |
| FI-2010 (benchmark only)             | ~0.4M windows    | 30–90 min / 50–100 epochs  | Fine. Early-stop sooner.           |
| 10 liquid names × 6 months, 100 ms snapshots | ~5–15M windows | 1–4 days for one full train | I/O bound if not memory-mapped. |
| 50 names × 1 year event LOB          | tens of millions | 1–3 weeks one pass + tune  | You will subsample or you will suffer. |
| Same on 1× A100/H100 CUDA            |                  | ~4–10× faster              | CuDNN LSTM + fatter batch.         |

"**Do not expect CUDA-paper times.** **MPS LSTM is the tax.** A distilled conv-only student trains faster than full DeepLOB-LSTM on this chip. **Retrain cadence:** weekly fine-tune on new month = **hours**, not weeks, if you freeze convs."

**Inference latency per prediction**

| Path                                              | Latency (example, one forward)  |
| ------------------------------------------------- | ------------------------------- |
| PyTorch MPS, batch=1, full DeepLOB                | 3–15 ms                         |
| Batched 32–128 (research)                         | < 1 ms / sample amortized       |
| TorchScript / Core ML / MLX distilled student     | 0.5–3 ms                        |
| Colocated FPGA/GPU near exchange                  | 100–400 µs — not this Mac       |

"The Mac is a **research + slow trigger** box (seconds-to-minutes holds). It is not a queue-join engine."

"RAM during train: activations for batch 128 × 100 × channels fit in a few GB. The killer is the **dataloader** holding LOB history. Memory-map parquet/zarr; do not `read_csv` a year of books."

**Are GBTs the sane default?**

"**Yes, as the production default**, with DeepLOB as a research ablation. Documented pattern:

- On FI-2010-style *raw-book benchmarks*, DeepLOB / TABL beat linear and shallow nets (Zhang et al.: F1 **83.4%** vs prior SOTA **77.6%**). That is the paper's claim.
- On **realistic crypto/equity snapshots with handcrafted microstructure features**, trees match or beat DeepLOB and train in minutes. Kolm-style and 2025 Bybit LOB study: XGBoost / CatBoost **equal or better** than DeepLOB / CNN-LSTM on several horizons; 'better inputs matter more than another hidden layer.'"

"Operational reasons trees win on a Mac:

|                        | LightGBM / XGBoost          | DeepLOB                          |
| ---------------------- | --------------------------- | -------------------------------- |
| Train 10M rows         | minutes–1 h, CPU            | days on MPS                      |
| Inference              | 10–100 µs                   | ms                               |
| Feature changes        | add a column, refit         | relabel + retrain                |
| Purged CV loops        | cheap enough to do properly | expensive enough that people cheat |
| Debug                  | gain plots                  | saliency theater                 |

**Recommended stack:** handcraft OFI, micro-price, depth imbalance, spread, signed volume → LightGBM **first**. Keep DeepLOB as a second model on a **subset** of names if the tree plateau is real out of sample. Hybrid 'CNN embedding → XGB head' is the usual compromise."

**Data cost (this dominates B)**

| Feed                                         | Indicative                                              |
| -------------------------------------------- | ------------------------------------------------------- |
| FI-2010                                      | Free (research only)                                    |
| Databento / similar L1–L2 historical equities | hundreds–low thousands $/mo plus exchange fees         |
| Exchange official L2 (Nasdaq TotalView, etc.) | $5k–$20k+/mo professional, plus display vs non-display rules |
| Futures depth (CME MDP)                      | often cheaper per contract than US stock L2             |

"Without a paid book feed, you are fitting FI-2010 and kidding yourself."

**Engineering hours**

| Work                                             | Hours                                        |
| ------------------------------------------------ | -------------------------------------------- |
| LOB ingest, clock sync, normalization            | 80–160                                       |
| Labeling (triple barrier / horizon) + purged/embargo CV | 40–80                                  |
| LightGBM baseline + monitoring                   | 40–80                                        |
| DeepLOB port to MPS, train loop, distillation    | 80–160                                       |
| Inference service + kill switches                | 40–80                                        |
| **Total**                                        | **280–560 h (~2–4 engineer-months), data contract extra** |

**Buy vs build**

- "**Build the tree pipeline. Rent or skip DeepLOB training on this Mac.**
- Buy **data**, not a 'DeepLOB SaaS' (there isn't a serious one).
- If you insist on DL at scale, **rent 1× A100 for a weekend** ($1–2k) rather than burning two weeks of laptop time per idea."

### (c) News-sentiment + novelty pipeline

**Mechanics you actually have to own**

"Ingest → entity link to ticker → **novelty** (first story in 24h / minhash/simhash vs last N days) → sentiment / relevance → point-in-time stamp

Novelty is a **near-duplicate + entity + time** problem, not an LLM problem. Use hashing + cosine on embeddings; LLM only for low-volume scoring if needed at all."

**Data and licensing (the expensive, legally sharp part)**

"**Redistribution:** you may **not** republish wire text, RavenPack scores, or Bloomberg stories in a product, Substack, or shared repo."

| Source                                   | Indicative $                                                                            | What you get                                      | Redistribution   |
| ---------------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------- | ---------------- |
| Bloomberg Terminal                       | ~$25k–$33k / seat / yr                                                                | News + everything else                            | No. API (B-PIPE) is another contract. |
| RavenPack / similar event+sentiment      | Typically $50k–$250k+ / yr institutional (not list-price; scales with universe + real-time) | Ticker-linked events, relevance, novelty-ish fields | No            |
| MarketPsych / LSEG news analytics        | Same order, sometimes bundled                                                             | Sentiment time series                             | No               |
| Dow Jones / Factiva / FT analytics via RavenPack | Add-on on top of core                                                            | Premium text                                      | No               |
| Benzinga / NewsAPI / RSS + own NLP       | $0–$5k / yr                                                                            | Dirty, slow, poor entity link                     | Check ToS per source |
| SEC EDGAR + PR wires                     | Free / cheap                                                                             | Filings, not first-minute tape                    | Filings OK; wires often not |

"Retail APIs will **not** give you a trustworthy t_0 aligned to the exchange clock. That timestamp is the strategy."

**Compute / RAM / storage**

- "Embedding + novelty index for 2–5 years of headlines: **10–50 GB**"
- "FinBERT / small classifier on M5 Max: **< 10 ms / story**; thousands/hour is easy."
- "No GPU training required if you freeze a 110M encoder and train a linear/GBT head on labels you build from **subsequent returns** (careful: leakage)."

**Engineering hours**

| Work                              | Hours                                 |
| --------------------------------- | ------------------------------------- |
| Vendor integration + PIT clock    | 40–80                                 |
| Entity link + novelty index       | 40–80                                 |
| Sentiment head + calibration      | 20–40                                 |
| Reaction study + slippage sim     | 40–80                                 |
| Runtime (gate at T+60s)           | 20–40                                 |
| **Total**                         | **160–320 h given a licensed feed; 2× if you scrape** |

**Buy vs build**

"**Buy the feed, build the reaction layer.** Rolling your own NLP on RSS is how you discover, six months later, that your 'edge' was embargoed Reuters churnalism. Novelty: **build** (simhash + entity window). Vendors' novelty flags are a start, not a research-grade duplicate graph."

### Roll-up: year-1 cash and time on this Mac

| Piece            | Build hours | Recurring $                         | Capex on this machine | Verdict                                                              |
| ---------------- | ----------- | ------------------------------------ | --------------------- | -------------------------------------------------------------------- |
| (a) Regime library | 100–200   | $0.6k–6k data                       | already paid          | Build                                                                |
| (b) Trigger      | 280–560     | $6k–60k+ LOB data (the real bill)   | SSD 4–8 TB ~$400–800 | Build GBT; DeepLOB only as ablation; rent CUDA if you train DL often |
| (c) News reaction | 160–320    | $0–5k toy or $50k–250k+ real       | negligible            | Buy licensed events; build novelty + 1-minute join                   |
| Glue / risk / logging | 80–160 | —                                    | —                     | Build once                                                           |

"**Year-1 all-in if you stay honest on data:** roughly **$60k–300k cash** (almost all licenses) + **~0.7–1.5 engineer-years**. **Year-1 if you use free news + FI-2010:** cheap, and the research is not about the market you think you are trading."

**What the 128 GB M5 Max is good for**

- "500-name HMM/Kalman nightly: yes.
- LightGBM on millions of microstructure rows: yes.
- DeepLOB experiments on a slice: yes (overnight–weekend).
- DeepLOB as a production, sub-ms, 500-name event engine: **no**.
- News scoring and novelty: yes."

"**What to spend first**

1. Clean bars + VIX for (a) — days of work, real allocator.
2. LightGBM + a **paid L1** book on 10 names — tells you if B exists.
3. One licensed news analytics trial (not a Terminal screenshot) before writing a transformer."

"Thresholds and dollar bands are **examples**. Get a written license before you store vendor JSON on disk."

**Q-TB6-2 citations (captured URLs)**
- M5 Max specs: https://lowendmac.com/2026/apple-silicon-m5-max-chip-specs/
- DeepLOB (arXiv html): https://arxiv.org/html/1808.03668
- TABL (arXiv:2105.10430): https://arxiv.org/pdf/2105.10430v1
- 2025 LOB study (Bybit, arXiv:2506.05764): https://arxiv.org/html/2506.05764v2
- Bloomberg Terminal pricing: https://costbrief.com/bloomberg-pricing-cost-plans-what-you-pay/
- (Named-only: FI-2010; Databento; Nasdaq TotalView; CME MDP; Zhang et al. 2019; 'Kolm-style'; RavenPack; MarketPsych/LSEG; Dow Jones/Factiva; Benzinga; NewsAPI.)

---

## Q-TB6-3 — success ratios, after-cost efficacy, failure modes (verbatim)

"All thresholds and dollar figures below remain **examples**. The literature's honest message is narrower than most pitch decks: **regime overlays can cut crashes; LOB nets predict mids better than chance; trees often match them; news drift exists and is slower than the first print; almost none of that is a licensed, after-cost P&L.**"

### 1. HMM regime-switching vs a static blend

"**What is documented.** Hamilton's Markov-switching model is the ancestor. In allocation, the useful object is not 'the HMM is true,' it is **state-contingent exposure**: scale momentum when persistence is high, cut it when the state that produces momentum *crashes* is likely."

"Daniel, Jagannathan and Kim's *Hidden Markov Model of Momentum* is the cleanest value-add paper: a two-state calm/turbulent HMM on the market, plus the fact that cross-sectional momentum embeds a call on the market and **crashes in turbulence**. A timing rule that stands down in the turbulent state **avoids momentum crashes and improves OOS risk-adjusted performance** versus always-on momentum. That is crash insurance, not a higher mean in every year."

"Vol-managed momentum (Barroso & Santa-Clara 2015) is the reduced-form cousin: scale by realized vol, no HMM required, nearly doubles Sharpe of raw momentum by killing the same crash. HMM vs that static-vol blend: extra value only if the hidden state is **not** spanned by last month's σ."

"**Honest OOS picture.** Rolling/causal filters beat full-sample smoothed labels. A TradingView-style walk on ES/SPY makes the leak explicit: full-sample regime labels **disagree with a real-time forward filter on ~1 day in 11**, concentrated **at turns**—exactly where the allocation change would have mattered. Any backtest that tags history with a model fit on the whole sample is not an allocator you could have run."

"Bulla-style multi-decade HMM timing that **charges costs and damps turnover** tends to report **modest** after-cost excess, not 2.0 Sharpes. Short-window papers that rotate leveraged factors on HMM labels (e.g. ~2.5y OOS, Sharpe ~2) usually concentrate gains in one or two crisis months and fail a Treynor–Mazuy timing test. Treat those as case studies, not a prior."

"**Intraday allocation specifically.** Peer-reviewed *intraday* HMM *allocator* evidence is thin. Most HMM work is daily. Intraday, persistence of A is lower, so **turnover explodes** unless you add hysteresis (two/three-bar confirmation) and a dead zone on π_t. Value-add vs 50/50 momentum/reversal is then mostly **not trading the muddy state**, not a precise π_t."

"**Failure regime — misclassification.** The filter is late by construction (causal). You will still be in the momentum book for the first bars of a reversal. That is the 2009 and 2020 momentum-crash shape: the state flips faster than EM can admit. Mitigation: vol overlay *and* HMM, hard cap on w^M when σ̂ jumps, never use γ_{t|T}."

### 2. DeepLOB-class models: accuracy vs after-cost P&L

"**Documented prediction.** Zhang, Zohren & Roberts (IEEE TSP 2019): on FI-2010, DeepLOB F1 **83.40%** at horizon k=10 vs C(TABL) **77.63%**. On one year of LSE L2, OOS accuracy ~**70%** at k=20, and similar on names **not** in train—so the net extracts transferable book geometry, not one-ticker memorizations."

"**The gap the original papers leave open.** BDLOB (same authors) shows uncertainty-aware sizing **improves simulated mid-to-mid P&L** versus vanilla DeepLOB—and they state they follow the **same mid-price, no-transaction-cost** assumptions as the parent paper. That is a forecast-quality result, not a live book."

"A direct critique (Reading / *Mathematics* 2022): DeepLOB-style mid simulations print **median ~0.01 GBX per trade**; contemporaneous spread on a name like TSCO was ~**0.1 GBX**. Crossing the spread **swamps** the mid-edge. Mid-price + zero fees **overstate** tradable P&L; 'in its current form with a basic trading strategy it is unlikely to generate a consis[tent profit — tail obscured in capture].'"

"Where after-cost numbers are claimed, the market is usually slower: Chinese A-share L2 published ~every 3 seconds, 'half a second please,' spreads and fees included, and they still need focal loss + a separate position-sizing [model]; ([gate] ~90 trades/day) single-shot mean ~11 bp before 10 bp fees and lag; after 1-tick lag + 10 bp fee the cumulative collapses. Raising [the gate] to 20 drops frequency to ~2.7/day and raises per-trade mean—i.e. the edge is in **rare, aligned bursts**, not F1."

"**Honest mapping.**

| Layer | Typical published number | After-cost translation |
| ----- | ------------------------ | ---------------------- |
| FI-2010 F1 @ k | ~83% | Not P&L |
| LSE accuracy @ k | ~70% | Mid move, not fill |
| Mid sim, no costs | small positive ticks | Often < 1 spread |
| Realistic take + fees + lag | often ≤ 0 | Need selectivity, maker flow, or slower venues |"

"**Failure regimes.** (i) **Model decay**: book dynamics and tick-size regimes change; a 2017 LSE net is not 2026 US SIP. (ii) **Adverse selection**: you are correct on mid and still lose to informed flow. (iii) **Latency**: a 5–15 ms Mac forward is a research trigger, not a queue join. (iv) Label leakage via overlapping [labels without purging]."

### 3. Handcrafted-feature GBM vs deep LOB nets

"**When DL wins.** On the **raw 100×40 tensor**, with no human features, DeepLOB / TABL beat SVM, MLP, plain LSTM on FI-2010. That is the point of the feature engineer."

"**When trees win or tie.** Once you build OFI, micro-price, imbalance, depth, spread:

- A 2025 Bybit BTC LOB bake-off (logistic, XGBoost, CatBoost, CNN+LSTM, CNN+XGB, DeepLOB) finds that after Savitzky–Golay / sensible filters, simpler models match or beat DeepLOB; 'better inputs matter more than stacking another hidden layer.' On some 500 ms / 40-level settings [DeepLOB] exceeded.
- A small multivariate LOB study: **XGBoost MSE 1.725 vs LSTM 1.972** (and vs ES/ARIMA), with LSTM error compounding under recursive multi-step.
- Sirignano–Cont-style work and 'DL modeling of LOB, a comparative perspective' note that an **MLP can match CNN-LSTM**, i.e. the spatial-temporal story is not uniquely identified."

"**Operational documented gap.** Trees: minutes to train, tens of microseconds to score, trivial purged-CV. DeepLOB: days on MPS, milliseconds [to score; purged-CV expensive enough to skip]. **GBM-on-features is the default; DeepLOB is the ablation.**"

### 4. News-sentiment strategies: half-lives and required speed

"**Two clocks, do not mix them.**"

"**Slow clock (days–months) — this is where published alpha lives.**
- Bernard & Thomas (1989): PEAD lasts weeks.
- Tetlock (2007): WSJ pessimism predicts short-term market dips then reversal; Tetlock (2011): stale/reprinted news is discounted poorly.
- Firm-level 'news momentum': news-day return continues; a long-short on news-return deciles ~**3.34%/month in the following week** (four-factor α ~3.37%), stronger when investors are distracted; analysts revise with a lag. Drift is **strongest over the next few sessions**, not the next 800 ms.
- 'Pure news' after purging predictable content still predicts **months ahead** (NBER w35093)—a cross-sectional anomaly, not an HFT tape."

"**Fast clock (milliseconds–first hour) — this is where speed is required and median edge is tiny.**
- Groß-Klußmann & Hautsch (2011): machine-readable news hits **spreads and depth immediately**.
- Event-time reaction tables (point-in-time, no look-ahead) on single names often show **median 5–30 min moves of a few bp**, with IQR that includes both signs—average news is not a trade. Earnings are the exception: after-hours [announcements have] >90% jump probability, then next-day open/first hour is the revision.
- LLM-era letter: median SPY post-CPI quote lag compressed **~450 ms (2018–19) → ~120 ms (2023–24)**. Scheduled macro is now a **sub-second** race if you want the first impulse. Firm news first-minute continuation is a **different**, slower bet."

"**Required speed by style.**

| Style | Horizon of documented drift | Speed that matters |
| ----- | --------------------------- | ------------------ |
| First tick after CPI/NFP | 100–500 ms | Co-lo + parse in tens of ms |
| First-minute agreement filter | 1–30 min | Feed delay < a few seconds; execution seconds |
| News-momentum / PEAD | days–weeks | PIT timestamp, not microseconds |"

"**Failure regime — feed latency.** If your t_0 is the vendor's **processed** stamp 2–15 s after the exchange-visible headline, the first-minute return is already in the price and [you trade the echo]."

### 5. Overfitting: what purged CV + embargo actually protect — and what still kills you

"**The leaks they target** (López de Prado, AFML ch. 7):

1. **Overlapping labels.** A sample at t labeled with horizon h shares the path [t → t+h] with neighbors. Random k-fold puts the **same path** in train and test → inflated accuracy. **Purging** drops train rows whose label interval overlaps the test interval.
2. **Serial correlation after the test block.** Features at t+ε still know the test outcome (ARMA, trailing σ, book imbalance). **Embargo** deletes a fraction ε of train **after** each test block (example 1–2% of the sample, or several horizons).
3. **Single-path optimism.** One walk-forward path is one lottery ticket. **CPCV** recombines folds into many OOS paths so you see a **distribution** of Sharpes.

**What they do not [protect against].**

- **Selection across thousands of models.** Purge/embargo a search of 5,000 GBM+DeepLOB+HMM configs and you still need **Deflated Sharpe / PBO** (Bailey & López de Prado 2014 JPM; Bailey, Borwein, López de Prado & Zhu 2017 J. Comp. Finance). Expected max Sharpe of many null trials grows like log (some order of log K); a handful of independent trials can already make a raw Sharpe 1.5 look fine and a DSR fail.
- **Non-stationarity.** CPCV assumes the **mechanism** is similar across folds. Post-2020 microstructure, tick-size changes, LLM quote lag compression—none [of that is fixed by purging].
- **Vendor look-ahead** (restated news, revised sentiment, backfilled fundamentals).
- **Cost misspecification.** A purged 70% accuracy with mid fills is still a zero-edge strategy."

"**Famous failure modes without this discipline.**

- **Goyal & Welch (2008):** equity-premium predictors that work in-sample collapse OOS—the predictability graveyard.
- **Momentum crash (Daniel & Moskowitz 2016):** always-on momentum looks great until the state that the HMM is supposed to catch.
- **Quant quake, Aug 2007:** overcrowded stat-arb; models validated on their own history, not on simultaneous liquidation.
- **FI-2010 leaderboards:** high F1, mid simulation, no embargo → papers that do not survive a spread.
- Rule of thumb with no scientific basis: 'halve the backtest Sharpe.' DSR is the actual correction."

### After-cost honesty and the three decay channels

| Channel | How it shows up | What the literature says to do |
| ------- | --------------- | ------------------------------ |
| Costs | Mid-edge < spread; news median 30-min move ~0 | Report fill, not mid; bake half-spread + impact + fees before Sharpe |
| Model decay | DeepLOB/GBM IC fades as participants copy features; LLM compresses news lags | Walk-forward refit; treat last 12–24 months as a separate test; retire features that everyone has |
| Regime misclass | HMM late at turns; 1-in-11 label error if you cheat with smoothing | Forward filter only; dead zone; vol cap |
| News latency | You trade Tetlock-stale reprints | Exchange-sync t_0; novelty hash; drop [stale] |
| Overfit | One CPCV path looks good | DSR on the number of trials, PBO via CSCV, freeze the spec |

"**Compact verdict the citations support.** HMM timing has a **documented crash-avoidance** premium vs static momentum, smaller vs vol-targeting, and is easy to fake with smoothed states. Deep[LOB has a] **documented classification** premium on raw books and a **documented hole** once you pay the spread. GBMs on microstructure features are **documented peers**, not a consolation prize. News has a **documented multi-day underreaction** [and a] **documented sub-second** race on scheduled macro; first-minute firm-news continuation sits in between and dies if the feed is [late]. [Failure channels:] **path leakage**, **multiple testing**, **non-stationarity**. After cost, most published 'edges' in these three families are either insurance, slow drift, or an [tail obscured]."

**Q-TB6-3 citations (captured URLs)**
- Daniel, Jagannathan & Kim "Hidden Markov Model of Momentum": https://business.columbia.edu/faculty/research/hidden-markov-model-momentum
- TradingView-style ES/SPY regime walk: https://www.tradingview.com/chart/ES1!/3VRMCBlU-One-Ticker-Two-Markets-Non-Stationarity-and-Hidden-Regimes/
- Bulla-style multi-decade HMM timing (Wang–Lin–Mikhelson 2020): https://www.signaltrace.wiki/markov-model/Papers/Wang-Lin-Mikhelson-2020
- BDLOB: https://scholar.googleusercontent.com/scholar?q=cache:sg_gSqVZu8YJ:scholar.google.com/&hl=en&as_sdt=0,5
- Reading / Mathematics 2022 DeepLOB critique: https://centaur.reading.ac.uk/104707/1/mathematics-10-01234-v2.pdf
- "Deep LOB trading: half a second please" (ScienceDirect): https://www.sciencedirect.com/science/article/abs/pii/S0957417422019170
- LLM-era CPI quote-lag letter (Taylor & Francis): https://www.tandfonline.com/doi/full/10.1080/23322039.2026.2683062
- Bailey & López de Prado 2014 (Deflated Sharpe): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- Bailey, Borwein, López de Prado & Zhu 2017 (PBO): https://escholarship.org/content/qt7r56s6sq/qt7r56s6sq.pdf
- (Named-only: Hamilton 1989; Barroso & Santa-Clara 2015; Treynor–Mazuy; Daniel & Moskowitz 2016; Goyal & Welch 2008; Bernard & Thomas 1989; Tetlock 2007/2011; Groß-Klußmann & Hautsch 2011; NBER w35093; Sirignano & Cont; López de Prado AFML ch. 7.)

---

## QC notes (orchestrator)

1. Q1 (A): the stated soft-blend formula w^M = clip((π^M − τ)/(1−2τ), 0, 1) contradicts the worked table. With τ=0.55, (1−2τ) = −0.10; the table's "raw map" values (2.70, 0.60, −0.70, −2.70) are computed with denominator (2τ−1) = +0.10: (0.82−0.55)/0.10 = 2.70 ✓; (0.48−0.55)/0.10 = −0.70 ✓. Under the formula as written, π^M=0.82 would give −2.70 → clip to 0, not 1.00. Table internally consistent with (2τ−1); formula text contradicts it. Preserved verbatim.
2. Q1 (B): EV arithmetic. With 1:1 tick target/stop, EV per fired + trade = 2·0.667−1 = 0.333 ticks before costs. Grok's "after 0.6 tick round-trip, EV still positive on +" contradicts its own numbers (0.333−0.6 = −0.267, negative). The − leg (2·0.571−1−0.6 = −0.46) is arithmetically correct. Preserved verbatim.
3. Q2: engineer-time ↔ engineer-months/years labels are inconsistent with the hours: 100–200 h labeled "(~1.5–3 engineer-months)" (~0.6–1.25 mo at 160 h/mo); 280–560 h as "~2–4 engineer-months" (~1.75–3.5 mo, closer); roll-up 620–1200 h labeled "~0.7–1.5 engineer-years" (~0.3–0.6 yr at 2000 h/yr). Roll-up cash (~$60k–300k) is roughly consistent with components ($0.6k–6k + $6k–60k+ + $0–5k toy or $50k–250k+ ≈ $56.6k–316k+). Preserved verbatim.
4. Capture caveats: a few rendering fragments were partially obscured in the accessibility tree and reconstructed in the most natural form, marked with `[brackets]`. Grok's own "Copy response" output pasted the (B) walk table twice (plain/markdown chrome); the duplication was omitted as UI chrome, not answer content.
5. Key sourced claims are research leads, not verified facts: Zhang–Zohren–Roberts 2019 (DeepLOB F1 83.40% FI-2010, ~70% LSE L2); Zhang et al. 2018 (BDLOB); Hamilton 1989 (Markov-switching); Corsi 2009 (HAR, cited TB5); López de Prado AFML (purged CV, embargo, CPCV); Bailey & López de Prado 2014 (deflated Sharpe); Bailey, Borwein, López de Prado & Zhu 2017 (PBO); Daniel, Jagannathan & Kim (HMM momentum timing); Barroso & Santa-Clara 2015 (vol-managed momentum ≈ doubles Sharpe); Daniel & Moskowitz 2016 (momentum crashes); Goyal & Welch 2008 (predictability graveyard); Bernard & Thomas 1989 (PEAD); Tetlock 2007/2011 (news pessimism, stale news); Groß-Klußmann & Hautsch 2011 (machine-readable news); Ni–Pearson–Poteshman 2005 (expiration clustering, TB5); Pan & Poteshman 2006 (open-buy volume, TB5); Driessen–Maenhout–Vilkov 2009 (correlation risk, TB5). Vendor prices: indicative — verify before budgeting.

---

## Source list (only papers actually used)

- Hamilton, J.D. (1989), "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle," Econometrica.
- Zhang, Z., Zohren, S. and Roberts, S. (2019), "DeepLOB: Deep Convolutional Neural Networks for Limit Order Books," IEEE TSP / arXiv:1808.03668.
- Zhang, Z. et al. (2018), "Bayesian DeepLOB: Uncertainty Quantification and Robustness" (BDLOB), arXiv:1811.10041.
- López de Prado, M. (2018), Advances in Financial Machine Learning (purged CV, embargo, CPCV).
- Bailey, D.H. and López de Prado, M. (2014), "The Deflated Sharpe Ratio," Journal of Portfolio Management.
- Bailey, D.H., Borwein, J.M., López de Prado, M. and Zhu, Q.J. (2017), "Pseudo-Mathematics and Financial Charlatanism," Notices AMS (PBO).
- Barroso, P. and Santa-Clara, P. (2015), "Momentum Has Its Moments," JFE (vol-managed momentum).
- Daniel, K., Jagannathan, R. and Kim, S. (2012), "Tail Risk in Momentum Strategy Returns" / HMM momentum timing (2012).
- Daniel, K. and Moskowitz, T.J. (2016), "Momentum Crashes," JFE.
- Bernard, V.L. and Thomas, J.K. (1989), "Post-Earnings-Announcement Drift," JAR.
- Tetlock, P.C. (2007), "Giving Content to Investor Sentiment," JF.
- Tetlock, P.C. (2011), "All the News That's Fit to Reprint," JF.
- Groß-Klußmann, A. and Hautsch, N. (2011), "When Machine Readable News Arrives," JFE.
- Daniel–Jagannathan–Kim HMM momentum paper (Columbia faculty page).
- Goyal, A. and Welch, I. (2008), "A Comprehensive Look at the Empirical Performance of Equity Premium Prediction," RFS.
- Everything not attributed to one of the above — thresholds, cost figures, worked-example values — is illustrative.
