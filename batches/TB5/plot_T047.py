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

rng = np.random.default_rng(147)  # seed = stage number; stated in chapter T4

# ---- synthetic 8-session skew tape (fictional "WXY"; all numbers synthetic) ----
# RR25 = IV_call,25d - IV_put,25d (desk convention: negative = downside puts richer)
RR  = np.array([-4.0, -3.8, -4.2, -6.8, -7.2, -6.5, -5.0, -4.6])
dRR = np.array([0.0, 0.2, -0.4, -2.6, -0.4, 0.7, 1.5, 0.4])
px  = np.array([90.20, 89.90, 89.50, 88.40, 87.30, 86.60, 86.15, 86.40])

# trailing 20-day history of daily RR changes (example), drawn with the chapter seed
hist_dRR = rng.normal(0.0, 1.0, 20)
sd_dRR = hist_dRR.std()
z = dRR / sd_dRR
print(f"trailing 20-day dRR: std {sd_dRR:.3f} vol pts")
print("sess | RR25 | dRR | z_dRR | WXY px")
for i in range(8):
    print(f"{i:4d} | {RR[i]:5.1f} | {dRR[i]:+5.1f} | {z[i]:+6.2f} | {px[i]:7.2f}")

Z_ENTRY = -2.0   # example: sharp skew steepening
Z_EXIT = 0.0     # example: change mean-reverted
N = 2000
SPREAD_BP, COMM = 2.0, 0.005

entry_i, exit_i = 3, 6
print(f"\nsession {entry_i}: z={z[entry_i]:.2f} < {Z_ENTRY} + UOA put sweep -> SHORT {N} @ {px[entry_i]:.2f}")
print(f"session {exit_i}: z={z[exit_i]:.2f} > {Z_EXIT} -> COVER @ {px[exit_i]:.2f}")

gross = N * (px[entry_i] - px[exit_i])
spread_cost = 2 * (SPREAD_BP / 2 / 10000.0 * N * px[entry_i])
comm_cost = 2 * COMM * N
net = gross - spread_cost - comm_cost
print(f"gross {N} x ({px[entry_i]:.2f}-{px[exit_i]:.2f}) = {gross:+.2f}")
print(f"spread {spread_cost:.2f} + commission {comm_cost:.2f} = {spread_cost+comm_cost:.2f}")
print(f"NET = {net:+.2f}")

# ---- chart: cumulative net P&L with entry/exit markers ----
cum = np.array([0.0, 0.0, 0.0, 0.0,
                N * (px[3] - px[4]),
                N * (px[3] - px[5]),
                N * (px[3] - px[6]) - (spread_cost + comm_cost),
                N * (px[3] - px[6]) - (spread_cost + comm_cost)])
xs = np.arange(8)

fig, ax = plt.subplots()
ax.step(xs, cum, where="post", color=PALETTE["price"], lw=2.2, label="Cumulative net P&L ($)")
ax.scatter(xs, cum, color=PALETTE["price"], s=36, zorder=5)
ax.scatter([3], [0], color=PALETTE["signal"], s=90, zorder=6, marker="v")
ax.scatter([6], [cum[6]], color=PALETTE["profit"], s=90, zorder=6, marker="^")
ax.annotate(f"SHORT {N} @ {px[3]:.2f}\n(RR Δz {z[3]:+.1f}, UOA put sweep)",
            xy=(3, 0), xytext=(24, 44), textcoords="offset points", fontsize=9,
            color=PALETTE["signal"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"], lw=1))
ax.annotate(f"COVER @ {px[6]:.2f}\nnet +${net:,.2f}", xy=(6, cum[6]), xytext=(-132, -40),
            textcoords="offset points", fontsize=9, color=PALETTE["profit"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"], lw=1))
ax.axhline(0, color=PALETTE["zero"], lw=1)
ax.set_title("T047 — Risk-Reversal Skew Momentum: cumulative net P&L on a synthetic skew-following short")
ax.set_xlabel("Session")
ax.set_ylabel("Cumulative net P&L ($)")
ax.legend()

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T047_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T047_example.png")
