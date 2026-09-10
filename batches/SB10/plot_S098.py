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

rng = np.random.default_rng(98)  # fixed seed, stated in chapter text

# ---- Synthetic 6-stock short-interest panel (hand-constructed; fictional tickers) ----
tickers = np.array(["ZQTA", "KLVR", "NORD", "MEMEQ", "PWRS", "DLTA"])
si   = np.array([6.0, 18.0, 9.0, 42.0, 30.0, 3.0])     # short interest, M shares
flt  = np.array([400.0, 220.0, 180.0, 150.0, 120.0, 90.0])  # float, M shares
adv  = np.array([12.0, 3.0, 6.0, 4.5, 15.0, 1.5])      # avg daily volume, M shares
fee  = np.array([0.4, 8.5, 1.2, 42.0, 28.0, 0.8])       # indicative borrow fee, %/ann
util = np.array([8.0, 61.0, 22.0, 97.0, 92.0, 15.0])    # utilization, %
dix  = np.array([7.5, 9.2, 8.1, 16.0, 13.5, 7.0])       # dark-pool buying proxy, %

si_float = 100 * si / flt            # % of float sold short
dtc = si / adv                        # days-to-cover
drag30 = fee * 30 / 365               # 30-day borrow drag on a short, % of notional

# Crowding composite (desk-specific example): sum of z-scores of SI/float, DTC, fee
def zscore(x):
    return (x - x.mean()) / x.std(ddof=1)
crowd = zscore(si_float) + zscore(dtc) + zscore(fee)

print("ticker | SI/float % | DTC (days) | fee %/ann | util % | DIX % | crowd z-sum | 30d drag %")
for i, t in enumerate(tickers):
    print(f" {t:6s} | {si_float[i]:10.2f} | {dtc[i]:10.2f} | {fee[i]:9.1f} | "
          f"{util[i]:6.1f} | {dix[i]:5.1f} | {crowd[i]:11.2f} | {drag30[i]:9.2f}")
print(f"\nMEMEQ hand-check: SI/float = 42/150 = {42/150*100:.1f}%; "
      f"DTC = 42/4.5 = {42/4.5:.2f} days; 30d drag = 42*30/365 = {42*30/365:.2f}%")

# ---- Chart: bubble scatter + borrow-drag bars ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2))

sizes = 120 + 260 * (dtc / dtc.max())     # bubble size ~ days-to-cover
colors = [PALETTE["signal"] if t == "MEMEQ" else PALETTE["price"] for t in tickers]
sc = ax1.scatter(si_float, fee, s=sizes, c=colors, alpha=0.75,
                 edgecolors=PALETTE["zero"], linewidths=1)
for i, t in enumerate(tickers):
    ax1.annotate(t, (si_float[i], fee[i]), fontsize=9, weight="bold",
                 xytext=(6, 6), textcoords="offset points", color=PALETTE["zero"])
ax1.set_xlabel("short interest / float (%)")
ax1.set_ylabel("indicative borrow fee (%/ann)")
ax1.set_title("Crowding map: SI/float vs borrow fee\n(bubble size = days-to-cover)")
ax1.annotate("MEMEQ: squeeze-risk corner\n28% SI/float, 42%/ann fee, 9.3 DTC",
             xy=(si_float[3], fee[3]), xytext=(12, 22), fontsize=9,
             color=PALETTE["signal"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.95))

bcols = [PALETTE["loss"] if d > 2.0 else PALETTE["volume"] for d in drag30]
ax2.barh(tickers, drag30, color=bcols, edgecolor=PALETTE["zero"])
ax2.set_xlabel("30-day borrow drag on a $1M short (% of notional)")
ax2.set_title("Negative carry: 30-day borrow cost by name")
ax2.annotate("3.45% fee drag\nbefore any price move",
             xy=(drag30[3], 3), xytext=(drag30[3] + 0.6, 3.4), fontsize=9,
             color=PALETTE["loss"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["loss"]),
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.95))

fig.suptitle("S098 — Short interest, borrow fees & days-to-cover (seed 98)",
             fontsize=13, weight="bold", y=1.02)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S098_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
