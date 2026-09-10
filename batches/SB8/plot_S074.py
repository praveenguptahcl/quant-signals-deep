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

rng = np.random.default_rng(74)  # fixed seed — reproducible (script scaffold; numbers are the verified worked example)

# VERIFIED worked example: 5-strike synthetic chain, S=100, M=100
# GEX(K) = Gamma(K) * NetOI(K) * M * S^2 * 0.01 ; M*S^2*0.01 = 10,000
strikes = np.array([90, 95, 100, 105, 110])
gamma   = np.array([0.020, 0.025, 0.030, 0.028, 0.022])
net_oi  = np.array([800, -500, 300, -200, 100])   # OI_C - OI_P (sign convention = ASSUMPTION)
gex = gamma * net_oi * 10000.0
total = gex.sum()
print("S074 worked-example verification, seed 74:")
for k, g, n, v in zip(strikes, gamma, net_oi, gex):
    print(f"K={k}: {g:.3f} x {n:+d} x 10,000 = ${v:+,.0f}")
print(f"GEX_total = ${total:+,.0f}")
assert all(abs(a - b) < 1e-6 for a, b in zip(gex, [160000, -125000, 90000, -56000, 22000]))
assert abs(total - 91000) < 1e-6

colors = [PALETTE["profit"] if v > 0 else PALETTE["loss"] for v in gex]
plt.figure()
bars = plt.bar(strikes.astype(str), gex / 1000.0, color=colors, edgecolor=PALETTE["zero"], width=0.62)
plt.axhline(0, color=PALETTE["zero"], lw=1)
plt.axhline(total / 1000.0, color=PALETTE["signal2"], ls="--", lw=1.5,
            label=f"GEX total = ${total:,.0f} (1% move P&L)")
for k, v in zip(strikes, gex):
    plt.text(str(k), v / 1000.0 + (6 if v > 0 else -10), f"${v/1000:+.0f}k",
             ha="center", fontsize=9, weight="bold")
# Gamma walls = top-2 by |GEX| (modest framing: visual only, little OOS value)
walls = np.argsort(-np.abs(gex))[:2]
plt.annotate("Gamma walls (top-2 by |GEX|)\n= K90, K95 — visual only,\nlittle OOS forecasting value",
             xy=(str(90), gex[0] / 1000.0), xytext=("95", 205),
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             fontsize=9, color=PALETTE["zero"])
plt.title("S074 — Gamma exposure: verified 5-strike synthetic chain (S = 100)")
plt.xlabel("Strike")
plt.ylabel("GEX per strike ($k of P&L per 1% move)")
plt.legend(loc="lower right")
fig_text = ("Sign convention OI_C - OI_P is an ASSUMPTION, not accounting identity.\n"
            "Pinning effects: cents or a small fraction of a percent — not an intraday magnet.")
plt.gcf().text(0.01, 0.02, fig_text, fontsize=8, color=PALETTE["zero"], va="bottom", ha="left",
               bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=PALETTE["volume"], alpha=0.85))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S074_example.png", bbox_inches="tight")
plt.close()
