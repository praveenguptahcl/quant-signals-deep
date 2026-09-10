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

# ---- SYNTHETIC DATA (seed 31) ----
rng = np.random.default_rng(31)

# Hand-designed 5-min close tape so the streak pattern is exact; volume jitter via rng.
C = np.array([100.00, 100.15, 100.32, 100.44, 100.61, 100.79,
              100.71, 100.60, 100.55, 100.66, 100.80, 100.95])
C0 = 99.95
O = np.empty_like(C); O[0] = C0; O[1:] = C[:-1]
H = np.maximum(O, C) + 0.03
L = np.minimum(O, C) - 0.03

r = C - np.concatenate(([C0], C[:-1]))
sign = np.sign(r).astype(int)
streak = np.empty(len(C), dtype=int)
streak[0] = 1
for i in range(1, len(C)):
    streak[i] = streak[i - 1] + 1 if sign[i] == sign[i - 1] else 1

vol = (900 + 120 * streak + rng.integers(0, 200, size=len(C))).astype(int)

K1, K2 = 3, 6  # example thresholds
actions = []
for i in range(len(C)):
    a = []
    if streak[i] >= K1:
        a.append(f"continuation {'LONG' if sign[i] > 0 else 'SHORT'} (k1={K1})")
    if streak[i] >= K2:
        a.append(f"EXHAUSTION fade (k2={K2})")
    actions.append("; ".join(a))

print("bar |    O |    H |    L |    C |  vol | sign | streak | action")
for i in range(len(C)):
    print(f"{i+1:3d} | {O[i]:5.2f} | {H[i]:5.2f} | {L[i]:5.2f} | {C[i]:6.2f} "
          f"| {vol[i]:4d} | {sign[i]:+d} | {streak[i]:6d} | {actions[i]}")

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})
x = np.arange(1, len(C) + 1)
ax1.plot(x, C, color=PALETTE["price"], marker="o", ms=4, label="Close (5-min bars)")
# highlight streak runs
ax1.axvspan(0.6, 6.4, color=PALETTE["profit"], alpha=0.12, label="up run (bars 1-6)")
ax1.axvspan(6.6, 9.4, color=PALETTE["loss"], alpha=0.12, label="down run (bars 7-9)")
ax1.axvspan(9.6, 12.4, color=PALETTE["profit"], alpha=0.12, label="up run (bars 10-12)")
for i in range(len(C)):
    ax1.annotate(f"S={streak[i]}", (x[i], C[i]), textcoords="offset points",
                 xytext=(0, 10), ha="center", fontsize=8, color=PALETTE["zero"])
ax1.annotate("continuation trigger\n(k1=3)", xy=(3, C[2]), xytext=(3.5, C[2] - 0.35),
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
             fontsize=9, color=PALETTE["signal"], ha="center")
ax1.annotate("EXHAUSTION fade\n(k2=6)", xy=(6, C[5]), xytext=(7.6, C[5] + 0.28),
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal2"]),
             fontsize=9, color=PALETTE["signal2"], ha="center", weight="bold")
ax1.set_ylabel("Price ($)")
ax1.set_title("S031 — Consecutive-bar streaks: synthetic 12-bar 5-min tape (seed 31)")
ax1.legend(loc="upper left")

ax2.bar(x, vol, color=PALETTE["volume"], width=0.7, label="Volume (shares)")
ax2.set_ylabel("Volume")
ax2.set_xlabel("Bar number (5-min)")
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S031_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
