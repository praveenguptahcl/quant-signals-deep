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

# ---- SYNTHETIC intraday GARCH(1,1) x diurnal season demo (seed 65) ----
rng = np.random.default_rng(65)
M = 78                                  # one 6.5h RTH session of 5-min bins
idx = np.arange(M)

# Deterministic time-of-day seasonal scale s_i, U-shape, mean 1 (example params)
u = (idx - (M - 1) / 2) / ((M - 1) / 2)         # -1 (open) .. +1 (close)
s = 1.0 + 0.55 * u ** 2
s = s / s.mean()

# GARCH(1,1) parameters: EXAMPLE VALUES — not an institutional standard.
# alpha+beta = 0.95 (persistence band 0.90-0.99 per chatbot lead, illustrative).
omega, alpha, beta = 2.0e-7, 0.06, 0.89
assert alpha + beta < 1.0

h = np.zeros(M)                          # stochastic GARCH variance component
h[0] = omega / (1 - alpha - beta)        # start at unconditional variance
z = rng.standard_normal(M)
for i in range(1, M):
    eps_prev = np.sqrt(h[i - 1]) * z[i - 1]
    h[i] = omega + alpha * eps_prev ** 2 + beta * h[i - 1]

sigma_stoch = np.sqrt(h)                 # GARCH path, no season
sigma_full = s * np.sqrt(h)              # final conditional sigma: season x GARCH
r = sigma_full * rng.standard_normal(M)  # synthetic deseasonalized-rescaled returns

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True)

ax1.plot(idx + 1, s, color=PALETTE["signal2"], lw=2.0, label="seasonal scale s_i (U-shape, mean 1)")
ax1.plot(idx + 1, sigma_stoch * 1e4, color=PALETTE["price"], lw=1.6,
         label="GARCH sigma (bp, no season)")
ax1.plot(idx + 1, sigma_full * 1e4, color=PALETTE["signal"], lw=1.6,
         label="final sigma_{t,i} = s_i x GARCH (bp)")
ax1.set_ylabel("sigma (basis points)")
ax1.set_title("S065 — Intraday GARCH(1,1) with diurnal scale: sigma path (seed 65)")
ax1.legend(loc="upper right")
ax1.text(0.02, 0.96,
         f"example params: omega={omega:.1e}, alpha={alpha}, beta={beta}, alpha+beta={alpha+beta:.2f}\n"
         "persistence band 0.90-0.99 is ILLUSTRATIVE — example, not an institutional standard",
         transform=ax1.transAxes, fontsize=8, va="top",
         bbox=dict(boxstyle="round", fc="white", ec=PALETTE["zero"], alpha=0.9))

ax2.bar(idx + 1, r * 1e4, color=[PALETTE["price"]] * M, edgecolor="none", width=0.9)
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_xlabel("5-minute bin of the session (1=open, 78=close)")
ax2.set_ylabel("return (basis points)")
ax2.set_title("synthetic 5-min returns drawn from the sigma path above", fontsize=10, fontweight="normal")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S065_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print(f"mean(s)={s.mean():.6f} final_sigma_mean_bp={sigma_full.mean()*1e4:.2f} persistence={alpha+beta:.2f}")
