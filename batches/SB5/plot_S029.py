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

rng = np.random.default_rng(29)  # fixed seed — reproducible synthetic tape

# ---- Same synthetic 30-bar tape as S028 (verified worked-example data) ----
opens, highs, lows, closes = [], [], [], []
base = np.linspace(99.70, 100.40, 9)
for c in base:
    o = c - 0.05 + rng.normal(0, 0.02)
    opens.append(o); highs.append(max(o, c) + 0.15)
    lows.append(min(o, c) - 0.15); closes.append(c)
opens.append(100.40); highs.append(101.20); lows.append(99.80); closes.append(100.50)  # bar 10
for _ in range(19):  # bars 11-29: flat compression (exact)
    opens.append(100.00); highs.append(100.80); lows.append(99.80); closes.append(100.20)
opens.append(100.20); highs.append(102.50); lows.append(100.00); closes.append(102.00)  # bar 30
opens = np.array(opens); highs = np.array(highs); lows = np.array(lows); closes = np.array(closes)
bars = np.arange(1, 31)

# ---- Keltner(20/20/m=2): EMA(20) +/- 2*ATR(20) ----
# NOTE: this worked example uses windows INCLUDING bar 30 (bars 11-30), unlike the
# completed-bar Donchian convention — the mixed-convention pitfall flagged in the chapter.
idx = np.arange(10, 30)  # bars 11..30 (0-based indices 10..29)
c_prev = np.roll(closes, 1)
TR = np.maximum(highs - lows, np.maximum(np.abs(highs - c_prev), np.abs(lows - c_prev)))
ATR20 = TR[idx].mean()                      # simple average per example: 1.075
EMA0 = closes[idx].mean()                    # SMA-seeded EMA: 100.29
K_UP, K_LO = EMA0 + 2 * ATR20, EMA0 - 2 * ATR20  # 102.44 / 98.14
# ---- Bollinger(20/k=2): SMA(20) +/- 2*sigma ----
mu = closes[idx].mean()                      # 100.29
sigma = closes[idx].std(ddof=0)              # population std: 0.3923
B_UP, B_LO = mu + 2 * sigma, mu - 2 * sigma  # 101.0746 / 99.5054
assert abs(ATR20 - 1.075) < 1e-9 and abs(EMA0 - 100.29) < 1e-9
assert abs(K_UP - 102.44) < 1e-9 and abs(sigma - 0.3923) < 1e-4
assert abs(B_UP - 101.0746) < 1e-3

kup = np.full(30, K_UP); klo = np.full(30, K_LO)
bup = np.full(30, B_UP); blo = np.full(30, B_LO)

fig, ax = plt.subplots()
ax.plot(bars, closes, color=PALETTE["price"], lw=2.2, label="Close (5-min bars)")
ax.fill_between(bars, klo, kup, color=PALETTE["band"], alpha=0.35)
ax.plot(bars, kup, color=PALETTE["signal"], lw=1.4, ls="--",
        label="Keltner upper EMA20+2ATR = 102.44")
ax.plot(bars, klo, color=PALETTE["signal"], lw=1.4, ls="--",
        label="Keltner lower EMA20-2ATR = 98.14")
ax.plot(bars, np.full(30, EMA0), color=PALETTE["signal"], lw=1.0, ls=":")
ax.plot(bars, bup, color=PALETTE["signal2"], lw=1.6, ls="-",
        label="Bollinger upper SMA20+2\u03c3 = 101.0746")
ax.plot(bars, blo, color=PALETTE["signal2"], lw=1.6, ls="-",
        label="Bollinger lower SMA20-2\u03c3 = 99.5054")
ax.plot(bars, np.full(30, mu), color=PALETTE["signal2"], lw=1.0, ls=":")
ax.axvline(30, color=PALETTE["zero"], lw=1.2, ls="-.", alpha=0.7)
ax.scatter([30], [102.00], color=PALETTE["zero"], s=70, zorder=5)
ax.scatter([30], [102.50], color=PALETTE["signal"], s=50, zorder=5, marker="^")
ax.annotate("Keltner: close 102.00 < 102.44\nNO close-breakout — high 102.50\nthrough the band only",
            xy=(30, 102.44), xytext=(15.5, 102.95), fontsize=9, color=PALETTE["signal"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=PALETTE["signal"], alpha=0.9))
ax.annotate("Bollinger: close 102.00 > 101.0746\nclose-breakout (bands respond to \u03c3, not range)",
            xy=(30, 101.0746), xytext=(15.5, 100.30), fontsize=9, color=PALETTE["signal2"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["signal2"]),
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=PALETTE["signal2"], alpha=0.9))
ax.set_title("S029 — Keltner vs Bollinger: close-breakout vs high-through distinction")
ax.set_xlabel("Bar (5-min)")
ax.set_ylabel("Price ($)")
ax.set_xlim(0.5, 30.5); ax.set_ylim(97.8, 103.4)
ax.legend(loc="upper left", fontsize=8.5)
# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S029_example.png", bbox_inches="tight")
plt.close()
print("S029 PNG written; ATR=%.3f EMA=%.2f Keltner=%.2f/%.2f Boll=%.4f sigma=%.4f"
      % (ATR20, EMA0, K_UP, K_LO, B_UP, sigma))
