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

rng = np.random.default_rng(46)  # seed 46

# ---- SYNTHETIC U-SHAPE SEASONALITY (seed 46) ----
# 39 ten-minute buckets, 9:30 -> 16:00. Season: high vol/volume at open & close, low at lunch.
B = 39
b = np.arange(B)
vol_season = 8.0 + 14.0 * np.exp(-((b - 4) / 6.0) ** 2) + 16.0 * np.exp(-((b - 35) / 5.0) ** 2)   # bp
vlm_season = 0.35 + 1.10 * np.exp(-((b - 4) / 5.0) ** 2) + 1.30 * np.exp(-((b - 35) / 4.0) ** 2)  # volume index
vol_obs = vol_season * (1.0 + rng.normal(0, 0.06, B))
vlm_obs = vlm_season * (1.0 + rng.normal(0, 0.06, B))

def hhmm(i):
    mins = 9 * 60 + 30 + i * 10
    return f"{mins // 60:02d}:{mins % 60:02d}"

print("== S046 synthetic U-shape profile (seed 46): every 4th bucket + lunch ==")
print(" bkt | clock | vol_season(bp) | vol_obs(bp) | vlm_index")
for i in list(range(0, B, 4)) + [19]:
    print(f" {i:3d} | {hhmm(i)} | {vol_season[i]:12.2f} | {vol_obs[i]:10.2f} | {vlm_obs[i]:9.2f}")

# worked example: deseasonalize one session's bucket moves (5 key buckets)
keys = [0, 6, 13, 21, 38]   # open, 10:30, ~11:40 lunch, 13:00, close
S_b = np.array([21.5, 10.2, 7.8, 9.6, 23.1])   # prior-20-session mean |return| (bp) — synthetic season
x_b = np.array([19.0, 11.5, 14.0, 8.0, 25.0])  # this session's |return| (bp) — synthetic
z_b = x_b / S_b
thr = 1.5  # example threshold
print("== S046 deseasonalization worked example (synthetic) ==")
print(" bucket      | S_b prior-20d (bp) | x_b session (bp) | z = x/S | trade?")
for i, kk in enumerate(keys):
    print(f" {hhmm(kk)} ({['open','10:30','lunch','13:00','close'][i]:>6}) | {S_b[i]:17.1f} | {x_b[i]:16.1f} | {z_b[i]:7.2f} | {'YES — bucket z>1.5' if z_b[i] > thr else 'no'}")

fig, ax1 = plt.subplots()
# dual axes justified: volatility (bp) and volume index are different units sharing one time-of-day clock
ax1.plot(b, vol_obs, color=PALETTE["price"], lw=2.2, marker="o", ms=4, label="avg |10-min return| (bp)")
ax1.plot(b, vol_season, color=PALETTE["signal2"], lw=1.4, ls="--", label="seasonal component S(b) (bp)")
ax1.set_xlabel("10-minute bucket (9:30 → 16:00)")
ax1.set_ylabel("volatility — avg |return| (bp)", color=PALETTE["price"])
ax2 = ax1.twinx()
ax2.bar(b, vlm_obs, color=PALETTE["volume"], alpha=0.45, width=0.9, label="volume index")
ax2.set_ylabel("volume index (session avg = 1.0)", color=PALETTE["volume"])
ax1.set_xticks([0, 9, 19, 29, 38])
ax1.set_xticklabels([hhmm(i) for i in [0, 9, 19, 29, 38]])
ax1.annotate("open auction\nvol + volume spike", xy=(4, vol_obs[4]), xytext=(8, 30),
             fontsize=8, arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]))
ax1.annotate("lunch lull", xy=(19, vol_obs[19]), xytext=(19, 16),
             fontsize=8, ha="center", arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]))
ax1.annotate("close auction\nvol + volume spike", xy=(35, vol_obs[35]), xytext=(27, 31),
             fontsize=8, arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]))
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper center", ncol=3,
           bbox_to_anchor=(0.5, -0.16))
ax1.set_title("S046 — U-shaped intraday volatility/volume seasonality (synthetic 10-min buckets)")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S046_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
