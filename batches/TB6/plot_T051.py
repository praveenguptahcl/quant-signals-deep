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

rng = np.random.default_rng(151)  # seed = stage number

# ---- synthetic 20-bar 5-min mid-price tape (SYNTHETIC; same numbers as T4) ----
n = 20
mu = np.zeros(n); mu[0:7] = 0.003; mu[7:14] = -0.0025; mu[14:20] = 0.0018
sig = 0.0015
rets = mu + sig * rng.standard_normal(n)
px = 250.0 * np.cumprod(1 + rets)

# ---- local-level Kalman filter (S077 machinery); Q/R are example calibrations ----
Q, R = 0.04, 0.64
x, P = px[0], R
xs, Ps, dx = [], [], []
for y in px:
    Pp = P + Q; K = Pp / (Pp + R); xp = x
    x = x + K * (y - x); P = (1 - K) * Pp
    xs.append(x); Ps.append(P); dx.append(x - xp)
xs, Ps, dx = map(np.array, (xs, Ps, dx))

# ---- mechanical trade rule (example thresholds; same rules as T4) ----
TH, MAXH = 0.15, 6            # entry threshold on fair-value velocity; time stop (bars)
PREF = 0.14                    # sizing reference variance (example)
COST_PS = 0.027                # $0.027/share round-trip (spread 2c + fees 0.7c; example)
bars = np.arange(n)
pos, q = 0, 0
entries, exits, trades = [], [], []   # entries: (bar, px, side); exits: (bar, px, side)
net_pnl_per_trade, eq_curve, eq = [], [0.0], 0.0
entry_bar = -99
for t in range(n - 1):
    if pos == 0 and abs(dx[t]) > TH:
        side = 1 if dx[t] > 0 else -1
        q = int(round(500 * np.sqrt(PREF / Ps[t]) / 100) * 100)
        pos, entry_bar = side, t
        entries.append((t + 1, px[t], side, q))
    elif pos != 0:
        flipped = (pos == 1 and dx[t] < 0) or (pos == -1 and dx[t] > 0)
        if flipped or (t - entry_bar) >= MAXH:
            exits.append((t + 1, px[t], pos, q, "flip" if flipped else "time"))
            gross = pos * q * (px[t] - px[entry_bar])
            net = gross - q * COST_PS
            net_pnl_per_trade.append(net); eq += net
            pos = 0
    eq_curve.append(eq)
if pos != 0:  # end of window: flat everything (no overnight carry in the toy)
    exits.append((n - 1, px[n - 1], pos, q, "end"))
    gross = pos * q * (px[n - 1] - px[entry_bar])
    net = gross - q * COST_PS
    net_pnl_per_trade.append(net); eq += net
    pos = 0
eq_curve[-1] = eq  # bar 19 carries the forced flat

print(" t      y        x_hat    P_t|t    d_x")
for t in range(n):
    print(f"{t:2d} {px[t]:8.3f} {xs[t]:8.3f} {Ps[t]:7.4f} {dx[t]:+7.4f}")
print("trades (open_bar, side, q, open_px):")
for (b, p, s, qq) in entries:
    print(f"  open bar {b}: {'LONG' if s > 0 else 'SHORT'} {qq} sh px {p:.4f}")
print("exits (close_bar, px, reason):")
for (b, p, s, qq, why) in exits:
    print(f"  close bar {b} px {p:.4f} ({why})")
print("net per trade:", [round(v, 2) for v in net_pnl_per_trade], "total:", round(eq, 2))

# ---- chart ----
fig, ax = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                       gridspec_kw={"height_ratios": [3, 2]})
t_ax = np.arange(n)
ax[0].plot(t_ax, px, color=PALETTE["price"], lw=1.8, label="mid price (5-min bars)")
ax[0].plot(t_ax, xs, color=PALETTE["signal2"], lw=1.5, ls="--",
           label="Kalman fair value x̂ (S077)")
for (b, p, s, qq) in entries:
    ax[0].scatter([b], [p], s=90, color=PALETTE["profit"] if s > 0 else PALETTE["loss"],
                  marker="^" if s > 0 else "v", zorder=5,
                  label=("long entry" if s > 0 else "short entry"))
for (b, p, s, qq, why) in exits:
    ax[0].scatter([b], [p], s=70, color=PALETTE["zero"], marker="x", zorder=5,
                  label="exit")
# de-duplicate legend entries
handles, labels = ax[0].get_legend_handles_labels()
seen, uh, ul = set(), [], []
for h, l in zip(handles, labels):
    if l not in seen:
        seen.add(l); uh.append(h); ul.append(l)
ax[0].legend(uh, ul, loc="upper left")
ax[0].set_ylabel("price ($)")
ax[0].set_title("T051 — Kalman Fair-Value Trend: price vs fair value with trades")

cum_eq = np.concatenate([[0.0], np.cumsum(net_pnl_per_trade)])
ax[1].step([0] + [b for (b, p, s, qq, why) in exits], cum_eq, where="post",
           color=PALETTE["price"], lw=1.8, label="cumulative net P&L ($)")
ax[1].axhline(0, color=PALETTE["zero"], lw=1)
for i, ((b, p, s, qq, why), v) in enumerate(zip(exits, net_pnl_per_trade), start=1):
    ax[1].annotate(f"${v:+.0f}", xy=(b, cum_eq[i]), xytext=(6, 10 if v > 0 else -14),
                  textcoords="offset points", fontsize=8,
                  color=PALETTE["profit"] if v > 0 else PALETTE["loss"],
                  fontweight="bold")
ax[1].set_xlabel("bar (5-min)")
ax[1].set_ylabel("net P&L ($)")
ax[1].legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T051_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T051_example.png")
