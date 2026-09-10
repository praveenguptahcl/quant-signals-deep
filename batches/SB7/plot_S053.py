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

# ---- SYNTHETIC PAIRS (seed stated in chapter) ----
# Formation (250 daily bars): Pair A = fast OU (many zero crossings -> quality);
# Pair B = slow OU with huge excursions (few crossings -> rejected by the gate).
nf, nt = 250, 250

def ou_path(n, kappa, sigma, seed, s0=0.0):
    rng = np.random.default_rng(seed)
    s = np.empty(n); s[0] = s0
    for i in range(1, n):
        s[i] = s[i - 1] + kappa * (0.0 - s[i - 1]) + rng.normal(0.0, sigma)
    return s

def crossings(s):
    return int((np.sign(s[:-1]) * np.sign(s[1:]) < 0).sum())

formA = ou_path(nf, kappa=0.30, sigma=1.0, seed=7)
formB = ou_path(nf, kappa=0.005, sigma=1.0, seed=7)
cA, cB = crossings(formA), crossings(formB)
GATE = 20  # example quality-gate threshold (illustrative — not an institutional standard)
print(f"formation crossings: A={cA} B={cB} gate>={GATE}")

# Trading period: A keeps mean-reverting; B suffers a mean shift +2.5 (regime break).
tradeA = ou_path(nt, kappa=0.30, sigma=1.0, seed=99, s0=formA[-1])
tradeB = ou_path(nt, kappa=0.005, sigma=1.0, seed=99, s0=formB[-1]) + 2.5
tA, tB = crossings(tradeA), crossings(tradeB)
print(f"trading crossings: A={tA} B={tB}; B trading range {tradeB.min():.2f}..{tradeB.max():.2f}")

# ---- worked-example rows: first 12 formation obs of Pair A ----
print("t, s_t, sign, crossing?, cum_crossings")
cum = 0
for i in range(12):
    sgn = int(np.sign(formA[i]))
    xing = i > 0 and np.sign(formA[i - 1]) != 0 and sgn != 0 \
        and np.sign(formA[i - 1]) * sgn < 0
    cum += xing
    print(f"{i+1},{formA[i]:+.4f},{sgn:+d},{'YES' if xing else 'no'},{cum}")

# ---- plots ----
fig, axes = plt.subplots(1, 2)

t = np.arange(1, nf + 1)
axes[0].plot(t, formA, color=PALETTE["price"], lw=1.2, label="Pair A spread (fast OU)")
axes[0].plot(t, formB, color=PALETTE["signal2"], lw=1.2, alpha=0.9,
             label="Pair B spread (slow OU)")
axes[0].axhline(0, color=PALETTE["zero"], lw=1)
zcA = np.where(np.sign(formA[:-1]) * np.sign(formA[1:]) < 0)[0] + 1
zcB = np.where(np.sign(formB[:-1]) * np.sign(formB[1:]) < 0)[0] + 1
axes[0].plot(zcA, np.zeros_like(zcA), "o", color=PALETTE["profit"], ms=4,
             label=f"Pair A crossings (n={cA})")
axes[0].plot(zcB, np.zeros_like(zcB), "s", color=PALETTE["loss"], ms=5,
             label=f"Pair B crossings (n={cB})")
axes[0].set_title(f"Formation: zero crossings vs gate >= {GATE}")
axes[0].set_xlabel("t (synthetic daily bars)")
axes[0].set_ylabel("spread (normalized units)")
axes[0].legend(loc="upper right", fontsize=8)

t2 = np.arange(nf + 1, nf + nt + 1)
axes[1].plot(t2, tradeA, color=PALETTE["profit"], lw=1.2,
             label=f"Pair A (gate PASS): {tA} crossings")
axes[1].plot(t2, tradeB, color=PALETTE["loss"], lw=1.2,
             label=f"Pair B (gate FAIL): {tB} crossings, wild excursions")
axes[1].axhline(0, color=PALETTE["zero"], lw=1)
axes[1].axhline(2, color=PALETTE["signal"], ls="--", lw=1, alpha=0.7)
axes[1].axhline(-2, color=PALETTE["signal"], ls="--", lw=1, alpha=0.7)
axes[1].set_title("Trading period: A keeps converging; B breaks")
axes[1].set_xlabel("t (synthetic daily bars)")
axes[1].set_ylabel("spread (normalized units)")
axes[1].legend(loc="upper left", fontsize=8)

fig.suptitle("S053 — Do–Faff zero-crossing quality filter (synthetic formation)",
             fontsize=13, weight="bold")
fig.text(0.5, 0.965, f"Quality gate (example): trade pairs with >= {GATE} formation "
                      "crossings — Pair A passes, Pair B is rejected",
         ha="center", fontsize=9, style="italic", color=PALETTE["zero"])

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S053_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
