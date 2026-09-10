"""T065 worked-example chart — MUST match the T4 table in batches/TB7/T065.md.
seed 165. Run from quant-signals-deep/: python3 batches/TB7/plot_T065.py
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

rng = np.random.default_rng(165)  # seed stated in T065.md T4

# ---- synthetic tape anchored to the T4 numbers ----
# pre-open: prior close 90.00; 09:15 indicative ~90.40; 09:25 indicative 90.45 (P_hat, T4).
# official open print 90.42 (MOO fill, T4); 10:00 exit 90.73 (T4).
pre_xs = np.array([0, 1, 2])                       # 09:15, 09:20, 09:25
indic = np.array([90.40, 90.43, 90.45])

N = 6                                              # 09:30-10:00, 5-min bars
close = np.linspace(90.42, 90.73, N) + rng.normal(0, 0.03, N)
close[0] = 90.42                                   # official open print = MOO fill (T4)
close[-1] = 90.73                                  # 10:00 exit (T4)
xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=False,
                               gridspec_kw={"hspace": 0.35, "height_ratios": [1.15, 1]})
fig.suptitle("T065 — Open-Auction Imbalance Continuation:\nsynthetic pre-open + tape + P&L (seed 165)",
             fontweight="bold")

# Top: pre-open indicative (left) + continuous tape (right) on a shared time feel
ax1.plot(pre_xs, indic, color=PALETTE["signal2"], lw=1.6, marker="o", ms=5,
         label="indicative match price (pre-open)")
ax1.plot(xs + 4, close, color=PALETTE["price"], lw=1.4, marker="o", ms=4,
         label="synthetic 5-min close (ABC)")
ax1.axhline(90.00, color=PALETTE["volume"], lw=1.0, ls=":", label="prior close 90.00")
ax1.scatter([4], [90.42], color=PALETTE["profit"], marker="^", s=110, zorder=5,
            label="MOO buy 90.42 (official open print)")
ax1.scatter([9], [90.73], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="exit 90.73 (10:00)")
ax1.annotate("imb 250k @09:25\n(+50 bps)", (2, 90.45), textcoords="offset points",
             xytext=(10, 12), fontsize=8, color=PALETTE["signal2"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal2"], lw=1))
ax1.set_ylabel("price ($)")
ax1.set_xlabel("synthetic time (pre-open prints 0-2; 5-min bars 4-9)")
ax1.legend(loc="upper left", ncol=2)

# Bottom: cumulative net P&L — T4 ledger: gross +193.75, comm -6.25, net +187.50
trades = [("Long", 90.42, 90.73, +193.75, -6.25, +187.50)]
net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
ax2.plot([1], cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate(f"{net[0]:+.2f}", (1, cum_net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10, color=PALETTE["profit"], weight="bold")
ax2.annotate("Long 90.42\u219290.73 x625 (MOO)", (1, cum_net[0]),
             textcoords="offset points", xytext=(0, -16), ha="center", fontsize=8,
             color=PALETTE["volume"])
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("trade")
ax2.set_xlim(0, 2)
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T065_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T065_example.png; final cum net =", cum_net[-1])
