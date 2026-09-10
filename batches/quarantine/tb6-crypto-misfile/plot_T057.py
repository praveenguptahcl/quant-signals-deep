import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
import os

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

os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# synthetic fractional-differentiation memory trade walk, seed = stage number
rng = np.random.default_rng(157)

D_FRAC = 0.40         # differentiation order (example)
TAU = 0.001           # truncation tolerance (example)
COST_GATE_BP = 2.5    # skip trades whose |forecast| < gate (example)
HALF_SPREAD_BP = 1.25
FEE_SHARE = 0.005
SHARES = 1000
P0 = 250.00

def fracdiff_weights(d, tau):
    w = [1.0]
    while True:
        w.append(-w[-1] * (d - len(w) + 1) / len(w))
        if abs(w[-1]) < tau:
            break
        if len(w) > 500:
            break
    return np.array(w)

w = fracdiff_weights(D_FRAC, TAU)
L = len(w)
print(f"seed=157 | d={D_FRAC} truncation width L={L} (first 5 weights: {w[:5].round(4)})")

# synthetic log-price with long memory: ARFIMA-like via truncated MA of innovations
N = 120
eps = rng.standard_normal(N + L)
x = np.zeros(N)
for t in range(N):
    x[t] = np.dot(w, eps[t + L - 1::-1][:L])
logp = np.log(P0) + 0.002 * np.cumsum(x) / np.std(x)  # scale to ~bp-level 1-min moves
price = np.exp(logp)
r = np.diff(logp, prepend=logp[0])

# fractional differentiation of the return series with order d
xhat = np.zeros(N)
for t in range(N):
    k = min(L, t + 1)
    xhat[t] = np.dot(w[:k], r[t::-1][:k])
xhat[np.isnan(xhat)] = 0.0

# AR(1) on the differenced series (estimated on first 60 bars, example)
SEG = 60
phi = np.dot(xhat[1:SEG], xhat[:SEG - 1]) / np.dot(xhat[:SEG - 1], xhat[:SEG - 1])
sig_eps = np.std(xhat[1:SEG] - phi * xhat[:SEG - 1], ddof=1)

# rolling VR(4) on the raw log-returns for the S090 memory gate (window 40, example)
W, K = 40, 4
vr = np.full(N, np.nan)
for t in range(W - 1, N):
    seg = r[t - W + 1:t + 1]
    rk = np.convolve(seg, np.ones(K), mode="valid")
    v = np.var(seg, ddof=1)
    vr[t] = np.var(rk, ddof=1) / (K * v) if v > 0 else np.nan

print(f"AR(1) phi={phi:.3f}, sigma_eps={sig_eps:.6f}")

def rt_cost(px):
    return 2 * (HALF_SPREAD_BP / 10000) * px * SHARES + 2 * FEE_SHARE * SHARES

trades = []
print("seed=157 | trades (bar, forecast_bp, VR, side, gross, cost, net):")
for t in range(SEG, N - 1):
    f = phi * xhat[t]                       # forecast of xhat_{t+1}
    f_bp = f * 10000
    gate_ok = abs(f_bp) > COST_GATE_BP and not np.isnan(vr[t]) and abs(vr[t] - 1) > 0.05
    if not gate_ok:
        continue
    side = 1 if f > 0 else -1
    pe, px = price[t], price[t + 1]
    gross = side * (px - pe) * SHARES
    net = gross - rt_cost(pe)
    trades.append((t, t + 1, side, f_bp, vr[t], pe, px, gross, rt_cost(pe), net))
    print(f"  bar {t:3d}: fcst={f_bp:+.2f}bp VR={vr[t]:.2f} -> "
          f"{'LONG ' if side>0 else 'SHORT'} gross={gross:+.2f} cost={rt_cost(pe):.2f} net={net:+.2f}")
    if len(trades) >= 6:
        break
print(f"total net = {sum(t[9] for t in trades):+.2f} over {len(trades)} trades")

cum = np.zeros(N)
for tr in trades:
    cum[tr[1]] += tr[9]
equity = np.cumsum(cum)

fig, (ax1, ax2, ax3) = plt.subplots(3, 1, sharex=True, gridspec_kw={"hspace": 0.10})
ax1.plot(price, color=PALETTE["price"], lw=1.2, label="Synthetic price (USD)")
ax1.axvline(SEG, color=PALETTE["signal"], ls="--", lw=1, label="AR(1) fit window ends")
for i, tr in enumerate(trades):
    te, tx, side, f_bp, vr_, pe, px, g, c, n = tr
    ax1.scatter([te], [pe], color=PALETTE["profit"] if side > 0 else PALETTE["loss"],
                marker="^" if side > 0 else "v", s=70, zorder=5)
    ax1.scatter([tx], [px], color=PALETTE["zero"], marker="x", s=50, zorder=5)
    ax1.annotate(f"T{i+1}", (te, pe), fontsize=7, ha="right",
                 color=PALETTE["profit"] if side > 0 else PALETTE["loss"])
ax1.set_ylabel("Price (USD)")
ax1.legend(loc="upper left")
ax1.set_title("T057 — Fractional-Differentiation Memory Trader: synthetic trade walk (seed 157)")

ax2.plot(xhat, color=PALETTE["signal2"], lw=1.1, label="Fractionally differenced series xhat")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.axvline(SEG, color=PALETTE["signal"], ls="--", lw=1)
ax2.set_ylabel("xhat")
ax2.legend(loc="upper left")

ax3.plot(equity, color=PALETTE["price"], lw=1.8, label="Cumulative net P&L (USD)")
for i, tr in enumerate(trades):
    te, tx, side, f_bp, vr_, pe, px, g, c, n = tr
    col = PALETTE["profit"] if n >= 0 else PALETTE["loss"]
    ax3.scatter([tx], [equity[tx]], color=col, s=40, zorder=5)
    ax3.annotate(f"T{i+1} {n:+.0f}", (tx, equity[tx]), fontsize=8, color=col,
                 xytext=(4, 6), textcoords="offset points")
ax3.axhline(0, color=PALETTE["zero"], lw=0.8)
ax3.set_ylabel("Net P&L (USD)")
ax3.set_xlabel("1-min bar index (synthetic)")
ax3.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T057_example.png", bbox_inches="tight")
plt.close()
