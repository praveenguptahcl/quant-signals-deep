"""T019 worked-example chart. Run: python3 batches/TB2/plot_T019.py  (cwd: quant-signals-deep)"""
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

rng = np.random.default_rng(119)
n = 60  # 5-min bars, 09:35 -> 14:35
O = np.zeros(n); H = np.zeros(n); L = np.zeros(n); C = np.zeros(n)

# baseline chop 09:35-11:00 (ranges ~$0.75 so ATR20 lands near $0.85)
C[0:20] = 200.20 + np.cumsum(rng.normal(0, 0.30, 20))
C[0:20] = np.clip(C[0:20], 199.00, 200.80)
# trade 1: squeeze-armed upside breakout, trigger bar 20
C[20] = 202.60
C[21:27] = [202.95, 203.40, 203.85, 204.10, 204.20, 204.30]
# fade back down
C[27:40] = [203.90, 203.55, 203.10, 202.75, 202.40, 202.10, 201.75,
            201.45, 201.10, 200.80, 200.55, 200.30, 200.00]
# trade 2: expansion-only downside breakout (short), trigger bar 40
C[40] = 199.10
C[41:47] = [199.05, 198.95, 198.85, 198.95, 198.75, 198.60]
C[47:60] = 198.90 + np.cumsum(rng.normal(0, 0.15, 13))
C[47:60] = np.clip(C[47:60], 198.40, 199.60)

O[0] = 200.15
O[1:] = C[:-1] + rng.normal(0, 0.08, n - 1)
O[21] = 202.70   # t+1 open: momentum gap-up on the breakout
O[41] = 199.05   # t+1 open for the short
H = np.maximum(O, C) + np.abs(rng.normal(0, 0.30, n))
L = np.minimum(O, C) - np.abs(rng.normal(0, 0.30, n))
H[0:20] = np.minimum(H[0:20], 201.10)   # keep the breakout real vs the rail
L[27:40] = np.maximum(L[27:40], 199.55)  # keep the short trigger real vs the rail
# pin the trigger bars to the worked-example values
O[20], H[20], L[20], C[20] = 200.90, 202.75, 200.80, 202.60
O[40], H[40], L[40], C[40] = 199.30, 199.70, 197.90, 199.10
O[21], C[21] = 202.70, 202.95
O[41], C[41] = 199.05, 199.05
H[21], L[21] = 203.10, 202.65
H[41], L[41] = 199.20, 198.90

# ---- rails ----
N = 20
D_UP = np.full(n, np.nan); D_LO = np.full(n, np.nan)
for t in range(N, n):
    D_UP[t] = H[t - N:t].max()
    D_LO[t] = L[t - N:t].min()
alpha = 2 / (N + 1)
EMA = np.full(n, np.nan); EMA[N - 1] = C[0:N].mean()
for t in range(N, n):
    EMA[t] = alpha * C[t] + (1 - alpha) * EMA[t - 1]
TR = np.full(n, np.nan)
TR[0] = H[0] - L[0]
for t in range(1, n):
    TR[t] = max(H[t] - L[t], abs(H[t] - C[t - 1]), abs(L[t] - C[t - 1]))
ATR = np.full(n, np.nan)
for t in range(N - 1, n):
    ATR[t] = TR[t - N + 1:t + 1].mean()   # simple-average convention (S029)
K_UP = EMA + 1.5 * ATR
K_LO = EMA - 1.5 * ATR
RNG_MEAN = np.full(n, np.nan)
for t in range(10, n):
    RNG_MEAN[t] = (H[t - 10:t] - L[t - 10:t]).mean()
RR20 = (H[20] - L[20]) / RNG_MEAN[20]
RR40 = (H[40] - L[40]) / RNG_MEAN[40]

print(f"bar20: DonU={D_UP[20]:.2f} DonL={D_LO[20]:.2f} KelU={K_UP[20]:.2f} "
      f"KelL={K_LO[20]:.2f} EMA={EMA[20]:.2f} ATR={ATR[20]:.2f} rangeRatio={RR20:.2f}")
print(f"bar40: DonU={D_UP[40]:.2f} DonL={D_LO[40]:.2f} KelU={K_UP[40]:.2f} "
      f"KelL={K_LO[40]:.2f} EMA={EMA[40]:.2f} ATR={ATR[40]:.2f} rangeRatio={RR40:.2f}")

# ---- trades (match T4 table) ----
T1 = dict(side="LONG", shares=750, entry_i=21, entry_px=202.70,
          exit_i=26, exit_px=204.30, net=1176.50)
T2 = dict(side="SHORT", shares=375, entry_i=41, entry_px=199.05,
          exit_i=46, exit_px=198.60, net=156.50)

fig, ax = plt.subplots()
ax.plot(range(n), C, color=PALETTE["price"], lw=1.6, label="5-min close (synthetic)")
ax.plot(range(n), D_UP, color=PALETTE["signal2"], ls="--", lw=1.1, label="Donchian(20) rails")
ax.plot(range(n), D_LO, color=PALETTE["signal2"], ls="--", lw=1.1)
ax.plot(range(n), K_UP, color=PALETTE["volume"], ls=":", lw=1.1, label="Keltner(EMA20, 1.5xATR) rails")
ax.plot(range(n), K_LO, color=PALETTE["volume"], ls=":", lw=1.1)

ax.plot(T1["entry_i"], T1["entry_px"], marker="^", ms=11, color=PALETTE["profit"], zorder=5)
ax.plot(T1["exit_i"], T1["exit_px"], marker="v", ms=11, color=PALETTE["profit"], zorder=5)
ax.annotate("T1 LONG 750 sh\nin $202.70 -> out $204.30\nnet +$1,176.50",
            (T1["entry_i"], T1["entry_px"]), xytext=(2, 201.0), fontsize=9,
            color=PALETTE["profit"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]))
ax.plot(T2["entry_i"], T2["entry_px"], marker="v", ms=11, color=PALETTE["loss"], zorder=5)
ax.plot(T2["exit_i"], T2["exit_px"], marker="^", ms=11, color=PALETTE["loss"], zorder=5)
ax.annotate("T2 SHORT 375 sh\nin $199.05 -> out $198.60\nnet +$156.50",
            (T2["entry_i"], T2["entry_px"]), xytext=(44, 201.2), fontsize=9,
            color=PALETTE["loss"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["loss"]))

times = [f"{9 + (35 + 5 * i) // 60}:{(35 + 5 * i) % 60:02d}" for i in range(n)]
xt = [0, 12, 24, 36, 48, 59]
ax.set_xlim(0, n - 1)
ax.set_ylim(197.5, 205.7)
ax.set_xticks(xt); ax.set_xticklabels([times[i] for i in xt])
ax.set_xlabel("Time (ET)")
ax.set_ylabel("Price ($)")
ax.set_title("T019 — Donchian/Keltner Breakout + Vol Sizing: two synthetic breakout trades")
ax.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T019_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T019_example.png | seed 119")
