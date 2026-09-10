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

# ---- SYNTHETIC WORKED EXAMPLE (seed 86086) ----
# 12 synthetic primary-signal trades. Primary picks side s_t; triple-barrier
# labels y_t = 1 (win) / 0 (loss); meta-model outputs p_hat = P(win).
rng = np.random.default_rng(86086)
n = 12
sides = rng.choice([-1, 1], size=n)
wins = rng.random(n) < 0.45
p_hat = np.clip(0.5 + 0.33 * (2 * wins - 1) + rng.normal(0, 0.13, n), 0.05, 0.95)
rvol_z = np.round(rng.normal(0, 1.2, n), 2)
sprd_z = np.round(rng.normal(0, 1.0, n), 2)

TAU = 0.55  # example meta threshold — not an institutional standard
take = p_hat >= TAU

# P&L sketch: $1,000 notional/trade; win +$18, loss -$14, $2 round-trip cost
win_pnl, loss_pnl, cost = 18.0, -14.0, 2.0
trade_pnl = np.where(wins, win_pnl, loss_pnl) - cost
pnl_primary = trade_pnl.sum()
pnl_filtered = trade_pnl[take].sum()
prec_primary = wins.mean()
prec_filtered = wins[take].mean() if take.sum() else float("nan")

print("trade | side | rvol_z | sprd_z | barrier | p_hat | decision | pnl_$")
for i in range(n):
    print(f"{i+1:>5} | {sides[i]:>+4} | {rvol_z[i]:>6.2f} | {sprd_z[i]:>6.2f} | "
          f"{'win ' if wins[i] else 'loss'} | {p_hat[i]:.2f} | "
          f"{'BET ' if take[i] else 'SKIP'} | {trade_pnl[i]:+6.1f}")
print(f"\nprimary precision: {prec_primary:.3f} ({wins.sum()}/{n})")
print(f"filtered precision: {prec_filtered:.3f} ({wins[take].sum()}/{take.sum()})")
print(f"primary net P&L: ${pnl_primary:.0f} | filtered net P&L: ${pnl_filtered:.0f}")

# ---- CHART ----
fig, ax = plt.subplots()
x = np.arange(1, n + 1)
colors = [PALETTE["profit"] if w else PALETTE["loss"] for w in wins]
bars = ax.bar(x, p_hat, color=colors, edgecolor=PALETTE["zero"], linewidth=0.6)
# mark taken vs skipped
for i, b in enumerate(bars):
    if take[i]:
        b.set_edgecolor(PALETTE["price"])
        b.set_linewidth(2.2)
ax.axhline(TAU, color=PALETTE["signal"], linestyle="--", linewidth=1.5,
           label=f"meta threshold tau = {TAU} (example)")
ax.set_xlabel("Synthetic trade #")
ax.set_ylabel("Meta-model P(win)")
ax.set_title("S086 — Meta-labeling: 12-trade synthetic overlay (seed 86086)")
ax.set_xticks(x)
ax.set_ylim(0, 1.0)
ax.legend(handles=[
    plt.Rectangle((0, 0), 1, 1, color=PALETTE["profit"], label="barrier win (y=1)"),
    plt.Rectangle((0, 0), 1, 1, color=PALETTE["loss"], label="barrier loss (y=0)"),
    plt.Line2D([0], [0], color=PALETTE["signal"], linestyle="--",
               label=f"meta threshold tau = {TAU} (example)"),
    plt.Line2D([0], [0], marker="s", color="w", markerfacecolor="none",
               markeredgecolor=PALETTE["price"], markersize=10, markeredgewidth=2.2,
               label="thick border = bet taken"),
])
ax.text(0.98, 0.04,
        f"primary precision {prec_primary:.2f} -> filtered {prec_filtered:.2f}\n"
        f"net P&L ${pnl_primary:.0f} -> ${pnl_filtered:.0f} (synthetic)",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=PALETTE["zero"], alpha=0.9))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S086_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S086_example.png")
