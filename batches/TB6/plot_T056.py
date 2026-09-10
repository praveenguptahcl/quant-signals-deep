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

# ---- SYNTHETIC DATA (seed = stage number 156) ----
rng = np.random.default_rng(156)
n = 120
t = np.arange(n)

# base fee (gwei): baseline ~20 + congestion spikes
fee = 20 + rng.normal(0, 2.5, n)
for c, h, w in [(24, 120, 4), (58, 95, 4), (93, 130, 3)]:
    fee += h * np.exp(-0.5 * ((t - c) / w) ** 2)
fee = np.clip(fee, 5, None)

# activity volume z-score: high at spikes 1-2, dead at spike 3 (veto case)
act = rng.normal(0, 0.5, n)
for c, h, w in [(24, 2.6, 5), (58, 2.1, 5), (93, 0.4, 4)]:
    act += h * np.exp(-0.5 * ((t - c) / w) ** 2)

fee_z = (fee - 20) / 8.0  # z vs diurnal baseline (example normalization)

# ETH: slides after spike 1, rallies after spike 2 (stop), drifts after spike 3
drift = np.zeros(n)
drift[24:36] = -0.0020    # ~ -2.4% washout
drift[58:65] = 0.0014     # ~ +1.0% squeeze (hits stop)
drift[93:110] = 0.0002
eth = 3400.0 * np.exp(np.cumsum(drift + rng.normal(0, 0.0016, n)))

Z_GATE, ACT_GATE = 2.0, 1.5   # example entry gates
QTY = 10.0                    # ETH per trade
TAKER = 0.0005
FUND_8H = 0.0001
STOP_PCT = 0.009              # 0.9% stop (example)

SPIKES = [
    # (bar, note) — meta-model decides
    (24, "spike 1"),
    (58, "spike 2"),
    (93, "spike 3"),
]

print("T056 T4 numbers (seed 156):")
trades = []
cum = 0.0
for bar, note in SPIKES:
    fz, az = fee_z[bar], act[bar]
    ok = (fz > Z_GATE) and (az > ACT_GATE)
    print(f"  {note}: bar {bar} fee_z {fz:.2f} act_z {az:.2f} -> {'TRADE' if ok else 'VETOED (meta-model)'}")
    if not ok:
        continue
    epx = eth[bar]
    sl = epx * (1 + STOP_PCT)
    xb, xpx, how = None, None, "normalization exit"
    for b in range(bar + 1, n):
        if eth[b] >= sl:
            xb, xpx, how = b, sl, "stop 0.9%"
            break
        if fee_z[b] < 0.5 and b > bar + 4:
            xb, xpx, how = b, eth[b], "fee normalized"
            break
    hours = xb - bar
    gross = (epx - xpx) * QTY
    fees = TAKER * QTY * (epx + xpx)
    funding = FUND_8H * (hours / 8.0) * QTY * epx
    net = gross - fees - funding
    cum += net
    trades.append((bar, xb, epx, xpx, net, how))
    print(f"    short {QTY} ETH bar {bar} @ ${epx:,.0f} -> bar {xb} @ ${xpx:,.0f} ({how}); "
          f"gross ${gross:,.2f} fees ${fees:.2f} funding ${funding:.2f} NET ${net:,.2f}")
print(f"  TOTAL NET ${cum:,.2f}")

# ---- PLOT ----
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 5.2), sharex=True,
                                    gridspec_kw={"height_ratios": [1.4, 2, 1]})

ax1.plot(t, fee, color=PALETTE["signal2"], lw=1.4, label="base fee (gwei, synthetic)")
ax1.axhline(20 + 2.0 * 8, color=PALETTE["signal"], ls="--", lw=1, label="z=2.0 gate (~36 gwei)")
ax1.set_ylabel("gwei")
ax1.legend(loc="upper right", fontsize=7.5)

ax2.plot(t, eth, color=PALETTE["price"], lw=1.6, label="ETH/USD perp (synthetic)")
for bar, note in SPIKES:
    ax2.axvline(bar, color=PALETTE["signal2"], ls=":", lw=1.0)
for (eb, xb, epx, xpx, net, how) in trades:
    ax2.scatter([eb], [epx], s=80, marker="v", color=PALETTE["signal"], zorder=5)
    ax2.scatter([xb], [xpx], s=80, marker="^",
                color=PALETTE["profit"] if net > 0 else PALETTE["loss"], zorder=5)
    ax2.annotate(f"short @ ${epx:,.0f}\nexit @ ${xpx:,.0f}\nnet ${net:+,.0f}",
                 xy=(xb, xpx), xytext=(10, -36 if net > 0 else 12),
                 textcoords="offset points", fontsize=7.5,
                 color=PALETTE["profit"] if net > 0 else PALETTE["loss"],
                 arrowprops=dict(arrowstyle="->",
                                 color=PALETTE["profit"] if net > 0 else PALETTE["loss"], lw=1))
ax2.annotate("spike 3 vetoed\nby meta-model", xy=(93, eth[93]), xytext=(-60, 18),
             textcoords="offset points", fontsize=7.5, color=PALETTE["volume"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["volume"], lw=1))
ax2.set_ylabel("price (USD)")
ax2.set_title("T056 — Mempool Congestion Fee-Cycle Trader: synthetic fee-spike fade timeline")
ax2.legend(["ETH/USD perp (synthetic)"], loc="upper left", fontsize=8)

run = np.zeros(n)
s = 0.0
exits = {xb: net for (_, xb, _, _, net, _) in trades}
for bar in range(n):
    s += exits.get(bar, 0.0)
    run[bar] = s
ax3.step(t, run, where="post", color=PALETTE["profit"], lw=1.8, label="cumulative net P&L ($)")
ax3.axhline(0, color=PALETTE["zero"], lw=0.8)
ax3.set_ylabel("net P&L ($)")
ax3.set_xlabel("hour bar (synthetic)")
ax3.legend(loc="upper left", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T056_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T056_example.png")
