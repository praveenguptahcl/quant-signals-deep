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

rng = np.random.default_rng(92)  # seed 92; events below are fixed, script regenerates exactly

# ---- S092 worked-example events (fixed synthetic tape; outcomes illustrative, NOT a backtest) ----
# columns: time, jump %, jump z, news? (1=yes/0=no), news text, action, next-60min %
events = [
    ("10:04", +1.8, +4.2, 1, "earnings headline 10:03", "FOLLOW long",  +0.6),
    ("10:41", -2.1, -4.8, 0, "none",                   "FADE (buy)",   +0.9),
    ("11:15", +1.5, +3.6, 1, "analyst upgrade 11:12",  "FOLLOW long",  -0.2),
    ("13:02", +2.4, +5.1, 0, "none",                   "FADE (short)", -1.1),
    ("14:20", -1.6, -3.8, 1, "FDA headline 14:18",     "FOLLOW short", +0.3),
    ("15:30", +1.9, +4.4, 0, "none",                   "FADE (short)", -0.7),
]
NOTIONAL = 10_000.0
ALLIN_BPS = 5.0  # example: 2 spread + 1 fees + 2 slippage, round-trip
cost = NOTIONAL * ALLIN_BPS / 10_000

labels, jumps, nxt, news = [], [], [], []
total_net = 0.0
for t, j, z, nw, txt, act, r in events:
    labels.append(f"{t}\n{act}")
    jumps.append(j); nxt.append(r); news.append(nw)
    # trade P&L: sign depends on follow vs fade and jump direction
    if "FOLLOW" in act:
        pnl_dir = np.sign(j) * np.sign(r)   # +1 if drift continued in jump direction
    else:  # FADE: position opposite the jump
        pnl_dir = -np.sign(j) * np.sign(r)  # +1 if move reversed
    gross = NOTIONAL * abs(r) / 100 * pnl_dir
    net = gross - cost
    total_net += net
    print(f"{t}: jump {j:+.1f}% (z={z:+.1f}) news={'YES' if nw else 'no '} -> {act:13s} "
          f"next-60m {r:+.1f}% gross=${gross:+.0f} net=${net:+.0f}")
print(f"all-in cost/event=${cost:.2f}; total synthetic net=${total_net:+.0f} (illustrative only)")

x = np.arange(len(events))
w = 0.36
ax = plt.gca()
ax.bar(x - w / 2, jumps, w, label="jump (5-min %)", color=PALETTE["volume"])
colors = [PALETTE["price"] if n else PALETTE["signal2"] for n in news]
bars = ax.bar(x + w / 2, nxt, w, label="next-60min return %", color=colors)
ax.axhline(0, color=PALETTE["zero"], linewidth=1)
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=8)
ax.set_xlabel("synthetic jump event (time, action taken)")
ax.set_ylabel("return (%)")
ax.set_title("S092 — Identified-news vs no-news drift: 6 synthetic jump events")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(facecolor=PALETTE["price"], label="news-backed → follow"),
                   Patch(facecolor=PALETTE["signal2"], label="no-news → fade"),
                   Patch(facecolor=PALETTE["volume"], label="initial jump")],
          loc="upper left", fontsize=8)
for i, r in enumerate(nxt):
    ax.text(i + w / 2, r + (0.12 if r >= 0 else -0.16), f"{r:+.1f}%", ha="center", fontsize=8,
            weight="bold", color=colors[i])
ax.text(0.98, 0.96, "outcomes illustrative — not a backtest",
        transform=ax.transAxes, ha="right", va="top", fontsize=9,
        color=PALETTE["loss"], style="italic",
        bbox=dict(boxstyle="round", fc="white", ec=PALETTE["loss"]))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S092_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S092_example.png")
