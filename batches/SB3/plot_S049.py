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

# ---- S049 worked example (SYNTHETIC, seed 49) ----
# Normalized prices (cumulative-return index, 1.0 at formation start) for 3 stocks,
# 12-day formation + 6-day trading window. Values chosen to be hand-checkable.
rng = np.random.default_rng(49)

A_f = np.array([1.00, 1.02, 1.01, 1.03, 1.05, 1.04, 1.06, 1.08, 1.07, 1.09, 1.11, 1.10])
B_f = np.array([1.00, 1.015, 1.025, 1.02, 1.045, 1.055, 1.05, 1.075, 1.085, 1.08, 1.10, 1.105])
C_f = np.array([1.00, 1.05, 1.10, 1.08, 1.15, 1.20, 1.18, 1.25, 1.30, 1.28, 1.35, 1.40])

D_AB = float(np.sum((A_f - B_f) ** 2))
D_AC = float(np.sum((A_f - C_f) ** 2))
D_BC = float(np.sum((B_f - C_f) ** 2))

d_f = A_f - B_f                      # formation spread (A,B) = chosen pair
mu = float(d_f.mean())
sig = float(d_f.std(ddof=1))

# Trading window: normalized prices continue; B drops -> spread widens -> 2-sigma entry
A_t = np.array([1.12, 1.13, 1.125, 1.13, 1.135, 1.14])
B_t = np.array([1.095, 1.105, 1.12, 1.125, 1.13, 1.135])
d_t = A_t - B_t
z_t = (d_t - mu) / sig

Z_ENTRY, Z_EXIT = 2.0, 0.5
open_idx = int(np.argmax(np.abs(z_t) >= Z_ENTRY))       # first breach
exit_idx = int(np.argmax(np.abs(z_t[open_idx:]) <= Z_EXIT)) + open_idx

entry_px_A, entry_px_B = A_t[open_idx], B_t[open_idx]
exit_px_A, exit_px_B = A_t[exit_idx], B_t[exit_idx]
pnl_norm = (entry_px_A - exit_px_A) + (exit_px_B - entry_px_B)  # short A, long B

print(f"D_AB={D_AB:.6f} D_AC={D_AC:.6f} D_BC={D_BC:.6f}")
print(f"mu={mu:.6f} sigma={sig:.6f}")
for i, (sp, z) in enumerate(zip(d_t, z_t), start=13):
    print(f"day {i}: spread={sp:.4f} z={z:+.3f}")
print(f"open_idx(trading)={open_idx} exit_idx={exit_idx}")
print(f"entry A={entry_px_A:.3f} B={entry_px_B:.3f}; exit A={exit_px_A:.3f} B={exit_px_B:.3f}")
print(f"gross_pnl_normalized={pnl_norm:.4f}")

# ---- Plot: formation normalized prices (top) + spread with bands (bottom) ----
fig, (ax1, ax2) = plt.subplots(2, 1, sharex=False)

days_f = np.arange(1, 13)
ax1.plot(days_f, A_f, color=PALETTE["price"], marker="o", ms=3, label="A (norm. price)")
ax1.plot(days_f, B_f, color=PALETTE["signal2"], marker="o", ms=3, label="B (norm. price)")
ax1.plot(days_f, C_f, color=PALETTE["volume"], marker="o", ms=3, label="C (norm. price)")
ax1.set_title("S049 — Distance-method pairs: synthetic formation + trading spread (seed 49)")
ax1.set_ylabel("normalized price (index)")
ax1.set_xlabel("formation day")
ax1.legend()

days_all = np.arange(1, 19)
d_all = np.concatenate([d_f, d_t])
ax2.plot(days_f, d_f, color=PALETTE["price"], marker="o", ms=3, label="spread A-B (formation)")
ax2.plot(np.arange(13, 19), d_t, color=PALETTE["signal"], marker="o", ms=4, label="spread A-B (trading)")
for k, lab in ((2.0, "+2σ entry"), (-2.0, "-2σ entry")):
    ax2.axhline(mu + k * sig, color=PALETTE["signal"], ls="--", lw=1)
    ax2.text(18.2, mu + k * sig, lab, fontsize=8, color=PALETTE["signal"], va="center")
ax2.axhline(mu, color=PALETTE["zero"], ls=":", lw=1)
ax2.fill_between([13, 18], mu + 2 * sig, mu - 2 * sig, color=PALETTE["band"], alpha=0.25)
ax2.scatter([13 + open_idx], [d_t[open_idx]], color=PALETTE["signal"], s=80, zorder=5,
            marker="v", label=f"open short A / long B (z={z_t[open_idx]:+.2f})")
ax2.scatter([13 + exit_idx], [d_t[exit_idx]], color=PALETTE["profit"], s=80, zorder=5,
            marker="^", label=f"exit at |z|<={Z_EXIT} (z={z_t[exit_idx]:+.2f})")
ax2.set_ylabel("spread (A-B, norm. units)")
ax2.set_xlabel("day (1-12 formation, 13-18 trading)")
ax2.legend()

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S049_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
