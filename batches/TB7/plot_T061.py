"""T061 worked-example chart — MUST match the T4 table in batches/TB7/T061.md.
seed 161. Run from quant-signals-deep/: python3 batches/TB7/plot_T061.py
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

rng = np.random.default_rng(161)  # seed stated in T061.md T4

# ---- synthetic 5-min tape anchored to the T4 numbers ----
# bars 0..5  = 09:30-10:00 IB window; bar 6 = 10:00-10:05 breakout; bar 7 open = entry
N = 78
close = np.empty(N)
close[0:6] = np.linspace(50.10, 50.30, 6) + rng.normal(0, 0.03, 6)
close[6] = 50.46            # breakout close (T4)
close[7:66] = np.linspace(50.48, 50.89, 59) + rng.normal(0, 0.04, 59)
close[66:] = 50.89 + rng.normal(0, 0.03, N - 66)
close[7] = 50.48            # entry fill (T4)
close[65] = 50.89           # exit fill (T4)
high = close + np.abs(rng.normal(0, 0.05, N))
low = close - np.abs(rng.normal(0, 0.05, N))
high[2] = 50.40             # IBH (T4)
low[4] = 49.90              # IBL (T4)
IBH, IBL = 50.40, 49.90
ENTRY, EXIT = 50.48, 50.89
STOP = 50.275

xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T061 — Initial-Balance Expansion Trader:\nsynthetic session tape + P&L (seed 161)",
             fontweight="bold")

# Top: tape with IB box, breakout, entry/exit, stop
ax1.plot(xs, close, color=PALETTE["price"], lw=1.4, label="synthetic 5-min close (XYZ)")
ax1.axvspan(-0.5, 5.5, color=PALETTE["band"], alpha=0.45, label="initial balance (09:30-10:00)")
ax1.axhline(IBH, color=PALETTE["signal2"], lw=1.2, ls="--", label=f"IBH {IBH:.2f}")
ax1.axhline(IBL, color=PALETTE["signal2"], lw=1.2, ls="--", label=f"IBL {IBL:.2f}")
ax1.axhline(STOP, color=PALETTE["loss"], lw=1.0, ls=":", label=f"stop {STOP:.3f}")
ax1.scatter([6], [50.46], color=PALETTE["signal"], s=80, zorder=5,
            label="breakout close 50.46 (10:05)")
ax1.scatter([7], [ENTRY], color=PALETTE["profit"], marker="^", s=100, zorder=5,
            label=f"long entry {ENTRY:.2f} (10:10)")
ax1.scatter([65], [EXIT], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label=f"exit {EXIT:.2f} (15:00)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left", ncol=2)
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net P&L — T4 ledger: +399.75 gross, -9.75 comm, +390.00 net
trades = [("Long", ENTRY, EXIT, +399.75, -9.75, +390.00)]
net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
ax2.plot([65], cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=7,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
ax2.annotate(f"{net[0]:+.2f}", (65, cum_net[0]), textcoords="offset points",
             xytext=(0, 12), ha="center", fontsize=10, color=PALETTE["profit"], weight="bold")
ax2.annotate(f"Long {ENTRY:.2f}\u2192{EXIT:.2f} x975", (65, cum_net[0]),
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
plt.savefig("images/T061_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T061_example.png; final cum net =", cum_net[-1])
