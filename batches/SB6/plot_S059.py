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

# ---- SYNTHETIC DATA: futures lead spot by 5 minutes (seed 59) ----
rng = np.random.default_rng(59)
N, LEAD = 120, 5  # 120 one-minute bars; spot lags futures by 5 min
fut_ret = rng.normal(0, 0.0008, N)          # ES futures 1-min mid returns
spot_noise = rng.normal(0, 0.0005, N)
spot_ret = np.concatenate([np.zeros(LEAD), fut_ret[:N - LEAD]]) + spot_noise
fut_px = 5000 * np.exp(np.cumsum(fut_ret))
spot_px = 5000 * np.exp(np.cumsum(spot_ret))
tmin = np.arange(N)

# Cross-correlation of spot(t) vs futures(t - lag): peak expected at lag = 5 min
lags = np.arange(0, 11)
ccf = np.array([np.corrcoef(spot_ret[l:], fut_ret[:N - l])[0, 1] for l in lags])
peak_lag = lags[np.argmax(ccf)]

# Lagged predictive regression: spot(t) = a + b * fut(t-5)  (example threshold demo)
x = fut_ret[:N - LEAD]
y = spot_ret[LEAD:]
b = np.cov(x, y, bias=True)[0, 1] / np.var(x)
a = y.mean() - b * x.mean()
r2 = (np.corrcoef(x, y)[0, 1]) ** 2
print(f"peak lag = {peak_lag} min; slope b={b:.4f}; intercept a={a:.7f}; R^2={r2:.4f}")
print("CCF by lag (min):", ", ".join(f"{l}:{c:.3f}" for l, c in zip(lags, ccf)))
print("first/last px: fut", f"{fut_px[0]:.2f} -> {fut_px[-1]:.2f}; spot", f"{spot_px[0]:.2f} -> {spot_px[-1]:.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=False, gridspec_kw={"height_ratios": [3, 2]})
ax1.plot(tmin, fut_px, color=PALETTE["price"], lw=1.8, label="Synthetic ES futures (1-min mids)")
ax1.plot(tmin, spot_px, color=PALETTE["signal"], lw=1.5, linestyle="--",
         label="Synthetic SPY spot (1-min mids, lagging 5 min)")
ax1.set_ylabel("Index level")
ax1.set_title("S059 — Futures–spot lead-lag: synthetic 5-min futures lead (seed 59)")
ax1.legend(loc="upper left")

ax2.bar(lags, ccf, color=PALETTE["band"], edgecolor=PALETTE["price"], lw=1.2,
        label="Cross-corr corr(spot(t), fut(t-lag))")
ax2.bar([peak_lag], [ccf[peak_lag]], color=PALETTE["signal"], edgecolor=PALETTE["price"], lw=1.2)
ax2.axvline(peak_lag, color=PALETTE["signal"], linestyle=":", lw=1.4)
ax2.annotate(f"peak at {peak_lag} min  (corr={ccf[peak_lag]:.2f})",
             xy=(peak_lag, ccf[peak_lag]), xytext=(peak_lag + 2.2, ccf[peak_lag] - 0.06),
             fontsize=9, arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]))
ax2.set_xlabel("Lag (minutes)")
ax2.set_ylabel("Cross-correlation")
ax2.legend(loc="lower right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S059_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
