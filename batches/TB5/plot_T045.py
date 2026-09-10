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

rng = np.random.default_rng(145)  # seed = stage number; stated in chapter T4

# ---- synthetic 11-session VIX futures tape (all numbers synthetic) ----
MULT = 1000.0          # $ per futures point
vix = np.array([16.0, 15.8, 15.9, 15.4, 15.6, 15.1, 14.9, 15.0, 14.7, 14.6, 14.5])
vx1 = np.array([17.50, 17.10, 16.90, 16.40, 16.30, 15.90, 15.60, 15.50, 15.20, 15.00, 14.90])
vx2 = np.array([18.60, 18.20, 17.95, 17.50, 17.30, 17.00, 16.70, 16.50, 16.30, 16.10, 16.00])
har_fcst = np.full(11, 13.0)   # example HAR(1,5,22) vol forecast, vol points

# trailing 60-day slope history (example), drawn with the chapter seed
hist_slope = rng.normal(0.6, 0.3, 60)
mu_s, sd_s = hist_slope.mean(), hist_slope.std()
slope = vx2 - vx1
slope_z = (slope - mu_s) / sd_s
vrp = vix - har_fcst                       # desk shorthand, vol points

Z_ENTRY, VRP_MIN, MAX_HOLD = 1.0, 2.0, 10  # example thresholds
COMM, SLIP_PTS = 2.50, 0.05                # $/side, futures points/side

pos, entry_px, hold = 0, 0.0, 0
cum_gross = 0.0
print("day | VIX | VX1 | VX2 | slope | slope_z | VRP | action | daily_MTM | cum_gross")
print(f"trailing slope history: mean {mu_s:.3f} std {sd_s:.3f}")
for d in range(11):
    action, mtm = "-", 0.0
    if pos == 0 and d == 0 and slope_z[d] >= Z_ENTRY and vrp[d] >= VRP_MIN:
        pos, entry_px, action = -1, vx1[d], f"SHORT 1 VX1 @ {vx1[d]:.2f}"
    elif pos != 0:
        mtm = -pos * (vx1[d] - vx1[d - 1]) * MULT if False else 0.0
        # MTM of a short from prior close
        mtm = (vx1[d - 1] - vx1[d]) * MULT
        cum_gross += mtm
        hold += 1
        if hold >= MAX_HOLD or d == 10:
            action = f"COVER @ {vx1[d]:.2f}"
            pos = 0
    print(f"{d:3d} | {vix[d]:5.1f} | {vx1[d]:5.2f} | {vx2[d]:5.2f} | {slope[d]:5.2f} | "
          f"{slope_z[d]:7.2f} | {vrp[d]:5.1f} | {action:>20s} | {mtm:+9.2f} | {cum_gross:+9.2f}")

gross = (entry_px - vx1[10]) * MULT
cost = 2 * COMM + 2 * SLIP_PTS * MULT
net = gross - cost
print(f"\nentry 17.50 -> exit 14.90 | gross {gross:+.2f} | commission {2*COMM:.2f} | "
      f"slippage {2*SLIP_PTS*MULT:.2f} | NET {net:+.2f}")

# ---- chart: cumulative gross MTM with entry/exit markers ----
days = np.arange(11)
cum_curve = np.zeros(11)
run = 0.0
for d in range(1, 11):
    run += (vx1[d - 1] - vx1[d]) * MULT
    cum_curve[d] = run

fig, ax = plt.subplots()
ax.step(days, cum_curve, where="post", color=PALETTE["price"], lw=2.2, label="Cumulative gross MTM ($)")
ax.scatter([0, 10], [0.0, cum_curve[10]], color=PALETTE["signal"], s=70, zorder=5)
ax.annotate("SHORT 1 VX1 @ 17.50\n(slope z +1.78, VRP +3.0)", xy=(0, 0), xytext=(20, 40),
            textcoords="offset points", fontsize=9, color=PALETTE["signal"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"], lw=1))
ax.annotate(f"COVER @ 14.90\nnet +${net:,.0f}", xy=(10, cum_curve[10]), xytext=(-150, -34),
            textcoords="offset points", fontsize=9, color=PALETTE["profit"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"], lw=1))
ax.axhline(0, color=PALETTE["zero"], lw=1)
ax.set_title("T045 — VIX Term-Structure Carry: cumulative P&L of a synthetic short-VX1 carry trade")
ax.set_xlabel("Session")
ax.set_ylabel("Cumulative P&L ($)")
ax.legend()

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T045_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T045_example.png")
