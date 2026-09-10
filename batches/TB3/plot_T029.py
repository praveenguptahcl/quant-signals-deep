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

# T029 worked example — Spread-Estimate Edge Filter (SYNTHETIC, seed 129)
# Seed recorded so the script is reproducible; the 6 setups are the hand-verified
# rows in the chapter's T4 table (identical numbers).
rng = np.random.default_rng(129)
OUT = "/home/hatch/workspace/quant-signals-deep/images/T029_example.png"

# 6 synthetic RVOL-breakout setups, 200 shares each, example spread cap 2.0 cents.
# Gate: TRADE only if Roll_hat <= 2.0c AND CS_hat <= 2.0c AND estimated edge >= 2 x spread.
# net = shares*(exit-entry)*direction - shares*spread_hat_used  (taker round-trip cost ~= spread)
setups  = ["A", "B", "C", "D", "E", "F"]
rvol    = np.array([1.8, 2.3, 1.6, 3.1, 1.9, 1.5])
side    = np.array(["long", "long", "long", "long", "short", "long"])
entry   = np.array([100.00, 100.05, 100.02, 100.10, 99.98, 100.00])
exitp   = np.array([100.09, 100.10, 99.99, 100.16, 99.90, 100.07])
roll    = np.array([1.2, 1.0, 1.4, 2.8, 1.1, 2.5])      # Roll-implied spread (cents)
cs      = np.array([1.1, 0.9, 1.3, 2.6, 1.0, 2.4])      # Corwin-Schultz spread (cents)
spread_cap = 2.0
pass_gate = (roll <= spread_cap) & (cs <= spread_cap) & (rvol >= 1.5)
spr_used = np.maximum(roll, cs) / 100.0                # cost per share ($) = max of estimates
dirn = np.where(side == "long", 1.0, -1.0)
gross = 200 * dirn * (exitp - entry)
cost = np.where(pass_gate, 200 * spr_used, 0.0)
net = np.where(pass_gate, gross - cost, 0.0)
cum = np.cumsum(net)
assert abs(gross.sum() * 0 + gross[pass_gate].sum() - 38.0) < 1e-9
assert abs(cost.sum() - 9.40) < 1e-9, cost.sum()
assert abs(cum[-1] - 28.60) < 1e-9, cum[-1]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                              gridspec_kw={"height_ratios": [1.2, 1]})
fig.suptitle("T029 — Spread-Estimate Edge Filter: estimated spread vs gate and "
             "cumulative net P&L (6 synthetic RVOL setups, seed 129)",
             fontsize=13, fontweight="bold", y=0.98)

x = np.arange(len(setups))
w = 0.36
ax1.bar(x - w / 2, roll, w, label="Roll spread est (S012)", color=PALETTE["signal2"],
        edgecolor="#2c3e50")
ax1.bar(x + w / 2, cs, w, label="Corwin-Schultz spread est (S013)", color=PALETTE["band"],
        edgecolor="#2c3e50")
ax1.axhline(spread_cap, color=PALETTE["signal"], linestyle="--", linewidth=1.5,
            label="spread gate cap (example 2.0c)")
for i, g in enumerate(pass_gate):
    ax1.text(x[i], max(roll[i], cs[i]) + 0.12, "TRADE" if g else "BLOCKED",
             ha="center", fontsize=8.5, fontweight="bold",
             color=PALETTE["profit"] if g else PALETTE["loss"])
ax1.set_xticks(x); ax1.set_xticklabels(
    [f"{s}\nRVOL {r}x {d}" for s, r, d in zip(setups, rvol, side)])
ax1.set_ylabel("estimated effective spread (cents)")
ax1.set_title("Estimated spreads vs the example gate (blocked = too expensive to touch)")
ax1.legend(loc="upper left")

ax2.step(x, cum, where="mid", color=PALETTE["price"], linewidth=2.2,
         label="cumulative net P&L (after estimated spread costs)")
ax2.scatter(x, cum, c=[PALETTE["profit"] if g else "#bdc3c7" for g in pass_gate],
            s=60, zorder=5, edgecolors="#2c3e50")
for i, (n, g) in enumerate(zip(net, pass_gate)):
    ax2.annotate("$%+.2f" % n if g else "$0.00 (blocked)",
                 (x[i], cum[i]), textcoords="offset points", xytext=(0, 12),
                 ha="center", fontsize=8.5, fontweight="bold",
                 color=PALETTE["profit"] if (g and n > 0)
                 else (PALETTE["loss"] if (g and n < 0) else "#7f8c8d"))
ax2.axhline(0, color=PALETTE["zero"], linewidth=1)
ax2.set_xticks(x); ax2.set_xticklabels(setups)
ax2.set_xlabel("RVOL-breakout setup (event order)")
ax2.set_ylabel("cumulative net P&L ($)")
ax2.legend(loc="upper left")
ax2.text(0.02, 0.06, "setup D blocked despite RVOL 3.1x: spread 2.8c > 2.0c gate "
         "(a would-be +$12.00 gross trade refused)",
         transform=ax2.transAxes, fontsize=8.5, color="#7f8c8d")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig(OUT, bbox_inches="tight")
plt.close()
print("wrote", OUT, "| net total $%.2f" % cum[-1])
