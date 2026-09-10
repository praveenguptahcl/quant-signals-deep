"""S055 plot: VECM error-correction path, 3-leg synthetic basket. seed=55055.

Every number on this chart is computed from the stated recipe below
(statsmodels 0.15.0, seed 55055, N=120, det_order=1, k_ar_diff=1).
Nothing is hard-coded: the Johansen test, beta-hat, the EC tape, the band,
and the breach days are all recomputed here.
"""
import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
from statsmodels.tsa.vector_ar.vecm import coint_johansen

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

# ---- STATED RECIPE (identical to the chapter's S4) ----
SEED = 55055
N = 120  # 120 daily observations
rng = np.random.default_rng(SEED)

# Synthetic 3-leg basket with ONE cointegrating vector beta = [1, -0.7, -0.4].
A = np.cumsum(rng.standard_normal(N))  # common trend 1 (random walk)
B = np.cumsum(rng.standard_normal(N))  # common trend 2 (random walk)
X1 = 100.0 + 0.7 * A + 0.4 * B + rng.standard_normal(N) * 0.6
X2 = 50.0 + 1.0 * A + rng.standard_normal(N) * 0.8
X3 = 30.0 + 1.0 * B + rng.standard_normal(N) * 0.5
X = np.column_stack([X1, X2, X3])

# ---- COMPUTED, NOT HARD-CODED: the Johansen test itself ----
res = coint_johansen(X, det_order=1, k_ar_diff=1)
eig = res.eig
trace_stat, trace_crit = res.lr1, res.cvt[:, 1]   # 95% column
maxeig_stat, maxeig_crit = res.lr2, res.cvm[:, 1]
beta_hat = res.evec[:, 0] / res.evec[0, 0]         # normalize beta_1 = 1
print(f"eig = {np.round(eig, 4)}")
print(f"trace  = {np.round(trace_stat, 2)}  crit95 = {np.round(trace_crit, 2)}")
print(f"maxeig = {np.round(maxeig_stat, 2)}  crit95 = {np.round(maxeig_crit, 2)}")
print(f"beta_hat = {np.round(beta_hat, 4)}")

# ---- COMPUTED: the error-correction spread tape ----
ec = X @ beta_hat
ec = ec - ec[:50].mean()  # center on formation-window mean (standard practice)
sigma = ec.std(ddof=1)
band = 2 * sigma
print(f"sigma = {sigma:.4f}, band = {band:.4f}")

days = np.arange(1, N + 1)
breach_hi = days[ec > band]
breach_lo = days[ec < -band]
print(f"short-basket entry days: {list(breach_hi)} vals {np.round(ec[breach_hi - 1], 3)}")
print(f"long-basket entry days:  {list(breach_lo)} vals {np.round(ec[breach_lo - 1], 3)}")

fig, ax = plt.subplots()
ax.set_title("S055 — Johansen VECM: error-correction path for a 3-leg synthetic basket")
ax.plot(days, ec, color=PALETTE["price"], linewidth=1.2,
        label=r"EC spread $e_t = \hat{\beta}'X_t$, centered (points)")
ax.axhline(band, color=PALETTE["signal"], linestyle="--", linewidth=1,
           label=f"+2 sigma entry band (+{band:.2f}, example)")
ax.axhline(-band, color=PALETTE["signal"], linestyle="--", linewidth=1,
           label=f"-2 sigma entry band ({-band:.2f}, example)")
ax.axhline(0, color=PALETTE["zero"], linestyle=":", linewidth=1, label="equilibrium (exit level)")
ax.fill_between(days, -band, band, color=PALETTE["band"], alpha=0.35)

ax.scatter(breach_hi, ec[breach_hi - 1], s=70, color=PALETTE["loss"], marker="v",
           zorder=5, label=f"short-basket entries ({len(breach_hi)} days)")
ax.scatter(breach_lo, ec[breach_lo - 1], s=70, color=PALETTE["profit"], marker="^",
           zorder=5, label=f"long-basket entries ({len(breach_lo)} day)")
ax.annotate(f"day {breach_lo[0]}: {ec[breach_lo[0]-1]:+.2f}\nlong basket",
            xy=(breach_lo[0], ec[breach_lo[0] - 1]), xytext=(56, -2.35),
            fontsize=8, arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]))
ax.annotate(f"day {breach_hi[-1]}: {ec[breach_hi[-1]-1]:+.2f}\nshort basket",
            xy=(breach_hi[-1], ec[breach_hi[-1] - 1]), xytext=(97, 2.55),
            fontsize=8, arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]))
ax.set_xlim(1, N)
ax.set_xlabel("trading day")
ax.set_ylabel("error-correction spread (index points)")
ax.text(0.02, 0.97,
        f"Johansen trace: {trace_stat[0]:.2f} > {trace_crit[0]:.2f} (reject r=0); "
        f"{trace_stat[1]:.2f} < {trace_crit[1]:.2f} (accept r=1)\n"
        f"rank = 1 cointegrating vector; beta-hat = [{beta_hat[0]:.1f}, "
        f"{beta_hat[1]:.4f}, {beta_hat[2]:.4f}]",
        transform=ax.transAxes, fontsize=8, va="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.85))
ax.legend(loc="lower right", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S055_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
