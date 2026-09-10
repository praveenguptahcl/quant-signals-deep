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

# ---- synthetic worked-example tape (hardcoded; matches S010.md S4) ----
rng = np.random.default_rng(10)  # fixed seed; tape values are hardcoded below
q = np.array([100, -200, 100, 300, -100, 200, -100, -300], dtype=float)  # signed shares
dp = np.array([0.005, -0.008, 0.006, 0.013, -0.006, 0.011, -0.004, -0.017])  # Δp in $

lam = float(np.sum(q * dp) / np.sum(q ** 2))  # = 4.9667e-05 $/signed-share
assert abs(lam - 4.9666666667e-05) < 1e-12
assert abs(np.sum(q * dp) - 14.9) < 1e-9
assert np.sum(q ** 2) == 300000

fig, ax = plt.subplots()
ax.scatter(q, dp, color=PALETTE["price"], s=80, zorder=3,
           label="trade (q, Δp): signed shares vs price change")
xs = np.linspace(q.min() * 1.05, q.max() * 1.05, 200)
ax.plot(xs, lam * xs, color=PALETTE["signal"], lw=2.2,
        label=f"OLS slope λ̂ = {lam:.3e} $/signed-share")
ax.axhline(0, color=PALETTE["zero"], lw=0.9)
ax.axvline(0, color=PALETTE["zero"], lw=0.9)
ax.set_title("S010 — Kyle's lambda: Δp vs signed share volume (8-trade synthetic tape)")
ax.set_xlabel("signed volume q (shares)")
ax.set_ylabel("mid-price change Δp ($)")
ax.legend(loc="upper left")
ax.text(0.02, 0.98,
        f"λ̂ = ΣqΔp / Σq² = 14.9 / 300,000\n= 4.97e-05 $/signed-share\n"
        f"⇒ impact̂ ≈ λ̂·Q: 10,000 sh → ≈ $0.50\n(units: $ of price move per signed share)",
        transform=ax.transAxes, va="top", ha="left", fontsize=9,
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=PALETTE["price"], alpha=0.92))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S010_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S010_example.png, λ̂ =", lam)
