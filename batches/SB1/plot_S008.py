import math
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

rng = np.random.default_rng(7)  # seed 7 — stated in chapter text

NB, PER = 10, 6  # 10 volume buckets, 6 trades per bucket (synthetic)
dp_all = rng.normal(0, 0.015, size=(NB, PER))      # price changes per trade
sizes_all = rng.integers(20, 150, size=(NB, PER))  # trade sizes
sigma = dp_all.std(ddof=1)

def Phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

V, B, S = [], [], []
for b in range(NB):
    bv = sum(v * Phi(dp / sigma) for v, dp in zip(sizes_all[b], dp_all[b]))
    tot = float(sizes_all[b].sum())
    V.append(tot); B.append(bv); S.append(tot - bv)
V, B, S = map(np.array, (V, B, S))
OI = np.abs(B - S)
ratio = OI / V

# Rolling VPIN over n=4 buckets (example — not an institutional standard)
n = 4
vpin = np.array([OI[i-n+1:i+1].sum() / V[i-n+1:i+1].sum() for i in range(n-1, NB)])

# Print the worked-example table (copy into chapter S4)
print(f"sigma(dp)={sigma:.5f}")
print("bucket | Vtot | Vbuy | Vsell | |OI| | |OI|/V")
for i in range(NB):
    print(f"{i+1:>2} | {V[i]:>5.0f} | {B[i]:>6.1f} | {S[i]:>6.1f} | {OI[i]:>6.1f} | {ratio[i]:.3f}")
for i, v in enumerate(vpin, n):
    print(f"VPIN rolling n=4 ending at bucket {i}: {v:.4f}")

# ---- Plot: per-bucket imbalance ratio bars + rolling VPIN line (0..1 axis) ----
x = np.arange(1, NB + 1)
fig, ax = plt.subplots()
ax.bar(x, ratio, color=PALETTE["volume"], alpha=0.8,
       label="Bucket imbalance |Vbuy−Vsell|/V (BVC)")
ax.plot(np.arange(n, NB + 1), vpin, color=PALETTE["signal"], marker="o",
        linewidth=2.4, label=f"VPIN, rolling {n} buckets")
ax.axhline(0.30, color=PALETTE["signal2"], linestyle="--", linewidth=1.2,
           label="Toxicity gate (example threshold 0.30)")
ax.set_ylim(0, 1.05)
ax.set_title("S008 — VPIN flow toxicity: 10 synthetic volume buckets (BVC classification)")
ax.set_xlabel("Volume bucket # (equal-volume, event time)")
ax.set_ylabel("Imbalance ratio / VPIN (0–1)")
ax.set_xticks(x)
ax.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S008_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S008_example.png")
