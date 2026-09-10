"""S071 worked-example chart — synthetic 25-delta risk-reversal skew curve (seed 71)."""
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

# ---- SYNTHETIC WORKED EXAMPLE (seed 71) ----
# Synthetic equity skew (smirk): IV falls as moneyness rises. BS deltas are
# illustrative example inputs (T = 30d, q = 1.5%, S = 100) so the 25-delta
# points can be identified without a solver in the worked example.
rng = np.random.default_rng(71)
mny = np.array([0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20])  # K/S
iv = np.array([34.0, 30.0, 26.5, 22.0, 19.5, 17.8, 16.9, 16.5, 16.3])    # IV %
# BS deltas are illustrative example inputs for the same 30-day expiry (puts for
# K < S, calls for K >= S), chosen so the 25-delta put sits at 0.90 and the
# 25-delta call at 1.10.
delta = np.array([-0.08, -0.15, -0.25, -0.40, 0.50, 0.38, 0.25, 0.14, 0.08])
rr_call = iv[6]   # IV at 25-delta call (mny 1.10)
rr_put = iv[2]    # IV at 25-delta put  (mny 0.90)
rr_25 = rr_call - rr_put            # FX/desk convention: call - put
rr_25_putminuscall = rr_put - rr_call  # equity-desk flip: put - call (positive = crash fear)
bfly = iv[6] + iv[2] - 2 * iv[4]    # 25-delta butterfly
print("moneyness   IV%   delta")
for m, v, d in zip(mny, iv, delta):
    mark = "  <-- 25-delta" if abs(abs(d) - 0.25) < 1e-9 else ""
    print(f"{m:9.2f}  {v:5.1f}  {d:+6.2f}{mark}")
print(f"RR_25 (call-put) = {rr_call:.1f} - {rr_put:.1f} = {rr_25:+.1f} vol pts")
print(f"RR_25 (put-call flip) = {rr_25_putminuscall:+.1f} vol pts (positive = downside fear)")
print(f"butterfly = {bfly:+.1f} vol pts")

plt.plot(mny, iv, marker="o", color=PALETTE["price"], label="Implied vol by moneyness (30d expiry)")
plt.scatter([1.10], [16.9], s=160, color=PALETTE["profit"], zorder=5,
            label="25Δ call (IV 16.9%)")
plt.scatter([0.90], [26.5], s=160, color=PALETTE["signal"], zorder=5,
            label="25Δ put (IV 26.5%)")
plt.scatter([1.00], [19.5], s=100, color=PALETTE["signal2"], zorder=5,
            label="ATM (IV 19.5%)")
plt.annotate("", xy=(1.10, 16.9), xytext=(0.90, 26.5),
             arrowprops=dict(arrowstyle="<->", color=PALETTE["zero"], lw=1.8))
plt.text(1.0, 22.3, "RR_25 = 16.9 − 26.5 = −9.6 vol pts\n(downside puts richer)",
         ha="center", fontsize=9, color=PALETTE["zero"],
         bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#bbbbbb", alpha=0.9))
plt.title("S071 — Equity skew: 25Δ risk-reversal points on a synthetic smile")
plt.xlabel("Moneyness (strike / spot)")
plt.ylabel("Implied volatility (%)")
plt.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S071_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
