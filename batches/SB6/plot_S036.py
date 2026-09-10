"""S036 plot: the 10-bar gap-fade tape (corrected worked example, seed fixed).
Chart numbers are the S4 worked-example numbers in batches/SB6/S036.md.
Run: python3 batches/SB6/plot_S036.py   (cwd = quant-signals-deep)
"""
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

rng = np.random.default_rng(36)  # stated in chapter text (tape is the fixed worked example)

# synthetic worked-example tape (bot-verified, hand-checked): prior close 100.00,
# open 102.00 -> g = +2.00%; 10 post-open 1-min closes
close_prev = 100.00
bars = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
px = np.array([102.00, 101.50, 101.1030, 100.8055, 100.5068, 100.1093,
               99.7115, 99.4135, 99.2149, 99.1157, 99.2148])
gap = px[0] / close_prev - 1
fade_pl = -(px[-1] - px[0]) / px[0]  # short the gap at the open, exit bar 10
print(f"gap g = {gap*100:.2f}% ; fade P/L(10) = {fade_pl*100:.3f}% before costs")
print("tape:", list(zip(bars.tolist(), np.round(px, 4).tolist())))

fig, ax = plt.subplots()
ax.plot(bars, px, color=PALETTE["price"], lw=2.0, marker="o", ms=4,
        label="synthetic 1-min closes (10-bar tape)")
ax.axhline(close_prev, color=PALETTE["zero"], lw=1.2, ls="--", label="prior close 100.00")
ax.axhspan(px[-1], px[0], color=PALETTE["band"], alpha=0.30, label="fade profit zone")
ax.annotate(f"gap g = +{gap*100:.2f}%", xy=(0, px[0]), xytext=(2.2, 102.6),
            fontsize=10, color=PALETTE["signal"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]))
ax.scatter([0], [px[0]], color=PALETTE["loss"], s=90, zorder=5, label="short at open")
ax.scatter([10], [px[-1]], color=PALETTE["profit"], s=90, zorder=5, label="cover at bar 10")
ax.annotate(f"fade P/L(10) = +{fade_pl*100:.3f}% (before costs)",
            xy=(10, px[-1]), xytext=(4.4, 100.35), fontsize=10, color=PALETTE["profit"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]))
ax.set_title("S036 — Overnight-gap fade: synthetic 10-bar tape (gap +2.00%, fill 2.731%)")
ax.set_xlabel("1-min bars after the open")
ax.set_ylabel("price (USD, synthetic)")
ax.set_xlim(-0.4, 10.6)
ax.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S036_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S036_example.png")
