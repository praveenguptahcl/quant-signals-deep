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

# ---- SYNTHETIC DATA (seed = stage number 157) ----
rng = np.random.default_rng(157)
n = 120
t = np.arange(n)

cex = 3400.0 * np.exp(np.cumsum(rng.normal(0, 0.0009, n)))
basis = rng.normal(0, 0.0006, n)  # DEX-CEX basis (fraction)
# gap episodes: (bar, quoted basis bp, realized basis bp)
EPISODES = [
    (20, 55, 55, "DEX rich"),
    (45, -48, -48, "DEX cheap"),
    (70, 62, 62, "DEX rich"),
    (88, -40, -40, "DEX cheap"),
    (100, 44, 44, "DEX rich"),
    (112, 38, 25, "DEX cheap, gap faded mid-fill"),
]
for bar, qbp, rbp, _ in EPISODES:
    basis[bar] += qbp / 1e4
dex = cex * (1 + basis)
basis_bp = basis * 1e4

NOTIONAL = 25_000.0
POOL_FEE = 0.0005 * NOTIONAL   # 5 bp Uniswap v3 0.05% tier (example)
GAS_USD = 8.0                 # per round trip (example)
CEX_TAKER = 0.00075 * NOTIONAL  # 7.5 bp (example)
GATE_BP = 35.0                # example entry gate

print("T057 T4 numbers (seed 157):")
trades = []
cum = 0.0
for bar, qbp, rbp, note in EPISODES:
    slip_bp = 5.0 if rbp == qbp else 10.0
    slip = slip_bp / 1e4 * NOTIONAL
    gross = abs(rbp) / 1e4 * NOTIONAL
    costs = POOL_FEE + GAS_USD + CEX_TAKER + slip
    net = gross - costs
    cum += net
    trades.append((bar, qbp, rbp, net, note))
    side = "sell DEX / buy CEX" if qbp > 0 else "buy DEX / sell CEX"
    print(f"  bar {bar}: {side}; quoted {qbp}bp realized {rbp}bp; gross ${gross:.2f} "
          f"costs ${costs:.2f} (pool ${POOL_FEE:.2f} gas ${GAS_USD:.2f} cex ${CEX_TAKER:.2f} slip ${slip:.2f}) "
          f"NET ${net:+.2f} [{note}]")
print(f"  TOTAL NET ${cum:+.2f} over {len(EPISODES)} round trips")

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})

ax1.plot(t, basis_bp, color=PALETTE["price"], lw=1.5, label="DEX-CEX basis (bp, synthetic)")
ax1.axhline(GATE_BP, color=PALETTE["signal"], ls="--", lw=1, label="entry gate ±35 bp (example)")
ax1.axhline(-GATE_BP, color=PALETTE["signal"], ls="--", lw=1)
ax1.axhline(0, color=PALETTE["zero"], lw=0.8)
for (bar, qbp, rbp, net, note) in trades:
    col = PALETTE["profit"] if net > 0 else PALETTE["loss"]
    ax1.scatter([bar], [qbp], s=90, marker="D", color=col, zorder=5,
                edgecolors="white", linewidths=0.8)
    ax1.annotate(f"{qbp:+.0f}bp\n${net:+.0f}", xy=(bar, qbp),
                 xytext=(6, 12 if qbp > 0 else -26), textcoords="offset points",
                 fontsize=7.5, color=col, weight="bold")
ax1.set_ylabel("basis (bp)")
ax1.set_title("T057 — DEX–CEX Price Gap Arbitrage: synthetic basis round trips")
ax1.legend(loc="upper right", fontsize=8)

run = np.zeros(n)
s = 0.0
fills = {bar: net for (bar, _, _, net, _) in trades}
for bar in range(n):
    s += fills.get(bar, 0.0)
    run[bar] = s
ax2.step(t, run, where="post", color=PALETTE["profit"], lw=1.8, label="cumulative net P&L ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("5-min bar (synthetic)")
ax2.legend(loc="upper left", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T057_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T057_example.png")
