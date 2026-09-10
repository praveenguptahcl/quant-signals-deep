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

rng = np.random.default_rng(125)

fig, axes = plt.subplots(3, 1, figsize=(10, 5.2), sharex=True)

# Trade windows: minutes from 15:20 ET; entry at minute 10 (15:30), exit at 38/37 (15:58/15:57)
windows = [
    ("ZVXR — long 1,000 @ 62.10 → 62.32", 62.10, 62.32, "long", 10, 38, "+204.00"),
    ("QLYQ — short 1,000 @ 38.40 → 38.21", 38.40, 38.21, "short", 10, 37, "+174.00"),
    ("MNOP — VETOED (zLR +0.3, p-hat 0.51)", 25.00, 25.03, "veto", 10, 38, "no trade"),
]

for ax, (title, p0, p1, side, te, tx, net) in zip(axes, windows):
    t = np.arange(0, 45)
    base = p0 + (p1 - p0) * np.clip((t - te) / max(tx - te, 1), 0, 1)
    w = np.clip(np.abs(t - te) / 6.0, 0, 1) * np.clip(np.abs(t - tx) / 6.0, 0, 1)
    price = base + rng.normal(0, 0.02 * p0 / 60, size=t.shape) * w
    price[te] = p0
    price[tx] = p1
    ax.plot(t, price, color=PALETTE["price"], lw=1.4)
    if side == "veto":
        ax.scatter([te], [p0], s=110, marker="X", color=PALETTE["volume"],
                   edgecolors="black", linewidths=0.8, zorder=5)
        ax.annotate("VETOED by S007+S086", xy=(te, p0), xytext=(16, 10),
                    textcoords="offset points", fontsize=8, color=PALETTE["volume"],
                    weight="bold")
    else:
        mk = "^" if side == "long" else "v"
        col = PALETTE["profit"]
        ax.scatter([te], [p0], s=90, marker=mk, color=PALETTE["signal"],
                   edgecolors="black", linewidths=0.7, zorder=5)
        ax.scatter([tx], [p1], s=90, marker="x", color=PALETTE["signal2"],
                   linewidths=2.2, zorder=5)
        ax.annotate(f"net ${net}", xy=(tx, p1), xytext=(8, 12),
                    textcoords="offset points", fontsize=8, color=col, weight="bold",
                    arrowprops=dict(arrowstyle="-", color=col, lw=0.8))
    ax.axvline(te, color=PALETTE["signal"], ls=":", lw=1, alpha=0.6)
    ax.set_title(title, fontsize=10, loc="left")
    ax.set_ylabel("Price ($)")

axes[-1].set_xlabel("Minutes from 15:20 ET (entry at 10 = 15:30)")
fig.suptitle("T025 — Trade-Classification Trend Filter: synthetic entry windows (seed 125)",
             fontsize=13, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T025_example.png", bbox_inches="tight")
plt.close()
