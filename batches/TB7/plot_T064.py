"""T064 worked-example chart — MUST match the T4 table in batches/TB7/T064.md.
seed 164. Run from quant-signals-deep/: python3 batches/TB7/plot_T064.py
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

rng = np.random.default_rng(164)  # seed stated in T064.md T4

# ---- synthetic 5-min JKL tape anchored to the T4 numbers ----
# Morning arm: bar 1 (09:35) arm-on; bar 2 open: long 30.12; bar 12 (10:30): exit 30.58.
# Afternoon arm: bar 66 (15:05) arm-on; bar 67 open: long 30.70; bar 77 (15:55): exit 30.55.
N = 78
close = np.empty(N)
close[0:2] = [29.80, 30.05]
close[2] = 30.12                       # morning entry (T4)
close[3:12] = np.linspace(30.15, 30.58, 9) + rng.normal(0, 0.04, 9)
close[12] = 30.58                      # morning exit (T4)
close[13:66] = np.linspace(30.55, 30.45, 53) + rng.normal(0, 0.06, 53)
close[66] = 30.60
close[67] = 30.70                      # afternoon entry (T4)
close[68:77] = np.linspace(30.68, 30.55, 9) + rng.normal(0, 0.03, 9)
close[77] = 30.55                      # afternoon exit (T4)

xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T064 — U-Shape Seasonality Timer:\nsynthetic tape + P&L (seed 164)",
             fontweight="bold")

# Top: tape with arm windows and trade markers
ax1.plot(xs, close, color=PALETTE["price"], lw=1.4, label="synthetic 5-min close (JKL)")
ax1.axvspan(0.5, 11.5, color=PALETTE["band"], alpha=0.4, label="morning arm (09:35-10:30)")
ax1.axvspan(65.5, 77.5, color=PALETTE["band"], alpha=0.4, label="afternoon arm (15:00-15:55)")
ax1.scatter([2], [30.12], color=PALETTE["profit"], marker="^", s=100, zorder=5,
            label="long 30.12 (arm-on 1.77x)")
ax1.scatter([12], [30.58], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="exit 30.58 (10:30)")
ax1.scatter([67], [30.70], color=PALETTE["profit"], marker="^", s=100, zorder=5,
            label="long 30.70 (arm-on 1.83x)")
ax1.scatter([77], [30.55], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="exit 30.55 (15:55)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left", ncol=2)
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net P&L — T4 ledger
trades = [
    ("Long", 30.12, 30.58, +239.66, -5.21, +234.45),
    ("Long", 30.70, 30.55,  -73.05, -4.87,  -77.92),
]
net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
comp = [12, 77]
ax2.plot(comp, cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=6,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
for i, ct in enumerate(comp):
    n = net[i]
    col = PALETTE["profit"] if n > 0 else PALETTE["loss"]
    ax2.annotate(f"{n:+.2f}", (ct, cum_net[i]), textcoords="offset points",
                 xytext=(0, 12), ha="center", fontsize=9, color=col, weight="bold")
    d, entry, ex = trades[i][0], trades[i][1], trades[i][2]
    ax2.annotate(f"{d} {entry:.2f}\u2192{ex:.2f}", (ct, cum_net[i]),
                 textcoords="offset points", xytext=(0, -15), ha="center", fontsize=7,
                 color=PALETTE["volume"])
ax2.annotate(f"session {cum_net[-1]:+.2f}", (77, cum_net[-1]),
             textcoords="offset points", xytext=(10, 10), ha="left", fontsize=10,
             color=PALETTE["zero"], weight="bold")
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
plt.savefig("images/T064_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T064_example.png; final cum net =", cum_net[-1])
