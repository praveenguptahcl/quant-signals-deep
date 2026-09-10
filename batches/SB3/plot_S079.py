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

rng = np.random.default_rng(79)  # SEED 79 — stated in chapter text

# ---- synthetic 2-state Gaussian HMM tape (5-min bars) ----
mu  = np.array([0.0003, -0.0005])   # calm / volatile mean log-return
sig = np.array([0.004,  0.012])    # calm / volatile stdev
A   = np.array([[0.97, 0.03],       # rows = from-state
                [0.08, 0.92]])
n = 120
states = np.zeros(n, dtype=int)
for t in range(1, n):
    states[t] = 0 if rng.random() < A[states[t - 1], 0] else 1
r = mu[states] + sig[states] * rng.standard_normal(n)
price = 100.0 * np.cumprod(1.0 + r)

def gauss(x, m, s):
    return np.exp(-0.5 * ((x - m) / s) ** 2) / (s * np.sqrt(2 * np.pi))

# forward algorithm (FILTERED probabilities — no future data)
pi0 = np.array([(1 - A[1, 1]) / ((1 - A[0, 0]) + (1 - A[1, 1])),
                (1 - A[0, 0]) / ((1 - A[0, 0]) + (1 - A[1, 1]))])
alpha = np.zeros((n, 2))
alpha[0] = pi0 * gauss(r[0], mu, sig)
alpha[0] /= alpha[0].sum()
for t in range(1, n):
    alpha[t] = (alpha[t - 1] @ A) * gauss(r[t], mu, sig)
    alpha[t] /= alpha[t].sum()
pfilt_vol = alpha[:, 1]

# ---- print worked-example table (bars 40..51) for the chapter ----
print("bar | r_t (bp) | true state | P(volatile|data) | rule action")
for i in range(39, 51):
    p = pfilt_vol[i]
    action = "SUSPEND entries" if p > 0.8 else ("halve size" if p > 0.7 else "full size")
    print(f"{i+1:>3} | {r[i]*1e4:>8.2f} | {'volatile' if states[i] else 'calm    '} | {p:>16.4f} | {action}")

# ---- one hand-checkable recursion step (bar 46, 1-indexed; idx 45) ----
i = 45
pred = alpha[i - 1] @ A
lik = gauss(r[i], mu, sig)
print("\nHand-check bar 46:")
print(f"  filtered bar45: calm={alpha[i-1,0]:.6f} vol={alpha[i-1,1]:.6f}")
print(f"  predicted 46 : calm={pred[0]:.6f} vol={pred[1]:.6f}")
print(f"  r46 = {r[i]*1e4:.2f} bp; likelihood calm={lik[0]:.4f} vol={lik[1]:.4f}")
print(f"  filtered bar46: calm={alpha[i,0]:.6f} vol={alpha[i,1]:.6f}")
print(f"E[D_calm]={1/(1-A[0,0]):.2f} bars; E[D_vol]={1/(1-A[1,1]):.2f} bars")

# ---- chart ----
fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 2]})
bars = np.arange(1, n + 1)
ax1.plot(bars, price, color=PALETTE["price"], lw=1.4, label="synthetic price (index pts)")
for t in range(n):
    if states[t] == 1:
        ax1.axvspan(bars[t] - 0.5, bars[t] + 0.5, color=PALETTE["signal"], alpha=0.08)
ax1.set_ylabel("price (synthetic pts)")
ax1.legend(loc="upper left")
ax1.set_title("S079 — HMM regime-switching: 120-bar synthetic 5-min tape (seed 79)")

ax2.plot(bars, pfilt_vol, color=PALETTE["signal"], lw=1.4, label="filtered P(volatile)")
ax2.axhline(0.7, color=PALETTE["zero"], ls="--", lw=1, label="halve-size threshold 0.7 (example)")
ax2.axhline(0.8, color=PALETTE["loss"], ls=":", lw=1, label="suspend threshold 0.8 (example)")
ax2.fill_between(bars, 0.7, 1.0, where=pfilt_vol > 0.7, color=PALETTE["signal"], alpha=0.15)
ax2.set_xlabel("5-min bar index")
ax2.set_ylabel("filtered probability")
ax2.set_ylim(0, 1.02)
ax2.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S079_example.png", bbox_inches="tight")
plt.close()
