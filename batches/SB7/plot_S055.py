"""S055 plot: VECM error-correction path, 3-leg synthetic basket. seed=55055."""
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

SEED = 55055
N = 120  # 120 daily observations
rng = np.random.default_rng(SEED)

# Synthetic 3-leg basket with ONE cointegrating vector beta = [1, -0.7, -0.4].
A = np.cumsum(rng.standard_normal(N))  # common trend 1 (random walk)
B = np.cumsum(rng.standard_normal(N))  # common trend 2 (random walk)
X1 = 100.0 + 0.7 * A + 0.4 * B + rng.standard_normal(N) * 0.6
X2 = 50.0 + 1.0 * A + rng.standard_normal(N) * 0.8
X3 = 30.0 + 1.0 * B + rng.standard_normal(N) * 0.5

# Estimated cointegrating vector from a Johansen fit on this sample (normalized, beta_1 = 1):
BETA_HAT = np.array([1.0, -0.7113, -0.3631])  # Johansen (statsmodels), true [1, -0.7, -0.4]
ec = np.column_stack([X1, X2, X3]) @ BETA_HAT
ec = ec - ec[:50].mean()  # center on formation-window mean (standard practice)
sigma = ec.std(ddof=1)  # 0.856
band = 2 * sigma  # entry band, example threshold

days = np.arange(1, N + 1)
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

breach_hi = np.where(ec > band)[0] + 1   # days 14, 30, 87
breach_lo = np.where(ec < -band)[0] + 1  # day 38
ax.scatter(breach_hi, ec[breach_hi - 1], s=70, color=PALETTE["loss"], marker="v",
           zorder=5, label=f"short-basket entries ({len(breach_hi)} days)")
ax.scatter(breach_lo, ec[breach_lo - 1], s=70, color=PALETTE["profit"], marker="^",
           zorder=5, label=f"long-basket entries ({len(breach_lo)} day)")
ax.annotate("day 38: -1.90\nlong basket", xy=(38, ec[37]), xytext=(56, -2.35),
            fontsize=8, arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]))
ax.annotate("day 87: +2.19\nshort basket", xy=(87, ec[86]), xytext=(97, 2.55),
            fontsize=8, arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]))
ax.set_xlim(1, N)
ax.set_xlabel("trading day")
ax.set_ylabel("error-correction spread (index points)")
ax.text(0.02, 0.97,
        "Johansen trace: 56.61 > 35.19 (reject r=0); 7.63 < 20.26 (accept r=1)\n"
        "rank = 1 cointegrating vector; beta-hat = [1, -0.7113, -0.3631]",
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
