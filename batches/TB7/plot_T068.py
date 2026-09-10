"""T068 worked-example chart — MUST match the T4 table in batches/TB7/T068.md.
seed 168. Run from quant-signals-deep/: python3 batches/TB7/plot_T068.py
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

rng = np.random.default_rng(168)  # seed stated in T068.md T4

# ---- synthetic 5-min SPY tape anchored to the T4 numbers (FOMC day) ----
# bars 54-59: pre-release compression (13:30-14:00); bar 60: release 14:00,
# expansion bar 14:00-14:05 close 601.20; bar 61 open: long 601.35;
# bar 78 close against position; bar 79 open: exit 603.10.
N = 80
close = np.empty(N)
close[0:54] = np.linspace(599.50, 600.60, 54) + rng.normal(0, 0.10, 54)
close[54:60] = 600.60 + rng.normal(0, 0.07, 6)   # pre-release compression (T4)
close[60] = 601.20                               # expansion-bar close (T4)
close[61] = 601.35                               # long entry (T4)
close[62:78] = np.linspace(601.60, 603.05, 16) + rng.normal(0, 0.12, 16)
close[78] = 602.90                               # exhaustion: closes against (T4)
close[79] = 603.10                               # exit (T4)

xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T068 — Scheduled-Event Vol Expansion:\nsynthetic FOMC-day tape + P&L (seed 168)",
             fontweight="bold")

# Top: tape with compression window, release marker, expansion bar, trade markers
ax1.plot(xs, close, color=PALETTE["price"], lw=1.4, label="synthetic 5-min close (SPY)")
ax1.axvspan(53.5, 59.5, color=PALETTE["band"], alpha=0.45, label="pre-release compression")
ax1.axvspan(59.5, 60.5, color=PALETTE["signal"], alpha=0.25, label="expansion bar (14:00-14:05)")
ax1.axvline(60, color=PALETTE["signal2"], lw=1.4, ls="--", label="FOMC release 14:00 ET")
ax1.scatter([61], [601.35], color=PALETTE["profit"], marker="^", s=100, zorder=5,
            label="long 601.35 (14:10)")
ax1.scatter([79], [603.10], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="exit 603.10 (exhaustion)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left", ncol=2)
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net P&L — T4 ledger: gross +301.00, comm -1.72, net +299.28
trades = [("Long", 601.35, 603.10, +301.00, -1.72, +299.28)]
net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
ax2.plot([79], cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate(f"{net[0]:+.2f}", (79, cum_net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10, color=PALETTE["profit"], weight="bold")
ax2.annotate("Long 601.35\u2192603.10 x172", (79, cum_net[0]),
             textcoords="offset points", xytext=(0, -16), ha="center", fontsize=8,
             color=PALETTE["volume"])
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("synthetic 5-min bars (FOMC day)")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T068_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T068_example.png; final cum net =", cum_net[-1])
