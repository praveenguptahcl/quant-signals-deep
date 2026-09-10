import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
import os

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

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# synthetic DeepLOB + feature-stack prediction walk, seed = stage number
rng = np.random.default_rng(155)

Q_BASE = 100          # shares (example)
C_MIN = 0.58          # confidence gate (example)
P0_FLAT_MAX = 0.40    # flat-class veto (example)
TICK = 0.01           # USD
COST_TICK = 0.6       # round-trip cost in ticks (example: half-spread + fees)

N = 12
p_minus = np.array([0.10, 0.62, 0.15, 0.08, 0.40, 0.70, 0.12, 0.55, 0.05, 0.25, 0.66, 0.20])
p_flat  = np.array([0.20, 0.18, 0.25, 0.12, 0.40, 0.15, 0.28, 0.30, 0.10, 0.50, 0.20, 0.60])
p_plus  = 1.0 - p_minus - p_flat
probs = np.column_stack([p_minus, p_flat, p_plus])

trades = []
print("seed=155 | synthetic prediction walk (side, size, true move, gross, cost, net):")
for i in range(N):
    pm, pf, pp = probs[i]
    c = max(pm, pp)
    side = 1 if pp >= pm else -1
    fire = (c >= C_MIN) and (pf < P0_FLAT_MAX)
    if not fire:
        print(f"  pred#{i+1:2d}: p-={pm:.2f} p0={pf:.2f} p+={pp:.2f} c={c:.2f} -> NO FIRE")
        continue
    size = int(Q_BASE * (c - C_MIN) / (1 - C_MIN))
    true_cls = rng.choice([-1, 0, 1], p=[pm, pf, pp])
    move_ticks = 2 * true_cls                      # +/-2 ticks on a directional hit, 0 on flat
    gross = side * move_ticks * TICK * size
    cost = COST_TICK * TICK * size
    net = gross - cost
    trades.append((i + 1, side, size, c, true_cls, gross, cost, net))
    print(f"  pred#{i+1:2d}: p-={pm:.2f} p0={pf:.2f} p+={pp:.2f} c={c:.2f} -> "
          f"{'LONG ' if side>0 else 'SHORT'} size={size:3d} true={true_cls:+d} "
          f"gross={gross:+.2f} cost={cost:.2f} net={net:+.2f}")
total = sum(t[7] for t in trades)
print(f"fired {len(trades)}/{N} predictions; total net = {total:+.2f}")

idx = np.array([t[0] for t in trades])
nets = np.array([t[7] for t in trades])
sides = np.array([t[1] for t in trades])
conf = np.array([t[3] for t in trades])
equity = np.cumsum(nets)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, gridspec_kw={"hspace": 0.08})
x = np.arange(1, N + 1)
ax1.bar(x, p_plus, color=PALETTE["profit"], alpha=0.8, label="p(up)")
ax1.bar(x, p_flat, bottom=p_plus, color=PALETTE["volume"], alpha=0.8, label="p(flat)")
ax1.bar(x, p_minus, bottom=p_plus + p_flat, color=PALETTE["loss"], alpha=0.8, label="p(down)")
ax1.axhline(C_MIN, color=PALETTE["signal"], ls="--", lw=1.2,
            label=f"Confidence gate c_min={C_MIN} (example)")
fired_x = idx
ax1.scatter(fired_x, np.full_like(fired_x, 1.02, dtype=float),
            color=PALETTE["zero"], marker="^", s=60, zorder=5, label="fired trades")
ax1.set_ylim(0, 1.15)
ax1.set_ylabel("Predicted class probability")
ax1.legend(loc="upper left")
ax1.set_title("T055 — DeepLOB + Feature-Stack Classifier: synthetic prediction walk (seed 155)")

ax2.plot(np.arange(1, len(equity) + 1), equity, color=PALETTE["price"], lw=1.5,
         label="Cumulative net P&L (USD)")
for i, t in enumerate(trades):
    n_, side, size, c = t[7], t[1], t[2], t[3]
    col = PALETTE["profit"] if n_ >= 0 else PALETTE["loss"]
    ax2.scatter([i + 1], [equity[i]], color=col, s=60, zorder=5)
    ax2.annotate(f"T{i+1}\n{n_:+.0f} ({'L' if side>0 else 'S'}{size})",
                 (i + 1, equity[i]), fontsize=7, color=col,
                 xytext=(5, 8), textcoords="offset points")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("Net P&L (USD)")
ax2.set_xlabel("Fired trade sequence (synthetic)")
ax2.set_xlim(0.5, len(trades) + 0.5)
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T055_example.png", bbox_inches="tight")
plt.close()
