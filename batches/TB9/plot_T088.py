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

rng = np.random.default_rng(188)  # T088 seed — stated in chapter text

# ---- T088 worked-example inputs (SYNTHETIC) ----
# 5 primary families: naive CV AUC vs purged-CV AUC (synthetic leak-inflation demo)
fams = ["M1 microstruct", "M2 momentum", "M3 reversal", "M4 vol regime", "M5 news"]
auc_naive = np.array([0.61, 0.58, 0.59, 0.56, 0.57])
auc_purged = np.array([0.55, 0.53, 0.54, 0.52, 0.51])
stack_w = np.array([0.38, 0.22, 0.26, 0.06, 0.08])  # logistic stacking weights (example)
print("family | naive AUC | purged AUC | leak inflation | stack weight")
for f, an, ap, sw in zip(fams, auc_naive, auc_purged, stack_w):
    print(f"{f:14s} | {an:.2f} | {ap:.2f} | +{an-ap:.2f} | {sw:.2f}")
print("stack weights sum:", stack_w.sum())
# Meta-label (S086): synthetic precision 0.46 -> 0.58, veto keeps 62% of bets
prec0, prec1, keep = 0.46, 0.58, 0.62
print(f"meta-label precision {prec0:.2f} -> {prec1:.2f}, keeps {keep:.0%} of bets")
# Synthetic sleeve: 20 meta-approved bets, 11 wins x $120, 9 losses x $100
wins, avg_w, losses, avg_l = 11, 120.0, 9, 100.0
gross = wins * avg_w - losses * avg_l
costs = 0.01 * 100 * 20 * 2  # $0.01/share x 100 sh x 20 bets x 2 legs
net = gross - costs
print(f"gross=${gross:.0f}, costs=${costs:.0f}, NET=${net:.0f} (synthetic, NOT forward alpha)")
# synthetic per-bet path for the walk
bets = np.array([120, -100, 120, 120, -100, 120, -100, 120, -100, 120,
                 120, -100, -100, 120, 120, -100, 120, -100, 120, -100], dtype=float) - 2.0  # -$2/bet cost
cum = np.cumsum(bets)
print("walk check: final =", cum[-1], "target net =", net)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), gridspec_kw={"height_ratios": [2, 3]})
fig.suptitle("T088 — Full-Stack Signal Ensemble: synthetic leak demo + meta-labeled sleeve (seed 188)",
             fontweight="bold")
x = np.arange(len(fams)); w = 0.35
ax1.bar(x - w / 2, auc_naive, w, color=PALETTE["signal"], label="naive k-fold AUC (leaky)")
ax1.bar(x + w / 2, auc_purged, w, color=PALETTE["price"], label="purged+embargo AUC")
for i in range(len(fams)):
    ax1.annotate("", xy=(x[i], auc_naive[i]), xytext=(x[i], auc_purged[i]),
                 arrowprops=dict(arrowstyle="->", color=PALETTE["zero"], lw=1.2))
ax1.axhline(0.5, color=PALETTE["zero"], ls=":", lw=1)
ax1.set_xticks(x); ax1.set_xticklabels(fams, rotation=12, ha="right")
ax1.set_ylabel("OOS AUC (synthetic)")
ax1.set_ylim(0.45, 0.68)
ax1.legend(loc="upper right", fontsize=8)
ax1.text(0.02, 0.90, "arrows = leak inflation removed\nby purge+embargo (S088)", transform=ax1.transAxes,
         fontsize=8, va="top", bbox=dict(boxstyle="round", fc="white", alpha=0.9))

ax2.plot(np.arange(1, 21), cum, color=PALETTE["price"], lw=1.8, marker="o", ms=4,
         label="cumulative net P&L (synthetic)")
ax2.fill_between(np.arange(1, 21), cum, 0, where=cum >= 0, color=PALETTE["profit"], alpha=0.15)
ax2.fill_between(np.arange(1, 21), cum, 0, where=cum < 0, color=PALETTE["loss"], alpha=0.15)
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.text(20, cum[-1] + 12, f"net ${net:.0f}\n(11W x $120 - 9L x $100 - ${costs:.0f} costs)",
         ha="right", fontsize=9, fontweight="bold")
ax2.set_xlim(1, 20); ax2.set_xlabel("meta-approved bet # (synthetic)")
ax2.set_ylabel("cumulative net P&L ($)")
ax2.legend(loc="upper left", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T088_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
