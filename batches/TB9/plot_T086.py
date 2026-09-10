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

rng = np.random.default_rng(186)  # T086 seed — stated in chapter text

# ---- T086 worked-example inputs (SYNTHETIC) ----
# Parent: 100,000-share BUY, arrival mid $250.00, 10 volume-time slices.
Q, arrival = 100_000, 250.00
vol_w = np.array([0.07, 0.08, 0.09, 0.11, 0.12, 0.12, 0.11, 0.10, 0.11, 0.09])  # diurnal curve (S067)
base = Q * vol_w
z = np.array([0.4, 1.6, 0.3, -0.8, -1.5, 0.3, 1.5, 0.2, -0.5, 0.0])  # OFI z, buy-positive (S001)
z = z - z.mean()  # demeaned: raw z-scores are not demeaned by default (reviewer correction)
gamma_m, kappa = 0.25, 0.5  # pace tilt and clip (example)
m = np.clip(1 + gamma_m * z, 1 - kappa, 1 + kappa)
raw = base * m
pov_cap = 0.10  # 10% of tape (example)
tape = np.array([90, 100, 110, 130, 140, 140, 180, 120, 130, 110]) * 1000
# POV cap enforced slice by slice, iterated so renormalization cannot breach it
x = raw.copy()
for _ in range(10):
    x = np.minimum(x, pov_cap * tape)
    x = x * Q / x.sum()
paced = x
print("slice | base | z | m | raw | paced (POV-capped) | tape | POV")
for i in range(10):
    pov = paced[i] / tape[i]
    flag = "CAPPED" if raw[i] > pov_cap * tape[i] else "ok"
    assert pov <= pov_cap + 1e-9, f"slice {i+1} breaches cap"
    print(f"{i+1:5d} | {base[i]:6.0f} | {z[i]:+4.1f} | {m[i]:.3f} | {raw[i]:7.1f} | {paced[i]:7.1f} | "
          f"{tape[i]:6.0f} | {pov:.3f} {flag}")
print(f"paced sum = {paced.sum():.1f} (target {Q})")
# RVOL gate (S032): horizon RVOL = 1.15 -> participation scaled x1.0 (no clip; example gate: stand down if RVOL<0.5)
print("RVOL=1.15 (example): gate passes, schedule unchanged")

# Slippage (example model): fill_i = mid_i + half-spread 1c + temp impact eta*sqrt(q_i/V_i), eta=$0.04
eta, half_spread = 0.04, 0.01
mid = arrival + 0.02 * np.cumsum(rng.standard_normal(10)) / 3 + np.linspace(0, 0.06, 10)  # synthetic slice mids
temp = eta * np.sqrt(paced / tape)
fill = mid + half_spread + temp
IS = float(np.sum(paced * (fill - arrival)))
int_vwap = float(np.sum(tape * mid) / np.sum(tape))  # interval-VWAP benchmark of the same horizon
print(f"arrival=${arrival:.2f}; interval VWAP=${int_vwap:.4f}")
print(f"avg fill=${np.sum(paced*fill)/Q:.4f}; implementation shortfall vs arrival=${IS:.2f}")
print(f"shortfall vs interval VWAP=${float(np.sum(paced*(fill-int_vwap))):.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), gridspec_kw={"height_ratios": [3, 2]})
fig.suptitle("T086 — OFI-Paced Participation Tracker: synthetic 10-slice schedule (seed 186)",
             fontweight="bold")
x = np.arange(1, 11)
w = 0.35
ax1.bar(x - w / 2, base / 1000, w, color=PALETTE["volume"], label="base schedule (diurnal curve)")
ax1.bar(x + w / 2, paced / 1000, w, color=PALETTE["price"], label="OFI-paced schedule")
for i in range(10):
    ax1.text(i + 1 + w / 2, paced[i] / 1000 + 0.25, f"z={z[i]:+.1f}", ha="center", fontsize=7,
             color=PALETTE["signal"] if z[i] < 0 else PALETTE["profit"], fontweight="bold")
ax1.set_xticks(x); ax1.set_xlabel("volume-time slice")
ax1.set_ylabel("shares (000s)")
ax1.legend(loc="upper left")
ax1.text(0.98, 0.94, "pace m = clip(1 + 0.25 z, [0.5, 1.5])\nPOV cap 10% of tape: slice 2 capped",
         transform=ax1.transAxes, ha="right", va="top", fontsize=8,
         bbox=dict(boxstyle="round", fc="white", alpha=0.9))

cost_per_slice = paced * (fill - arrival)
cum = np.cumsum(cost_per_slice)
ax2.bar(x, cost_per_slice, color=PALETTE["signal2"], label="per-slice shortfall vs arrival")
ax2.plot(x, cum, color=PALETTE["price"], marker="o", ms=4, lw=1.8, label="cumulative IS")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.text(10, cum[-1] * 1.02, f"IS ${IS:.2f}\n(avg fill ${np.sum(paced*fill)/Q:.4f})",
         ha="right", fontsize=9, fontweight="bold")
ax2.set_xticks(x); ax2.set_xlabel("volume-time slice")
ax2.set_ylabel("shortfall vs arrival ($)")
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T086_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
