"""T075 worked-example chart \u2014 MUST match the T4 table in batches/TB8/T075.md.
seed 175. Run from quant-signals-deep/: python3 batches/TB8/plot_T075.py
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

rng = np.random.default_rng(175)  # seed stated in T075.md T4

# ---- synthetic hourly tape anchored to the T4 numbers ----
N = 48
rng = np.random.default_rng(175)
price = 67200 + np.cumsum(rng.normal(0, 18, N))
price[6] = 67200.0    # short entry (T4)
price[36] = 67176.0   # exit (T4)
funding = np.linspace(120, 4, N) + rng.normal(0, 4, N)  # annualized %; normalizes
funding = np.clip(funding, 2, 130)
xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T075 \u2014 Crypto Funding-Rate Reversal:\nsynthetic hourly tape + P&L (seed 175)",
             fontweight="bold")

ax1.plot(xs, price, color=PALETTE["price"], lw=1.4, label="synthetic hourly BTC perp")
ax1.scatter([6], [67200.0], color=PALETTE["loss"], marker="v", s=100, zorder=5,
            label="short 0.5 BTC 67200.00 (funding 120% ann.)")
ax1.scatter([36], [67176.0], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="exit 67176.00 (funding < 10%)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left", ncol=2)
ax1b = ax1.twinx()
ax1b.plot(xs, funding, color=PALETTE["signal2"], lw=1.1, ls="--",
          label="annualized funding % (S095)")
ax1b.axhline(40, color=PALETTE["signal2"], lw=0.8, ls=":",
             label="crowded threshold 40%")
ax1b.set_ylabel("funding (% ann.)")
ax1b.legend(loc="upper right", fontsize=8)
ax1.tick_params(labelbottom=False)

# Bottom: T4 ledger: +6.00 gross, costs 8.50 fees + 4.50 spread + 3.00 impact = -16.00, net -10.00
net = np.array([-10.00])
ax2.plot([36], net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate("-10.00", (36, net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10,
             color=PALETTE["loss"], weight="bold")
ax2.annotate("short 67200\u219267176 x0.5 BTC", (36, net[0]),
             textcoords="offset points", xytext=(0, -16), ha="center", fontsize=8,
             color=PALETTE["volume"])
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("synthetic hourly bars")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data \u2014 not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T075_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T075_example.png; final cum net =", net[-1])
