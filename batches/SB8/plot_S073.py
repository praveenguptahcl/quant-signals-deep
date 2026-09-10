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

rng = np.random.default_rng(73)  # fixed seed — reproducible

# 8 synthetic contracts for fictional name "ABC" (one session). Columns:
# contract | type | volume | open interest | trailing-20d median volume | premium ($k)
contracts = ["ABC 100C", "ABC 105C", "ABC 95P", "ABC 90P",
             "ABC 110C", "ABC 102C", "ABC 97P", "ABC 85P"]
cp = np.array(["C", "C", "P", "P", "C", "C", "P", "P"])
oi = np.array([8200, 3100, 5400, 2900, 1500, 6600, 4200, 1200])
vol = np.array([9800, 2600, 7100, 1600, 340, 5100, 2200, 610])
med_hist = np.array([2100, 2400, 2300, 1700, 1500, 4800, 2000, 900])
premium_k = np.array([186.0, 41.0, 128.0, 24.0, 6.0, 97.0, 33.0, 8.0])

U = vol / med_hist                      # standardized unusual-volume score
vol_oi = vol / oi                        # volume / open interest (example >1.5 flag)
order = np.argsort(-U)
contracts_s = [contracts[i] for i in order]
U_s = U[order]
vol_oi_s = vol_oi[order]

colors = [PALETTE["signal"] if U_s[i] >= 2.0 else PALETTE["volume"] for i in range(len(U_s))]

plt.figure()
bars = plt.bar(range(len(U_s)), U_s, color=colors, edgecolor=PALETTE["zero"])
plt.axhline(2.0, color=PALETTE["signal2"], ls="--", lw=1.5,
            label="Unusual threshold U = 2.0 (example — not a standard)")
plt.xticks(range(len(U_s)), contracts_s, rotation=18, ha="right")
plt.ylabel("U = volume / trailing-20d median volume")
plt.title("S073 — Unusual options activity: ranked synthetic scan (open/close flag MISSING)")
plt.legend(loc="upper right")
# Flag the top hit's ambiguity directly on the chart
plt.annotate("Top hit: bought-or-sold?\nopened-or-closed?\nOPRA prints lack the flag",
             xy=(0, U_s[0]), xytext=(3.2, U_s[0] * 0.94),
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
             fontsize=9, color=PALETTE["signal"], weight="bold")
for i, v in enumerate(U_s):
    plt.text(i, v + 0.06, f"{v:.1f}x", ha="center", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S073_example.png", bbox_inches="tight")
plt.close()

print("S073 worked-example table (ranked by U), seed 73:")
print("contract  | type | volume | OI   | med_vol | U     | vol/OI | premium($k)")
for i in order:
    print(f"{contracts[i]:<9} | {cp[i]:>3} | {vol[i]:>6} | {oi[i]:>4} | {med_hist[i]:>7} | {U[i]:.2f}x | {vol_oi[i]:.2f}  | {premium_k[i]:.1f}")
