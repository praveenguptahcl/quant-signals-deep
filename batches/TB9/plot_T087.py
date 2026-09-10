import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
import os

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

rng = np.random.default_rng(187)  # T087 seed — stated in chapter text

# ---- T087 worked-example inputs (SYNTHETIC) ----
# 5 sub-strategies with CPCV haircut scores (example):
#   score_i = median_j(PSR_j) - 0.5*IQR_j(PSR_j); negative -> ineligible
names = ["S1 scalp", "S2 breakout", "S3 reversal", "S4 news", "S5 vol"]
s = np.array([1.40, 0.85, 0.20, -0.30, 0.55])
tau, cash = 0.40, 0.10  # softmax temperature and cash sleeve (example)
eligible = s >= 0
e = np.exp(s[eligible] / tau)
w_raw = e / e.sum()
w = np.zeros_like(s); w[eligible] = (1 - cash) * w_raw
print("haircut scores:", s)
print("exp(s/tau):", np.round(e, 2), "sum:", round(e.sum(), 2))
print("raw weights:", np.round(w_raw, 4))
print("final weights (cash 10%):", np.round(w, 4), "sum:", round(w.sum() + cash, 4))
NAV = 1_000_000
notional = w * NAV
for n_, wi, ni in zip(names, w, notional):
    print(f"{n_}: w={wi:.4f} -> ${ni:,.0f}")
print(f"cash sleeve: {cash:.0%} -> ${cash*NAV:,.0f}")
# Synthetic next-week sleeve outcome (illustrative weighting math, NOT forward alpha):
ret = np.array([0.012, -0.004, 0.021, 0.0, 0.006])
sleeve = float(np.sum(w * ret) * NAV)
print("next-week returns:", ret, "-> sleeve P&L = $", round(sleeve, 2))

# Synthetic CPCV path scores for the dispersion panel (10 paths x 4 eligible strategies):
paths = np.stack([
    np.clip(rng.normal(1.40, 0.55, 10), -1, 3),
    np.clip(rng.normal(0.85, 0.30, 10), -1, 3),
    np.clip(rng.normal(0.20, 0.25, 10), -1, 3),
    np.clip(rng.normal(0.55, 0.40, 10), -1, 3),
])
med = np.median(paths, axis=1); q1 = np.percentile(paths, 25, axis=1); q3 = np.percentile(paths, 75, axis=1)
print("path medians:", np.round(med, 2), "IQR:", np.round(q3 - q1, 2))

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2))
fig.suptitle("T087 — Purged-CV Strategy Selector: synthetic CPCV scores -> softmax weights (seed 187)",
             fontweight="bold")
eli_names = [n for n, ok in zip(names, eligible) if ok]
y = np.arange(len(eli_names))
ax1.errorbar(med, y, xerr=[med - q1, q3 - med], fmt="o", color=PALETTE["price"],
             ecolor=PALETTE["volume"], elinewidth=2, capsize=4, label="median +/- IQR (10 CPCV paths)")
for i, yi in enumerate(y):
    ax1.scatter(paths[i], np.full(10, yi) + rng.normal(0, 0.06, 10), color=PALETTE["band"],
                s=18, alpha=0.8, zorder=1)
ax1.axvline(0, color=PALETTE["signal"], ls="--", lw=1, label="eligibility floor (score=0)")
ax1.set_yticks(y); ax1.set_yticklabels(eli_names)
ax1.set_xlabel("haircut score = median(PSR) - 0.5 x IQR")
ax1.set_title("CPCV path dispersion (synthetic)", fontsize=11)
ax1.legend(loc="lower right", fontsize=8)
ax1.text(0.02, 0.96, "S4 excluded: score -0.30 < 0", transform=ax1.transAxes, fontsize=8,
         color=PALETTE["signal"], fontweight="bold", va="top",
         bbox=dict(boxstyle="round", fc="white", alpha=0.9))

all_names = names + ["cash"]
all_w = list(w) + [cash]
cols = [PALETTE["signal"] if wi == 0 else PALETTE["profit"] for wi in all_w]
ax2.barh(all_names, all_w, color=cols)
for i, wi in enumerate(all_w):
    lbl = "excluded" if wi == 0 else f"{wi:.1%}  (${wi*NAV:,.0f})"
    ax2.text(wi + 0.012, i, lbl, va="center", fontsize=8)
ax2.set_xlabel("final weight (softmax tau=0.40, cash 10%)")
ax2.set_title(f"allocation on $1M NAV; sleeve week +${sleeve:,.0f} (synthetic)", fontsize=11)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T087_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
