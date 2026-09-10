"""Plot script for S025 worked example. Run with cwd=~/workspace/quant-signals-deep."""
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

SEED = 25
rng = np.random.default_rng(SEED)

# --- Synthetic 13 half-hour bars (seed 25), one session.
# First half-hour return +0.42% (incl. overnight gap), last half-hour +0.31%: momentum day.
ret_bps = np.round(rng.normal(0.0, 14.0, 13), 1)
ret_bps[0] = 42.0
ret_bps[12] = 31.0
ret_bps[1:-1] = np.round(ret_bps[1:-1] / 2.0, 1)  # calmer midday (keep sign pattern mild)

price = np.empty(13)
price[0] = 100.00 * (1 + ret_bps[0] / 1e4)
for j in range(1, 13):
    price[j] = price[j - 1] * (1 + ret_bps[j] / 1e4)
price = np.round(price, 2)
cum_bps = np.round(np.cumsum(ret_bps), 1)

L = 1  # signal uses the first half-hour return only (example variant of the report's window)
signal = 1 if ret_bps[0] > 0 else (-1 if ret_bps[0] < 0 else 0)
# Toy trade: enter at start of last half-hour (bar 13 open), exit at close.
entry_px = np.round(price[11], 2)
exit_px = price[12]
trade_bps = np.round((exit_px / entry_px - 1) * 1e4 * signal, 1)

def slot_label(j):
    # slot j covers [09:30 + 30*j, 10:00 + 30*j) ET
    smin = 9 * 60 + 30 + 30 * j
    emin = smin + 30
    return f"{smin // 60:02d}:{smin % 60:02d}"

labels = [slot_label(j) for j in range(13)]

print("S025 worked-example table (seed 25)")
print(" j | slot  | ret(bps) | cum(bps) |  close  | note")
for j in range(13):
    note = ""
    if j == 0:
        note = "<- formation return r1 = +42.0 bps => signal = +1 (LONG)"
    if j == 12:
        note = f"<- trade: enter {entry_px:.2f} -> exit {exit_px:.2f} = {trade_bps:+.1f} bps (gross, synthetic)"
    print(f"{j+1:>2} | {labels[j]} | {ret_bps[j]:8.1f} | {cum_bps[j]:8.1f} | {price[j]:6.2f} | {note}")
print(f"\nSignal = sign(first half-hour return) = {signal:+d}; toy trade P&L = {trade_bps:+.1f} bps before costs")

x = np.arange(13)
plt.plot(x, cum_bps, marker="o", color=PALETTE["price"], label="Synthetic cumulative intraday return (bps)")
plt.axvspan(11.5, 12.5, color=PALETTE["band"], alpha=0.45, label="Last half-hour (trade window)")
plt.axhline(0, color=PALETTE["zero"], linewidth=1)
plt.plot(0, cum_bps[0], marker="D", markersize=10, color=PALETTE["signal2"],
         label="Formation return r1 = +42 bps")
plt.annotate(f"enter long\n@ slot 15:30 ({entry_px:.2f})", xy=(12, cum_bps[12]),
             xytext=(8.5, cum_bps[12] + 25),
             arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]),
             fontsize=9, color=PALETTE["profit"])
plt.xlabel("Half-hour slot (13 per session)")
plt.ylabel("Cumulative return (bps)")
plt.xticks(x, labels, rotation=45)
plt.title("S025 — Intraday time-series momentum: 13-slot synthetic session")
plt.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S025_example.png", bbox_inches="tight")
plt.close()
print("saved images/S025_example.png")
