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

# ---- synthetic worked-example decomposition (hardcoded; matches S015.md S4) ----
rng = np.random.default_rng(15)  # fixed seed; values are hardcoded below
half_spread = 0.020  # S/2 from OLS (S = $0.04)
components = [
    ("Adverse selection\n(α·S/2, α = 0.30)", 0.006, PALETTE["loss"]),
    ("Inventory\n(β·S/2, β = 0.20)",          0.004, PALETTE["signal2"]),
    ("Order processing\n((1−α−β)·S/2 = 0.50·S/2)", 0.010, PALETTE["volume"]),
]
assert abs(sum(v for _, v, _ in components) - half_spread) < 1e-12

fig, ax = plt.subplots()
bottom = 0.0
for label, value, color in components:
    ax.bar("traded half-spread\n(S/2 = $0.020)", value, bottom=bottom, color=color,
           edgecolor=PALETTE["zero"], linewidth=0.8, width=0.55, label=label)
    pct = value / half_spread * 100
    ax.text(0, bottom + value / 2, f"${value:.3f}\n({pct:.0f}%)",
            ha="center", va="center", fontsize=10, weight="bold", color="white")
    bottom += value
ax.set_ylim(0, half_spread * 1.15)
ax.set_title("S015 — Huang–Stoll spread decomposition (8-observation synthetic regression sample)")
ax.set_ylabel("component of traded half-spread ($)")
ax.legend(loc="upper right")
ax.text(0.02, 0.98,
        "OLS: ΔM_t = (S/2)·Q_{t−1} + (α+β)(S/2)·Q_t + e_t\n"
        "c₁ = 0.020 ⇒ S = $0.04; c₂ = 0.010 ⇒ α+β = 0.50\n"
        "second stage splits α = 0.30 (adverse selection), β = 0.20 (inventory)",
        transform=ax.transAxes, va="top", ha="left", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=PALETTE["price"], alpha=0.92))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S015_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S015_example.png")
