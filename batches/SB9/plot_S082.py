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

# ---- REPRODUCIBILITY SEED (stated in the chapter): the worked-example arithmetic
#      below is fully deterministic (no sampling); the seed fixes the environment
#      so re-runs are byte-identical. ----
rng = np.random.default_rng(82)

# ---- SYNTHETIC worked-example numbers (stated, hand-checkable) ----
# 55% directional accuracy; correct trade: mid moves 0.06p our way; wrong trade: 0.06p against.
# Market order pays half the 0.10p spread + 0.005p fees+slippage. All in pence.
acc = 0.55
move = 0.06        # pence, mid move in the trade's favor when correct
half_spread = 0.05 # pence (0.10p quoted spread)
fees_slip = 0.005
net_correct = move - half_spread - fees_slip        # +0.005
net_wrong = -move - half_spread - fees_slip         # -0.115
exp_net = acc * net_correct + (1 - acc) * net_wrong # -0.049
print(f"net_correct={net_correct:+.3f}p  net_wrong={net_wrong:+.3f}p  expected={exp_net:+.3f}p per trade")

# ---- PLOT: left = waterfall of expected per-trade P&L; right = accuracy vs economics ----
fig, axes = plt.subplots(1, 2, figsize=(10, 5.2), gridspec_kw={"width_ratios": [1.25, 1]})
ax = axes[0]
steps = [("start", 0.0, ""), ("E[mid move]\n55% acc", 0.006, "#1f3a5f"),
         ("half-spread paid", -0.05, "#c0392b"), ("fees+slippage", -0.005, "#c0392b"),
         ("net E[P&L]", exp_net, "#922b21")]
cum = 0.0
for i, (label, delta, color) in enumerate(steps[1:], 1):
    ax.bar(i, delta, bottom=cum, color=color)
    ax.plot([i - 0.45, i + 0.45], [cum, cum], color=PALETTE["zero"], lw=1)
    cum += delta
    ax.text(i, cum + (0.004 if delta > 0 else -0.004), f"{delta:+.3f}p",
            ha="center", va="bottom" if delta > 0 else "top", fontsize=9, weight="bold")
ax.set_xticks(range(1, len(steps)))
ax.set_xticklabels([s[0] for s in steps[1:]], fontsize=9)
ax.axhline(0, color=PALETTE["zero"], lw=1)
ax.set_ylabel("expected per-trade P&L (pence)")
ax.set_title("S082 — why 55% accuracy is not profit\n(waterfall, synthetic example)")

ax2 = axes[1]
labels = ["correct\n55% of trades", "wrong\n45% of trades"]
vals = [net_correct, net_wrong]
ax2.bar(labels, vals, color=[PALETTE["profit"], PALETTE["loss"]])
ax2.axhline(0, color=PALETTE["zero"], lw=1)
for x, v in zip(labels, vals):
    ax2.text(x, v + (0.004 if v > 0 else -0.004), f"{v:+.3f}p", ha="center",
             va="bottom" if v > 0 else "top", fontsize=9, weight="bold")
ax2.set_ylabel("net per trade (pence)")
ax2.set_title("economics of a correct\nvs incorrect call")
fig.suptitle("S082 — DeepLOB: accuracy ≠ profit (synthetic example)", fontsize=13, weight="bold")
fig.text(0.5, 0.02, "Unverified review lead: median gross ≈ 0.01p/trade vs 0.10p spread — spread is exactly 10× the gross edge.",
         ha="center", fontsize=9, color=PALETTE["signal"], style="italic")
plt.tight_layout(rect=[0, 0.04, 1, 0.94])

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout(rect=[0, 0.04, 1, 0.94])
plt.savefig("images/S082_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
