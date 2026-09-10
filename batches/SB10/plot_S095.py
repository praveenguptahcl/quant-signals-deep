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

# ---- OPERATOR-VERIFIED WORKED EXAMPLE (Worked Example B, seed 95) ----
# $10k long spot + $10k short perp, 8h funding intervals over 24h.
# Funding rates: 0.020%, 0.015%, 0.025% -> funding payments $2.00, $1.50, $2.50 = $6.00.
# Fees: 0.04%/leg x 4 legs = $16.00. Net P&L = -$10.00 (-0.10%).
rng = np.random.default_rng(95)  # seed recorded; numbers are the verified worked example
_ = rng  # deterministic seed; example values below are fixed/verified

funding_per_interval = np.array([2.00, 1.50, 2.50])          # dollars received
labels = ["Entry\nfees", "Funding\n8h", "Funding\n16h", "Funding\n24h", "Exit\nfees"]
cashflows = np.array([-8.00, 2.00, 1.50, 2.50, -8.00])
cum = np.cumsum(cashflows)
t_axis = np.arange(5)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2))

colors = [PALETTE["loss"] if v < 0 else PALETTE["profit"] for v in cashflows]
ax1.bar(labels, cashflows, color=colors, edgecolor="black", linewidth=0.6)
ax1.axhline(0, color=PALETTE["zero"], linewidth=1)
ax1.set_title("S095 — Funding cash-and-carry\ncash flows ($)")
ax1.set_ylabel("dollars")
for i, v in enumerate(cashflows):
    ax1.text(i, v + (0.55 if v > 0 else -0.75), f"${v:+.2f}",
             ha="center", fontsize=9, weight="bold")

ax2.step(t_axis, np.concatenate([[0], cum[:-1]]), where="post",
         color=PALETTE["price"], linewidth=2.5, label="Cumulative net P&L")
ax2.scatter(t_axis, cum, color=PALETTE["price"], s=45, zorder=5)
ax2.axhline(0, color=PALETTE["zero"], linewidth=1)
ax2.set_title("Cumulative net P&L (fees included)")
ax2.set_xlabel("event")
ax2.set_ylabel("dollars (net)")
ax2.set_xticks(t_axis)
ax2.set_xticklabels(labels, fontsize=8)
ax2.text(4, -10.0, " Net = -$10.00\n(-0.10% on $10k)", fontsize=9, weight="bold",
         color=PALETTE["loss"], va="bottom", ha="center",
         bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))
ax2.text(0.02, 0.98,
         "Gross funding R_24h = +0.060% | f_ann = 21.9% (simple)\nFees = $16.00 -> net negative",
         transform=ax2.transAxes, fontsize=8, va="top", ha="left",
         bbox=dict(boxstyle="round,pad=0.3", facecolor=PALETTE["band"], alpha=0.6))
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S095_example.png", bbox_inches="tight")
plt.close()
print("S095 chart written; final net P&L =", cum[-1])
