"""T062 worked-example chart — MUST match the T4 table in batches/TB7/T062.md.
seed 162. Run from quant-signals-deep/: python3 batches/TB7/plot_T062.py
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

rng = np.random.default_rng(162)  # seed stated in T062.md T4

# ---- synthetic 5-min DEF tape anchored to the T4 numbers ----
# Trade 1: up-streak bars 0-4 (09:45-10:10), exhaustion bar 5 (10:10-10:15),
#          short entry 62.30 at bar 6 open (10:20), stopped 62.74 at bar 7.
# Trade 2: down-streak bars 45-50 (13:30-14:00), exhaustion bar 51,
#          long entry 61.10 at bar 52 open (14:10), exit 61.66 at bar 74 open.
N = 80
close = np.empty(N)
close[0:5] = np.linspace(61.35, 62.05, 5) + rng.normal(0, 0.02, 5)   # up-streak
close[5] = 62.20                                                     # exhaustion close
close[6] = 62.30                                                     # short entry (T4)
close[7] = 62.74                                                     # stopped (T4)
close[8:45] = np.linspace(62.60, 62.00, 37) + rng.normal(0, 0.05, 37)
close[45:51] = np.linspace(61.95, 61.30, 6) + rng.normal(0, 0.02, 6)  # down-streak
close[51] = 61.15                                                    # exhaustion close
close[52] = 61.10                                                    # long entry (T4)
close[53:74] = np.linspace(61.15, 61.66, 21) + rng.normal(0, 0.04, 21)
close[74] = 61.66                                                    # exit (T4)
close[75:] = 61.66 + rng.normal(0, 0.03, N - 75)

xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T062 — Streak Runner with Exhaustion Flip:\nsynthetic tape + P&L (seed 162)",
             fontweight="bold")

# Top: tape with streak/exhaustion shading and trade markers
ax1.plot(xs, close, color=PALETTE["price"], lw=1.4, label="synthetic 5-min close (DEF)")
ax1.axvspan(-0.5, 5.5, color=PALETTE["band"], alpha=0.4, label="up-streak (5 bars)")
ax1.axvspan(4.5, 5.5, color=PALETTE["signal"], alpha=0.25, label="exhaustion bar")
ax1.axvspan(44.5, 51.5, color=PALETTE["band"], alpha=0.4, label="down-streak (6 bars)")
ax1.axvspan(50.5, 51.5, color=PALETTE["signal"], alpha=0.25)
ax1.scatter([6], [62.30], color=PALETTE["loss"], marker="v", s=100, zorder=5,
            label="short entry 62.30")
ax1.scatter([7], [62.74], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="stopped 62.74")
ax1.scatter([52], [61.10], color=PALETTE["profit"], marker="^", s=100, zorder=5,
            label="long entry 61.10")
ax1.scatter([74], [61.66], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="exit 61.66")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper right", ncol=2)
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net P&L — T4 ledger
trades = [
    ("Short", 62.30, 62.74, -199.76, -4.54, -204.30),
    ("Long",  61.10, 61.66, +177.52, -3.17, +174.35),
]
net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
comp = [7, 74]
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
ax2.annotate(f"session {cum_net[-1]:+.2f}", (74, cum_net[-1]),
             textcoords="offset points", xytext=(28, 0), ha="left", fontsize=10,
             color=PALETTE["zero"], weight="bold")
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("synthetic 5-min bars")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T062_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T062_example.png; final cum net =", cum_net[-1])
