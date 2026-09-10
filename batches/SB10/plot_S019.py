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

rng = np.random.default_rng(19)  # seed 19; tape below is fixed, script regenerates it exactly

# ---- S019 worked-example tape (fixed synthetic tape; bucket cutoffs are illustrative) ----
# columns: trade $, signed size direction (+1 buy / -1 sell), midprice change $
trades = [
    # small bucket: <$10k notional (example cutoff)
    ( 3000, +1, +0.010),
    ( 2500, -1, +0.012),
    ( 4000, +1, -0.008),
    ( 2000, -1, -0.010),
    # medium bucket: $10k-$50k (example cutoff)
    (20000, +1, +0.020),
    (15000, +1, +0.025),
    (30000, +1, +0.015),
    (12000, +1, +0.030),
    (25000, +1, +0.010),
    # large bucket: >$50k (example cutoff)
    ( 80000, +1, +0.005),
    (120000, -1, +0.004),
    ( 60000, +1, -0.006),
]
trades = np.array(trades, dtype=float)
notional, direction, dm = trades[:, 0], trades[:, 1], trades[:, 2]
signed_impact = direction * notional * dm  # q_k * dM_k  ($)

def bucket(v):
    if v < 10000: return 0
    if v <= 50000: return 1
    return 2
names = ["small\n(<$10k)", "medium\n($10k-$50k)", "large\n(>$50k)"]
bidx = np.array([bucket(v) for v in notional])

n_tr, vol, abs_imp = [], [], []
for b in range(3):
    m = bidx == b
    n_tr.append(m.sum())
    vol.append(notional[m].sum())
    abs_imp.append(np.abs(signed_impact[m]).sum())
n_tr, vol, abs_imp = map(np.array, (n_tr, vol, abs_imp))
trade_share = 100 * n_tr / n_tr.sum()
vol_share = 100 * vol / vol.sum()
imp_share = 100 * abs_imp / abs_imp.sum()
for i, nm in enumerate(["small", "medium", "large"]):
    print(f"{nm}: n={int(n_tr[i])} vol=${vol[i]:,.0f} |impact|=${abs_imp[i]:,.0f} "
          f"trade_share={trade_share[i]:.1f}% vol_share={vol_share[i]:.1f}% impact_share={imp_share[i]:.1f}%")
print(f"medium excess vs trades: {imp_share[1]-trade_share[1]:+.1f}pp; vs volume: {imp_share[1]-vol_share[1]:+.1f}pp")

x = np.arange(3)
w = 0.26
ax = plt.gca()
ax.bar(x - w, trade_share, w, label="trade share %", color=PALETTE["price"])
ax.bar(x, vol_share, w, label="volume share %", color=PALETTE["volume"])
bars = ax.bar(x + w, imp_share, w, label="|impact| share %", color=PALETTE["signal"])
ax.set_xticks(x)
ax.set_xticklabels(names)
ax.set_xlabel("size bucket (cutoffs are illustrative examples, not standards)")
ax.set_ylabel("share of total (%)")
ax.set_title("S019 — Stealth trading: medium bucket carries excess price impact (synthetic 12-trade tape)")
ax.legend(loc="upper left")
ax.set_ylim(0, 75)
for i in range(3):
    ax.text(i + w, imp_share[i] + 1.5, f"{imp_share[i]:.1f}%", ha="center", fontsize=9,
            weight="bold", color=PALETTE["signal"])
ax.annotate("stealth signature:\n57.6% of impact from\n41.7% of trades, 27.3% of volume",
            xy=(1 + w, imp_share[1]), xytext=(1.9, 62),
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
            fontsize=9, color=PALETTE["zero"],
            bbox=dict(boxstyle="round", fc="white", ec=PALETTE["zero"]))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S019_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S019_example.png")
