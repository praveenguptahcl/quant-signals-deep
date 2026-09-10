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

rng = np.random.default_rng(30)  # fixed seed — reproducible synthetic series

# ---- Synthetic 30-bar bandwidth series (verified worked-example data) ----
# Bars 10-29: prior 20 BW values, compression tightening 0.0090 -> 0.0145 (example conveniences)
bw = np.empty(30)
bw[0:9] = np.linspace(0.0220, 0.0095, 9)     # bars 1-9: coming out of a wider-vol period
bw[9:29] = np.linspace(0.0090, 0.0145, 20)   # bars 10-29: prior-20 compression window
bw[29] = 0.01564                              # bar 30: expansion bar (1.564%, verified)
bars = np.arange(1, 31)

# Bandwidth percentile over trailing R=20 prior bars (example parameters, not a standard)
R = 20
pct = np.full(30, np.nan)
for t in range(R, 30):
    pct[t] = 100.0 * np.sum(bw[t - R:t] <= bw[t]) / R
assert abs(pct[29] - 100.0) < 1e-9  # all 20 prior values lower -> percentile 100%

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"height_ratios": [3, 2], "hspace": 0.12})
ax1.plot(bars, bw * 100, color=PALETTE["price"], lw=2.2, label="Bandwidth (upper-lower)/mid")
ax1.axhline(0.90, color=PALETTE["volume"], lw=1.0, ls="--", label="Prior-window low 0.90%")
ax1.axvspan(10, 29, color=PALETTE["band"], alpha=0.25, label="Compression window (bars 10-29)")
ax1.scatter([30], [bw[29] * 100], color=PALETTE["signal"], s=70, zorder=5)
ax1.annotate("Bar 30: bandwidth 1.564%\n(expansion bar after compression)",
             xy=(30, 1.564), xytext=(15, 1.95), fontsize=9, color=PALETTE["signal"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=PALETTE["signal"], alpha=0.9))
ax1.set_ylabel("Bandwidth (%)")
ax1.set_title("S030 — Bollinger bandwidth squeeze \u2192 expansion: synthetic percentile series")
ax1.legend(loc="upper left", fontsize=8.5)

ax2.plot(bars, pct, color=PALETTE["signal2"], lw=2.0, label="Bandwidth percentile (trailing 20 bars)")
ax2.axhspan(0, 20, color=PALETTE["profit"], alpha=0.15, label="Squeeze zone (percentile \u226420, example)")
ax2.axhline(20, color=PALETTE["profit"], lw=1.2, ls="--")
ax2.scatter([30], [100.0], color=PALETTE["signal"], s=70, zorder=5)
ax2.annotate("Bar 30: percentile 100% \u2014 NOT a squeeze.\n"
             "Squeeze = volatility-STATE timing;\nit says nothing about direction.",
             xy=(30, 100), xytext=(14, 78), fontsize=9, color=PALETTE["signal"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=PALETTE["signal"], alpha=0.9))
ax2.set_xlabel("Bar (5-min)")
ax2.set_ylabel("Percentile")
ax2.set_xlim(0.5, 30.5); ax2.set_ylim(-2, 105)
ax2.legend(loc="center left", fontsize=8.5)
# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S030_example.png", bbox_inches="tight")
plt.close()
print("S030 PNG written; bar-30 BW=%.4f%% percentile=%.1f%%" % (bw[29] * 100, pct[29]))
