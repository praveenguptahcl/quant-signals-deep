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

# ---- STATED covariance (from the example — NOT re-estimated from the printed panel,
#      which was internally inconsistent; see chapter S4 disclosure).
#      Exact fractions (13/12, 35/36) are used so the eigen-decomposition is clean;
#      the chapter displays them rounded as 1.0833 / 0.9722, with lambda1 = 2.0556. ----
SIGMA = np.array([[13/12, 35/36, 0.0],
                  [35/36, 13/12, 0.0],
                  [0.0,    0.0,  13/12]])
lam, V = np.linalg.eigh(SIGMA)
order = np.argsort(lam)[::-1]
lam, V = lam[order], V[:, order]
print("eigvals:", np.round(lam, 4))
print("v1:", np.round(V[:, 0], 4), " (= (1/sqrt2)[1,1,0] up to sign)")
print("variance explained:", np.round(lam / lam.sum() * 100, 2), "%")

# ---- SYNTHETIC standardized-return panel (seed 80) for stocks A, B ----
# Day 1 is fixed to the verified arithmetic: A_1 = 1.0, B_1 = 0.0  ->  Ahat_1 = 0.5, u_{A,1} = 0.5.
rng = np.random.default_rng(80)
n = 10
A = rng.normal(0, 1, n); B = rng.normal(0, 1, n)
A[0], B[0] = 1.0, 0.0
Ahat = (A + B) / 2.0                 # 1-factor reconstruction (m = 1, PC1 = market)
uA = (A - B) / 2.0                   # residual (verified derivation from stated Sigma)
sig_u = uA.std(ddof=1)
z = uA / sig_u
thresh = 2.0                          # example z-threshold (NOT a standard)

print("\nS080 worked-example table (standardized returns), seed=80")
print(" day | A_t | B_t | Ahat_t=(A+B)/2 | uA_t=(A-B)/2 | z_t | signal")
for t in range(n):
    sig = "NONE"
    if z[t] > thresh: sig = "SHORT A (fade +residual)"
    elif z[t] < -thresh: sig = "LONG A (fade -residual)"
    print(f"{t+1:3d} | {A[t]:+.3f} | {B[t]:+.3f} | {Ahat[t]:+.3f} | {uA[t]:+.3f} | {z[t]:+.2f} | {sig}")
print("residual std:", round(sig_u, 4))

# ---- PLOT ----
fig, axes = plt.subplots(1, 2, figsize=(10, 5.2), gridspec_kw={"width_ratios": [1, 2]})
ax = axes[0]
ax.bar([1, 2, 3], lam, color=[PALETTE["price"], PALETTE["volume"], PALETTE["volume"]])
ax.set_xticks([1, 2, 3]); ax.set_xticklabels(["λ1=2.0556\n63.25%", "λ2=1.0833\n33.33%", "λ3=0.1111\n3.42%"])
ax.set_ylabel("eigenvalue (variance units)")
ax.set_title("Stated-Σ eigendecomposition\n(v1 = (1/√2)[1,1,0])")
ax.annotate("chatbot panel inconsistent\nwith this Σ — see text", xy=(2, 1.2), fontsize=8,
            color=PALETTE["signal"], ha="center")

ax2 = axes[1]
days = np.arange(1, n + 1)
ax2.plot(days, uA, "o-", color=PALETTE["price"], label="residual u_A,t = (A_t − B_t)/2")
ax2.axhline(2 * sig_u, color=PALETTE["signal"], ls="--", label="±2σ gate (example)")
ax2.axhline(-2 * sig_u, color=PALETTE["signal"], ls="--")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
for t in range(n):
    if abs(z[t]) > thresh:
        ax2.annotate("FADE", (t + 1, uA[t]), textcoords="offset points", xytext=(0, 10),
                     ha="center", fontsize=8, color=PALETTE["signal"], weight="bold")
ax2.set_xlabel("day (standardized returns, seed 80)")
ax2.set_ylabel("residual (std units)")
ax2.set_title("S080 — eigenportfolio residual: trade the mean-reverting component")
ax2.legend(loc="best")
plt.tight_layout()

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S080_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
