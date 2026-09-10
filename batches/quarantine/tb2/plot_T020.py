"""T020 worked-example chart. Run: python3 batches/TB2/plot_T020.py  (cwd: quant-signals-deep)"""
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

rng = np.random.default_rng(120)  # stated seed; table values are fixed by hand

# ---- T4 worked-example numbers (exact) ----
# cost = shares * $0.03 + $1.00 per round trip (half-spread + commission)
inst = [
    # id, side, features, p_hat, mult, shares, outcome, gross, cost, net_meta, net_naive
    (1, "Long",  "quiet vol, RVOL 1.8", 0.82, 0.64, 320, "upper hit (+$3.00/sh)",
     960.00, 10.60, 949.40, 1484.00),
    (2, "Long",  "news spike, wide spread", 0.48, 0.00, 0, "VETOED (would hit lower)",
     0.00, 0.00, 0.00, -1016.00),
    (3, "Short", "RSI-2=94, trend down", 0.53, 0.00, 0, "VETOED (would hit upper)",
     0.00, 0.00, 0.00, -1516.00),
    (4, "Long",  "gap-fade setup", 0.63, 0.26, 130, "vertical (+$0.80/sh)",
     104.00, 4.90, 99.10, 384.00),
    (5, "Short", "crowded, high ADV", 0.88, 0.76, 380, "lower hit (+$2.00/sh)",
     760.00, 12.40, 747.60, 984.00),
]
labels = [f"#{r[0]}\n{r[1]}\np={r[3]:.2f}" for r in inst]
meta_net = np.array([r[9] for r in inst])
naive_net = np.array([r[10] for r in inst])
cum_meta, cum_naive = np.cumsum(meta_net), np.cumsum(naive_net)

x = np.arange(len(inst))
w = 0.36
fig, ax = plt.subplots()
b1 = ax.bar(x - w / 2, naive_net, w, color=PALETTE["volume"], alpha=0.85,
            label="Naive (500 sh every bet)")
b2 = ax.bar(x + w / 2, meta_net, w,
            color=[PALETTE["profit"] if v >= 0 else PALETTE["loss"] for v in meta_net],
            label="Meta-gated (veto if p<0.55; size=(p-0.5)/0.5)")
ax.axhline(0, color=PALETTE["zero"], lw=1)
for i, v in enumerate(meta_net):
    ax.text(x[i] + w / 2, v + (55 if v >= 0 else -95), f"${v:,.0f}",
            ha="center", fontsize=8.5,
            color=PALETTE["profit"] if v > 0 else PALETTE["loss"], weight="bold")
ax.text(0.02, 0.96,
        f"Cumulative net: meta \\${cum_meta[-1]:,.2f} vs naive \\${cum_naive[-1]:,.2f}\n"
        "Meta vetoed 2 full losers (-\\$2,532 avoided) and sized 3 bets by p-hat.",
        transform=ax.transAxes, fontsize=9, va="top",
        bbox=dict(boxstyle="round", fc="white", ec="#7f8c8d", alpha=0.9))
ax.set_xticks(x); ax.set_xticklabels(labels)
ax.set_xlabel("Primary-signal instance (seed 120)")
ax.set_ylabel("Net P&L per instance ($)")
ax.set_title("T020 — Triple-Barrier + Meta-Labeling Overlay: naive vs meta-gated net P&L")
ax.legend(loc="lower right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T020_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print(f"saved images/T020_example.png | seed 120 | meta total {cum_meta[-1]:.2f} | "
      f"naive total {cum_naive[-1]:.2f}")
