"""T074 worked-example chart \u2014 MUST match the T4 table in batches/TB8/T074.md.
seed 174. Run from quant-signals-deep/: python3 batches/TB8/plot_T074.py
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

rng = np.random.default_rng(174)  # seed stated in T074.md T4

# ---- synthetic tape anchored to the T4 numbers ----
N = 15
close = np.empty(N)
close[:4] = np.linspace(11.6, 12.3, 4) + rng.normal(0, 0.08, 4)
close[4:10] = np.linspace(12.3, 13.05, 10 - 4) + rng.normal(0, 0.08, 10 - 4)
close[10:] = 13.05 + rng.normal(0, 0.08, N - 10)
close[4] = 12.3   # entry fill (T4)
close[10] = 13.05    # exit fill (T4)

xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T074 \u2014 Short-Interest Squeeze Rider:\nsynthetic tape + P&L (seed 174)",
             fontweight="bold")

# Top: tape with entry/exit markers
ax1.plot(xs, close, color=PALETTE["price"], lw=1.4, label="synthetic daily close (SQZ)")
ax1.axvspan(2.5, 4.5, color=PALETTE["band"], alpha=0.45, label="covering ignition (SI 22%, fee 6%)")
ax1.scatter([4], [12.3], color=PALETTE["profit"], marker="^", s=100, zorder=5,
            label="long entry 12.30 (bar 4)")
ax1.scatter([10], [13.05], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="exit 13.05 (bar 10)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left", ncol=2)
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net P&L \u2014 T4 ledger: +3150.00 gross, -250.00 costs, +2900.00 net
trades = [("Long", 12.3, 13.05, +3150.00, -250.00, +2900.00)]
net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
ax2.plot([10], cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate(f"{net[0]:+.2f}", (10, cum_net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10,
             color=PALETTE["profit"], weight="bold")
ax2.annotate(f"{trades[0][0]} 12.30\u219213.05 x4,200", (10, cum_net[0]),
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
plt.savefig("images/T074_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T074_example.png; final cum net =", cum_net[-1])
