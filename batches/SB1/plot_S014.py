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

rng = np.random.default_rng(11)  # seed 11 — stated in chapter text

N = 12
# Mid-price walk (12 trades + 3 look-ahead mids for the realized-spread Δ)
midwalk = 100.00 + np.cumsum(rng.normal(0, 0.005, size=N + 3))
spread = rng.choice([0.01, 0.02, 0.03], size=N)
D = rng.choice([1, -1], size=N)                       # aggressor direction
slip = rng.normal(0, 0.002, size=N)                   # inside-spread/price-improvement noise
bid = midwalk[:N] - spread / 2
ask = midwalk[:N] + spread / 2
P = midwalk[:N] + D * spread / 2 + slip               # trade price

DELTA = 3  # realized spread vs mid DELTA trades later (example — not an institutional standard)
eff = 2 * D * (P - midwalk[:N])                       # effective spread
rlz = 2 * D * (midwalk[DELTA:N + DELTA] - midwalk[:N]) # realized spread
imp = eff - rlz                                       # price impact (adverse selection)

# Print the worked-example table (copy into chapter S4)
print("tr | bid | ask | mid | D | price | eff | rlz | impact   (cents)")
for i in range(N):
    print(f"{i+1:>2} | {bid[i]:6.3f} | {ask[i]:6.3f} | {midwalk[i]:6.3f} | {D[i]:+d} "
          f"| {P[i]:6.3f} | {100*eff[i]:+.2f} | {100*rlz[i]:+.2f} | {100*imp[i]:+.2f}")
print(f"avg effective: {100*eff.mean():+.2f} c, avg realized: {100*rlz.mean():+.2f} c, "
      f"avg impact: {100*imp.mean():+.2f} c")

# ---- Plot: stacked bars — realized (bottom) + impact (top) = effective ----
x = np.arange(1, N + 1)
fig, ax = plt.subplots()
ax.bar(x, 100 * rlz, color=PALETTE["profit"], alpha=0.8, label="Realized spread (cents)")
ax.bar(x, 100 * imp, bottom=100 * rlz, color=PALETTE["signal"], alpha=0.8,
       label="Price impact = effective − realized (cents)")
ax.axhline(0, color=PALETTE["zero"], linewidth=1)
ax.axhline(100 * eff.mean(), color=PALETTE["price"], linestyle="--", linewidth=1.4,
           label=f"Avg effective spread {100*eff.mean():.2f} c")
ax.set_title("S014 — Spread decomposition: 12-trade synthetic tape (Δ=3 trades)")
ax.set_xlabel("Trade # (event time)")
ax.set_ylabel("Cents")
ax.set_xticks(x)
ax.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S014_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S014_example.png")
