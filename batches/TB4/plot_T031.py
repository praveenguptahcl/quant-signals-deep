"""T031 worked-example chart. Synthetic 20-day spread path (seed 131).

Formation is stipulated (not shown): 9 zero-crossings, sigma_formation = 0.020,
pair accepted by the S053 gate. The trading window below is generated with
rng = np.random.default_rng(131); the script scans for entries/exits and prints
the exact table used in the chapter.
"""
import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
from math import erf

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

rng = np.random.default_rng(131)
SIGMA = 0.020            # formation spread std (stipulated)
NOTIONAL = 100_000.0     # per leg, USD (example)
COST_RT = 0.0005          # 5 bp one-way per leg (example)
BORROW = 0.0050           # 50 bp annualized on short leg (example)

# Hand-shaped two-episode divergence path + seeded noise (disclosed in chapter)
base = np.array([0.00, 0.90, 2.05, 2.40, 1.65, 0.60, -0.20, 0.10, 0.00, -0.30,
                 -1.90, -2.20, -1.40, -0.50, 0.15, 0.10, -0.20, 0.30, -0.10, 0.20])
z = base + rng.normal(0.0, 0.08, 20)
S = z * SIGMA
days = np.arange(1, 21)

# ---- trade scan: |z|>=2 enter (example), zero-cross / |z|>4 / 126d exit ----
pos = 0            # 0 flat, +1 long-spread, -1 short-spread
entry_day = entry_S = None
trades = []
rows = []
for t in range(20):
    action, newpos = "—", pos
    if pos == 0 and z[t] >= 2.0:
        pos, action = -1, "OPEN short-spread (short A / long B)"
        entry_day, entry_S = days[t], S[t]
    elif pos == 0 and z[t] <= -2.0:
        pos, action = 1, "OPEN long-spread (long A / short B)"
        entry_day, entry_S = days[t], S[t]
    elif pos != 0:
        crossed = (t > 0 and np.sign(S[t]) != np.sign(S[t - 1]) and S[t - 1] != 0)
        if crossed or abs(z[t]) > 4.0:
            why = "CLOSE (zero-cross)" if crossed else "CLOSE (stop)"
            action = why
            if pos == -1:
                gross = NOTIONAL * (entry_S - S[t])
            else:
                gross = NOTIONAL * (S[t] - entry_S)
            days_held = int(days[t] - entry_day)
            cost = 4 * COST_RT * NOTIONAL                      # 2 legs x 2 turns x 5bp
            borrow = NOTIONAL * BORROW * days_held / 365.0      # short leg only
            net = gross - cost - borrow
            trades.append(dict(entry_day=int(entry_day), entry_S=entry_S,
                               exit_day=int(days[t]), exit_S=S[t], days=days_held,
                               side="short-spread" if pos == -1 else "long-spread",
                               gross=gross, cost=cost, borrow=borrow, net=net))
            pos = 0
        else:
            action = "hold"
    rows.append((days[t], S[t], z[t], action, pos))

print("day | S_t | z_t | action | position")
for d, s, zz, a, p in rows:
    print(f"{int(d):3d} | {s:+.4f} | {zz:+.2f} | {a} | {p:+d}")
print("\nTRADES:")
tot_net = 0.0
for tr in trades:
    tot_net += tr["net"]
    print(f"{tr['side']}: entry d{tr['entry_day']} S={tr['entry_S']:+.4f} -> "
          f"exit d{tr['exit_day']} S={tr['exit_S']:+.4f} ({tr['days']}d held)")
    print(f"  gross=${tr['gross']:,.0f}  costs=${tr['cost']:,.0f}  "
          f"borrow=${tr['borrow']:,.2f}  NET=${tr['net']:,.0f}")
print(f"TOTAL NET = ${tot_net:,.0f}")

# ---- chart ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
ax1.plot(days, z, color=PALETTE["price"], lw=2, label="spread z-score (synthetic)")
ax1.axhline(2.0, color=PALETTE["signal"], ls="--", lw=1, label="±2σ entry (example)")
ax1.axhline(-2.0, color=PALETTE["signal"], ls="--", lw=1)
ax1.axhline(0.0, color=PALETTE["zero"], lw=1)
ax1.fill_between(days, 2.0, -2.0, color=PALETTE["band"], alpha=0.25)
entry_days = [tr["entry_day"] for tr in trades]
exit_days = [tr["exit_day"] for tr in trades]
ax1.scatter(entry_days, [z[d - 1] for d in entry_days], color=PALETTE["signal"],
            marker="v", s=90, zorder=5, label="entry")
ax1.scatter(exit_days, [z[d - 1] for d in exit_days], color=PALETTE["profit"],
            marker="o", s=70, zorder=5, label="exit (zero-cross)")
for tr in trades:
    ax1.annotate(f"net ${tr['net']:,.0f}", xy=(tr["exit_day"], z[tr["exit_day"] - 1]),
                 xytext=(6, 12), textcoords="offset points", fontsize=8,
                 color=PALETTE["profit"] if tr["net"] > 0 else PALETTE["loss"],
                 weight="bold")
ax1.set_ylabel("z-score (σ units)")
ax1.legend(loc="upper right")
ax1.set_title("T031 — Distance Pairs + Quality Filter: synthetic 20-day spread path")

cum = np.zeros(20)
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
plt.savefig("images/T031_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T031_example.png")
