"""T002 worked-example chart — MUST match the T4 table in batches/TB1/T002.md.
seed 102. Run from quant-signals-deep/: python3 batches/TB1/plot_T002.py
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

rng = np.random.default_rng(102)  # seed stated in T002.md T4

# Trade table — identical to T002.md T4 (dollars). shares = 5,000 per trade.
# (dir, entry, exit, gross, commission, net); entry/exit are fill prices.
trades = [
    ("Long",  80.010, 80.025,  +75.00, -50.00,  +25.00),
    ("Long",  80.015, 80.020,  +25.00, -50.00,  -25.00),
    ("Short", 80.020, 80.008,  +60.00, -50.00,  +10.00),
    ("Long",  80.010, 80.002,  -40.00, -50.00,  -90.00),
    ("Short", 80.025, 80.015,  +50.00, -50.00,    0.00),
    ("Long",  80.005, 80.020,  +75.00, -50.00,  +25.00),
]
HALF = 0.005  # synthetic half-spread in dollars

ticks_per_trade = 40
mid, midxs, entry_ticks, exit_ticks = [], [], [], []
t0 = 0
for d, entry, ex, gross, comm, net in trades:
    if d == "Long":
        m0, m1 = entry - HALF, ex + HALF
    else:
        m0, m1 = entry + HALF, ex - HALF
    seg = np.linspace(m0, m1, ticks_per_trade) + rng.normal(0, 0.0012, ticks_per_trade)
    seg[0], seg[-1] = m0, m1
    xx = np.arange(t0, t0 + ticks_per_trade)
    mid.extend(seg); mid.append(np.nan)
    xx = list(xx) + [np.nan]
    midxs.extend(xx)
    entry_ticks.append(t0)
    exit_ticks.append(t0 + ticks_per_trade - 1)
    t0 += ticks_per_trade
mid = np.array(mid); midxs = np.array(midxs)

net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
comp_ticks = np.array(exit_ticks)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, gridspec_kw={"hspace": 0.25,
                                                              "height_ratios": [1.15, 1]})
fig.suptitle("T002 — Microprice Fair-Value Scalper: synthetic 6-trade P&L walk\n(seed 102)",
             fontweight="bold")

ax1.plot(midxs, mid, color=PALETTE["price"], lw=1.2, label="synthetic mid-price (per-trade segments)")
for i, (et, xt) in enumerate(zip(entry_ticks, exit_ticks)):
    d = trades[i][0]
    ax1.scatter([et], [mid[et]], color=PALETTE["profit"] if d == "Long" else PALETTE["loss"],
                marker="^" if d == "Long" else "v", s=90, zorder=5)
    ax1.scatter([xt], [mid[xt]], color=PALETTE["signal"], marker="x", s=70, zorder=5)
ax1.set_ylabel("price ($)")
ax1.tick_params(labelbottom=False)

ax2.plot(comp_ticks, cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=5,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
for i, ct in enumerate(comp_ticks):
    n = net[i]
    col = PALETTE["profit"] if n > 0 else (PALETTE["loss"] if n < 0 else PALETTE["volume"])
    ax2.annotate(f"{n:+.0f}", (ct, cum_net[i]), textcoords="offset points",
                 xytext=(0, 10 if cum_net[i] >= 0 else -16), ha="center", fontsize=9,
                 color=col, weight="bold")
    d, entry, ex = trades[i][0], trades[i][1], trades[i][2]
    ax2.annotate(f"{d[0]} {entry:.3f}\u2192{ex:.3f}", (ct, cum_net[i]),
                 textcoords="offset points", xytext=(0, -14), ha="center", fontsize=7,
                 color=PALETTE["volume"])
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("synthetic time (ticks) — annotations: per-trade net ($); grey captions: entry\u2192exit fill prices")
# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T002_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T002_example.png; final cum net =", cum_net[-1])
