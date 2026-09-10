"""T018 worked-example chart. Run: python3 batches/TB2/plot_T018.py  (cwd: quant-signals-deep)"""
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

rng = np.random.default_rng(118)

# ---- Synthetic tape matching the T4 worked example ----
PRIOR_CLOSE = 120.00
ATR20 = 3.00
OPEN = 126.60                       # gap = +2.2 x ATR20
F5_HIGH, F5_LOW = 127.10, 126.30    # first-5-min range (09:30-09:35)
ENTRY_T, EXIT_T = 15, 65            # bar indices: entry 09:45, exit 10:35
ENTRY_PX, EXIT_PX = 127.40, 130.40  # entry = t+1 open; exit = +1.0xATR target
SHARES = 1000

n = 211  # 09:30 -> 13:00, 1-min bars
close = np.zeros(n)
close[0] = OPEN
# bars 1..4: inside first-5-min range
close[1:5] = [126.80, 127.05, 126.55, 126.90]
close[5:10] = [126.95, 126.75, 127.00, 127.20, 127.05]   # hold: lows > 120
close[10] = 127.35                                        # trigger bar close > 127.10
drift = np.linspace(close[10], ENTRY_PX - 0.06, ENTRY_T - 11)
close[11:ENTRY_T] = drift + rng.normal(0, 0.06, ENTRY_T - 11)
close[ENTRY_T] = ENTRY_PX
drift2 = np.linspace(ENTRY_PX, EXIT_PX - 0.05, EXIT_T - ENTRY_T - 1)
close[ENTRY_T + 1:EXIT_T] = drift2 + rng.normal(0, 0.10, EXIT_T - ENTRY_T - 1)
close[EXIT_T] = EXIT_PX                                   # target touched first here
drift3 = np.linspace(EXIT_PX - 0.30, EXIT_PX - 0.55, n - EXIT_T - 1)
close[EXIT_T + 1:] = drift3 + rng.normal(0, 0.08, n - EXIT_T - 1)
# keep the target from being touched before the exit bar
close[ENTRY_T:EXIT_T] = np.minimum(close[ENTRY_T:EXIT_T], EXIT_PX - 0.01)

hi = close + np.abs(rng.normal(0, 0.10, n))
lo = close - np.abs(rng.normal(0, 0.10, n))
hi[0:5] = np.maximum(hi[0:5], F5_HIGH)
lo[0:5] = np.minimum(lo[0:5], F5_LOW)

times = [f"{9 + (30 + i) // 60}:{(30 + i) % 60:02d}" for i in range(n)]
xt = [0, 30, 60, 90, 120, 150, 180, 210]
xl = [times[i] for i in xt]

fig, ax = plt.subplots()
ax.plot(range(n), close, color=PALETTE["price"], lw=1.6, label="1-min close (synthetic)")
ax.axhspan(F5_LOW, F5_HIGH, color=PALETTE["band"], alpha=0.45,
           label="First-5-min range $126.30–$127.10")
ax.axhline(PRIOR_CLOSE, color=PALETTE["zero"], ls=":", lw=1.2, label="Prior close $120.00")
ax.axhline(EXIT_PX, color=PALETTE["profit"], ls="--", lw=1.2, label="Target +1.0xATR $130.40")
ax.axhline(F5_LOW, color=PALETTE["loss"], ls="--", lw=1.2, label="Stop (first-5-min low)")
ax.plot(ENTRY_T, ENTRY_PX, marker="^", ms=11, color=PALETTE["profit"],
        label="Entry", zorder=5)
ax.plot(EXIT_T, EXIT_PX, marker="v", ms=11, color=PALETTE["loss"],
        label="Exit", zorder=5)
ax.annotate("ENTRY 09:45\n$127.40 x 1000 sh", (ENTRY_T, ENTRY_PX),
            xytext=(40, 124.6), fontsize=9, color=PALETTE["profit"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]))
ax.annotate("EXIT 10:35\n$130.40 -> net +$2,939", (EXIT_T, EXIT_PX),
            xytext=(100, 128.6), fontsize=9, color=PALETTE["loss"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["loss"]))
ax.set_xlim(0, n - 1)
ax.set_xticks(xt); ax.set_xticklabels(xl)
ax.set_xlabel("Time (ET)")
ax.set_ylabel("Price ($)")
ax.set_title("T018 — RVOL-Gated Gap-and-Go: synthetic gap-day trade timeline (1-min bars)")
ax.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T018_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T018_example.png | seed 118 | entry", ENTRY_PX, "| exit", EXIT_PX)
