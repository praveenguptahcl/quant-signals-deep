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

# T051 worked-example data (seed 151). Values here are the T4 table, hardcoded.
# Intra-window basis points are deterministic rng(151) interpolation for display;
# window-close basis values below are the table values.
rng = np.random.default_rng(151)

windows = ["W1", "W2", "W3", "W4", "W5"]
funding_bp = np.array([9.0, 12.0, 7.0, -4.0, 3.0])       # f_8h per window, bp of notional
basis_close = np.array([20.0, 15.0, 12.0, 8.0, 5.0])     # window-close basis, bp (entry 25 bp at W1 open)
# Position 1 (carry, W1 open -> W5 close): per-window funding P&L ($) on $100k notional
p1_funding = np.array([90.0, 120.0, 70.0, -40.0, 30.0])
p1_basis_mtm = np.array([50.0, 50.0, 30.0, 40.0, 30.0])  # basis 25->20->15->12->8->5 bp
p1_costs = 120.0                                        # 4 legs x 2 bp fees + 2 crossed spreads x 2 bp
# Position 2 (thin basis MR, W3 open -> W4 close): funding and basis P&L ($)
p2_funding = np.array([0.0, 0.0, 20.0, -30.0, 0.0])
p2_basis_mtm = np.array([0.0, 0.0, 20.0, 20.0, 0.0])     # basis 10->8->6 bp
p2_costs = 120.0

p1_net_cum = np.cumsum(p1_funding + p1_basis_mtm)
p1_net_cum[-1] -= p1_costs          # costs booked at close
p2_net_cum = np.cumsum(p2_funding + p2_basis_mtm)
p2_net_cum[-1] -= p2_costs
total_net = p1_net_cum[-1] + p2_net_cum[-1]   # +350 - 90 = +260

x = np.arange(len(windows))

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [1, 1.1], "hspace": 0.12})

# Panel 1: funding rate bars + basis line (both in bp)
colors = [PALETTE["profit"] if f >= 0 else PALETTE["loss"] for f in funding_bp]
ax1.bar(x, funding_bp, color=colors, alpha=0.75, label="Funding f_8h (bp of notional)")
# intra-window basis display points: linear interp of window-close values + tiny rng jitter
basis_entry = 25.0
closes = np.concatenate(([basis_entry], basis_close))
bx, by = [], []
for i in range(len(windows)):
    seg = np.linspace(closes[i], closes[i + 1], 5)[:-1]
    seg = seg + rng.normal(0, 0.35, size=seg.shape)
    bx.extend(i - 0.4 + 0.8 * np.arange(4) / 4)
    by.extend(seg)
bx.append(len(windows) - 0.2); by.append(closes[-1])  # close exactly at table value
ax1.plot(bx, by, color=PALETTE["price"], linewidth=2.0, label="Basis (bp)", zorder=3)
ax1.scatter([0, 4], [basis_entry, basis_close[-1]], color=PALETTE["price"], zorder=4)
ax1.axhline(0, color=PALETTE["zero"], linewidth=0.8)
ax1.set_ylabel("bp")
ax1.legend(loc="upper right")
ax1.set_title("T051 — Funding-Rate Carry + Basis Mean-Reversion: synthetic two-position book (seed 151)")

# Panel 2: cumulative net P&L with entry/exit markers
ax2.step(x, p1_net_cum, where="mid", color=PALETTE["profit"], linewidth=2.2,
         label="Position 1 (carry) cum. net P&L")
ax2.step(x, p2_net_cum, where="mid", color=PALETTE["loss"], linewidth=2.2,
         label="Position 2 (thin MR) cum. net P&L")
ax2.scatter([0], [p1_net_cum[0] - (p1_funding[0] + p1_basis_mtm[0])],
            color=PALETTE["profit"], s=90, marker="^", zorder=5)
ax2.scatter([4], [p1_net_cum[-1]], color=PALETTE["profit"], s=90, marker="v", zorder=5)
ax2.scatter([2], [p2_net_cum[2] - (p2_funding[2] + p2_basis_mtm[2])],
            color=PALETTE["loss"], s=90, marker="^", zorder=5)
ax2.scatter([3], [p2_net_cum[-1]], color=PALETTE["loss"], s=90, marker="v", zorder=5)
ax2.annotate("Pos 1 net +$350\n(entry W1, exit W5)", xy=(4, p1_net_cum[-1]),
             xytext=(2.6, 300), fontsize=9, color=PALETTE["profit"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]))
ax2.annotate("Pos 2 net -$90\n(costs > gross)", xy=(3, p2_net_cum[-1]),
             xytext=(3.4, -40), fontsize=9, color=PALETTE["loss"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["loss"]))
ax2.set_xticks(x); ax2.set_xticklabels(windows)
ax2.set_xlabel("8-hour funding window (synthetic)")
ax2.set_ylabel("Cumulative net P&L ($)")
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T051_example.png", bbox_inches="tight")
plt.close()
print("T051: pos1 net = $%.0f, pos2 net = $%.0f, total = $%.0f"
      % (p1_net_cum[-1], p2_net_cum[-1], total_net))
