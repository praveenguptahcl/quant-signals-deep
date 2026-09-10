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

# ---- SYNTHETIC DATA (seed 78) ----
# AR(1) on 1-min mid-price returns (basis points): r_t = phi*r_{t-1} + eps_t
rng = np.random.default_rng(78)
phi = 0.28            # example fitted coefficient (rolling window estimate)
sig_eps = 4.5         # bp, residual std from the same window
cost_gate = 2.5       # bp — example round-trip cost threshold (NOT a standard)
n = 12
r = np.zeros(n)
r[0] = rng.normal(0, sig_eps)
for t in range(1, n):
    r[t] = phi * r[t - 1] + rng.normal(0, sig_eps)
f = np.concatenate([[np.nan], phi * r[:-1]])      # one-step forecast, causal
innov = r - np.where(np.isnan(f), 0.0, f)         # forecast innovation
trade = np.abs(f) > cost_gate
direction = np.where(f > 0, "long", "short")

print("S078 worked-example table (bp), seed=78")
print(" t | r_t | f_t | innov | |f|>2.5bp | action")
for t in range(n):
    fs = "  -- " if np.isnan(f[t]) else f"{f[t]:+.2f}"
    print(f"{t:2d} | {r[t]:+.2f} | {fs} | {innov[t]:+.2f} | {str(trade[t] if not np.isnan(f[t]) else False):>5} | "
          f"{'NONE' if np.isnan(f[t]) or not trade[t] else ('BUY ' if direction[t]=='long' else 'SELL')}")

# ---- PLOT ----
fig, axes = plt.subplots(2, 1, sharex=True, figsize=(10, 5.2))
t = np.arange(n)
ax = axes[0]
ax.plot(t, r, "o-", color=PALETTE["price"], label="realized 1-min return r_t (bp)")
ax.plot(t[1:], f[1:], "s--", color=PALETTE["signal"], label="AR(1) forecast f_t = 0.28·r_{t-1} (bp)")
ax.axhline(cost_gate, color=PALETTE["signal2"], ls=":", label="cost gate ±2.5 bp (example)")
ax.axhline(-cost_gate, color=PALETTE["signal2"], ls=":")
ax.set_ylabel("return (bp)")
ax.set_title("S078 — AR(1) forecast vs realized 1-min returns: synthetic 12-bar tape")
ax.legend(loc="best")

ax2 = axes[1]
ax2.bar(t, innov, color=[PALETTE["profit"] if v > 0 else PALETTE["loss"] for v in innov],
        label="innovation ε̂_t = r_t − f_t (bp)")
for i in np.where(trade)[0]:
    ax2.annotate("TRADE", (i, innov[i]), textcoords="offset points", xytext=(0, 8),
                 ha="center", fontsize=8, color=PALETTE["signal"], weight="bold")
ax2.set_xlabel("bar t (1-min mid-price returns, seed 78)")
ax2.set_ylabel("innovation (bp)")
ax2.legend(loc="best")
plt.tight_layout()

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S078_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
