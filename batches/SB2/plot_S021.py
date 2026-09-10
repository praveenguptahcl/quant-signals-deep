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

# ---- DATA: chatbot-reported Crabel worked example (operator-verified), seed 21 ----
rng = np.random.default_rng(21)  # fixed seed; values below are the verified tape, no randomness used
# 5-min bars B1..B8 as (O, H, L, C)
bars = np.array([
    [100.0, 100.8, 99.7, 100.5],  # B1
    [100.5, 100.9, 100.1, 100.3], # B2
    [100.3, 100.6, 99.9, 100.1],  # B3
    [100.1, 100.4, 99.8, 100.2],  # B4
    [100.2, 100.7, 100.0, 100.6], # B5
    [100.6, 100.8, 100.2, 100.7], # B6
    [100.7, 101.0, 100.5, 100.9], # B7
    [100.9, 101.3, 100.8, 101.2], # B8
])
O, H, L, C = bars.T
n = len(bars)
ORH = H[:6].max()          # 100.9
ORL = L[:6].min()          # 99.7
DELTA = 0.30               # example entry offset
LONG = ORH + DELTA         # 101.2
SHORT = ORL - DELTA        # 99.4

idx = np.arange(1, n + 1)
fig, ax = plt.subplots()
# bar ranges L..H
for i in range(n):
    ax.vlines(idx[i], L[i], H[i], color=PALETTE["price"], lw=4, alpha=0.75)
    ax.plot(idx[i], C[i], marker="o", color=PALETTE["price"], ms=5)
# opening-range band
ax.axhspan(ORL, ORH, color=PALETTE["band"], alpha=0.45, label=f"opening range [{ORL:.1f}, {ORH:.1f}]")
ax.axhline(ORH, color=PALETTE["signal"], ls="--", lw=1.5, label=f"ORH = {ORH:.1f}")
ax.axhline(ORL, color=PALETTE["signal"], ls="--", lw=1.5, label=f"ORL = {ORL:.1f}")
# entry offsets (example delta)
ax.axhline(LONG, color=PALETTE["profit"], ls=":", lw=1.8, label=f"long trigger {LONG:.1f} (ORH+δ, δ=0.30 ex.)")
ax.axhline(SHORT, color=PALETTE["loss"], ls=":", lw=1.8, label=f"short trigger {SHORT:.1f} (ORL−δ)")
# entry marker on bar 8
ax.plot(8, C[7], marker="^", color=PALETTE["profit"], ms=12, label="long entry @ 101.2 (bar 8)")
ax.annotate("long 101.2", xy=(8, 101.2), xytext=(6.3, 101.45),
            arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]),
            color=PALETTE["profit"], fontsize=9, weight="bold")
ax.set_title("S021 — Opening-range breakout (Crabel): 8×5-min synthetic tape")
ax.set_xlabel("5-minute bar (1..6 = opening range, 7..8 = post-range)")
ax.set_ylabel("price ($)")
ax.set_xticks(idx)
ax.legend(loc="upper left")
ax.set_ylim(99.2, 101.6)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S021_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("S021: ORH=%.1f ORL=%.1f long=%.1f short=%.1f" % (ORH, ORL, LONG, SHORT))
