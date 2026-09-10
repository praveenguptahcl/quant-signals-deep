"""T079 worked-example chart \u2014 MUST match the T4 table in batches/TB8/T079.md.
seed 179. Run from quant-signals-deep/: python3 batches/TB8/plot_T079.py
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

rng = np.random.default_rng(179)  # seed stated in T079.md T4

# ---- synthetic tape anchored to the T4 numbers ----
N = 20
close = np.empty(N)
close[:2] = np.linspace(3.45, 3.2, 2) + rng.normal(0, 0.06, 2)
close[2:14] = np.linspace(3.2, 2.45, 14 - 2) + rng.normal(0, 0.06, 14 - 2)
close[14:] = 2.45 + rng.normal(0, 0.06, N - 14)
close[2] = 3.2   # entry fill (T4)
close[14] = 2.45    # exit fill (T4)

xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T079 \u2014 Post-Announcement Vol Fade:\nsynthetic tape + P&L (seed 179)",
             fontweight="bold")

# Top: tape with entry/exit markers
ax1.plot(xs, close, color=PALETTE["price"], lw=1.4, label="synthetic daily close (VOL straddle)")
ax1.axhline(2.73, color=PALETTE["signal2"], lw=1.2, ls="--", label="jump-robust fair value 2.73")
ax1.scatter([2], [3.2], color=PALETTE["loss"], marker="v", s=100, zorder=5,
            label="short straddle 3.20 (bar 2)")
ax1.scatter([14], [2.45], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="exit 2.45 (bar 14)")
ax1.set_ylabel("straddle price ($)")
ax1.legend(loc="upper left", ncol=2)
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net P&L \u2014 T4 ledger: +7500.00 gross, -1430.00 costs, +6070.00 net
trades = [("Short", 3.2, 2.45, +7500.00, -1430.00, +6070.00)]
net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
ax2.plot([14], cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate(f"{net[0]:+.2f}", (14, cum_net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10,
             color=PALETTE["profit"], weight="bold")
ax2.annotate(f"{trades[0][0]} 3.20\u21922.45 x100", (14, cum_net[0]),
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
plt.savefig("images/T079_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T079_example.png; final cum net =", cum_net[-1])
