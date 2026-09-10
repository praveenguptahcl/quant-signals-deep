import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
import os

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

rng = np.random.default_rng(190)  # T090 seed — stated in chapter text

# ---- T090 worked-example inputs (SYNTHETIC) ----
# 5-name carry book, sleeve NAV $1M, vol-target 10% (example).
# Gates (example): Lee-Mykland jump stat < 6.63 (no jump at 1%); borrow fee < 2% ann.;
# VIX term slope > 0 (contango); carry only if ALL pass.
names = ["AAA", "BBB", "CCC", "DDD", "EEE"]
jump = np.array([2.1, 9.4, 1.3, 0.9, 3.2])       # Lee-Mykland stat
borrow = np.array([0.8, 0.5, 12.5, 0.4, 1.1])    # % annualized
vix_slope = np.array([2.1, 2.1, 2.1, 2.1, -1.5])  # VIX term slope (pts)
w = np.array([0.04, 0.0, 0.0, 0.03, 0.0])         # carry weights (example sizing)
NAV = 1_000_000
notional = w * NAV
gap = np.array([0.006, 0.0, 0.0, -0.003, 0.0])    # synthetic overnight gap returns
pnl_gap = notional * gap
borrow_cost = notional * (borrow / 100) / 365
pnl = pnl_gap - borrow_cost
print("name | jump | borrow% | VIXslope | carry? | notional | gap% | gap$ | borrow$ | net$")
for i, n_ in enumerate(names):
    carry = "YES" if w[i] > 0 else "no"
    print(f"{n_:4s} | {jump[i]:4.1f} | {borrow[i]:6.1f} | {vix_slope[i]:+6.1f} | {carry:4s} | "
          f"${notional[i]:7,.0f} | {gap[i]*100:+5.1f} | ${pnl_gap[i]:+7.2f} | ${borrow_cost[i]:5.2f} | ${pnl[i]:+7.2f}")
net = pnl.sum()
print(f"sleeve net = ${net:.2f} (synthetic)")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), gridspec_kw={"height_ratios": [2, 3]})
fig.suptitle("T090 — Overnight Inventory Carry Manager: synthetic 5-name carry book (seed 190)",
             fontweight="bold")
x = np.arange(len(names))
cols_j = [PALETTE["signal"] if j >= 6.63 else PALETTE["profit"] for j in jump]
ax1.bar(x - 0.2, jump, 0.4, color=cols_j, label="Lee-Mykland jump stat")
ax1.axhline(6.63, color=PALETTE["zero"], ls="--", lw=1.2, label="jump gate 6.63 (example)")
cols_b = [PALETTE["signal"] if b >= 2.0 else PALETTE["profit"] for b in borrow]
ax1b = ax1.twinx()
ax1b.bar(x + 0.2, borrow, 0.4, color=cols_b, alpha=0.55, label="borrow fee %")
ax1b.axhline(2.0, color=PALETTE["zero"], ls=":", lw=1.2)
ax1.set_xticks(x); ax1.set_xticklabels(names)
ax1.set_ylabel("jump stat"); ax1b.set_ylabel("borrow fee (% ann.)")
ax1.text(0.02, 0.92, "BBB: jump -> no carry\nCCC: borrow 12.5% -> no carry\nEEE: VIX backwardation -> no carry",
         transform=ax1.transAxes, fontsize=8, va="top", bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax1.legend(loc="upper right", fontsize=8)

# sleeve equity walk: flat -> carry decision -> overnight gaps -> open
steps = ["15:30\nflat", "15:55\ncarry set", "open AAA\n+0.6%", "open DDD\n-0.3%", "net"]
vals = [0, 0, pnl_gap[0], pnl_gap[0] + pnl_gap[3], net]
ax2.step(steps, vals, color=PALETTE["price"], lw=2, where="mid", label="sleeve P&L (synthetic)")
ax2.scatter(steps, vals, color=PALETTE["price"], s=50, zorder=5)
for s_, v in zip(steps, vals):
    ax2.text(s_, v + 8, f"${v:+.0f}", ha="center", fontsize=9, fontweight="bold")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.set_ylabel("cumulative P&L ($)")
ax2.set_title(f"carry AAA 4% + DDD 3% of $1M -> net ${net:.2f} (synthetic; borrow costs netted)",
              fontsize=11)
ax2.legend(loc="lower left", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T090_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
