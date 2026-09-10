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

# ---- DATA: synthetic 12-day RVOL breakout tape, seed 32 ----
rng = np.random.default_rng(32)
# OR-window = first 5 minutes; volumes in thousands of shares
or_vol = np.array([120, 95, 260, 140, 310, 110, 85, 220, 130, 280, 100, 150], dtype=float)
# 14-day trailing mean OR-window volume (synthetic baseline, thousands of shares)
baseline = np.array([130, 125, 128, 122, 126, 131, 129, 124, 127, 125, 132, 128], dtype=float)
rvol = or_vol / baseline
THR = 1.5  # example threshold
# synthetic price break direction (+1 up, -1 down, 0 no break) and realized post-break move (R multiples)
break_dir = np.array([0, 0, 1, 0, 1, 0, 0, 1, 0, -1, 0, 1], dtype=float)
move_R    = np.array([0.0, 0.0, 1.8, 0.0, 2.6, 0.0, 0.0, -0.4, 0.0, 1.9, 0.0, 1.2])
valid = (rvol >= THR) & (break_dir != 0)
print("day | or_vol | baseline | RVOL | break | valid | move_R")
for i in range(12):
    print(f"{i+1:>3} | {or_vol[i]:>6.0f} | {baseline[i]:>8.0f} | {rvol[i]:.2f} | "
          f"{break_dir[i]:+.0f} | {str(bool(valid[i])):>5} | {move_R[i]:+.1f}")
n_valid = valid.sum()
n_winners = (move_R[valid] > 0).sum()
print(f"valid trades {n_valid}, winners {n_winners}, mean move {move_R[valid].mean():+.2f} R")

x = np.arange(1, 13)
fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, gridspec_kw={"hspace": 0.08})
# top: OR-window volume vs baseline
ax1.bar(x, or_vol, color=PALETTE["volume"], alpha=0.85, label="OR-window vol (k shares)")
ax1.plot(x, baseline, color=PALETTE["price"], marker="o", ms=4, lw=1.5,
         label="14-day mean OR vol (baseline)")
ax1.set_ylabel("shares (000s)")
ax1.set_title("S032 — RVOL-filtered breakout: 12-day synthetic tape (seed 32)")
ax1.legend(loc="upper left")
for i in np.where(valid)[0]:
    ax1.annotate("valid", xy=(i + 1, or_vol[i]), xytext=(0, 8), textcoords="offset points",
                 ha="center", fontsize=8, weight="bold", color=PALETTE["signal"])
# bottom: RVOL with example threshold
colors = [PALETTE["signal"] if v else PALETTE["volume"] for v in valid]
ax2.bar(x, rvol, color=colors, alpha=0.9, label="RVOL = OR vol / baseline")
ax2.axhline(THR, color=PALETTE["zero"], ls="--", lw=1.5,
            label=f"example threshold RVOL ≥ {THR}")
ax2.axhline(1.0, color=PALETTE["band"], ls=":", lw=1.2)
for i in np.where(valid)[0]:
    col = PALETTE["profit"] if move_R[i] > 0 else PALETTE["loss"]
    ax2.annotate(f"{move_R[i]:+.1f}R", xy=(i + 1, rvol[i]), xytext=(0, 9),
                 textcoords="offset points", ha="center", fontsize=8, weight="bold", color=col)
ax2.set_xlabel("synthetic trading day")
ax2.set_ylabel("RVOL (×)")
ax2.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S032_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
