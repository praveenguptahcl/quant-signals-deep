"""Plot script for S040 worked example. Run with cwd=~/workspace/quant-signals-deep."""
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

SEED = 40
rng = np.random.default_rng(SEED)

# --- Synthetic 12-minute tape (seed 40). Price overshoots above VWAP early
# (z > +1.5 at bar 4 -> SHORT fade signal, example threshold), drifts back inside
# the +/-0.25 band at bar 9 -> exit.
base = np.array([100.00, 100.05, 100.10, 100.16, 100.20, 100.18, 100.14,
                 100.10, 100.06, 100.03, 100.00, 99.98])
jitter = np.round(rng.normal(0.0, 0.008, 12), 2)
close = np.round(base + jitter, 2)
high = np.round(close + np.abs(np.round(rng.normal(0.020, 0.008, 12), 2)), 2)
low = np.round(close - np.abs(np.round(rng.normal(0.020, 0.008, 12), 2)), 2)
vol = np.array([8200, 9900, 11400, 13100, 12600, 11200, 10400, 9600,
                8900, 8300, 8100, 7900])

tp = np.round((high + low + close) / 3, 2)
vwap = np.round(np.cumsum(tp * vol) / np.cumsum(vol), 2)
dev = (close - vwap) / vwap                      # fractional deviation
dev_bps = np.round(dev * 1e4, 1)
# Rolling std of the deviation series (window 10, min_periods=5) -> z-score
W = 10
std = np.array([np.std(dev[max(0, i - W + 1):i + 1], ddof=1) if i >= 4 else np.nan
                for i in range(12)])
z = np.round(dev / std, 2)

ENTER_K, EXIT_K = 1.5, 0.25                      # example thresholds — not institutional standards
entry = next((i for i in range(12) if not np.isnan(z[i]) and abs(z[i]) > ENTER_K), None)
exit_, exit_reason = None, ""
if entry is not None:
    side = -int(np.sign(z[entry]))
    band_exit = next((i for i in range(entry + 1, 12)
                      if not np.isnan(z[i]) and abs(z[i]) < EXIT_K), None)
    if band_exit is not None:
        exit_, exit_reason = band_exit, f"|z|<{EXIT_K}"
    else:
        exit_, exit_reason = 11, "TIME STOP (band never re-entered)"
trade_bps = None
if entry is not None and exit_ is not None:
    # side: -1 = short (faded an upside extension), +1 = long
    trade_bps = np.round(side * (close[exit_] - close[entry]) / close[entry] * 1e4, 1)

print("S040 worked-example table (seed 40)")
print("bar |   C    |   VWAP | dev(bps) |  z   | event")
for i in range(12):
    ev = ""
    if i == entry:
        ev = f"<- ENTRY {'SHORT' if side == -1 else 'LONG'} (example |z|>{ENTER_K})"
    if i == exit_:
        ev = f"<- EXIT: {exit_reason}"
    print(f"{i+1:>2} | {close[i]:6.2f} | {vwap[i]:6.2f} | {dev_bps[i]:7.1f} | {z[i]:5.2f} | {ev}")
if entry is not None and exit_ is not None:
    print(f"\nToy fade: {'short' if side == -1 else 'long'} {close[entry]:.2f} -> "
          f"{close[exit_]:.2f} = {trade_bps:+.1f} bps gross (synthetic, no costs, exit: {exit_reason})")

x = np.arange(1, 13)
sig = np.nan_to_num(std, nan=0.0)
upper = vwap * (1 + ENTER_K * sig)
lower = vwap * (1 - ENTER_K * sig)
plt.plot(x, close, marker="o", color=PALETTE["price"], label="Synthetic close price")
plt.plot(x, vwap, color=PALETTE["signal"], linewidth=2, label="Session VWAP")
plt.fill_between(x, lower, upper, color=PALETTE["band"], alpha=0.5,
                 label=f"VWAP ± {ENTER_K}σ band (rolling dev std, example)")
if entry is not None:
    plt.axvline(entry + 1, color=PALETTE["loss"], linestyle=":",
                label=f"Entry bar {entry + 1}: z = {z[entry]:+.2f}")
if exit_ is not None:
    plt.axvline(exit_ + 1, color=PALETTE["profit"], linestyle=":",
                label=f"Exit bar {exit_ + 1}: {exit_reason}")
plt.xlabel("Synthetic minute bar (09:31–09:42)")
plt.ylabel("Price ($)")
plt.title("S040 — VWAP-deviation mean reversion: 12-bar synthetic fade")
plt.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S040_example.png", bbox_inches="tight")
plt.close()
print("saved images/S040_example.png")
