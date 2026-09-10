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

rng = np.random.default_rng(9)  # seed 9; tape is fixed below, script regenerates it exactly

# ---- S009 worked-example tape (operator-verified fixed tape; matches chapter S4) ----
days = np.arange(1, 11)
B = np.array([90, 40, 42, 39, 40, 88, 41, 38, 40, 41], dtype=float)
S = np.array([40, 90, 38, 41, 40, 42, 87, 42, 39, 40], dtype=float)
imb = (B - S) / (B + S)
event_day = np.abs(B - S) >= 40  # example event rule: |B-S| >= 40  ->  days 1,2,6,7

alpha, delta, mu, eps = 0.40, 0.50, 50.0, 40.0
PIN = alpha * mu / (alpha * mu + 2 * eps)
print(f"Bbar={B.mean():.1f} Sbar={S.mean():.1f} PIN={PIN:.4f}")
for d, b, s, i_ in zip(days, B, S, imb):
    print(f"day {int(d):2d}: B={int(b):3d} S={int(s):3d} imbalance={i_:+.4f} event={bool(event_day[int(d)-1])}")

fig, (ax1, ax2) = plt.subplots(1, 2, gridspec_kw={"width_ratios": [2.2, 1]})
fig.suptitle("S009 — PIN (probability of informed trading): 10-day synthetic B/S tape", y=1.02)

# Left: daily buyer- vs seller-initiated counts; shaded = inferred information-event days
x = np.arange(10)
w = 0.38
for d in np.where(event_day)[0]:
    ax1.axvspan(d - 0.5, d + 0.5, color=PALETTE["band"], alpha=0.55, zorder=0)
ax1.bar(x - w / 2, B, w, label="buyer-initiated B", color=PALETTE["price"])
ax1.bar(x + w / 2, S, w, label="seller-initiated S", color=PALETTE["volume"])
ax1.set_xticks(x)
ax1.set_xticklabels([f"D{d}" for d in days])
ax1.set_xlabel("day (synthetic)")
ax1.set_ylabel("trade count")
ax1.set_title("Daily B/S counts (shaded = info-event days)")
ax1.legend(loc="upper right")
for d in np.where(event_day)[0]:
    ax1.text(d, max(B[d], S[d]) + 2.5, f"I={imb[d]:+.2f}", ha="center", fontsize=8,
             color=PALETTE["signal"], weight="bold")

# Right: arrival-rate decomposition -> PIN
labels = ["informed\n$\\alpha\\mu = 20$/day", "uninformed\n$\\varepsilon_b{+}\\varepsilon_s = 80$/day"]
vals = [alpha * mu, 2 * eps]
bars = ax2.bar(["arrival rates"], [vals[0]], color=PALETTE["signal"], label=labels[0])
ax2.bar(["arrival rates"], [vals[1]], bottom=[vals[0]], color=PALETTE["volume"], label=labels[1])
ax2.set_ylim(0, 110)
ax2.set_ylabel("expected arrivals / day")
ax2.set_title("Mixture decomposition")
ax2.legend(loc="upper right", fontsize=8)
ax2.text(0, 102, f"PIN = 20/100 = {PIN:.0%}", ha="center", fontsize=12, weight="bold",
         color=PALETTE["signal"], bbox=dict(boxstyle="round", fc="white", ec=PALETTE["signal"]))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S009_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S009_example.png")
