"""S069 worked-example chart — synthetic IV vs realized variance (seed 69)."""
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

# ---- SYNTHETIC WORKED EXAMPLE (seed 69) ----
# 12 synthetic months. IV_ann = 30-day implied vol (annualized %);
# RV_ann = subsequently realized vol over the matched 30-day window (annualized %).
rng = np.random.default_rng(69)
months = np.arange(1, 13)
iv_ann = np.array([15.2, 16.1, 14.8, 17.3, 28.6, 19.4, 16.9, 15.8, 24.7, 18.2, 15.5, 16.4])
rv_ann = np.array([12.4, 13.9, 11.7, 14.2, 34.1, 15.3, 13.1, 12.0, 27.8, 14.9, 12.8, 13.5])
vrp_vol = np.round(iv_ann - rv_ann, 1)              # vol points
vrp_var = np.round(iv_ann ** 2 - rv_ann ** 2, 0)    # variance points
print("mo  IV_ann  RV_ann  VRP_vol  VRP_var")
for m, i, r, vv, va in zip(months, iv_ann, rv_ann, vrp_vol, vrp_var):
    print(f"{m:>2}  {i:6.1f}  {r:6.1f}  {vv:+7.1f}  {va:+7.0f}")

plt.plot(months, iv_ann, marker="o", color=PALETTE["price"],
         label="Implied vol, 30d annualized (IV)")
plt.plot(months, rv_ann, marker="s", color=PALETTE["signal"],
         label="Realized vol, matched 30d window (RV)")
plt.fill_between(months, iv_ann, rv_ann, where=(rv_ann > iv_ann),
                 color=PALETTE["loss"], alpha=0.25, label="VRP < 0 (RV > IV)")
plt.axhline(0, color=PALETTE["zero"], lw=1)
plt.text(0.98, 0.06,
         "HONEST HORIZON NOTE: strongest documented VRP evidence is at\n"
         "weekly\u2192monthly\u2192multi-month horizons, NOT intraday.",
         transform=plt.gca().transAxes, ha="right", va="bottom", fontsize=8,
         color=PALETTE["zero"], bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#bbbbbb", alpha=0.9))
plt.title("S069 — Implied vs realized variance: 12-month synthetic VRP example")
plt.xlabel("Month (synthetic)")
plt.ylabel("Volatility, annualized (%)")
plt.xticks(months)
plt.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S069_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
