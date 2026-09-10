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

rng = np.random.default_rng(183)  # T083 seed — stated in chapter text

# ---- T083 worked-example inputs (SYNTHETIC) ----
# Fictional retail-heavy name "RTE", mid $40.00. Retail = sub-penny prints; odd-lot <100 sh.
# 10 synthetic trades: (side, shares, price, retail?)
trades = [
    ("buy", 40, 40.006, True), ("buy", 40, 40.008, True), ("sell", 100, 39.995, False),
    ("buy", 40, 40.005, True), ("buy", 200, 40.010, False), ("buy", 40, 40.007, True),
    ("sell", 40, 39.992, True), ("buy", 40, 40.006, True), ("buy", 40, 40.009, True),
    ("buy", 40, 40.004, True),
]
rb = sum(s for d, s, p, r in trades if r and d == "buy")
rs = sum(s for d, s, p, r in trades if r and d == "sell")
imb = (rb - rs) / (rb + rs)
mu, sd = 0.05, 0.30  # 20-day retail-imbalance baseline (example)
z = (imb - mu) / sd
print(f"retail buys={rb}, sells={rs}, imbalance={imb:.3f}, z=({imb:.3f}-{mu})/{sd}={z:.2f}")
print("trigger: z >= +1.5 (example) ->", "FADE SHORT" if z >= 1.5 else "no trade")
# Huang-Stoll (S015): adverse-selection share theta=0.30 < 0.40 cap (example) -> gate passes
theta_hs = 0.30
print(f"Huang-Stoll adverse-selection share={theta_hs:.2f} < 0.40 cap -> cost gate PASSES")

# Internalizer shorts 4 clips of 200 sh at ask 40.01 into retail buy flow (fills at t+1),
# covers at the bounce 39.99 (S047). Clip 3 drifts: cover at 39.96 (adverse selection).
clips = [
    {"n": 1, "short": 40.01, "cover": 39.99},
    {"n": 2, "short": 40.01, "cover": 39.99},
    {"n": 3, "short": 40.01, "cover": 40.03},  # adverse selection: cover drifts UP
    {"n": 4, "short": 40.01, "cover": 39.99},
]
shares = 200
rebate = 0.002  # $/share maker rebate (example)
gross = sum((c["short"] - c["cover"]) * shares for c in clips)
reb = rebate * shares * len(clips) * 2  # both legs maker
# clip-3 adverse drift already inside its gross; isolate for reporting:
adv = (40.03 - 39.99) * shares
net = gross + reb
print(f"gross capture=${gross:.2f} (incl. -${adv:.2f} adverse on clip 3), rebates=${reb:.2f}, NET=${net:.2f}")

# retail imbalance z path for the plot (build-up across the 10 trades)
zpath = np.array([0.10, 0.42, 0.31, 0.62, 0.55, 0.88, 0.80, 1.12, 1.31, z])
# simpler: cumulative net after each clip incl. rebates
per_clip_net = [ (c["short"]-c["cover"])*shares + rebate*shares*2 for c in clips ]
cum = np.cumsum(per_clip_net)
print("per-clip net:", [f"${x:.2f}" for x in per_clip_net], "cum:", [f"${x:.2f}" for x in cum])

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), gridspec_kw={"height_ratios": [3, 2]})
fig.suptitle("T083 — Retail-Flow Internalizer Fade: synthetic retail tape + fade P&L (seed 183)",
             fontweight="bold")
x = np.arange(1, 11)
ax1.plot(x, zpath, color=PALETTE["signal"], lw=1.6, marker="o", ms=4, label="retail-imbalance z (synthetic)")
ax1.axhline(1.5, color=PALETTE["zero"], ls="--", lw=1.2, label="fade trigger z=+1.5 (example)")
ax1.axhline(0, color=PALETTE["zero"], lw=0.8)
ax1.annotate("z=1.50 -> fade SHORT\n4 x 200 sh @ ask 40.01", xy=(10, z), xytext=(6.2, 2.1),
             fontsize=8, arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax1.set_xlim(1, 10); ax1.set_xlabel("trade # (synthetic tape)")
ax1.set_ylabel("retail imbalance z")
ax1.legend(loc="upper left")

xc = np.arange(1, 5)
ax2.bar(xc, per_clip_net, color=[PALETTE["profit"] if v >= 0 else PALETTE["loss"] for v in per_clip_net])
ax2.plot(xc, cum, color=PALETTE["price"], marker="o", ms=5, lw=1.8, label="cumulative net P&L")
for i, v in enumerate(cum):
    ax2.text(xc[i], v + 0.25, f"${v:.2f}", ha="center", fontsize=8, fontweight="bold")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.set_xticks(xc); ax2.set_xticklabels(["clip 1", "clip 2", "clip 3\n(adverse)", "clip 4"])
ax2.set_ylabel("P&L ($)")
ax2.set_title(f"Internalizer fade: 800 sh net ${net:.2f} (synthetic)", fontsize=11)
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T083_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
