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

# ---- SYNTHETIC DATA (seed = stage number 139) ----
rng = np.random.default_rng(139)
COST_BP_ONE_WAY = 0.0005  # 5 bp one-way on notional per equity leg turn (example)
FUT_FEE = 0.75            # $/contract round trip (indicative)

# Micro index futures: $5/pt (MES-class spec, real contract spec)
# legs: ("eq", side, shares, px_in, px_out) or ("fut", side, contracts, px_in, px_out)
trades = [
    dict(name="T1", prem_in=-10.2, prem_out=-3.1,
         rvol=2.6, block_imb=+0.55,
         legs=[("eq", "+", 1000, 120.44, 120.72), ("fut", "-", 4, 6000.00, 6001.20)],
         entry_snap=20, exit_snap=55,
         entry_note="long 1000 SYNETF @ 120.44 / short 4 MXF @ 6000.00",
         exit_note="sell @ 120.72 / cover @ 6001.20 (conv)"),
    dict(name="T2", prem_in=+9.1, prem_out=+2.8,
         rvol=2.2, block_imb=-0.48,
         legs=[("eq", "-", 800, 121.10, 120.86), ("fut", "+", 3, 6010.00, 6011.50)],
         entry_snap=90, exit_snap=130,
         entry_note="short 800 SYNETF @ 121.10 / long 3 MXF @ 6010.00",
         exit_note="cover @ 120.86 / sell @ 6011.50 (conv)"),
    dict(name="T3", prem_in=-9.4, prem_out=-14.2,
         rvol=2.4, block_imb=+0.41,
         legs=[("eq", "+", 900, 119.80, 119.52), ("fut", "-", 4, 5990.00, 5991.60)],
         entry_snap=160, exit_snap=195,
         entry_note="long 900 SYNETF @ 119.80 / short 4 MXF @ 5990.00",
         exit_note="STOP @ -14bps: sell @ 119.52 / cover @ 5991.60"),
]

for t in trades:
    gross = 0.0
    fees = 0.0
    for kind, side, n, pxi, pxo in t["legs"]:
        if kind == "eq":
            gross += n * (pxo - pxi) * (1 if side == "+" else -1)
            fees += COST_BP_ONE_WAY * n * (pxi + pxo)
        else:
            gross += n * 5 * (pxo - pxi) * (1 if side == "+" else -1)
            fees += FUT_FEE * n
    t["gross"] = gross
    t["fees"] = fees
    t["net"] = gross - fees

print("T039 synthetic trade table (seed 139):")
cum = 0.0
for t in trades:
    cum += t["net"]
    print(f"  {t['name']}: prem {t['prem_in']:+.1f}->{t['prem_out']:+.1f} bps, "
          f"RVOL={t['rvol']}, BlockImb={t['block_imb']:+.2f}, "
          f"gross={t['gross']:+.2f} fees=-{t['fees']:.2f} net={t['net']:+.2f} cum={cum:+.2f}")
print(f"  total net = {cum:+.2f}")
cum_vals = np.cumsum([t["net"] for t in trades])

# Synthetic premium/discount path (bps) over 215 1-min snapshots
N = 215
anchors = {0: -3.0, 20: -10.2, 55: -3.1, 90: 9.1, 130: 2.8, 160: -9.4, 195: -14.2, 214: -8.0}
xs = sorted(anchors)
prem = np.zeros(N)
for i in range(N):
    for a, b in zip(xs[:-1], xs[1:]):
        if a <= i <= b:
            w = (i - a) / (b - a) if b > a else 0.0
            prem[i] = anchors[a] * (1 - w) + anchors[b] * w
            break
prem = prem + rng.normal(0, 0.5, N)
for k, v in anchors.items():
    prem[k] = v

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [3, 2]})
snaps = np.arange(N)
ax1.plot(snaps, prem, color=PALETTE["price"], lw=1.2,
         label="SYNETF premium/discount (bps, synthetic)")
ax1.axhline(8, color=PALETTE["signal"], ls="--", lw=0.9, label="entry |prem| = 8 bps")
ax1.axhline(-8, color=PALETTE["signal"], ls="--", lw=0.9)
ax1.axhline(4, color=PALETTE["signal2"], ls="-.", lw=0.9, label="exit |prem| = 4 bps")
ax1.axhline(-4, color=PALETTE["signal2"], ls="-.", lw=0.9)
ax1.axhline(-14, color=PALETTE["loss"], ls=":", lw=0.9, label="stop -14 bps")
ax1.axhline(0, color=PALETTE["zero"], lw=0.8)
for t in trades:
    col = PALETTE["profit"] if t["net"] > 0 else PALETTE["loss"]
    ax1.scatter(t["entry_snap"], t["prem_in"], color=PALETTE["signal"],
                marker="v", s=70, zorder=5)
    ax1.scatter(t["exit_snap"], t["prem_out"], color=col, marker="^", s=70, zorder=5)
    ax1.annotate(f"{t['name']} in\n(RVOL {t['rvol']}, blk {t['block_imb']:+.2f})",
                 (t["entry_snap"], t["prem_in"]), fontsize=7,
                 xytext=(6, -30 if t["prem_in"] < 0 else 14), textcoords="offset points")
    ax1.annotate(f"{t['name']} out", (t["exit_snap"], t["prem_out"]), fontsize=7,
                 xytext=(6, 10), textcoords="offset points")
ax1.set_ylabel("premium / discount (bps)")
ax1.set_xlabel("synthetic 1-min snapshots")
ax1.legend(loc="lower left", ncol=2, fontsize=8)

ax2.step([0] + [t["exit_snap"] for t in trades],
         [0.0] + list(cum_vals), where="post", color=PALETTE["price"], lw=1.6,
         label="cumulative net P&L ($)")
for t, cv in zip(trades, cum_vals):
    ax2.annotate(f"{t['name']}: {t['net']:+.2f}",
                 (t["exit_snap"], cv), fontsize=8,
                 xytext=(0, 12 if t["net"] > 0 else -18),
                 textcoords="offset points", ha="center",
                 color=PALETTE["profit"] if t["net"] > 0 else PALETTE["loss"],
                 weight="bold")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("cumulative net P&L ($)")
ax2.set_xlabel("synthetic 1-min snapshots")

fig.suptitle("T039 — ETF Creation/Redemption Flow Trader: premium timeline + cumulative net P&L (synthetic)",
             fontsize=12, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T039_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T039_example.png")
