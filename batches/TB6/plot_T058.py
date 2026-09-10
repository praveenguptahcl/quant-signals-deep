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

# ---- T058 worked-example numbers (seed 158, synthetic) ----
rng = np.random.default_rng(158)
days = np.arange(0, 21)  # day 0 = entry, day 20 = exit

# Daily GROSS P&L of the long-single-stock / short-index dispersion book ($)
# (gamma capture from idiosyncratic moves minus index theta, delta-hedged daily)
gross_daily = np.round(rng.normal(1500, 5000, 20)).astype(int)
# Daily delta-hedge slippage ($)
hedge_slip = np.round(rng.uniform(60, 180, 20)).astype(int)

ENTRY_COST = 10890.0  # spread cross (500*$0.15 + 100*$0.30)*100 contracts = $10,500 + commissions 600*$0.65 = $390
EXIT_COST = 10890.0   # symmetric unwind

net_daily = gross_daily - hedge_slip
cum_net = np.zeros(21)
cum_net[0] = -ENTRY_COST
for d in range(1, 21):
    cum_net[d] = cum_net[d - 1] + net_daily[d - 1]
cum_net[20] -= EXIT_COST
trade_net = cum_net[20]

print("T058 synthetic trade (seed 158)")
print(f"entry cost ${ENTRY_COST:.2f}, exit cost ${EXIT_COST:.2f}")
for d in range(1, 21):
    print(f"day {d:2d}: gross {gross_daily[d-1]:7d}  hedge-slip {hedge_slip[d-1]:4d}  net {net_daily[d-1]:7d}  cum {cum_net[d]:9.0f}")
print(f"TRADE NET: ${trade_net:,.2f}")

fig, ax = plt.subplots()
ax.plot(days, cum_net, color=PALETTE["price"], lw=2, label="Cumulative net P&L ($)")
ax.axhline(0, color=PALETTE["zero"], lw=1)
ax.scatter([0], [cum_net[0]], color=PALETTE["signal"], s=70, zorder=5,
           label="Entry day 0 (spread 0.16 > k=0.10, VRP gate pass)")
ax.scatter([20], [cum_net[20]], color=PALETTE["signal2"], s=70, zorder=5,
           label="Exit day 20 (signal-flip: spread 0.03 < 0.05)")
ax.annotate(f"Trade net\n${trade_net:,.0f}", xy=(20, cum_net[20]),
            xytext=(13, cum_net[20] + 4000),
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
            fontsize=10, weight="bold", color=PALETTE["profit"] if trade_net > 0 else PALETTE["loss"])
ax.set_title("T058 — Dispersion Trader: 20-day synthetic dispersion trade, cumulative net P&L")
ax.set_xlabel("Trading day (day 0 = entry, day 20 = signal-flip exit)")
ax.set_ylabel("Cumulative net P&L ($)")
ax.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T058_example.png", bbox_inches="tight")
plt.close()
print("saved images/T058_example.png")
