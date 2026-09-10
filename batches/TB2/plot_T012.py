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

# ---- SYNTHETIC DATA (seed 112; same numbers as T012.md T4) ----
# Scenario A: gap down -0.80% (prior close 100.00 -> open 99.20), ATR20 = 2.40,
# Lee-Mykland T(open) = 1.8 (no jump), S100 screen clean (no earnings, SUE +0.3).
# Long 568 shares, entry 09:35 at 99.24, exit 99.78 (75% fill toward 100.00).
# Scenarios B/C are vetoed by S037 (jump) and S100 (earnings) respectively.
rng = np.random.default_rng(112)

A = dict(label="A (executed)", prior=100.00, open=99.20, entry=99.24, entry_bar=5,
         exit=99.78, exit_bar=30, shares=568,
         comm=2 * (568 * 0.005 + 0.50), spread_impact=22.60)
A["gross"] = (A["exit"] - A["entry"]) * A["shares"]
A["costs"] = A["comm"] + A["spread_impact"]
A["net"] = A["gross"] - A["costs"]
B = dict(label="B (vetoed: jump)", net=0.00)
C = dict(label="C (vetoed: earnings)", net=0.00)

# Synthetic 60-bar intraday path for scenario A, anchored to entry/exit prices.
n = 60
p = np.zeros(n)
for t in range(n):
    if t <= A["exit_bar"]:
        frac = t / A["exit_bar"]
        p[t] = A["open"] + (A["exit"] - A["open"]) * frac ** 0.75
    else:
        frac = (t - A["exit_bar"]) / (n - A["exit_bar"])
        p[t] = A["exit"] + (99.85 - A["exit"]) * min(frac * 1.2, 1.0)
p = p + rng.normal(0, 0.012, n)
p[A["entry_bar"]] = A["entry"]
p[A["exit_bar"]] = A["exit"]
p[0] = A["open"]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [3, 2]})
fig.suptitle("T012 — Jump-Filtered Overnight-Gap Fade: intraday fade timeline (scenario A)\n"
             "and per-scenario net P&L", fontweight="bold")

# Panel 1: trade timeline with entry/exit price markers.
ax1.plot(np.arange(n), p, color=PALETTE["price"], lw=1.4, label="synthetic 1-min price")
ax1.axhline(A["prior"], color=PALETTE["volume"], ls="--", lw=1.0, label="prior close 100.00")
ax1.scatter([A["entry_bar"]], [A["entry"]], marker="^", s=90, color=PALETTE["profit"],
            zorder=5, label=f'entry long @ {A["entry"]:.2f} (09:35)')
ax1.scatter([A["exit_bar"]], [A["exit"]], marker="v", s=90, color=PALETTE["signal"],
            zorder=5, label=f'exit @ {A["exit"]:.2f} (75% fill)')
ax1.annotate(f'entry\n${A["entry"]:.2f}', xy=(A["entry_bar"], A["entry"]),
             xytext=(-30, -28), textcoords="offset points", fontsize=9,
             color=PALETTE["profit"], weight="bold",
             arrowprops=dict(arrowstyle="->", color=PALETTE["profit"], lw=1.2))
ax1.annotate(f'exit\n${A["exit"]:.2f}', xy=(A["exit_bar"], A["exit"]),
             xytext=(10, 12), textcoords="offset points", fontsize=9,
             color=PALETTE["signal"], weight="bold",
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"], lw=1.2))
ax1.annotate(f'net +${A["net"]:.2f}', xy=(A["exit_bar"], A["exit"]),
             xytext=(40, -30), textcoords="offset points", fontsize=9,
             color=PALETTE["profit"], weight="bold")
ax1.set_ylabel("price ($)")
ax1.set_xlabel("minutes after open (synthetic 1-min bars, seed 112)")
ax1.set_title("Scenario A: fade a -0.80% gap with no detected jump, no earnings", fontsize=11)
ax1.legend(loc="lower right", fontsize=8)

# Panel 2: per-scenario net P&L bars.
labels = [A["label"], B["label"], C["label"]]
vals = [A["net"], B["net"], C["net"]]
colors = [PALETTE["profit"], PALETTE["volume"], PALETTE["volume"]]
bars = ax2.bar(labels, vals, color=colors, edgecolor=PALETTE["zero"], lw=0.8)
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("net P&L ($)")
ax2.set_title("Per-scenario net P&L: vetoes earn $0 (stand down is a position)", fontsize=11)
for b, v in zip(bars, vals):
    ax2.annotate(f"${v:+.2f}", xy=(b.get_x() + b.get_width() / 2, v),
                 xytext=(0, 8 if v >= 0 else -18), textcoords="offset points",
                 ha="center", fontsize=9, weight="bold",
                 color=PALETTE["profit"] if v > 0 else PALETTE["volume"])
ax2.set_ylim(-60, 340)

print("T012 scenario check (seed 112):")
print(f'  A: entry {A["entry"]:.2f} x{A["shares"]} exit {A["exit"]:.2f} '
      f'gross {A["gross"]:+.2f} comm {A["comm"]:.2f} spread/impact {A["spread_impact"]:.2f} '
      f'net {A["net"]:+.2f}')
print(f'  B: vetoed (jump) net {B["net"]:+.2f} | C: vetoed (earnings) net {C["net"]:+.2f}')

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T012_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
