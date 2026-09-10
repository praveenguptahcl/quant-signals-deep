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

# ---- SYNTHETIC DATA (seed = stage number 138) ----
rng = np.random.default_rng(138)
COST_BP_ONE_WAY = 0.0005  # 5 bp one-way on notional per leg turn (example)

# Trades: (name, legs=[(side, shares, px_in, px_out)], entry_snap, exit_snap, note)
trades = [
    dict(name="T1", sleeve="sector momentum",
         legs=[("+", 800, 100.00, 100.28)],
         entry_snap=5, exit_snap=30,
         entry_note="long 800 XLK @ 100.00 (top sector, 12:00 rank)",
         exit_note="sell 800 XLK @ 100.28 (15:55 flatten)"),
    dict(name="T2", sleeve="idiosyncratic fade (winner)",
         legs=[("+", 500, 50.00, 50.18), ("-", 300, 80.00, 79.90)],
         entry_snap=8, exit_snap=38,
         entry_note="long 500 AAA @ 50.00 (z=-1.6) / short 300 BBB @ 80.00 (z=+1.9)",
         exit_note="exit both @ z->0.2 (conv): 50.18 / 79.90"),
    dict(name="T3", sleeve="idiosyncratic fade (stop)",
         legs=[("+", 400, 60.00, 59.88), ("-", 250, 90.00, 90.14)],
         entry_snap=45, exit_snap=60,
         entry_note="long 400 CCC @ 60.00 (z=-1.7) / short 250 DDD @ 90.00 (z=+1.8)",
         exit_note="STOP |z|>=2.5: 59.88 / 90.14"),
]

for t in trades:
    gross = sum(s * (pxo - pxi) * (1 if side == "+" else -1)
                for side, s, pxi, pxo in t["legs"])
    costs = sum(COST_BP_ONE_WAY * s * (pxi + pxo) for _, s, pxi, pxo in t["legs"])
    t["gross"] = gross
    t["fees"] = costs
    t["net"] = gross - costs

print("T038 synthetic trade table (seed 138):")
cum = 0.0
for t in trades:
    cum += t["net"]
    print(f"  {t['name']}: gross={t['gross']:+.2f} costs=-{t['fees']:.2f} "
          f"net={t['net']:+.2f} cum={cum:+.2f}")
print(f"  total net = {cum:+.2f}")
cum_vals = np.cumsum([t["net"] for t in trades])

# Synthetic residual z-score paths for the fade sleeve (1-min bars, 70 bars)
N = 70
# negative-z series (AAA / CCC candidates)
anchors_neg = {0: 0.0, 8: -1.60, 20: -0.70, 38: -0.20, 45: -1.70, 52: -2.20, 60: -2.80, 69: -1.50}
# positive-z series (BBB / DDD candidates)
anchors_pos = {0: 0.0, 8: 1.90, 20: 0.90, 38: 0.20, 45: 1.80, 52: 2.30, 60: 2.90, 69: 1.60}

def interp(anchors):
    xs = sorted(anchors)
    y = np.zeros(N)
    for i in range(N):
        for a, b in zip(xs[:-1], xs[1:]):
            if a <= i <= b:
                w = (i - a) / (b - a) if b > a else 0.0
                y[i] = anchors[a] * (1 - w) + anchors[b] * w
                break
    return y

z_neg = interp(anchors_neg) + rng.normal(0, 0.12, N)
z_pos = interp(anchors_pos) + rng.normal(0, 0.12, N)
for k, v in anchors_neg.items():
    z_neg[k] = v
for k, v in anchors_pos.items():
    z_pos[k] = v

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [3, 2]})
bars = np.arange(N)
ax1.plot(bars, z_neg, color=PALETTE["price"], lw=1.2, label="z (long-fade names AAA/CCC)")
ax1.plot(bars, z_pos, color=PALETTE["signal2"], lw=1.2, label="z (short-fade names BBB/DDD)")
for lev, ls, lab in [(1.5, "--", "entry |z| = 1.5"), (2.5, ":", "stop |z| = 2.5")]:
    ax1.axhline(lev, color=PALETTE["signal"], ls=ls, lw=0.9, label=f"+{lab}")
    ax1.axhline(-lev, color=PALETTE["signal"], ls=ls, lw=0.9, label=f"-{lab}")
ax1.axhline(0, color=PALETTE["zero"], lw=0.8)
# T2 markers (bars 8 / 38)
for s, z, mk, col in [(8, -1.60, "v", PALETTE["signal"]), (8, 1.90, "v", PALETTE["signal"])]:
    ax1.scatter(s, z, color=col, marker=mk, s=70, zorder=5)
for s, z, mk, col in [(38, -0.20, "^", PALETTE["profit"]), (38, 0.20, "^", PALETTE["profit"])]:
    ax1.scatter(s, z, color=col, marker=mk, s=70, zorder=5)
# T3 markers (bars 45 / 60)
for s, z in [(45, -1.70), (45, 1.80)]:
    ax1.scatter(s, z, color=PALETTE["signal"], marker="v", s=70, zorder=5)
for s, z in [(60, -2.80), (60, 2.90)]:
    ax1.scatter(s, z, color=PALETTE["loss"], marker="^", s=70, zorder=5)
ax1.annotate("T2 entry", (8, 1.90), fontsize=7, xytext=(4, 10),
             textcoords="offset points")
ax1.annotate("T2 exit (conv)", (38, 0.20), fontsize=7, xytext=(4, 10),
             textcoords="offset points")
ax1.annotate("T3 entry", (45, 1.80), fontsize=7, xytext=(4, 10),
             textcoords="offset points")
ax1.annotate("T3 STOP", (60, 2.90), fontsize=7, xytext=(4, 10),
             textcoords="offset points", color=PALETTE["loss"], weight="bold")
ax1.set_ylabel("residual z-score")
ax1.set_xlabel("synthetic 1-min bars (fade sleeve)")
ax1.legend(loc="lower left", ncol=2, fontsize=8)
ax1.set_title("T1 (sector momentum sleeve): long 800 XLK 12:00→15:55 — see P&L panel below",
              fontsize=9, color=PALETTE["zero"])

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
ax2.set_xlabel("synthetic 1-min bars")

fig.suptitle("T038 — Sector Momentum + Idiosyncratic Fade: residual z paths + cumulative net P&L (synthetic)",
             fontsize=12, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T038_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T038_example.png")
