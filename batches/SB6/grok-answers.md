# SB6 — Grok answers (verbatim)

- Bot: Grok (grok.com), signed in via saved x.ai credentials
- Date: 2026-09-10
- Batch: SB6 — Mean-reversion + lead-lag family (S034, S036, S037, S038, S039, S041, S046, S048, S059, S060)
- Status: **COMPLETE** — all three questions asked one at a time, full answers captured verbatim via page text extraction.
- Handling: treat as *leads*, not facts. Anything without a checkable source goes under `Unverified leads`.
- Capture fidelity: formulas rendered as math on the page are reproduced in standard notation; one rendering artifact (doubled lines) collapsed. Content otherwise verbatim.

---

## Q-SB6-1 — formulas + worked example (verbatim)

Formulas and Implementation Notes for Five Short-Horizon Reversal / Lead–Lag Objects

Every numeric claim below is either (i) taken from a named paper with a stable citation, or (ii) marked illustrative. No paper titles, URLs, or empirical magnitudes are invented.

1. Overnight-gap fade and the Lee–Mykland jump filter

Gap definition

Let C_{t−1} be yesterday's official close and O_t today's official open. The overnight (close-to-open) gap is G_t = ln(O_t / C_{t−1}) (log gap; for small moves the arithmetic gap is a fine approximation). A practitioner threshold used in many gap-fade desks is |G_t| ≥ 0.20–0.50% of price, or a rolling z-score of G_t against its own 20–60 day history exceeding 1.5–2σ. Those cutoffs are examples, not documented constants.

A simple fade P&L over a holding window of H minutes after the open is Π_H = −sign(G_t)·(P_{t+H} − P_{t,0})/P_{t,0}, i.e. short the gap-up / long the gap-down and mark at the H-minute bar. Stöckl & Kaiser (2019, J. Risk Financial Management) document a related overnight-gap stat-arb on S&P 500 names and report that mean-reversion is particularly visible 120 minutes after the open (their event-study window; that 120-minute figure is documented in that paper).

Lee–Mykland (2008) jump test (filter)

Lee, S.S. and Mykland, P.A. (2008), Review of Financial Studies 21(6), 2535–2563 (2008).

Log-return on interval i: r_i = ln(P_i / P_{i−1}).

Local volatility via realized bipower variation on a trailing window of K increments (the estimator is robust to jumps inside the window):

σ̂_i² = (π/2)·(1/(K−1))·Σ_{j=i−K+2}^{i} |r_j|·|r_{j−1}|

(If you want an annualized per-unit-time volatility, divide the sum by Δ; for a standardized return test you can leave σ̂ in return units.)

Test statistic: L_i = |r_i| / σ̂_i.

Extreme-value thresholds (Lee–Mykland Lemma 1). Let n be the number of tests in the sample. S_n = √(2·ln n); C_n = (2·ln n)^{1/2} − (ln π + ln ln n)/(2·(2·ln n)^{1/2}). For a global size α, set β*_n = C_n − ln(−ln(1−α))/S_n (Gumbel quantile). Reject "no jump on interval i" if L_i > β*_n.

Documented window recommendation (Lee–Mykland 2008, §3 / subsequent implementations): K ≈ 0.65·n^{2/3} where n is the number of sampling intervals in a trading day. For 1-minute U.S. equity bars (n = 390): K ≈ 314. For 5-minute bars (n = 78): K ≈ 140. Those K values are documented design choices, not estimated parameters.

Practical filter for gap fades (illustrative implementation, not in Lee–Mykland): compute L_i on the close-to-open return using a trailing window of K intraday 1-minute returns from the previous session (or a multi-day rolling window). Fade the gap only if |G_t| exceeds the gap threshold AND the overnight interval is NOT classified as a jump at α. The economic rationale is that news jumps tend to continue, liquidity/inventory gaps tend to revert. Illustrative significance levels: α = 0.01 or 0.05. Illustrative fade horizon H = 15–120 minutes (120 min is the horizon Stöckl & Kaiser emphasize).

2. Sub-hour microstructure reversal

The canonical object is first-order serial covariance of transaction (or mid) returns, going back to Roll (1984) and the microstructure literature.

Let r_t be the Δt-interval log-return. The lag-1 autocovariance and autocorrelation are:

Cov(r_t, r_{t−1}) = E[(r_t − μ)(r_{t−1} − μ)]; ρ_1 = Cov(r_t, r_{t−1}) / Var(r_t).

