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

# ---- SYNTHETIC DATA (seed = stage number 108) ----
rng = np.random.default_rng(108)
N = 240
# Hand-anchored z-score path: linear interp between anchors + small rng noise, anchors exact.
anchors = {0: 0.0, 40: 2.00, 60: 1.20, 88: 0.23, 100: 0.10,
           120: 2.00, 152: 3.50, 165: -0.10, 175: -2.00, 215: -0.23,
           230: 0.05, 239: 0.0}
xs = sorted(anchors)
z = np.zeros(N)
for i in range(N):
    for a, b in zip(xs[:-1], xs[1:]):
        if a <= i <= b:
            w = (i - a) / (b - a) if b > a else 0.0
            z[i] = anchors[a] * (1 - w) + anchors[b] * w
            break
z = z + rng.normal(0, 0.15, N)
for k, v in anchors.items():
    z[k] = v

FEE = 0.005  # $/share each way

def leg_pnl(shares, entry_px, exit_px, side):
    # side: +1 = long (buy entry, sell exit), -1 = short (sell entry, buy exit)
    return side * shares * (exit_px - entry_px)

trades = [
    dict(name="T1", entry_bar=40, exit_bar=88, entry_z=2.00, exit_z=0.23,
         desc="short spread, Kalman re-hedge mid-trade",
         entry_note="short A 444 @ 150.59 / long B 710 @ 93.76",
         exit_note="cover A 444 @ 149.28 / sell B 728 @ 93.24",
         nets={"A": leg_pnl(444, 150.59, 149.28, -1),
               "B1": leg_pnl(710, 93.76, 93.24, +1),
               "B2_rehedge": leg_pnl(18, 93.30, 93.24, +1)},
         shares=444 + 710 + 18),
    dict(name="T2", entry_bar=120, exit_bar=152, entry_z=2.00, exit_z=3.50,
         desc="short spread, stop-loss at |z|=3.5",
         entry_note="short A 444 @ 150.59 / long B 710 @ 93.76",
         exit_note="cover A 444 @ 151.06 / sell B 710 @ 93.74",
         nets={"A": leg_pnl(444, 150.59, 151.06, -1),
               "B": leg_pnl(710, 93.76, 93.74, +1)},
         shares=444 + 710),
    dict(name="T3", entry_bar=175, exit_bar=215, entry_z=-2.00, exit_z=-0.23,
         desc="long spread, convergence exit",
         entry_note="long A 444 @ 149.41 / short B 710 @ 93.74",
         exit_note="sell A 444 @ 149.92 / cover B 710 @ 93.76",
         nets={"A": leg_pnl(444, 149.41, 149.92, +1),
               "B": leg_pnl(710, 93.74, 93.76, -1)},
         shares=444 + 710),
]
for t in trades:
    t["gross"] = sum(t["nets"].values())
    t["fees"] = t["shares"] * 2 * FEE
    t["net"] = t["gross"] - t["fees"]

print("T008 synthetic trade table (seed 108):")
cum = 0.0
for t in trades:
    cum += t["net"]
    print(f"  {t['name']}: gross={t['gross']:+.2f} fees=-{t['fees']:.2f} "
          f"net={t['net']:+.2f} cum={cum:+.2f}")
print(f"  total net = {cum:+.2f}")
cum_vals = np.cumsum([t["net"] for t in trades])

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=False,
                               gridspec_kw={"height_ratios": [3, 2]})
bars = np.arange(N)
ax1.plot(bars, z, color=PALETTE["price"], lw=1.2, label="Kalman innovation z-score")
for lvl, ls, lab in [(2.0, "--", "entry +/-2.0"), (-2.0, "--", None),
                     (3.5, ":", "stop +/-3.5"), (-3.5, ":", None),
                     (0.25, "-.", "exit +/-0.25"), (-0.25, "-.", None)]:
    ax1.axhline(lvl, color=PALETTE["signal"] if abs(lvl) >= 2 else PALETTE["signal2"],
                ls=ls, lw=0.9, alpha=0.7, label=lab)
anno_cfg = {
    "T1": dict(entry_off=(6, 12), entry_ha="left", exit_off=(6, -22), exit_ha="left"),
    "T2": dict(entry_off=(-6, 16), entry_ha="right", exit_off=(8, -30), exit_ha="left"),
    "T3": dict(entry_off=(-6, -16), entry_ha="right", exit_off=(8, 12), exit_ha="left"),
}
for t in trades:
    cfg = anno_cfg[t["name"]]
    ax1.scatter(t["entry_bar"], t["entry_z"], color=PALETTE["signal"],
                marker="v", s=70, zorder=5)
    ax1.scatter(t["exit_bar"], t["exit_z"],
                color=PALETTE["profit"] if t["net"] > 0 else PALETTE["loss"],
                marker="^", s=70, zorder=5)
    ax1.annotate(f"{t['name']} entry\n{t['entry_note']}",
                 (t["entry_bar"], t["entry_z"]), fontsize=7,
                 xytext=cfg["entry_off"], textcoords="offset points",
                 ha=cfg["entry_ha"])
    ax1.annotate(f"{t['name']} exit\n{t['exit_note']}",
                 (t["exit_bar"], t["exit_z"]), fontsize=7,
                 xytext=cfg["exit_off"], textcoords="offset points",
                 ha=cfg["exit_ha"])
ax1.set_ylabel("z-score")
ax1.set_xlabel("imbalance bar index (synthetic)")
ax1.legend(loc="upper right", ncol=2)

ax2.step([0] + [t["exit_bar"] for t in trades],
         [0.0] + list(cum_vals), where="post", color=PALETTE["price"], lw=1.6,
         label="cumulative net P&L ($)")
for t, cv in zip(trades, cum_vals):
    ax2.annotate(f"{t['name']}: {t['net']:+.2f}",
                 (t["exit_bar"], cv), fontsize=8,
                 xytext=(0, 10 if t["net"] > 0 else -16),
                 textcoords="offset points", ha="center",
                 color=PALETTE["profit"] if t["net"] > 0 else PALETTE["loss"],
                 weight="bold")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("cumulative net P&L ($)")
ax2.set_xlabel("imbalance bar index (synthetic)")

fig.suptitle("T008 — Kalman Dynamic-Hedge Pairs: spread z-score trade timeline + cumulative net P&L (synthetic)",
             fontsize=13, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T008_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T008_example.png")
