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

# ---- SYNTHETIC TAPE (rng-drawn, seed stated) ----
rng = np.random.default_rng(49)
base = 100.0
closes = [base]
highs, lows, opens = [], [], []
for i in range(10):
    drift = 0.4 * np.sin(i * 1.1) + rng.normal(0, 0.9)
    o = closes[-1]
    c = o + drift
    span = abs(rng.normal(2.4, 0.5))
    skew = rng.uniform(-0.45, 0.45)          # where the close lands inside the range
    h = max(o, c) + span * (0.5 - skew) / 2 + abs(span) * 0.25
    l = min(o, c) - span * (0.5 + skew) / 2 - abs(span) * 0.25
    opens.append(o); highs.append(h); lows.append(l); closes.append(c)
opens, highs, lows = (np.round(np.array(x), 2) for x in (opens, highs, lows))
closes = np.round(np.array(closes[1:]), 2)

ibs = (closes - lows) / (highs - lows)   # in [0, 1]

ENTRY, EXIT = 0.2, 0.5   # example thresholds — not an institutional standard
print("Day   Open    High     Low   Close    IBS")
for t in range(10):
    print(f"D{t+1:<4d}{opens[t]:>6.2f} {highs[t]:>7.2f} {lows[t]:>7.2f} {closes[t]:>7.2f}  {ibs[t]:>6.3f}")

long_days = [t for t in range(10) if ibs[t] < ENTRY]
exit_days = [t for t in range(10) if ibs[t] >= EXIT]
print("Long-signal days (IBS<0.2):", [f"D{t+1}" for t in long_days])
print("Exit-signal days (IBS>=0.5):", [f"D{t+1}" for t in exit_days])

days = np.arange(1, 11)
fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [1.6, 1]})
ax1.set_title("S043 — Internal Bar Strength (IBS): 10-day synthetic tape")
ax1.plot(days, closes, marker="o", color=PALETTE["price"], label="Close ($, synthetic)")
for t in long_days:
    ax1.scatter([t + 1], [closes[t]], s=100, color=PALETTE["profit"], zorder=5,
                label="Long signal" if t == long_days[0] else None)
for t in exit_days:
    ax1.scatter([t + 1], [closes[t]], s=70, marker="x", color=PALETTE["signal2"],
                zorder=5, label="Exit signal" if t == exit_days[0] else None)
ax1.set_ylabel("Price ($)")
ax1.legend(loc="best")
ax2.plot(days, ibs, marker="s", color=PALETTE["signal"], label="IBS")
ax2.axhline(ENTRY, color=PALETTE["profit"], ls="--", lw=1.2, label=f"Long line ({ENTRY}, example)")
ax2.axhline(EXIT, color=PALETTE["signal2"], ls="--", lw=1.2, label=f"Exit line ({EXIT}, example)")
ax2.set_ylabel("IBS (0-1)")
ax2.set_xlabel("Day")
ax2.set_ylim(-0.05, 1.05)
ax2.set_xticks(days)
ax2.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S043_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S043_example.png")
