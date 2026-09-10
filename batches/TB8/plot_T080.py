"""T080 worked-example chart \u2014 MUST match the T4 table in batches/TB8/T080.md.
seed 180. Run from quant-signals-deep/: python3 batches/TB8/plot_T080.py
All numbers synthetic.
"""
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
    "price":   "#1f3a5f",  # dark navy \u2014 primary price/equity line
    "signal":  "#c0392b",  # red \u2014 signal / entries
    "signal2": "#8e44ad",  # purple \u2014 secondary signal
    "volume":  "#7f8c8d",  # grey \u2014 volume bars
    "band":    "#aed6f1",  # light blue \u2014 bands / fill
    "profit":  "#1e8449",  # green \u2014 profits / long
    "loss":    "#922b21",  # dark red \u2014 losses / short
    "zero":    "#2c3e50",  # baseline
}

rng = np.random.default_rng(180)  # seed stated in T080.md T4

# ---- synthetic tape anchored to the T4 numbers ----
N = 20
close = np.empty(N)
close[:5] = np.linspace(31.6, 33.9, 5) + rng.normal(0, 0.1, 5)
close[5:12] = np.linspace(33.9, 33.42, 12 - 5) + rng.normal(0, 0.1, 12 - 5)
close[12:] = 33.42 + rng.normal(0, 0.1, N - 12)
close[5] = 33.9   # entry fill (T4)
close[12] = 33.42    # exit fill (T4)
close[3] = 34.35  # composite spike high
xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T080 \u2014 Multi-Source Attention Composite:\nsynthetic tape + P&L (seed 180)",
             fontweight="bold")

# Top: tape with entry/exit markers
ax1.plot(xs, close, color=PALETTE["price"], lw=1.4, label="synthetic daily close (CMP)")
ax1.axvspan(2.5, 5.5, color=PALETTE["band"], alpha=0.45, label="composite spike (ASVI+social+stale)")
ax1.scatter([5], [33.9], color=PALETTE["loss"], marker="v", s=100, zorder=5,
            label="short entry 33.90 (bar 5)")
ax1.scatter([12], [33.42], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="exit 33.42 (bar 12)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left", ncol=2)
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net P&L \u2014 T4 ledger: +4320.00 gross, -540.00 costs, +3780.00 net
trades = [("Short", 33.9, 33.42, +4320.00, -540.00, +3780.00)]
net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
ax2.plot([12], cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate(f"{net[0]:+.2f}", (12, cum_net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10,
             color=PALETTE["profit"], weight="bold")
ax2.annotate(f"{trades[0][0]} 33.90\u219233.42 x9,000", (12, cum_net[0]),
             textcoords="offset points", xytext=(0, -16), ha="center", fontsize=8,
             color=PALETTE["volume"])
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("synthetic daily bars")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data \u2014 not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T080_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T080_example.png; final cum net =", cum_net[-1])
