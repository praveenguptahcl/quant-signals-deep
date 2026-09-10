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

rng = np.random.default_rng(26)  # SEED 26 — stated in chapter text

# 13 half-hour buckets x 60 synthetic days (worked-example table prints the last 12).
# Same-bucket day-to-day persistence: phi = 0.35 for buckets 1 and 13 (HKS-style
# morning/close periodicity), 0.05 elsewhere. U-shaped volatility across the day.
DAYS = 60
phi = np.full(13, 0.05)
phi[0] = 0.35
phi[12] = 0.35
sig = 0.004 * np.array([1.50, 0.90, 0.75, 0.70, 0.65, 0.60, 0.60, 0.60, 0.65, 0.70, 0.75, 0.90, 1.40])

R = np.zeros((13, DAYS))
for h in range(13):
    burn = rng.normal(0, sig[h], 50)
    for t in range(1, 50):
        burn[t] = phi[h] * burn[t - 1] + rng.normal(0, sig[h])
    prev = burn[-1]
    for t in range(DAYS):
        cur = phi[h] * prev + rng.normal(0, sig[h])
        R[h, t] = cur
        prev = cur

R12 = R[:, DAYS - 12:]  # 12-day worked-example window printed in chapter text
r1 = R12[0] * 10000   # first half-hour return, bps
r13 = R12[12] * 10000 # last half-hour return, bps
print("day | r1 (bps) | r13 (bps)")
for t in range(12):
    print(f"{DAYS - 12 + t + 1:>3} | {r1[t]:8.2f} | {r13[t]:9.2f}")

# same-bucket lag-1 autocorrelation per bucket (full 60-day window)
ac = np.array([np.corrcoef(R[h, :-1], R[h, 1:])[0, 1] for h in range(13)])
print("bucket lag-1 autocorr:", np.round(ac, 3).tolist())

# Gao-style predictive regression: r13,t = alpha + beta * r1,t (full 60-day window)
x = R[0] * 10000 - (R[0] * 10000).mean()
y = R[12] * 10000
beta = (x * (y - y.mean())).sum() / (x * x).sum()
alpha = y.mean() - beta * (R[0] * 10000).mean()
yhat = alpha + beta * (R[0] * 10000)
r2 = 1 - ((y - yhat) ** 2).sum() / ((y - y.mean()) ** 2).sum()
print(f"regression: alpha={alpha:.2f} bps, beta(x100)={beta * 100:.2f}, R2={r2 * 100:.2f}%")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2),
                               gridspec_kw={"width_ratios": [3, 2]})
vmax = np.abs(R).max()
im = ax1.imshow(R, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
ax1.set_xlabel("synthetic day")
ax1.set_ylabel("half-hour bucket")
ax1.set_xticks(range(12))
ax1.set_xticklabels([f"d{t+1}" for t in range(12)], rotation=45)
ax1.set_yticks(range(13))
ax1.set_yticklabels([f"b{h+1}" for h in range(13)])
ax1.set_title("half-hour returns (red = +)")
ax1.grid(False)
cbar = fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
cbar.set_label("return (decimal)")
ax1.annotate("", xy=(11, 0), xytext=(11, 1),
             arrowprops=dict(arrowstyle="-", color="black", lw=1.5))
ax1.text(11.2, 0.2, "bucket 1 persists", fontsize=8)
ax1.text(11.2, 12.2, "bucket 13 persists", fontsize=8)

bars = ax2.bar(range(1, 14), ac, color=PALETTE["price"])
bars[0].set_color(PALETTE["signal"])
bars[12].set_color(PALETTE["signal"])
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.set_xlabel("half-hour bucket")
ax2.set_ylabel("same-bucket lag-1 autocorrelation")
ax2.set_title("day-to-day persistence per bucket")
ax2.set_xticks(range(1, 14))
ax2.grid(True, axis="y")

fig.suptitle("S026 — Half-hour return periodicity: 13-bucket x 12-day synthetic heatmap (seed 26)",
             fontsize=13, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S026_example.png", bbox_inches="tight")
plt.close()
