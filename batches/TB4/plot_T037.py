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

# ---- T037 synthetic scenario (seed 137 == stage number) ----
# Fictional dual-listed name "QZL": ADR ratio n=2, home shares trade in JPY,
# ADR in USD. Premium Pi_t = P_ADR / (n * P_local / X) - 1, dimensionless.
rng = np.random.default_rng(137)
days = np.arange(90)
prem = np.zeros(90)
prem[0] = 0.002
for t in range(1, 90):
    prem[t] = prem[t - 1] * 0.87 + 0.0002 + rng.normal(0, 0.0018)
prem += 0.028 * np.exp(-((np.arange(90) - 66) / 5) ** 2)  # premium excursion ~day 66

W = 60  # example lookback
z = np.full(90, np.nan)
for t in range(W, 90):
    win = prem[t - W + 1:t + 1]
    z[t] = (prem[t] - win.mean()) / win.std()

Z_ENTRY, Z_EXIT, PI_MIN = 1.5, 0.5, 0.005  # example thresholds
entry_c = np.where((days > W) & (z > Z_ENTRY) & (prem > PI_MIN))[0]
entry = int(entry_c[0])
exit_c = np.where((days > entry) & (np.abs(z) < Z_EXIT))[0]
exitd = int(exit_c[0]) if len(exit_c) else 89

NOTIONAL = 500_000.0
gross = (prem[entry] - prem[exitd]) * NOTIONAL
hold = exitd - entry
borrow = 0.020 * NOTIONAL * hold / 365     # ADR short fee 2.0%/ann (example, S098)
comm = 900.0                                # RT commissions both legs (example)
fx = 0.0005 * NOTIONAL                      # FX spread 5 bp (example)
net = gross - borrow - comm - fx
pnl = (prem[entry] - prem) * NOTIONAL - (borrow * np.clip((days - entry) / max(hold, 1), 0, 1)
                                          + comm + fx)
pnl[exitd:] = net                        # position closed at exit: P&L frozen at realized net

print(f"entry_day={entry} prem_entry={prem[entry]*100:.2f}% z_entry={z[entry]:.2f}")
print(f"exit_day={exitd} prem_exit={prem[exitd]*100:.2f}% z_exit={z[exitd]:.2f} hold={hold}d")
print(f"gross=${gross:,.0f} borrow=${borrow:,.0f} comm=${comm:,.0f} fx=${fx:,.0f} net=${net:,.0f}")
print("day : premium% | z")
for t in range(W, 90):
    print(f"  {t:2d} : {prem[t]*100:6.2f} | {z[t]:6.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True)
ax1.plot(days, prem * 100, color=PALETTE["price"], lw=1.6,
         label="FX-adjusted ADR premium (%)")
ax1.axhline(PI_MIN * 100, color=PALETTE["signal"], ls="--", lw=1,
            label="min premium filter 0.50% (example)")
ax1.axhline(0, color=PALETTE["zero"], lw=0.8)
ax1.fill_between(days, -0.5, 0.5, color=PALETTE["band"], alpha=0.35,
                 label="cost band (no-trade)")
ax1.scatter([entry], [prem[entry] * 100], color=PALETTE["profit"], s=80, zorder=5,
            label=f"ENTRY day {entry} (Pi={prem[entry]*100:.2f}%, z={z[entry]:.2f})")
ax1.scatter([exitd], [prem[exitd] * 100], color=PALETTE["loss"], s=80, zorder=5,
            label=f"EXIT day {exitd} (Pi={prem[exitd]*100:.2f}%, z={z[exitd]:.2f})")
ax1.set_ylabel("premium (%)")
ax1.legend(loc="upper left", ncol=2)
ax1.set_title("T037 — ADR / Dual-Listed Premium Convergence: synthetic 90-day premium path")

ax2.plot(days, pnl, color=PALETTE["profit"], lw=1.6, label="mark-to-market P&L vs entry ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.scatter([exitd], [pnl[exitd]], color=PALETTE["loss"], s=80, zorder=5)
ax2.annotate(f"net = ${net:,.0f}", xy=(exitd, pnl[exitd]), xytext=(exitd - 26, pnl[exitd] + 1800),
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
plt.savefig("images/T037_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
