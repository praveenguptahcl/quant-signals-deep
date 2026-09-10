import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm

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

# ---- SYNTHETIC 12-TRADE TAPE, CORRECTED Lee-Ready signs (seed in chapter text) ----
seed = 20260907
rng = np.random.default_rng(seed)  # fixed for reproducibility (tape itself is fixed)
prices = np.array([100.00, 100.10, 100.10, 100.20, 100.10, 100.00,
                   100.00, 99.90, 100.00, 100.10, 99.90, 100.00])
sizes = np.full(12, 10)
mid = 100.00
# Corrected labels (trade 5 = +1, not "-"):
#  1:+1 (tick rule, no prior -> +1 convention)  2:+1  3:+1  4:+1  5:+1 (quote rule)
#  6:-1 (tick: downtick from 100.10)  7:-1 (downtick from 100.10)  8:-1
#  9:+1 (uptick from 99.90)  10:+1  11:-1  12:+1 (uptick from 99.90)
signs = np.array([+1, +1, +1, +1, +1, -1, -1, -1, +1, +1, -1, +1])
rules = np.array(["tick(conv.)", "quote", "quote", "quote", "quote",
                  "tick", "tick", "quote", "tick", "quote", "quote", "tick"])
n_buy, n_sell = int((signs == 1).sum()), int((signs == -1).sum())
ofi_lr = int((sizes * signs).sum())
print("S007 corrected tape: buys =", n_buy, "sells =", n_sell, "OFI_LR =", ofi_lr)

# ---- BVC on 3 synthetic volume bars (verified) ----
sigma_p = 0.10
bars_o = np.array([100.00, 100.10, 100.00])
bars_c = np.array([100.20, 99.90, 100.00])
bar_v = np.array([40.0, 40.0, 40.0])
z = (bars_c - bars_o) / sigma_p
phi = norm.cdf(z)
buy_v = np.round(bar_v * phi, 2)
sell_v = np.round(bar_v - buy_v, 2)
bvc = np.round(buy_v - sell_v, 2)
for i in range(3):
    print(f"bar{i+1}: z={z[i]:+.1f} Phi={phi[i]:.5f} buy={buy_v[i]:.2f} "
          f"sell={sell_v[i]:.2f} BVC={bvc[i]:+.2f}")

# ---- FIGURE ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2))
fig.suptitle("S007 — Trade classification: 12-trade synthetic tape (Lee–Ready, corrected)")

# Panel 1: trade prices with corrected signs
t = np.arange(1, 13)
colors = [PALETTE["profit"] if s > 0 else PALETTE["loss"] for s in signs]
ax1.plot(t, prices, color=PALETTE["price"], linewidth=1.2, label="trade price ($)")
ax1.scatter(t, prices, s=110, c=colors, edgecolor="black", linewidth=0.7,
            zorder=5)
for i, (ti, p, s) in enumerate(zip(t, prices, signs)):
    ax1.annotate("+" if s > 0 else "−", (ti, p), fontsize=9, weight="bold",
                 color="white", ha="center", va="center")
ax1.axhline(mid, color=PALETTE["zero"], linestyle=":", linewidth=1.2,
            label="midpoint 100.00")
ax1.set_xlabel("trade #")
ax1.set_ylabel("price ($)")
ax1.set_title("Corrected Lee–Ready signs (green=buy, red=sell)")
ax1.set_xticks(t)
ax1.legend(loc="lower right")
ax1.text(0.02, 0.97,
         f"{n_buy} buys / {n_sell} sells\nOFI_LR = 10×({n_buy}−{n_sell}) = {ofi_lr}",
         transform=ax1.transAxes, va="top", fontsize=9,
         bbox=dict(boxstyle="round", facecolor="white", alpha=0.85))

# Panel 2: BVC on the 3 volume bars
x = np.arange(1, 4)
w = 0.35
ax2.bar(x - w / 2, buy_v, width=w, color=PALETTE["profit"], edgecolor="black",
        linewidth=0.6, label="est. buy volume")
ax2.bar(x + w / 2, sell_v, width=w, color=PALETTE["loss"], edgecolor="black",
        linewidth=0.6, label="est. sell volume")
for i in range(3):
    ax2.text(x[i], buy_v[i] + 1.2, f"{buy_v[i]:.2f}", ha="center", fontsize=8)
    ax2.text(x[i], sell_v[i] + 1.2, f"{sell_v[i]:.2f}", ha="center", fontsize=8)
    ax2.text(x[i], 2.5, f"BVC={bvc[i]:+.2f}", ha="center", fontsize=8,
             weight="bold", color=PALETTE["signal2"])
ax2.set_xlabel("volume bar (40 shares each, σₚ=0.10)")
ax2.set_ylabel("volume (shares)")
ax2.set_title("Bulk Volume Classification (BVC, synthetic)")
ax2.set_xticks(x)
ax2.legend()

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S007_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
