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

rng = np.random.default_rng(127)

fig, axes = plt.subplots(3, 1, figsize=(10, 5.2), sharex=True)

# (title, shock_low, entry, exit_price, side, te, tx, net)
windows = [
    ("QLYQ — buy 2,000 @ 22.40 → 22.85 (2 half-lives)", 22.40, 22.40, 22.85, "long", 10, 34, "+768.00"),
    ("MNOP — buy 2,000 @ 15.10 → 15.28 (2 half-lives)", 15.10, 15.10, 15.28, "long", 10, 40, "+248.00"),
    ("VVRS — buy 2,000 @ 9.80 → 9.55 (stop, permanent leg)", 9.80, 9.80, 9.55, "long", 10, 34, "-612.00"),
]

for ax, (title, shock, p0, p1, side, te, tx, net) in zip(axes, windows):
    t = np.arange(0, 61)
    # shock dip at minute 8, entry at 10, then recovery (or continued fall for VVRS)
    dip = np.where(t < 8, p0 + (p0 - shock) * 0 + 0.0, np.nan)
    base = np.empty_like(t, dtype=float)
    pre = p0 + abs(p1 - p0) * 0.4  # pre-shock level slightly above entry
    for i, ti in enumerate(t):
        if ti <= 8:
            base[i] = pre - (pre - shock) * (ti / 8)
        elif ti <= te:
            base[i] = shock
        else:
            frac = min((ti - te) / max(tx - te, 1), 1.0)
            base[i] = p0 + (p1 - p0) * frac
    w = np.clip(np.abs(t - te) / 5.0, 0, 1) * np.clip(np.abs(t - tx) / 5.0, 0, 1)
    price = base + rng.normal(0, abs(p1 - p0) * 0.03 + 0.01, size=t.shape) * w
    price[te] = p0
    price[tx] = p1
    ax.plot(t, price, color=PALETTE["price"], lw=1.4)
    col = PALETTE["profit"] if float(net) > 0 else PALETTE["loss"]
    ax.scatter([te], [p0], s=90, marker="^", color=PALETTE["signal"],
               edgecolors="black", linewidths=0.7, zorder=5)
    ax.scatter([tx], [p1], s=90, marker="x", color=PALETTE["signal2"],
               linewidths=2.2, zorder=5)
    ax.annotate(f"net ${net}", xy=(tx, p1), xytext=(8, 12),
                textcoords="offset points", fontsize=8, color=col, weight="bold",
                arrowprops=dict(arrowstyle="-", color=col, lw=0.8))
    ax.axvline(8, color=PALETTE["signal2"], ls=":", lw=1, alpha=0.6)
    ax.set_title(title, fontsize=10, loc="left")
    ax.set_ylabel("Price ($)")

axes[-1].set_xlabel("Minutes from shock detection (entry at 10)")
fig.suptitle("T027 — Illiquidity Temporary-Impact Fade: synthetic shock recoveries (seed 127)",
             fontsize=13, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T027_example.png", bbox_inches="tight")
plt.close()