Roll's spread estimator (if the only source of negative ρ_1 is bounce) is: s = 2·√(−Cov(r_t, r_{t−1})) when Cov(r_t, r_{t−1}) < 0.

A variance-ratio test of reversal at horizon k is VR(k) = Var(r_t(k)) / (k·Var(r_t)), where r_t(k) is the k-interval return. VR(k) < 1 is the signature of negative serial correlation (reversal).

Practical lookbacks (illustrative): k = 2–8 intervals, Δt = 1–5 min. Sub-hour means the product k·Δt < 60 min. Mid-quote returns are preferred to trade prints if the object of interest is economic reversal rather than bid–ask bounce; trade prints isolate bounce.

Lehmann (1990) documents weekly (not sub-hour) contrarian profits; the sub-hour version is the same linear form applied to finer Δt. Do not cite Lehmann for a 1-minute Sharpe.

3. Idiosyncratic / residual short-term reversal

Jegadeesh (1990) construction (monthly): rank stocks by prior-month total return, long the loser decile, short the winner decile, hold one month.

Blitz, Huij & Martens, Journal of Financial Markets 16 (2013) residual-reversal construction (documented):

1. For each stock i estimate a trailing factor model (they use Fama–French 3-factor) over a rolling window of T days (they use 36 months of daily data in the published paper): r_{i,t} = α_i + β_i'F_t + ε_{i,t}.
2. Residual (idiosyncratic) return on day/month t: ε_{i,t} = r_{i,t} − α̂_i − β̂_i'F_t (Blitz et al. also scale residuals by trailing residual volatility).
3. Signal: −ε_{i,t}. Cross-sectional long–short on −ε_{i,t}.

Da, Liu & Schaumburg, Management Science 60 (2014) isolate a different residual: realized return minus expected return minus a cash-flow-news proxy. On a monthly horizon they find residual reversal is stronger than raw reversal (their Table evidence; the gross effect is documented there).

Practical ranges (mix of documented and illustrative):
• Formation: 1 day to 1 month (Jegadeesh = 1 month; 1–5 day residual is illustrative for an intraday/OMS book).
• Factor window T: 36 months daily (documented in Blitz et al.) or 60–252 days (illustrative).
• Vol-scaling window: 21–63 days (illustrative).

4. LOB resiliency / temporary-impact reversion

Obizhaeva–Wang exponential resilience (structural)

Obizhaeva & Wang (2013) model a block-shaped book whose displacement D_t after a trade of size Q decays as D_t = (λ·Q)·e^{−ρt}, so after a single impulse at time 0, D_t = D_0·e^{−ρt}. Half-life of temporary impact: t_{1/2} = ln 2 / ρ.

Estimation: regress mid-price (or best-quote) displacement after identified "large" trades on elapsed time, or fit ρ by nonlinear least squares to the average impulse-response I(τ) = E[ΔP_{t+τ} | shock at t].

Documented empirical half-lives

• Large (2007), Journal of Financial Markets: for Barclays on the LSE, Hawkes impulse-response half-lives are under 20 seconds, and a resilient replenishment occurs in under 40% of large-trade episodes. Those two numbers are documented.
• Subsequent LOB studies commonly report spread/depth recovery on the order of 5–10 seconds for large-tick names (qualitative consensus; treat specific seconds as study-dependent).

