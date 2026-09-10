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

# ---- SYNTHETIC DATA: exponential temporary-impact decay (seed 48) ----
rng = np.random.default_rng(48)
LAMBDA_Q = 10.0      # bps: temporary impact at t=0 (lambda*Q)
KAPPA = 0.05         # 1/s: true mean-reversion speed
HALF_TRUE = np.log(2) / KAPPA
t = np.arange(0, 61, 2.0)                 # seconds since shock, 2-s snapshots
true_impact = LAMBDA_Q * np.exp(-KAPPA * t)
obs_impact = true_impact + rng.normal(0, 0.8, size=t.shape)

# Fit: OLS on y = log|I| = log|LAMBDA_Q| - kappa*t
mask = obs_impact > 0
y = np.log(obs_impact[mask])
tt = t[mask]
slope, intercept = np.polyfit(tt, y, 1)
kappa_hat = -slope
lam_hat = np.exp(intercept)
half_hat = np.log(2) / kappa_hat
fit_impact = lam_hat * np.exp(-kappa_hat * t)

print(f"true kappa={KAPPA:.4f}, true half-life={HALF_TRUE:.2f}s")
print(f"fitted kappa_hat={kappa_hat:.4f}, lam_hat={lam_hat:.3f} bps, half_hat={half_hat:.2f}s")
for ti, oi, fi in zip(t, obs_impact, fit_impact):
    print(f"t={ti:5.1f}s  observed={oi:6.3f} bps  fitted={fi:6.3f} bps")

fig, ax = plt.subplots()
ax.scatter(t, obs_impact, s=34, color=PALETTE["signal"], alpha=0.85,
           label="Observed temporary impact (synthetic 2-s snapshots)")
ax.plot(t, true_impact, color=PALETTE["price"], lw=2.2, linestyle="--",
        label=f"True decay  I(t)=10·exp(-0.05t)  (half-life {HALF_TRUE:.1f}s)")
ax.plot(t, fit_impact, color=PALETTE["profit"], lw=2.0,
        label=f"Fitted OLS  Î(t)={lam_hat:.2f}·exp(-{kappa_hat:.3f}t)  (half-life {half_hat:.1f}s)")
ax.axvline(half_hat, color=PALETTE["signal2"], linestyle=":", lw=1.6)
ax.annotate(f"fitted half-life\n{half_hat:.1f}s", xy=(half_hat, fit_impact[np.argmin(np.abs(t - half_hat))]),
            xytext=(half_hat + 16, 8.6), fontsize=9, color=PALETTE["signal2"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["signal2"]))
ax.set_xlabel("Seconds since liquidity shock t")
ax.set_ylabel("Temporary price impact I(t) (bps)")
ax.set_title("S048 — LOB resiliency: exponential temporary-impact decay (synthetic)")
ax.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S048_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
