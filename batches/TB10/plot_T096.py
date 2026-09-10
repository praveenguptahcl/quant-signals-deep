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

rng = np.random.default_rng(196)  # seed 196 — stated in T096 text

# ---- Worked example (SYNTHETIC) — same numbers as T096 T4 ----
# 120 1-min bars, synthetic. Kalman fair-value tracks mid; HMM state: trend bars 0-79, chop 80-119.
# Trades (3,000 sh, fill t+1): T1 long 61.20->61.95 (+$2,250); T2 short 62.40->61.85 (+$1,650).
# A third candidate at bar 95 is VETOED (inside the stated chop window) — no fill, no ledger line.
# gross +$3,900; costs 1.5c RT x 3000 x 2 = $90; net +$3,810.
n = 120
bars = np.arange(n)
trend = np.where(bars < 80, 0.016 * bars, 1.28 - 0.004 * (bars - 80))
noise = rng.standard_normal(n) * 0.05
mid = 60.90 + trend + noise
# Kalman-style smoother (simple causal EMA standing in for the filter output)
fair = np.zeros(n)
a = 0.18
fair[0] = mid[0]
for i in range(1, n):
    fair[i] = fair[i - 1] + a * (mid[i] - fair[i - 1])

trades = [("long", 20, 61.20, 44, 61.95), ("short", 55, 62.40, 74, 61.85)]
gross = (61.95 - 61.20) * 3000 + (62.40 - 61.85) * 3000
costs = 2 * 3000 * 0.015
net = gross - costs
print(f"T096 ledger: gross={gross:.0f} costs={costs:.0f} net={net:.0f}")

fig, ax = plt.subplots(figsize=(10, 5.2))
fig.suptitle("T096 — Kalman + HMM Adaptive Trend: fair-value trend gated by regime (synthetic)",
             fontweight="bold")
ax.axvspan(0, 80, color=PALETTE["profit"], alpha=0.07, label="HMM state: TREND (P>0.6, example)")
ax.axvspan(80, 120, color=PALETTE["volume"], alpha=0.12, label="HMM state: CHOP (no new entries)")
ax.plot(bars, mid, color=PALETTE["price"], lw=1.3, label="mid price (synthetic)")
ax.plot(bars, fair, color=PALETTE["signal"], lw=2, label="Kalman fair value (Q/R calibrated)")
for side, te, pe, tx, px in trades:
    ax.scatter([te], [pe], color=PALETTE["profit"] if side == "long" else PALETTE["signal2"],
               s=95, marker="^" if side == "long" else "v", zorder=5)
    ax.scatter([tx], [px], color=PALETTE["zero"], s=80, marker="s", zorder=5)
ax.annotate("entries ▲▼ (t+1 fills) / exits ■", xy=(44, 62.05), fontsize=9,
            bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax.scatter([95], [62.10], color=PALETTE["loss"], s=110, marker="x", zorder=5,
           label=None)
ax.annotate("bar 95 VETOED (chop)", xy=(95, 62.10), xytext=(78, 62.75),
            arrowprops=dict(arrowstyle="->", color=PALETTE["loss"]),
            fontsize=9, color=PALETTE["loss"],
            bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax.set_xlabel("1-min bar index (synthetic)")
ax.set_ylabel("price ($)")
ax.legend(loc="upper left", fontsize=8)
fig.text(0.5, 0.01, f"2 trades (3,000 sh): +$2,250 / +$1,650 → gross +${gross:,.0f} − ${costs:,.0f} costs = net +${net:,.0f} (bar-95 candidate vetoed: chop) — synthetic",
         ha="center", fontsize=9, fontweight="bold", color=PALETTE["zero"])

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout(rect=[0, 0.03, 1, 1])
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T096_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
