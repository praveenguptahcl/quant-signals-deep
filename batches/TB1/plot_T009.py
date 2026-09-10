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

# ---- SYNTHETIC DATA (seed = stage number 109) ----
rng = np.random.default_rng(109)
N = 200  # 15-second snapshots
# Hand-anchored premium/discount (bps) path; anchors exact after noise.
anchors = {0: -4.0, 30: -9.9, 70: -0.9, 110: -6.0, 140: -10.0, 175: -15.6, 199: -8.0}
xs = sorted(anchors)
prem = np.zeros(N)
for i in range(N):
    for a, b in zip(xs[:-1], xs[1:]):
        if a <= i <= b:
            w = (i - a) / (b - a) if b > a else 0.0
            prem[i] = anchors[a] * (1 - w) + anchors[b] * w
            break
prem = prem + rng.normal(0, 0.6, N)
for k, v in anchors.items():
    prem[k] = v

ETF_FEE = 0.01   # $/share round trip
MES_FEE = 0.75   # $/contract round trip (indicative)

trades = [
    dict(name="T1", entry_snap=30, exit_snap=70,
         entry_prem=-9.9, exit_prem=-0.9,
         desc="discount convergence: long ETF, short MES hedge",
         entry_note="long 666 ETF @ 500.76 / short 10 MES @ 7000.50",
         exit_note="sell 666 ETF @ 501.20 / cover 10 MES @ 7001.00",
         n_etf=666, n_mes=10,
         etf=666 * (501.20 - 500.76),
         mes=10 * 5 * (7000.50 - 7001.00)),
    dict(name="T2", entry_snap=140, exit_snap=175,
         entry_prem=-10.0, exit_prem=-15.6,
         desc="discount widens: stop at -14 bps",
         entry_note="long 666 ETF @ 500.76 / short 10 MES @ 7000.50",
         exit_note="sell 666 ETF @ 500.46 / cover 10 MES @ 7000.75",
         n_etf=666, n_mes=10,
         etf=666 * (500.46 - 500.76),
         mes=10 * 5 * (7000.50 - 7000.75)),
]
for t in trades:
    t["gross"] = t["etf"] + t["mes"]
    t["fees"] = t["n_etf"] * ETF_FEE + t["n_mes"] * MES_FEE
    t["net"] = t["gross"] - t["fees"]

print("T009 synthetic trade table (seed 109):")
cum = 0.0
for t in trades:
    cum += t["net"]
    print(f"  {t['name']}: ETF leg={t['etf']:+.2f} MES leg={t['mes']:+.2f} "
          f"gross={t['gross']:+.2f} fees=-{t['fees']:.2f} net={t['net']:+.2f} cum={cum:+.2f}")
print(f"  total net = {cum:+.2f}")
cum_vals = np.cumsum([t["net"] for t in trades])

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [3, 2]})
snaps = np.arange(N)
ax1.plot(snaps, prem, color=PALETTE["price"], lw=1.2, label="ETF premium/discount (bps, synthetic)")
ax1.axhline(-8, color=PALETTE["signal"], ls="--", lw=0.9, label="entry |prem| = 8 bps")
ax1.axhline(8, color=PALETTE["signal"], ls="--", lw=0.9)
ax1.axhline(-4, color=PALETTE["signal2"], ls="-.", lw=0.9, label="exit |prem| = 4 bps")
ax1.axhline(4, color=PALETTE["signal2"], ls="-.", lw=0.9)
ax1.axhline(-14, color=PALETTE["loss"], ls=":", lw=0.9, label="stop -14 bps")
ax1.axhline(0, color=PALETTE["zero"], lw=0.8)
for t in trades:
    ax1.scatter(t["entry_snap"], t["entry_prem"], color=PALETTE["signal"],
                marker="v", s=70, zorder=5)
    ax1.scatter(t["exit_snap"], t["exit_prem"],
                color=PALETTE["profit"] if t["net"] > 0 else PALETTE["loss"],
                marker="^", s=70, zorder=5)
    ax1.annotate(f"{t['name']} entry\n{t['entry_note']}",
                 (t["entry_snap"], t["entry_prem"]), fontsize=7,
                 xytext=(6, -26), textcoords="offset points")
    ax1.annotate(f"{t['name']} exit\n{t['exit_note']}",
                 (t["exit_snap"], t["exit_prem"]), fontsize=7,
                 xytext=(6, 12), textcoords="offset points")
ax1.set_ylabel("premium / discount (bps)")
ax1.set_xlabel("15-second snapshot index (synthetic)")
ax1.legend(loc="lower left", ncol=2)

ax2.step([0] + [t["exit_snap"] for t in trades],
         [0.0] + list(cum_vals), where="post", color=PALETTE["price"], lw=1.6,
         label="cumulative net P&L ($)")
for t, cv in zip(trades, cum_vals):
    ax2.annotate(f"{t['name']}: {t['net']:+.2f}",
                 (t["exit_snap"], cv), fontsize=8,
                 xytext=(0, 10 if t["net"] > 0 else -16),
                 textcoords="offset points", ha="center",
                 color=PALETTE["profit"] if t["net"] > 0 else PALETTE["loss"],
                 weight="bold")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("cumulative net P&L ($)")
ax2.set_xlabel("15-second snapshot index (synthetic)")

fig.suptitle("T009 — ETF-vs-Basket Arbitrage: premium/discount timeline + cumulative net P&L (synthetic)",
             fontsize=13, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T009_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T009_example.png")
