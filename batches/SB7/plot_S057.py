"""S057 plot: cash-and-carry basis decomposition waterfall (4.0% gross -> 0.1% net)."""
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

# Verified arithmetic (duck.ai Q-SB7-3, hand-checked): gross 4.0% annualized basis,
# less financing 3.2%, basket+execution 0.4%, ops/dividend leakage 0.3% => net 0.1%.
steps = [
    ("Gross annualized\nbasis (over fair)", +4.0, True),
    ("Financing the\nbasket (r = 5.0%)", -3.2, False),
    ("Basket + execution\n(spreads, commissions)", -0.4, False),
    ("Ops / dividend\nleakage", -0.3, False),
    ("Net carry\n(annualized)", 0.0, True),  # total bar
]
values = np.array([s[1] for s in steps])
labels = [s[0] for s in steps]
is_total = np.array([s[2] for s in steps])

fig, ax = plt.subplots()
ax.set_title("S057 — Cash-and-carry: basis decomposition waterfall (synthetic, annualized)")

pos = np.arange(len(steps))
cum = 0.0
for i, (lab, val, total) in enumerate(steps):
    if total and i == 0:
        bottom, height, color = 0, val, PALETTE["price"]
        cum = val
    elif total:
        bottom, height, color = 0, cum, PALETTE["profit"] if cum >= 0 else PALETTE["loss"]
    else:
        bottom, height, color = (cum + val, -val) if val < 0 else (cum, val), val, PALETTE["loss"]
        if val < 0:
            bottom, height = cum + val, -val
        else:
            bottom, height = cum, val
        cum += val
    ax.bar(pos[i], height, bottom=bottom, width=0.62, color=color, edgecolor="white")
    if not total:
        ax.text(pos[i], bottom + height / 2, f"{val:+.1f}%", ha="center", va="center",
                fontsize=10, color="white", weight="bold")
    else:
        ax.text(pos[i], height + (0.12 if height >= 0 else -0.12), f"{cum:.1f}%",
                ha="center", va="bottom" if height >= 0 else "top",
                fontsize=11, weight="bold", color=PALETTE["zero"])
    # connector
    if i < len(steps) - 1 and not total:
        nxt = cum
        ax.plot([pos[i] + 0.31, pos[i + 1] - 0.31], [nxt, nxt], color=PALETTE["zero"],
                linestyle=":", linewidth=1)

ax.axhline(0, color=PALETTE["zero"], linewidth=1)
ax.set_xticks(pos)
ax.set_xticklabels(labels, fontsize=9)
ax.set_xlim(-0.7, len(steps) - 0.3)
ax.set_ylabel("annualized return (%)")
ax.text(0.98, 0.96,
        "S = 5000, T = 90d, F* = 5039.61, F observed = 5088.92\n"
        "gross basis = (F - F*)/S x 365/90 = 4.00%\n"
        "4.00 - 3.20 - 0.40 - 0.30 = 0.10% net",
        transform=ax.transAxes, fontsize=8, va="top", ha="right",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.9))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S057_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
