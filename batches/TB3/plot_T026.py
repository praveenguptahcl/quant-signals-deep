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

rng = np.random.default_rng(126)

# ---- T4 numbers: 10 throttled slices x $108 vs 2 unthrottled x $1,660 ----
# Slice cost components: impact 56, spread 40, fees 12 (throttled)
# Unthrottled per-slice: impact 1400, spread 200, fees 60
n_thr = 10
thr_impact = np.full(n_thr, 56.0)
thr_spread = np.full(n_thr, 40.0)
thr_fees = np.full(n_thr, 12.0)
# exact T4 numbers — no jitter, so chart and text agree point for point

x = np.arange(1, n_thr + 1)
fig, ax = plt.subplots()
b1 = ax.bar(x, thr_impact, color=PALETTE["signal"], label="impact cost ($)")
b2 = ax.bar(x, thr_spread, bottom=thr_impact, color=PALETTE["volume"], label="spread ($)")
b3 = ax.bar(x, thr_fees, bottom=thr_impact + thr_spread, color=PALETTE["band"],
            label="fees ($)", edgecolor=PALETTE["zero"], linewidth=0.6)

for i, xi in enumerate(x):
    ax.annotate(f"${thr_impact[i] + thr_spread[i] + thr_fees[i]:.0f}",
                xy=(xi, thr_impact[i] + thr_spread[i] + thr_fees[i] + 60),
                ha="center", fontsize=7.5, color=PALETTE["zero"])

# unthrottled counterfactual as reference line
ax.axhline(1660, color=PALETTE["loss"], ls="--", lw=1.6,
           label="unthrottled slice cost $1,660 (2 slices)")
ax.text(n_thr, 1450, "unthrottled: 2 x $1,660",
        color=PALETTE["loss"], fontsize=8, va="top", ha="right")

ax.set_xlabel("Child slice (5-min resiliency-spaced slots)")
ax.set_ylabel("Execution cost per slice ($)")
ax.set_title("T026 — Kyle-Lambda Participation Throttle: synthetic per-slice cost (seed 126)")
ax.set_xticks(x)
ax.legend(loc="upper right")
ax.text(0.02, 0.96,
        "Throttled total: $1,080 (4.5 bps)   |   Unthrottled total: $3,320 (13.8 bps)\nSaving: $2,240 = 9.3 bps on $2.4M parent",
        transform=ax.transAxes, fontsize=9, va="top", ha="left",
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=PALETTE["zero"], alpha=0.9))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T026_example.png", bbox_inches="tight")
plt.close()
