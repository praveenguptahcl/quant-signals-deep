"""T066 worked-example chart — MUST match the T4 table in batches/TB7/T066.md.
seed 166. Run from quant-signals-deep/: python3 batches/TB7/plot_T066.py
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

rng = np.random.default_rng(166)  # seed stated in T066.md T4

# ---- synthetic 5-min MNO tape anchored to the T4 numbers ----
# 10:25 (bar 11): close 80.10 vs VWAP 80.18, RVOL 0.9 — no signal.
# 10:30 (bar 12): close 80.22 crosses above VWAP 80.19, RVOL 1.8 — signal.
# 10:35 (bar 13) open: long fill 80.25 (T4).
# 14:10 (bar 52): close 80.20 crosses below VWAP 80.31, RVOL 1.6 — opposite cross.
# next open (bar 53): exit 80.18 (T4).
N = 78
close = np.empty(N)
close[0:12] = np.linspace(80.30, 80.10, 12) + rng.normal(0, 0.02, 12)
close[11] = 80.10
close[12] = 80.22                                # cross close (T4)
close[13] = 80.25                                # long entry (T4)
close[14:52] = np.linspace(80.28, 80.20, 38) + rng.normal(0, 0.04, 38)
close[52] = 80.20                                # opposite-cross close (T4)
close[53] = 80.18                                # exit (T4)
close[54:] = 80.18 + rng.normal(0, 0.03, N - 54)

vwap = np.empty(N)                               # causal session VWAP (synthetic)
vwap[0:12] = np.linspace(80.25, 80.18, 12)
vwap[11] = 80.18
vwap[12] = 80.19                                 # VWAP at cross (T4)
vwap[13:52] = np.linspace(80.20, 80.31, 39)
vwap[52] = 80.31                                 # VWAP at opposite cross (T4)
vwap[53:] = np.linspace(80.31, 80.28, N - 53)

xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T066 — VWAP-Cross Institutional Follower:\nsynthetic tape vs VWAP + P&L (seed 166)",
             fontweight="bold")

# Top: price vs session VWAP with cross markers
ax1.plot(xs, close, color=PALETTE["price"], lw=1.4, label="synthetic 5-min close (MNO)")
ax1.plot(xs, vwap, color=PALETTE["signal2"], lw=1.2, ls="--", label="session VWAP (causal)")
ax1.scatter([13], [80.25], color=PALETTE["profit"], marker="^", s=100, zorder=5,
            label="long 80.25 (cross + RVOL 1.8)")
ax1.scatter([53], [80.18], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="exit 80.18 (opposite cross, RVOL 1.6)")
ax1.annotate("10:30 cross\n80.22 > VWAP 80.19", (12, 80.22),
             textcoords="offset points", xytext=(-52, 14), fontsize=8,
             color=PALETTE["signal2"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal2"], lw=1))
ax1.annotate("14:10 cross\n80.20 < VWAP 80.31", (52, 80.20),
             textcoords="offset points", xytext=(8, -28), fontsize=8,
             color=PALETTE["signal2"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal2"], lw=1))
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper right", ncol=2)
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net P&L — T4 ledger: gross -35.00, comm -5.00, net -40.00
trades = [("Long", 80.25, 80.18, -35.00, -5.00, -40.00)]
net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
ax2.plot([53], cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate(f"{net[0]:+.2f}", (53, cum_net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10, color=PALETTE["loss"], weight="bold")
ax2.annotate("Long 80.25\u219280.18 x500 (losing example)", (53, cum_net[0]),
             textcoords="offset points", xytext=(0, -16), ha="center", fontsize=8,
             color=PALETTE["volume"])
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("synthetic 5-min bars (09:30-16:00)")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T066_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T066_example.png; final cum net =", cum_net[-1])
