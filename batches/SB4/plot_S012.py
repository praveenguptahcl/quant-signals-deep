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

# ---- synthetic worked-example tape (hardcoded; matches S012.md S4) ----
rng = np.random.default_rng(12)  # fixed seed; tape values are hardcoded below
p = np.array([100.00, 100.10, 100.10, 100.20, 100.10, 100.00,
              100.00, 99.90, 100.00, 100.10, 99.90, 100.00])  # trade prices ($)
dp = np.diff(p)  # 11 price changes
assert abs(dp.sum()) < 1e-9, "corrected: Δp sums to 0, mean = 0 (bot mis-summed as −0.10)"
prods = dp[1:] * dp[:-1]  # 10 lag-1 cross-products
assert abs(prods.sum() - (-0.04)) < 1e-9
gamma1 = float(prods.sum() / 10)  # = −0.004  (corrected; bot said −0.00402)
spread = float(2 * np.sqrt(-gamma1))  # ≈ $0.126 (corrected; bot said $0.127)
assert abs(gamma1 - (-0.004)) < 1e-12
assert abs(spread - 0.1264911064) < 1e-6

fig, ax = plt.subplots()
t = np.arange(1, len(dp) + 1)
colors = [PALETTE["profit"] if v >= 0 else PALETTE["loss"] for v in dp]
ax.bar(t, dp, color=colors, edgecolor=PALETTE["zero"], linewidth=0.6, zorder=3,
       label="Δp_t (trade-price change, $)")
ax.axhline(0, color=PALETTE["zero"], lw=1.0)
ax.set_title("S012 — Roll implied spread: 11-change synthetic trade-price series")
ax.set_xlabel("trade index t (Δp_t = p_t − p_{t−1})")
ax.set_ylabel("price change Δp ($)")
ax.set_xticks(t)
ax.legend(loc="upper right")
ax.text(0.02, 0.98,
        f"ΣΔp = 0  ⇒  mean = 0  (bot error: −0.10/11 = −0.00909)\n"
        f"γ̂₁ = Σ Δp_t·Δp_t₋₁ / 10 = −0.04/10 = −0.004  (bot: −0.00402)\n"
        f"implied spread = 2√(−γ̂₁) = 2√0.004 ≈ ${spread:.3f}  (bot: $0.127)",
        transform=ax.transAxes, va="top", ha="left", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=PALETTE["price"], alpha=0.92))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S012_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S012_example.png, γ̂₁ =", gamma1, "spread ≈", round(spread, 4))
