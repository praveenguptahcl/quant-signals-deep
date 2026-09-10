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

# ---- T034 synthetic scenario (seed 134 == stage number) ----
rng = np.random.default_rng(134)
days = np.arange(90)
m = np.zeros(90)  # mispricing m_t = F_mkt - F_fair, index points
m[0] = 16.2
for t in range(1, 90):
    m[t] = m[t - 1] * 0.96 + rng.normal(0, 0.85)
m[30:38] -= 9.0  # cheap swing: reverse signal appears, vetoed by borrow fee

ENTRY_BOUND = 12.0   # example: enter cash-and-carry if m_t > +12 pts
EXIT_FRAC = 0.25     # example: unwind when m back within 25% of entry level
entry = int(np.where((days >= 5) & (m > ENTRY_BOUND))[0][0])
exit_c = np.where((days > entry) & (m < EXIT_FRAC * m[entry]))[0]
exitd = int(exit_c[0]) if len(exit_c) else 89
m_entry, m_exit = m[entry], m[exitd]

CONTRACTS, MULT = 20, 50.0
gross = (m_entry - m_exit) * MULT * CONTRACTS
cost_cash = 2000.0    # 4 bp round-trip on $5mm ETF leg
cost_fut = 1000.0     # $50/contract round-trip x 20
net = gross - cost_cash - cost_fut
pnl = (m_entry - m) * MULT * CONTRACTS  # mark-to-market vs entry level
pnl[exitd:] = gross                      # position closed at exit: P&L frozen at realized gross

# veto arithmetic (reverse cash-and-carry at the cheap swing)
cheap_day = int(np.argmin(m))
cheap_pts = -m[cheap_day]
borrow_fee = 0.028 * 5_000_000 * (89 - cheap_day) / 365  # 2.8% ann special, example
cheap_gross = cheap_pts * MULT * CONTRACTS

print(f"entry_day={entry} m_entry={m_entry:.2f} exit_day={exitd} m_exit={m_exit:.2f}")
print(f"gross=${gross:,.0f} costs=${cost_cash + cost_fut:,.0f} net=${net:,.0f}")
print(f"cheap_day={cheap_day} cheap_pts={cheap_pts:.2f} cheap_gross=${cheap_gross:,.0f} borrow_drag=${borrow_fee:,.0f} VETO={'YES' if borrow_fee > cheap_gross else 'no'}")
print("day : m_t (first 90 days, index pts)")
for t in range(90):
    print(f"  {t:2d} : {m[t]:7.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True)
ax1.plot(days, m, color=PALETTE["price"], lw=1.6, label="mispricing m = F_mkt - F_fair (index pts)")
ax1.axhline(ENTRY_BOUND, color=PALETTE["signal"], ls="--", lw=1, label="entry bound +12 pts (example)")
ax1.axhline(0, color=PALETTE["zero"], lw=0.8)
ax1.fill_between(days, -8, 8, color=PALETTE["band"], alpha=0.35, label="cost band (no-trade)")
ax1.scatter([entry], [m_entry], color=PALETTE["profit"], s=80, zorder=5,
            label=f"ENTRY day {entry} (m={m_entry:.1f} pts)")
ax1.scatter([exitd], [m_exit], color=PALETTE["loss"], s=80, zorder=5,
            label=f"EXIT day {exitd} (m={m_exit:.1f} pts)")
ax1.scatter([cheap_day], [m[cheap_day]], color=PALETTE["signal2"], s=80, marker="x", zorder=5,
            label=f"reverse signal day {cheap_day} — VETOED (borrow)")
ax1.set_ylabel("index points")
ax1.legend(loc="upper right")
ax1.set_title("T034 — Index Futures Cash-and-Carry: synthetic 90-day mispricing path")

ax2.plot(days, pnl, color=PALETTE["profit"], lw=1.6, label="mark-to-market P&L vs entry ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.scatter([entry], [0], color=PALETTE["profit"], s=80, zorder=5)
ax2.scatter([exitd], [(m_entry - m_exit) * MULT * CONTRACTS], color=PALETTE["loss"], s=80, zorder=5)
ax2.annotate(f"exit gross ${gross:,.0f} → net ${net:,.0f} after costs", xy=(exitd, pnl[exitd]), xytext=(exitd - 30, pnl[exitd] + 1500),
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
plt.savefig("images/T034_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
