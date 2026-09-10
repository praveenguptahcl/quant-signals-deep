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

rng = np.random.default_rng(191)  # seed 191 — stated in T091 text

# ---- Worked example (SYNTHETIC) — same numbers as T091 T4 ----
# GENL, 1-min synthetic tape, mid from 100.02; entry at t=8 fill @100.06,
# PT exit at t=24 fill @100.33. 12,000 sh; gross $3,240; costs $180; net +$3,060.
t = np.arange(25)
mid = np.array([100.02,100.03,100.04,100.05,100.04,100.05,100.06,100.06,
                100.06,100.08,100.10,100.12,100.14,100.16,100.18,100.19,
                100.20,100.21,100.22,100.23,100.24,100.26,100.28,100.30,100.34])
S_A = np.array([0.60,0.70,0.80,0.85,0.90,0.95,1.05,1.20,1.41,1.45,1.48,1.50,1.50,
                1.45,1.35,1.20,1.00,0.70,0.50,0.35,0.25,0.15,0.10,0.08,0.05])

ENTRY_T, EXIT_T = 8, 24
ENTRY_PX, EXIT_PX = 100.06, 100.33
SHARES = 12000
gross = (EXIT_PX - ENTRY_PX) * SHARES
costs = SHARES * 0.015
net = gross - costs
print(f"T091 ledger: gross={gross:.0f} costs={costs:.0f} net={net:.0f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [1.4, 1]})
fig.suptitle("T091 — Multi-Level Book-Pressure Swing: synthetic 25-min tape, one swing trade", fontweight="bold")

ax1.plot(t, mid, color=PALETTE["price"], lw=2, label="synthetic mid price (GENL)")
ax1.scatter([ENTRY_T], [ENTRY_PX], color=PALETTE["profit"], s=110, zorder=5,
            label=f"BUY 12,000 @ {ENTRY_PX:.2f} (fill t+1)")
ax1.scatter([EXIT_T], [EXIT_PX], color=PALETTE["signal"], s=110, marker="s", zorder=5,
            label=f"SELL 12,000 @ {EXIT_PX:.2f} (profit target)")
ax1.annotate(f"net +${net:,.0f}\n(gross ${gross:,.0f} − ${costs:,.0f} costs)",
             xy=(EXIT_T, EXIT_PX), xytext=(13, 100.24),
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             fontsize=9, color=PALETTE["zero"],
             bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax1.set_ylabel("mid price ($)")
ax1.legend(loc="upper left")

ax2.plot(t, S_A, color=PALETTE["signal2"], lw=2, label="book-pressure score S_A")
ax2.axhline(1.25, color=PALETTE["profit"], ls="--", lw=1.2, label="long entry +1.25 (example)")
ax2.axhline(-1.25, color=PALETTE["loss"], ls="--", lw=1.2, label="short entry −1.25 (example)")
ax2.axvspan(0, 8, color=PALETTE["band"], alpha=0.35, label="persistence window (8 bars)")
ax2.set_xlabel("minutes since 10:00 (synthetic)")
ax2.set_ylabel("S_A (z-score)")
ax2.legend(loc="upper right", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T091_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
