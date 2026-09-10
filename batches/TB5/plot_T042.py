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

rng = np.random.default_rng(142)

HALF_SPREAD = 0.005
FEE = 0.0035
SHARES = 200
SLIP_BP = 1.0        # 1 bp entry slippage on notional (example; T2 cost model)

# Window A — clean continuous vol spike (fixed synthetic 5-min closes, SYNX, $)
CLOSES_A = np.array([200.00, 200.10, 200.02, 200.16, 200.04, 200.24,
                     199.96, 200.28, 200.10, 200.32, 200.06, 200.22, 200.08])
r = CLOSES_A[1:] / CLOSES_A[:-1] - 1          # 12 log-ish returns (simple returns fine at this scale)
rv_sum = np.sum(r ** 2)
bv_sum = (np.pi / 2) * np.sum(np.abs(r[:-1]) * np.abs(r[1:]))
J = max(rv_sum - bv_sum, 0.0)
RJ = J / rv_sum if rv_sum > 0 else 0.0
print(f"Window A: RV={rv_sum:.3e} BV={bv_sum:.3e} J={J:.3e} RJ={RJ:.1%}")

# Window B — jump day (fixed synthetic returns x1e-4, +90bp jump at bar 7)
rB = np.array([3., -2., 4., -3., 5., -4., 90., -6., 4., -5., 3., -4.]) * 1e-4
rvB = np.sum(rB ** 2)
bvB = (np.pi / 2) * np.sum(np.abs(rB[:-1]) * np.abs(rB[1:]))
JB = max(rvB - bvB, 0.0)
RJB = JB / rvB
print(f"Window B: RV={rvB:.3e} BV={bvB:.3e} J={JB:.3e} RJ={RJB:.1%}")

# Trade on Window A: expansion bar 7 closed up -> LONG at bar-8 open (= close of bar 7)
entry_px = float(CLOSES_A[7])    # 200.28
exit_px = float(CLOSES_A[11])    # bar-12 open = 200.22 (4-bar time stop)
gross = (exit_px - entry_px) * SHARES
slip = SLIP_BP / 10000.0 * SHARES * entry_px   # 1 bp x $40,056 entry notional = $4.01
costs = 2 * SHARES * (HALF_SPREAD + FEE) + slip
net = gross - costs
print(f"Trade A: long {SHARES} @ {entry_px:.2f} -> {exit_px:.2f} | "
      f"gross {gross:+.2f} | spread+fees {2*SHARES*(HALF_SPREAD+FEE):.2f} | "
      f"entry slippage {slip:.2f} | net {net:+.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
bars = np.arange(len(CLOSES_A))

# top: trade timeline
ax1.plot(bars, CLOSES_A, color=PALETTE["price"], lw=1.8, marker="o", ms=4,
         label="SYNX 5-min closes (synthetic, $)")
ax1.scatter([7], [CLOSES_A[7]], s=130, marker="^", color=PALETTE["profit"],
            zorder=5, edgecolors="black", linewidths=0.8, label="Long entry bar 7")
ax1.scatter([11], [CLOSES_A[11]], s=130, marker="v", color=PALETTE["loss"],
            zorder=5, edgecolors="black", linewidths=0.8, label="Exit bar 11 (time stop)")
ax1.axvspan(6.5, 7.5, color=PALETTE["signal2"], alpha=0.10)
ax1.text(7, 200.36, "expansion bar\n(range ratio 2.83)", fontsize=8,
         ha="center", color=PALETTE["signal2"])
ax1.annotate(f"Long 200 sh @ {entry_px:.2f}\n-> {exit_px:.2f} · net {net:+.2f}$",
             xy=(11, CLOSES_A[11]), fontsize=9,
             xytext=(30, 26), textcoords="offset points",
             arrowprops=dict(arrowstyle="-", color="#2c3e50", lw=0.8),
             bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.9))
ax1.set_ylabel("Price ($)")
ax1.legend(loc="lower right", fontsize=8)

# bottom: RV vs BV decomposition per interval (x1e-6), both windows summarized
x = np.arange(12)
rv_terms = r ** 2 * 1e6
bv_terms = np.abs(r[:-1]) * np.abs(r[1:]) * 1e6   # raw |r_{i-1} r_i|; pi/2 applies to the aggregate
w = 0.38
ax2.bar(x - w / 2, rv_terms, width=w, color=PALETTE["signal"], alpha=0.75, label="RV summand r^2")
ax2.bar(x[1:] + w / 2, bv_terms, width=w, color=PALETTE["band"],
        edgecolor=PALETTE["price"], label="BV summand |r_i-1||r_i| (raw; x pi/2 in aggregate)")
ax2.text(11, max(rv_terms.max(), bv_terms.max()) * 0.92,
         f"Window A: RV={rv_sum*1e6:.2f}e-6  BV={bv_sum*1e6:.2f}e-6\n"
         f"J=0, RJ=0% -> TRADE\n"
         f"Window B: RV={rvB*1e6:.2f}e-6  BV={bvB*1e6:.2f}e-6\n"
         f"J={JB*1e6:.2f}e-6, RJ={RJB:.1%} > 50% -> VETO",
         fontsize=8, ha="right", va="top",
         bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.9))
ax2.set_xlabel("5-min interval")
ax2.set_ylabel("Variance summand (x1e-6)")
ax2.legend(loc="upper left", fontsize=8)

fig.suptitle("T042 — Jump-Robust Vol Spike Trader: synthetic jump-filtered vol-spike tape",
             fontsize=13, fontweight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T042_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T042_example.png")
