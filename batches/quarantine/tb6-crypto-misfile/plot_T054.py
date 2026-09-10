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
# synthetic session for T054, seed = stage number
rng = np.random.default_rng(154)

N = 240                      # 240 1-min bars, 09:31 -> 15:30 ET (synthetic)
SIGMA = 0.0004               # 4 bp/min
P0 = 250.00
phi = np.zeros(N)
phi[0:80] = 0.25             # persistent block (trend regime)
phi[80:160] = -0.25          # anti-persistent block (reversion regime)
# bars 160-239: white noise
eps = rng.standard_normal(N)
r = np.zeros(N)
for t in range(N):
    prev = r[t - 1] if t > 0 else 0.0
    r[t] = phi[t] * prev + SIGMA * eps[t]
price = P0 * np.exp(np.cumsum(r))

# rolling variance-ratio VR(4) on window 60 (example), then Hurst mapping
W, K = 60, 4
vr = np.full(N, np.nan)
for t in range(W - 1, N):
    seg = r[t - W + 1:t + 1]
    rk = np.convolve(seg, np.ones(K), mode="valid")
    v = np.var(seg, ddof=1)
    vk = np.var(rk, ddof=1)
    vr[t] = vk / (K * v) if v > 0 else np.nan
hurst = 0.5 * (1.0 + np.log(np.clip(vr, 1e-6, None)) / np.log(K))
regime = np.where(hurst > 0.55, "trend", np.where(hurst < 0.45, "reversion", "dead"))
# regime only defined once the estimator window is warm
regime[:W - 1] = "dead"

HALF_SPREAD_BP = 1.25
FEE_PER_SHARE = 0.005
SHARES = 1000

def roundtrip_cost(px):
    return 2 * (HALF_SPREAD_BP / 10000) * px * SHARES + 2 * FEE_PER_SHARE * SHARES

trades = []  # (side, entry_t, exit_t, entry_px, exit_px, gross, cost, net)

def add_trade(side, te, tx):
    pe, px = price[te], price[tx]
    gross = side * (px - pe) * SHARES
    net = gross - roundtrip_cost(pe)
    trades.append((side, te, tx, pe, px, gross, roundtrip_cost(pe), net))

# Momentum sleeve: S025-style rolling 30-min momentum in trend regime (example)
atr30 = np.array([np.std(price[max(0, t - 29):t + 1]) * np.sqrt(30) for t in range(N)])
mom_done = 0
for t in range(60, 80, 5):
    if mom_done >= 3 or regime[t] != "trend":
        continue
    sgn = 1 if np.sum(r[t - 29:t + 1]) > 0 else -1
    te = t + 1
    stop = 1.5 * atr30[t]
    tx = te
    for b in range(te + 1, min(te + 30, 80)):
        if regime[b] != "trend" or abs(price[b] - price[te]) > stop:
            tx = b
            break
        tx = b
    add_trade(sgn, te, tx)
    mom_done += 1

# Reversion sleeve: S041 tag-and-reenter Bollinger(20, 2.0) in reversion regime (example)
sma = np.array([np.mean(price[max(0, t - 19):t + 1]) for t in range(N)])
sd = np.array([np.std(price[max(0, t - 19):t + 1], ddof=1) for t in range(N)])
upper, lower = sma + 2 * sd, sma - 2 * sd
rev_done = 0
for t in range(80, 160):
    if rev_done >= 3:
        break
    if regime[t] != "reversion":
        continue
    side = 0
    if price[t] < lower[t] and t + 1 < N and price[t + 1] > lower[t + 1]:
        side = 1
    elif price[t] > upper[t] and t + 1 < N and price[t + 1] < upper[t + 1]:
        side = -1
    if side == 0:
        continue
    te = t + 1
    tx = te
    for b in range(te + 1, min(te + 11, N)):
        if side == 1 and (price[b] >= sma[b] or regime[b] != "reversion"):
            tx = b
            break
        if side == -1 and (price[b] <= sma[b] or regime[b] != "reversion"):
            tx = b
            break
        tx = b
    add_trade(side, te, tx)
    rev_done += 1

print("seed=154 | trades (side,entry_bar,exit_bar,entry_px,exit_px,gross,cost,net,hurst@entry):")
for tr in trades:
    s, te, tx, pe, px, g, c, n = tr
    print(f"  {'LONG ' if s>0 else 'SHORT'} entry={te} exit={tx} entry_px={pe:.3f} "
          f"exit_px={px:.3f} gross={g:+.2f} cost={c:.2f} net={n:+.2f} H={hurst[te]:.2f}")
print(f"total net = {sum(t[7] for t in trades):+.2f} over {len(trades)} trades")

cum = np.zeros(N)
for tr in trades:
    s, te, tx, pe, px, g, c, n = tr
    cum[tx] += n
equity = np.cumsum(cum)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, gridspec_kw={"hspace": 0.08})
for lo, hi, lab, col in [(0, 80, "persistent (true)", "#d5f5e3"),
                         (80, 160, "anti-persistent (true)", "#fadbd8"),
                         (160, 240, "white noise (true)", "#eaf2f8")]:
    ax1.axvspan(lo, hi, color=col, alpha=0.35, zorder=0)
    ax2.axvspan(lo, hi, color=col, alpha=0.35, zorder=0)
ax1.plot(price, color=PALETTE["price"], lw=1.2, label="Synthetic mid price (USD)")
ax1.plot(upper, color=PALETTE["volume"], lw=0.8, ls="--")
ax1.plot(lower, color=PALETTE["volume"], lw=0.8, ls="--", label="Bollinger(20,2) bands")
for i, tr in enumerate(trades):
    s, te, tx, pe, px, g, c, n = tr
    ax1.scatter([te], [pe], color=PALETTE["profit"] if s > 0 else PALETTE["loss"],
                marker="^" if s > 0 else "v", s=70, zorder=5)
    ax1.scatter([tx], [px], color=PALETTE["zero"], marker="x", s=50, zorder=5)
    ax1.annotate(f"T{i+1}", (te, pe), fontsize=7, ha="right",
                 color=PALETTE["profit"] if s > 0 else PALETTE["loss"])
ax1.set_ylabel("Price (USD)")
ax1.legend(loc="upper left")
ax1.set_title("T054 — Hurst/Variance-Ratio Regime Toggle: synthetic trade timeline (seed 154)")

ax2.plot(equity, color=PALETTE["price"], lw=1.5, label="Cumulative net P&L (USD)")
for i, tr in enumerate(trades):
    s, te, tx, pe, px, g, c, n = tr
    col = PALETTE["profit"] if n >= 0 else PALETTE["loss"]
    ax2.scatter([tx], [equity[tx]], color=col, s=40, zorder=5)
    ax2.annotate(f"T{i+1} {n:+.0f}", (tx, equity[tx]), fontsize=8, color=col,
                 xytext=(4, 6), textcoords="offset points")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("Net P&L (USD)")
ax2.set_xlabel("1-min bar index (synthetic session)")
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T054_example.png", bbox_inches="tight")
plt.close()
