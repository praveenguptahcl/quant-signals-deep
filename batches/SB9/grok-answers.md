# SB9 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials
- Date: 2026-09-10
- Chat: https://grok.com/c/2804bf43-9461-42ec-9a76-84321223e2fc
- Batch: SB9 — Stat/ML infrastructure + MM skew (S075, S076, S077, S078, S080, S082, S084, S087, S089, S016)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim via page text extraction.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: DOM-echo duplication collapsed to one instance per phrase. Square-bracket markers like `[truncated in extraction]` are the browser task's own markers — the rendered page almost certainly showed complete words, but nothing was filled in. A few inline parameter symbols (T, gamma, kappa, tau, K) were lost in math extraction.

---

## Q-SB9-1 — formulas + worked example (verbatim)

Exact formulas, symbol definitions, and illustrative parameter ranges follow. Then one fully worked numerical example (3 Kalman updates by hand + first-PC residual on a 3-asset 10-day panel). All numbers and ranges marked as examples are not calibrated claims.

### (1) Kalman-filtered local-level fair value

State-space (local-level / random-walk-plus-noise) — Durbin & Koopman; Harvey, Forecasting, Structural Time Series Models.

- y_t: observed mid/last/microprice
- mu_t: latent "fair" level (filtered state)
- Q: process (signal) variance
- R: observation (noise) variance
- q = Q/R: signal-to-noise ratio

Filter (scalar). Prior at t: mu_{t|t-1}, P_{t|t-1}. Prediction innovation v_t = y_t − mu_{t|t-1}, F_t = P_{t|t-1} + R. Kalman gain K_t = P_{t|t-1} / F_t. Update: mu_{t|t} = mu_{t|t-1} + K_t v_t, P_{t|t} = (1 − K_t) P_{t|t-1}. Predict (already implicit after previous update): mu_{t+1|t} = mu_{t|t}, P_{t+1|t} = P_{t|t} + Q. Fair value at t: mu_{t|t}. Diffuse start often P_{1|0} = 10^6 · Q (or e.g. 10); a finite start is also used in practice.

Practical ranges (examples, not universal):
- Tick/1-second mids: Q on order of short-horizon mid variance. [page shows garbled repeated fragment after this — extraction artifact]
- R is set to a squared tick or short-horizon mid variance; Q is often 10^-3 to 10^-1 x R on 1-min.
- If you estimate Q/R from first-difference ACF: rho_1 = − R / (Q + 2R).
- Too large Q: filter tracks noise. Too small Q: laggy fair value.

Sources: Durbin & Koopman, Time Series Analysis by State Space Methods; Harvey (1989).

### (2) PCA / eigenportfolio residual reversal

Avellaneda & Lee (2010), "Statistical Arbitrage in the U.S. Equities Market."

On a window of T days and N names, let r_{t,i} be returns. Standardize X_{t,i} = (r_{t,i} − mu_i)/sigma_i. Let C be the N x N sample correlation matrix of X. Eigen-decomposition C = V Lambda V', eigenvalues lambda_1 >= lambda_2 >= ... , eigenvectors v^(k). Eigenportfolio (factor) return F_{k,t} = sum_i v_i^(k) X_{t,i} (Avellaneda–Lee weights w_i^(k) = v_i^(k)/sigma_i in raw-return space). Equivalently in standardized space the first-PC score is s_{1,t} = sum_i v_i^(1) X_{t,i}. Idiosyncratic residual for name i after K PCs (standardized): Xtilde_{t,i} = X_{t,i} − sum_{k<=K} v_i^(k) s_{k,t}. In raw-return space after one PC: eps_{t,i} = sigma_i (X_{t,i} − v_i^(1) s_{1,t}). Residual is then treated as OU; s-score uses estimated sigma_eps: s_t = eps_{t,i} / sigma_eps.

Practical ranges (examples):
- Correlation window: 252 days (Avellaneda–Lee default); 60–504 also used.
- Residual/OU window: 60 days (A&L).
- Factors K: 1 on a small universe; ~15 on S&P-500 scale, or first M that push residual spectrum near Marchenko–Pastur.
- Trade residual when |s_t| >= ~1.25 large (A&L illustrative: reversion time tau < estimation window).

Sources: Avellaneda & Lee, Quant. Finance 2010.

### (3) Hasbrouck (1991) trade–quote VAR

Hasbrouck, "Measuring the Information Content of Stock Trades," Journal of Finance 46 (1991).

Let r_t be the quote-mid (or mid) revision and x_t signed trade (e.g. +q buy, −q sell; sometimes sign or sign|q|). Bivariate VAR(p) with trades contemporaneously causing quotes r_t, not the reverse:

r_t = sum_{i=1..p} a_i r_{t-i} + sum_{i=0..p} b_i x_{t-i} + u_t
x_t = sum_{i=1..p} c_i r_{t-i} + sum_{i=1..p} d_i x_{t-i} + v_t

