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

# ---- SYNTHETIC DATA (seed stated in chapter text) ----
rng = np.random.default_rng(61)

# Fictional dual listing: ADR "XYZ" (ratio 5 local shares = 1 ADR),
# local "XYZ3" quoted in BRL, FX = BRL per USD, 30-min bars, 10:00-15:30 ET overlap.
n = 12
bars = [f"{10 + i // 2}:{(i % 2) * 30:02d}" for i in range(n)]  # 10:00, 10:30, ...
local_p = 50.0 + np.cumsum(rng.normal(0, 0.25, n))          # BRL
fx = 5.00 + rng.normal(0, 0.01, n)                          # BRL/USD
parity = 5.0 * local_p / fx                                 # USD parity of one ADR
# A premium episode: +1.5% peak around bars 4-7, decays; tiny noise elsewhere.
episode = np.array([0, 0, 0.4, 1.0, 1.5, 1.4, 1.1, 0.7, 0.4, 0.2, 0.1, 0.0])
adr_p = parity * (1 + episode / 100.0) * (1 + rng.normal(0, 0.0005, n))
premium = (adr_p - parity) / parity * 100.0                 # percent
z = (premium - premium.mean()) / premium.std(ddof=1)        # z-score, trailing-sample

print("bar, local_BRL, FX, parity_USD, ADR_USD, premium_pct, z")
for i in range(n):
    print(f"{bars[i]}, {local_p[i]:.2f}, {fx[i]:.4f}, {parity[i]:.3f}, "
          f"{adr_p[i]:.3f}, {premium[i]:.3f}, {z[i]:.2f}")

# After-cost waterfall (verified chatbot arithmetic; labelled chatbot source in text)
steps = ["Gross\npremium", "ADR spread\n(cross)", "ADR fees +\ncommissions",
         "Borrow\n(HTB leg)", "FX hedge\ncost", "Slippage /\nimpact", "Net"]
vals = [1.50, -0.30, -0.20, -0.60, -0.20, -0.30, -0.10]
assert abs(sum(vals[:-1]) - vals[-1]) < 1e-9

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.4), sharex=False)

# Top: premium series with z-signal band
ax1.plot(bars, premium, marker="o", color=PALETTE["price"], lw=2,
         label="FX-adjusted premium (ADR vs parity), %")
ax1.fill_between(bars, premium - premium.std(ddof=1), premium + premium.std(ddof=1),
                 color=PALETTE["band"], alpha=0.6, label="±1σ band (example)")
ax1.axhline(0, color=PALETTE["zero"], lw=1)
ax1.set_ylabel("Premium (%)")
ax1.set_title("S061 — ADR / dual-listed premium: 12-bar synthetic overlap session")
ax1.set_xticks(range(n)); ax1.set_xticklabels(bars, rotation=45, ha="right")
ax1.legend(loc="upper left")
ax1.annotate("peak z = +%.2f\n(trade toward zero)" % z.max(),
             xy=(bars[4], premium[4]), xytext=(7, max(premium) * 0.75),
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
             fontsize=9, color=PALETTE["signal"])

# Bottom: after-cost waterfall
colors = [PALETTE["profit"]] + [PALETTE["loss"]] * 5 + \
    ([PALETTE["profit"]] if vals[-1] >= 0 else [PALETTE["loss"]])
ax2.bar(steps, vals, color=colors, edgecolor="#2c3e50")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.set_ylim(-0.8, 1.8)
ax2.set_ylabel("P&L (bps of notional, %)")
ax2.set_title("After-cost waterfall: 1.50% gross premium → -0.10% net (verified arithmetic)")
for i, v in enumerate(vals):
    ax2.text(i, v + (0.05 if v >= 0 else -0.12), f"{v:+.2f}%", ha="center", fontsize=9,
             fontweight="bold" if i in (0, len(vals) - 1) else "normal")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S061_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S061_example.png")
