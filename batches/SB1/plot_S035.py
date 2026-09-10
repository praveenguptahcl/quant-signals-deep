"""Plot script for S035 worked example. Run with cwd=~/workspace/quant-signals-deep."""
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

SEED = 35
rng = np.random.default_rng(SEED)

# --- Synthetic 10-stock month: formation return (t-1) then holding return (t).
# Short-term reversal: holding return leans against formation return (plus noise).
names = np.array(["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ"])
form_pct = np.round(rng.normal(0.0, 6.0, 10), 2)          # prior-month return, %
hold_pct = np.round(-0.28 * form_pct + rng.normal(0.0, 2.0, 10), 2)  # next-month return, %

order = np.argsort(form_pct)
longs = order[:3]    # 3 worst losers -> LONG
shorts = order[-3:]  # 3 best winners -> SHORT
port_gross = np.round(hold_pct[longs].mean() - hold_pct[shorts].mean(), 2)
corr = np.round(np.corrcoef(form_pct, hold_pct)[0, 1], 3)

print("S035 worked-example table (seed 35)")
print(" name | form(t-1) % | hold(t) % | leg")
for i in range(10):
    leg = "LONG (loser)" if i in longs else ("SHORT (winner)" if i in shorts else "flat")
    print(f" {names[i]}  | {form_pct[i]:+10.2f} | {hold_pct[i]:+9.2f} | {leg}")
print(f"\ncorr(formation, holding) = {corr}  ->  reversal signature")
print(f"Equal-weight L3/S3 portfolio gross = {port_gross:+.2f}% for the toy month (before costs)")

colors = np.array([PALETTE["volume"]] * 10)
colors[longs] = PALETTE["profit"]
colors[shorts] = PALETTE["loss"]
plt.scatter(form_pct, hold_pct, c=colors, s=90, zorder=3)
for i, nm in enumerate(names):
    plt.annotate(nm, (form_pct[i], hold_pct[i]), fontsize=8,
                 xytext=(5, 5), textcoords="offset points")
# Least-squares line through the synthetic scatter (illustrative only)
m, b = np.polyfit(form_pct, hold_pct, 1)
xs = np.array([form_pct.min() - 1, form_pct.max() + 1])
plt.plot(xs, m * xs + b, linestyle="--", color=PALETTE["signal"],
         label=f"Toy fit: slope {m:.2f} (< 0 = reversal)")
plt.axhline(0, color=PALETTE["zero"], linewidth=1)
plt.axvline(0, color=PALETTE["zero"], linewidth=1)
plt.xlabel("Formation-month return (%) — synthetic")
plt.ylabel("Holding-month return (%) — synthetic")
plt.title("S035 — Short-term reversal: 10-stock synthetic sort")
from matplotlib.lines import Line2D
plt.legend(handles=[
    Line2D([0], [0], marker="o", color="w", markerfacecolor=PALETTE["profit"],
           markersize=9, label="Long leg (prior losers)"),
    Line2D([0], [0], marker="o", color="w", markerfacecolor=PALETTE["loss"],
           markersize=9, label="Short leg (prior winners)"),
    Line2D([0], [0], color=PALETTE["signal"], linestyle="--",
           label=f"Toy fit: slope {m:.2f} (< 0 = reversal)"),
], loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S035_example.png", bbox_inches="tight")
plt.close()
print("saved images/S035_example.png")
