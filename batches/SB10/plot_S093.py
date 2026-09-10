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

# ---- SYNTHETIC EVENT TABLE (seed 93) ----
# Rule: stale stories move more on day 0 (overreact) and reverse in the following week;
# novel stories drift mildly. Numbers printed below are pasted into S4's table.
rng = np.random.default_rng(93)
n = 10
events = [f"E{i+1}" for i in range(n)]
novelty = np.round(rng.uniform(0.05, 0.98, n), 2)
staleness = 1.0 - novelty
day0_abs = rng.uniform(1.0, 4.0, n)
sign = rng.choice([-1.0, 1.0], n)
day0 = np.round(day0_abs * sign * (0.4 + 0.6 * staleness), 2)
week = np.round(-0.45 * day0 * staleness + rng.normal(0.0, 0.15, n), 2)

print("event | novelty | day0% | week%")
for e, nv, d, w in zip(events, novelty, day0, week):
    print(f"{e:>5} | {nv:7.2f} | {d:+6.2f} | {w:+6.2f}")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2))

x = np.arange(n)
ax1.bar(x, novelty, color=PALETTE["price"], edgecolor="black", linewidth=0.6,
        label="Novelty (1 = brand-new)")
ax1.axhline(0.5, color=PALETTE["signal"], linestyle="--", linewidth=1.5,
            label="Novelty threshold 0.5 (example)")
ax1.set_title("S093 — News novelty scores\n10 synthetic story-events (seed 93)")
ax1.set_xlabel("story event")
ax1.set_ylabel("novelty  (0 = stale, 1 = new)")
ax1.set_xticks(x)
ax1.set_xticklabels(events, fontsize=8)
ax1.legend()

x2 = np.arange(n)
w2 = 0.38
ax2.bar(x2 - w2 / 2, np.abs(day0), width=w2, color=PALETTE["volume"],
        edgecolor="black", linewidth=0.6, label="Day-0 |move| %")
week_colors = [PALETTE["profit"] if v >= 0 else PALETTE["loss"] for v in week]
ax2.bar(x2 + w2 / 2, week, width=w2, color=week_colors,
        edgecolor="black", linewidth=0.6, label="Next-5-day return %")
ax2.axhline(0, color=PALETTE["zero"], linewidth=1)
ax2.set_title("Day-0 move vs next-week reversal")
ax2.set_xlabel("story event")
ax2.set_ylabel("percent")
ax2.set_xticks(x2)
ax2.set_xticklabels(events, fontsize=8)
ax2.legend()

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S093_example.png", bbox_inches="tight")
plt.close()
print("S093 chart written")
