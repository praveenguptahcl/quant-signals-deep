"""T078 worked-example chart \u2014 MUST match the T4 table in batches/TB8/T078.md.
seed 178. Run from quant-signals-deep/: python3 batches/TB8/plot_T078.py
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

rng = np.random.default_rng(178)  # seed stated in T078.md T4

# ---- synthetic tape anchored to the T4 numbers ----
N = 78
close = np.empty(N)
close[:3] = np.linspace(40.3, 40.8, 3) + rng.normal(0, 0.06, 3)
close[3:50] = np.linspace(40.8, 41.42, 50 - 3) + rng.normal(0, 0.06, 50 - 3)
close[50:] = 41.42 + rng.normal(0, 0.06, N - 50)
close[3] = 40.8   # entry fill (T4)
close[50] = 41.42    # exit fill (T4)

xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T078 \u2014 Earnings-Drift Intraday Leg:\nsynthetic tape + P&L (seed 178)",
             fontweight="bold")

# Top: tape with entry/exit markers
ax1.plot(xs, close, color=PALETTE["price"], lw=1.4, label="synthetic 5-min close (ERN)")
ax1.axvspan(-0.5, 2.5, color=PALETTE["band"], alpha=0.45, label="09:30-09:45 leg confirm (SUE +2.1)")
ax1.scatter([3], [40.8], color=PALETTE["profit"], marker="^", s=100, zorder=5,
            label="long entry 40.80 (bar 3)")
ax1.scatter([50], [41.42], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="exit 41.42 (bar 50)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left", ncol=2)
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net P&L \u2014 T4 ledger: +15500.00 gross, -5712.00 costs, +9788.00 net
trades = [("Long", 40.8, 41.42, +15500.00, -5712.00, +9788.00)]
net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
ax2.plot([50], cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate(f"{net[0]:+.2f}", (50, cum_net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10,
             color=PALETTE["profit"], weight="bold")
ax2.annotate(f"{trades[0][0]} 40.80\u219241.42 x25,000", (50, cum_net[0]),
             textcoords="offset points", xytext=(0, -16), ha="center", fontsize=8,
             color=PALETTE["volume"])
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("synthetic 5-min bars")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data \u2014 not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T078_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T078_example.png; final cum net =", cum_net[-1])
