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

# ---- SYNTHETIC MLOFI TAPE (seed stated in chapter text) ----
seed = 20260902
rng = np.random.default_rng(seed)
LEVELS = 5
BUCKETS = 10
# per-level attenuation of the common buying-pressure pulse (deeper = weaker)
level_w = np.array([1.0, 0.7, 0.5, 0.35, 0.25])
# common buying pressure per bucket (shares, synthetic)
pulse = rng.normal(0, 120, BUCKETS)
pulse = np.round(pulse, 1)
# level-wise OFI: pulse attenuated by level + idiosyncratic noise (shares)
ofi_levels = np.round(
    pulse[:, None] * level_w[None, :] + rng.normal(0, 25, (BUCKETS, LEVELS)), 1)
# integrated OFI: equal-weighted combination of the 5 level OFIs (shares)
iofi = np.round(ofi_levels.sum(axis=1), 1)
# contemporaneous mid-price change in ticks: 0.004 tick/share * iOFI + noise
dmid = np.round(0.004 * iofi + rng.normal(0, 0.35, BUCKETS), 2)

print("S002 synthetic tape, seed", seed)
print("bucket | pulse | OFI L1..L5 | iOFI (shares) | dMid (ticks)")
for b in range(BUCKETS):
    lv = " ".join(f"{v:7.1f}" for v in ofi_levels[b])
    print(f"{b+1:6d} | {pulse[b]:6.1f} | {lv} | {iofi[b]:8.1f} | {dmid[b]:7.2f}")
print("level vector of bucket 5:", ofi_levels[4])

# ---- FIGURE ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2))
fig.suptitle("S002 — Multi-level / integrated OFI: 10-bucket synthetic tape (L=5)")

# Panel 1: level-wise OFI bars for bucket 5
b5 = ofi_levels[4]
colors1 = [PALETTE["signal"] if v > 0 else PALETTE["price"] for v in b5]
bars = ax1.bar(range(1, LEVELS + 1), b5, color=colors1, edgecolor="black", linewidth=0.6)
ax1.axhline(0, color=PALETTE["zero"], linewidth=1)
for bar, v in zip(bars, b5):
    ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + (6 if v > 0 else -9),
             f"{v:.1f}", ha="center", va="bottom" if v > 0 else "top", fontsize=9)
ax1.set_xlabel("book level (1 = touch)")
ax1.set_ylabel("level OFI (shares)")
ax1.set_title("Level-wise OFI — bucket 5 (synthetic)")
ax1.set_xticks(range(1, LEVELS + 1))
ax1.text(0.02, 0.98,
         f"pulse = {pulse[4]:.1f} sh\nnoise attenuated by level",
         transform=ax1.transAxes, va="top", fontsize=8,
         bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

# Panel 2: integrated OFI vs contemporaneous mid-price change
ax2.scatter(iofi, dmid, s=64, color=PALETTE["signal2"], edgecolor="black",
            linewidth=0.6, label="bucket (iOFI, Δmid)")
for b in range(BUCKETS):
    ax2.annotate(str(b + 1), (iofi[b], dmid[b]), fontsize=7,
                 xytext=(3, 4), textcoords="offset points")
# OLS line through the 10 points
coef = np.polyfit(iofi, dmid, 1)
xs = np.array([iofi.min() - 10, iofi.max() + 10])
ax2.plot(xs, np.polyval(coef, xs), color=PALETTE["price"], linewidth=1.5,
         label=f"OLS: Δmid = {coef[1]:.3f} + {coef[0]:.4f}·iOFI")
ax2.axhline(0, color=PALETTE["zero"], linewidth=0.8)
ax2.set_xlabel("integrated OFI (shares)")
ax2.set_ylabel("mid-price change (ticks)")
ax2.set_title("Integrated OFI vs mid-price change (synthetic)")
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S002_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
