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

# ---- T036 synthetic scenario (seed 136 == stage number) ----
rng = np.random.default_rng(136)
N = 60  # 1-minute bars, synthetic session
rf = rng.normal(0, 0.0009, N)          # leader (futures) 1-min returns
rs = np.zeros(N)                       # laggard (spot) 1-min returns: 3-min delay
rs[3:] = 1.0 * rf[:-3] + rng.normal(0, 0.0003, N - 3)

pf = 100 * np.exp(np.cumsum(rf))        # leader level (index)
ps = 100 * np.exp(np.cumsum(rs))        # laggard level (index)

# lead-lag grid scan (1-min resolution, integer lags; ell>0 => futures lead)
lags = np.arange(-5, 6)
def xc(lag):
    a = rs[10:55]
    b = rf[10 - lag:55 - lag]
    return np.corrcoef(a, b)[0, 1]
rhos = np.array([xc(l) for l in lags])
lhat = int(lags[np.argmax(np.abs(rhos))])
rho_hat = float(rhos[np.argmax(np.abs(rhos))])

# S060 entry: |3-min leader move| >= 10 bps (example cost filter c); trade laggard at t+1
LEAD_WIN, COST_C = 3, 0.0010
MAX_HOLD = 10      # minutes (example), time stop 30
NOTIONAL, RT_BP = 500_000.0, 0.0006   # $500k; 6 bp round-trip = $300
trades, cum, busy_until = [], 0.0, -1
for t in range(10, N - MAX_HOLD - 2):
    if t < busy_until:
        continue
    move = float(np.sum(rf[t - LEAD_WIN + 1:t + 1]))
    if abs(move) >= COST_C:
        d = 1 if move > 0 else -1
        epx, exx = t + 1, t + 1 + MAX_HOLD
        gross = d * (ps[exx] - ps[epx]) / ps[epx] * NOTIONAL
        net = gross - RT_BP * NOTIONAL
        cum += net
        trades.append(dict(entry=t + 1, exit=exx, d=d, lead_move=move,
                           epx=ps[epx], exx=ps[exx], gross=gross, net=net, cum=cum))
        busy_until = exx

print(f"lhat={lhat} min rho_hat={rho_hat:.3f}")
print(f"#trades={len(trades)}")
for i, tr in enumerate(trades, 1):
    print(f"trade{i}: dir={'LONG' if tr['d']>0 else 'SHORT'} entry_min={tr['entry']} "
          f"lead_move={tr['lead_move']*10000:.1f}bps px_in={tr['epx']:.4f} px_out={tr['exx']:.4f} "
          f"gross=${tr['gross']:,.2f} net=${tr['net']:,.2f}")
tot_gross = sum(t['gross'] for t in trades)
tot_net = sum(t['net'] for t in trades)
print(f"total gross=${tot_gross:,.2f} costs=${RT_BP*NOTIONAL*len(trades):,.2f} net=${tot_net:,.2f}")

mins = np.arange(N)
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True)
ax1.plot(mins, (pf / pf[0] - 1) * 10000, color=PALETTE["signal"], lw=1.6,
         label="leader: futures cum. return (bps)")
ax1.plot(mins, (ps / ps[0] - 1) * 10000, color=PALETTE["price"], lw=1.6,
         label="laggard: spot cum. return (bps)")
for i, tr in enumerate(trades, 1):
    col = PALETTE["profit"] if tr['d'] > 0 else PALETTE["loss"]
    ax1.scatter([tr['entry']], [(ps[tr['entry']] / ps[0] - 1) * 10000], color=col, s=70, zorder=5)
    ax1.annotate(f"#{i} {'L' if tr['d']>0 else 'S'}", xy=(tr['entry'], (ps[tr['entry']] / ps[0] - 1) * 10000),
                 xytext=(4, 8), textcoords="offset points", fontsize=9, color=col, weight="bold")
    ax1.scatter([tr['exit']], [(ps[tr['exit']] / ps[0] - 1) * 10000], color=col, s=70,
                marker="x", zorder=5)
ax1.set_ylabel("bps")
ax1.legend(loc="upper left")
ax1.set_title(f"T036 — Cross-Asset Lead-Lag (Hayashi-Yoshida): synthetic 60-min session "
              f"(HY lag {lhat} min, rho={rho_hat:.2f})")

stepx, stepy = [0], [0.0]
for tr in trades:
    stepx += [tr['entry'], tr['exit'], tr['exit']]
    prev = stepy[-1]
    stepy += [prev, prev, prev + tr['net']]
ax2.step(stepx, stepy, where="post", color=PALETTE["profit"], lw=2, label="cumulative net P&L ($)")
for i, tr in enumerate(trades, 1):
    ax2.annotate(f"#{i} ${tr['net']:,.0f}", xy=(tr['exit'], tr['cum']),
                 xytext=(6, 6), textcoords="offset points", fontsize=9,
                 color=PALETTE["profit"] if tr['net'] > 0 else PALETTE["loss"], weight="bold")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("net P&L ($)")
ax2.set_xlabel("minute (synthetic)")
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T036_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
