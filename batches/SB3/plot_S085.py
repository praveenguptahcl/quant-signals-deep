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

rng = np.random.default_rng(85)  # SEED 85 — stated in chapter text

# ---- synthetic 20-day spread tape (matches the corrected duck.ai tape values) ----
days = np.arange(1, 21)
spread = np.array([-2., -1., 0., 1., 2., 1., 0., -1., -2., 0.,
                    2., 1., 0., -1., -2., -1., 0., 1., 2., 0.])
sigma_hat = np.sqrt((spread ** 2).sum() / (len(spread) - 1))  # mean ~ 0 -> sqrt(32/19)
z = spread / sigma_hat

# ---- worked example: long spread entered day 15 ----
entry_day, entry = 15, spread[14]
profit, stop, horizon = 1.0, 1.0, 5  # spread points; vertical barrier = day 15+5 = 20
upper, lower = entry + profit, entry - stop
print(f"sigma_hat = sqrt(32/19) = {sigma_hat:.5f}")
print(f"entry day 15: S15 = {entry:.1f} (z15 = {spread[14]/sigma_hat:.3f})")
print(f"profit barrier {upper:.1f} | stop barrier {lower:.1f} | vertical barrier day {entry_day+horizon}")
print("day | S_t | z_t  | barrier check")
label, first_hit = None, None
for i in range(14, 20):
    S = spread[i]; hit = ""
    if label is None:
        if S >= upper: label, hit, first_hit = +1, "PROFIT HIT", i + 1
        elif S <= lower: label, hit, first_hit = -1, "STOP HIT", i + 1
    print(f"{i+1:>3} | {S:>3.0f} | {S/sigma_hat:>+5.3f} | {hit}")
print(f"label y15 = {label} (first touch day {first_hit}, {(first_hit-entry_day)}-day exit)")

# ---- chart ----
fig, ax = plt.subplots()
ax.plot(days, spread, color=PALETTE["price"], lw=1.6, marker="o", ms=4,
        label="synthetic spread (spread points)")
ax.axvspan(entry_day, entry_day + horizon, color=PALETTE["band"], alpha=0.35)
ax.axhline(upper, color=PALETTE["profit"], ls="--", lw=1.4, label="profit barrier (-1.0)")
ax.axhline(lower, color=PALETTE["loss"], ls="--", lw=1.4, label="stop barrier (-3.0)")
ax.axvline(entry_day + horizon, color=PALETTE["zero"], ls=":", lw=1.4,
           label="vertical barrier (day 20)")
ax.scatter([entry_day], [entry], color=PALETTE["signal"], s=110, marker="D",
           zorder=5, label="entry day 15 (long spread)")
ax.scatter([first_hit], [spread[first_hit - 1]], color=PALETTE["profit"], s=110,
           marker="*", zorder=5, label="profit hit day 16 → label +1")
ax.annotate("entry S15 = -2.0\n(z15 = -1.541)", xy=(entry_day, entry),
            xytext=(entry_day - 6.5, entry - 0.7),
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
            fontsize=9, color=PALETTE["zero"])
ax.annotate("profit hit day 16\n1-day exit, y15 = +1", xy=(first_hit, spread[first_hit - 1]),
            xytext=(first_hit + 1.2, spread[first_hit - 1] + 0.9),
            arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]),
            fontsize=9, color=PALETTE["profit"])
ax.set_xlabel("day")
ax.set_ylabel("spread (synthetic spread points)")
ax.set_title("S085 — Triple-barrier labeling: 20-day synthetic spread tape (seed 85)")
ax.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S085_example.png", bbox_inches="tight")
plt.close()
