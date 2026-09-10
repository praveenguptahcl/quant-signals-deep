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

rng = np.random.default_rng(28)  # fixed seed — reproducible synthetic tape

# ---- Synthetic 30-bar 5-min tape (verified worked-example data) ----
# Bars 1-10: ramp to 100.50 (bar-10 high 101.20 = Donchian max over bars 10-29)
opens, highs, lows, closes = [], [], [], []
base = np.linspace(99.70, 100.40, 9)
for c in base:
    o = c - 0.05 + rng.normal(0, 0.02)
    opens.append(o); highs.append(max(o, c) + 0.15)
    lows.append(min(o, c) - 0.15); closes.append(c)
opens.append(100.40); highs.append(101.20); lows.append(99.80); closes.append(100.50)  # bar 10
for _ in range(19):  # bars 11-29: flat compression (exact values)
    opens.append(100.00); highs.append(100.80); lows.append(99.80); closes.append(100.20)
opens.append(100.20); highs.append(102.50); lows.append(100.00); closes.append(102.00)  # bar 30
opens = np.array(opens); highs = np.array(highs); lows = np.array(lows); closes = np.array(closes)
bars = np.arange(1, 31)

# Donchian(20), completed-bar convention: channel at bar t uses PRIOR 20 bars (t-20..t-1)
N = 20
UC = np.full(30, np.nan); LC = np.full(30, np.nan)
for t in range(N, 30):
    UC[t] = highs[t - N:t].max()
    LC[t] = lows[t - N:t].min()
MID = (UC + LC) / 2
# Verified: at bar 30 (index 29) UC=101.20, LC=99.80, MID=100.50; C30=102.00 > 101.20
assert abs(UC[29] - 101.20) < 1e-9 and abs(LC[29] - 99.80) < 1e-9
assert abs(MID[29] - 100.50) < 1e-9 and abs(closes[29] - 102.00) < 1e-9

fig, ax = plt.subplots()
ax.plot(bars, closes, color=PALETTE["price"], lw=2.2, label="Close (5-min bars)")
ax.plot(bars, UC, color=PALETTE["signal"], lw=1.4, ls="--", label="Donchian(20) upper (prior-20 max high)")
ax.plot(bars, LC, color=PALETTE["loss"], lw=1.4, ls="--", label="Donchian(20) lower (prior-20 min low)")
ax.plot(bars, MID, color=PALETTE["signal2"], lw=1.0, ls=":", label="Midline (example)")
ax.fill_between(bars, LC, UC, color=PALETTE["band"], alpha=0.35, label="Channel width")
ax.axvline(30, color=PALETTE["signal"], lw=1.2, ls="-.", alpha=0.7)
ax.scatter([30], [102.00], color=PALETTE["signal"], s=70, zorder=5, label="Bar-30 close 102.00")
ax.annotate("Bar 30 breakout: close 102.00 > UC 101.20\n"
            "(channel excludes bar 30 — completed-bar convention)\n"
            "Earliest fill: bar-31 open (causal timing t→t+1)",
            xy=(30, 102.00), xytext=(13, 103.1), fontsize=9, color=PALETTE["signal"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=PALETTE["signal"], alpha=0.9))
ax.annotate("midline 100.50", xy=(30, 100.50), xytext=(24.5, 100.15), fontsize=9,
            color=PALETTE["signal2"], arrowprops=dict(arrowstyle="->", color=PALETTE["signal2"]))
ax.set_title("S028 — Donchian breakout: 30-bar synthetic 5-min tape")
ax.set_xlabel("Bar (5-min)")
ax.set_ylabel("Price ($)")
ax.set_xlim(0.5, 30.5)
ax.legend(loc="upper left")
# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S028_example.png", bbox_inches="tight")
plt.close()
print("S028 PNG written; bar-30 UC=%.2f LC=%.2f MID=%.2f close=%.2f" % (UC[29], LC[29], MID[29], closes[29]))
