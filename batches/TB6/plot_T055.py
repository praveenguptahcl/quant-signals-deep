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

# ---- SYNTHETIC DATA (seed = stage number 155) ----
rng = np.random.default_rng(155)
n = 96
t = np.arange(n)

# piecewise drift so the intended barrier outcomes occur (noise on top)
drift = np.zeros(n)
drift[10:23] = -0.00125   # post-alert-1 slide ~ -1.5%
drift[23:55] = 0.00045    # chop back up
drift[55:64] = 0.00135    # post-alert-3 rally ~ +1.2% (hits stop)
drift[64:75] = -0.0006
drift[75:91] = -0.00028   # post-alert-4 gentle slide ~ -0.45%
noise = rng.normal(0, 0.0018, n)
price = 67000.0 * np.exp(np.cumsum(drift + noise))

ALERTS = [
    # (bar, confirmed, p_hat, qty_btc, note)
    (10, True, 0.68, 2.0, "A1 confirmed"),
    (30, False, 0.48, 0.0, "A2 vetoed"),
    (55, True, 0.63, 2.0, "A3 confirmed"),
    (75, True, 0.55, 1.0, "A4 confirmed (half size)"),
]

ATR_PCT = 0.008      # hourly ATR, example
PROFIT_K, STOP_K = 1.5, 1.0
VERT_BARS = 24
TAKER = 0.0005       # 5 bp per side (example)
FUND_8H = 0.0001     # 1 bp per 8h paid by shorts (example)

def resolve(entry_bar, entry_px):
    tp = entry_px * (1 - PROFIT_K * ATR_PCT)
    sl = entry_px * (1 + STOP_K * ATR_PCT)
    for b in range(entry_bar + 1, min(entry_bar + VERT_BARS, n)):
        if price[b] <= tp:
            return b, price[b], "profit barrier"
        if price[b] >= sl:
            return b, price[b], "stop barrier"
    b = min(entry_bar + VERT_BARS, n - 1)
    return b, price[b], "time stop"

print("T055 T4 numbers (seed 155):")
trades = []
cum_net = 0.0
for bar, conf, p_hat, qty, note in ALERTS:
    if not conf or qty == 0:
        print(f"  {note}: bar {bar} BTC ${price[bar]:,.0f} -> VETOED by meta-model (p-hat {p_hat:.2f} < 0.55), no trade")
        continue
    epx = price[bar]
    xb, xpx, how = resolve(bar, epx)
    hours = xb - bar
    gross = (epx - xpx) * qty
    fees = TAKER * qty * (epx + xpx)
    funding = FUND_8H * (hours / 8.0) * qty * epx
    net = gross - fees - funding
    cum_net += net
    trades.append((bar, xb, epx, xpx, qty, net, how))
    print(f"  {note}: short {qty} BTC bar {bar} @ ${epx:,.0f} -> bar {xb} @ ${xpx:,.0f} ({how}); "
          f"gross ${gross:,.2f} fees ${fees:.2f} funding ${funding:.2f} NET ${net:,.2f}")
print(f"  TOTAL NET ${cum_net:,.2f}")

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})

ax1.plot(t, price, color=PALETTE["price"], lw=1.6, label="BTC/USD perp (synthetic)")
for bar, conf, p_hat, qty, note in ALERTS:
    ax1.axvline(bar, color=PALETTE["signal2"], ls=":", lw=1.2)
    ax1.annotate(note, xy=(bar, price[bar]), xytext=(4, 14), textcoords="offset points",
                 fontsize=7.5, color=PALETTE["signal2"])
for (eb, xb, epx, xpx, qty, net, how) in trades:
    ax1.scatter([eb], [epx], s=80, marker="v", color=PALETTE["signal"], zorder=5)
    ax1.scatter([xb], [xpx], s=80, marker="^",
                color=PALETTE["profit"] if net > 0 else PALETTE["loss"], zorder=5)
    ax1.annotate(f"short {qty}g @ ${epx:,.0f}\ncover @ ${xpx:,.0f}\nnet ${net:+,.0f}",
                 xy=(xb, xpx), xytext=(10, -34 if net > 0 else 12),
                 textcoords="offset points", fontsize=7.5,
                 color=PALETTE["profit"] if net > 0 else PALETTE["loss"],
                 arrowprops=dict(arrowstyle="->",
                                 color=PALETTE["profit"] if net > 0 else PALETTE["loss"], lw=1))
ax1.set_ylabel("price (USD)")
ax1.set_title("T055 — On-Chain Whale-Flow Tracker: synthetic whale-alert short timeline")
ax1.legend(["BTC/USD perp (synthetic)", "whale alert (exchange inflow)"],
           loc="upper left", fontsize=8)

run = np.zeros(n)
s = 0.0
exits = {xb: net for (_, xb, _, _, _, net, _) in trades}
for bar in range(n):
    s += exits.get(bar, 0.0)
    run[bar] = s
ax2.step(t, run, where="post", color=PALETTE["profit"], lw=1.8, label="cumulative net P&L ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("hour bar (synthetic)")
ax2.legend(loc="upper left", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T055_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T055_example.png")
