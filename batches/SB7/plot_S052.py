import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np

# ---- HOUSE STYLE (do not restyle) ----
plt.rcParams.update({
    "figure.figsize": (10, 5.2),
    "figure.dpi": 150,
    "savefig.dpi": 150,
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "legend.framealpha": 0.9,
})
PALETTE = {
    "price":   "#1f3a5f",  # dark navy — primary price/equity line
    "signal":  "#c0392b",  # red — signal / entries
    "signal2": "#8e44ad",  # purple — secondary signal
    "volume":  "#7f8c8d",  # grey — volume bars
    "band":    "#aed6f1",  # light blue — bands / fill
    "profit":  "#1e8449",  # green — profits / long
    "loss":    "#922b21",  # dark red — losses / short
    "zero":    "#2c3e50",  # baseline
}

# ---- SYNTHETIC PAIR (seed stated in chapter) ----
# Leg A: stationary AR(1) around 0. Leg B: y_t = mu + beta_t * x_t + noise,
# with a genuinely DRIFTING hedge ratio (the case where Kalman earns its keep).
rng = np.random.default_rng(52)
n = 400
x = np.empty(n)
x[0] = 0.0
for i in range(1, n):
    x[i] = 0.97 * x[i - 1] + rng.normal(0.0, 0.50)
t = np.arange(n)
beta_true = (1.20 + 0.20 * np.sin(2 * np.pi * t / 150.0)
             + np.cumsum(rng.normal(0.0, 0.003, n)))
mu_true = 1.0
y = mu_true + beta_true * x + rng.normal(0.0, 0.30, n)

# ---- 1-state Kalman on the hedge ratio beta ----
# Production uses the joint 2-state [mu, beta] form (see S3); for a hand-followable
# demo we demean leg B (mu_hat fixed from the first 60 obs) and filter beta only.
# Scale-aware Q/R tuning (bot lead Q-SB7-1): R = short-run OLS residual variance,
# q_beta = alpha_beta * R / Var(x), alpha_beta = 1e-4.
def ols_resid_var(xw, yw):
    b = np.cov(xw, yw)[0, 1] / np.var(xw)
    a = yw.mean() - b * xw.mean()
    return float(np.var(yw - (a + b * xw)))

R = ols_resid_var(x[:60], y[:60])
vx = float(np.var(x))
q_beta = 1e-4 * R / vx
b60 = np.cov(x[:60], y[:60])[0, 1] / np.var(x[:60])   # formation OLS slope
mu_hat = float(y[:60].mean() - b60 * x[:60].mean())   # formation OLS intercept
yd = y - mu_hat                                       # demeaned leg B
print(f"R={R:.5f} q_beta={q_beta:.3e} mu_hat={mu_hat:.4f}")

beta = 1.20                                           # state: hedge ratio
P = 0.04                                              # state variance
beta_k = np.empty(n); F = np.empty(n); e = np.empty(n)
Kg = np.empty(n)
for i in range(n):
    P = P + q_beta                                    # predict
    e[i] = yd[i] - beta * x[i]                        # innovation
    F[i] = x[i] * P * x[i] + R                        # innovation variance
    Kg[i] = (P * x[i]) / F[i]                         # Kalman gain
    beta = beta + Kg[i] * e[i]                        # update
    P = (1.0 - Kg[i] * x[i]) * P
    beta_k[i] = beta

sqrtF = np.sqrt(F)
z_k = e / sqrtF                                       # Kalman standardized spread

# ---- static OLS benchmark (whole-sample, one fixed beta) ----
b_ols = np.cov(x, y)[0, 1] / np.var(x)
a_ols = y.mean() - b_ols * x.mean()
spread_ols = y - (a_ols + b_ols * x)
z_ols = (spread_ols - spread_ols.mean()) / spread_ols.std()

# ---- synthetic trade counts: enter |z|>2, exit |z|<0.5 (example rule) ----
def trade_count(z):
    entered, count = False, 0
    for v in z:
        if not entered and abs(v) > 2.0:
            entered, count = True, count + 1
        elif entered and abs(v) < 0.5:
            entered = False
    return count

nk, no = trade_count(z_k), trade_count(z_ols)
print(f"static OLS beta={b_ols:.4f}  trades: kalman={nk} ols={no}")

# ---- worked-example table rows (t=150..159), recompute and print ----
print("t, x, yd, beta_prior, innov, sqrtF, K, beta_post")
beta = 1.20; P = 0.04
for i in range(n):
    Pp = P + q_beta
    beta_pr = beta
    ev = yd[i] - beta * x[i]
    Fv = x[i] * Pp * x[i] + R
    Kv = (Pp * x[i]) / Fv
    beta = beta + Kv * ev
    P = (1.0 - Kv * x[i]) * Pp
    if 150 <= i <= 159:
        print(f"{i},{x[i]:.4f},{yd[i]:.4f},{beta_pr:.4f},"
              f"{ev:.4f},{np.sqrt(Fv):.4f},{Kv:.5f},{beta:.4f}")

# ---- plots ----
fig, axes = plt.subplots(1, 2)

axes[0].plot(t, beta_true, color=PALETTE["volume"], ls="--", lw=1.4,
             label="true synthetic beta_t (unknown to filter)")
axes[0].plot(t, beta_k, color=PALETTE["price"], lw=1.6, label="Kalman beta_t")
axes[0].axhline(b_ols, color=PALETTE["signal"], lw=1.6, ls=":",
                label=f"static OLS beta = {b_ols:.3f}")
axes[0].set_title("Hedge-ratio tracking: Kalman vs static OLS")
axes[0].set_xlabel("t (synthetic daily bars)")
axes[0].set_ylabel("hedge ratio beta")
axes[0].set_xlim(0, n)
axes[0].legend(loc="lower left")

axes[1].bar(t, np.abs(z_k), color=PALETTE["signal"], alpha=0.55, width=1.0,
            label="Kalman |z| (innovation / sqrt F)")
axes[1].plot(t, np.abs(z_ols), color=PALETTE["price"], lw=1.0,
             label="static OLS |z|")
axes[1].axhline(2.0, color=PALETTE["signal2"], ls="--", lw=1.2,
                label="entry |z| = 2.0 (example)")
axes[1].axhline(0.5, color=PALETTE["zero"], ls=":", lw=1.2,
                label="exit |z| = 0.5 (example)")
axes[1].set_title(f"Trade count (synthetic rule): Kalman {nk} vs OLS {no}")
axes[1].set_xlabel("t (synthetic daily bars)")
axes[1].set_ylabel("|z-score| of spread")
axes[1].set_ylim(0, 7)
axes[1].legend(loc="upper right", fontsize=8)

fig.suptitle("S052 — Kalman dynamic hedge ratio vs static OLS (synthetic pair)",
             fontsize=13, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S052_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
