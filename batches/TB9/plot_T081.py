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

rng = np.random.default_rng(181)  # T081 seed — stated in chapter text

# ---- T081 worked-example inputs (SYNTHETIC — see chapter T4) ----
# Regime detector features (computed on causal 1-min reference bars):
# sigma20 = 20-bar realized vol of log returns; lam = ticks/min; rho = AR(1) of signed volume
regimes = [
    {"name": "R1 quiet",      "minutes": 30, "clock": "dollar bars",
     "sigma20": 0.00070, "sigma_med": 0.00120, "rho": 0.10, "lam": 167, "lam_med": 400,
     "trades": 5000, "bars_closed": 1,  "why": "sigma20=0.583x med <0.6x, |rho|=0.10<0.15"},
    {"name": "R2 busy 2-sided", "minutes": 10, "clock": "volume bars",
     "sigma20": 0.00180, "sigma_med": 0.00120, "rho": 0.08, "lam": 1300, "lam_med": 400,
     "trades": 13000, "bars_closed": 65, "why": "lam=3.25x med >3x, |rho|=0.08<0.20"},
    {"name": "R3 informed",   "minutes": 10, "clock": "DIB (imbalance bars)",
     "sigma20": 0.00240, "sigma_med": 0.00120, "rho": 0.52, "lam": 300, "lam_med": 400,
     "trades": 3000, "bars_closed": 5,  "why": "|rho|=0.52>0.35 -> imbalance clock"},
]
D_target = 2_000_000      # $2.0M = ADV/50 (example threshold)
V_target = 20_000         # 20,000 shares = ADV_shares/50 (example threshold)
theta_DIB = 40_000        # 40,000 signed shares fixed fallback (example)

for r in regimes:
    print(f"{r['name']}: clock={r['clock']}, sigma_ratio={r['sigma20']/r['sigma_med']:.3f}, "
          f"lam_ratio={r['lam']/r['lam_med']:.2f}x, |rho|={abs(r['rho']):.2f}, bars={r['bars_closed']}")
total_trades = sum(r["trades"] for r in regimes)
total_bars = sum(r["bars_closed"] for r in regimes)
print(f"TOTAL trades={total_trades}, bars={total_bars}")
# Synthetic conditioning statistics (illustrative, not measured):
kurt_min, kurt_vol = 8.4, 4.1
print(f"kurtosis: minute-bar returns={kurt_min}, volume-bar returns={kurt_vol} (synthetic, illustrative)")

# ---- synthetic rate series for the timeline panel ----
rate, seg_bounds, clock_labels, seg_colors = [], [0], [], ["#d5f5e3", "#fdebd0", "#fadbd8"]
colors = [PALETTE["profit"], PALETTE["signal2"], PALETTE["signal"]]
m = 0
for i, r in enumerate(regimes):
    seg = r["lam"] * (1 + 0.06 * rng.standard_normal(r["minutes"]))
    seg = np.clip(seg, 1, None)
    rate.extend(seg)
    m += r["minutes"]
    seg_bounds.append(m)
    clock_labels.append(r["clock"])
rate = np.array(rate)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=False,
                               gridspec_kw={"height_ratios": [3, 2]})
fig.suptitle("T081 — Adaptive Bar-Clock Sampler: synthetic 3-regime session (seed 181)", fontweight="bold")

t = np.arange(len(rate))
ax1.plot(t, rate, color=PALETTE["price"], lw=1.4, label="trades/min (synthetic)")
for i, r in enumerate(regimes):
    ax1.axvspan(seg_bounds[i], seg_bounds[i + 1], color=seg_colors[i], alpha=0.45)
    mid = (seg_bounds[i] + seg_bounds[i + 1]) / 2
    ax1.text(mid, max(rate) * 1.02, f"{r['name']}\n-> {r['clock']}", ha="center", va="bottom",
             fontsize=8, fontweight="bold")
ax1.axhline(400, color=PALETTE["zero"], ls=":", lw=1, label="median rate 400/min")
ax1.set_ylabel("trades / min")
ax1.set_xlim(0, len(rate))
ax1.legend(loc="upper right")

names = [r["name"] for r in regimes]
bars = [r["bars_closed"] for r in regimes]
x = np.arange(len(names))
ax2.bar(x, bars, color=[PALETTE["profit"], PALETTE["signal2"], PALETTE["signal"]],
        label="bars closed per regime")
for i, b in enumerate(bars):
    ax2.text(i, b + 1.2, f"{b} {clock_labels[i]}", ha="center", fontsize=8, fontweight="bold")
ax2.set_xticks(x); ax2.set_xticklabels(names)
ax2.set_ylabel("bars closed")
ax2.set_ylim(0, max(bars) * 1.35)
ax2.text(0.98, 0.92, f"synthetic conditioning stat:\nminute-bar kurtosis {kurt_min}  vs\n"
         f"volume-bar kurtosis {kurt_vol}\n(stabilized features, illustrative)",
         transform=ax2.transAxes, ha="right", va="top", fontsize=8,
         bbox=dict(boxstyle="round", fc="white", alpha=0.9))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T081_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
