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

rng = np.random.default_rng(99)  # fixed seed, stated in chapter text

# ---- Synthetic 10-week Google Trends tape for ticker "XYZQ" (hand-constructed) ----
weeks = np.arange(1, 11)
svi = np.array([18., 22., 19., 25., 21., 24., 23., 20., 88., 64.])

W = 8
z_raw = np.full(10, np.nan)
asvi_deg = np.full(10, np.nan)
for t in range(W, 10):
    win = svi[t - W:t]                       # prior 8 weeks, excluding current
    z_raw[t] = (svi[t] - win.mean()) / win.std(ddof=1)   # reconstruction form, sample sd
    asvi_deg[t] = np.log(svi[t]) - np.log(np.median(win)) # canonical Da-Engelberg-Gao form
z_win = np.clip(z_raw, -5, 5)                 # winsorized at +/-5, per chapter gate

print("wk | SVI | z-form (raw) | z-form (wins +/-5) | ASVI canonical log-median")
for t in range(10):
    if np.isnan(z_raw[t]):
        print(f" {t+1:2d} | {svi[t]:4.0f} |      n/a    |        n/a         |        n/a")
    else:
        print(f" {t+1:2d} | {svi[t]:4.0f} | {z_raw[t]:11.2f} | {z_win[t]:19.2f} | {asvi_deg[t]:23.2f}")

# hand-check week 9 (printed for chapter):
win9 = svi[0:8]
print(f"\nweek-9 check: mean={win9.mean():.2f} sd={win9.std(ddof=1):.4f} "
      f"z={(svi[8]-win9.mean())/win9.std(ddof=1):.2f}")
print(f"week-9 check: median={np.median(win9):.1f} "
      f"DEG={np.log(svi[8]) - np.log(np.median(win9)):.4f}")
win10 = svi[1:9]
print(f"week-10 check: mean={win10.mean():.2f} sd={win10.std(ddof=1):.4f} "
      f"z={(svi[9]-win10.mean())/win10.std(ddof=1):.2f}")
print(f"week-10 check: median={np.median(win10):.1f} "
      f"DEG={np.log(svi[9]) - np.log(np.median(win10)):.4f}")

# ---- Chart: SVI bars + the two ASVI forms ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True)

bars = ax1.bar(weeks, svi, color=PALETTE["volume"], edgecolor=PALETTE["zero"])
bars[8].set_color(PALETTE["signal"])          # attention shock
bars[9].set_color(PALETTE["signal"])
ax1.set_ylabel("weekly SVI (0-100)")
ax1.set_title("S099 — Google Trends attention (ASVI): 10-week synthetic tape (seed 99)")
ax1.tick_params(axis="x", labelbottom=False)
ax1.annotate("attention shock: SVI 88\nvs 21.5 eight-week mean",
             xy=(9, 88), xytext=(5.2, 74), fontsize=9, color=PALETTE["signal"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.95))

ax2.plot(weeks, z_win, color=PALETTE["signal"], marker="o", lw=2,
         label="reconstruction z-form (winsorized +/-5; raw = +27.1 at wk 9)")
ax2.plot(weeks, asvi_deg, color=PALETTE["price"], marker="s", lw=2,
         label="canonical Da-Engelberg-Gao log-median form")
ax2.axhline(3, color=PALETTE["signal"], ls=":", lw=1.2)
ax2.axhline(-3, color=PALETTE["signal"], ls=":", lw=1.2)
ax2.set_ylabel("ASVI (standardized)")
ax2.set_xlabel("week")
ax2.set_ylim(-1, 6)
ax2.legend(loc="upper right")
ax2.annotate("same shock, different answer:\nz explodes on a quiet baseline\nDEG reads +1.41",
             xy=(9, 5), xytext=(2.2, 3.4), fontsize=9, color=PALETTE["zero"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.95))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S099_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
