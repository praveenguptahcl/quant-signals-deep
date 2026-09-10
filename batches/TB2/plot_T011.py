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

# ---- SYNTHETIC DATA (seed 111; same numbers as T011.md T4 table) ----
# Five synthetic intraday reversal trades, liquid large-cap XYZ, $100 scale,
# quoted spread $0.02 (2 bps). Entry: passive limit buy at the bid after a
# mid-price liquidity-shock impulse (sell-initiated). Exits per T2 rules.
# trade: (label, entry_bid, exit_price, exit_side, shares, commission_RT)
rng = np.random.default_rng(111)
trades = [
    ("T1",  99.91,  99.99, "ask", 1000, 11.00, "70% recovery"),
    ("T2",  99.84,  99.87, "bid", 1000, 11.00, "time stop"),
    ("T3",  99.79,  99.74, "bid", 1000, 11.00, "stop (new extreme)"),
    ("T4", 100.11, 100.11, "bid",  500,  6.00, "time stop (scratch)"),
    ("T5",  99.66,  99.73, "ask", 1000, 11.00, "80% recovery"),
]

rows = []
for label, entry, exitp, side, shares, comm, why in trades:
    gross = (exitp - entry) * shares
    slip = 0.005 * shares if side == "bid" else 0.0   # 0.5-tick aggressive-exit slippage
    net = gross - comm - slip
    rows.append(dict(label=label, entry=entry, exit=exitp, side=side,
                     shares=shares, comm=comm, slip=slip, gross=gross, net=net, why=why))
nets = np.array([r["net"] for r in rows])
cum = np.cumsum(nets)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=False,
                               gridspec_kw={"height_ratios": [3, 2]})
fig.suptitle("T011 — Short-Term Reversal + Bounce Timing: five synthetic reversal trades\n"
             "with entry/exit markers and cumulative net P&L", fontweight="bold")

# Top: synthetic tick path per trade window, anchored to the fixed entry/exit prices.
xs_all, ps_all = [], []
offset = 0
gap = 12
entry_ticks, exit_ticks, entry_ps, exit_ps = [], [], [], []
for r in rows:
    n = 80
    mid_entry = r["entry"] + 0.01
    mid_exit = r["exit"] - 0.01 if r["side"] == "ask" else r["exit"] + 0.01
    impulse = 0.07 if r["label"] != "T4" else 0.05
    pre = mid_entry + impulse + 0.01
    t_in = np.arange(10)
    seg_in = pre + (mid_entry - pre) * t_in / 9 + rng.normal(0, 0.003, 10)
    seg_in[-1] = mid_entry
    t_out = np.arange(n - 10)
    seg_out = mid_entry + (mid_exit - mid_entry) * np.minimum(t_out / max(len(t_out) - 1, 1), 1) ** 0.9
    seg_out = seg_out + rng.normal(0, 0.0025, len(t_out))
    seg_out[-1] = mid_exit
    xs = np.arange(offset, offset + n)
    ps = np.concatenate([seg_in, seg_out])
    xs_all.append(xs); ps_all.append(ps)
    entry_ticks.append(offset + 10); exit_ticks.append(offset + n - 1)
    entry_ps.append(r["entry"]); exit_ps.append(r["exit"])
    offset += n + gap
for xs, ps in zip(xs_all, ps_all):
    ax1.plot(xs, ps, color=PALETTE["price"], lw=1.1)
ax1.scatter(entry_ticks, entry_ps, marker="^", s=70, color=PALETTE["profit"],
            zorder=5, label="entry (limit buy at bid)")
ax1.scatter(exit_ticks, exit_ps, marker="v", s=70, color=PALETTE["signal"],
            zorder=5, label="exit")
for r, et, xp, xt in zip(rows, entry_ticks, exit_ps, exit_ticks):
    ax1.annotate(f'{r["label"]}\n${r["net"]:+.0f}',
                 xy=(xt, xp), xytext=(6, 14), textcoords="offset points",
                 fontsize=8, color=PALETTE["profit"] if r["net"] >= 0 else PALETTE["loss"],
                 weight="bold",
                 arrowprops=dict(arrowstyle="-", color="#7f8c8d", lw=0.8))
ax1.set_ylabel("price ($)")
ax1.set_title("Synthetic tick path per trade window (seed 111)", fontsize=11)
ax1.legend(loc="upper left")
ax1.set_xlim(0, offset)

# Bottom: cumulative net P&L steps with per-trade annotations.
xbar = np.arange(len(rows))
colors = [PALETTE["profit"] if v >= 0 else PALETTE["loss"] for v in nets]
ax2.bar(xbar, nets, color=colors, alpha=0.85, edgecolor=PALETTE["zero"], lw=0.6)
ax2.plot(xbar, cum, color=PALETTE["price"], marker="o", ms=5, lw=1.6,
         label="cumulative net P&L")
for i, (r, c) in enumerate(zip(rows, cum)):
    ax2.annotate(f'${r["net"]:+.0f}\n(cum ${c:+.0f})', xy=(i, r["net"]),
                 xytext=(0, 12 if r["net"] >= 0 else -22), textcoords="offset points",
                 ha="center", fontsize=8,
                 color=PALETTE["profit"] if r["net"] >= 0 else PALETTE["loss"], weight="bold")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_xticks(xbar); ax2.set_xticklabels([r["label"] for r in rows])
ax2.set_ylabel("P&L ($, net of costs)")
ax2.set_xlabel("synthetic trade")
ax2.legend(loc="upper left")
ax2.set_title("Per-trade net P&L and cumulative P&L", fontsize=11)

print("T011 trade check (seed 111):")
for r in rows:
    print(f'  {r["label"]}: entry {r["entry"]:.2f} exit {r["exit"]:.2f} x{r["shares"]} '
          f'gross {r["gross"]:+.2f} comm {r["comm"]:.2f} slip {r["slip"]:.2f} net {r["net"]:+.2f} ({r["why"]})')
print(f'  TOTAL net: {cum[-1]:+.2f}')

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T011_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
