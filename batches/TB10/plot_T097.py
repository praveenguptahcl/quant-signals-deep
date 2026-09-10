import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
import os

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

rng = np.random.default_rng(197)  # seed 197 — stated in T097 text

# ---- Worked example (SYNTHETIC) — same numbers as T097 T4 ----
# 6 fades of sharp 5-30 min moves, 1,000 sh each, 1.5c RT cost ($15/trade).
# gross per trade: +310, +180, −140, +290, +260, +40 = +$940; costs $90; net +$850.
names = ["F1", "F2", "F3", "F4", "F5", "F6"]
gross_t = np.array([310, 180, -140, 290, 260, 40], dtype=float)
net_t = gross_t - 15.0
cum_net = np.cumsum(net_t)
print(f"T097 ledger: gross={gross_t.sum():.0f} net={net_t.sum():.0f}")

x = np.arange(len(names))
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [1.2, 1]})
fig.suptitle("T097 — Sub-Hour Microstructure Reversal Scalper: 6 fades, thin edge (synthetic)",
             fontweight="bold")

colors = [PALETTE["profit"] if v >= 0 else PALETTE["loss"] for v in net_t]
bars = ax1.bar(x, net_t, color=colors, edgecolor=PALETTE["zero"], lw=0.8)
ax1.axhline(0, color=PALETTE["zero"], lw=1)
for i, v in enumerate(net_t):
    ax1.text(i, v + (18 if v >= 0 else -26), f"${v:+.0f}", ha="center", fontsize=9,
             fontweight="bold", color=PALETTE["zero"])
ax1.set_ylabel("net per fade ($)")
ax1.set_title("per-trade net (1,000 sh, $15 RT cost each)", fontsize=11)

ax2.plot(x, cum_net, color=PALETTE["price"], marker="o", lw=2.2, label="cumulative net P&L")
ax2.fill_between(x, cum_net, 0, color=PALETTE["band"], alpha=0.4)
ax2.set_xticks(x, names)
ax2.set_xlabel("fade sequence (synthetic)")
ax2.set_ylabel("cumulative net ($)")
ax2.annotate(f"session net +${net_t.sum():,.0f}\n(gross +${gross_t.sum():,.0f} − $90 costs)",
             xy=(5, cum_net[-1]), xytext=(2.6, 950),
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             fontsize=9, bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T097_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
