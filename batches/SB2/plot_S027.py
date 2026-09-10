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

# ---- DATA: synthetic 6-day session, seed 27 ----
rng = np.random.default_rng(27)
# anchor prices: P930, P1530, Pclose per day (synthetic, $)
P930   = np.array([100.00, 101.40, 99.60, 100.80, 102.20, 100.10])
P1530  = np.array([101.40, 100.60, 100.90, 101.90, 100.90, 100.70])
Pclose = np.array([101.90, 100.10, 101.30, 102.40, 100.40, 100.50])
r_first = P1530 / P930 - 1          # open->15:30 return (signal side)
r_last  = Pclose / P1530 - 1        # 15:30->close return (hold return)
pos = np.sign(r_first)              # signal = sign(first-half return)
pnl = pos * r_last                  # intraday trade P&L
hit = np.sum(pnl > 0)
for i in range(6):
    print(f"day{i+1}: r_first={r_first[i]*100:+.2f}% r_last={r_last[i]*100:+.2f}% "
          f"pos={pos[i]:+.0f} pnl={pnl[i]*100:+.2f}%")
print("hit-rate %.0f/6, avg pnl/day %.2f%%" % (hit, pnl.mean() * 100))

x = np.arange(1, 7)
w = 0.35
fig, ax = plt.subplots()
b1 = ax.bar(x - w/2, r_first * 100, w, color=PALETTE["price"], label="first-half return (9:30→15:30, signal)")
b2 = ax.bar(x + w/2, r_last * 100, w, color=PALETTE["signal"], label="last-half return (15:30→close, hold)")
ax.axhline(0, color=PALETTE["zero"], lw=1)
for i, v in enumerate(pnl):
    ax.annotate(f"{v*100:+.2f}%", xy=(i + 1 + w/2, r_last[i] * 100),
                xytext=(0, 8 if r_last[i] >= 0 else -14), textcoords="offset points",
                ha="center", fontsize=8,
                color=PALETTE["profit"] if v > 0 else PALETTE["loss"], weight="bold")
ax.set_title("S027 — End-of-day momentum: 6-day synthetic session returns")
ax.set_xlabel("synthetic trading day")
ax.set_ylabel("return (%)")
ax.set_xticks(x)
ax.legend(loc="upper right")
ax.set_ylim(min(r_first.min(), r_last.min()) * 100 - 0.6, max(r_first.max(), r_last.max()) * 100 + 0.6)
ax.text(0.02, 0.97, f"signal = sign(9:30→15:30) → hit-rate {hit}/6 (synthetic, before costs)",
        transform=ax.transAxes, fontsize=9, va="top", color=PALETTE["zero"])

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S027_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
