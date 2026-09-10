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

# ---- T059 worked-example numbers (seed 159, synthetic) ----
# 10 synthetic news events; gate: |s|>=0.50, |r1m|>=15bp, sign match, RVOL>=2.0, spread<=3 ticks
rng = np.random.default_rng(159)
s_vals   = np.round(rng.uniform(-0.80, 0.80, 10), 2)
r1m_vals = np.round(rng.uniform(-45, 45, 10), 1)      # first-minute return, bp
rvol_vals = np.round(rng.uniform(1.0, 6.0, 10), 1)
spr_vals  = rng.integers(1, 6, 10)                    # quoted spread, ticks
tickers = ["ABC", "DEF", "GHI", "JKL", "MNO", "PQR", "STU", "VWX", "YZA", "BCD"]

FEE = 0.0008  # $ per share per side
events = []
cum = 0.0
print("T059 synthetic events (seed 159)")
print("#  tkr   s     r1m  RVOL spr  trade side  shares   entry     exit      gross      fees     net")
for i in range(10):
    s, r1m, rvol, spr = s_vals[i], r1m_vals[i], rvol_vals[i], spr_vals[i]
    trade = (abs(s) >= 0.50 and abs(r1m) >= 15 and np.sign(r1m) == np.sign(s)
             and rvol >= 2.0 and spr <= 3)
    if trade:
        side = +1 if s > 0 else -1
        shares = int(round(25000 * abs(s) * min(1.0, abs(r1m) / 40.0) / 100.0) * 100)
        slip_in = round(float(rng.uniform(0.01, 0.05)), 3)   # entry slippage vs decision mid, $
        slip_out = round(float(rng.uniform(0.005, 0.03)), 3)
        entry = round(100.0 + side * 0.0, 3)                 # decision mid normalized to 100.00
        drift_bp = round(float(rng.normal(6 if s > 0 else 6, 18)), 1)  # hold return, bp (signed by side)
        exitp = round(entry + side * drift_bp / 100.0, 3)
        gross = round(side * shares * (exitp - entry), 2)
        fees = round(shares * 2 * FEE, 2)
        net = round(gross - fees, 2)
    else:
        side, shares, entry, exitp, gross, fees, net = 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0
    cum += net
    events.append((i + 1, tickers[i], s, r1m, rvol, spr, trade, side, shares, entry, exitp, gross, fees, net, cum))
    print(f"{i+1:2d} {tickers[i]:3s} {s:+.2f} {r1m:+6.1f} {rvol:4.1f} {spr:3d}  "
          f"{'Y' if trade else 'N':>5} {'+' if side>0 else '-' if side<0 else ' ':>4} {shares:7d} "
          f"{entry:8.3f} {exitp:8.3f} {gross:9.2f} {fees:7.2f} {net:9.2f}  cum {cum:9.2f}")
print(f"TOTAL NET: ${cum:,.2f}")

nums = [e[0] for e in events]
nets = np.array([e[13] for e in events])
cums = np.array([e[14] for e in events])
colors = [PALETTE["profit"] if v > 0 else PALETTE["loss"] if v < 0 else PALETTE["volume"] for v in nets]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1], "hspace": 0.08})
ax1.plot(nums, cums, color=PALETTE["price"], lw=2, marker="o", ms=5, label="Cumulative net P&L ($)")
for e in events:
    n, tkr, s, r1m, rvol, spr, trade, side, shares, entry, exitp, gross, fees, net, c = e
    marker = "o" if trade else "x"
    mc = (PALETTE["profit"] if net > 0 else PALETTE["loss"] if net < 0 else PALETTE["volume"])
    ax1.scatter([n], [c], color=mc, s=55, zorder=5, marker=marker)
    if trade:
        ax1.annotate(f"${net:,.0f}", xy=(n, c), xytext=(0, 10), textcoords="offset points",
                     ha="center", fontsize=8, weight="bold", color=mc)
ax1.axhline(0, color=PALETTE["zero"], lw=1)
ax1.set_title("T059 — News-Sentiment First-Minute Momentum: 10 synthetic events, cumulative net P&L")
ax1.set_ylabel("Cum. net P&L ($)")
ax1.legend(loc="upper left")
ax1.text(0.98, 0.06, f"Total net ${cum:,.0f}", transform=ax1.transAxes, ha="right",
         fontsize=11, weight="bold", color=PALETTE["profit"] if cum > 0 else PALETTE["loss"])

ax2.bar(nums, nets, color=colors)
ax2.set_xlabel("Synthetic event # (1–10)")
ax2.set_ylabel("Net/event ($)")
ax2.set_xticks(nums)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T059_example.png", bbox_inches="tight")
plt.close()
print("saved images/T059_example.png")
