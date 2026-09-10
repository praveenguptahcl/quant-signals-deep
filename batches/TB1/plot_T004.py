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

# ---- T004 worked example (seed 104) ----
# Synthetic 1-minute session 10:30-11:30 for fictional large-cap "XYZ".
# All values below are SYNTHETIC — not market data.
rng = np.random.default_rng(104)
n = 61
t = np.arange(n)                      # bar index, 10:30 = bar 0
VWAP = 119.55 + 0.001 * t             # session VWAP, nearly flat (synthetic)
sigma_d = 0.0062                      # rolling std of deviation (example value)

# Designed deviation path: drifts down to -2.3 sigma by bar 30, reverts to ~+0.1 sigma by bar 50
d = np.zeros(n)
d[:31] = np.linspace(0, -2.3, 31) * sigma_d
d[31:51] = np.linspace(-2.3, 0.1, 20) * sigma_d
d[51:] = 0.1 * sigma_d
d += rng.normal(0, 0.10 * sigma_d, n)  # small microstructure noise
d[30] = -2.30 * sigma_d               # exact entry anchor
d[44] = -0.30 * sigma_d               # exact exit anchor

C = VWAP * (1 + d)                    # synthetic mid/close price
z = d / sigma_d                       # deviation z-score (matches S040)

# Queue imbalance: mostly noise, hand-set at entry/exit bars
I = np.clip(rng.normal(0.05, 0.28, n), -1, 1)
I[30] = 0.45                          # entry bar: bid-side replenishment (example)
I[44] = -0.10

# ---- Trade logic (mirrors the chapter's T3 pseudocode, example thresholds) ----
K_IN, K_OUT = 2.0, 0.5                # z entry / exit (example)
I_MIN = 0.30                          # queue-imbalance timing gate (example)
SPREAD = 0.02                         # $ synthetic spread
COMM_RT = 0.01                        # $/share round trip (example)
SHARES = 1500                         # example size (risk $300 / $0.20 stop)
TIME_STOP = 30                        # bars (example)

entry_bar = 30                        # z[30] = -2.30 <= -2.0 and I[30] = 0.45 >= 0.30
assert z[entry_bar] <= -K_IN and I[entry_bar] >= I_MIN
exit_idx = None
for b in range(entry_bar + 1, min(n, entry_bar + TIME_STOP + 1)):
    if abs(z[b]) <= K_OUT:            # reversion exit
        exit_idx = b
        break
assert exit_idx == 44

entry_fill = C[entry_bar] + SPREAD / 2  # buy: pay ask
exit_fill = C[exit_idx] - SPREAD / 2    # sell: hit bid
gross = SHARES * (exit_fill - entry_fill)
comm = SHARES * COMM_RT
net = gross - comm

print(f"T004 worked example (seed 104) — SYNTHETIC")
print(f"entry bar 30 (11:00): z={z[30]:.2f}, I={I[30]:.2f}, diurnal |d|={abs(d[30])*1e4:.0f} bps vs slot-median 60 bps")
print(f"  mid {C[30]:.2f} -> buy {SHARES} @ {entry_fill:.2f}")
print(f"exit  bar 44 (11:14): z={z[44]:.2f}, mid {C[44]:.2f} -> sell @ {exit_fill:.2f}")
print(f"gross {gross:.2f} | commission {comm:.2f} | NET {net:.2f}")

# ---- Plot ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
ax1.plot(t, C, color=PALETTE["price"], lw=1.6, label="Synthetic mid price ($)")
ax1.plot(t, VWAP, color=PALETTE["signal"], lw=1.2, ls="--", label="Session VWAP ($)")
ax1.scatter([entry_bar], [entry_fill], s=90, color=PALETTE["profit"], marker="^",
            zorder=5, label=f"Long entry @ ${entry_fill:.2f}")
ax1.scatter([exit_idx], [exit_fill], s=90, color=PALETTE["loss"], marker="v",
            zorder=5, label=f"Exit @ ${exit_fill:.2f}")
ax1.set_ylabel("Price ($)")
ax1.set_title("T004 — VWAP-Deviation Mean-Reversion: synthetic trade timeline and net P&L")
ax1.legend(loc="lower left")

cum = np.zeros(n)
cum[exit_idx:] = net
ax2.step(t, cum, where="post", color=PALETTE["profit"], lw=1.8, label="Cumulative net P&L ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.annotate(f"Trade 1 net: ${net:,.2f}", xy=(exit_idx, net), xytext=(exit_idx + 8, net + 60),
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             fontsize=9, color=PALETTE["profit"], weight="bold")
ax2.set_xlabel("1-minute bar index (bar 0 = 10:30 ET, synthetic)")
ax2.set_ylabel("Net P&L ($)")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
plt.savefig(ROOT / "images" / "T004_example.png", bbox_inches="tight")
plt.close()
print("saved", ROOT / "images" / "T004_example.png")
