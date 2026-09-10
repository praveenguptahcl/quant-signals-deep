"""T069 worked-example chart — MUST match the T4 table in batches/TB7/T069.md.
seed 169. Run from quant-signals-deep/: python3 batches/TB7/plot_T069.py
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

rng = np.random.default_rng(169)  # seed stated in T069.md T4

# ---- synthetic 5-min STU day tape anchored to the T4 numbers ----
# day high 55.90, day low 54.20; 15:30 (bar 72) close 55.72 -> day_pos 0.894;
# bar 73 open: short 55.68; partial cover 55.57 (x153); MOC flatten 55.42 (x154, T4).
N = 79
close = np.empty(N)
close[0:60] = np.linspace(54.30, 55.60, 60) + rng.normal(0, 0.06, 60)
close[60:72] = np.linspace(55.60, 55.72, 12) + rng.normal(0, 0.04, 12)
close[72] = 55.72                                # 15:30 extreme read (T4)
close[73] = 55.68                                # short entry (T4)
close[74] = 55.60
close[75] = 55.57                                # partial-cover level (T4)
close[76] = 55.50
close[77] = 55.46
close[78] = 55.42                                # official close print / MOC (T4)

high = close + np.abs(rng.normal(0, 0.03, N))
low = close - np.abs(rng.normal(0, 0.03, N))
high[58] = 55.90                                 # day high (T4)
low[3] = 54.20                                   # day low (T4)

xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T069 — Late-Day Reversal into Close:\nsynthetic day tape + P&L (seed 169)",
             fontweight="bold")

# Top: day tape with high/low, extreme read, fade markers, MOC
ax1.plot(xs, close, color=PALETTE["price"], lw=1.4, label="synthetic 5-min close (STU)")
ax1.axhline(55.90, color=PALETTE["signal2"], lw=1.2, ls="--", label="day high 55.90")
ax1.axhline(54.20, color=PALETTE["signal2"], lw=1.2, ls="--", label="day low 54.20")
ax1.axvspan(71.5, 72.5, color=PALETTE["signal"], alpha=0.22,
            label="15:30 extreme read (day_pos 0.894)")
ax1.scatter([73], [55.68], color=PALETTE["loss"], marker="v", s=100, zorder=5,
            label="short 55.68 (15:35)")
ax1.scatter([75], [55.57], color=PALETTE["profit"], marker="x", s=80, zorder=5,
            label="cover half 55.57 (x153)")
ax1.scatter([78], [55.42], color=PALETTE["signal2"], marker="D", s=80, zorder=5,
            label="MOC flatten 55.42 (x154)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left", ncol=2)
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net P&L — T4 ledger: gross +56.87, comm -3.07, net +53.80
net = np.array([+53.80])
cum_net = np.cumsum(net)
ax2.plot([78], cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate(f"{net[0]:+.2f}", (78, cum_net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10, color=PALETTE["profit"], weight="bold")
ax2.annotate("Short 55.68 x307; cover 55.57 x153; MOC 55.42 x154", (78, cum_net[0]),
             textcoords="offset points", xytext=(0, -16), ha="center", fontsize=8,
             color=PALETTE["volume"])
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("synthetic 5-min bars (full RTH day)")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T069_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T069_example.png; final cum net =", cum_net[-1])
