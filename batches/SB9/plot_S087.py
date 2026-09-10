import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
from statsmodels.tsa.stattools import adfuller

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

rng = np.random.default_rng(2)  # fixed seed, stated in chapter text
TAU = 1e-5  # truncation tolerance (illustrative)


def fracdiff_weights(d, tau=TAU, maxk=5000):
    """FFD binomial weights: w_0=1, w_k = -w_{k-1}(d-k+1)/k, truncate at |w|<tau."""
    w = [1.0]
    k = 1
    while k <= maxk:
        wk = -w[-1] * (d - k + 1) / k
        w.append(wk)
        if abs(wk) < tau:
            break
        k += 1
    return np.array(w)


# ---- Synthetic log-price: random walk (unit root), T=5000 ----
T = 5000
logp = 5.0 + np.cumsum(rng.normal(0.0, 0.005, T))


def ffd(series, d):
    w = fracdiff_weights(d)
    y = np.convolve(series, w, mode="full")[:len(series)]
    return y, w


# ---- Panel 1 inputs: weights for d = 0.2 / 0.5 / 0.8 ----
ds_plot = [0.2, 0.5, 0.8]
winfo = {}
for d in ds_plot:
    w = fracdiff_weights(d)
    winfo[d] = (w, len(w) - 1)  # truncation lag L = first k with |w_k| < tau
    print(f"d={d}: truncation lag L={len(w)-1} at tau={TAU:g}")

# ---- Panel 2 inputs: memory (corr) vs stationarity (ADF p) across d ----
grid = np.arange(0.0, 1.001, 0.05)
corrs, pvals = [], []
for d in grid:
    y, w = ffd(logp, d)
    L = len(w) - 1
    yy = y[L:] if L < len(y) else y
    if len(yy) < 100:
        corrs.append(np.nan); pvals.append(np.nan); continue
    corrs.append(float(np.corrcoef(yy, logp[L:])[0, 1]))
    pvals.append(float(adfuller(yy, autolag="AIC", result_object=False)[1]))
corrs = np.array(corrs)
pvals = np.array(pvals)
passed = np.where(np.nan_to_num(pvals, nan=1.0) < 0.05)[0]
dstar = float(grid[passed[0]]) if len(passed) else float("nan")
print(f"d* (smallest d with ADF p<0.05) = {dstar:.2f}")
print(" d   |w_L|<tau?  ADF p    corr(x_tilde, logp)")
for d, pv, c in zip(grid, pvals, corrs):
    print(f"{d:4.2f}   {pv:8.4f}   {c:6.3f}")

# ---- Worked-example table: d=0.4 weights k=0..9 (hand-checkable recursion) ----
w04 = fracdiff_weights(0.4, tau=1e-3)  # illustrative tau for the table
print("d=0.4 weights k=0..9 (tau=1e-3 illustrative):")
print(np.array2string(w04[:10], precision=6, suppress_small=True))
# Medium/RAPIDS hand-check: values 100,99,98,97,96 at lags 0..4, d=0.4
vals = np.array([100., 99, 98, 97, 96])
wcheck = fracdiff_weights(0.4, tau=1e-12)[:5]
print(f"d=0.4 hand-check on [100..96]: {float(wcheck @ vals):.3f} "
      f"(hand arithmetic: 100-39.6-11.76-6.208-3.9936 = 38.438)")
print(f"d=0 identity check: {float(fracdiff_weights(0.0)[:1] @ np.array([123.45])):.2f}")
print(f"d=1 diff check: {float(np.array([1., -1.]) @ np.array([100., 99.])):.2f}")

# ---- Chart ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2))
ks = np.arange(0, 1001)
for d, col in zip(ds_plot, [PALETTE["price"], PALETTE["signal"], PALETTE["signal2"]]):
    w, L = winfo[d]
    wp = np.zeros(1001)
    wp[:min(len(w), 1001)] = w[:1001]
    ax1.plot(ks, wp, lw=2.0, color=col, label=f"d={d}")
    ax1.axvline(L, color=col, ls=":", lw=1.4)
    ax1.text(L + 12, -0.0006 - 0.0012 * ds_plot.index(d), f"L={L}", fontsize=9, color=col)
ax1.axhline(0, color=PALETTE["zero"], lw=1)
ax1.set_title("FFD weights w_k (|: truncation at |w|<τ)")
ax1.set_xlabel("Lag k")
ax1.set_ylabel("Weight w_k")
ax1.set_xlim(0, 1000)
ax1.legend(loc="lower right", title="τ = 1e-5")

ax2.plot(grid, corrs, color=PALETTE["price"], lw=2.2, label="corr(FFD, log-price) — memory")
ax2.plot(grid, pvals, color=PALETTE["signal"], lw=2.2, label="ADF p-value — stationarity")
ax2.axhline(0.05, color=PALETTE["zero"], ls="--", lw=1.5, label="ADF p = 0.05")
ax2.axvline(dstar, color=PALETTE["profit"], ls=":", lw=1.8)
ax2.annotate(f"d* = {dstar:.2f}", (dstar, 0.5), textcoords="offset points",
             xytext=(8, 10), fontsize=10, color=PALETTE["profit"], weight="bold")
ax2.set_title("Memory vs stationarity tradeoff (seed 2)")
ax2.set_xlabel("Fractional order d")
ax2.set_ylabel("Correlation / ADF p-value")
ax2.set_xlim(0, 1)
ax2.set_ylim(-0.05, 1.05)
ax2.legend(loc="center right")

fig.suptitle("S087 — Fractional differentiation: weights and the memory–stationarity tradeoff",
             fontsize=13, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S087_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
