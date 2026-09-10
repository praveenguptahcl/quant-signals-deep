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

# ---- SYNTHETIC TICK TAPE (rng-drawn, seed stated) ----
rng = np.random.default_rng(83)
N_TRADES = 48
prices = np.round(100.0 + np.cumsum(rng.normal(0, 0.35, N_TRADES)), 2)
sizes = rng.choice([100, 200, 300, 500, 800, 1000, 1500], N_TRADES)
# tick-rule sign: +1 if uptick, -1 if downtick, carry forward on zero ticks
signs, prev, carry = np.zeros(N_TRADES, dtype=int), prices[0], 1
for i, p in enumerate(prices):
    if p > prev:
        carry = 1
    elif p < prev:
        carry = -1
    signs[i] = carry
    prev = p
times = [f"09:30:{i * 10 // 60:02d}.{i * 10 % 60:02d}" for i in range(N_TRADES)]

print("Trade  Price    Size  TickSign")
for i in range(N_TRADES):
    print(f"T{i+1:<4d} {prices[i]:>6.2f} {sizes[i]:>6d}  {signs[i]:>+3d}")

# ---- Standard bars: tick bars (every 6 trades), volume bars (every 3000 shares) ----
def boundaries(closes_idx, counts, threshold):
    bounds, cum = [0], 0
    for i, c in enumerate(counts):
        cum += c
        if cum >= threshold:
            bounds.append(i + 1); cum = 0
    return bounds

tick_bounds = boundaries(range(N_TRADES), np.ones(N_TRADES, int), 6)
vol_bounds = boundaries(range(N_TRADES), sizes, 3000)
print(f"Tick bars (6 trades each): {len(tick_bounds)-1} bars, boundaries {tick_bounds}")
print(f"Volume bars (3000 shares each): {len(vol_bounds)-1} bars, boundaries {vol_bounds}")

# ---- Imbalance bars: close when |theta| >= THETA_IMB (signed-share example) ----
# theta_T = sum of tick-sign * shares; THETA_IMB is an example threshold, not an
# institutional standard (production: rolling expected imbalance, see S3).
THETA_IMB = 1500
imb_bounds, cum_theta, thetas = [0], 0, []
for i in range(N_TRADES):
    cum_theta += signs[i] * sizes[i]
    if abs(cum_theta) >= THETA_IMB:
        imb_bounds.append(i + 1); thetas.append(cum_theta); cum_theta = 0
print(f"Imbalance bars (theta = tick-sign x shares, |theta|>={THETA_IMB} (example)): "
      f"{len(imb_bounds)-1} bars, boundaries {imb_bounds}, theta at close {thetas}")

print("Bar  Type        O      H      L      C   #trades")
for k, (a, b) in enumerate(zip(tick_bounds[:-1], tick_bounds[1:])):
    o, h, l, c, n = prices[a], prices[a:b].max(), prices[a:b].min(), prices[b-1], b-a
    print(f"TB{k+1:<3d} tick      {o:>6.2f} {h:>6.2f} {l:>6.2f} {c:>6.2f}  {n:>5d}")
for k, (a, b) in enumerate(zip(vol_bounds[:-1], vol_bounds[1:])):
    o, h, l, c, n = prices[a], prices[a:b].max(), prices[a:b].min(), prices[b-1], b-a
    print(f"VB{k+1:<3d} volume    {o:>6.2f} {h:>6.2f} {l:>6.2f} {c:>6.2f}  {n:>5d}")
for k, (a, b) in enumerate(zip(imb_bounds[:-1], imb_bounds[1:])):
    o, h, l, c, n = prices[a], prices[a:b].max(), prices[a:b].min(), prices[b-1], b-a
    print(f"IB{k+1:<3d} imbalance {o:>6.2f} {h:>6.2f} {l:>6.2f} {c:>6.2f}  {n:>5d}  theta={thetas[k]:+d}")

# ---- Chart: trade prices with the three bar-clock boundary sets ----
fig, ax = plt.subplots()
ax.set_title("S083 — Bar clocks on a 48-trade synthetic tape")
idx = np.arange(N_TRADES)
ax.plot(idx, prices, marker=".", color=PALETTE["price"], lw=1.2, label="Trade price ($, synthetic)")
for b in tick_bounds[1:-1]:
    ax.axvline(b - 0.5, color=PALETTE["signal"], ls=":", lw=1.1)
for b in vol_bounds[1:-1]:
    ax.axvline(b - 0.5, color=PALETTE["profit"], ls="--", lw=1.2)
for b in imb_bounds[1:-1]:
    ax.axvline(b - 0.5, color=PALETTE["signal2"], ls="-", lw=1.6)
from matplotlib.lines import Line2D
ax.legend(handles=[
    Line2D([0], [0], color=PALETTE["price"], marker=".", label="Trade price"),
    Line2D([0], [0], color=PALETTE["signal"], ls=":", label="Tick-bar close (every 6 trades)"),
    Line2D([0], [0], color=PALETTE["profit"], ls="--", label="Volume-bar close (every 3000 sh)"),
    Line2D([0], [0], color=PALETTE["signal2"], ls="-", label="Imbalance-bar close (|θ|≥thr)"),
], loc="best")
ax.set_xlabel("Trade index (synthetic, ~1 trade per 10s)")
ax.set_ylabel("Price ($)")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S083_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S083_example.png")
