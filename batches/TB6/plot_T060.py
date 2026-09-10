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

# ---- T060 worked-example data (MUST match T4 text exactly) ----
rng = np.random.default_rng(160)  # seed stated in T4
par = 1.00
days = np.arange(0, 6)
# anchors: (day, wUSD price) — hand-set; seeded noise keeps anchors exact
anchors = {0: 0.9600, 1: 0.9120, 2: 0.9050, 3: 0.8700, 4: 0.9400, 5: 1.0000}
base = np.interp(days, list(anchors.keys()), list(anchors.values()))
noise = rng.normal(0, 0.004, len(days))
noise[list(anchors.keys())] = 0.0
wusd = base + noise
redeem_fee = 0.005   # 0.5% redemption haircut (example)
swap_fee = 0.003     # 0.3% DEX swap fee per side (example)

# Trade T1: buy 50k wUSD @ 0.9120 (day 1), redeem day 5 at par minus haircut
t1 = dict(label="T1 buy 50k", day=1, qty=50000, entry=0.9120, exit_day=5)
t1_buy = t1["qty"] * t1["entry"]
t1_recv = t1["qty"] * par * (1 - redeem_fee)
t1_net = t1_recv - t1_buy * (1 + swap_fee) - 25.00 - 40.00  # bridge fee + gas (example)
print(f"{t1['label']}: buy {t1_buy:.2f}$ recv {t1_recv:.2f}$ NET {t1_net:+.2f}$")
# Trade T2: buy 5k @ 0.9050 (day 2), stop 0.8700 (day 3)
t2 = dict(label="T2 buy 5k", day=2, qty=5000, entry=0.9050, exit=0.8700, exit_day=3)
t2_net = t2["qty"] * (t2["exit"] * (1 - swap_fee) - t2["entry"] * (1 + swap_fee))
print(f"{t2['label']}: entry {t2['entry']:.4f} exit {t2['exit']:.4f} NET {t2_net:+.2f}$")
print(f"TOTAL NET {t1_net + t2_net:+.2f}$")

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, height_ratios=[3, 2])
ax1.axhline(par, color=PALETTE["zero"], lw=1.5, ls="-", label="native par ($1.00)")
ax1.fill_between(days, wusd, par, alpha=0.25, color=PALETTE["band"], label="reported discount")
ax1.plot(days, wusd, color=PALETTE["price"], lw=2, label="wUSD synthetic price ($)")
for t, n, px in [(t1, t1_net, 0.9120), (t2, t2_net, 0.9050)]:
    ax1.scatter([t["day"]], [t["entry"]], s=90, marker="^", color=PALETTE["profit"],
                zorder=5, edgecolors="k")
    ex, exd = (par * (1 - redeem_fee), 5) if t is t1 else (t["exit"], 3)
    ax1.scatter([exd], [ex], s=90, marker="v",
                color=PALETTE["profit"] if n > 0 else PALETTE["loss"],
                zorder=5, edgecolors="k")
    ax1.annotate(f"{t['label']}\nnet {n:+.2f}$", xy=(exd, ex),
                 xytext=(10, 14 if n > 0 else -22), textcoords="offset points",
                 fontsize=8, color=PALETTE["profit"] if n > 0 else PALETTE["loss"],
                 arrowprops=dict(arrowstyle="->",
                                 color=PALETTE["profit"] if n > 0 else PALETTE["loss"], lw=1))
ax1.set_ylabel("price ($)")
ax1.legend(loc="lower right")
ax1.set_title("T060 — Cross-Chain Bridge Flow Arbitrage: synthetic wrapped-asset discount & net P&L")

cum = np.array([0, t2_net, t1_net + t2_net])
ax2.step([0, 3, 5], cum, where="post", color=PALETTE["price"], lw=2,
         label="cumulative net P&L ($)")
ax2.fill_between([0, 3, 5], cum, 0, step="post", alpha=0.25, color=PALETTE["profit"])
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.set_xlabel("days since bridge stress (t=0)")
ax2.set_ylabel("cumulative net ($)")
ax2.legend(loc="lower right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T060_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T060_example.png")
