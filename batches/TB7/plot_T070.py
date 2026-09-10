"""T070 worked-example chart — MUST match the T4 table in batches/TB7/T070.md.
seed 170. Run from quant-signals-deep/: python3 batches/TB7/plot_T070.py
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
    "price":   "#1f3a5f",  # dark navy — primary price/equity line
    "signal":  "#c0392b",  # red — signal / entries
    "signal2": "#8e44ad",  # purple — secondary signal
    "volume":  "#7f8c8d",  # grey — volume bars
    "band":    "#aed6f1",  # light blue — bands / fill
    "profit":  "#1e8449",  # green — profits / long
    "loss":    "#922b21",  # dark red — losses / short
    "zero":    "#2c3e50",  # baseline
}

rng = np.random.default_rng(170)  # seed stated in T070.md T4

# ---- synthetic 15:50-16:00 ABC tape anchored to the T4 numbers ----
# 15:50: buy imbalance 120k, indicative 40.08; 15:52: buy imbalance 110k,
# indicative 40.10, mid 40.04; buy 2000 continuous @ 40.05;
# 15:58: offsetting MOC sell; official close print 40.11 (T4).
t = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])  # minutes 15:50..16:00
mid = np.array([40.02, 40.03, 40.04, 40.045, 40.05, 40.055, 40.06, 40.065, 40.07,
                40.075, 40.08]) + rng.normal(0, 0.004, 11)
mid[2] = 40.04                                   # mid at signal (T4)
indic = np.array([40.08, 40.09, 40.10, 40.10, 40.10, 40.105, 40.105, 40.108, 40.11,
                  40.11, 40.11])
imb = np.array([120000, 115000, 110000, 108000, 105000, 103000, 102000, 101000,
                100000, 100000, 0])

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T070 — MOC Auction-Pin Trader:\nsynthetic close tape + P&L (seed 170)",
             fontweight="bold")

# Top: mid vs indicative with imbalance annotations and trade markers
ax1.plot(t, mid, color=PALETTE["price"], lw=1.6, marker="o", ms=4,
         label="synthetic mid (ABC)")
ax1.plot(t, indic, color=PALETTE["signal2"], lw=1.6, ls="--", marker="s", ms=4,
         label="indicative match price")
ax1.axhline(40.00, color=PALETTE["volume"], lw=1.0, ls=":",
            label="high-OI strike 40.00 (GEX proxy: long-gamma)")
ax1.annotate("imb 120k\n40.08", (0, 40.08), textcoords="offset points",
             xytext=(6, 10), fontsize=8, color=PALETTE["signal2"])
ax1.annotate("imb 110k\n40.10", (2, 40.10), textcoords="offset points",
             xytext=(6, 10), fontsize=8, color=PALETTE["signal2"])
ax1.scatter([2], [40.05], color=PALETTE["profit"], marker="^", s=110, zorder=5,
            label="buy 2000 @ 40.05 (15:52)")
ax1.scatter([10], [40.11], color=PALETTE["signal"], marker="D", s=90, zorder=5,
            label="MOC sell @ 40.11 (official close print)")
ax1.set_ylabel("price ($)")
ax1.set_xlabel("minutes after 15:50 ET")
ax1.legend(loc="upper left", ncol=2)
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net P&L — T4 ledger: gross +120.00, comm -20.00, net +100.00
net = np.array([+100.00])
cum_net = np.cumsum(net)
ax2.plot([10], cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate(f"{net[0]:+.2f}", (10, cum_net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10, color=PALETTE["profit"], weight="bold")
ax2.annotate("Buy 40.05 x2000; MOC sell 40.11 x2000", (10, cum_net[0]),
             textcoords="offset points", xytext=(0, -16), ha="center", fontsize=8,
             color=PALETTE["volume"])
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("minutes after 15:50 ET")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T070_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T070_example.png; final cum net =", cum_net[-1])
