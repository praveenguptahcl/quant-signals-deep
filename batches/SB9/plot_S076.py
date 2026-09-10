import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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

rng = np.random.default_rng(76)  # seed recorded in chapter text

# ---- SYNTHETIC 60-bar series: squeeze -> true breakout (bar 30), later false breakout (bar 46) ----
n = 60
close = np.zeros(n); close[0] = 100.0
seg = np.array([0.012, 0.01, 0.008, 0.011, 0.009, 0.01, 0.007, 0.012, 0.009, 0.01,
                0.008, 0.011, 0.006, 0.01, 0.009, 0.008, 0.012, 0.007, 0.01, 0.009,
                0.008, 0.011, 0.007, 0.01])
for i in range(1, 25):
    close[i] = close[i-1] + seg[i-1]
close[25:30] = close[24] + np.array([0.005, 0.008, 0.010, 0.011, 0.012])
close[30] = close[29] + 0.43                              # true breakout bar
for i in range(31, 37):
    close[i] = close[i-1] + 0.10 - 0.004 * (i - 31)
close[37:46] = np.array([101.02, 100.96, 100.91, 100.87, 100.84, 100.82, 100.81, 100.80, 100.79])
close[46] = 101.32                                        # false breakout bar
close[47:51] = np.array([101.22, 101.08, 100.97, 100.90])
for i in range(51, 60):
    close[i] = close[i-1] + rng.normal(0, 0.03)           # seeded filler noise

r = np.empty(n)
r[0:25] = 0.09; r[25:30] = 0.05; r[30] = 0.54
r[31:37] = np.array([0.27, 0.26, 0.25, 0.24, 0.23, 0.22])
r[37:46] = 0.08; r[46] = 0.46
r[47:51] = np.array([0.24, 0.26, 0.22, 0.20])
r[51:] = np.abs(rng.normal(0.09, 0.02, 9))

open_ = np.empty(n); open_[1:] = close[:-1] + 0.005; open_[0] = 99.99
open_[30] = close[29] + 0.02; open_[31] = close[30] + 0.03
open_[46] = close[45] + 0.02; open_[47] = close[46] + 0.03
high = np.maximum(close, open_) + r * 0.55
low = np.minimum(close, open_) - r * 0.45
high[30] = close[30] + 0.07; low[30] = close[30] - 0.47
high[46] = close[46] + 0.14; low[46] = close[46] - 0.32
rng_bars = high - low

s = pd.Series(close); rr = pd.Series(rng_bars)
ma = s.rolling(10).mean(); sd = s.rolling(10).std()       # 10-bar, 2-sigma bands (example parameter)
upper, lower = ma + 2 * sd, ma - 2 * sd
bw = (upper - lower) / ma
bw_pct = bw.rolling(20, min_periods=8).rank(pct=True) * 100   # squeeze gauge (illustrative window)
avg_r = rr.rolling(10).mean()                             # range-expansion reference

print("Tape A (squeeze -> true breakout), bars 27-32:")
print("bar | O | H | L | C | range | 10b-avgrng | ratio | bw% | upper | lower")
for i in range(27, 33):
    print(f"{i:>3} | {open_[i]:.2f} | {high[i]:.2f} | {low[i]:.2f} | {close[i]:.2f} | "
          f"{rng_bars[i]:.2f} | {avg_r[i-1]:.3f} | {rng_bars[i]/avg_r[i-1]:.2f} | {bw_pct[i]:.1f} | {upper[i]:.2f} | {lower[i]:.2f}")
print("Tape B (expansion false breakout), bars 44-49:")
for i in range(44, 50):
    print(f"{i:>3} | {open_[i]:.2f} | {high[i]:.2f} | {low[i]:.2f} | {close[i]:.2f} | "
          f"{rng_bars[i]:.2f} | {avg_r[i-1]:.3f} | {rng_bars[i]/avg_r[i-1]:.2f} | {bw_pct[i]:.1f} | {upper[i]:.2f} | {lower[i]:.2f}")

# trades: signal at t -> tradable at t+1 (entry at open)
spread, fee = 0.01, 0.003   # example: half-spread $0.01, fee $0.003 per side per share
e1, x1 = open_[31], close[36]; gross1 = x1 - e1; net1 = gross1 - 2 * (spread + fee)
e2, x2 = open_[47], close[49]; gross2 = x2 - e2; net2 = gross2 - 2 * (spread + fee)
print(f"TRADE1 (true): entry bar31 open {e1:.2f}, exit bar36 close {x1:.2f}, gross/share {gross1:+.3f}, net/share {net1:+.3f}, net on 500 sh ${net1*500:+.0f}")
print(f"TRADE2 (false): entry bar47 open {e2:.2f}, exit bar49 close {x2:.2f}, gross/share {gross2:+.3f}, net/share {net2:+.3f}, net on 500 sh ${net2*500:+.0f}")

# ---- chart ----
fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1]})
x = np.arange(n)
ax1.fill_between(x, lower, upper, color=PALETTE["band"], alpha=0.45, label="10-bar 2\u03c3 bands (example)")
ax1.plot(x, close, color=PALETTE["price"], lw=1.6, label="close (synthetic 1-min bars)")
ax1.plot(x, ma, color=PALETTE["zero"], lw=1, ls="--", label="10-bar MA")
# squeeze zone
ax1.axvspan(24.5, 29.5, color=PALETTE["signal2"], alpha=0.12)
ax1.text(27, 101.45, "SQUEEZE\n(bw pct \u2264 5%)", color=PALETTE["signal2"], fontsize=9, ha="center", weight="bold")
# true breakout
ax1.plot(31, e1, "^", color=PALETTE["profit"], ms=11, label="entry (next-bar open)")
ax1.plot(36, x1, "v", color=PALETTE["profit"], ms=11, label="exit (6-bar time stop)")
ax1.annotate("TRUE breakout bar 30\nrange 7.4\u00d7 avg", xy=(30, 100.67), xytext=(12, 100.85),
             arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]), fontsize=9, color=PALETTE["profit"])
# false breakout
ax1.plot(47, e2, "^", color=PALETTE["loss"], ms=11)
ax1.plot(49, x2, "v", color=PALETTE["loss"], ms=11)
ax1.annotate("FALSE breakout bar 46\nrange 3.1\u00d7 avg, reverses", xy=(46, 101.32), xytext=(48, 101.75),
             arrowprops=dict(arrowstyle="->", color=PALETTE["loss"]), fontsize=9, color=PALETTE["loss"])
ax1.set_ylabel("price ($)")
ax1.set_title("S076 \u2014 Volatility breakout / squeeze: 60-bar synthetic example (one true, one false breakout)")
ax1.legend(loc="lower left", ncol=2)

ax2.bar(x, bw_pct.values, color=PALETTE["volume"], alpha=0.8, width=0.8)
ax2.axhline(10, color=PALETTE["signal2"], ls="--", lw=1.2, label="squeeze line: 10th pct (example)")
ax2.set_xlabel("synthetic 1-min bar")
ax2.set_ylabel("bandwidth pct (%)")
ax2.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S076_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
