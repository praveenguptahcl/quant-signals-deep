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

rng = np.random.default_rng(200)  # seed 200 — stated in T100 text

# ---- Worked example (SYNTHETIC) — same numbers as T100 T4 ----
# 5-signal stacking walk + meta-label sizing. Unit risk $2,500; $80 cost per unit round-trip.
# Event nets (gated): +3,020, 0 (pass), +1,848, −2,330, +1,088 -> walk +$3,626.
# Ungated: event 2 taken short (−$2,980), event 5 at 1.0x (+$2,720) -> walk +$2,278.
events = ["1", "2", "3", "4", "5"]
p_meta = np.array([0.71, 0.52, 0.81, 0.66, 0.61])
sizes = np.array([1.0, 0.0, 1.4, 1.0, 0.4])
gross_ev = np.array([3100, 0, 1960, -2250, 1120], dtype=float)
net_gated = gross_ev - np.array([80, 0, 112, 80, 32], dtype=float)
cum_gated = np.cumsum(net_gated)
# ungated counterfactual
net_ungated = np.array([3020, -2980, 1848, -2330, 2720], dtype=float)
cum_ungated = np.cumsum(net_ungated)
print(f"T100 ledger: gated net={cum_gated[-1]:.0f} ungated net={cum_ungated[-1]:.0f}")

x = np.arange(5)
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [1.3, 1]})
fig.suptitle("T100 — Grand Ensemble: meta-gate adds value by trading less (synthetic)", fontweight="bold")

ax1.plot(x, cum_gated, color=PALETTE["profit"], marker="o", lw=2.4, label=f"meta-gated net +${cum_gated[-1]:,.0f}")
ax1.plot(x, cum_ungated, color=PALETTE["loss"], marker="x", lw=2, ls="--",
         label=f"ungated net +${cum_ungated[-1]:,.0f}")
ax1.axhline(0, color=PALETTE["zero"], lw=0.8)
ax1.set_xticks(x, [f"event {e}" for e in events])
ax1.set_ylabel("cumulative net P&L ($)")
ax1.legend(loc="upper left")
ax1.annotate("event 2: vetoed\n(avoided −$2,980)", xy=(1, cum_gated[1]), xytext=(0.2, 4200),
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]), fontsize=8,
             bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax1.annotate("event 5: 0.4× size\n(avoided 0.6× overbet)", xy=(4, cum_gated[4]), xytext=(3.1, 1500),
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]), fontsize=8,
             bbox=dict(boxstyle="round", fc="white", alpha=0.9))

cols = [PALETTE["profit"] if p >= 0.58 else PALETTE["volume"] for p in p_meta]
b = ax2.bar(x, p_meta, color=cols, edgecolor=PALETTE["zero"], lw=0.8)
for i, (p, s) in enumerate(zip(p_meta, sizes)):
    ax2.text(i, p + 0.015, f"{p:.2f}\n{s:.1f}×", ha="center", fontsize=8, fontweight="bold")
ax2.axhline(0.58, color=PALETTE["loss"], ls="--", lw=1.2, label="trade gate p̂ ≥ 0.58 (example)")
ax2.axhline(0.55, color=PALETTE["volume"], ls=":", lw=1, label="0.55 (0.4× band)")
ax2.axhline(0.78, color=PALETTE["volume"], ls=":", lw=1, label="0.78 (1.4× band)")
ax2.set_ylabel("meta p̂ (calibrated)")
ax2.set_xlabel("stacking events (synthetic)")
ax2.set_ylim(0, 1.0)
ax2.legend(loc="upper right", fontsize=7)
fig.text(0.5, 0.005, "5 events · unit risk $2,500 · triple-barrier labels (u=1.25, d=0.90, τ=2d) · $80/unit costs — synthetic worked example",
         ha="center", fontsize=9, color=PALETTE["zero"])

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout(rect=[0, 0.02, 1, 1])
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T100_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
