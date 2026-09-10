"""T063 worked-example chart — MUST match the T4 table in batches/TB7/T063.md.
seed 163. Run from quant-signals-deep/: python3 batches/TB7/plot_T063.py
All numbers synthetic.
"""
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

rng = np.random.default_rng(163)  # seed stated in T063.md T4

# ---- synthetic 5-min GHI tape anchored to the T4 numbers ----
# bars 24-29: compression window (11:00-11:25); bar 30: stretch close 44.83, z=+3.5;
# bar 31 open: short entry 44.80; bar 64 close: z recross, bar 65 open: cover 44.36.
N = 80
z = np.zeros(N)
z[0:24] = rng.normal(0, 0.8, 24)
z[24:30] = rng.normal(0, 0.35, 6)      # compression window
z[30] = 3.5                            # stretch trigger (T4)
z[31:64] = np.linspace(3.2, 0.4, 33) + rng.normal(0, 0.25, 33)
z[64] = 0.4                            # recross below +0.5 (T4)
z[65:] = rng.normal(0, 0.5, N - 65)

close = np.empty(N)
close[0] = 44.20
for i in range(1, N):
    close[i] = close[i - 1] + 0.18 * (z[i] - z[i - 1]) * 0.35 + rng.normal(0, 0.02)
close[30] = 44.83                      # stretch close (T4)
close[31] = 44.80                      # short entry (T4)
close[65] = 44.36                      # cover (T4)
# smooth the path between anchors
close[32:65] = np.linspace(44.80, 44.36, 33) + rng.normal(0, 0.05, 33)
close[65] = 44.36

xs = np.arange(N)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"hspace": 0.25, "height_ratios": [1.15, 1]})
fig.suptitle("T063 — Stretched-Move Z-Score Fade:\nsynthetic tape + z-score + P&L (seed 163)",
             fontweight="bold")

# Top: price with compression shading and fade markers
ax1.plot(xs, close, color=PALETTE["price"], lw=1.4, label="synthetic 5-min close (GHI)")
ax1.axvspan(23.5, 29.5, color=PALETTE["band"], alpha=0.45, label="compression window")
ax1.scatter([31], [44.80], color=PALETTE["loss"], marker="v", s=100, zorder=5,
            label="short entry 44.80")
ax1.scatter([65], [44.36], color=PALETTE["signal"], marker="x", s=90, zorder=5,
            label="cover 44.36 (z-recross)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper right")
ax1.tick_params(labelbottom=False)

# Bottom: z-score with trigger lines; session net annotated
ax2.plot(xs, z, color=PALETTE["signal2"], lw=1.3, label="z-score (close-MA20)/sd20")
ax2.axhline(2.5, color=PALETTE["signal"], lw=1.2, ls="--", label="stretch trigger +/-2.5")
ax2.axhline(-2.5, color=PALETTE["signal"], lw=1.2, ls="--")
ax2.axhline(0.5, color=PALETTE["volume"], lw=1.0, ls=":", label="exit recross +/-0.5")
ax2.axhline(-0.5, color=PALETTE["volume"], lw=1.0, ls=":")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.scatter([30], [3.5], color=PALETTE["signal"], s=80, zorder=5,
            label="z=+3.5 trigger")
ax2.set_ylabel("z-score")
ax2.set_xlabel("synthetic 5-min bars")
ax2.legend(loc="upper right", ncol=2)
# T4 ledger: gross +325.60, commission -7.40, net +318.20
ax2.text(0.02, 0.06,
         "session net +$318.20  (short 44.80\u219244.36 x740; gross +325.60, comm -7.40)",
         transform=ax2.transAxes, fontsize=9, color=PALETTE["profit"], weight="bold",
         bbox=dict(facecolor="white", alpha=0.85, edgecolor=PALETTE["profit"]))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T063_example.png", bbox_inches="tight")
plt.close()
print("wrote images/T063_example.png; final cum net = 318.2")
