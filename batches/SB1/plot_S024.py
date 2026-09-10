"""Plot script for S024 worked example. Run with cwd=~/workspace/quant-signals-deep."""
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

SEED = 24
rng = np.random.default_rng(SEED)

# --- Synthetic 12-minute tape (seed 24). Design: soft open (price at/below VWAP),
# then buying builds; cross above VWAP at bar 6 on rising volume, holds 3+ bars.
base_close = np.array([100.00, 99.97, 99.94, 99.96, 99.99, 100.04, 100.09,
                       100.13, 100.16, 100.19, 100.21, 100.23])
jitter = np.round(rng.normal(0.0, 0.008, 12), 2)
close = np.round(base_close + jitter, 2)
high = np.round(close + np.abs(np.round(rng.normal(0.020, 0.008, 12), 2)), 2)
low = np.round(close - np.abs(np.round(rng.normal(0.020, 0.008, 12), 2)), 2)
vol = np.array([9100, 8300, 7600, 9400, 11200, 14800, 18600, 21900,
                23400, 20100, 17800, 16500])

tp = np.round((high + low + close) / 3, 2)
vwap = np.round(np.cumsum(tp * vol) / np.cumsum(vol), 2)
dev_bps = np.round((close - vwap) / vwap * 1e4, 1)
above = close > vwap

# Cross + hold rule (matches the chapter text): the cross is DETECTED at the close
# of bar t* (s flips from <=0 to +1); the N-bar hold is the N bars AFTER the cross
# bar (t*+1 .. t*+N) all closing above VWAP. Confirmation completes at the close
# of bar t*+N; the earliest honest fill is the open of bar t*+N+1.
N = 3
trigger = None
for i in range(1, 12 - N):
    if (not above[i - 1]) and above[i] and above[i + 1:i + 1 + N].all():
        trigger = i
        break
# Anchored VWAP re-set at the cross bar (0-based trigger index)
anchor = trigger if trigger is not None else 5
anch_vwap = np.full(12, np.nan)
anch_vwap[anchor:] = np.round(
    np.cumsum(tp[anchor:] * vol[anchor:]) / np.cumsum(vol[anchor:]), 2)
anchor_label = anchor + 1

print("S024 worked-example table (seed 24)")
print("bar |   C    |    V   |   TP   |  VWAP  | AnchVWAP | dev(bps) | above | cross/hold")
for i in range(12):
    av = f"{anch_vwap[i]:7.2f}" if not np.isnan(anch_vwap[i]) else "    n/a"
    mark = ""
    if trigger is not None and i == trigger:
        mark = "<- CROSS"
    if trigger is not None and i > trigger and above[i]:
        mark = "<- holds"
    print(f"{i+1:>2} | {close[i]:6.2f} | {vol[i]:6d} | {tp[i]:6.2f} | {vwap[i]:6.2f} | {av} | "
          f"{dev_bps[i]:7.1f} | {'Y' if above[i] else 'n':^5} | {mark}")
print(f"\nCross detected (N=3 hold): bar {trigger+1 if trigger is not None else 'NONE'}; "
      f"hold bars {trigger+2}-{trigger+N+1}; earliest honest fill: bar {trigger+N+2} open")

x = np.arange(1, 13)
plt.plot(x, close, marker="o", color=PALETTE["price"], label="Synthetic close price")
plt.plot(x, vwap, color=PALETTE["signal"], linewidth=2, label="Session VWAP (from open)")
plt.plot(x, anch_vwap, linestyle="--", color=PALETTE["signal2"],
         label=f"Anchored VWAP (re-set at cross bar {anchor_label})")
if trigger is not None:
    plt.axvline(trigger + 1, color=PALETTE["volume"], linestyle="--", linewidth=1.4,
                label=f"Cross detected: bar {trigger + 1} close (not yet tradable)")
    plt.axvline(trigger + N + 1, color=PALETTE["profit"], linestyle="-", linewidth=1.6,
                label=f"Hold confirmed (N={N}): bar {trigger + N + 1} close")
    plt.annotate(f"earliest honest fill:\nbar {trigger + N + 2} open",
                 xy=(trigger + N + 2, close[trigger + N + 1]),
                 xytext=(trigger + N + 2.6, close[trigger + N + 1] + 0.03),
                 fontsize=9, color=PALETTE["signal"], weight="bold",
                 arrowprops=dict(arrowstyle="->", color=PALETTE["signal"], lw=1.4))
plt.xlabel("Synthetic minute bar (09:31–09:42)")
plt.ylabel("Price ($)")
plt.title("S024 — VWAP cross & anchored VWAP: 12-bar synthetic tape")
plt.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S024_example.png", bbox_inches="tight")
plt.close()
print("saved images/S024_example.png")
