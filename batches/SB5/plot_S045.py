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

# ---- VERIFIED SYNTHETIC TAPE (operator hand-checked; see chapter text) ----
# bars 1-10: closes ramp 100.00 -> 100.50 (step 0.50/9); bars 11-29: 100.20; bar 30: 102.00
rng = np.random.default_rng(45)  # required by house spec; tape itself is the verified tape
C = np.empty(30)
C[0:10] = 100.00 + np.arange(10) * (0.50 / 9)
C[10:29] = 100.20
C[29] = 102.00

N = 20
mu, sig, z = np.full(30, np.nan), np.full(30, np.nan), np.full(30, np.nan)
for t in range(N - 1, 30):
    w = C[t - N + 1:t + 1]          # window INCLUDES current bar (completed-bar convention)
    mu[t] = w.mean()
    sig[t] = w.std(ddof=0)          # population std, as in the verified example
    z[t] = (C[t] - mu[t]) / sig[t]

print("bar |    C |   mu20 | sigma20 |   z")
for t in range(19, 30):
    print(f"{t+1:3d} | {C[t]:5.2f} | {mu[t]:6.4f} | {sig[t]:7.4f} | {z[t]:+.2f}")

# methodology-caveat comparison: strictly PRIOR-only window (bars 10-29) at bar 30
w_prior = C[9:29]
mu_p, sig_p = w_prior.mean(), w_prior.std(ddof=0)
z_p = (C[29] - mu_p) / sig_p
print(f"\nbar 30 PRIOR-only convention (bars 10-29): mu={mu_p:.4f} sigma={sig_p:.5f} z={z_p:+.2f}")
print(f"bar 30 INCLUDING-bar-30 convention:        mu={mu[29]:.4f} sigma={sig[29]:.4f} z={z[29]:+.2f}")

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
x = np.arange(1, 31)
ax1.plot(x, C, color=PALETTE["price"], marker="o", ms=4, label="Close (5-min bars)")
ax1.annotate("extreme bar\n(C=102.00)", xy=(30, 102.00), xytext=(23, 102.9),
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
             fontsize=9, color=PALETTE["signal"], ha="center", weight="bold")
ax1.set_ylabel("Price ($)")
ax1.set_title("S045 — Stretched-move z-score: verified 30-bar tape (incl-bar-30 convention)")
ax1.set_xlim(0.5, 30.5)
ax1.legend(loc="upper left")

xz = np.arange(20, 31)
ax2.plot(xz, z[19:30], color=PALETTE["signal"], marker="o", ms=5, label="z (20-bar, incl. current bar)")
ax2.axhline(2, color=PALETTE["zero"], ls="--", lw=1, label="fade threshold ±2 (example)")
ax2.axhline(-2, color=PALETTE["zero"], ls="--", lw=1)
ax2.axhline(0, color=PALETTE["zero"], ls=":", lw=1)
ax2.annotate(f"z = +{z[29]:.2f}\n(σ = {sig[29]:.4f})", xy=(30, z[29]), xytext=(25.5, z[29] - 1.3),
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
             fontsize=9, color=PALETTE["signal"], ha="center", weight="bold")
ax2.set_ylabel("z-score")
ax2.set_xlabel("Bar number (5-min)")
ax2.set_ylim(-1.5, 5.5)
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S045_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
