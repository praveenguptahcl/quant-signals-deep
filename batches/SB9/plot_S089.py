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

rng = np.random.default_rng(21)  # fixed seed, stated in chapter text

# ---- A-S parameters (consistent price/time units; all illustrative) ----
s = 100.00        # mid-price ($)
gamma = 0.1       # risk aversion (per $^2)
sigma = 0.3       # mid-price vol over the horizon ($)
Tt = 1.0          # time to horizon (one session)
kappa = 1.5       # order-book depth parameter (per $)
A = 140.0         # baseline fill intensity (per session)


def r(q):
    return s - q * gamma * sigma ** 2 * Tt


spread = gamma * sigma ** 2 * Tt + (2 / gamma) * np.log(1 + gamma / kappa)
dstar = spread / 2.0


def p_a(q):
    return r(q) + dstar


def p_b(q):
    return r(q) - dstar


def lam_a(q):
    return A * np.exp(-kappa * (p_a(q) - s))


def lam_b(q):
    return A * np.exp(-kappa * (s - p_b(q)))


# ---- Numbers the chapter quotes (text == chart) ----
print(f"gamma*sigma^2*(T-t) = {gamma*sigma**2*Tt:.6f}")
print(f"(2/gamma)*ln(1+gamma/kappa) = {(2/gamma)*np.log(1+gamma/kappa):.6f}")
print(f"total spread = {spread:.6f} ; half-spread delta* = {dstar:.6f}")
print(" q |   r(q)  |   p_b   |   p_a   | lam_b | lam_a")
for q in [-20, -10, 0, 10, 20]:
    print(f"{q:+3d} | {r(q):7.4f} | {p_b(q):7.4f} | {p_a(q):7.4f} |"
          f" {lam_b(q):6.2f} | {lam_a(q):6.2f}")

# ---- Poisson fill dispersion at q=0, ask side: N=200 simulated sessions ----
fills = rng.poisson(lam_a(0), size=200)
print(f"fills/session at q=0 ask: mean={fills.mean():.2f} (theory {lam_a(0):.2f}), "
      f"std={fills.std(ddof=1):.2f} (theory {np.sqrt(lam_a(0)):.2f}), "
      f"min={fills.min()}, max={fills.max()}")

# ---- Chart ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2))
qs = np.arange(-30, 31)
ax1.plot(qs, [r(q) for q in qs], color=PALETTE["price"], lw=2.4, label="reservation price r(q)")
ax1.plot(qs, [p_a(q) for q in qs], color=PALETTE["signal"], ls="--", lw=1.8, label="ask p_a = r+δ*")
ax1.plot(qs, [p_b(q) for q in qs], color=PALETTE["profit"], ls="--", lw=1.8, label="bid p_b = r−δ*")
ax1.axhline(s, color=PALETTE["volume"], lw=1.2, label="mid s")
ax1.fill_between(qs, [p_b(q) for q in qs], [p_a(q) for q in qs],
                 color=PALETTE["band"], alpha=0.35, label="quoted spread")
ax1.set_title("Quotes vs inventory")
ax1.set_xlabel("Inventory q (shares)")
ax1.set_ylabel("Price ($)")
ax1.legend(loc="upper right", fontsize=8)
ax1.annotate("long inventory → r below mid:\nboth quotes drop to unload",
             xy=(-24, r(-24)), xytext=(-29, r(-24) - 0.55),
             fontsize=9, color=PALETTE["zero"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.9))
ax1.annotate("buy-limit fill at the bid\njust before mid falls:\nnominal spread < adverse selection",
             xy=(0, p_b(0)), xytext=(6, p_b(0) - 0.75),
             fontsize=9, color=PALETTE["loss"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["loss"]),
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=PALETTE["loss"], alpha=0.9))

ds = np.linspace(0.1, 2.0, 200)
ax2.plot(ds, A * np.exp(-kappa * ds), color=PALETTE["price"], lw=2.2,
         label="fill intensity λ(δ) = A·e^{−κδ}")
ax2.axvline(dstar, color=PALETTE["signal"], ls="--", lw=1.8,
            label=f"δ* = {dstar:.3f} → λ = {lam_a(0):.1f}/session")
ax2.plot(dstar, lam_a(0), "o", color=PALETTE["signal"], ms=8)
# simulated session fill counts at delta*, jittered
jx = dstar + rng.normal(0, 0.02, 30)
ax2.scatter(jx, fills[:30], s=18, color=PALETTE["volume"], alpha=0.7, zorder=5,
            label="30 simulated sessions (Poisson, seed 21)")
ax2.set_title("Fill intensity and simulated fill dispersion")
ax2.set_xlabel("Distance from mid δ ($)")
ax2.set_ylabel("Fills per session")
ax2.legend(loc="upper right", fontsize=8)

fig.suptitle("S089 — Avellaneda–Stoikov: reservation price, optimal spread, fill risk (seed 21)",
             fontsize=13, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S089_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
