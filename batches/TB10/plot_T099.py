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

rng = np.random.default_rng(199)  # seed 199 — stated in T099 text

# ---- Worked example (SYNTHETIC) — same numbers as T099 T4 ----
# EURO ADR vs home-market ordinary, FX-adjusted premium. Signal at close day 3 (+1.9% >= +1.5%
# example entry threshold) -> fill day 4 open: SHORT 3,000 ADR @ 52.40 / LONG 3,000 ordinary @ 51.40.
# Exit signal close day 12 (premium +0.6% <= +0.75% example exit) -> fill day 13 open: ADR 50.90, ordinary 50.60.
# gross = 3000 x (1.00 − 0.30) = $2,100.
# costs: borrow 10d x 3000 x 52.40 x 1.8%/360 = $78.60; trading $60 + $60; FX $25 -> $223.60. net +$1,876.
days = np.arange(15)
prem = np.array([2.4, 2.2, 2.1, 1.9, 1.7, 1.5, 1.4, 1.2, 1.1, 1.0, 0.9, 0.7, 0.6, 0.6, 0.5])

gross = 3000 * (1.00 - 0.30)
borrow = 10 * 3000 * 52.40 * 0.018 / 360
trade_fx = 60 + 60 + 25
costs = borrow + trade_fx
net = gross - costs
print(f"T099 ledger: gross={gross:.0f} borrow={borrow:.2f} costs={costs:.2f} net={net:.0f}")

fig, ax = plt.subplots(figsize=(10, 5.2))
fig.suptitle("T099 — ADR + Borrow Corporate Arb: FX-adjusted premium convergence (synthetic)",
             fontweight="bold")

ax.plot(days, prem, color=PALETTE["price"], marker="o", lw=2, label="FX-adjusted ADR premium (%)")
ax.axhline(1.5, color=PALETTE["profit"], ls="--", lw=1.3, label="entry ≥ +1.5% (example)")
ax.axhline(0.75, color=PALETTE["signal"], ls="--", lw=1.3, label="exit ≤ +0.75% (example)")
ax.axvspan(4, 13, color=PALETTE["band"], alpha=0.3, label="position window (t+1 fills)")
ax.scatter([3], [1.9], color=PALETTE["signal2"], s=110, zorder=5, label="signal day 3 (close)")
ax.annotate("SHORT 3,000 ADR @ 52.40\nLONG 3,000 ordinary @ 51.40\n(fill day 4 open)",
            xy=(4, 1.7), xytext=(6.5, 2.6), arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
            fontsize=9, bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax.annotate("cover day 13 open\nADR 50.90 / ordinary 50.60\nspread 1.00 → 0.30",
            xy=(13, 0.6), xytext=(9.5, 0.05), arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
            fontsize=9, bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax.set_xlabel("session (synthetic)")
ax.set_ylabel("FX-adjusted premium (%)")
ax.legend(loc="upper right", fontsize=8)
fig.text(0.5, 0.01,
         f"gross +${gross:,.0f} − borrow ${borrow:,.2f} − trading/FX ${trade_fx:,.0f} = net +${net:,.0f} — synthetic",
         ha="center", fontsize=9, fontweight="bold", color=PALETTE["zero"])

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout(rect=[0, 0.03, 1, 1])
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T099_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
