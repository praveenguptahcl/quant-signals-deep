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

rng = np.random.default_rng(194)  # seed 194 — stated in T094 text

# ---- Worked example (SYNTHETIC) — same numbers as T094 T4 ----
# Trade 1 (VOLT): squeeze -> upper-band break + UOA 4.2x + vol expansion.
# BUY 4,000 @ 84.24 (t+1 fill) -> SELL @ 88.10. gross +$15,440; costs $160; net +$15,280.
# Setup 2 (DEAD): false break -> VETOED by the 3.5x UOA gate: no fill, no ledger line.
# Strategy net +$15,280 (the avoided -2,280 is the veto's saved outcome, not a booked loss).
d1 = np.arange(30)
volt = 84.00 + np.cumsum(rng.standard_normal(30) * 0.12)
volt[14:] += np.linspace(0, 3.9, 16)      # expansion leg after squeeze
volt[15] = 84.24                          # pin entry bar to the T4 fill price
volt[29] = 88.10
upper1 = 84.00 + 0.30 + np.cumsum(rng.standard_normal(30) * 0.03); upper1[14:] += np.linspace(0, 2.9, 16)
lower1 = 84.00 - 0.30 + np.cumsum(rng.standard_normal(30) * 0.03)
bw1 = np.linspace(11.0, 7.6, 14).tolist() + [8.0, 9.2, 11.5, 14.0, 15.2, 16.1, 15.0, 13.8, 12.9, 12.1, 11.5, 11.0, 10.6, 10.2, 9.8, 9.5]
assert len(bw1) == 30

d2 = np.arange(15)
dead = 31.60 + np.cumsum(rng.standard_normal(15) * 0.18)
dead[9:] = 31.55 - np.linspace(0, 0.62, 6)  # false break fades into stop
upper2 = 31.60 + 0.28 + np.cumsum(rng.standard_normal(15) * 0.02)
lower2 = 31.60 - 0.28 + np.cumsum(rng.standard_normal(15) * 0.02)

g1, c1 = (88.10 - 84.24) * 4000, 4000 * 0.04   # 4c/sh RT all-in (example)
sess = g1 - c1
print(f"T094 ledger: t1 net={g1-c1:.0f} dead VETOED (no fill) session={sess:.0f}")

fig, axes = plt.subplots(3, 1, figsize=(10, 5.2), sharex=False,
                         gridspec_kw={"height_ratios": [1.6, 1, 1.2]})
fig.suptitle("T094 — Squeeze Breakout (Options-Confirmed): one true break; false break vetoed, no fill (synthetic)",
             fontweight="bold")
ax1, axb, ax2 = axes

ax1.plot(d1, volt, color=PALETTE["price"], lw=1.8, label="VOLT (synthetic $)")
ax1.plot(d1, upper1, color=PALETTE["volume"], lw=1.1, label="upper band (20d, 2σ)")
ax1.plot(d1, lower1, color=PALETTE["volume"], lw=1.1, label="lower band")
ax1.axvspan(0, 14, color=PALETTE["band"], alpha=0.3, label="squeeze: bandwidth 2nd %-ile (14 sessions)")
ax1.scatter([15], [84.24], color=PALETTE["profit"], s=110, zorder=5, label="BUY 4,000 @ 84.24 (fill t+1)")
ax1.scatter([29], [88.10], color=PALETTE["signal"], s=110, marker="s", zorder=5,
            label="SELL @ 88.10 — net +$15,280")
ax1.set_ylabel("VOLT price ($)")
ax1.legend(loc="upper left", fontsize=7)

axb.plot(d1, bw1, color=PALETTE["signal2"], lw=1.8, label="Bollinger bandwidth %")
axb.axhline(8.0, color=PALETTE["loss"], ls="--", lw=1.1, label="squeeze line 8% (example)")
axb.set_ylabel("bandwidth %")
axb.legend(loc="upper right", fontsize=7)

ax2.plot(d2, dead, color=PALETTE["price"], lw=1.8, label="DEAD (synthetic $)")
ax2.plot(d2, upper2, color=PALETTE["volume"], lw=1.1)
ax2.plot(d2, lower2, color=PALETTE["volume"], lw=1.1)
ax2.scatter([9], [31.55], color=PALETTE["loss"], s=110, marker="x", zorder=5,
            label="VETOED false break (no fill; avoided −$2,280)")
ax2.set_ylabel("DEAD price ($)")
ax2.set_xlabel("sessions (synthetic)")
ax2.legend(loc="upper right", fontsize=7)
fig.text(0.5, 0.005, f"session net +${sess:,.0f} (one true break; vetoed setup never filled) — synthetic worked example",
         ha="center", fontsize=10, fontweight="bold", color=PALETTE["zero"])

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout(rect=[0, 0.02, 1, 1])
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T094_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
