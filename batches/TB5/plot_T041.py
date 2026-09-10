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

rng = np.random.default_rng(141)

HALF_SPREAD = 0.005   # $/share per side (example cost schedule)
FEE = 0.0035          # $/share per side (example cost schedule)

# (name, entry_min, entry_px, exit_min, exit_px, shares, direction(+1 long/-1 short))
TRADES = [
    ("T1", 605, 200.00, 641, 200.62, 335, +1),
    ("T2", 680, 200.30, 712, 199.85, 167, -1),
    ("T3", 785, 199.90, 820, 199.72, 335, +1),
    ("T4", 890, 200.10, 930, 200.44, 250, +1),
]

# price anchors (minute-of-day, price) — events forced exact below
ANCHORS = [(570, 199.70)] + \
    [(t[1], t[2]) for t in TRADES] + [(t[3], t[4]) for t in TRADES] + [(960, 200.30)]
ANCHORS = sorted(set(ANCHORS))

mins = np.arange(570, 961)
ax_, ay_ = zip(*ANCHORS)
price = np.interp(mins, ax_, ay_) + rng.normal(0, 0.035, len(mins))
# force exact anchor prices at event minutes (chart must match the T4 table)
for m_, p_ in ANCHORS:
    price[mins == m_] = p_

fig, ax = plt.subplots()
# overlay-multiplier regime bands (example thresholds from T4)
ax.axvspan(570, 675, color=PALETTE["profit"], alpha=0.10, label="m = 0.67 (baseline)")
ax.axvspan(675, 770, color=PALETTE["signal"], alpha=0.12, label="m = 0.335 (S076 throttle)")
ax.axvspan(770, 870, color=PALETTE["profit"], alpha=0.10)
ax.axvspan(870, 930, color="#f39c12", alpha=0.14, label="m = 0.50 (intraday throttle)")
ax.axvspan(930, 961, color=PALETTE["profit"], alpha=0.10)
ax.text(622, 200.78, "baseline m=0.67", fontsize=8, color=PALETTE["profit"])
ax.text(690, 200.10, "S076 vol-breakout\nthrottle m=0.335", fontsize=8,
        color=PALETTE["signal"], ha="center")
ax.text(900, 200.62, "intraday throttle\nm=0.50", fontsize=8, color="#7d6608", ha="center")

ax.plot(mins, price, color=PALETTE["price"], lw=1.6, label="SYNX price (synthetic, $)")

total = 0.0
for name, em, ep, xm, xp, sh, d in TRADES:
    gross = d * (xp - ep) * sh
    costs = 2 * sh * (HALF_SPREAD + FEE)
    net = gross - costs
    total += net
    ax.scatter([em], [price[mins == em]], s=90, marker="^",
               color=PALETTE["profit"], zorder=5, edgecolors="black", linewidths=0.7)
    ax.scatter([xm], [price[mins == xm]], s=90, marker="v",
               color=PALETTE["loss"], zorder=5, edgecolors="black", linewidths=0.7)
    ax.annotate(f"{name}\n{net:+.2f}$ net",
                xy=(xm, price[mins == xm][0]), fontsize=8,
                xytext=(14, 18 if net > 0 else -30), textcoords="offset points",
                arrowprops=dict(arrowstyle="-", color="#2c3e50", lw=0.8),
                bbox=dict(boxstyle="round,pad=0.25", fc="white", alpha=0.85))
    print(f"{name}: entry {ep:.2f} x{sh} -> exit {xp:.2f} | gross {gross:+.2f} "
          f"| spread {2*sh*HALF_SPREAD:.2f} | fees {2*sh*FEE:.2f} | net {net:+.2f}")
print(f"TOTAL net: {total:+.2f}")

# sanity: plotted event prices equal the T4 constants
for name, em, ep, xm, xp, sh, d in TRADES:
    assert abs(price[mins == em][0] - ep) < 1e-9, name
    assert abs(price[mins == xm][0] - xp) < 1e-9, name

ax.set_xlim(570, 960)
ax.set_xlabel("Time of day (minutes past midnight ET)")
ax.set_ylabel("Price ($)")
ax.set_title("T041 — HAR Vol-Timing Overlay: synthetic intraday trade timeline with overlay multipliers")
ax.legend(loc="lower left")
ax.set_xticks([570, 630, 690, 750, 810, 870, 930, 960])
ax.set_xticklabels(["09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30", "16:00"])

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T041_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T041_example.png")
