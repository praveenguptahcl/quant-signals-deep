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

rng = np.random.default_rng(97)  # fixed seed, stated in chapter text

# ---- Synthetic 10-day social tape (hand-constructed; seed 97 fixes baseline jitter) ----
days = np.arange(1, 11)
base = rng.integers(-6, 7, size=10)                    # small baseline jitter, seed 97
posts = np.array([128, 141, 122, 139, 131, 410, 980, 720, 390, 185]) + base
posts[5:8] = [410, 980, 720]                          # attention spike days 6-8
authors = np.array([101, 104, 90, 105, 97, 152, 210, 268, 203, 141])
raw_sent = np.array([0.05, -0.02, 0.08, 0.03, -0.05, 0.25, 0.45, 0.18, -0.10, -0.02])
wtd_sent = np.array([0.04, -0.02, 0.07, 0.02, -0.04, 0.12, 0.064, 0.10, -0.06, -0.02])
hhi = np.array([0.021, 0.023, 0.022, 0.020, 0.024, 0.090, 0.317, 0.180, 0.075, 0.030])

# ---- Message-volume z-score: trailing 5-day window, sample sd (ddof=1) ----
z = np.full(10, np.nan)
for t in range(5, 10):
    w = posts[t - 5:t]
    z[t] = (posts[t] - w.mean()) / w.std(ddof=1)

print("day | posts | authors | raw_sent | wtd_sent | hhi   | vol_z (5d, sample sd)")
for d in range(10):
    zs = f"{z[d]:7.2f}" if not np.isnan(z[d]) else "    n/a"
    print(f" {d+1:2d} | {posts[d]:5d} | {authors[d]:7d} | {raw_sent[d]:8.3f} | "
          f"{wtd_sent[d]:8.3f} | {hhi[d]:.3f} | {zs}")
# hand-check values printed for chapter:
w6 = posts[0:5]
print(f"\nday-6 window mean={w6.mean():.2f} sd={w6.std(ddof=1):.4f} "
      f"z={(posts[5]-w6.mean())/w6.std(ddof=1):.2f}")

# ---- Day-7 eight-post micro-table (hand-computed; see chapter) ----
w = np.array([0.2, 0.2, 0.3, 0.4, 0.9, 0.6, 0.6, 0.8])   # user quality
q = np.array([0.1, 0.1, 0.2, 0.3, 0.9, 0.7, 0.6, 0.8])   # originality/bot adjustment
s = np.array([1.0, 1.0, 0.8, 0.9, 0.2, 0.3, -0.2, -0.4]) # signed post sentiment
wq = w * q
print(f"\nday-7: unweighted mean s = {s.mean():.3f}; "
      f"weighted = {(wq*s).sum()/wq.sum():.4f} (sum wq*s={(wq*s).sum():.3f}, sum wq={wq.sum():.2f})")
# concentration HHI hand-check: shares 0.55,0.08,0.06,0.05,0.04 + 205 small authors
shares = np.array([0.55, 0.08, 0.06, 0.05, 0.04])
rest = (1 - shares.sum()) / 205
print(f"day-7 HHI = {(shares**2).sum() + 205*rest**2:.4f}")

# ---- Chart: top = volume + z; bottom = concentration + weighted sentiment ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True)

bars1 = ax1.bar(days, posts, color=PALETTE["volume"], edgecolor=PALETTE["zero"],
                label="posts/day")
ax1.set_ylabel("posts / day")
ax1.tick_params(axis="x", labelbottom=False)
ax1b = ax1.twinx()
ln = ax1b.plot(days, z, color=PALETTE["signal"], marker="o", lw=2,
               label="volume z-score (5-day, sample sd)")
ax1b.axhline(3, color=PALETTE["signal"], ls=":", lw=1.2)
ax1b.axhline(-3, color=PALETTE["signal"], ls=":", lw=1.2)
ax1b.set_ylabel("z-score (sd units)")
ax1b.set_ylim(-4.5, 30)
ax1.set_title("S097 — Social/media sentiment: 10-day synthetic tape (seed 97)")
ax1.annotate("attention spike\nz = +%.1f" % z[5],
             xy=(6, z[5]), xytext=(7.8, 24), fontsize=9, color=PALETTE["signal"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.95))
h1, l1 = ax1.get_legend_handles_labels(); h2, l2 = ax1b.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, loc="upper left")

bars2 = ax2.bar(days, hhi, color=PALETTE["signal2"], edgecolor=PALETTE["zero"],
                label="concentration HHI (0-1)")
ax2.set_ylabel("HHI concentration")
ax2.set_ylim(0, 0.40)
ax2b = ax2.twinx()
ln2 = ax2b.plot(days, wtd_sent, color=PALETTE["price"], marker="s", lw=2,
                label="weighted signed sentiment (-1..+1)")
ax2b.plot(days, raw_sent, color=PALETTE["price"], lw=1, ls="--", alpha=0.6,
          label="raw mean sentiment (for contrast)")
ax2b.set_ylabel("sentiment (-1..+1)")
ax2b.set_ylim(-0.6, 0.7)
ax2.set_xlabel("day")
ax2.annotate("day 7: HHI 0.317 — bot-dominated\nraw +0.45 collapses to weighted +0.06",
             xy=(7, hhi[6]), xytext=(3.2, 0.30), fontsize=9, color=PALETTE["zero"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.95))
h3, l3 = ax2.get_legend_handles_labels(); h4, l4 = ax2b.get_legend_handles_labels()
ax2.legend(h3 + h4, l3 + l4, loc="upper right")
fig.text(0.01, 0.01, "twin axes justified: left = counts/index (0-1), right = unitless z / sentiment",
         fontsize=7, color="#7f8c8d")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S097_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
