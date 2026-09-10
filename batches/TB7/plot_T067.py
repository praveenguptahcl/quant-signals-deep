"""T067 worked-example chart — MUST match the T4 table in batches/TB7/T067.md.
seed 167. Run from quant-signals-deep/: python3 batches/TB7/plot_T067.py
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

rng = np.random.default_rng(167)  # seed stated in T067.md T4

# ---- synthetic 5-min PQR tape anchored to the T4 numbers ----
# bar 24 = event bar (10:40-10:45, headline 10:42, close 25.60);
# bar 25 open: long entry 25.66; bar 43 close below AVWAP; bar 44 open: exit 26.10.
N = 60
close = np.empty(N)
close[0:24] = np.linspace(25.00, 25.20, 24) + rng.normal(0, 0.05, 24)
close[24] = 25.60                                # event-bar close (T4)
close[25] = 25.66                                # long entry (T4)
close[26:43] = np.linspace(25.75, 26.15, 17) + rng.normal(0, 0.05, 17)
close[43] = 26.02                                # closes below AVWAP (T4)
close[44] = 26.10                                # exit (T4)
close[45:] = 26.10 + rng.normal(0, 0.04, N - 45)

# AVWAP anchored at bar 24 (synthetic: volume-weighted drift near price)
avwap = np.full(N, np.nan)
anchor_path = np.linspace(25.30, 26.05, 20)      # 24..43
avwap[24:44] = anchor_path
# force the cross: bar 42 above, bar 43 below
avwap[42] = 26.00
avwap[43] = 26.06

xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T067 — Anchored-VWAP Event Trader:\nsynthetic tape + AVWAP + P&L (seed 167)",
             fontweight="bold")

# Top: tape with event bar, AVWAP, entry/exit
ax1.plot(xs, close, color=PALETTE["price"], lw=1.4, label="synthetic 5-min close (PQR)")
ax1.plot(xs, avwap, color=PALETTE["signal2"], lw=1.6, label="AVWAP (anchored at event bar)")
ax1.axvspan(23.5, 24.5, color=PALETTE["signal"], alpha=0.22, label="event bar (headline 10:42)")
ax1.annotate("guidance raised\n(S093: BULLISH)", (24, 25.60),
             textcoords="offset points", xytext=(-64, -34), fontsize=8,
             color=PALETTE["signal"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"], lw=1))
ax1.scatter([25], [25.66], color=PALETTE["profit"], marker="^", s=100, zorder=5,
            label="long 25.66 (10:50)")
ax1.scatter([44], [26.10], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="exit 26.10 (AVWAP cross)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left", ncol=2)
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net P&L — T4 ledger: gross +143.88, comm -3.27, net +140.61
trades = [("Long", 25.66, 26.10, +143.88, -3.27, +140.61)]
net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
ax2.plot([44], cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate(f"{net[0]:+.2f}", (44, cum_net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10, color=PALETTE["profit"], weight="bold")
ax2.annotate("Long 25.66\u219226.10 x327", (44, cum_net[0]),
             textcoords="offset points", xytext=(0, -16), ha="center", fontsize=8,
             color=PALETTE["volume"])
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
plt.savefig("images/T067_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T067_example.png; final cum net =", cum_net[-1])
