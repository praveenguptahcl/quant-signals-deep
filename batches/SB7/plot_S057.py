"""S057 plot: cash-and-carry basis decomposition waterfall.

CORRECTED 2026-09-10: the previous version double-counted carry (it took the
OVER-FAIR excess 4.00% as gross, then subtracted financing 3.20% a second time,
printing a 0.10% net). This version starts from the RAW (F-S) basis and charges
financing and dividends exactly once, per the rebuilt S4 waterfall. Every number
is computed from the synthetic inputs below; the friction rows are stated
`example` assumptions, labeled as such.
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

# ---- SYNTHETIC INPUTS (identical to the chapter's S4) ----
S = 5000.0            # index spot
T_days = 90
r = 0.05              # financing rate
q = 0.018             # dividend yield
F_star = S * np.exp((r - q) * T_days / 365.0)   # fair value -> 5039.61
F = 5088.92           # synthetic observed future
ANN = 365.0 / T_days  # annualization factor = 4.0556

# ---- COMPUTED WATERFALL (annualized %) ----
raw_basis = (F - S) / S * ANN            # 7.21%
financing = -r * 100.0                   # -5.00% (charged once)
dividends = +q * 100.0                   # +1.80% (collected once)
exec_costs = -0.40                       # spreads + commissions/fees (example)
impact = -0.30                           # market impact / slippage (example)
leakage = -0.30                          # ops / dividend-forecast leakage (example)

steps = [
    ("Raw gross basis\n(F - S), annualized", raw_basis, True),
    ("Financing the basket\n(r = 5.0%)", financing, False),
    ("Dividend income\ncollected (q = 1.8%)", dividends, False),
    ("Spreads + commissions\n/fees (example)", exec_costs, False),
    ("Market impact /\nslippage (example)", impact, False),
    ("Ops / dividend\nleakage (example)", leakage, False),
    ("Net\n(annualized)", 0.0, True),  # total bar
]
net = raw_basis + financing + dividends + exec_costs + impact + leakage
print(f"F* = {F_star:.2f}; raw basis = {raw_basis:.2f}%; "
      f"net = {net:.2f}% (check: 7.21-5.00+1.80-0.40-0.30-0.30 = 3.01)")

values = np.array([s[1] for s in steps])
labels = [s[0] for s in steps]
is_total = np.array([s[2] for s in steps])

fig, ax = plt.subplots()
ax.set_title("S057 — Cash-and-carry: basis decomposition waterfall (synthetic, annualized)")

pos = np.arange(len(steps))
cum = 0.0
for i, (lab, val, total) in enumerate(steps):
    if total and i == 0:
        bottom, height, color = 0, val, PALETTE["price"]
        cum = val
    elif total:
        bottom, height, color = 0, cum, PALETTE["profit"] if cum >= 0 else PALETTE["loss"]
    else:
        if val < 0:
            bottom, height, color = cum + val, -val, PALETTE["loss"]
        else:
            bottom, height, color = cum, val, PALETTE["profit"]
        cum += val
    ax.bar(pos[i], height, bottom=bottom, width=0.62, color=color, edgecolor="white")
    if not total:
        ax.text(pos[i], bottom + height / 2, f"{val:+.1f}%", ha="center", va="center",
                fontsize=10, color="white", weight="bold")
    else:
        ax.text(pos[i], height + (0.15 if height >= 0 else -0.15), f"{cum:+.2f}%",
                ha="center", va="bottom" if height >= 0 else "top",
                fontsize=11, weight="bold", color=PALETTE["zero"])
    # connector
    if i < len(steps) - 1 and not total:
        nxt = cum
        ax.plot([pos[i] + 0.31, pos[i + 1] - 0.31], [nxt, nxt], color=PALETTE["zero"],
                linestyle=":", linewidth=1)

ax.axhline(0, color=PALETTE["zero"], linewidth=1)
ax.set_xticks(pos)
ax.set_xticklabels(labels, fontsize=8)
ax.set_xlim(-0.7, len(steps) - 0.3)
ax.set_ylabel("annualized return (%)")
ax.text(0.98, 0.96,
        f"S = 5000, T = 90d, F* = {F_star:.2f}, F observed = {F:.2f}\n"
        f"raw basis = (F - S)/S x 365/90 = {raw_basis:.2f}%\n"
        f"{raw_basis:.2f} - 5.00 + 1.80 - 0.40 - 0.30 - 0.30 = {net:+.2f}% net",
        transform=ax.transAxes, fontsize=8, va="top", ha="right",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.9))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S057_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
