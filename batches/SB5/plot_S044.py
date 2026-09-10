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

# ---- SYNTHETIC DATA (seed 44) ----
rng = np.random.default_rng(44)
N_BARS, N_LOOK = 24, 14

# designed path: long 18-bar grind up (so %D is well established), then a rollover.
# %K stays pinned high into bar 18, then crosses down through %D while still above 80.
up = np.linspace(100.00, 104.00, 18)
down = np.linspace(103.80, 101.50, 7)[1:]
C = np.concatenate([up, down]) + rng.uniform(-0.02, 0.02, size=N_BARS)
C0 = 99.95
O = np.empty(N_BARS); O[0] = C0; O[1:] = C[:-1]
H = C + 0.15 + rng.uniform(0.0, 0.05, size=N_BARS)
L = C - 0.15 - rng.uniform(0.0, 0.05, size=N_BARS)

pctK = np.full(N_BARS, np.nan)
pctR = np.full(N_BARS, np.nan)
for i in range(N_LOOK - 1, N_BARS):
    Hn = H[i - N_LOOK + 1:i + 1].max()
    Ln = L[i - N_LOOK + 1:i + 1].min()
    pctK[i] = 100.0 * (C[i] - Ln) / (Hn - Ln)
    pctR[i] = -100.0 * (Hn - C[i]) / (Hn - Ln)
pctD = np.full(N_BARS, np.nan)
for i in range(N_LOOK + 1, N_BARS):
    pctD[i] = np.mean(pctK[i - 2:i + 1])

sig = [""] * N_BARS
for i in range(N_LOOK + 2, N_BARS):
    if pctK[i - 1] <= pctD[i - 1] and pctK[i] > pctD[i] and pctK[i] < 20:
        sig[i] = "LONG cross"
    if pctK[i - 1] >= pctD[i - 1] and pctK[i] < pctD[i] and pctK[i] > 80:
        sig[i] = "SHORT cross"

print("bar |     O |     H |     L |     C |   %K |   %D |   %R | signal")
for i in range(8, N_BARS):
    print(f"{i+1:3d} | {O[i]:5.2f} | {H[i]:5.2f} | {L[i]:5.2f} | {C[i]:6.2f} "
          f"| {pctK[i]:5.1f} | {pctD[i]:5.1f} | {pctR[i]:6.1f} | {sig[i]}")

# ---- PLOT ----
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 5.2), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1.6, 1.6]})
x = np.arange(1, N_BARS + 1)
ax1.plot(x, C, color=PALETTE["price"], marker="o", ms=4, label="Close (5-min bars)")
ax1.fill_between(x, L, H, color=PALETTE["band"], alpha=0.5, label="Bar range (L-H)")
ax1.set_ylabel("Price ($)")
ax1.set_title("S044 — Stochastic oscillator & Williams %R: synthetic 24-bar tape (seed 44)")
ax1.legend(loc="upper left")

ax2.plot(x, pctK, color=PALETTE["signal"], lw=1.6, label="%K (14)")
ax2.plot(x, pctD, color=PALETTE["signal2"], lw=1.6, ls="--", label="%D = SMA(%K,3)")
for lv in (80, 20):
    ax2.axhline(lv, color=PALETTE["zero"], ls=":", lw=1)
ax2.set_ylabel("%K / %D")
ax2.set_ylim(-5, 105)
ax2.legend(loc="upper left")

ax3.plot(x, pctR, color=PALETTE["price"], lw=1.6, label="Williams %R (14)")
for lv in (-20, -80):
    ax3.axhline(lv, color=PALETTE["zero"], ls=":", lw=1)
ax3.set_ylabel("Williams %R")
ax3.set_xlabel("Bar number (5-min)")
ax3.legend(loc="upper left")

for i, s in enumerate(sig):
    if s:
        for ax in (ax2, ax3):
            ax.axvline(x[i], color=PALETTE["signal"], ls="-", lw=1.2, alpha=0.7)
        ax1.annotate(s, xy=(x[i], C[i]), xytext=(x[i], C[i] + 0.55),
                     arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
                     fontsize=9, color=PALETTE["signal"], ha="center", weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S044_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
