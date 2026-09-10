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

# ---- S017 synthetic worked example: bivariate exponential Hawkes intensities ----
SEED = 1717
rng = np.random.default_rng(SEED)

DT = 5.0          # seconds per bin (event-time grid coarsened to 5-s bins)
N = 120           # 600 s = 10 minutes
MU = 0.5          # baseline events per bin per side
ALPHA = 0.6       # excitation per buy/sell event
HALF_LIFE = 30.0  # seconds — excitation half-life (example, not an institutional standard)
DECAY = np.exp(-np.log(2) * DT / HALF_LIFE)  # per-bin decay factor

# Synthetic event tape: baseline Poisson + one self-excitation "burst" episode
# (e.g. an algo child-order burst) in bins 60..71.
t = np.arange(N) * DT
x_b = rng.poisson(MU, N).astype(float)
x_s = rng.poisson(MU, N).astype(float)
burst_extra = 5.0 * np.exp(-(np.arange(N) - 60) / 4.0)
burst_extra[:60] = 0.0
burst_extra[72:] = 0.0
x_b += rng.poisson(burst_extra)

# Bivariate exponential recursion: kappa_{t+1} = decay*(kappa_t + alpha*x_t); lam_t = mu + kappa_t
def hawkes_intensity(x):
    kappa = 0.0
    lam = np.zeros_like(x)
    for i in range(N):
        lam[i] = MU + kappa
        kappa = DECAY * (kappa + ALPHA * x[i])
    return lam

lam_b = hawkes_intensity(x_b)
lam_s = hawkes_intensity(x_s)
imb = lam_b - lam_s
z = (imb - imb.mean()) / imb.std()

# Worked-example table: bins 58..67 around the burst onset (numbers the chapter reproduces)
rows = []
for i in range(58, 68):
    rows.append((t[i], x_b[i], x_s[i], lam_b[i], lam_s[i], z[i]))
print("bin_t(s) | x_b | x_s | lam_b | lam_s | z")
for r in rows:
    print(f"{r[0]:7.0f} | {r[1]:3.0f} | {r[2]:3.0f} | {r[3]:5.3f} | {r[4]:5.3f} | {r[5]:+5.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 5.2))
ax1.plot(t, lam_b, color=PALETTE["profit"], lw=1.6, label="λ⁺(t) buy intensity")
ax1.plot(t, lam_s, color=PALETTE["loss"], lw=1.6, label="λ⁻(t) sell intensity")
ax1.axvspan(300, 360, color=PALETTE["band"], alpha=0.45, label="burst episode")
ax1.axhline(MU, color=PALETTE["zero"], ls=":", lw=1.0, label="baseline μ")
ax1.set_ylabel("intensity λ (events / 5 s)")
ax1.set_title("S017 — Hawkes self-excitation intensity: synthetic buy/sell event tape with burst")
ax1.legend(loc="upper left", ncol=2)

ax2.plot(t, z, color=PALETTE["signal"], lw=1.6, label="signal z = (λ⁺−λ⁻) z-scored")
ax2.axhline(2.0, color=PALETTE["zero"], ls="--", lw=1.0)
ax2.axhline(-2.0, color=PALETTE["zero"], ls="--", lw=1.0)
ax2.axhline(0.0, color=PALETTE["zero"], ls=":", lw=1.0)
ax2.text(605, 1.7, "+2 threshold (example)", ha="right", va="bottom", fontsize=8)
ax2.set_xlabel("time (s)")
ax2.set_ylabel("imbalance z-score")
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S017_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S017_example.png")
