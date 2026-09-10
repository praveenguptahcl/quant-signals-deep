"""T032 worked-example chart. Synthetic 12-day copula conditional-probability
path (seed 132).

Formation is stipulated (not shown): Student-t copula selected by rolling
out-of-sample likelihood, rho-hat = 0.8, purged-CV (S088) validation passed.
The demo uses the S054 Gaussian closed form with the conditioning leg neutral
(z2 = 0), so p(A|B) = Phi(z1/0.6); entry at p >= 0.95 / <= 0.05 (example),
exit when p crosses 0.5, max hold 5 days = 2x the stipulated OU half-life
(2.5 days, S051). The script scans for entries/exits and prints the exact
table used in the chapter.
"""
import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
from math import erf, sqrt

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

rng = np.random.default_rng(132)
RHO = 0.8                 # stipulated copula dependence (example)
P_U, P_L = 0.95, 0.05     # entry thresholds (example)
NOTIONAL = 100_000.0      # per leg, USD (example)
SPREAD_SD_USD = 400.0     # 1 sigma of spread = 40 bp of leg notional (example)
COST_RT = 0.0005          # 5 bp one-way per leg (example)
BORROW = 0.0050           # 50 bp annualized on short leg (example)
MAX_HOLD = 5              # days = 2x stipulated OU half-life 2.5d (example)

Phi = np.vectorize(lambda x: 0.5 * (1.0 + erf(x / sqrt(2.0))))

# Hand-shaped conditional-quantile path + seeded noise (disclosed in chapter)
base = np.array([0.20, 1.20, 2.60, 1.80, 0.60, -0.40,
                 -2.90, -1.70, -0.50, 0.60, 1.30, 0.30])
z1 = base + rng.normal(0.0, 0.10, 12)
p = Phi(z1 / sqrt(1 - RHO ** 2))   # = Phi(z1/0.6) with conditioning leg neutral
days = np.arange(1, 13)

# ---- trade scan ----
pos = 0            # 0 flat, +1 long-spread (long A/short B), -1 short-spread
entry_day = entry_z = entry_pv = None
trades, rows = [], []
for t in range(12):
    action = "—"
    if pos == 0 and p[t] >= P_U:
        pos, action = -1, "OPEN short-spread (short A / long B)"
        entry_day, entry_z, entry_pv = days[t], z1[t], p[t]
    elif pos == 0 and p[t] <= P_L:
        pos, action = 1, "OPEN long-spread (long A / short B)"
        entry_day, entry_z, entry_pv = days[t], z1[t], p[t]
    elif pos != 0:
        crossed = (t > 0 and (p[t] - 0.5) * (p[t - 1] - 0.5) < 0) or abs(p[t] - 0.5) < 0.02
        aged = (days[t] - entry_day) >= MAX_HOLD
        if crossed or aged:
            why = "CLOSE (p->0.5)" if crossed else "CLOSE (time stop 2xHL)"
            action = why
            if pos == -1:
                gross = (entry_z - z1[t]) * SPREAD_SD_USD
            else:
                gross = (z1[t] - entry_z) * SPREAD_SD_USD
            dh = int(days[t] - entry_day)
            cost = 4 * COST_RT * NOTIONAL
            borrow = NOTIONAL * BORROW * dh / 365.0
            net = gross - cost - borrow
            trades.append(dict(entry_day=int(entry_day), entry_pv=entry_pv,
                               exit_day=int(days[t]), days=dh,
                               side="short-spread" if pos == -1 else "long-spread",
                               entry_z=entry_z, exit_z=z1[t], exit_pv=p[t],
                               gross=gross, cost=cost, borrow=borrow, net=net))
            pos = 0
        else:
            action = "hold"
    rows.append((days[t], p[t], z1[t], action, pos))

print("day | p(A|B) | z1 | action | pos")
for d, pp, zz, a, q in rows:
    print(f"{int(d):3d} | {pp:.4f} | {zz:+.2f} | {a} | {q:+d}")
print("\nTRADES:")
tot = 0.0
for i, tr in enumerate(trades):
    tot += tr["net"]
    print(f"{tr['side']}: entry d{tr['entry_day']} p={tr['entry_pv']:.4f} z={tr['entry_z']:+.2f} -> "
          f"exit d{tr['exit_day']} p={tr['exit_pv']:.4f} z={tr['exit_z']:+.2f} ({tr['days']}d)")
    print(f"  gross=${tr['gross']:,.0f}  costs=${tr['cost']:,.0f}  "
          f"borrow=${tr['borrow']:,.2f}  NET=${tr['net']:,.0f}")
print(f"TOTAL NET = ${tot:,.0f}")

# ---- chart ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
ax1.plot(days, p, color=PALETTE["price"], lw=2, label="p(A|B) conditional prob (synthetic)")
ax1.axhline(P_U, color=PALETTE["signal"], ls="--", lw=1, label="0.95/0.05 entry (example)")
ax1.axhline(P_L, color=PALETTE["signal"], ls="--", lw=1)
ax1.axhline(0.5, color=PALETTE["zero"], lw=1, label="0.5 exit")
ax1.fill_between(days, P_U, P_L, color=PALETTE["band"], alpha=0.25)
entry_days = [tr["entry_day"] for tr in trades]
exit_days = [tr["exit_day"] for tr in trades]
ax1.scatter(entry_days, [p[d - 1] for d in entry_days], color=PALETTE["signal"],
            marker="v", s=90, zorder=5, label="entry")
ax1.scatter(exit_days, [p[d - 1] for d in exit_days], color=PALETTE["profit"],
            marker="o", s=70, zorder=5, label="exit")
for tr in trades:
    ax1.annotate(f"net ${tr['net']:,.0f}", xy=(tr["exit_day"], p[tr["exit_day"] - 1]),
                 xytext=(6, 12), textcoords="offset points", fontsize=8,
                 color=PALETTE["profit"] if tr["net"] > 0 else PALETTE["loss"],
                 weight="bold")
ax1.set_ylabel("p(A|B)")
ax1.set_ylim(-0.05, 1.05)
ax1.legend(loc="upper right")
ax1.set_title("T032 — Copula Tail-Dependence Pairs: synthetic conditional-probability path")

cum = np.zeros(12)
run = 0.0
for tr in trades:
    run += tr["net"]
    cum[tr["exit_day"] - 1:] = run
ax2.step(days, cum, where="post", color=PALETTE["price"], lw=2,
         label="cumulative net P&L (synthetic)")
ax2.scatter(exit_days, [cum[d - 1] for d in exit_days],
            color=[PALETTE["profit"] if tr["net"] > 0 else PALETTE["loss"] for tr in trades],
            s=60, zorder=5)
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.set_xlabel("trading day")
ax2.set_ylabel("net P&L (USD)")
ax2.set_xticks(days)
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T032_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T032_example.png")
