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

# ---- S018 synthetic worked example: order-sign autocorrelation ----
SEED = 1818
rng = np.random.default_rng(SEED)
N = 2000
P_SAME = 0.72  # Markov persistence: P(eps_{t+1} = eps_t) — example, not an institutional standard

eps = np.empty(N, dtype=int)
eps[0] = 1 if rng.random() < 0.5 else -1
for i in range(1, N):
    eps[i] = eps[i - 1] if rng.random() < P_SAME else -eps[i - 1]
eps = eps.astype(float)

TMAX = 30
C = np.array([np.mean(eps[:N - tau] * eps[tau:]) for tau in range(1, TMAX + 1)])
taus = np.arange(1, TMAX + 1)

# Power-law fit on lags 2..30: log C = a - gamma * log tau
mask = (taus >= 2) & (C > 0)
coef = np.polyfit(np.log(taus[mask]), np.log(C[mask]), 1)
gamma = -coef[0]
C_fit = np.exp(coef[1]) * taus ** (-gamma)

print(f"C(1) = {C[0]:.4f}")
print(f"fitted gamma = {gamma:.3f}")
print("tau | C(tau)")
for tau_i, c in zip(taus[:10], C[:10]):
    print(f"{tau_i:3d} | {c:+.4f}")

fig, ax = plt.subplots()
ax.plot(taus, C, "o-", color=PALETTE["signal"], ms=4, lw=1.4,
        label=f"empirical C(τ), seed {SEED}")
ax.plot(taus, C_fit, "--", color=PALETTE["price"], lw=1.4,
        label=f"power-law fit τ^(−γ), γ̂ = {gamma:.2f}")
ax.axhline(0, color=PALETTE["zero"], ls=":", lw=1.0)
ax.set_xlim(0, TMAX + 1)
ax.set_xlabel("lag τ (trades)")
ax.set_ylabel("sign autocorrelation C(τ)")
ax.set_title("S018 — Order-sign autocorrelation: synthetic 2000-trade tape")
ax.legend(loc="upper right")
ax.text(0.98, 0.06,
        f"C(1) = {C[0]:.3f} — positive short-lag persistence",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#7f8c8d", alpha=0.9))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S018_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S018_example.png")
