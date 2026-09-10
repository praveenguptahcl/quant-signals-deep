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

# ---- VERIFIED HY worked example (operator-verified, grand sum = 17 exact) ----
# X: 11 returns on [0,1]...[10,11]; Y: 11 returns on [0.5,1.5]...[10.5,11.5];
# the [0,0.5] Y stub return is 0 (omitted) — see chapter S4/S10 for the wording caveat.
DX = np.array([2, 1, -1, 1, 2, 0, 0, 2, -1, 1, 1], dtype=float)   # ΔX_i, i=1..11
DY = np.array([2, 1, -1, 0, 2, -1, 1, 2, -2, 1, 1], dtype=float)  # ΔY_j, j=1..11
n = len(DX)

# Overlap: X interval (i-1, i] overlaps Y interval (j-0.5, j+0.5] iff j in {i-1, i} (i>=2),
# and i=1 overlaps only j=1 (the [0,0.5] stub return is 0 and contributes 0).
overlap = np.zeros((n, n))
for i in range(n):
    for j in range(n):
        if j == i or (i > 0 and j == i - 1):
            overlap[i, j] = 1.0
grid = DX[:, None] * DY[None, :] * overlap
row_sum = grid.sum(axis=1)
grand = float(grid.sum())
print("row contributions:", ", ".join(f"{v:.0f}" for v in row_sum))
print(f"grand sum [X,Y](HY) = {grand:.0f}")
assert grand == 17.0

fig, (ax1, ax2) = plt.subplots(1, 2, gridspec_kw={"width_ratios": [3, 1.4]})
cmap = plt.cm.get_cmap("RdYlGn")
disp = np.ma.masked_where(overlap == 0, grid)
im = ax1.imshow(disp, cmap=cmap, vmin=-4, vmax=6, aspect="equal")
for i in range(n):
    for j in range(n):
        if overlap[i, j]:
            val = grid[i, j]
            ax1.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=8,
                     color="white" if abs(val) > 3 else "black", weight="bold")
ax1.set_xticks(range(n))
ax1.set_yticks(range(n))
ax1.set_xticklabels([f"{j+1}" for j in range(n)], fontsize=8)
ax1.set_yticklabels([f"{i+1}" for i in range(n)], fontsize=8)
ax1.set_xlabel("Y return j (interval [j-0.5, j+0.5])")
ax1.set_ylabel("X return i (interval [i-1, i])")
ax1.set_title("Overlap products ΔXᵢ·ΔYⱼ (blank = no overlap)", fontsize=11)
fig.colorbar(im, ax=ax1, shrink=0.9, label="ΔXᵢ·ΔYⱼ")

colors = [PALETTE["loss"] if v < 0 else PALETTE["profit"] for v in row_sum]
ax2.barh(range(n), row_sum, color=colors, edgecolor=PALETTE["zero"], lw=0.8)
ax2.set_yticks(range(n))
ax2.set_yticklabels([f"{i+1}" for i in range(n)], fontsize=8)
ax2.invert_yaxis()
ax2.axvline(0, color=PALETTE["zero"], lw=1)
ax2.set_xlabel("Row contribution")
ax2.set_title("Row sums → [X,Y]̂(HY) = 17", fontsize=11)
for i, v in enumerate(row_sum):
    ax2.text(v + (0.15 if v >= 0 else -0.15), i, f"{v:.0f}", va="center",
             ha="left" if v >= 0 else "right", fontsize=8)
ax2.set_xlim(-3.2, 7.2)

fig.suptitle("S060 — Hayashi–Yoshida overlap grid: 11 verified return pairs (grand sum 17)",
             fontsize=13, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S060_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
