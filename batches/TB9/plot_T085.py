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

rng = np.random.default_rng(185)  # T085 seed — stated in chapter text

# ---- T085 worked-example inputs (SYNTHETIC) ----
# Fictional "MMX" @ $100.00. A-S example params: gamma=0.0001, sigma=$1.00/sqrt(day),
# kappa=200/day, (T-t)=1 day.
gamma, sigma, kappa, Tt = 0.0001, 1.00, 200, 1.0
spread = gamma * sigma**2 * Tt + (2 / gamma) * np.log(1 + gamma / kappa)
half = spread / 2
print(f"A-S optimal spread = {gamma*sigma**2*Tt:.6f} + {(2/gamma)*np.log(1+gamma/kappa):.6f} = ${spread:.4f} "
      f"-> {half*100:.2f}c each side")
# 10 synthetic quote updates: microprice fair value + inventory -> reservation price + quotes
micro = 100.00 + 0.004 * np.cumsum(rng.standard_normal(10))
inv = np.array([0, 100, 200, 100, 0, -100, -200, -100, 0, 100])  # shares
skew = inv * gamma * sigma**2 * Tt          # inventory skew in $/share-terms: q*gamma*sigma^2*(T-t)
res = micro - skew
bid = res - half
ask = res + half
for i in range(10):
    print(f"q{i+1}: micro={micro[i]:.4f} inv={inv[i]:+d} r={res[i]:.4f} bid={bid[i]:.4f} ask={ask[i]:.4f}")
# 10 synthetic round trips of 100 sh: capture half-spread 0.5c each, 2 trips suffer 1c adverse drift,
# maker rebate $0.002/share both legs (example).
cap = 0.005 * 100 * 10
adv = 0.01 * 100 * 2
reb = 0.002 * 100 * 2 * 10
net = cap - adv + reb
print(f"capture=${cap:.2f}, adverse=-${adv:.2f}, rebates=${reb:.2f}, NET=${net:.2f}")
# synthetic cumulative path shaped like the trips (8 wins, 2 adverse, rebates accrue)
trip_net = np.array([0.90, 0.90, -0.10, 0.90, 0.90, 0.90, -0.10, 0.90, 0.90, 0.90])
print("trip net check:", trip_net.sum(), "-> target", net)
cum = np.cumsum(trip_net)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), gridspec_kw={"height_ratios": [3, 2]})
fig.suptitle("T085 — Resiliency Market Maker: synthetic A-S quoting walk (seed 185)", fontweight="bold")
q = np.arange(1, 11)
ax1.plot(q, micro, color=PALETTE["signal2"], lw=1.4, marker="o", ms=3, label="microprice fair value (S004)")
ax1.plot(q, bid, color=PALETTE["profit"], lw=1.2, marker="s", ms=3, label="bid = r - spread/2")
ax1.plot(q, ask, color=PALETTE["signal"], lw=1.2, marker="s", ms=3, label="ask = r + spread/2")
ax1.fill_between(q, bid, ask, color=PALETTE["band"], alpha=0.4)
ax1.set_xlim(1, 10); ax1.set_xticks(q); ax1.set_xlabel("quote update (synthetic)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left", fontsize=8)
ax1.text(0.98, 0.06, f"A-S (example): spread {spread*100:.2f}c, skew {gamma*sigma**2*Tt*100:.3f}c/sh inventory",
         transform=ax1.transAxes, ha="right", fontsize=8, bbox=dict(boxstyle="round", fc="white", alpha=0.9))

ax2.bar(q, trip_net, color=[PALETTE["profit"] if v >= 0 else PALETTE["loss"] for v in trip_net])
ax2.plot(q, cum, color=PALETTE["price"], marker="o", ms=4, lw=1.8, label="cumulative net P&L")
ax2.text(10, cum[-1] + 0.15, f"${cum[-1]:.2f}", ha="right", fontsize=9, fontweight="bold")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.set_xlim(0.5, 10.5); ax2.set_xticks(q)
ax2.set_xlabel("round trip (100 sh each, synthetic)")
ax2.set_ylabel("P&L ($)")
ax2.set_title(f"10 round trips: capture ${cap:.2f} - adverse ${adv:.2f} + rebates ${reb:.2f} = net ${net:.2f}",
              fontsize=11)
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T085_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
