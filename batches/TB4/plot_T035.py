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

# ---- T035 synthetic scenario (seed 135 == stage number) ----
rng = np.random.default_rng(135)
days = np.arange(60)
sig = np.zeros(60)  # S058 calendar signal = (F2-F1) - (fair2-fair1), index points
sig[0] = 10.5
for t in range(1, 60):
    sig[t] = sig[t - 1] * 0.94 + rng.normal(0, 0.70)
# synthetic HAR forecast path (annualized %), calm regime
har = 13.5 + rng.normal(0, 0.6, 60)
har = np.clip(har, 11, 17)

ENTRY_BOUND = 8.0    # example: fade steepening if signal > +8 pts
EXIT_FRAC = 0.25     # example: exit when signal back within 25% of entry level
TIME_STOP = 50       # example: unwind by day 50 (front expiry day 60)
HAR_CAP = 18.0       # example: enter only if HAR forecast ann vol < 18%
entry_c = np.where((days >= 3) & (sig > ENTRY_BOUND) & (har < HAR_CAP))[0]
entry = int(entry_c[0])
exit_c = np.where((days > entry) & (sig < EXIT_FRAC * sig[entry]))[0]
exitd = int(exit_c[0]) if len(exit_c) and exit_c[0] <= TIME_STOP else TIME_STOP
sig_entry, sig_exit = sig[entry], sig[exitd]

N_SPREADS, MULT = 20, 50.0
gross = (sig_entry - sig_exit) * MULT * N_SPREADS
cost_fut = 2000.0  # $50/contract RT x 40 contracts (2 legs x 20 spreads)
net = gross - cost_fut
pnl = (sig_entry - sig) * MULT * N_SPREADS
pnl[exitd:] = gross                      # position closed at exit: P&L frozen at realized gross

print(f"entry_day={entry} sig_entry={sig_entry:.2f} har_entry={har[entry]:.1f}%")
print(f"exit_day={exitd} sig_exit={sig_exit:.2f}")
print(f"gross=${gross:,.0f} costs=${cost_fut:,.0f} net=${net:,.0f}")
print("day : signal (pts) | HAR ann%")
for t in range(60):
    print(f"  {t:2d} : {sig[t]:7.2f} | {har[t]:5.1f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True)
ax1.plot(days, sig, color=PALETTE["price"], lw=1.6,
         label="calendar signal (F2-F1) - (fair2-fair1) (index pts)")
ax1.axhline(ENTRY_BOUND, color=PALETTE["signal"], ls="--", lw=1,
            label="entry bound +8 pts (example)")
ax1.axhline(0, color=PALETTE["zero"], lw=0.8, label="fair spread")
ax1.fill_between(days, -4, 4, color=PALETTE["band"], alpha=0.35, label="cost band (no-trade)")
ax1.axvline(TIME_STOP, color=PALETTE["volume"], ls=":", lw=1.2,
            label="time stop: 10d before front expiry")
ax1.scatter([entry], [sig_entry], color=PALETTE["profit"], s=80, zorder=5,
            label=f"ENTRY day {entry} (sig={sig_entry:.1f} pts, HAR={har[entry]:.1f}%)")
ax1.scatter([exitd], [sig_exit], color=PALETTE["loss"], s=80, zorder=5,
            label=f"EXIT day {exitd} (sig={sig_exit:.1f} pts)")
ax1.set_ylabel("index points")
ax1.legend(loc="upper right", ncol=2)
ax1.set_title("T035 — Futures Calendar-Spread Carry: synthetic 60-day term-structure signal")

ax2.plot(days, pnl, color=PALETTE["profit"], lw=1.6, label="mark-to-market P&L vs entry ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.scatter([exitd], [pnl[exitd]], color=PALETTE["loss"], s=80, zorder=5)
ax2.annotate(f"exit gross ${gross:,.0f} → net ${net:,.0f} after costs", xy=(exitd, pnl[exitd]), xytext=(exitd - 24, pnl[exitd] - 1200),
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]), fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.9))
ax2.set_ylabel("P&L ($)")
ax2.set_xlabel("day (synthetic)")
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T035_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
