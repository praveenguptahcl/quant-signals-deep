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

# T052 worked-example data (seed 151+1=152). Hardcoded = T4 table values.
rng = np.random.default_rng(152)

bars = np.arange(12)
closes = np.array([100000, 99850, 99300, 98400, 97600, 97500,
                   97700, 98000, 98150, 98350, 98300, 98400], dtype=float)
reported_liq = np.array([1.5, 2.0, 8.0, 30.0, 45.0, 12.0,
                         4.0, 2.5, 2.0, 1.8, 1.6, 1.5])  # $M, censored lower bound
# Intra-bar display wicks: deterministic rng(152) jitter around closes (display only).
wick = rng.normal(0, 60, size=closes.shape)

ENTRY_BAR, EXIT_BAR, VETO_BAR = 4, 9, 6
entry_px, exit_px = 97600.0, 98350.0
gross, costs, net = 750.0, 98.0, 652.0

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [1.4, 1], "hspace": 0.12})

# Panel 1: synthetic price on volume bars + cascade zone + entry/exit markers
ax1.plot(bars, closes, color=PALETTE["price"], linewidth=2.2, label="Perp mid (synthetic $)")
ax1.scatter(bars, closes + wick, color=PALETTE["price"], s=12, alpha=0.35, zorder=3)
ax1.axvspan(2.5, 5.5, color=PALETTE["band"], alpha=0.35, label="Liquidation cluster (bars 3-5)")
ax1.scatter([ENTRY_BAR], [entry_px], color=PALETTE["profit"], s=130, marker="^", zorder=5)
ax1.scatter([EXIT_BAR], [exit_px], color=PALETTE["profit"], s=130, marker="v", zorder=5)
ax1.annotate("ENTRY long @ 97,600 (bar 5)", xy=(ENTRY_BAR, entry_px),
             xytext=(6.6, 97900), fontsize=9, color=PALETTE["profit"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]))
ax1.annotate("EXIT @ 98,350 (bar 10)\nnet +$652", xy=(EXIT_BAR, exit_px),
             xytext=(8.4, 99000), fontsize=9, color=PALETTE["profit"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]))
ax1.scatter([VETO_BAR], [closes[VETO_BAR]], color=PALETTE["signal2"], s=110,
            marker="x", linewidths=2.5, zorder=5)
ax1.annotate("S019 veto at bar 7 (no trade)", xy=(VETO_BAR, closes[VETO_BAR]),
             xytext=(7.6, 98100), fontsize=9, color=PALETTE["signal2"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal2"]))
ax1.set_ylabel("Price ($)")
ax1.legend(loc="upper right")
ax1.set_title("T052 — Liquidation-Cascade Fade: synthetic 12-bar cascade + fade trade (seed 152)")

# Panel 2: reported liquidation volume ($M) — censored lower bound
colors = [PALETTE["signal"] if v >= 10 else PALETTE["volume"] for v in reported_liq]
ax2.bar(bars, reported_liq, color=colors, alpha=0.85,
        label="reported_liq_$M (censored lower bound)")
ax2.axhline(10.0, color=PALETTE["signal"], linestyle=":", linewidth=1.4,
            label="Trigger: 3x trailing median (example)")
ax2.set_xticks(bars)
ax2.set_xlabel("Volume bar (synthetic, ~5 min each)")
ax2.set_ylabel("Reported liquidations ($M)")
ax2.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T052_example.png", bbox_inches="tight")
plt.close()
print("T052: gross = $%.0f, costs = $%.0f, net = $%.0f" % (gross, costs, net))
