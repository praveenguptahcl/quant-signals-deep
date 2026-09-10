"""Plot + worked-example generator for S008 (VPIN, bar-level BVC).

Follows Easley-Lopez de Prado-O'Hara: classification is at the VOLUME-BAR level.
Within each equal-volume bar tau, with bar price change dP_tau = P_last,tau -
P_last,tau-1 and sigma = std of bar price changes:
    V^B_tau = V * Phi(dP_tau / sigma),   V^S_tau = V - V^B_tau
Buckets hold EXACTLY V shares: trades straddling a bucket boundary are split
(ELO convention). VPIN over n bars = sum |OI| / (n * V).

Run with cwd=~/workspace/quant-signals-deep.
"""
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

# ---- Synthetic trade tape: trade 0 is the reference price for bar 1's dP ----
NTR = 120
prices = np.empty(NTR)
prices[0] = 100.00
prices[1:] = np.round(100.00 + np.cumsum(rng.normal(0, 0.015, NTR - 1)), 2)
sizes = rng.integers(20, 150, size=NTR)

V = 500          # bucket size in shares — every bucket holds EXACTLY V
NB = 10          # number of buckets

# Volume-clock bucketing with boundary trades split (ELO convention)
closes = []      # closing (last-trade) price of each bucket
fill = 0.0
for v, p in zip(sizes[1:], prices[1:]):
    need = V - fill
    if v < need:
        fill += v
    else:
        closes.append(float(p))   # this trade's price closes the bucket
        fill = v - need           # remainder starts the next bucket
        if len(closes) == NB:
            break
assert len(closes) == NB, "tape too short for 10 buckets"

dP = np.diff(np.concatenate([[prices[0]], closes]))  # bar price changes ($)
sigma = float(dP.std(ddof=1))

def Phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

frac = np.array([Phi(d / sigma) for d in dP])
VB = V * frac
VS = V - VB
OI = np.abs(VB - VS)
ratio = OI / V

# Rolling VPIN over n=4 buckets (example — not an institutional standard)
n = 4
vpin = np.array([OI[i - n + 1:i + 1].sum() / (n * V) for i in range(n - 1, NB)])

print(f"sigma(bar dP) = {sigma:.5f}  (ddof=1 over the {NB} bar price changes)")
print("bucket | V(sh) | dP($)  | Phi(dP/s) | Vbuy   | Vsell  | |OI|   | |OI|/V")
for i in range(NB):
    print(f"{i+1:>2} | {V:>5d} | {dP[i]:+6.3f} | {frac[i]:9.4f} | {VB[i]:6.1f} | "
          f"{VS[i]:6.1f} | {OI[i]:6.1f} | {ratio[i]:.3f}")
for i, v in enumerate(vpin, n):
    print(f"VPIN rolling n={n} ending at bucket {i}: {v:.4f}")
print(f"max VPIN = {vpin.max():.4f} vs example gate 0.30 -> "
      f"{'FIRES' if vpin.max() > 0.30 else 'never fires'}")

# ---- Plot: per-bucket imbalance ratio bars + rolling VPIN line (0..1 axis) ----
x = np.arange(1, NB + 1)
fig, ax = plt.subplots()
ax.bar(x, ratio, color=PALETTE["volume"], alpha=0.8,
       label="Bucket imbalance |Vbuy-Vsell|/V (bar-level BVC)")
ax.plot(np.arange(n, NB + 1), vpin, color=PALETTE["signal"], marker="o",
        linewidth=2.4, label=f"VPIN, rolling {n} buckets")
ax.axhline(0.30, color=PALETTE["signal2"], linestyle="--", linewidth=1.2,
           label="Toxicity gate (example threshold 0.30)")
ax.set_ylim(0, 1.05)
ax.set_title("S008 — VPIN flow toxicity: 10 equal-volume synthetic buckets (bar-level BVC)")
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
