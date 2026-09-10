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

# ---- T058 worked-example data (MUST match T4 text exactly) ----
rng = np.random.default_rng(158)  # seed stated in T4
# Anchor points (day, price) — hand-set from the T4 narrative; wiggle is seeded noise
anchors = {0: 2.4000, 6: 1.9120, 9: 2.0240, 11: 2.1500}
days = np.arange(0, 15)
base = np.interp(days, list(anchors.keys()), list(anchors.values()))
noise = rng.normal(0, 0.03, len(days))
noise[[0, 6, 9, 11]] = 0.0  # keep anchor points exact for text/chart agreement
price = base + noise
# trades: (day, side, qty, px)
trades = [
    dict(day=0,  side=-1, qty=20000, entry=2.4000, exit_day=6,  exit=1.9120, label="T1 short 20k"),
    dict(day=9,  side=-1, qty=8000,  entry=2.0240, exit_day=11, exit=2.1500, label="T2 short 8k"),
]
fee_bp = 0.0005      # taker fee per side (example)
funding_day = 0.0003 # perp funding per day on avg notional (example)

def net_pnl(t):
    gross = t["qty"] * t["side"] * (t["exit"] - t["entry"])
    fees = fee_bp * t["qty"] * (t["entry"] + t["exit"])
    avg_not = t["qty"] * (t["entry"] + t["exit"]) / 2
    funding = funding_day * (t["exit_day"] - t["day"]) * avg_not  # short pays funding
    return gross, fees, funding, gross - fees - funding

nets = []
for t in trades:
    g, f, fu, n = net_pnl(t)
    nets.append(n)
    print(f"{t['label']}: entry {t['entry']:.4f} exit {t['exit']:.4f} "
          f"gross {g:+.2f} fees {f:.2f} funding {fu:.2f} NET {n:+.2f}")
print(f"TOTAL NET {sum(nets):+.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, height_ratios=[3, 2])
ax1.plot(days, price, color=PALETTE["price"], lw=2, label="UNLK synthetic price ($)")
for t, n in zip(trades, nets):
    c = PALETTE["profit"] if n > 0 else PALETTE["loss"]
    ax1.scatter([t["day"]], [t["entry"]], s=90, marker="v", color=PALETTE["signal"],
                zorder=5, edgecolors="k", label=f"short entry {t['label']}" if n > 0 else "")
    ax1.scatter([t["exit_day"]], [t["exit"]], s=90, marker="^", color=c,
                zorder=5, edgecolors="k")
    ax1.annotate(f"{t['label']}\nnet {n:+.2f}$",
                 xy=(t["exit_day"], t["exit"]), xytext=(8, -14 if n < 0 else 12),
                 textcoords="offset points", fontsize=8, color=c,
                 arrowprops=dict(arrowstyle="->", color=c, lw=1))
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper right")
ax1.set_title("T058 — Token Unlock Supply-Shock Fade: synthetic 14-day trade timeline & net P&L")

cum = np.zeros(len(days) + 1)
for t, n in zip(trades, nets):
    cum[t["exit_day"] + 1:] += n
ax2.step(np.arange(len(days) + 1) - 0.5, cum, where="post", color=PALETTE["price"], lw=2,
         label="cumulative net P&L ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.fill_between(np.arange(len(days) + 1) - 0.5, cum, 0, step="post", alpha=0.25,
                 color=PALETTE["profit"])
ax2.set_xlabel("days since unlock (t=0)")
ax2.set_ylabel("cumulative net ($)")
ax2.legend(loc="lower right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T058_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T058_example.png")
