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

# ---- SYNTHETIC WORKED EXAMPLE (seed 94094) ----
# 12 synthetic 5-minute bins, 9:30-10:30. Baseline = 20-day average volume for
# the same time-of-day bin (k shares). Two institutional events: bin 4 (index 3)
# prints two buy blocks; bin 9 (index 8) prints one sell block.
rng = np.random.default_rng(94094)
labels = ["9:30", "9:35", "9:40", "9:45", "9:50", "9:55",
          "10:00", "10:05", "10:10", "10:15", "10:20", "10:25"]
baseline = np.array([120, 90, 70, 60, 55, 50, 48, 50, 55, 65, 80, 100], dtype=float)
mult = np.array([1.1, 0.9, 1.2, 3.4, 1.5, 0.8, 1.0, 1.3, 2.8, 1.6, 1.1, 0.9])
actual = np.round(baseline * mult + rng.normal(0, 3.0, 12), 0)
rvol = np.round(actual / baseline, 2)
# synthetic signed blocks (k shares); Lee-Ready-style sign: buy blocks at the ask
blocks = ["-"] * 12
block_imb = [0.0] * 12
blocks[3] = "2 buy (25k, 18k)"
block_imb[3] = +1.0
blocks[8] = "1 sell (30k)"
block_imb[8] = -1.0

RVOL_TRIG = 2.0  # example — not an institutional standard
trig = rvol > RVOL_TRIG

print("bin  | time  | baseline_k | actual_k | RVOL | blocks          | trig")
for i in range(12):
    print(f"{i+1:>3}  | {labels[i]:>5} | {baseline[i]:>10.0f} | {actual[i]:>8.0f} | "
          f"{rvol[i]:>4.2f} | {blocks[i]:<15} | {'YES' if trig[i] else '-'}")
print(f"\nRVOL trigger = {RVOL_TRIG} (example); triggered bins: "
      f"{[i+1 for i in range(12) if trig[i]]}")

# ---- CHART ----
fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, gridspec_kw={"hspace": 0.08})
x = np.arange(12)
w = 0.36
ax1.bar(x - w / 2, baseline, w, color=PALETTE["volume"], label="20-day avg, same time-of-day (k sh)")
ax1.bar(x + w / 2, actual, w, color=PALETTE["price"], label="actual volume (k sh)")
for i in (3, 8):
    ax1.annotate("block", xy=(x[i], actual[i]), xytext=(0, 8),
                 textcoords="offset points", ha="center", fontsize=8,
                 color=PALETTE["signal"], weight="bold")
ax1.set_ylabel("Volume (k shares)")
ax1.legend(loc="upper right")
ax1.set_title("S094 — RVOL + signed blocks: synthetic 12-bin morning tape (seed 94094)")

ax2.plot(x, rvol, color=PALETTE["signal2"], marker="o", linewidth=2.0, label="RVOL")
ax2.axhline(RVOL_TRIG, color=PALETTE["signal"], linestyle="--", linewidth=1.5,
            label=f"trigger = {RVOL_TRIG} (example)")
ax2.scatter([3], [rvol[3]], s=160, marker="^", color=PALETTE["profit"],
            edgecolor=PALETTE["zero"], zorder=5, label="buy blocks")
ax2.scatter([8], [rvol[8]], s=160, marker="v", color=PALETTE["loss"],
            edgecolor=PALETTE["zero"], zorder=5, label="sell block")
ax2.set_xticks(x)
ax2.set_xticklabels(labels, rotation=30, ha="right")
ax2.set_xlabel("5-min bin (ET)")
ax2.set_ylabel("RVOL (ratio)")
ax2.set_ylim(0, max(rvol) * 1.15)
ax2.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S094_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S094_example.png")
