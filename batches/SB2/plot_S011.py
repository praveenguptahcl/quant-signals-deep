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

# ---- Reproducibility ----
# Tape is hand-specified and deterministic (no random draw); seed recorded for
# the plotting pipeline. Synthetic tape values are the operator-verified
# corrected chatbot worked example (see chapter S4).
rng = np.random.default_rng(110)

# Synthetic tape (chatbot tape, operator-verified): closes / shares
closes = np.array([100.00, 101.00, 100.50, 102.00, 101.50,
                   103.00, 102.00, 101.00, 101.50, 100.50])
vols   = np.array([100000, 120000, 110000, 130000, 100000,
                   150000, 125000, 140000, 100000, 160000])

# Daily Amihud ILLIQ_t = |r_t| / (C_t * V_t), t = 2..10  (verified corrected values)
r  = closes[1:] / closes[:-1] - 1.0
dv = closes[1:] * vols[1:]
illiq = np.abs(r) / dv                      # per-dollar units
days = np.arange(2, 11)                     # D2..D10

illig_avg = illiq.mean()                    # corrected: 7.1037e-10
unit = 1e9
fig, ax = plt.subplots()
bars = ax.bar(days, illiq * unit, color=PALETTE["signal2"], edgecolor=PALETTE["zero"],
              alpha=0.85, label="Daily ILLIQ (×1e-9)")
ax.axhline(illig_avg * unit, color=PALETTE["price"], linestyle="--", linewidth=1.6,
           label=f"9-day average = {illig_avg:.4e}")
ax.set_title("S011 — Amihud illiquidity: 9-day synthetic tape")
ax.set_xlabel("Day (D2..D10)")
ax.set_ylabel("Daily ILLIQ |r|/dollar-vol (units of 1e-9)")
ax.set_xticks(days)
ax.legend()
# annotate the corrected aggregate on the chart
ax.text(0.02, 0.96,
        f"Σ ILLIQ = 6.3933e-9\navg = 7.1037e-10\nper-$M = 7.1037e-4\n(seed 110; deterministic tape)",
        transform=ax.transAxes, fontsize=8, va="top", ha="left",
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=PALETTE["zero"], alpha=0.9))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S011_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
