"""T033 worked-example chart. Synthetic 15-day 3-leg basket (seed 133).

Formation is stipulated (not shown): Johansen rank = 1, beta-hat = [1, -0.7,
-0.4], formation EC-spread sigma = 0.84 (computed on 60 seeded formation
days). A hand-shaped liquidity dislocation is superimposed on trading days
3-8 so the demo contains one full trade (disclosed in the chapter). Entry at
|e| >= 2 sigma with the S080 idiosyncratic veto passed (stipulated
max leg |s| = 1.2 < 2.0, example gate); exit at zero-cross; time stop at
2x the stipulated OU half-life (4 days -> 8 days). The script scans for
entries/exits and prints the exact table used in the chapter.
"""
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

rng = np.random.default_rng(133)
BETA = np.array([1.0, -0.7, -0.4])   # stipulated cointegrating vector (example)
GROSS_TARGET = 150_000.0             # basket gross exposure, USD (example)
COST_RT = 0.0005                     # 5 bp one-way per leg (example)
BORROW = 0.0050                      # 50 bp annualized on short legs (example)
HL = 4.0                             # stipulated OU half-life, days (example)
MAX_HOLD = int(2 * HL)               # time stop in days (example)

# 60 formation days + 15 trading days, one true cointegrating relation
n = 75
A = np.cumsum(rng.normal(0, 1, n))
B = np.cumsum(rng.normal(0, 1, n))
X1 = 100 + 0.7 * A + 0.4 * B + rng.normal(0, 0.6, n)
X2 = 50 + 1.0 * A + rng.normal(0, 0.8, n)
X3 = 30 + 1.0 * B + rng.normal(0, 0.5, n)

e = X1 + BETA[1] * X2 + BETA[2] * X3
form_mean = e[:60].mean()
form_sd = e[:60].std(ddof=1)
et = e[60:] - form_mean          # centered EC spread, trading window
sigma = form_sd
print(f"formation: mean={form_mean:.4f} sigma={sigma:.4f}  entry band=±{2*sigma:.4f}")

# disclosed hand-shaped dislocation on days 3-8 (liquidity shock episode)
hump = np.array([0.0, 0.0, 0.6, 1.4, 2.1, 2.4, 1.9, 1.2, 0.4, -0.2,
                 -0.4, -0.2, 0.0, 0.1, -0.1]) * sigma
et = et + hump
days = np.arange(1, 16)
z = et / sigma

# leg prices, trading window
P1, P2, P3 = X1[60:], X2[60:], X3[60:]

# ---- trade scan: beta-neutral basket, S080 veto stipulated as passed ----
pos = 0            # 0 flat, -1 short basket, +1 long basket
entry_day = None
trades, rows = [], []
for t in range(15):
    action = "—"
    if pos == 0 and z[t] >= 2.0:
        pos, action = -1, "OPEN short basket (sell X1, buy .7X2+.4X3)"
        entry_day, entry_P = days[t], (P1[t], P2[t], P3[t])
        unit_val = abs(P1[t]) + 0.7 * abs(P2[t]) + 0.4 * abs(P3[t])
        k = GROSS_TARGET / unit_val
    elif pos == 0 and z[t] <= -2.0:
        pos, action = 1, "OPEN long basket (buy X1, sell .7X2+.4X3)"
        entry_day, entry_P = days[t], (P1[t], P2[t], P3[t])
        unit_val = abs(P1[t]) + 0.7 * abs(P2[t]) + 0.4 * abs(P3[t])
        k = GROSS_TARGET / unit_val
    elif pos != 0:
        crossed = (t > 0 and np.sign(et[t]) != np.sign(et[t - 1]) and et[t - 1] != 0)
        aged = (days[t] - entry_day) >= MAX_HOLD
        stop = abs(z[t]) > 4.0
        if crossed or aged or stop:
            why = "CLOSE (zero-cross)" if crossed else ("CLOSE (time stop)" if aged else "CLOSE (stop)")
            action = why
            # per-leg P&L: short basket = -k*(dP1) + k*0.7*(dP2) + k*0.4*(dP3)
            dP1, dP2, dP3 = P1[t] - entry_P[0], P2[t] - entry_P[1], P3[t] - entry_P[2]
            if pos == -1:
                leg_pnl = (-k * dP1, k * 0.7 * dP2, k * 0.4 * dP3)
                short_legs = [k * entry_P[0]]
            else:
                leg_pnl = (k * dP1, -k * 0.7 * dP2, -k * 0.4 * dP3)
                short_legs = [k * 0.7 * entry_P[1], k * 0.4 * entry_P[2]]
            gross = sum(leg_pnl)
            leg_not = (k * entry_P[0], k * 0.7 * entry_P[1], k * 0.4 * entry_P[2])
            cost = 2 * COST_RT * sum(abs(x) for x in leg_not)   # 2 turns x 5bp x 3 legs
            dh = int(days[t] - entry_day)
            borrow = sum(short_legs) * BORROW * dh / 365.0
            net = gross - cost - borrow
            trades.append(dict(entry_day=int(entry_day), exit_day=int(days[t]), days=dh,
                               side="short-basket" if pos == -1 else "long-basket",
                               entry_z=z[entry_day - 1], exit_z=z[t],
                               leg_pnl=leg_pnl, gross=gross, cost=cost,
                               borrow=borrow, net=net))
            pos = 0
        else:
            action = "hold"
    rows.append((days[t], P1[t], P2[t], P3[t], et[t], z[t], action, pos))

print("day | X1 | X2 | X3 | e_t | z | action | pos")
for d, a, b, c, ee, zz, act, q in rows:
    print(f"{int(d):3d} | {a:.2f} | {b:.2f} | {c:.2f} | {ee:+.3f} | {zz:+.2f} | {act} | {q:+d}")
print("\nTRADES:")
tot = 0.0
for tr in trades:
    tot += tr["net"]
    print(f"{tr['side']}: entry d{tr['entry_day']} z={tr['entry_z']:+.2f} -> "
          f"exit d{tr['exit_day']} z={tr['exit_z']:+.2f} ({tr['days']}d)")
    print(f"  leg P&L: X1=${tr['leg_pnl'][0]:,.0f} X2=${tr['leg_pnl'][1]:,.0f} "
          f"X3=${tr['leg_pnl'][2]:,.0f}")
    print(f"  gross=${tr['gross']:,.0f}  costs=${tr['cost']:,.0f}  "
          f"borrow=${tr['borrow']:,.2f}  NET=${tr['net']:,.0f}")
print(f"TOTAL NET = ${tot:,.0f}")

# ---- chart ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
ax1.plot(days, z, color=PALETTE["price"], lw=2, label="EC spread z (synthetic)")
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
ax1.set_ylabel("z (σ units)")
ax1.legend(loc="upper right")
ax1.set_title("T033 — Johansen VECM Basket Arb: synthetic 3-leg error-correction path")

cum = np.zeros(15)
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
plt.savefig("images/T033_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T033_example.png")
