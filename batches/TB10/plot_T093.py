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

rng = np.random.default_rng(193)  # seed 193 — stated in T093 text

# ---- Worked example (SYNTHETIC) — same numbers as T093 T4 ----
# INNO: signal computed at close of day 0 (S_B=+1.46) -> earliest fill day +1 open.
# BUY 8,000 @ 50.61; stop 49.16 (1.1 x sigma20d=1.32); exit day +7 open @ 52.05.
# gross = 8000 x 1.44 = $11,520; costs $160 + $121.46 = $281.46 -> net +$11,238.54
# (long-only example: no borrow line — a prior draft's borrow charge was a ledger error)
days = np.arange(-5, 8)  # -5 .. +7
skew = np.array([5.5, 5.0, 4.4, 3.7, 3.0, 2.2, 1.8, 1.5, 1.3, 1.4, 1.8, 2.2, 2.4])
eq   = np.array([50.00, 50.08, 50.20, 50.40, 50.47, 50.52, 50.55, 50.61, 51.40, 51.62, 51.80, 52.10, 52.05])
# day idx: 5 -> day 0 close 50.55 (signal), idx 6 -> day +1 open 50.61 (fill), idx 12 -> day +7 open 52.05 (exit)

ENTRY_DX, EXIT_DX = 6, 12
ENTRY_PX, EXIT_PX = 50.61, 52.05
SHARES = 8000
gross = (EXIT_PX - ENTRY_PX) * SHARES
rt_cost = SHARES * 0.02
slip = SHARES * ENTRY_PX * 0.0003
costs = rt_cost + slip
net = gross - costs
print(f"T093 ledger: gross={gross:.0f} costs={costs:.2f} net={net:.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [1, 1.2]})
fig.suptitle("T093 — Options-to-Equity Lead: skew flatten + signed call flow → equity entry (synthetic)",
             fontweight="bold")

ax1.plot(days, skew, color=PALETTE["signal2"], marker="o", lw=2, label="25d put skew (vol pts)")
ax1.axvspan(-5, 0, color=PALETTE["band"], alpha=0.25, label="impulse window (5d)")
ax1.annotate("skew 5.5 → 1.8 vol pts\n(Δ −3.7, flattening = bullish lead)",
             xy=(0, 1.8), xytext=(-4.5, 3.4), arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             fontsize=9, bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax1.set_ylabel("skew (vol pts)")
ax1.legend(loc="upper right", fontsize=8)

ax2.plot(days, eq, color=PALETTE["price"], marker="o", lw=2, label="INNO equity (synthetic $)")
ax2.axvline(0, color=PALETTE["signal2"], ls=":", lw=1.4, label="signal at close day 0 (S_B=+1.46)")
ax2.scatter([days[ENTRY_DX]], [ENTRY_PX], color=PALETTE["profit"], s=110, zorder=5,
            label=f"BUY 8,000 @ {ENTRY_PX:.2f} (fill t+1)")
ax2.scatter([days[EXIT_DX]], [EXIT_PX], color=PALETTE["signal"], s=110, marker="s", zorder=5,
            label=f"SELL 8,000 @ {EXIT_PX:.2f} (skew mean-revert exit)")
ax2.axhline(49.16, color=PALETTE["loss"], ls="--", lw=1.2, label="stop 49.16 (1.1×σ20d, example)")
ax2.annotate(f"net +${net:,.0f}\n(gross ${gross:,.0f} − ${costs:,.0f} costs)",
             xy=(days[EXIT_DX], EXIT_PX), xytext=(3.2, 51.1),
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             fontsize=9, bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax2.set_xlabel("trading days (synthetic)")
ax2.set_ylabel("equity price ($)")
ax2.legend(loc="upper left", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T093_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
