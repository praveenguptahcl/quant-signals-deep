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

# ---- SYNTHETIC 22-DAY RV SERIES (hand-specified; operator-verified Duck.ai tape) ----
rng = np.random.default_rng(66)  # script seed (series itself is hand-specified, not drawn)
rv = np.array([0.000400, 0.000441, 0.000484, 0.000529, 0.000576, 0.000625, 0.000676,
               0.000729, 0.000784, 0.000841, 0.000900, 0.000841, 0.000784, 0.000729,
               0.000676, 0.000625, 0.000576, 0.000529, 0.000484, 0.000441, 0.000400,
               0.000361])

# CORRECTED values (operator hand-checked; raw chatbot 22-day sum 0.014821 was wrong)
sum22 = rv.sum()
rv5 = rv[-5:].mean()
rv22 = sum22 / 22.0
b0, bd, bw, bm = 0.000050, 0.40, 0.35, 0.20   # example betas — not an institutional standard
forecast = b0 + bd * rv[-1] + bw * rv5 + bm * rv22
sigma = np.sqrt(forecast)
ann = sigma * np.sqrt(252)

assert abs(sum22 - 0.013431) < 1e-9, sum22
assert abs(rv5 - 0.000443) < 1e-12, rv5
assert abs(rv22 - 0.000610500) < 1e-12, rv22
assert abs(forecast - 0.000471550) < 1e-12, forecast
assert abs(sigma - 0.021716) < 1e-6, sigma
assert abs(ann - 0.3447) < 1e-4, ann

print(f"22-day sum = {sum22:.6f}  (chatbot had 0.014821 — wrong)")
print(f"RV_22(22)  = {rv22:.9f}")
print(f"RV_22(5)   = {rv5:.9f}")
print(f"RV_22(1)   = {rv[-1]:.9f}")
print(f"forecast RV_hat(23|22) = {forecast:.9f}")
print(f"sigma_hat = {sigma:.6f} = {sigma*100:.4f}%/day; annualized = {ann*100:.2f}%")

days = np.arange(1, 23)
fig, ax = plt.subplots()
ax.set_title("S066 — HAR realized-volatility forecast: 22-day synthetic RV tape")
ax.bar(days, rv * 1e4, color=PALETTE["band"], edgecolor=PALETTE["price"], label="Daily RV (x1e4, synthetic)")
ax.axhline(rv22 * 1e4, color=PALETTE["signal2"], ls="--", lw=1.4,
           label=f"Monthly mean RV(22) = {rv22:.6f}")
ax.axhline(rv5 * 1e4, color=PALETTE["profit"], ls="--", lw=1.4,
           label=f"Weekly mean RV(5) = {rv5:.6f}")
ax.scatter([23], [forecast * 1e4], s=130, color=PALETTE["signal"], zorder=5,
           label=f"Forecast RV(23|22) = {forecast:.6f}")
ax.annotate(f"2.1716%/day -> 34.47% ann.", xy=(23, forecast * 1e4),
            xytext=(14, forecast * 1e4 + 0.35), fontsize=9, color=PALETTE["signal"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]))
ax.set_xlabel("Day (day 23 = forecast, not data)")
ax.set_ylabel("Realized variance (x1e-4)")
ax.set_xlim(0.5, 24.5)
ax.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S066_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S066_example.png")
