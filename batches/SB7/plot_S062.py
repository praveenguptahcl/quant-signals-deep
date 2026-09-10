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

# ---- SYNTHETIC DATA (seed stated in chapter text) ----
rng = np.random.default_rng(62)

# 10 fictional sector ETFs. Formation leg: open -> 12:00 ET (rank here).
# Holding leg: 12:00 -> 16:00 ET (trade here, flatten at close).
sectors = ["TECH", "FINL", "ENRG", "HLTH", "INDU", "CONS", "UTIL", "MATR", "COMM", "REAL"]
form_ret = rng.normal(0.35, 0.75, len(sectors))            # open->12:00 %, mean +0.35
# Holding leg: mild continuation + noise (illustrative continuation factor 0.25)
hold_ret = 0.25 * form_ret + rng.normal(0, 0.30, len(sectors))

order = np.argsort(form_ret)                              # worst -> best
ranked = [sectors[i] for i in order]
top3 = ranked[-3:][::-1]                                   # winners: long leg
bot3 = ranked[:3]                                         # losers: short leg

print("sector, formation_%, holding_%, leg")
for i in order:
    leg = "LONG" if sectors[i] in top3 else ("SHORT" if sectors[i] in bot3 else "-")
    print(f"{sectors[i]}, {form_ret[i]:+.3f}, {hold_ret[i]:+.3f}, {leg}")

long_leg = hold_ret[[sectors.index(s) for s in top3]].mean()
short_leg = hold_ret[[sectors.index(s) for s in bot3]].mean()
spread = long_leg - short_leg
print(f"long-leg avg: {long_leg:+.3f}% | short-leg avg: {short_leg:+.3f}% | spread: {spread:+.3f}%")

# Intraday cumulative paths for the chart (afternoon session, 8 half-hour steps).
# Paths are mean-adjusted so each leg closes EXACTLY at its table holding-leg value.
t = np.arange(9)  # 12:00, 12:30, ..., 16:00

def exact_close_path(close_value, seed_noise):
    inc = seed_noise - seed_noise.mean() + close_value / 8.0
    return np.concatenate([[0.0], np.cumsum(inc)])

cum_long = exact_close_path(long_leg, rng.normal(0, 0.08, 8))
cum_short = exact_close_path(short_leg, rng.normal(0, 0.08, 8))
assert abs(cum_long[-1] - long_leg) < 1e-9 and abs(cum_short[-1] - short_leg) < 1e-9
labels = [f"{12 + i // 2}:{(i % 2) * 30:02d}" for i in range(9)]

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2))

# Left: formation-period ranking bars
cols = [PALETTE["profit"] if s in top3 else (PALETTE["loss"] if s in bot3 else PALETTE["volume"])
        for s in ranked]
ax1.barh(ranked, form_ret[order], color=cols, edgecolor="#2c3e50")
ax1.axvline(0, color=PALETTE["zero"], lw=1)
ax1.set_xlabel("Formation return, open -> 12:00 (%)")
ax1.set_title("Formation ranking (top 3 long / bottom 3 short)")

# Right: afternoon holding-leg paths, flatten at close
ax2.plot(labels, cum_long, marker="o", color=PALETTE["profit"], lw=2,
         label=f"Winner leg (long), close {long_leg:+.2f}%")
ax2.plot(labels, cum_short, marker="o", color=PALETTE["loss"], lw=2,
         label=f"Loser leg (short), close {short_leg:+.2f}%")
ax2.plot(labels, cum_long - cum_short, ls="--", color=PALETTE["signal2"], lw=1.5,
         label=f"Long-short spread {spread:+.2f}%")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.set_ylabel("Cumulative holding-leg return (%)")
ax2.set_title("Holding leg: 12:00 -> 16:00 (flatten at close)")
ax2.set_xticks(range(9)); ax2.set_xticklabels(labels, rotation=45, ha="right")
ax2.legend(loc="best")
fig.suptitle("S062 — Sector momentum: synthetic 10-ETF day", y=1.02)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S062_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S062_example.png")
