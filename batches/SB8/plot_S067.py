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

# ---- SYNTHETIC diurnal deseasonalization demo (seed 67) ----
rng = np.random.default_rng(67)
M = 78                                   # one RTH session of 5-min bins
days = 20
idx = np.arange(M)

# True U-shaped diurnal scale (unknown to the estimator, mean 1)
u = (idx - (M - 1) / 2) / ((M - 1) / 2)
s_true = 1.0 + 0.60 * u ** 2
s_true = s_true / s_true.mean()

# 20 synthetic days of 5-min returns: r_{t,b} = s_true[b] * sigma_t * z
sigma_day = rng.uniform(0.0006, 0.0014, days)      # random daily vol level per day
R = s_true[None, :] * sigma_day[:, None] * rng.standard_normal((days, M))

# Estimate the diurnal factor: median |r| per bin, scaled to mean 1
s_hat = np.median(np.abs(R), axis=0)
s_hat = s_hat / s_hat.mean()

# Deseasonalized returns for one illustrative day (day 0)
r_raw = R[0]
r_adj = r_raw / s_hat

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True)

ax1.plot(idx + 1, s_true, color=PALETTE["signal2"], lw=2.2, ls="--",
         label="true U-shape s_b (mean 1, hidden from estimator)")
ax1.plot(idx + 1, s_hat, color=PALETTE["signal"], lw=2.0,
         label="estimated s_hat_b = median|r_b| / mean (20 synthetic days)")
ax1.set_ylabel("diurnal scale factor")
ax1.set_title("S067 — Diurnal U-shape: estimated intraday volatility profile (seed 67)")
ax1.legend(loc="upper right")
ax1.text(0.02, 0.62, "open and close bins ~1.3-1.5x midday vol\n"
                     "a raw GARCH/HAR fit on unadjusted returns\n"
                     "would mistake this for volatility clustering",
         transform=ax1.transAxes, fontsize=9,
         bbox=dict(boxstyle="round", fc="white", ec=PALETTE["zero"], alpha=0.9))

x = idx + 1
ax2.bar(x, r_raw * 1e4, color=PALETTE["price"], width=0.9, edgecolor="none", alpha=0.75,
        label="raw 5-min returns (bp), day 1")
ax2.bar(x, r_adj * 1e4, color=PALETTE["signal"], width=0.9, edgecolor="none", alpha=0.55,
        label="deseasonalized returns = r / s_hat_b (bp)")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_xlabel("5-minute bin of the session (1=open, 78=close)")
ax2.set_ylabel("return (basis points)")
ax2.legend(loc="upper right")
ax2.set_title("raw vs deseasonalized 5-min returns: the open spike is flattened",
              fontsize=10, fontweight="normal")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S067_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print(f"s_hat mean={s_hat.mean():.6f} max(s_hat)/min(s_hat)={s_hat.max()/s_hat.min():.2f} raw_open_bin1_bp={r_raw[0]*1e4:.1f} adj_open_bin1_bp={r_adj[0]*1e4:.1f}")
