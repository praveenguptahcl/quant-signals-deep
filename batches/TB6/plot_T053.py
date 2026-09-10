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

rng = np.random.default_rng(153)  # seed = stage number

# ---- synthetic 8-bar regime posteriors (SYNTHETIC; same numbers as T4) ----
lat = np.array([1, 1, 1, -1, -1, -1, 1, 1])          # designed latent regime (M,M,M,R,R,R,M,M)
jitter = (rng.uniform(0, 1, 8) - 0.5) * 0.20         # seed-driven jitter, +/-10pp
pi = np.clip(0.50 + 0.42 * lat + jitter, 0.02, 0.98)

# ---- allocation: soft blend with dead zone (example tau), vol target (example lambda=1) ----
TAU = 0.65                       # example dead-zone parameter
wM = np.clip((pi - (1 - TAU)) / (2 * TAU - 1), 0, 1)
wR = 1 - wM
NAV = 1_000_000                  # example NAV ($)
COST_BPS = 2.7                   # round-trip cost in bp (example)

# synthetic bar returns (%) — fixed toy design
r = np.array([1.2, -0.6, -1.8, -1.6, 0.9, -1.1, 1.3, 0.5]) / 100

print(" t     piM     wM     wR    N_M       N_R")
for t in range(8):
    print(f"{t}  {pi[t]:.4f} {wM[t]:.4f} {wR[t]:.4f}  {wM[t]*NAV:9.0f}  {wR[t]*NAV:9.0f}")

# ---- sleeve trades (example toy rules from T4) ----
# momentum book (S025-style): up-day >= +0.75% -> long next bar
# reversal book (S035-style): |return| >= 1.5% -> fade next bar
# a sleeve trade fires only if its book's allocator weight > 0 (hard example gate)
trades = []
vetoes = []
events = [  # (entry_bar t, book, side, holds_bar)
    (0, "MOM", +1, 1), (2, "REV", +1, 3), (3, "REV", +1, 4), (4, "MOM", +1, 5), (6, "MOM", +1, 7),
]
for t, book, side, hb in events:
    w = wM[t] if book == "MOM" else wR[t]
    if w <= 0:
        vetoes.append((t, book, r[hb]))
        continue
    N = w * NAV
    gross = side * N * r[hb]
    cost = N * COST_BPS / 1e4
    net = gross - cost
    trades.append((t, book, hb, N, r[hb], gross, cost, net))

eq = 0.0
for (t, book, hb, N, ret, gross, cost, net) in trades:
    eq += net
    print(f"{book} entry t={t} (hold bar {hb}): N {N:9.0f} ret {ret*1e4:+5.1f}bp "
          f"gross {gross:+9.2f} cost {cost:6.2f} net {net:+9.2f}")
for (t, book, ret) in vetoes:
    print(f"VETOED: {book} entry t={t} (w=0) — counterfactual hold-bar ret {ret*1e4:+5.1f}bp")
print("total net:", round(eq, 2))

# ---- chart: posterior + allocation (top), combined equity (bottom) ----
fig, ax = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                       gridspec_kw={"height_ratios": [3, 2]})
t_ax = np.arange(8)
ax[0].bar(t_ax, pi, color=PALETTE["band"], edgecolor=PALETTE["price"], alpha=0.9,
          label="π^M (HMM momentum posterior, S079)")
ax[0].step(t_ax, wM, where="mid", color=PALETTE["signal"], lw=2.2,
           label="w^M allocator weight (dead-zone blend)")
ax[0].step(t_ax, wR, where="mid", color=PALETTE["signal2"], lw=2.2, ls="--",
           label="w^R allocator weight")
ax[0].set_ylim(0, 1.05)
ax[0].set_ylabel("probability / weight")
ax[0].set_title("T053 — HMM Regime-Switching Allocator: posterior, sleeve weights, net P&L")
ax[0].legend(loc="upper right")

hold_bars = [hb for (t, book, hb, N, ret, g, c, nn) in trades]
nets = [nn for (t, book, hb, N, ret, g, c, nn) in trades]
cum = np.concatenate([[0.0], np.cumsum(nets)])
ax[1].step([0] + hold_bars, cum, where="post", color=PALETTE["price"], lw=1.8,
           label="combined book net P&L ($)")
ax[1].axhline(0, color=PALETTE["zero"], lw=1)
for i, ((t, book, hb, N, ret, g, c, nn)) in enumerate(trades, start=1):
    ax[1].annotate(f"{book}\n${nn:+.0f}", xy=(hb, cum[i]),
                   xytext=(6, 12 if nn > 0 else -24), textcoords="offset points",
                   fontsize=8, color=PALETTE["profit"] if nn > 0 else PALETTE["loss"],
                   fontweight="bold")
for (t, book, ret) in vetoes:
    ax[1].annotate(f"{book} veto", xy=(t, cum[-1]), xytext=(0, 14),
                   textcoords="offset points", fontsize=8, color=PALETTE["volume"],
                   ha="center")
ax[1].set_xlabel("bar")
ax[1].set_ylabel("net P&L ($)")
ax[1].legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T053_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T053_example.png")
