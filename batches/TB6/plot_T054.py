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

# ---- SYNTHETIC DATA (seed = stage number 154) ----
rng = np.random.default_rng(154)
n = 60
t = np.arange(n)
# depeg shock: gaussian dip centered at bar 34, depth ~3.5 cents
dip = 0.035 * np.exp(-0.5 * ((t - 34) / 10) ** 2)
noise = rng.normal(0, 0.0012, n)
price = 1.0 - dip + noise
price[0] = 1.0000

# trade plan (bars) — same numbers used in the T4 worked example
BUY_BARS = [22, 30, 36]
SELL_BAR = 55
QTY = 10_000          # STBL per tranche
FEE = 0.001           # 10 bp taker per side (example)

buy_px = price[BUY_BARS]
sell_px = price[SELL_BAR]

buy_cost = QTY * buy_px
buy_fee = FEE * buy_cost
sell_proceeds = QTY * sell_px
sell_fee = FEE * sell_proceeds
tranche_net = (sell_proceeds - buy_cost) - buy_fee - sell_fee
total_net = tranche_net.sum()
gross = (sell_proceeds - buy_cost).sum()

print("T054 T4 numbers (seed 154):")
for i, b in enumerate(BUY_BARS):
    print(f"  buy{i+1}: bar {b} px {buy_px[i]:.4f} cost ${buy_cost[i]:,.2f} fee ${buy_fee[i]:.2f}")
print(f"  sell: bar {SELL_BAR} px {sell_px:.4f} proceeds ${sell_proceeds.sum():,.2f} fees ${sell_fee.sum():.2f}")
print(f"  per-tranche net: {[f'${v:,.2f}' for v in tranche_net]}")
print(f"  gross ${gross:,.2f} total net ${total_net:,.2f}")

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 1]})

ax1.plot(t, price, color=PALETTE["price"], lw=1.8, label="STBL/USD (synthetic)")
ax1.axhline(1.0, color=PALETTE["zero"], ls="--", lw=1, label="peg $1.00")
ax1.axhspan(0.960, 0.990, color=PALETTE["band"], alpha=0.35, label="dip-buy zone (example)")
ax1.scatter(BUY_BARS, buy_px, s=90, marker="^", color=PALETTE["profit"],
            zorder=5, label="buy tranche (10k STBL)")
ax1.scatter([SELL_BAR], [sell_px], s=110, marker="v", color=PALETTE["signal"],
            zorder=5, label="exit all (30k STBL)")
for i, b in enumerate(BUY_BARS):
    ax1.annotate(f"buy @ {buy_px[i]:.4f}\nnet ${tranche_net[i]:,.0f}",
                 xy=(b, buy_px[i]), xytext=(8, 18), textcoords="offset points",
                 fontsize=8, color=PALETTE["profit"],
                 arrowprops=dict(arrowstyle="->", color=PALETTE["profit"], lw=1))
ax1.annotate(f"sell @ {sell_px:.4f}\nTOTAL NET ${total_net:,.2f}",
             xy=(SELL_BAR, sell_px), xytext=(-95, -32), textcoords="offset points",
             fontsize=8, color=PALETTE["signal"], weight="bold",
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"], lw=1))
ax1.set_ylabel("price (USD)")
ax1.set_title("T054 — Stablecoin Peg-Depeg Guard: synthetic depeg dip-buy timeline")
ax1.legend(loc="lower left", fontsize=8)

# cumulative net P&L (fees realized at fills; MTM ignored — cash accounting)
cum = np.zeros(n)
running = 0.0
bi = 0
for bar in range(n):
    if bar in BUY_BARS:
        running -= buy_fee[bi]
        bi += 1
    if bar == SELL_BAR:
        running += gross - sell_fee.sum()
    cum[bar] = running
ax2.step(t, cum, where="post", color=PALETTE["profit"], lw=1.8, label="cumulative net P&L ($)")
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
plt.savefig("images/T054_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T054_example.png")
