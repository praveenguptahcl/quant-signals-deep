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

rng = np.random.default_rng(195)  # seed 195 — stated in T095 text

# ---- Worked example (SYNTHETIC) — same numbers as T095 T4 ----
# 12-session dispersion: long 8-name straddle basket (single vol) vs short 20 SPX straddles (40 option contracts).
# Long leg cumulative: ends −$4,900. Short-index leg cumulative: ends +$12,300.
# gross +$7,400; fully costed (options spread/commissions x100 multiplier + hedge slippage) $1,850.
# net +$5,550. Day 9: modeled GEX flips negative -> position cut 50% (regime switch).
days = np.arange(1, 13)
long_leg = np.array([0, -200, -800, -1500, -2100, -2600, -2900, -3300, -3600, -3900, -4500, -4900], dtype=float)
short_leg = np.array([0, 500, 1200, 2100, 3300, 4800, 6200, 7600, 8800, 10000, 11200, 12300], dtype=float)
net_leg = long_leg + short_leg
gross = float(net_leg[-1])
costs = 1850.0
net = gross - costs
print(f"T095 ledger: gross={gross:.0f} costs={costs:.0f} net={net:.0f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [1.5, 1]})
fig.suptitle("T095 — Dispersion + GEX Regime Switch: correlation spread harvest (synthetic)", fontweight="bold")

ax1.plot(days, long_leg, color=PALETTE["loss"], lw=2, marker="o", ms=4,
         label="long 8-name single vol (realized 24.1% < implied 27.8%)")
ax1.plot(days, short_leg, color=PALETTE["profit"], lw=2, marker="o", ms=4,
         label="short SPX index vol (realized 16.2% < implied 21.5%)")
ax1.plot(days, net_leg, color=PALETTE["price"], lw=2.6, marker="s", ms=4, label="net (before cost)")
ax1.axvline(9, color=PALETTE["signal"], ls="--", lw=1.5,
            label="modeled GEX flips negative → size cut 50% (example)")
ax1.axhline(0, color=PALETTE["zero"], lw=0.8)
ax1.set_ylabel("cumulative P&L ($)")
ax1.legend(loc="upper left", fontsize=8)
ax1.annotate(f"gross +${gross:,.0f}\nnet +${net:,.0f} (costs ${costs:,.0f})",
             xy=(12, net_leg[-1]), xytext=(6.2, 9500),
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             fontsize=9, bbox=dict(boxstyle="round", fc="white", alpha=0.9))

gex = np.array([1.2, 1.4, 1.1, 1.5, 1.3, 1.6, 1.4, 1.2, -0.4, -0.8, -0.6, -0.3])
ax2.bar(days, gex, color=[PALETTE["profit"] if g > 0 else PALETTE["loss"] for g in gex],
        label="modeled aggregate GEX ($B per 1% move, proxy — not dealer positions)")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.set_xlabel("session (synthetic)")
ax2.set_ylabel("GEX proxy ($B)")
ax2.legend(loc="lower left", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T095_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
