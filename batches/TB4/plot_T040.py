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

# ---- SYNTHETIC DATA (seed = stage number 140) ----
rng = np.random.default_rng(140)
COST_BP_ONE_WAY = 0.0005  # 5 bp one-way on notional per leg turn (example)

# Residual trades: legs = (side, shares, px_in, px_out); S080 s-score path marked per trade
trades = [
    dict(name="T1", s_in=-1.52, s_out=-0.31,
         legs=[("+", 2222, 45.00, 45.55), ("-", 2000, 50.00, 49.90)],
         entry_snap=10, exit_snap=30,
         entry_note="long 2222 AAA @ 45.00 / short 2000 BBB @ 50.00 (s=-1.52)",
         exit_note="conv @ s=-0.31: 45.55 / 49.90"),
    dict(name="T2", s_in=+1.61, s_out=+0.28,
         legs=[("-", 2000, 50.00, 49.72), ("+", 2000, 50.00, 50.06)],
         entry_snap=50, exit_snap=75,
         entry_note="short 2000 CCC @ 50.00 / long 2000 BBB @ 50.00 (s=+1.61)",
         exit_note="conv @ s=+0.28: 49.72 / 50.06"),
    dict(name="T3", s_in=-1.44, s_out=-4.20,
         legs=[("+", 2500, 40.00, 39.78), ("-", 2500, 40.00, 40.06)],
         entry_snap=100, exit_snap=120,
         entry_note="long 2500 DDD @ 40.00 / short 2500 EEE @ 40.00 (s=-1.44)",
         exit_note="STOP @ s=-4.2: 39.78 / 40.06"),
]

for t in trades:
    gross = sum(n * (pxo - pxi) * (1 if side == "+" else -1)
                for side, n, pxi, pxo in t["legs"])
    fees = sum(COST_BP_ONE_WAY * n * (pxi + pxo) for _, n, pxi, pxo in t["legs"])
    t["gross"] = gross
    t["fees"] = fees
    t["net"] = gross - fees

print("T040 synthetic trade table (seed 140):")
cum = 0.0
for t in trades:
    cum += t["net"]
    print(f"  {t['name']}: s {t['s_in']:+.2f}->{t['s_out']:+.2f}, "
          f"gross={t['gross']:+.2f} fees=-{t['fees']:.2f} net={t['net']:+.2f} cum={cum:+.2f}")
print(f"  total net = {cum:+.2f}")
cum_vals = np.cumsum([t["net"] for t in trades])

# Synthetic s-score path (daily bars, 140 bars) passing through trade anchors
N = 140
anchors = {0: 0.0, 10: -1.52, 20: -0.90, 30: -0.31, 50: 1.61, 62: 0.80,
           75: 0.28, 90: -0.60, 100: -1.44, 110: -2.60, 120: -4.20, 139: -2.00}
xs = sorted(anchors)
s = np.zeros(N)
for i in range(N):
    for a, b in zip(xs[:-1], xs[1:]):
        if a <= i <= b:
            w = (i - a) / (b - a) if b > a else 0.0
            s[i] = anchors[a] * (1 - w) + anchors[b] * w
            break
s = s + rng.normal(0, 0.12, N)
for k, v in anchors.items():
    s[k] = v

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [3, 2]})
bars = np.arange(N)
ax1.plot(bars, s, color=PALETTE["price"], lw=1.2,
         label="residual s-score (synthetic, one name at a time)")
for lev, ls, lab in [(1.25, "--", "entry |s| = 1.25"), (0.5, "-.", "exit |s| = 0.5")]:
    ax1.axhline(lev, color=PALETTE["signal"], ls=ls, lw=0.9, label=f"+{lab}")
    ax1.axhline(-lev, color=PALETTE["signal"], ls=ls, lw=0.9, label=f"-{lab}")
ax1.axhline(4, color=PALETTE["loss"], ls=":", lw=0.9, label="+stop |s| = 4")
ax1.axhline(-4, color=PALETTE["loss"], ls=":", lw=0.9, label="-stop |s| = 4")
ax1.axhline(0, color=PALETTE["zero"], lw=0.8)
for t in trades:
    col = PALETTE["profit"] if t["net"] > 0 else PALETTE["loss"]
    ax1.scatter(t["entry_snap"], t["s_in"], color=PALETTE["signal"],
                marker="v", s=70, zorder=5)
    ax1.scatter(t["exit_snap"], t["s_out"], color=col, marker="^", s=70, zorder=5)
    ax1.annotate(f"{t['name']} in\n(s={t['s_in']:+.2f})", (t["entry_snap"], t["s_in"]),
                 fontsize=7, xytext=(6, 12 if t["s_in"] > 0 else -30),
                 textcoords="offset points")
    ax1.annotate(f"{t['name']} out\n(s={t['s_out']:+.2f})", (t["exit_snap"], t["s_out"]),
                 fontsize=7, xytext=(6, 10 if t["s_out"] > 0 else -30),
                 textcoords="offset points")
ax1.set_ylabel("s-score")
ax1.set_xlabel("synthetic daily bars (one residual at a time)")
ax1.legend(loc="lower left", ncol=3, fontsize=8)

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
ax2.set_xlabel("synthetic daily bars")

fig.suptitle("T040 — PCA Eigenportfolio Residual Reversal: s-score path + cumulative net P&L (synthetic)",
             fontsize=12, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T040_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T040_example.png")
