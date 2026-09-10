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

# ---- S020 synthetic worked example: retail vs institutional imbalance around an event ----
SEED = 2020
rng = np.random.default_rng(SEED)
days = np.arange(-20, 21)  # event day = 0 (e.g. an earnings announcement)

# Institutional imbalance: quiet positive drift before the event (informed leakage),
# unwinds after. Retail imbalance: noisy, attention-driven, contrarian dip at the event.
inst = 0.02 * days / 20.0 + rng.normal(0, 0.03, days.size)
inst[days >= 0] -= 0.10 * np.exp(-(days[days >= 0]) / 4.0)
inst[days < 0] += 0.10 * np.exp(days[days < 0] / 8.0)
retail = rng.normal(0, 0.06, days.size)
retail[days == 0] = -0.28          # attention-driven contrarian spike on the event day
retail[(days == 1) | (days == -1)] += -0.06

print("day | retail_IMB | inst_IMB")
for d, r, s in zip(days, retail, inst):
    if -4 <= d <= 4:
        print(f"{d:+3d} | {r:+.3f}      | {s:+.3f}")

fig, ax = plt.subplots()
ax.plot(days, retail, "o-", color=PALETTE["signal"], ms=4, lw=1.5,
        label="retail imbalance (BJZZ-style, synthetic)")
ax.plot(days, inst, "s-", color=PALETTE["price"], ms=4, lw=1.5,
        label="institutional imbalance (synthetic)")
ax.axvline(0, color=PALETTE["zero"], ls="--", lw=1.2)
ax.text(0.5, 0.93, "event day", transform=ax.transAxes, ha="center", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.9))
ax.axhline(0, color=PALETTE["zero"], ls=":", lw=1.0)
ax.set_xlim(-20, 20)
ax.set_xlabel("days relative to event")
ax.set_ylabel("order imbalance (buy − sell) / total")
ax.set_title("S020 — Retail vs institutional imbalance: synthetic 41-day event window")
ax.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S020_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S020_example.png")
