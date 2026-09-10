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
# synthetic Hasbrouck trade-quote VAR tape, seed = stage number
rng = np.random.default_rng(156)

N = 14                      # 1-s bars (synthetic)
MID0 = 50.00
# example VAR(2) coefficient matrices on x_t = (dm_t, q_t); all thresholds example
A1 = np.array([[0.25, 0.006],
               [0.02, 0.35]])
A2 = np.array([[0.10, 0.004],
               [-0.05, 0.15]])
FORECAST_GATE_C = 0.40      # cents: trade only if |forecast next-bar revision| > 0.40c
HAWKES_KAPPA = 2.0          # veto if |Hawkes imbalance z| >= 2.0 (example)
HALF_SPREAD_C = 0.50        # cents
FEE_SHARE = 0.005
SHARES = 500

# synthetic tape: mids (USD) and Lee-Ready signed trades
dm = np.array([0.01, -0.01, 0.02, 0.01, -0.02, 0.01, 0.02, -0.01,
               0.01, 0.02, -0.01, -0.02, 0.01, 0.01])
q = np.array([1, -1, 1, 1, -1, 1, 1, -1, 1, 1, -1, -1, 1, -1], dtype=float)
# synthetic Hawkes buy/sell intensity imbalance z-scores (from S081 estimator)
hz = np.array([0.3, -0.5, 1.2, 0.8, -1.1, 0.4, 2.6, 0.2, -0.7, 1.5, -0.3, 0.9, -1.8, 0.1])
mids = MID0 + np.cumsum(dm)

def forecast(t):
    # one-step-ahead forecast of dm_{t+1} from data <= t (example VAR(2))
    x1 = np.array([dm[t], q[t]])
    x2 = np.array([dm[t - 1], q[t - 1]]) if t - 1 >= 0 else np.zeros(2)
    return float(A1[0] @ x1 + A2[0] @ x2) * 100.0  # cents

def rt_cost_usd():
    # 0.50c half-spread + $0.005/share commission, each way, two legs
    return 2 * (HALF_SPREAD_C / 100.0) * SHARES + 2 * FEE_SHARE * SHARES

trades = []
print("seed=156 | VAR(2) tape (signal_bar, forecast_c, hawkes_z, action; fill at t+1, exit t+2):")
for t in range(2, N - 2):
    f = forecast(t)
    fire = abs(f) > FORECAST_GATE_C and abs(hz[t]) < HAWKES_KAPPA
    side = 1 if f > 0 else -1
    if fire:
        entry_px = mids[t + 1]                   # signal at t -> earliest fill t+1
        exit_px = mids[t + 2]                     # exit one bar later
        gross = side * (exit_px - entry_px) * SHARES
        net = gross - rt_cost_usd()
        trades.append((t + 1, t + 2, side, f, entry_px, exit_px, gross, rt_cost_usd(), net))
        print(f"  bar {t:2d}: fcst={f:+.2f}c hz={hz[t]:+.1f} -> {'LONG ' if side>0 else 'SHORT'} "
              f"entry_bar={t+1} exit_bar={t+2} entry={entry_px:.3f} exit={exit_px:.3f} gross={gross:+.2f} net={net:+.2f}")
    else:
        reason = "veto: Hawkes burst" if abs(hz[t]) >= HAWKES_KAPPA else "below gate"
        print(f"  bar {t:2d}: fcst={f:+.2f}c hz={hz[t]:+.1f} -> no trade ({reason})")
print(f"total net = {sum(t[8] for t in trades):+.2f} over {len(trades)} trades")

cum = np.zeros(N)
for tr in trades:
    cum[tr[1]] += tr[8]
equity = np.cumsum(cum)

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, gridspec_kw={"hspace": 0.08})
ax1.plot(mids, color=PALETTE["price"], lw=1.5, marker="o", ms=4, label="Synthetic mid (USD)")
ax1b = ax1.twinx()
ax1b.bar(np.arange(N), hz, color=PALETTE["signal2"], alpha=0.35, label="Hawkes z (S081)")
ax1b.axhline(HAWKES_KAPPA, color=PALETTE["signal"], ls="--", lw=1)
ax1b.axhline(-HAWKES_KAPPA, color=PALETTE["signal"], ls="--", lw=1)
ax1b.set_ylabel("Hawkes z")
for i, tr in enumerate(trades):
    te, tx, side, f, pe, px, g, c, n = tr
    ax1.scatter([te], [pe], color=PALETTE["profit"] if side > 0 else PALETTE["loss"],
                marker="^" if side > 0 else "v", s=80, zorder=5)
    ax1.scatter([tx], [px], color=PALETTE["zero"], marker="x", s=60, zorder=5)
    ax1.annotate(f"T{i+1} {f:+.1f}c", (te, pe), fontsize=7,
                 color=PALETTE["profit"] if side > 0 else PALETTE["loss"],
                 xytext=(4, 6), textcoords="offset points")
ax1.set_ylabel("Mid (USD)")
ax1.set_title("T056 — Hasbrouck Trade–Quote VAR Predictor: synthetic 1-s tape (seed 156)")

ax2.plot(equity, color=PALETTE["price"], lw=1.5, label="Cumulative net P&L (USD)")
for i, tr in enumerate(trades):
    te, tx, side, f, pe, px, g, c, n = tr
    col = PALETTE["profit"] if n >= 0 else PALETTE["loss"]
    ax2.scatter([tx], [equity[tx]], color=col, s=60, zorder=5)
    ax2.annotate(f"T{i+1} {n:+.2f}", (tx, equity[tx]), fontsize=8, color=col,
                 xytext=(5, 8), textcoords="offset points")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("Net P&L (USD)")
ax2.set_xlabel("1-s bar index (synthetic)")
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
import warnings as _warnings
with _warnings.catch_warnings():
    _warnings.simplefilter("ignore", UserWarning)  # spurious tight_layout warning on this mpl build
    plt.tight_layout()
plt.savefig("images/T056_example.png", bbox_inches="tight")
plt.close()
