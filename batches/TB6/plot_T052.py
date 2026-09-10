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

rng = np.random.default_rng(152)  # seed = stage number

# ---- synthetic 12-bar 1-min tape (SYNTHETIC; same numbers as T4) ----
# three designed events on seed-driven background noise:
#   bar 3: liquidity-driven down-spike (flow-OPPOSED -> traded fade)
#   bar 6: informed jump (flow-CONFIRMED -> vetoed by the VAR gate)
#   bar 8: liquidity-driven up-spike (flow-OPPOSED -> traded fade)
n = 12
r = rng.normal(0, 1.0, n)
r[3] = -9.0; r[6] = 6.5; r[8] = 7.8      # returns in bp
P0 = 250.00
px = P0 * np.cumprod(1 + r / 1e4)

# signed flow (toy stand-in for the S084 VAR check); event bars fixed by design
flow = np.where(rng.uniform(0, 1, n) > 0.5, 1, -1)
flow[3] = +1    # return -9bp, flow +: opposed
flow[6] = +1    # return +6.5bp, flow +: confirmed
flow[8] = -1    # return +7.8bp, flow -: opposed

# ---- AR(1) innovation signal (S078 machinery); example parameters ----
PHI, SIG_E = 0.15, 3.0      # AR coefficient, innovation scale (bp)
Z_ENTRY, MAXH = 2.0, 5       # entry |z| threshold (example); time stop (bars)
Q_SH = 800                   # shares per trade (example)
COST_PS = 0.027              # $/share round-trip (example)

eps = np.zeros(n); z = np.zeros(n)
for t in range(1, n):
    eps[t] = r[t] - PHI * r[t - 1]
    z[t] = eps[t] / SIG_E

pos, q = 0, 0
entries, exits, net_trades, reasons = [], [], [], []
eq = 0.0
for t in range(1, n - 1):
    fired = False
    if pos == 0 and abs(z[t]) > Z_ENTRY:
        side = -1 if z[t] > 0 else 1          # fade the innovation
        if np.sign(flow[t]) == np.sign(r[t]):
            reasons.append(("veto", t))       # VAR-gate stand-in: flow confirms move
        else:
            pos, q, fired = side, Q_SH, True
            entries.append((t + 1, px[t], side))
    elif pos != 0:
        crossed = (pos == 1 and z[t] > 0) or (pos == -1 and z[t] < 0)
        held = t - entry_t
        if crossed or held >= MAXH:
            exits.append((t + 1, px[t], pos, q, "zero-cross" if crossed else "time"))
            gross = pos * q * (px[t] - px[entry_t])
            net = gross - q * COST_PS
            net_trades.append(net); eq += net
            pos = 0
    if fired:
        entry_t = t

print(" t    r(bp)  innov   z      flow  action")
cum = 0.0
vi = 0
for t in range(n):
    tag = ""
    if t < len(entries) + 0:
        pass
    print(f"{t:2d} {r[t]:+7.2f} {eps[t]:+7.2f} {z[t]:+6.2f}  {'buy' if flow[t] > 0 else 'sell'}")
print("entries:", [(b, "LONG" if s > 0 else "SHORT", p) for (b, p, s) in entries])
print("exits:", [(b, p, why) for (b, p, s, qq, why) in exits])
print("vetoes:", reasons)
print("net per trade:", [v for v in net_trades], "total:", eq)
# counterfactual: what the vetoed bar-6 fade would have done (short @ bar7 open, exit at z sign flip)
zb = z[7]
print(f"counterfactual vetoed trade: short @ bar7 open {px[6]}, z[7]={zb:+.3f} -> exit bar8 open {px[7]}")
g_cf = -Q_SH * (px[7] - px[6])
print(f"  gross {g_cf:.2f}, net after costs {g_cf - Q_SH*COST_PS:.2f}")

# ---- chart: innovation z timeline with entries/exits + net equity ----
fig, ax = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                       gridspec_kw={"height_ratios": [3, 2]})
t_ax = np.arange(n)
ax[0].bar(t_ax, z, color=[PALETTE["signal2"] if abs(v) <= Z_ENTRY
                          else (PALETTE["loss"] if v > 0 else PALETTE["profit"])
                          for v in z], alpha=0.85, label="innovation z-score (S078)")
ax[0].axhline(Z_ENTRY, color=PALETTE["loss"], ls="--", lw=1, label="entry |z| = 2.0 (example)")
ax[0].axhline(-Z_ENTRY, color=PALETTE["loss"], ls="--", lw=1)
ax[0].axhline(0, color=PALETTE["zero"], lw=1)
for (b, p, s) in entries:
    ax[0].annotate("ENTER " + ("LONG" if s > 0 else "SHORT"),
                   xy=(b - 1, z[b - 1]), xytext=(4, 16 if z[b - 1] < 0 else -22),
                   textcoords="offset points", fontsize=8, fontweight="bold",
                   color=PALETTE["profit"] if s > 0 else PALETTE["loss"],
                   arrowprops=dict(arrowstyle="->", color="black", lw=0.8))
for (kind, t) in reasons:
    ax[0].annotate("VAR GATE VETO", xy=(t, z[t]), xytext=(4, 14),
                   textcoords="offset points", fontsize=8, fontweight="bold",
                   color=PALETTE["zero"])
for (b, p, s, qq, why) in exits:
    ax[0].annotate("EXIT", xy=(b - 1, z[b - 1]), xytext=(4, -20),
                   textcoords="offset points", fontsize=8,
                   arrowprops=dict(arrowstyle="->", color="black", lw=0.8))
ax[0].set_ylabel("innovation z-score")
ax[0].set_title("T052 — AR/ARMA Innovation Trader: innovation z with trades and VAR-gate veto")
ax[0].legend(loc="upper right")

cum_eq = np.concatenate([[0.0], np.cumsum(net_trades)])
ax[1].step([0] + [b for (b, p, s, qq, why) in exits], cum_eq, where="post",
           color=PALETTE["price"], lw=1.8, label="cumulative net P&L ($)")
ax[1].axhline(0, color=PALETTE["zero"], lw=1)
for i, ((b, p, s, qq, why), v) in enumerate(zip(exits, net_trades), start=1):
    ax[1].annotate(f"${v:+.2f}", xy=(b, cum_eq[i]), xytext=(6, 10 if v > 0 else -16),
                  textcoords="offset points", fontsize=8,
                  color=PALETTE["profit"] if v > 0 else PALETTE["loss"],
                  fontweight="bold")
ax[1].set_xlabel("bar (1-min)")
ax[1].set_ylabel("net P&L ($)")
ax[1].legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T052_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T052_example.png")
