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

# T053 worked-example data (seed 151+2=153). Hardcoded = T4 table values.
rng = np.random.default_rng(153)

bars = np.arange(8)
pxA = np.array([100010, 100060, 100220, 100180, 100120, 100060, 100036, 100020], dtype=float)
pxB = np.array([100000, 100010, 100000, 100010, 100015, 100020, 100004, 100004], dtype=float)
basis_bp = (pxA - pxB) / pxB * 1e4          # cross-venue basis, bp
GATE_BP = 15.0                              # example cost gate

ENTRY_BAR, EXIT_BAR = 2, 6
entryA, entryB, exitA, exitB = 100220.0, 100000.0, 100036.0, 100004.0
notional = 50000.0
gross_shortA = (entryA - exitA) / entryA * notional   # 18.4 bp -> $92
gross_longB = (exitB - entryB) / entryB * notional    # 0.4 bp -> $2
gross = gross_shortA + gross_longB                    # ~$94
costs = 4 * 0.0002 * notional + 2 * 0.0002 * notional  # 4 taker legs + 2 crossed spreads = $60
net = gross - costs                                    # ~$34

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [1.3, 1], "hspace": 0.12})

# Panel 1: both venue perps + entry/exit leg markers
ax1.plot(bars, pxA, color=PALETTE["signal"], linewidth=2.2, label="Venue A perp (rich at entry)")
ax1.plot(bars, pxB, color=PALETTE["price"], linewidth=2.2, label="Venue B perp (cheap at entry)")
ax1.scatter([ENTRY_BAR, EXIT_BAR], [entryA, exitA], color=PALETTE["signal"],
            s=110, marker="v", zorder=5)
ax1.scatter([ENTRY_BAR, EXIT_BAR], [entryB, exitB], color=PALETTE["price"],
            s=110, marker="^", zorder=5)
ax1.annotate("ENTRY bar 3: short A @ 100,220\nlong B @ 100,000", xy=(ENTRY_BAR, entryA),
             xytext=(3.6, 100030), fontsize=9, color=PALETTE["signal"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]))
ax1.annotate("EXIT bar 7: cover A @ 100,036\nsell B @ 100,004 — net +$34",
             xy=(EXIT_BAR, exitA), xytext=(0.2, 99990), fontsize=9,
             color=PALETTE["profit"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]))
ax1.set_ylabel("Price ($)")
ax1.legend(loc="upper right")
ax1.set_title("T053 — Cross-Exchange Basis Arbitrage: synthetic two-venue pair (seed 153)")

# Panel 2: cross-venue basis with cost gate
ax2.plot(bars, basis_bp, color=PALETTE["signal2"], linewidth=2.4, marker="o",
         label="Basis (A-B)/B (bp)")
ax2.axhline(GATE_BP, color=PALETTE["loss"], linestyle="--", linewidth=1.2,
            label="Cost gate +15 bp (example)")
ax2.axhline(-GATE_BP, color=PALETTE["loss"], linestyle="--", linewidth=1.2)
ax2.axhline(0, color=PALETTE["zero"], linewidth=0.8)
ax2.fill_between(bars, -GATE_BP, GATE_BP, color=PALETTE["band"], alpha=0.3)
ax2.scatter([ENTRY_BAR], [basis_bp[ENTRY_BAR]], color=PALETTE["signal2"], s=130,
            marker="*", zorder=5, edgecolors="black", linewidths=0.8)
ax2.scatter([EXIT_BAR], [basis_bp[EXIT_BAR]], color=PALETTE["profit"], s=130,
            marker="*", zorder=5, edgecolors="black", linewidths=0.8)
ax2.annotate("entry basis 22 bp", xy=(ENTRY_BAR, basis_bp[ENTRY_BAR]),
             xytext=(3.2, 19), fontsize=9,
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal2"]))
ax2.annotate("exit basis 3.2 bp", xy=(EXIT_BAR, basis_bp[EXIT_BAR]),
             xytext=(4.6, 6), fontsize=9,
             arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]))
ax2.set_xticks(bars)
ax2.set_xlabel("Synchronized volume bar (synthetic)")
ax2.set_ylabel("Basis (bp)")
ax2.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T053_example.png", bbox_inches="tight")
plt.close()
print("T053: basis entry %.1f bp -> exit %.1f bp; gross = $%.0f, costs = $%.0f, net = $%.0f"
      % (basis_bp[ENTRY_BAR], basis_bp[EXIT_BAR], gross, costs, net))
