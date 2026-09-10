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

# ---- SYNTHETIC 5-LEVEL BOOK SNAPSHOTS (seed stated in chapter text) ----
seed = 20260905
rng = np.random.default_rng(seed)
SNAPS, LEVELS = 8, 5
# bid sizes: slightly larger than ask sizes on average -> mild positive pressure,
# decaying with depth
bid = rng.integers(600, 1400, size=(SNAPS, LEVELS)) + np.array(
    [400, 300, 200, 100, 0])[None, :] * 0 + np.round(
    (rng.normal(120, 80, SNAPS)[:, None]) * np.array([1.0, 0.8, 0.6, 0.4, 0.3]), 0)
ask = rng.integers(600, 1400, size=(SNAPS, LEVELS)) + np.round(
    (rng.normal(60, 80, SNAPS)[:, None]) * np.array([1.0, 0.8, 0.6, 0.4, 0.3]), 0)
bid = np.clip(bid.astype(int), 150, None)
ask = np.clip(ask.astype(int), 150, None)
sum_bid = bid.sum(axis=1)
sum_ask = ask.sum(axis=1)
bp = (sum_bid - sum_ask) / (sum_bid + sum_ask)  # static book pressure, L=5

print("S005 synthetic snapshots, seed", seed)
print("snap | sum_bid | sum_ask | book pressure BP")
for s in range(SNAPS):
    print(f"{s+1:4d} | {sum_bid[s]:7d} | {sum_ask[s]:7d} | {bp[s]:+.4f}")
print("snapshot 4 bid sizes (L1..L5):", bid[3].tolist())
print("snapshot 4 ask sizes (L1..L5):", ask[3].tolist())
print("snapshot 4: sum_bid =", sum_bid[3], "sum_ask =", sum_ask[3],
      "BP =", round(bp[3], 4))

# ---- FIGURE ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2))
fig.suptitle("S005 — Multi-level book pressure: 8 synthetic snapshots (L=5)")

# Panel 1: per-level depth bars for snapshot 4
x = np.arange(1, LEVELS + 1)
w = 0.38
b1 = ax1.bar(x - w / 2, bid[3], width=w, color=PALETTE["profit"], edgecolor="black",
             linewidth=0.6, label="bid depth (shares)")
b2 = ax1.bar(x + w / 2, ask[3], width=w, color=PALETTE["loss"], edgecolor="black",
             linewidth=0.6, label="ask depth (shares)")
for v in list(zip(bid[3], ask[3])):
    pass
ax1.set_xlabel("book level (1 = touch)")
ax1.set_ylabel("resting depth (shares)")
ax1.set_title("Depth by level — snapshot 4 (synthetic)")
ax1.set_xticks(x)
ax1.legend()
ax1.text(0.98, 0.96,
         f"Σbid = {sum_bid[3]:,}\nΣask = {sum_ask[3]:,}\nBP = {bp[3]:+.3f}",
         transform=ax1.transAxes, va="top", ha="right", fontsize=9,
         bbox=dict(boxstyle="round", facecolor="white", alpha=0.85))

# Panel 2: book pressure across the 8 snapshots
ax2.plot(range(1, SNAPS + 1), bp, marker="o", color=PALETTE["signal2"],
         linewidth=2, markersize=7, markerfacecolor="white",
         markeredgewidth=1.5, label="BP (L=5)")
ax2.axhline(0, color=PALETTE["zero"], linewidth=1)
ax2.axhspan(0.2, 0.6, color=PALETTE["profit"], alpha=0.12)
ax2.axhspan(-0.6, -0.2, color=PALETTE["loss"], alpha=0.12)
ax2.text(7.2, 0.42, "example long tilt", color=PALETTE["profit"], fontsize=8)
ax2.text(7.2, -0.42, "example short tilt", color=PALETTE["loss"], fontsize=8)
ax2.set_xlabel("snapshot #")
ax2.set_ylabel("book pressure BP = (ΣQb−ΣQa)/(ΣQb+ΣQa)")
ax2.set_title("Book pressure across snapshots (synthetic)")
ax2.set_xticks(range(1, SNAPS + 1))
ax2.set_ylim(-0.6, 0.6)
ax2.legend()

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S005_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
