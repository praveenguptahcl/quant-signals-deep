"""S034 plot: synthetic 1-min price path around a scheduled macro announcement.
Seed 34. Chart numbers are the worked-example numbers in batches/SB6/S034.md S4.
Run: python3 batches/SB6/plot_S034.py   (cwd = quant-signals-deep)
"""
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

rng = np.random.default_rng(34)  # stated in chapter text

# ---- synthetic tape: announcement at t=0 (14:00 ET FOMC-style), 1-min bars ----
t = np.arange(-60, 46)                       # minutes relative to release
p0 = 6000.00
noise = rng.normal(0.0, 0.0002, size=t.shape)  # ~2bp/min synthetic noise

drift = np.zeros_like(t, dtype=float)
# pre-window: steady +30bp drift into the release
drift[t < 0] = np.linspace(0.0, 0.0030, np.sum(t < 0))
# announcement: hawkish surprise, -45bp over the first 2 minutes
sel = (t >= 0) & (t <= 2)
drift[sel] = 0.0030 - 0.0045 * ((t[sel] + 1) / 3.0)
# post-window: continuation drift -30bp more over the next 30 minutes
mask = t > 2
drift[mask] = -0.0015 - 0.0030 * (t[mask] - 2) / 30.0
drift[t > 32] = -0.0045

logp = np.log(p0) + drift + np.cumsum(noise) * 0.25
price = np.exp(logp)

# key marks for the worked example (S4 table)
def px(tt):
    return float(price[t == tt][0])

marks = {tt: px(tt) for tt in [-60, -45, -30, -15, -5, 0, 1, 2, 5, 10, 20, 30]}
pre_drift = marks[0] / marks[-60] - 1
entry, exitp = marks[1], marks[30]
trade_ret = entry / exitp - 1  # short
print("S034 worked-example marks (1-min, seed 34):")
for tt, v in marks.items():
    print(f"  t={tt:+4d}  {v:10.2f}")
print(f"pre-drift 60min: {pre_drift*1e4:+.1f} bp")
print(f"announce jump (0->2): {(marks[2]/marks[0]-1)*1e4:+.1f} bp")
print(f"short {entry:.2f} -> {exitp:.2f}: gross {trade_ret*1e4:+.1f} bp")

fig, ax = plt.subplots()
ax.plot(t, price, color=PALETTE["price"], lw=1.6, label="synthetic price (1-min)")
ax.axvspan(-60, 0, color=PALETTE["band"], alpha=0.35, label="pre-window (60 min)")
ax.axvspan(0, 30, color="#f9e79f", alpha=0.35, label="post-window (30 min)")
ax.axvline(0, color=PALETTE["signal"], lw=2.0, ls="--", label="announcement (14:00 ET)")
ax.scatter([1], [entry], color=PALETTE["loss"], s=70, zorder=5, label="enter short t=+1")
ax.scatter([30], [exitp], color=PALETTE["profit"], s=70, zorder=5, label="exit t=+30")
ax.annotate(f"pre-drift {pre_drift*1e4:+.0f} bp", xy=(-30, marks[-30]),
            xytext=(-95, marks[-30] + 6), fontsize=9, color=PALETTE["zero"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]))
ax.annotate(f"surprise {(marks[2]/marks[0]-1)*1e4:+.0f} bp", xy=(2, marks[2]),
            xytext=(12, marks[2] - 4), fontsize=9, color=PALETTE["signal"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]))
ax.set_title("S034 — Scheduled macro-announcement drift: synthetic 1-min path (seed 34)")
ax.set_xlabel("minutes relative to announcement")
ax.set_ylabel("price (index units)")
ax.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S034_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S034_example.png")
