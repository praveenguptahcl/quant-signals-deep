"""S068 worked-example chart — synthetic VIX term structure (seed 68)."""
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

# ---- SYNTHETIC WORKED EXAMPLE (seed 68) ----
rng = np.random.default_rng(68)
days = np.arange(1, 11)
# Calm regime days 1-6, stress spike days 7-8, settle days 9-10
vix = np.array([16.2, 16.8, 15.9, 17.1, 17.6, 18.0, 28.4, 33.7, 21.2, 18.3])
vix9d = np.array([14.1, 14.6, 13.8, 15.0, 15.4, 15.8, 25.9, 30.8, 19.4, 16.5])
vx1 = np.array([16.8, 17.4, 16.4, 17.8, 18.2, 18.6, 29.9, 35.6, 22.3, 19.0])
vx2 = np.array([17.5, 18.1, 17.1, 18.5, 18.9, 19.3, 28.1, 32.4, 21.9, 19.4])
slope = np.round(vx2 - vx1, 2)  # VX2 - VX1: >0 contango, <0 backwardation
rel = np.round(vx2 / vx1 - 1.0, 4) * 100  # percent
print("day  VIX  VIX9D  VX1   VX2   slope  F2/F1-1")
for d, a, b, c, e, s, r in zip(days, vix, vix9d, vx1, vx2, slope, rel):
    print(f"{d:>3}  {a:5.1f}  {b:5.1f}  {c:5.1f}  {e:5.1f}  {s:+5.1f}  {r:+5.1f}%")

plt.plot(days, vix, marker="o", color=PALETTE["price"], label="VIX (spot, 30d IV)")
plt.plot(days, vx1, marker="s", color=PALETTE["signal"], label="VX1 (front-month future)")
plt.plot(days, vx2, marker="^", color=PALETTE["signal2"], label="VX2 (second-month future)")
plt.fill_between(days, vx1, vx2, where=(vx2 >= vx1), color=PALETTE["profit"], alpha=0.15,
                 label="Contango (VX2>VX1)")
plt.fill_between(days, vx1, vx2, where=(vx2 < vx1), color=PALETTE["loss"], alpha=0.25,
                 label="Backwardation (VX2<VX1)")
plt.annotate("stress: curve inverts\nslope = -3.2", xy=(8, 34), xytext=(3.2, 31),
             arrowprops=dict(arrowstyle="->", color=PALETTE["loss"]),
             color=PALETTE["loss"], fontsize=9)
plt.title("S068 — VIX term structure: 10-day synthetic term-curve example")
plt.xlabel("Day (synthetic)")
plt.ylabel("Index / futures level (points)")
plt.xticks(days)
plt.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S068_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
