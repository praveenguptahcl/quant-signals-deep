import itertools
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

rng = np.random.default_rng(84)  # fixed seed, stated in chapter text

# ---- Synthetic DGP: common efficient price + venue transitory noise ----
# Venue A: fast/tight (leads), Venue B: medium, Venue C: slow/noisy (lags).
T = 5000
m = 100.0 + np.cumsum(rng.normal(0.0, 0.01, T))          # efficient price ($)
rhos = [0.10, 0.50, 0.90]                               # A, B, C transitory persistence
sig_n = 0.02
venues = ["A", "B", "C"]
P = np.zeros((T, 3))
for j, rho in enumerate(rhos):
    n = np.zeros(T)
    for t in range(1, T):
        n[t] = rho * n[t - 1] + rng.normal(0.0, sig_n)
    P[:, j] = m + n

# ---- VECM estimation (known beta: pA-pB, pA-pC stationary spreads) ----
# dP_t = c + alpha @ z_{t-1} + G1 @ dP_{t-1} + eps_t
beta = np.array([[1.0, 1.0], [-1.0, 0.0], [0.0, -1.0]])   # 3x2
dP = np.diff(P, axis=0)
z1 = P[:-1, 0] - P[:-1, 1]
z2 = P[:-1, 0] - P[:-1, 2]
X = np.column_stack([np.ones(len(dP) - 1), z1[:-1], z2[:-1], dP[:-1]])  # (T-2) x 6
Y = dP[1:]
Bhat = np.linalg.lstsq(X, Y, rcond=None)[0]              # 6x3
E = Y - X @ Bhat                                          # VECM residuals
alpha = Bhat[1:3, :].T                                   # 3x2 loadings on z1,z2
G1 = Bhat[3:, :].T                                       # 3x3 short-run
Omega = np.cov(E.T)                                      # 3x3 innovation covariance


def null_space_1d(M):
    u, svals, vh = np.linalg.svd(M)
    return vh[-1, :]


beta_perp = null_space_1d(beta.T)                        # (1,1,1)/sqrt(3)
alpha_perp = null_space_1d(alpha.T)
Gamma = np.eye(3) - G1
C1 = np.outer(beta_perp, alpha_perp) / float(alpha_perp @ Gamma @ beta_perp)
psi = C1[0, :]                                           # common long-run impact row (1x3)

print("psi (common long-run impact row):", np.array2string(psi, precision=4))
print("alpha loadings:\n", np.array2string(alpha, precision=4))
print("Omega:\n", np.array2string(Omega, precision=6, suppress_small=True))
denom = float(psi @ Omega @ psi)
print(f"psi Omega psi' = {denom:.8f}")
print("Cholesky F for ordering (A,B,C):\n" +
      np.array2string(np.linalg.cholesky(Omega), precision=6, suppress_small=True))

# ---- Information shares for all 6 Cholesky orderings ----
# IS_j(pi) = ([psi_pi F_pi]_j)^2 / (psi Omega psi'),  F_pi = chol(Omega_pi)
results = {}
for perm in itertools.permutations([0, 1, 2]):
    perm = list(perm)
    Pmat = np.zeros((3, 3))
    for new, old in enumerate(perm):
        Pmat[new, old] = 1.0
    Opi = Pmat @ Omega @ Pmat.T
    F = np.linalg.cholesky(Opi)
    v = (psi @ Pmat.T) @ F                                # psi in permuted order, times F
    shares = (v ** 2) / denom
    for new, old in enumerate(perm):
        results.setdefault(venues[old], []).append(float(shares[new]))
    print(f"ordering {[venues[i] for i in perm]}: " +
          " ".join(f"{venues[old]}={shares[new]:.3f}" for new, old in enumerate(perm)))

print("\nVenue | IS min | IS avg | IS max  (bounds across Cholesky orderings)")
bounds = {}
for j in venues:
    lo, hi = min(results[j]), max(results[j])
    avg = sum(results[j]) / len(results[j])
    bounds[j] = (lo, avg, hi)
    print(f"  {j}   | {lo:6.3f} | {avg:6.3f} | {hi:6.3f}")

# ---- Chart: bars = average IS, whiskers = Cholesky bounds ----
fig, ax = plt.subplots()
js = np.arange(3)
avgs = [bounds[j][1] for j in venues]
los = [bounds[j][1] - bounds[j][0] for j in venues]
his = [bounds[j][2] - bounds[j][1] for j in venues]
colors = [PALETTE["price"], PALETTE["signal2"], PALETTE["volume"]]
bars = ax.bar(js, [a * 100 for a in avgs],
              yerr=[[l * 100 for l in los], [h * 100 for h in his]],
              color=colors, edgecolor=PALETTE["zero"], capsize=8, error_kw={"lw": 1.8},
              tick_label=[f"Venue {j}\n(synthetic)" for j in venues])
for j, venue in enumerate(venues):
    lo, avg, hi = bounds[venue]
    ax.annotate(f"{lo*100:.0f}–{hi*100:.0f}%", (j, avg * 100 + his[j] * 100 + 2),
                ha="center", fontsize=10, color=PALETTE["zero"], weight="bold")
ax.set_title("S016 — Venue information shares with Cholesky-ordering bounds\n"
             "(seed 84, 1-s synthetic bars, cointegrated venues)")
ax.set_ylabel("Information share of efficient-price innovation (%)")
ax.set_ylim(0, 105)
ax.axhline(100, color=PALETTE["zero"], lw=0.8)
ax.annotate("whiskers = min/max over all 6\nCholesky orderings —\nreport bounds, not one number",
            xy=(2.0, 82), fontsize=9, color=PALETTE["zero"],
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.95))
ax.annotate("Venue A designed as the leader\n(fastest-adjusting quotes), but\nbounds overlap B and C —\nno venue dominates robustly",
            xy=(0, avgs[0] * 100), xytext=(0.9, 8), fontsize=9, color=PALETTE["price"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["price"]),
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.95))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S016_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
