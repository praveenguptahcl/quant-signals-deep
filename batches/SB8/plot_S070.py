"""S070 worked-example chart — synthetic straddle-implied vs realized move (seed 70)."""
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

# ---- SYNTHETIC WORKED EXAMPLE (seed 70) ----
# 10 synthetic earnings events (fictional tickers): implied move from the ATM
# straddle premium / underlying price; realized move = |post-earnings return|.
rng = np.random.default_rng(70)
ev = [f"E{i}" for i in range(1, 11)]
imp = np.array([6.2, 8.5, 4.1, 11.0, 5.4, 9.8, 3.6, 12.4, 7.1, 5.9])   # implied move %
real = np.array([3.8, 9.7, 5.2, 7.9, 2.9, 13.1, 2.2, 10.6, 4.4, 6.8])  # realized move %
hit = real < imp
print("event  implied%  realized%  hit(fade wins)")
for e, i, r, h in zip(ev, imp, real, hit):
    print(f"{e:>5}  {i:8.1f}  {r:9.1f}  {str(h):>5}")
print("hit rate:", hit.sum(), "/", len(hit), "=", round(hit.mean() * 100, 0), "% (SYNTHETIC)")

x = np.arange(len(ev))
w = 0.38
bars1 = plt.bar(x - w / 2, imp, w, color=PALETTE["price"], label="Implied move (straddle / price)")
colors = [PALETTE["profit"] if h else PALETTE["loss"] for h in hit]
bars2 = plt.bar(x + w / 2, real, w, color=colors)
plt.legend(handles=[bars1, plt.Rectangle((0, 0), 1, 1, color=PALETTE["profit"]),
                    plt.Rectangle((0, 0), 1, 1, color=PALETTE["loss"])],
           labels=["Implied move (straddle / price)",
                   "Realized move — fade wins (green)",
                   "Realized move — fade loses (red)"])
plt.text(0.98, 0.97,
         "After-cost arithmetic (verified):\n"
         "$0.40 option, $0.08 spread \u2192 2\u00d7$0.04 = $0.08 = 20% of premium\n"
         "$5.00 option, $0.10 spread \u2192 2\u00d7$0.05 = $0.10 = 2% of premium",
         transform=plt.gca().transAxes, ha="right", va="top", fontsize=8,
         color=PALETTE["zero"], bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#bbbbbb", alpha=0.9))
plt.title("S070 — Straddle-implied vs realized move: 10-event synthetic example")
plt.xlabel("Earnings event (fictional tickers)")
plt.ylabel("Move (%)")
plt.xticks(x, ev)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S070_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
