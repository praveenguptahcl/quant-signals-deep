"""S037 plot: Lee-Mykland Z/T statistics with the 2.970 threshold + jump-filter decision.
Uses the CORRECTED worked example (bot single-digit typo fixed: 0.000011649 -> 0.000011749).
Chart numbers are the S4 numbers in batches/SB6/S037.md.
Run: python3 batches/SB6/plot_S037.py   (cwd = quant-signals-deep)
"""
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

rng = np.random.default_rng(37)  # stated in chapter text

# ---- corrected Lee-Mykland chain (independent recomputation confirms bot correction) ----
r_open = float(np.log(102 / 100))          # 0.019803
Sigma = 0.000087954                        # corrected adjacent |r||r| sum
Vhat = (np.pi / 2.0) * Sigma                # 0.00013816
sq = float(np.sqrt(Vhat))                   # 0.011754
Z = r_open / sq                             # 1.685
C, S_ = 3.031, 0.2894                       # extreme-value normalization (Delta=1/390)
T = (abs(Z) - C) / S_                       # -4.65
q95, q99 = 2.970, 4.600
print(f"r(open)={r_open:.6f} Vhat={Vhat:.8f} sqrt={sq:.6f} Z={Z:.3f} T={T:.2f} "
      f"q95={q95:.3f} q99={q99:.3f} -> {'JUMP' if T > q95 else 'NOT a jump'}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [1.35, 1]}, sharex=False)

# panel A: the corrected arithmetic chain as a waterfall-ish bar of the key inputs
labels = ["|r(4)|·|r(5)|\n(×10⁶)", "Σ adjacent\n|Δp|·|Δp| (×10⁶)",
          "V̂ (×10⁶)", "√V̂ (×10³)", "|Z(open)|", "T(open)"]
vals = [0.000011749 * 1e6, Sigma * 1e6, Vhat * 1e6, sq * 1e3, abs(Z), T]
colors = [PALETTE["volume"]] * 4 + [PALETTE["signal2"], PALETTE["profit"]]
bars = ax1.bar(labels, vals, color=colors, edgecolor="#2c3e50", lw=0.8)
ax1.set_title("S037 — Lee–Mykland opening-jump test: corrected arithmetic (synthetic tape)")
ax1.set_ylabel("value (scaled)")
for b, v in zip(bars, [0.000011749, Sigma, Vhat, sq, abs(Z), T]):
    ax1.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03 * (b.get_height() or 1),
             f"{v:.6g}", ha="center", va="bottom", fontsize=9)
ax1.text(0.02, 0.94, "typo fixed: |r(4)|·|r(5)| = 0.000011749 (printed 0.000011649)",
         transform=ax1.transAxes, fontsize=9, color=PALETTE["signal"],
         bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=PALETTE["signal"], alpha=0.9))

# panel B: T(open) on the decision axis with the extreme-value thresholds
ax2.axvspan(q95, 6.5, color=PALETTE["signal"], alpha=0.18, label="reject no-jump (α=5%)")
ax2.axvspan(-6.5, q95, color=PALETTE["profit"], alpha=0.12, label="no jump — fade allowed")
ax2.axvline(q95, color=PALETTE["signal"], lw=2.0, ls="--", label=f"q(0.95) = {q95:.3f}")
ax2.axvline(q99, color=PALETTE["loss"], lw=1.5, ls=":", label=f"q(0.99) = {q99:.3f}")
ax2.axvline(0, color=PALETTE["zero"], lw=1.0)
ax2.scatter([T], [0.5], color=PALETTE["price"], s=160, zorder=5, edgecolors="white", lw=1.2)
ax2.annotate(f"T(open) = {T:.2f}", xy=(T, 0.5), xytext=(T - 0.4, 0.78),
            fontsize=11, weight="bold", color=PALETTE["price"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["price"]))
ax2.annotate("−4.65 < 2.970\nNOT a Lee–Mykland jump at 5%\n→ fade the gap",
            xy=(T, 0.5), xytext=(-4.3, 0.18), fontsize=10, color=PALETTE["profit"],
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=PALETTE["profit"], alpha=0.95))
ax2.set_xlim(-6.5, 6.5)
ax2.set_ylim(0, 1)
ax2.set_yticks([])
ax2.set_xlabel("Lee–Mykland extreme-value statistic T(i)  (rejection: T > q(1−α))")
ax2.legend(loc="upper right", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S037_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S037_example.png")
