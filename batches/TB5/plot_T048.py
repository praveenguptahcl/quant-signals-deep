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

# ---- SYNTHETIC WORKED EXAMPLE: T048 put/call-ratio contrarian (seed 148) ----
# Chapter text and chart MUST agree: both are generated from these arrays.
rng = np.random.default_rng(148)

days = np.arange(10)
# Synthetic 10-session close path for fictional large-cap "XLQ" (~$100 scale)
closes = 100.0 + np.cumsum(rng.normal(0, 0.9, 10))
closes[0] = 100.0
closes[2] = 97.10   # engineered selloff into the put-panic extreme
closes[3] = 98.40
closes[7] = 101.60  # engineered melt-up into the call-euphoria extreme
closes[8] = 100.20
closes[9] = 101.85  # engineered continuation: the T2 short fade loses (honest illustration)
closes = np.round(closes, 2)

# Synthetic signal reads (chapter: S072 PCR z, S045 stretched-move z, S097 sentiment z)
pcr_z   = np.array([0.4, 1.1, 2.6, 0.7, -0.3, -0.9, -1.4, -2.3, 0.2, 0.1])  # S072
s045_z  = np.array([-0.5, -1.2, -2.4, -0.6, 0.4, 1.1, 1.6, 2.1, 0.3, -0.2])  # S045
sent_z  = np.array([0.1, 0.9, -2.4, 0.5, -0.2, -0.8, -1.2, 2.1, 0.0, 0.3])  # S097 composite (bearish-negative / bullish-positive)

print("Day | close | PCR z | S045 z | sent z")
for d in days:
    print(f"{d:3d} | {closes[d]:6.2f} | {pcr_z[d]:5.1f} | {s045_z[d]:6.1f} | {sent_z[d]:6.1f}")

# Strategy rule (example thresholds): enter at NEXT OPEN (t+1), fade PCR extreme
# only if S045 stretched in the same direction (|z|>=2.0) and sentiment agrees
# (z97 bearish-negative at put panic, bullish-positive at call euphoria).
# Trade 1 (long fade of put panic): signal day 2 -> enter open day 3, exit at PCR normalization.
# Trade 2 (short fade of call euphoria): signal day 7 -> enter open day 8, exit at PCR normalization.
trades = [
    {"dir": +1, "sig_day": 2, "entry": closes[3], "exit": closes[5],
     "note": "long fade of put-panic (PCR z=+2.6, 96th pct)"},
    {"dir": -1, "sig_day": 7, "entry": closes[8], "exit": closes[9],
     "note": "short fade of call-euphoria (PCR z=-2.3, 6th pct)"},
]
shares = 500
cost_rt = shares * 0.005 * 2 + shares * 0.01 * 2  # $0.005/sh fee + 1bp (~$0.01/sh on $100 stock) each way (example)

net_total = 0.0
print("\nTrades (line-by-line net P&L):")
for i, t in enumerate(trades, 1):
    gross = t["dir"] * shares * (t["exit"] - t["entry"])
    net = gross - cost_rt
    net_total += net
    print(f"T{i}: {t['note']}\n"
          f"    {'long' if t['dir']>0 else 'short'} {shares} @ {t['entry']:.2f} -> "
          f"{t['exit']:.2f}: gross {gross:+.2f}, costs {cost_rt:.2f}, NET {net:+.2f}")
print(f"Session total NET: {net_total:+.2f}")

# ---- PLOT: price path with entry/exit markers + per-trade net P&L, cumulative P&L ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
ax1.plot(days, closes, color=PALETTE["price"], marker="o", ms=4,
         label="XLQ close (synthetic $)")
nets = []
for i, t in enumerate(trades, 1):
    e_day = t["sig_day"] + 1
    x_day = e_day + (2 if i == 1 else 1)
    gross = t["dir"] * shares * (t["exit"] - t["entry"])
    net = gross - cost_rt
    nets.append(net)
    ax1.annotate("", xy=(e_day, t["entry"]), xytext=(e_day - 0.35, t["entry"] + (1.5 if i == 1 else -1.5)),
                 arrowprops=dict(arrowstyle="->", color=PALETTE["profit"] if i == 1 else PALETTE["loss"], lw=2))
    ax1.text(e_day - 0.35, t["entry"] + (1.5 if i == 1 else -1.5),
             f"T{i} {'long' if t['dir'] > 0 else 'short'} @ {t['entry']:.2f}",
             color=PALETTE["profit"] if i == 1 else PALETTE["loss"], fontsize=9, va="center")
    ax1.plot(x_day, t["exit"], marker="X", ms=10,
             color=PALETTE["profit"] if net > 0 else PALETTE["loss"])
    ax1.text(x_day + 0.08, t["exit"], f"exit {t['exit']:.2f}\nnet {net:+.2f}",
             fontsize=8, va="center",
             color=PALETTE["profit"] if net > 0 else PALETTE["loss"])
ax1.set_ylabel("Price ($)")
ax1.legend(loc="best")
ax1.set_title("T048 — Put/Call Ratio Contrarian: 10-day synthetic fade scenario")

cum = np.cumsum(nets)
bars = ax2.bar([1, 2], nets, tick_label=[f"T1\n{nets[0]:+.2f}", f"T2\n{nets[1]:+.2f}"],
               color=[PALETTE["profit"] if n > 0 else PALETTE["loss"] for n in nets])
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.set_ylabel("Net P&L ($)")
ax2.set_xlabel("Trade (synthetic)")
ax2.text(1.5, max(nets) * 0.6, f"cumulative net {net_total:+.2f}", ha="center", fontsize=10,
         bbox=dict(boxstyle="round", fc=PALETTE["band"], ec=PALETTE["price"]))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T048_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("\nSaved images/T048_example.png")
