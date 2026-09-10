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

# ---- SYNTHETIC 72-HOUR WINDOW (seed 96) ----
# Cascade designed at hours 50-52: mark price -3.5%, reported OI -10%,
# reported long liquidations spike, reported funding flips sign; partial
# recovery hours 53-57 (the post-cascade fade window).
rng = np.random.default_rng(96)
T = 72
hours = np.arange(T)

price = 100.0 + np.cumsum(rng.normal(0.0, 0.12, T))
price[50] -= 1.8
price[51] -= 1.2
price[52] -= 0.5
price[53:58] += np.array([0.25, 0.30, 0.20, 0.15, 0.10])

oi = 1.0 + np.cumsum(rng.normal(0.0, 0.004, T))      # reported OI, $B synthetic
oi[50] -= 0.060
oi[51] -= 0.030
oi[52] -= 0.015

fund = np.clip(rng.normal(0.00015, 0.00020, T), -0.002, 0.002)  # reported funding
fund[48] = 0.00040
fund[49] = 0.00060
fund[50] = 0.00080
fund[51] = 0.00060
fund[52] = 0.00020
fund[53] = -0.00030

liq_long = np.abs(rng.normal(0.20, 0.15, T))          # reported long liqs, $M
liq_long[50] = 2.8
liq_long[51] = 8.5
liq_long[52] = 4.2
liq_short = np.abs(rng.normal(0.15, 0.10, T))         # reported short liqs, $M
liq_short[54] = 1.9

# print the worked-example window (hours 45-56) for pasting into S4's table
print("hr | price | rpt_OI($B) | rpt_fund | rpt_long_liq($M) | rpt_short_liq($M)")
for h in range(45, 57):
    print(f"{h:>2} | {price[h]:6.2f} | {oi[h]:10.3f} | {fund[h]:+8.5f} |"
          f" {liq_long[h]:17.2f} | {liq_short[h]:18.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [1.6, 1]})

px0, oi0 = price[40], oi[40]
ax1.plot(hours, 100.0 * price / px0, color=PALETTE["price"], linewidth=2,
         label="Mark price (indexed, h40=100)")
ax1.plot(hours, 100.0 * oi / oi0, color=PALETTE["volume"], linewidth=1.6,
         linestyle="--", label="Reported OI (indexed, h40=100)")
ax1.axvspan(50, 52.5, color=PALETTE["signal"], alpha=0.12, label="Cascade window")
ax1.axvspan(53, 57.5, color=PALETTE["profit"], alpha=0.10, label="Post-cascade fade window")
ax1.set_title("S096 — Reported OI shock & liquidation cascade (synthetic 72h, seed 96)")
ax1.set_ylabel("index (h40 = 100)")
ax1.legend(loc="lower left", fontsize=8)

ax2.step(hours, 1e4 * fund, where="mid", color=PALETTE["signal2"], linewidth=1.8,
         label="Reported funding (bps)")
ax2.bar(hours - 0.2, liq_long, width=0.4, color=PALETTE["loss"],
        label="Reported long liqs ($M)")
ax2.bar(hours + 0.2, liq_short, width=0.4, color=PALETTE["signal2"], alpha=0.7,
        label="Reported short liqs ($M)")
ax2.axhline(0, color=PALETTE["zero"], linewidth=1)
ax2.set_xlabel("hour")
ax2.set_ylabel("bps / $M")
ax2.legend(loc="upper left", fontsize=8)
ax2.text(51, max(liq_long) * 0.85, "funding flips + -> -",
         fontsize=8, color=PALETTE["signal2"], weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S096_example.png", bbox_inches="tight")
plt.close()
print("S096 chart written")
