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

rng = np.random.default_rng(198)  # seed 198 — stated in T098 text

# ---- Worked example (SYNTHETIC) — same numbers as T098 T4 ----
# Setup A (jump-validated): LM stat 5.8 > 4.5 (example), RVOL 3.2x.
# The 5-bar drift window t+1..t+5 must close before entry -> entry at the t+6 open.
# Jump flagged at bar 30 -> long 5,000 @ 75.16 (bar-36 open, t+6 fill), exit 76.05.
# gross = (76.05 - 75.16) x 5000 = $4,450; costs 2c RT x 5000 = $100; net +$4,350.
# Setup B: momentum without jump (LM 2.1) -> VETOED (would have lost −$1,300, illustrative).
# Setup C: jump but RVOL 0.8x (thin) -> VETOED.
n = 78
bars = np.arange(n)
px = 75.00 + np.cumsum(rng.standard_normal(n) * 0.03)
px[30:] += np.linspace(0, 1.05, n - 30)   # jump ignition at bar 30
px[62:] -= np.linspace(0, 0.45, n - 62)   # partial give-back
px[36] = 75.16                             # pin t+6 entry bar to the T4 fill price
px[60] = 76.05                             # pin exit bar to the T4 target
rvol = np.full(n, 1.0) + rng.standard_normal(n) * 0.15
rvol[28:40] = 3.2 + rng.standard_normal(12) * 0.2

gross = (76.05 - 75.16) * 5000
costs = 5000 * 0.02
net = gross - costs
print(f"T098 ledger: gross={gross:.0f} costs={costs:.0f} net={net:.0f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [1.5, 1]})
fig.suptitle("T098 — Jump-Validated Momentum Ignition: trade only the jumps (synthetic)",
             fontweight="bold")

ax1.plot(bars, px, color=PALETTE["price"], lw=1.6, label="INNO (synthetic $)")
ax1.axvline(30, color=PALETTE["signal2"], ls=":", lw=1.6, label="Lee–Mykland jump flag (stat 5.8, example)")
ax1.scatter([36], [75.16], color=PALETTE["profit"], s=110, zorder=5,
            label="BUY 5,000 @ 75.16 (fill t+6 open)")
ax1.scatter([60], [76.05], color=PALETTE["signal"], s=110, marker="s", zorder=5,
            label="SELL @ 76.05 — net +$4,350")
ax1.scatter([50], [px[50]], color=PALETTE["loss"], s=110, marker="x", zorder=5,
            label="Setup B VETOED: momentum, no jump (LM 2.1)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left", fontsize=7)

ax2.bar(bars, rvol, color=PALETTE["volume"], width=0.9, label="RVOL (× trailing mean)")
ax2.axhline(2.0, color=PALETTE["loss"], ls="--", lw=1.2, label="RVOL gate 2.0× (example)")
ax2.axvspan(28, 40, color=PALETTE["band"], alpha=0.4, label="funded window")
ax2.set_xlabel("1-min bar index (synthetic)")
ax2.set_ylabel("RVOL (×)")
ax2.legend(loc="upper right", fontsize=7)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T098_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
