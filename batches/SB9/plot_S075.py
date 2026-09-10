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

rng = np.random.default_rng(75)  # seed recorded in chapter text

# ---- SYNTHETIC worked example: 10-day dispersion trade (equal weights, 3 stocks) ----
w = 1.0 / 3.0
days = np.arange(1, 11)
index_iv = np.array([27.0]*6 + [30.0, 33.0, 38.0, 40.0])
stock_ivs = np.array([[33., 35., 37.]]*6 + [[33., 35., 37.]]*2 + [[38., 40., 42.]]*2)
realized_corr = np.array([0.30, 0.28, 0.32, 0.29, 0.31, 0.30, 0.55, 0.75, 0.92, 0.97])

def implied_corr(sig_I, sigs):
    num = sig_I**2 - np.sum(w**2 * sigs**2)
    den = 2 * w**2 * (sigs[0]*sigs[1] + sigs[0]*sigs[2] + sigs[1]*sigs[2])
    return num / den

rho_impl = np.array([implied_corr(index_iv[d], stock_ivs[d]) for d in range(10)])
spread_pnl = 1000.0 * (rho_impl - realized_corr)          # $1,000 per corr point (example scaling)
index_iv_delta = np.diff(index_iv, prepend=index_iv[0])
vega_bleed = -1000.0 * np.clip(index_iv_delta, 0, None)    # short index variance leg, -$1,000/vol-pt (example)
daily_total = spread_pnl + vega_bleed
cum_pnl = np.cumsum(daily_total)

print("day | idxIV | stockIVs | rho_impl | rho_real | spread$ | vega$ | daily$ | cum$")
for d in range(10):
    print(f"{days[d]:>3} | {index_iv[d]:5.1f} | {stock_ivs[d,0]:.0f}/{stock_ivs[d,1]:.0f}/{stock_ivs[d,2]:.0f} | "
          f"{rho_impl[d]:.4f} | {realized_corr[d]:.2f} | {spread_pnl[d]:+7.1f} | {vega_bleed[d]:+7.1f} | "
          f"{daily_total[d]:+8.1f} | {cum_pnl[d]:+9.1f}")

# ---- chart ----
fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
ax1.plot(days, rho_impl, color=PALETTE["price"], marker="o", ms=5, label="implied correlation (index vs constituents)")
ax1.plot(days, realized_corr, color=PALETTE["signal"], marker="s", ms=5, ls="--", label="realized correlation (synthetic)")
ax1.axvspan(8.5, 10.5, color=PALETTE["signal"], alpha=0.08)
ax1.text(9.5, 0.62, "correlation spike\n(correlations \u2192 1)", color=PALETTE["signal"], fontsize=9, ha="center")
ax1.set_ylabel("correlation")
ax1.set_title("S075 \u2014 Dispersion trading: 10-day synthetic example (correlation spike breaks the trade)")
ax1.legend(loc="upper left")
ax1.set_ylim(0.15, 1.08)

ax2.plot(days, cum_pnl, color=PALETTE["profit"], marker="o", ms=5, label="cumulative dispersion P&L ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.fill_between(days, cum_pnl, 0, where=(cum_pnl >= 0), color=PALETTE["profit"], alpha=0.18)
ax2.fill_between(days, cum_pnl, 0, where=(cum_pnl < 0), color=PALETTE["loss"], alpha=0.18)
ax2.annotate("short index leg bleeds as index IV reprices", xy=(8, cum_pnl[7]), xytext=(5.5, -1500),
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]), fontsize=9, ha="center")
ax2.set_xlabel("synthetic day")
ax2.set_ylabel("cumulative P&L ($)")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S075_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
