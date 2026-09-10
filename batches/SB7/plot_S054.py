"""S054 plot: copula conditional-probability signal, 10 synthetic days. seed=54054."""
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

from scipy.stats import norm

SEED = 54054
RHO = 0.8  # example Gaussian-copula parameter
rng = np.random.default_rng(SEED)

Z = rng.standard_normal((10, 2))
L = np.array([[1.0, 0.0], [RHO, np.sqrt(1 - RHO**2)]])
Zc = Z @ L.T
u = norm.cdf(Zc[:, 0])
v = norm.cdf(Zc[:, 1])
x1, x2 = norm.ppf(u), norm.ppf(v)
p_1g2 = norm.cdf((x1 - RHO * x2) / np.sqrt(1 - RHO**2))  # P(U_A <= u | U_B = v)
p_2g1 = norm.cdf((x2 - RHO * x1) / np.sqrt(1 - RHO**2))  # reverse
days = np.arange(1, 11)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=False)
fig.suptitle("S054 — Copula pairs trading: conditional-probability signal on 10 synthetic days")

# Panel 1: conditional-probability time series with example thresholds
ax1.plot(days, p_1g2, marker="o", color=PALETTE["price"], label="p(A|B) = P(U_A<=u | U_B=v)")
ax1.plot(days, p_2g1, marker="s", color=PALETTE["signal2"], label="p(B|A) = P(U_B<=v | U_A=u)")
for thr, lab in [(0.05, "entry 0.05: long A / short B"), (0.95, "entry 0.95: short A / long B")]:
    ax1.axhline(thr, color=PALETTE["signal"], linestyle="--", linewidth=1,
                label=f"{lab} (example)")
ax1.axhline(0.5, color=PALETTE["zero"], linestyle=":", linewidth=1, label="exit 0.5 (example)")
ax1.set_ylim(-0.08, 1.12)
ax1.scatter([1], [p_1g2[0]], s=120, facecolors="none", edgecolors=PALETTE["loss"], linewidths=2)
ax1.scatter([5], [p_1g2[4]], s=120, facecolors="none", edgecolors=PALETTE["profit"], linewidths=2)
ax1.annotate("day 1: 0.97 > 0.95\nshort A / long B", xy=(1, 0.97), xytext=(2.6, 1.04),
             fontsize=8, arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]))
ax1.annotate("day 5: 0.01 < 0.05\nlong A / short B", xy=(5, 0.01), xytext=(6.8, 0.22),
             fontsize=8, arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]))
ax1.set_xlim(0.5, 10.5)
ax1.set_ylabel("conditional probability")
ax1.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=7)

# Panel 2: unit-square scatter of the (u, v) pairs + conditional-probability contours
ax2.scatter(v, u, c=days, cmap="viridis", s=70, zorder=3)
for c in [0.05, 0.5, 0.95]:
    vv = np.linspace(0.001, 0.999, 400)
    uu = norm.cdf(RHO * norm.ppf(vv) + np.sqrt(1 - RHO**2) * norm.ppf(c))
    ax2.plot(vv, uu, color=PALETTE["signal"], linestyle="--" if c != 0.5 else "-",
             linewidth=1.2, label=f"p(A|B) = {c}")
for i in range(10):
    ax2.annotate(str(i + 1), (v[i], u[i]), fontsize=7, xytext=(4, 4),
                 textcoords="offset points", color=PALETTE["zero"])
ax2.set_xlim(0, 1); ax2.set_ylim(0, 1)
ax2.set_xlabel("V = F_B(return B) — PIT uniform (unitless)")
ax2.set_ylabel("U = F_A(return A) — PIT uniform (unitless)")
ax2.set_title("Uniforms in the unit square (Gaussian copula, rho = 0.8 example)", fontsize=10)
ax2.legend(loc="upper left", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S054_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
