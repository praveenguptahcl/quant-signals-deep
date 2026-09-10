"""S058 plot: synthetic futures curve with the calendar spread marked. seed=58058."""
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

SEED = 58058  # stated in text (used only to fix the quote-noise pattern below)
S0, r, q = 100.0, 0.05, 0.018  # synthetic: spot, risk-free rate, dividend yield
T = np.array([1, 2, 3, 6, 9, 12]) / 12.0  # expiries in years
fair = S0 * np.exp((r - q) * T)  # cost-of-carry fair curve
# synthetic observed quotes: front month cheap -0.80, second month rich +0.50
noise = np.array([-0.80, 0.50, -0.10, 0.20, -0.15, 0.10])
obs = fair + noise
xlabels = ["M1", "M2", "M3", "M6", "M9", "M12"]
x = np.arange(6)

fair_spread = fair[1] - fair[0]   # 0.2677
obs_spread = obs[1] - obs[0]      # 1.5677
signal = obs_spread - fair_spread  # +1.30: observed richer than fair

fig, ax = plt.subplots()
ax.set_title("S058 — Futures term structure: fair curve vs observed quotes with calendar spread")
ax.plot(x, fair, marker="o", color=PALETTE["price"], linewidth=1.8,
        label="fair curve F*(T) = S0 e^((r-q)T)  (r=5.0%, q=1.8%)")
ax.scatter(x, obs, s=90, color=PALETTE["signal"], zorder=5, label="observed quotes (synthetic)")
for i in range(6):
    ax.annotate(f"{obs[i]-fair[i]:+.2f}", (x[i], obs[i]), fontsize=8, xytext=(6, 6),
                textcoords="offset points", color=PALETTE["zero"])

# Mark the calendar spread between M1 and M2: observed vs fair
ax.annotate("", xy=(1.25, obs[1]), xytext=(1.25, obs[0]),
            arrowprops=dict(arrowstyle="<->", color=PALETTE["loss"], linewidth=2))
ax.text(1.32, (obs[0] + obs[1]) / 2,
        f"observed spread F2-F1 = {obs_spread:.2f}", fontsize=9, color=PALETTE["loss"],
        va="center", weight="bold")
ax.annotate("", xy=(0.75, fair[1]), xytext=(0.75, fair[0]),
            arrowprops=dict(arrowstyle="<->", color=PALETTE["profit"], linewidth=2))
ax.text(0.42, (fair[0] + fair[1]) / 2,
        f"fair spread F*2-F*1 = {fair_spread:.2f}", fontsize=9, color=PALETTE["profit"],
        va="center", weight="bold")
ax.annotate(f"calendar signal = {signal:+.2f}\n(observed richer than fair)",
            xy=(1.25, (obs[0] + obs[1]) / 2), xytext=(2.9, 99.35), fontsize=9,
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.9))

ax.set_xticks(x)
ax.set_xticklabels(xlabels)
ax.set_xlabel("contract expiry")
ax.set_ylabel("futures price (index points)")
ax.set_ylim(98.5, 104.2)
ax.legend(loc="upper left", fontsize=8)
ax.text(0.98, 0.04,
        "seed 58058 (synthetic quotes); continuous-futures series alone would\n"
        "hide these per-expiry prices — research needs contract-level quotes",
        transform=ax.transAxes, fontsize=8, va="bottom", ha="right",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.9))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S058_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