Innovations (u_t, v_t): contemporaneous covariance sigma_uv need not be 0 (ordering assumption handles it). Permanent price impact of a trade innovation is the cumulative impulse response CUMIRF = sum_{h>=0} dr_{t+h}/dv_t. Hasbrouck's summary informativeness (RFS 1991 companion) decomposes efficient-price variance into trade-correlated and trade-uncorrelated parts.

Practical ranges (examples):
- Lags p = 5 (Hasbrouck's NYSE illustration) to p = 10–20 on event time.
- Horizon for CUMIRF: 10–50 events (until response flattens).
- x_t: signed size, or log|q_t|.

Sources: Hasbrouck (1991) JF.

### (4) Fractional differentiation, fixed-width window

Lopez de Prado, Advances in Financial Machine Learning, Ch. 5; weights from Hosking (1981).

Infinite filter: Delta^d X_t = sum_{k>=0} w_k X_{t-k}, w_0 = 1, w_k = − w_{k-1} (d − k + 1)/k. Fixed-width: drop weights with |w_k| < tau, keep the first l*. (−d choose k) up to sign convention; recursion above is the one used in code.

- d in [0.3, 0.6] for many equity/FX levels (find smallest d with ADF reject).
- Weight floor tau: [no numeric value in extracted text]
- Resulting l*: tens to a few hundred lags depending on d.
- d = 0 recovers X_t; d = 1 is the raw series. [extraction shows "d = 1 is the raw series" — normally d=1 is first differences; preserved verbatim]

Sources: Lopez de Prado (2018), Ch. 5; Hosking (1981).

### (5) Avellaneda–Stoikov reservation price and optimal spread

Avellaneda & Stoikov, "High-frequency trading in a limit order book," Quant. Finance 8 (2008). Mid s is arithmetic Brownian motion with vol sigma; exponential utility risk aversion gamma; fill intensity lambda(delta) = A e^{−kappa delta}. Reservation (indifference) price r = s − q · gamma sigma^2 (T − t). Optimal total spread (asymptotic closed form): delta_a + delta_b = gamma sigma^2 (T − t) + 2/gamma ln(1 + gamma/kappa). Symmetric quotes about r ± (delta_{a,b}/2).

- q: signed inventory (long +)
- A: base fill intensity
- sigma: mid vol in the same time unit as T
- kappa: decay of fill intensity in price space
- T − t: remaining horizon

Practical ranges (examples — units must be consistent):
- Session horizon T if time is in days; or seconds if sigma is per-second. [symbols lost in extraction]
- gamma = 0.01 in paper-style units; must be rescaled with price/inventory units.
- kappa = 1.5 in the original numerical example; empirically fitted from log [truncated in extraction]
- Hummingbot-style public configs often use kappa starting values, then calibrate.

Sources: Avellaneda & Stoikov (2008).

### Worked numerical example

Illustrative parameters (not estimated): Kalman R = 1, Q = 0.25. PCA: full 9-return window, K = 1 factor.

**A. Ten synthetic prices — first 3 Kalman updates by hand**

y = [100.0, 100.8, 99.6, 101.2, 100.4, 102.0, 101.1, 103.0, 102.2, 104.1]

Initialize prior for mu_{1|0} = 100.0, P_{1|0} = 1.0.

Step 1: v_1 = 0, F_1 = 2.0, K_1 = 0.5, mu_{1|1} = 100.0, P_{1|1} = 0.5. Next prior: P_{2|1} = 0.75.

Step 2: v_2 = 0.8, F_2 = 1.75, K_2 = 0.428571, mu_{2|2} = 100.342857, P_{2|2} = 0.428571. Next prior: P_{3|2} = 0.678571.

Step 3: v_3 = −0.742857, F_3 = 1.678571, K_3 = 0.404255, mu_{3|3} = 100.042553, P_{3|3} = 0.404255.

Filtered fair values after 1, 2, 3 observations: 100.000, 100.343, 100.043 (3 d.p.).

**B. 3-asset, 10-day panel — first-PC residual for asset 1**

Prices:
| day | A | B | C |
| 1 | 100.0 | 50.0 | 80.0 |
| 2 | 101.0 | 50.4 | 80.6 |
| 3 | 102.2 | 51.0 | 81.5 |
| 4 | 101.5 | 50.2 | 80.8 |
| 5 | 103.0 | 51.5 | 82.4 |
| 6 | 104.1 | 51.8 | 83.0 |
| 7 | 103.4 | 51.1 | 82.2 |
| 8 | 105.0 | 52.4 | 83.9 |
| 9 | 106.2 | 52.8 | 84.6 |
| 10 | 105.5 | 52.0 | 83.8 |

Simple returns (9 rows). Sample means and s.d. (ddof=1):
A: mean 0.006009, sd 0.009710
B: mean 0.004483, sd 0.016175
C: mean 0.005232, sd 0.011901

Correlation of standardized returns:
( 1 0.9574 0.9697; 0.9574 1 0.9968; 0.9697 0.9968 1 )

Leading eigenvalue lambda_1 = 2.949; eigenvector (sign flipped so first loading > 0): v_1 = (0.57293, 0.57835, 0.58074). PC1 scores s_{1,t} = sum_i v_i X_{t,i}. Asset-A residual in return space eps_{t,A} = sigma_A (X_{t,A} − v_{1,A} s_{1,t}), last day (return from day 9→10): −0.000571. Full residual series for A (return space): (0.00137, 0.00086, −0.00087, −0.00232, 0.00231, −0.00094, −0.00200, 0.00217, −0.00057).

Interpretation: after stripping the common eigenfactor, A's last move is a small negative idiosyncratic residual — the reversal signal would be a modest long if one traded the residual (illustrative only).

Source list. Kalman local level: Durbin–Koopman; Harvey. PCA residual: Avellaneda & Lee (2010). Trade–quote VAR: Hasbrouck (1991) JF. Fracdiff FFD: Lopez de Prado (2018) Ch. 5. Reservation/spread: Avellaneda & Stoikov (2008). All numerical values, windows, and the 10-price panel are worked illustrations, not fitted market estimates.

---

## Q-SB9-2 — local build + buy vs build (verbatim)

All numbers below are order-of-magnitude engineering estimates for a 128 GB M5 Max (40-core GPU, ~614 GB/s unified bandwidth, ~20 TFLOPS FP32 / much higher FP16 via GPU Neural Accelerators). They assume one engineer who already knows Python/NumPy and is competent at quant, not a first-time ML hire. "Hours" are focused build hours, not calendar time.

Hardware context: 128 GB unified memory is the binding constraint for panels and LOB tensors; compute is not the binding constraint for (a)(b)(d)(e). It is the constraint for serious DeepLOB-scale research (many symbols x years of L2), not for a single-name DeepLOB replica.

### Snapshot verdict

- (a) Kalman/HMM/ARMA 1-min library: Build. Buy only if you want a vendor risk system. Deep vs trees: N/A.
- (b) Rolling PCA 500x252: Build. Buy risk models (Barra/Axioma) only if you need production factors.
- (c) DeepLOB-style: Prototype only. Don't buy a "DeepLOB SaaS". Trees + features first.
- (d) Fracdiff preprocess: Build (afternoon). Don't buy.
- (e) A–S tick loop: Build the simulator; don't build a live matcher. Buy OMS/SOR if you go live.

Deep learning is not worth it as the first production signal on this box. Documented FI-2010-style tables show XGBoost already in the 60s F1 while DeepLOB/CTABL/BiN-CTABL win the academic leaderboard; those gains collapse or become non-tradable on real NASDAQ/LOBSTER books once costs, queue position, and non-stationarity are included. Build DeepLOB as a research probe, not as the quoting brain.

### (1) Data needs and indicative pricing

Assumptions: 500 US names, ~6.5h x 252d.

Bars (a, b, d):
- 1-min OHLCV, 500 names, 5 years: ~500 x 252 x 5 x 390 ≈ 2.5x10^8 bars. Packed float64 OHLCV+vol ≈ 15–25 GB. Parquet/zstd often 3–8 GB. Polygon Stocks Starter ~$200–400/mo; Databento equity OHLCV historical is cheap relative to L2 (often low hundreds to low thousands one-off for years of 1-min, schema-dependent). Norgate / FirstRate / Kibot cheaper, dirtier.
- Corporate actions / point-in-time universe: mandatory for PCA. Included in decent vendors; budget $1–3k/yr if separate.

You do not need L2 for (a)(b)(d).

L2 / MBO for DeepLOB and A–S. DeepLOB input is typically a tensor T x 40 (10 levels x bid/ask price+size) per event or per subsampled snapshot.
- L2 snapshots, 10 levels, 100 ms, 500 names, 1 year: order 5–20 TB compressed if you keep all names all day; 200–800 GB if you keep 20 liquid names + event-time windows around trades. Databento MBP-10 / MBO: real-time often $199–several hundred / month / dataset plus historical egress; a year of full-depth US equities for 500 names is commonly low-to-mid five figures if you pull MBO, not bars. Exact quote is usage-metered.
- LOBSTER-style event books, 5–20 mega-caps, 1–2 years: 50–300 GB. Academic LOBSTER is cheap per ticker-day; commercial rebuild via Databento MBO is the practical path.
- SIP vs exchange proprietary: SIP is not enough for a serious LOB model. NYSE Integrated / Nasdaq ITCH historical: institutional, often $10k–$50k+/yr per feed family.

Practical data budget for this project:
- Research-only (1-min + 20-name L2): $2k–$8k year 1.
- Ambition (500-name L2 + live): $20k–$80k year 1 plus exchange agreements.
- Live A–S in production also needs colocation or a sponsored DMA, which dwarfs Mac cost.

Databento's public list starts around $199/mo for many datasets; depth and symbol-count drive the real bill.

### (2) Training time and inference latency on M5 Max

M5 Max: 40 GPU cores + per-core Neural Accelerators, 128 GB unified, 614 GB/s. FP32 peak ~20 TFLOPS; AI matmul is severalx that in FP16. MLX/PyTorch MPS are the right stacks; CUDA kernels will not run.

(c) DeepLOB-class model. Canonical DeepLOB is small: ~1.4x10^5 parameters, input 100 x 40, CNN + Inception + LSTM. Published GPU inference ~1.3 ms/sample (server GPU, batch-ish).

- Train FI-2010-sized set (~400k windows): 15–45 min / epoch in MLX or PyTorch-MPS; 2–6 hours to a usable checkpoint (early stop).
- Train 1 liquid name, 1 year, event-time, ~5–20M windows: 8–30 hours wall, mixed precision, if you stream from SSD and don't materialize all tensors.
- Train 20 names x 1 year: 1–2 weeks nights-and-weekends on this Mac, or rent an A100/H100 for $50–300 and finish in hours. [no unit given — presumably $/hour or $/run]
- Train 500 names x years of L2: wrong machine. Data I/O and epoch time dominate; use a GPU box or don't.
- Inference, batch=1, compiled MLX/Core ML: 0.3–2 ms per forward on GPU; 1–5 ms on CPU. Model is tiny vs memory bandwidth.
- Inference, batch=64–256 (research): well under 1 ms/sample amortized.
- End-to-end "feature build + predict" in a tick loop: 50–500 us is not achievable if you rebuild a 100-step book tensor from a Python object each event. Plan 0.5–5 ms in Python; 50–200 us only after a C++/Rust book + preallocated tensor.

DeepLOB is not an LLM. Do not use LLM tok/s numbers. The M5 Max Neural Accelerators help CNN/LSTM matmuls, but the model is so small that Python and book-building dominate, not FLOPs.

(a)(b)(d)(e) — no "training" in the DL sense:
- Kalman 500 symbols x 390 bars/day: milliseconds per day, CPU.
- Rolling PCA 500x252, one eigen-decomp: 10–80 ms with np.linalg.eigh on 500x500; 252 daily rolls ≈ 2–20 s. Intraday 1-min rolls on 500 names: minutes per day if naive; seconds if you use incremental PCA / rank-1 updates.
- Fracdiff 500 x 2.5e8 bars [see QC note — this contradicts the earlier 2.5x10^8 total], window ~50–200: a few minutes to ~1 hour vectorized NumPy; one-time.
- A–S closed form per tick: tens of nanoseconds of arithmetic; the loop cost is book I/O.

### (3) RAM for panels and LOB tensors

128 GB is comfortable for (a)(b)(d) and tight only if you are sloppy with L2.

- 500 x 252 return panel: 500 x 252 x 8 bytes ≈ 1 MB. Laughably small.
- 500 x 5y x 1-min returns: 500 x 252 x 5 x 390 x 8 ≈ 2 GB.
- Same with 30 features: ~60 GB if dense float64; 15–25 GB float32 + sparse. Fits.
- Kalman state 500 names: tiny, <10 MB.
- Fracdiff weights + rolling buffer: <1 GB.
- DeepLOB batch tensor B x 100 x 40 x 4: batch 1024 ≈ 16 MB. Irrelevant.
- Danger: 500 names x 10 levels x 100 ms x 1 session, float32 prices+sizes: 500 x 234000 x 40 x 8 ≈ 37 GB/day raw; a week in RAM will OOM. Stream by date/symbol. [label says float32 but formula uses x8 bytes — preserved verbatim, see QC note]
- Event-time reconstructed book, 20 names, 1 day: 1–8 GB depending on tick density.
- Live A–S: one book + inventory + quotes: <100 MB.

Rule: keep the 500-name panel in RAM; never keep 500-name L2 history in RAM. 128 GB is the right size for a multi-model research workstation, not a 500-name MBO data lake.

### (4) Engineering hours per component

One strong quant-dev, including tests and a small dashboard. Not including exchange legal or a production OMS.

- (a) Kalman/HMM/ARMA on 1-min, 500 names: 40–80 h v0 (correct, local, tested; Statsmodels + custom Kalman; HMM is the long pole). 120–200 h v1 (regime diagnostics, missing bars, corporate actions, parameter grids).
- (b) Rolling PCA / eigenportfolio / residual OU / s-score: 30–60 h v0 (Avellaneda–Lee clone on daily bars). 100–180 h v1 (1-min, universe PIT, shrinkage, Marchenko–Pastur cutoff, borrow/adv filters).
- (c) DeepLOB train + infer: 80–150 h v0 (reproduce FI-2010 + one real name end-to-end on MLX/PyTorch). 300–600 h v1 (normalization, leakage, costs, walk-forward, multi-name). Do not budget "production alpha" hours.
- (d) Fixed-window fracdiff: 4–12 h v0 (Lopez de Prado snippet + Parquet pipeline). 20–40 h v1 (wired into every feature store with ADF-d search).
- (e) A–S engine, sim tick loop: 40–80 h v0 (closed-form + synthetic mid + fill model). 200–400 h v1 (research backtester with queue, latency, adverse selection). Live quoting: 1–2+ engineer-years plus legal/infra — not a Mac project.
- Glue: data lake, calendar, eval harness: 80–150 h.

Total to a serious local research stack (a+b+d + A–S sim + DeepLOB prototype): ~400–700 hours (3–5 months part-time, ~2 months full-time). Total to anything you would wire to a live order: add a year and a broker stack.

### (5) Buy vs build, and deep net vs gradient-boosted trees

Buy vs build:
- 1-min data: Buy. Commodity. Building a tape is waste.
- L2/MBO: Buy (Databento / exchange). Reconstructing ITCH yourself is a product.
- Kalman/ARMA/HMM: Build. 200 lines + tests. No vendor is worth the contract.
- PCA residual engine: Build for research. Buy Barra/Axioma/Northfield only if you need a risk model others accept. 500x252 is a homework problem.
- Fracdiff: Build. Don't pay for a filter.
- DeepLOB weights: Build a small one or skip. Don't buy "AI alpha API." Edge, if any, dies in transfer. Prata et al. show SOTA LOB nets overfit FI-2010 and drop on LOBSTER. Briola et al. (2025) Quant. Finance: high forecast metrics != actionable fills.
- A–S formulas: Build. Closed form is one screen.
- Live matching / risk / kill-switch: Buy broker + EMS. Building this on a laptop is how accounts die.

DeepLOB vs gradient-boosted trees on handcrafted features — documented picture, not folklore:
- On FI-2010, XGBoost F1 at short horizons is about 62 / 60 / 65 / 68 (h = 10, 20, 50, 100). DeepLOB is about 71 / 62 / 75 / 78. BiN-CTABL and newer nets go higher still. So on the toy benchmark, deep wins.
- Same papers' inference: XGBoost/MLP << 1 ms; DeepLOB ~1.3 ms; still fine on M5 Max. Latency is not the argument.
- On real names (TSLA/INTC-style tables in TLOB 2025), DeepLOB F1 can fall to the mid-30s on Tesla — near noise after costs. Transfer is the actual problem.
- Briola, Bartolucci, Aste (2025): microstructural heterogeneity drives whether DL works at all; standard ML metrics overstate tradable edge.

What to do on this Mac:
1. Handcraft: mid-return, imbalance, microprice, OFI, spread, Kalman fair residual, PC1 residual, fracdiff features, roll/depth.
2. Fit LightGBM/XGBoost with purged CV (Lopez de Prado). Hours of train time, inspectable, easy to kill.
3. Use DeepLOB only as a second opinion on 5–20 names where the book is thick and you already have L2.
4. Put A–S around inventory + a slow fair value (Kalman / microprice), not around a 100-step CNN. That split matches the hardware: M5 Max is excellent at wide panels, rolling linear algebra, and small-net inference; it is a poor substitute for a multi-GPU LOB research cluster and a worse substitute for a colocated quoting stack.

Cost roll-up (year 1, research only):
- Machine (already owned): $0.
- 1-min + reference data: $2k–$6k.
- Limited L2 (10–20 names): $2k–$15k.
- Engineer time @ $150–250/h blended, 500 h: $75k–$125k.
- Cloud GPU burst for DL sweeps: $100–$1k.
- Total: ~$80k–$150k.

Live market-making on top of (e) is a different business (colocation, capital, registration), not a line item on the Mac.

If you only do one thing this quarter: build (a)+(b)+(d) on bought 1-min data, add an A–S simulator, and a LightGBM on those features. Park DeepLOB until L2 for a short name list is paid for and the tree model has a walk-forward that survives costs.

---

## Q-SB9-3 — success ratios, after-cost efficacy, failure modes (verbatim)

After-cost honesty first: none of these five objects is a turnkey P&L engine. Two are measurement tools (DeepLOB-class classifiers, Hasbrouck IS). Two are risk premia with a crash signature (PCA residuals after 2003, short-correlation dispersion). One is a quoting policy, not an alpha (Avellaneda–Stoikov). Where papers report Sharpe or accuracy, I flag what was and was not after costs.

### (1) DeepLOB and successors — accuracy vs tradable P&L

What the original paper documents. Zhang, Zohren & Roberts (IEEE TSP 2019 / arXiv 1808.03668) train a CNN–Inception–LSTM on FI-2010 and report stable out-of-sample accuracy, including transfer to names not in the training set: later multi-horizon follow-up (Zhang, Zohren …) reports 65% / 62% / 59% accuracy at horizons [page shows "50 100 events" with likely lost labels — see QC note] for DeepLOB, with Seq2Seq/Attention a point or two higher. That is directional classification of mid-price labels, not fills.

The academic leaderboard is real and narrow. On FI-2010, published F1 is roughly:
- XGBoost (handcrafted / raw-ish features): ~60–68%
- DeepLOB (2019) (CNN+LSTM): ~71–78% depending on h and split
- C(TABL) / BiN-CTABL / later nets (attention / bilinear): often above DeepLOB on FI-2010

So trees are not "close enough to ignore" on the toy set — deep nets win the benchmark — but the gap is single-digit F1, not a different sport.

The honest gap to money.
1. Label != trade. Mid-move labels ignore that you buy the ask and sell the bid. A 60–70% mid classifier can have negative expectancy after half-spread if the predicted move is smaller than the spread plus fee.
2. FI-2010 does not reconstruct a live book. It is pre-normalized, pre-labelled Nordic data. You cannot compute queue position, cancel/replace, or [truncated in extraction].
3. Transfer collapses. Prata et al. (2024, Artificial Intelligence Review): models that look robust on FI-2010 show a sharp drop on unseen LOBSTER/NASDAQ books. TLOB (2025) reports DeepLOB F1 on Tesla in the mid-30s on some horizons — near a 3-class coin flip after costs.
4. Forecast metric != fill. Briola, Bartolucci & Aste (Quantitative Finance 2025): high classification scores do not imply complete-transaction forecasts; stock microstructure (tick, spread, queue) dominates whether a "correct" mid call is cashable.
5. Papers that run a book sim often omit maker/taker fees, queue priority, and adverse selection, or they use Chine[se — truncated in extraction] … a transferable Sharpe.

After-cost takeaway. Treat DeepLOB-class accuracy as evidence that the book has short-horizon structure, not as an edge size. A small-account implementation that crosses the spread on every signal should [expect] zero or negative net P&L until a fill-level backtest with fees, latency, and walk-forward on your names says otherwise. Trees on OFI/imbalance/microprice are the correct first production model; deep [LOB is a research probe — truncated in extraction].

### (2) PCA residual reversal — documented returns and crowding

The canonical result. Avellaneda & Lee, 10(7), 2010: PCA or ETF residuals, OU/s-score, market-neutral, [profitable] after their transaction-cost assumption.
- PCA, 1997–2007: average annual Sharpe 1.44
- 2003–2007 only: Sharpe 0.9
- ETF residuals, 1997–2007: Sharpe 1.1
- ETF + volume, 2003–2007: Sharpe 1.51 (their best late-sample variant)
They explicitly flag degradation after ~2002–03 and study August 2007 in the Khandani–Lo "quant unwind" setting.

What that Sharpe includes and excludes. Costs in the paper are a stylized friction, not 2026 US agency + borrow + impact on a 500-name daily [book — truncated in extraction].

Crowding is the documented sequel, not a rumor. Khandani & Lo (2007/2011) document the August 2007 quant-equity liquidation: many market-neutral boo[ks — truncated] long residual-cheap / short residual-rich unwound together. Correlation of supposedly idiosyncratic books went to 1 for a few days. That is th[e canonical crowding example — truncated]. Capacity and crowding ate the easy Sharpe. A 2026 replica of A&L on liquid US names, after 5–10 bp round-trip and borrow, should be planned a[t] Sharpe 0–0.8 in calm years, with a left tail when residual books are crowded — not Sharpe 1.44.

After-cost takeaway. The residual [is] a real, slow statistical object. The published Sharpe is a historical artifact of a less-crowded book. Size it as a diversifier with kill-switches on residual-correlation spikes, not as a compounding e[ngine — truncated].

### (3) Dispersion trading — edge, capital, 2008-style correlation break

Economic identity (after Bossu / Jacquier–Slaoui). A variance-dispersion that is short index variance and long a basket of single-stock variance has P&L proportional to (rho_implied − rho_realized) x (avg single-stock variance). You are short correlation. Implied correlation has historically sat ~8–15 correlation points above subsequent realized (Jacquier–Slaoui note ~10 points vs a correlation-swap strike). That gap i[s a] risk premium, not a free lunch: dealers and structured-product books are structurally short the crash-correlatio[n — truncated].

Documented backtest shape. A rules-based short-SPX-vol / long-single-name-vol construction over 2006–2025 (pre-cost) in one lon[g sample] [returned] ~4.8% annualized, Sharpe ~0.62, max DD ~28%. Calm windows look good (2012–19 Sharpe ~1.3); 2008, Mar-2020, 2022 dominate the left tail. In 2008 implied correlation exploding from ~0.45 toward 0.80+ is the textbook break; that reconstruction marks about a 19% strategy loss in 2008. S&P DJI's dispersion–correlation map makes the same qualitative point: 2000–02 was high [dispersion] / modest correlation (stock-pickers survived); 2008 was high correlation — everything fell together, short-corr books died.

Capital intensity. You need margin on short index var / short index options plus long 50–500 single-name options or varswaps. Post-2008, single-name variance-swap liquidity collapsed (Bossu); many books moved to listed options and live with gap risk, pin, and borrow on hard names. A multi-million notional options book, not a Mac strategy.

After-cost takeaway. Expect a modest, negatively skewed premium if you can warehouse crash-correlation. After bid–ask on single-name options, roll, and vega-hedge f[ees], something like 0.2–0.5 [Sharpe] for a non-dealer, with one or two career-risk years per decade. Size to the 2008 / Mar-2020 path, not to the 2012–19 Sharpe.

### (4) Avellaneda–Stoikov — documented "performance" vs inventory reality

What the 2008 paper is. [A] stochastic-control quoting rule under exponential utility, Poisson fills, arithmetic Brownian mid. It is not an empirical alpha pape[r — truncated].

What later work actually shows.
- Simulations / synthetic mids: inventory-aware quotes cut terminal-wealth variance and inventory excursions versus a symmetric fixe[d spread — truncated] of […]. Gueant–Lehalle–Fernandez-Tapia and follow-ons formalize inventory penalties; Fodra–Labadie-type nu[merical schemes — truncated] trade mean P&L for a much tighter inventory law.
- On real tapes the formula is not magic. A BTC L2 study that wraps RL around A–S (PLOS One 2022) finds vanilla A–S already better than dumb b[aseline — truncated] … better still — with a few violent inventory drawdowns still present. An hourly BTCUSDT perpetual study reports plain A–S losing ~29% annualized, Sharpe −2.6 on that sample: the closed form was misspecified for that horizon and fee schedule.
- Demo/H1 FX scripts that "beat fixed spread" are [not] evidence you can make a living; they show inventory skew reduces drift, which you already knew from [theory — truncated].

Small-account inventory reality (the part papers under-sell).
- A–S assumes you get filled at your quotes at intensity [lambda(delta) — truncated]. In a real book you are behind HFT queues. A $25–100k account on liquid US names is adverse-selected: you fill when the mid is about to run through you.
- Inventory of even 100–500 shares of a $200 name is a several-sigma mid move in dollars. The reservation-price skew only helps if you trade out [of it — truncated]. On a 1-lot account, one missed flatten into the close is the day.
- Maker rebates on US equities are often ~0.1–0.3c/share; taker fees and SEC fee when you lift to flatten erase days of spread capture.
- Without colocation, your [fill-rate] estimates are fine; your queue position is not. [truncated]

After-cost takeaway. A–S is a risk scheduler, not a return source. On a small account it is useful as a skew + inventory cap + end-of-day flatten overlay around a separately estimated fair value. Do not expect the paper's indifference-price math to pay the rent. If inventory variance [exceeds your capital — truncated].

### (5) Hasbrouck information share — what it measures, what it is not

What it documents. Hasbrouck (1995) Journal of Finance: in a VECM of cointegrated venue prices, the [information share] of venue [j] is the fraction of the efficient-price innovation variance attributable to that venue's residuals (C[holeski — truncated] bounds, not a point). Empirically: the venue that prints first / has tighter quotes usually owns a large I[S — truncated]. RFS companion: trades explain a larger share of efficient-price variance in small caps; opening prints are more informative in absolute variance, slightly less in relative terms.

Documented limits (why it is not a signal).
1. Bounds can be huge. At coarse clocks IS is nearly unidentified; at one-second resolution bounds can span most of [0,1] ([…] [truncated]).
2. IS mixes leadership and noise. Putnins (J. Empirical Finance 2013): if venues differ in microstructure noise, Hasbrouck IS and Harris–McInish–Wood component shar[es — truncated] confound "who is first" with "who is less noisy." Information-leadership share is the patch; raw IS is not "alpha of venue A."
3. It is an attribution of past innovations, estimated on a trailing VECM. It does not forecast the next mid. A venue with IS 0.7 can still be stale on the next event.
4. Clock and lag choice change the ranking. Sub-millisecond data need restricted VECMs; different lag structure rearranges shares.
5. Related Hasbrouck–Saar work on fleeting orders is a warning: much of the displayed book is cancelled in seconds. IS on quotes is not IS on tradable depth.

After-cost takeaway. Use IS to choose where to listen (which feed is informative for a given name) and to sanity-check a cointegrated pair. Do not convert an IS of 0.65 into a trade. There is no after-cost Sharpe in the [measure — truncated]; it was never a strategy.

Cross-cut: what survives a cost ledger:
- DeepLOB-class mid classifier: Documented "win" = 60–85% accuracy on FI-2010; ~60–70% transfer on LSE in-paper. After-cost, small book = usually not tradable; transfer and spread eat it.
- PCA residual reversal: Documented "win" = Sharpe 1.44 (1997–07, paper costs); 0.9 after 2003. After-cost, small book = crowded; plan Sharpe << 1, August-2007 tail.
- Dispersion / short corr: Documented "win" = implied–realized corr gap ~0.10; long-run +Sharpe ~0.6 pre-cost. After-cost, small book = capital-heavy, crash-skewed; 2008 is the design case.
- A–S quotes: Documented "win" = lower inventory variance in sims. After-cost, small book = risk tool; adverse selection dominates small accounts.
- Hasbrouck IS: Documented "win" = venue A explains X% of efficient variance. After-cost, small book = diagnostic only.

If the filter is "would I fund this with a five-figure account after fees," the only items that can [be] implemented are a slow residual book with tight risk and an A–S-style inventory overlay. The rest is either a measurement (IS, DeepLOB accuracy) or a balance-sheet premium (dispersion) that does not fit a 128 GB workstation and a cash account.

---

## QC notes (orchestrator)

1. Q-SB9-1 worked example: the 3 Kalman steps are arithmetically consistent (K_1 = 0.5 → mu = 100.0; K_2 = 0.428571 → mu = 100.342857; K_3 = 0.404255 → mu = 100.042553). PCA first-PC residual for asset 1's last day ≈ −0.000571, matching Grok's series. Eigenvector norm ≈ 1.0001. No arithmetic errors found in the worked example.
2. Q-SB9-1 (5): the total-spread formula renders as "delta_a + delta_b = gamma sigma^2 (T−t) + 2/gamma ln(1 + gamma/kappa)" — the original paper's closed form is 2/gamma ln(1 + gamma/kappa); the browser task flagged a likely missing "/" glyph in the render. Preserved verbatim.
3. Q-SB9-1 (1) practical-ranges: one bullet contains a garbled repeated fragment (extraction artifact); several bullets lost leading parameter symbols in math extraction.
4. Q-SB9-1 (4): the "Weight floor tau" bullet shows no numeric value in the extracted text (extraction gap).
5. Q-SB9-1 (4): Grok states "d = 1 is the raw series" — the standard mapping is d = 0 recovers the original series and d = 1 gives first differences. Preserved verbatim; possible Grok error or truncation.
6. Q-SB9-2 inconsistency: "Fracdiff 500 x 2.5e8 bars" contradicts the earlier "≈2.5x10^8 bars" total for 500 names x 5 years of 1-min data (the x500 factor appears double-counted).
7. Q-SB9-2: "rent an A100/H100 for $50–300" has no unit (presumably $/hour or $/run).
8. Q-SB9-2 RAM table "Danger" row: labeled float32 but the formula uses x8 bytes (500x234000x40x8 ≈ 37 GB/day); x8 is what produces the stated ~37 GB/day, so the "float32" label is inconsistent.
9. Q-SB9-3 (1): "reports 65% / 62% / 59% accuracy at horizons 50 100 events" — three accuracies against two visible horizon labels; pairing is garbled (likely lost "h =" labels).
10. Key sourced claims are research leads, not verified facts: A&L 2010 (PCA Sharpe 1.44 1997–2007, 0.9 after 2003); Khandani–Lo 2007/2011 (August 2007 quant unwind); Prata et al. 2024 (DeepLOB transfer drop); Briola–Bartolucci–Aste 2025 (forecast metrics != actionable fills); Popovici 2026 style (see SB8); Soebhag 2023 (see SB8). Vendor prices: indicative — verify before budgeting.

---

## Source list (only papers actually used)

- Durbin, J. and Koopman, S.J., Time Series Analysis by State Space Methods.
- Harvey, A.C. (1989), Forecasting, Structural Time Series Models and the Kalman Filter.
- Avellaneda, M. and Lee, J.-H. (2010), "Statistical Arbitrage in the U.S. Equities Market."
- Hasbrouck, J. (1991), "Measuring the Information Content of Stock Trades," Journal of Finance 46.
- Hasbrouck, J. (1995), "One Security, Many Markets," Journal of Finance.
- Lopez de Prado, M. (2018), Advances in Financial Machine Learning, Ch. 5.
- Hosking, J.R.M. (1981), "Fractional Differencing."
- Avellaneda, M. and Stoikov, S. (2008), "High-frequency trading in a limit order book," Quant. Finance 8.
- Zhang, Z., Zohren, S. and Roberts, S. (2019), "DeepLOB: Deep Convolutional Neural Networks for Limit Order Books."
- Prata, M. et al. (2024), Artificial Intelligence Review — LOB model transfer.
- Briola, A., Bartolucci, S. and Aste, T. (2025), Quantitative Finance — forecast metrics vs actionable fills.
- Khandani, A.E. and Lo, A.W. (2007/2011), "What Happened to the Quants in August 2007?"
- Everything not attributed to one of the above — parameter ranges, cost figures, worked-example values — is illustrative.
