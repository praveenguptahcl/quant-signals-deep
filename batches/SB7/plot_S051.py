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

# ---- VERIFIED SYNTHETIC OU WORKED EXAMPLE (seed stated in chapter) ----
rng = np.random.default_rng(51)  # recorded; example is exact/analytic
t = np.arange(1, 21)                     # t = 1..20
S = 10.0 * 0.8 ** (t - 1)                # S_t = 10(0.8)^{t-1} (VERIFIED)
dS = S[1:] - S[:-1]                      # Delta S_t = -0.2 S_{t-1} exactly
Slag = S[:-1]

# OLS AR(1): Delta S_t = alpha + phi S_{t-1} + u_t
d = Slag - Slag.mean()
phi = ((d * (dS - dS.mean())).sum()) / ((d ** 2).sum())
alpha = dS.mean() - phi * Slag.mean()
kappa = -np.log(1.0 + phi)
half_life = np.log(2.0) / kappa
print(f"alpha={alpha:.10f} phi={phi:.10f} half_life={half_life:.6f} days")

fig, axes = plt.subplots(1, 2)

# Left: spread decay with half-life annotation
axes[0].plot(t, S, color=PALETTE["price"], lw=2.2, marker="o", ms=4,
             label=r"$S_t = 10(0.8)^{t-1}$")
axes[0].axhline(5.0, color=PALETTE["signal2"], ls="--", lw=1.2, alpha=0.8)
axes[0].axvline(1.0 + half_life, color=PALETTE["signal2"], ls="--", lw=1.2,
                alpha=0.8)
axes[0].plot(1.0 + half_life, 5.0, "D", color=PALETTE["signal2"], ms=7)
axes[0].annotate(f"half-life\nt_1/2 = {half_life:.4f} days\n"
                 r"$-\ln 2 / \ln(0.8)$",
                 xy=(1.0 + half_life, 5.0), xytext=(8.5, 6.5),
                 fontsize=9, color=PALETTE["signal2"],
                 arrowprops=dict(arrowstyle="->", color=PALETTE["signal2"], lw=1.2))
axes[0].set_title("Synthetic OU spread decay")
axes[0].set_xlabel("t (days)")
axes[0].set_ylabel("S_t (spread, $)")
axes[0].legend(loc="upper right")

# Right: AR(1) regression check
axes[1].scatter(Slag, dS, color=PALETTE["price"], s=26, zorder=3,
                label=r"data: $\Delta S_t$ vs $S_{t-1}$")
grid = np.array([Slag.min(), Slag.max()])
axes[1].plot(grid, alpha + phi * grid, color=PALETTE["signal"], lw=2.0,
             label=rf"OLS fit: $\hat\alpha={alpha:.2f},\ \hat\phi={phi:.2f}$")
axes[1].axhline(0, color=PALETTE["zero"], lw=1)
axes[1].set_title(r"AR(1) check: $\Delta S_t = \alpha + \phi S_{t-1}$")
axes[1].set_xlabel(r"$S_{t-1}$ (spread, $)")
axes[1].set_ylabel(r"$\Delta S_t$ (spread change, $)")
axes[1].legend(loc="upper left")

fig.suptitle("S051 — Ornstein–Uhlenbeck half-life: verified synthetic decay tape",
             fontsize=13, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S051_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
