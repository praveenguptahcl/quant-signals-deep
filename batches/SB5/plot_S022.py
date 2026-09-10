import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

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

rng = np.random.default_rng(22)  # SEED 22 — stated in chapter text

# 30 synthetic 5-min bars, 09:30–12:00. Bars 1-12 = first hour (Initial Balance window).
O = np.array([100.00, 100.05, 100.15, 100.30, 100.35, 100.40, 100.45, 100.42, 100.30, 100.60] +
             [100.00] * 19 + [100.20])
H = np.array([100.20, 100.35, 100.50, 100.70, 100.60, 100.80, 100.70, 100.60, 100.90, 101.20] +
             [100.80] * 19 + [102.50])
L = np.array([99.90, 99.95, 100.00, 100.10, 100.20, 100.25, 100.30, 100.10, 100.20, 100.40] +
             [99.80] * 19 + [100.00])
C = np.array([100.05, 100.15, 100.30, 100.35, 100.40, 100.45, 100.42, 100.30, 100.60, 100.80] +
             [100.20] * 19 + [102.00])
base_vol = np.linspace(850, 670, 29).astype(int)
V = np.concatenate([base_vol + rng.integers(-15, 16, 29), [2500]])

IBH = H[:12].max()          # 101.20
IBL = L[:12].min()          # 99.80
IBR = IBH - IBL             # 1.40
excursion = C[29] - IBH     # 0.80
exc_pct = excursion / IBR * 100  # 57.14

print("bar | open | high | low | close | vol")
for i in range(30):
    print(f"{i+1:>3} | {O[i]:6.2f} | {H[i]:6.2f} | {L[i]:6.2f} | {C[i]:6.2f} | {V[i]:>4}")
print(f"IBH={IBH:.2f} IBL={IBL:.2f} IBR={IBR:.2f} excursion={excursion:.2f} ({exc_pct:.2f}% of IBR)")

x = np.arange(1, 31)
fig, (ax, axv) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                              gridspec_kw={"height_ratios": [3, 1]})
ax.axvspan(0.5, 12.5, color=PALETTE["band"], alpha=0.55, label="Initial Balance (bars 1-12)")
ax.axhline(IBH, color=PALETTE["signal"], lw=1.4, ls="--", label=f"IBH = {IBH:.2f}")
ax.axhline(IBL, color=PALETTE["signal2"], lw=1.4, ls="--", label=f"IBL = {IBL:.2f}")
for i in range(30):
    up = C[i] >= O[i]
    col = PALETTE["profit"] if up else PALETTE["loss"]
    ax.plot([x[i], x[i]], [L[i], H[i]], color=PALETTE["price"], lw=1.2)
    w = 0.62
    body = Rectangle((x[i] - w / 2, min(O[i], C[i])), w, abs(C[i] - O[i]) + 1e-9,
                     facecolor=col, edgecolor=PALETTE["price"], lw=0.8)
    ax.add_patch(body)
# highlight expansion bar 30
ax.add_patch(Rectangle((x[29] - 0.45, L[29] - 0.06), 0.9, H[29] - L[29] + 0.12,
                       facecolor="none", edgecolor=PALETTE["signal"], lw=2.2))
ax.annotate(f"expansion bar 30\nC−IBH = +{excursion:.2f} ({exc_pct:.1f}% of IBR)",
            xy=(x[29], C[29]), xytext=(22.5, 102.9),
            arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
            fontsize=9, color=PALETTE["signal"], weight="bold",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.9))
ax.text(6.5, 101.32, f"IBR = {IBR:.2f}", fontsize=9, ha="center",
        bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.85))
ax.set_ylabel("price (USD)")
ax.set_title("S022 — First-hour range expansion / initial balance: 30-bar synthetic 5-min tape (seed 22)")
ax.legend(loc="lower left", fontsize=8)

axv.bar(x, V, color=PALETTE["volume"], width=0.7)
axv.bar(x[29], V[29], color=PALETTE["signal"], width=0.7)
axv.set_ylabel("shares")
axv.set_xlabel("5-min bar (09:30 → 12:00)")
axv.set_xticks(np.arange(1, 31, 2))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S022_example.png", bbox_inches="tight")
plt.close()
