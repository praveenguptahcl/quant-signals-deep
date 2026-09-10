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

# ---- SYNTHETIC WORKED EXAMPLE (seed 91091) ----
# Synthetic 1-minute price path around a positive machine-readable news event.
# News: ESS = +0.85 (example), relevance 90, novelty 80.
# First available timestamp at minute 0; mean path jumps +35 bps in the first
# minute, drifts to +52 bps by minute 5, then fades to +18 bps by minute 30.
rng = np.random.default_rng(91091)
mins = np.arange(-30, 31)
mean = np.zeros_like(mins, dtype=float)
mean[mins >= 0] = 35.0
mean[mins >= 2] = 47.0
mean[mins >= 4] = 52.0
drift = np.clip(mins, 5, 30)
mean[mins >= 5] = 52.0 - (drift[mins >= 5] - 5) * (34.0 / 25.0)  # fade to 18 by t=30
cum_bps = mean + rng.normal(0, 6.0, len(mins))
per_min = np.diff(cum_bps, prepend=cum_bps[0])

print("minute | per-min return (bps) | cumulative (bps)")
for t in range(0, 11):
    idx = t + 30
    print(f"{t:>6} | {per_min[idx]:>20.1f} | {cum_bps[idx]:>16.1f}")
print(f"\nfirst-minute reaction (t=0): {per_min[30]:.1f} bps")
print(f"cumulative at t=10: {cum_bps[40]:.1f} bps | at t=30: {cum_bps[60]:.1f} bps")

# ---- CHART ----
fig, ax = plt.subplots()
ax.axvspan(0, 1, color=PALETTE["band"], alpha=0.55, label="first minute after news")
ax.plot(mins, cum_bps, color=PALETTE["price"], linewidth=2.0,
        label="cumulative return, synthetic (bps)")
ax.axvline(0, color=PALETTE["signal"], linestyle="--", linewidth=1.5,
           label="news first available timestamp (t=0)")
ax.axhline(0, color=PALETTE["zero"], linewidth=0.8)
ax.set_xlim(-30, 30)
ax.set_xlabel("Minutes relative to news arrival")
ax.set_ylabel("Cumulative return (basis points)")
ax.set_title("S091 — Machine-readable news: synthetic first-minute reaction (seed 91091)")
ax.legend(loc="upper left")
ax.annotate("ESS = +0.85 (example)\nrelevance 90, novelty 80",
            xy=(0, cum_bps[30]), xytext=(8, cum_bps[30] + 18),
            fontsize=9, ha="left",
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=PALETTE["zero"], alpha=0.9))
ax.text(0.99, 0.03, "reaction completes, then fades — synthetic path",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=PALETTE["zero"], alpha=0.9))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S091_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S091_example.png")
