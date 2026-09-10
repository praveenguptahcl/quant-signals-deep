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

# ---- SYNTHETIC WORKED EXAMPLE: T049 UOA sweep follower (seed 149) ----
# Chapter text and chart MUST agree: both are generated from these arrays.
rng = np.random.default_rng(149)

# Synthetic 5-min bar closes, fictional single-name "QBT", day 1 (40 bars) + day 2 (10 bars)
n1, n2 = 40, 10
path1 = 84.20 + np.cumsum(rng.normal(0, 0.12, n1))
path1 = np.round(path1, 2)
path1[8] = 83.85   # engineered pullback to the sweep-day dip (entry zone)
path2 = 84.30 + np.cumsum(rng.normal(0, 0.15, n2))
path2 = np.round(path2, 2)
path2[-1] = 85.68  # engineered day-2 exit close

# Synthetic signal reads at key times
sweep_bar = 7                                  # 10:17 ET bar (approx)
entry_bar = 8                                  # 10:41 dip entry (first bar at/after dip)
print("Sweep (bar 7, ~10:17 ET): 2,400 21-DTE 87.5 calls swept at ask $1.85, "
      "premium $444k, prior OI 410, vol/OI = 5.9 (example U > 1.5x), delta 0.32")
print("S094 confirm at sweep bar: 5-min RVOL 3.2x (example trigger 2.0), "
      "block imbalance +0.55 (buy-leaning)")
print("S091 confirm: bucket sentiment S_b z = +2.1 (example >= 2.0), "
      "novelty 88 (example floor 70)")
print(f"Entry: 800 shares @ {path1[entry_bar]:.2f} on pullback (bar {entry_bar}, ~10:41 ET)")
print(f"Stop 82.90 (example 1.0-1.5x ATR) | Target 86.20 (example 1.5-2.0R) | "
      f"time stop 2-5 sessions (example)")

shares = 800
entry_px, exit_px = float(path1[entry_bar]), float(path2[-1])
cost_rt = shares * 0.005 * 2 + shares * (entry_px + exit_px) / 2 * 0.0001 * 2  # example
gross = shares * (exit_px - entry_px)
net = gross - cost_rt
risk = shares * (entry_px - 82.90)
print("\nTrade (line-by-line net P&L):")
print(f"  long {shares} @ {entry_px:.2f} -> {exit_px:.2f}: gross {gross:+.2f}, "
      f"costs {cost_rt:.2f}, NET {net:+.2f}")
print(f"  risk to stop: {risk:.2f} ({net/risk:.2f}R realized)")

# ---- PLOT: trade timeline with sweep/entry/exit markers + net P&L ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
x = np.arange(n1 + n2)
px = np.concatenate([path1, path2])
ax1.plot(x[:n1], px[:n1], color=PALETTE["price"], lw=1.6, label="QBT 5-min (synthetic $)")
ax1.plot(x[n1 - 1:], px[n1 - 1:], color=PALETTE["price"], lw=1.6, ls="--")

ax1.axvline(sweep_bar, color=PALETTE["signal2"], lw=1.5, ls=":")
ax1.text(sweep_bar + 0.3, 84.05, "SWEEP\n2,400 87.5C @ ask $1.85\nvol/OI 5.9x", fontsize=8,
         color=PALETTE["signal2"], va="center")
ax1.annotate("", xy=(entry_bar, entry_px), xytext=(entry_bar - 6, entry_px - 0.35),
             arrowprops=dict(arrowstyle="->", color=PALETTE["profit"], lw=2))
ax1.text(entry_bar - 6, entry_px - 0.35, f"long 800 @ {entry_px:.2f}",
         color=PALETTE["profit"], fontsize=9, va="center")
ax1.plot(x[n1 + n2 - 1], exit_px, marker="X", ms=11, color=PALETTE["profit"])
ax1.text(x[n1 + n2 - 1] - 3, exit_px + 0.12, f"exit day 2 @ {exit_px:.2f}",
         color=PALETTE["profit"], fontsize=9)
ax1.axhline(82.90, color=PALETTE["loss"], lw=1, ls="--", label="stop 82.90")
ax1.axhline(86.20, color=PALETTE["profit"], lw=1, ls="--", label="target 86.20")
ax1.set_ylabel("Price ($)")
ax1.legend(loc="best")
ax1.set_title("T049 — Unusual Options Activity Follower: synthetic sweep-follow trade timeline")

ax2.bar([1], [net], tick_label=[f"sweep-follow\n{net:+.2f}"],
        color=PALETTE["profit"] if net > 0 else PALETTE["loss"])
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.set_ylabel("Net P&L ($)")
ax2.set_xlabel("Trade (synthetic)")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T049_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("\nSaved images/T049_example.png")
