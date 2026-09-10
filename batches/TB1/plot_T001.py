"""T001 worked-example chart — MUST match the T4 table in batches/TB1/T001.md.
seed 101. Run from quant-signals-deep/: python3 batches/TB1/plot_T001.py
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

rng = np.random.default_rng(101)  # seed stated in T001.md T4

# Trade table — identical to T001.md T4 (dollars). shares = 10,000 per trade.
# (dir, entry, exit, gross, commission, net); entry/exit are fill prices.
trades = [
    ("Long",  50.010, 50.030, +200.00, -100.00, +100.00),
    ("Short", 50.030, 50.010, +200.00, -100.00, +100.00),
    ("Long",  50.010, 49.990, -200.00, -100.00, -300.00),
    ("Long",  50.020, 50.030, +100.00, -100.00,    0.00),
    ("Short", 50.040, 50.040,    0.00, -100.00, -100.00),
    ("Long",  50.000, 50.025, +250.00, -100.00, +150.00),
]
HALF = 0.005  # synthetic half-spread in dollars

# Per-trade synthetic mid segments (NaN-separated so segments don't connect).
ticks_per_trade = 40
mid, xs = [], []
entry_xy, exit_xy = [], []
t0 = 0
for d, entry, ex, gross, comm, net in trades:
    m0, m1 = (entry - HALF, ex + HALF) if d == "Long" else (entry + HALF, ex - HALF)
    seg = np.linspace(m0, m1, ticks_per_trade) + rng.normal(0, 0.0012, ticks_per_trade)
    seg[0], seg[-1] = m0, m1
    xx = np.arange(t0, t0 + ticks_per_trade)
    mid.extend(seg); mid.append(np.nan)
    xs.extend(xx); xs.append(np.nan)
    entry_xy.append((t0, m0)); exit_xy.append((t0 + ticks_per_trade - 1, m1))
    t0 += ticks_per_trade
mid = np.array(mid); xs = np.array(xs)

net = np.array([t[5] for t in trades])
cum_net = np.cumsum(net)
comp_ticks = np.array([xt for (xt, _) in exit_xy])

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T001 — OFI + Queue-Imbalance Directional Scalper:\nsynthetic 6-trade P&L walk (seed 101)",
             fontweight="bold")

# Top: synthetic mid segments with entry/exit markers
ax1.plot(xs, mid, color=PALETTE["price"], lw=1.2, label="synthetic mid-price (per-trade segments)")
seen_long, seen_short = False, False
for i, ((et, em), (xt, xm)) in enumerate(zip(entry_xy, exit_xy)):
    d = trades[i][0]
    ax1.scatter([et], [em], color=PALETTE["profit"] if d == "Long" else PALETTE["loss"],
                marker="^" if d == "Long" else "v", s=90, zorder=5,
                label=("long entry" if d == "Long" and not seen_long
                       else "short entry" if d == "Short" and not seen_short else None))
    seen_long |= d == "Long"; seen_short |= d == "Short"
    ax1.scatter([xt], [xm], color=PALETTE["signal"], marker="x", s=70, zorder=5,
                label="exit" if i == 0 else None)
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left")
ax1.tick_params(labelbottom=False)

# Bottom: cumulative net equity, one point per completed trade
ax2.plot(comp_ticks, cum_net, color=PALETTE["price"], lw=1.8, marker="o", ms=5,
         label="cumulative net P&L")
ax2.axhline(0, color=PALETTE["zero"], lw=1, ls="--")
for i, ct in enumerate(comp_ticks):
    n = net[i]
    col = PALETTE["profit"] if n > 0 else (PALETTE["loss"] if n < 0 else PALETTE["volume"])
    ax2.annotate(f"{n:+.0f}", (ct, cum_net[i]), textcoords="offset points",
                 xytext=(0, 10), ha="center", fontsize=9, color=col, weight="bold")
    d, entry, ex = trades[i][0], trades[i][1], trades[i][2]
    ax2.annotate(f"{d[0]} {entry:.3f}\u2192{ex:.3f}", (ct, cum_net[i]),
                 textcoords="offset points", xytext=(0, -14), ha="center", fontsize=7,
                 color=PALETTE["volume"])
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("synthetic time (ticks) — annotations: per-trade net ($); grey captions: entry\u2192exit fill prices")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T001_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T001_example.png; final cum net =", cum_net[-1])
