"""T077 worked-example chart \u2014 MUST match the T4 table in batches/TB8/T077.md.
seed 177. Run from quant-signals-deep/: python3 batches/TB8/plot_T077.py
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

rng = np.random.default_rng(177)  # seed stated in T077.md T4

# ---- synthetic daily basis tape anchored to the T4 numbers ----
N = 30
rng = np.random.default_rng(177)
basis = np.linspace(720, 50, N) + rng.normal(0, 25, N)  # quoted basis $/BTC
basis[2] = 720.0   # entry (T4)
basis[28] = 50.0   # unwind (T4)
funding_cum = np.linspace(0, 2100, N)  # funding collected, short perp leg
xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T077 \u2014 Crypto Basis Cash-and-Carry:\nsynthetic basis tape + P&L (seed 177)",
             fontweight="bold")

ax1.plot(xs, basis, color=PALETTE["price"], lw=1.4,
         label="synthetic quoted basis $/BTC (spot 67200 / perp 67920)")
ax1.axhline(470, color=PALETTE["signal2"], lw=1.2, ls="--",
            label="attainable-basis hurdle (~12% ann.)")
ax1.scatter([2], [720.0], color=PALETTE["profit"], marker="^", s=100, zorder=5,
            label="enter pair: long 10 spot / short 10 perp")
ax1.scatter([28], [50.0], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="unwind pair at basis 50")
ax1.set_ylabel("basis ($/BTC)")
ax1.legend(loc="upper right")
ax1.tick_params(labelbottom=False)

# Bottom: T4 ledger: +6100.00 gross, -2750.00 costs, +3350.00 net
net = np.array([3350.00])
ax2.plot([28], net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate("+3350.00", (28, net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10,
             color=PALETTE["profit"], weight="bold")
ax2.annotate("basis 720\u219250 x10 BTC + funding 2100", (28, net[0]),
             textcoords="offset points", xytext=(0, -16), ha="center", fontsize=8,
             color=PALETTE["volume"])
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("synthetic daily bars (30-day hold)")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data \u2014 not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T077_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T077_example.png; final cum net =", net[-1])