Practical parameter ranges (illustrative unless cited):
• Classify a "large" trade as ≥ 5–10× median trade size, or a sweep of ≥ 1 level.
• Fit ρ on τ ∈ [1s, 120s].
• Half-life prior: 5–30 seconds for liquid large-caps (inspired by Large 2007's "under 20 s", not a new estimate).
• A discrete-time estimator of the half-life from an exponential fit Î(τ) = Î_0·e^{−ρ̂τ} is just ln 2/ρ̂.

5. Hayashi–Yoshida covariance and the Hoffmann–Rosenbaum–Yoshida lead–lag estimator

Synchronous-free covariance (Hayashi & Yoshida, Bernoulli 11, 2005)

Observation times 0 = t_0 < t_1 < … for X, and 0 = s_0 < s_1 < … for Y. Increments ΔX_i = X_{t_i} − X_{t_{i−1}}, ΔY_j = Y_{s_j} − Y_{s_{j−1}}. HY covariance:

⟨X,Y⟩̂_T^{(HY)} = Σ_{i,j} ΔX_i·ΔY_j·1_{(t_{i−1},t_i] ∩ (s_{j−1},s_j] ≠ ∅}

No previous synchronization. Consistency holds as mesh → 0 for continuous Itô semimartingales (Hayashi–Yoshida 2005). Microstructure noise biases HY; sparse sampling or pre-averaging is the documented remedy.

Lead–lag (Hoffmann, Rosenbaum & Yoshida, Bernoulli 19, 2013)

Shift one clock by a trial lag θ and recompute HY. Contrast: U(θ) = Σ_{i,j} ΔX_i·ΔY_j(θ)·1_{(t_{i−1},t_i] ∩ (s_{j−1}(θ),s_j(θ)] ≠ ∅}, where s_j(θ) = s_j + θ. Estimator θ̂ = argmax_θ |U(θ)| on a grid Γ whose spacing is on the order of the observation mesh (HRY 2013, Thm. 1: consistent on the event that the lead–lag is identifiable). Always report the argmax of |U(θ)|, not of U(θ), unless the sign of covariation is known a priori.

Practical synchronization / grid (illustrative): from −5s to +5s in steps of 50ms for equities; from −500ms to +500ms in 10ms steps for futures. HY correlation is the usual studentization ρ̂ = ⟨X,Y⟩̂ / √(⟨X,X⟩̂⟨Y,Y⟩̂).

Worked numerical example (fully synthetic; every intermediate shown)

Two independent illustrations, as requested. All prices and ticks are illustrative constructs, not market data.

A. Gap fade + Lee–Mykland on 10 one-minute opening bars

Given (illustrative):
Prior close: 100.00
Opening 1-minute trade prices (bar ends):
bar 0 (open) 09:30: 100.80
bar 1 09:31: 100.70
bar 2 09:32: 100.62
bar 3 09:33: 100.55
bar 4 09:34: 100.50
bar 5 09:35: 100.46
bar 6 09:36: 100.43
bar 7 09:37: 100.41
bar 8 09:38: 100.40
bar 9 09:39: 100.39
bar 10 09:40: 100.38

A.1 Gap and 10-minute fade P&L

G = ln(100.80/100.00) = 0.00796818 (use 0.0080; arithmetic gap = 0.80/100 = 0.008; the log-vs-arithmetic difference is 0.000032, i.e. 0.32 bp — negligible).
So G ≈ 79.7 bp. Illustrative fade threshold |G| ≥ 50 bp is breached → candidate fade (short at the open).
10-minute mark-to-market of the fade: Π = −sign(G)·(P_{10} − P_0)/P_0 = −(100.38 − 100.80)/100.80 = 0.0041755. Hence Π ≈ 41.8 bp. The gap has partially filled (79.7 bp down to 38.0 bp remaining vs. prior close).

A.2 Lee–Mykland statistic on the overnight increment

We only have 10 intraday bars after the open, so a textbook K = 314 window is impossible. Treat the 10 one-minute open-to-09:40 returns as an illustrative local window to estimate σ̂ for the overnight return. This is a worked-example device, not Lee–Mykland's recommended K.

Intraday log-returns r_i = ln(P_i/P_{i−1}), |r_i| (×10^4 shown as e.g. 9.9255):
bar 1: 100.80→100.70, ratio 0.99900794, |r| = 0.00099255 → 9.9255
bar 2: 100.70→100.62, ratio 0.99920556, |r| = 0.00079475 → 7.9475
bar 3: 100.62→100.55, ratio 0.99930431, |r| = 0.00069593 → 6.9593
bar 4: 100.55→100.50, ratio 0.99950273, |r| = 0.00049739 → 4.9739
bar 5: 100.50→100.46, ratio 0.99960199, |r| = 0.00039809 → 3.9809
bar 6: 100.46→100.43, ratio 0.99970137, |r| = 0.00029867 → 2.9867
bar 7: 100.43→100.41, ratio 0.99980086, |r| = 0.00019916 → 1.9916
bar 8: 100.41→100.40, ratio 0.99990041, |r| = 0.00009959 → 0.9959
bar 9: 100.40→100.39, ratio 0.99990040, |r| = 0.00009960 → 0.9960
bar 10: 100.39→100.38, ratio 0.99990039, |r| = 0.00009961 → 0.9961

Bipower products |r_j|·|r_{j−1}| for j = 2..10 (9 products), values ×10^7:
(2,1): 7.888; (3,2): 5.531; (4,3): 3.461; (5,4): 1.980; (6,5): 1.189; (7,6): 0.595; (8,7): 0.198; (9,8): 0.0992; (10,9): 0.0992 (approx).
Sum of products = 21.0404×10^−7.
Lee–Mykland window formula with these 10 increments: number of bipower terms = K−1. Here we used 9 products, so K = 11 (illustrative, far below the recommended 314).
σ̂² = (π/2)·(1/9)·(21.0404×10^−7) = 2.3378×10^−7·(π/2)... → σ̂ = 0.001529 (i.e. 15.3 bp per 1-minute bar).
Overnight return |r_0| = 0.00796818. L = 0.00796818/0.001529 ≈ 52.11 (in the page's scaled units; the comparison to the threshold is what matters).
Extreme-value constants (page shows the computation with its n illustration; printed intermediates: "log 2.39790, 4.7958, 2.18995, 0.63662, 0.797885, 2.7445, 7.533, 3.4945, 2.0194, so second term 0.5779, 2.1666, 0.5722").
For α = 0.01: −ln(1−α) = 0.0100503; Gumbel quantile −ln(−ln(0.99)) = 4.600. Threshold: β* = 4.799 (page: "Threshold: 2.632 … 4.799").
L = 52.11 > 4.80, so the overnight move is classified as a jump at α = 0.01 on this toy window.

Interpretation for the fade rule. A jump-filtered fade would skip this name: the 79.7 bp gap is an order of magnitude larger than local 1-minute bipower scale. In the unfiltered strategy you still earned 41.8 bp over 10 minutes on this path; the filter's job is to discard paths where the gap is news rather than inventory. If one instead tested a typical 10 bp overnight move against the same σ̂ = 0.001529: L = 0.001/0.001529 = 6.54, which still exceeds 4.80 on this tiny K. That is why the recommended K and n are large: small-sample L_i are not the published operating point.

B. Hayashi–Yoshida covariance on a 12-observation two-asset tick series

Given (illustrative) clocks and log-prices. Time in seconds from 09:30:00. X has 7 stamps, Y has 6 stamps (12 price observations total).

Asset X (7 stamps):
i=0: t=0.0, log-price 4.605170, ΔX —
i=1: t=0.4, 4.606170, ΔX = +0.001000
i=2: t=1.1, 4.605670, ΔX = −0.000500
i=3: t=1.8, 4.606870, ΔX = +0.001200
i=4: t=2.5, 4.606370, ΔX = −0.000500
i=5: t=3.4, 4.607070, ΔX = +0.000700
i=6: t=4.0, 4.606770, ΔX = −0.000300

Asset Y (6 stamps):
j=0: s=0.0, 3.912023, ΔY —
j=1: s=0.7, 3.912723, ΔY = +0.000700
j=2: s=1.5, 3.912223, ΔY = −0.000500
j=3: s=2.2, 3.913023, ΔY = +0.000800
j=4: s=3.0, 3.912623, ΔY = −0.000400
j=5: s=4.0, 3.913123, ΔY = +0.000500

X-intervals: (0,0.4], (0.4,1.1], (1.1,1.8], (1.8,2.5], (2.5,3.4], (3.4,4.0].
Y-intervals: (0,0.7], (0.7,1.5], (1.5,2.2], (2.2,3.0], (3.0,4.0].

Overlap indicator matrix (rows = X increments 1…6, columns = Y increments 1…5):
X1 (0–0.4): 1 0 0 0 0
X2 (0.4–1.1): 1 1 0 0 0
X3 (1.1–1.8): 0 1 1 0 0
X4 (1.8–2.5): 0 0 1 1 0
X5 (2.5–3.4): 0 0 0 1 1
X6 (3.4–4.0): 0 0 0 0 1

Contributing products on overlaps (values ×10^6):
• ΔX1·ΔY1 = 0.001000×0.000700 = 0.70
• ΔX2·ΔY1 = (−0.000500)×0.000700 = −0.35
• ΔX2·ΔY2 = (−0.000500)×(−0.000500) = 0.25
• ΔX3·ΔY2 = 0.001200×(−0.000500) = −0.60
• ΔX3·ΔY3 = 0.001200×0.000800 = 0.96
• ΔX4·ΔY3 = (−0.000500)×0.000800 = −0.40
• ΔX4·ΔY4 = (−0.000500)×(−0.000400) = 0.20
• ΔX5·ΔY4 = 0.000700×(−0.000400) = −0.28
• ΔX5·ΔY5 = 0.000700×0.000500 = 0.35
• ΔX6·ΔY5 = (−0.000300)×0.000500 = −0.15
Sum (the HY covariation over [0,4]) = 0.68×10^−6 (page: "Sum (the HY covariation over [0,4]) 6.800", in ×10^−7 units).

HY quadratic variations (for a correlation) (each X-interval overlaps itself):
X: 1.00 + 0.25 + 1.44 + 0.25 + 0.49 + 0.09 = 3.52×10^−6.
Y: 0.49 + 0.25 + 0.64 + 0.16 + 0.25 = 1.79×10^−6.
HY correlation = 0.68/√(3.52·1.79) = 0.68/2.5101 = 0.271.

Lead–lag contrast at two trial shifts (illustration of HRY)
Shift Y's clock by θ = +0.5s (Y lags X if this raises |U|). New Y-intervals: (0.5,1.2], (1.2,2.0], (2.0,2.7], (2.7,3.5], (3.5,4.5]. Overlap with X-intervals changes. Recomputing the products the same way:
• X1 overlaps shifted Y1: only (0.4,0.5]: ΔX1·ΔY1 = 0.7 → contributes 0.70
• X2 (0.4–1.1] with Y1: ΔX2·ΔY1 = −0.35; X2 with Y2 (1.2–2.0]? touches (1.1,1.2]: ΔX2·ΔY2 = 0.25
• X3 (1.1–1.8] with Y2: ΔX3·ΔY2 = −0.60; X3 with Y3 (2.0–2.7]? touches (1.8,2.0]: ΔX3·ΔY3 = 0.96
• X4 (1.8–2.5] with Y3: −0.40; X4 with Y4 (2.7–3.5]? touches (2.5,2.7]: ΔX4·ΔY4 = 0.20
• X5 (2.5–3.4] with Y4: −0.28; X5 with Y5 (3.5–4.5]? touches (3.4,3.5]: ΔX5·ΔY5 = 0.35
• X6 (3.4–4.0] with Y5: −0.15
Sum U(+0.5) = 0.25×10^−6 (page: "Sum 2.5" in ×10^−7) vs U(0) = 0.68×10^−6 ("6.8" ×10^−7), so on this two-point grid the HRY contrast still prefers θ = 0. A real estimator scans a mesh; this pair is only to show the arithmetic of the indicator after a clock shift.

Source list (only papers actually used)
• Lee, S.S. and Mykland, P.A. (2008), "Jumps in Financial Markets: A New Nonparametric Test and Jump Detection," Review of Financial Studies 21(6), 2535–2563.
• Hayashi, T. and Yoshida, N. (2005), "On covariance estimation of non-synchronously observed diffusion processes," Bernoulli 11(2), 359–379.
• Hoffmann, M., Rosenbaum, M. and Yoshida, N. (2013), "Estimation of the lead-lag parameter from non-synchronously observed data," Bernoulli 19(2), 426–461.
• Jegadeesh, N. (1990), "Evidence of Predictable Behavior of Security Returns," Journal of Finance 45(3), 881–898.
• Lehmann, B.N. (1990), "Fads, Martingales, and Market Efficiency," Quarterly Journal of Economics 105(1), 1–28.
• Blitz, D., Huij, J. and Martens, M. (2013), "Residual momentum," residual-reversal companion in Journal of Financial Markets 16, 477–504 ("Short-term residual reversal").
• Da, Z., Liu, Q. and Schaumburg, E. (2014), "A Closer Look at the Short-Term Return Reversal," Management Science 60(3), 658–674.
• Large, J. (2007), "Measuring the resiliency of an electronic limit order book," Journal of Financial Markets 10(1), 1–25.
• Obizhaeva, A. and Wang, J. (2013), "Optimal trading strategy and supply/demand dynamics," Journal of Financial Markets 16(1), 1–32.
• Stöckl, S. and Kaiser, L. (2019), "Statistical Arbitrage with Mean-Reverting Overnight Price Gaps…," Journal of Risk and Financial Management 12(2), 51.
• Roll, R. (1984), "A Simple Implicit Measure of the Effective Bid-Ask Spread," Journal of Finance 39(4), 1127–1139.
• Everything not attributed to one of the above — gap |G|-cutoffs of 0.20–0.50%, z-score cutoffs of 1.5–2σ, fade horizons other than Stöckl–Kaiser's 120 minutes, K in the toy LM calculation, the 12-tick path, half-life priors of 5–30 s beyond Large's "under 20 s" — is illustrative.
