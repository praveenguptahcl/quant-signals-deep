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

# T028 worked example — Spread-Decomposition Router (SYNTHETIC, seed 128)
# Seed recorded so the script is reproducible; the 8 router decisions are the
# hand-verified rows in the chapter's T4 table (identical numbers).
rng = np.random.default_rng(128)
OUT = "/home/hatch/workspace/quant-signals-deep/images/T028_example.png"

# Per-candidate-row router state (all $ numbers below are synthetic):
# decision = POST when alpha_hat < 0.35 (example) AND quoted >= 1 tick AND
#            trailing realized spread > 0; else STAND DOWN.
# net per filled trade = shares * (Sr/2) + shares * rebate,
#   Sr in cents, shares = 200, maker rebate = $0.0020/share (example).
labels   = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"]
Sr_cents = np.array([1.2, 0.8, -0.6, np.nan, 1.0, -1.4, np.nan, 0.6])  # realized spread kept (cents)
alpha    = np.array([0.28, 0.31, 0.33, 0.52, 0.29, 0.36, 0.61, 0.25])  # S015 AS share
decision = np.array(["POST", "POST", "POST", "STAND DOWN", "POST", "POST",
                     "STAND DOWN", "POST"])
shares, rebate = 200, 0.0020
filled = decision == "POST"
# 200 shares x (Sr_cents/2 cents per share) / 100 = Sr_cents dollars, plus 200 x $0.0020 = $0.40
net = np.where(filled, Sr_cents + 0.40, 0.0)
cum = np.cumsum(net)
assert abs(cum[-1] - 4.00) < 1e-9, cum[-1]  # +$4.00 net over 8 candidates

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                              gridspec_kw={"height_ratios": [1.2, 1]})
fig.suptitle("T028 — Spread-Decomposition Router: per-trade realized spread kept "
             "and cumulative net P&L (8 synthetic router decisions, seed 128)",
             fontsize=13, fontweight="bold", y=0.98)

x = np.arange(len(labels))
colors = [PALETTE["profit"] if (f and s >= 0) else (PALETTE["loss"] if f else "#bdc3c7")
          for f, s in zip(filled, np.nan_to_num(Sr_cents))]
ax1.bar(x, np.nan_to_num(Sr_cents), color=colors, edgecolor="#2c3e50")
ax1.axhline(0, color=PALETTE["zero"], linewidth=1)
ax1.set_xticks(x); ax1.set_xticklabels(labels)
ax1.set_ylabel("realized spread kept (cents/share)")
ax1.set_title("Realized spread kept per filled trade (S014); grey = stood down (S015 alpha too high)")
for i in range(len(labels)):
    ax1.text(i, 0.06, f"alpha={alpha[i]:.2f}", ha="center", fontsize=8, color="#2c3e50")

ax2.step(x, cum, where="mid", color=PALETTE["price"], linewidth=2.2,
         label="cumulative net P&L (incl. $0.40/trade maker rebate)")
ax2.scatter(x, cum, c=[PALETTE["profit"] if f else "#bdc3c7" for f in filled],
            s=60, zorder=5, edgecolors="#2c3e50")
ann = {0: "+$1.60", 1: "+$1.20", 2: "-$0.20", 3: "$0.00", 4: "+$1.40",
       5: "-$1.00", 6: "$0.00", 7: "+$1.00"}
for i, a in ann.items():
    ax2.annotate(a, (x[i], cum[i]), textcoords="offset points", xytext=(0, 12),
                 ha="center", fontsize=8.5, fontweight="bold",
                 color=PALETTE["profit"] if float(a[2:]) > 0
                 else (PALETTE["loss"] if float(a[2:]) < 0 else "#7f8c8d"))
ax2.axhline(0, color=PALETTE["zero"], linewidth=1)
ax2.set_xticks(x); ax2.set_xticklabels(labels)
ax2.set_xlabel("router decision (event order)")
ax2.set_ylabel("cumulative net P&L ($)")
ax2.legend(loc="upper left")
ax2.text(0.02, 0.95, "T4 blocked: alpha 0.52 / 0.61 > 0.35 (example gate) — "
         "the router's value is the trades it refuses",
         transform=ax2.transAxes, fontsize=8.5, color="#7f8c8d")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig(OUT, bbox_inches="tight")
plt.close()
print("wrote", OUT, "| net total $%.2f" % cum[-1])
