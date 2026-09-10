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

# ---- S050 worked example (SYNTHETIC, verified Duck.ai tape, seed 50) ----
# P_B(t) = 100 + t ; P_A(t) = 2*P_B(t) + e_t ; stipulated spread S_t = P_A - 2*P_B = e_t
rng = np.random.default_rng(50)
e = np.array([-2, -1, 0, 1, 2, 1, 0, -1, -2, 0, 2, 1, 0, -1, -2, -1, 0, 1, 2, 0], dtype=float)
t = np.arange(1, 21)
P_B = 100.0 + t
P_A = 2 * P_B + e
S = P_A - 2 * P_B                      # stipulated spread (exactly e_t)

ssq = float(np.sum(S ** 2))            # corrected: 32 (chatbot wrongly said 40)
std_full = float(S.std(ddof=1))        # corrected full-sample: sqrt(32/19) ~= 1.298 (not 1.451)

# Causally honest live-trading version: estimate mu/sigma on days 1-14 ONLY
# (strictly before the trading interval), then trade from day 15 on.
EST = 14
mu14 = float(S[:EST].mean())
std14 = float(S[:EST].std(ddof=1))
z = (S - mu14) / std14
z_full15 = -2.0 / std_full            # verified full-sample check: ~ -1.541

# OLS correction note: from the tape itself,
# beta_hat = 2 + sum(e*(t-10.5))/sum((t-10.5)^2) = 2 + 20/665 ; alpha_hat = 221 - beta_hat*110.5
beta_hat = 2 + float(np.sum(e * (t - 10.5))) / float(np.sum((t - 10.5) ** 2))
alpha_hat = float(P_A.mean()) - beta_hat * float(P_B.mean())

Z_ENTRY, Z_EXIT = 1.25, 0.5
entry_day = EST + 1 + int(np.argmax(z[EST:] <= -Z_ENTRY))       # first trade day z <= -1.25
post = z[entry_day:]
exit_day = entry_day + 1 + int(np.argmax(post >= -Z_EXIT))     # first day z back >= -0.5

pnl = (P_A[exit_day - 1] - P_A[entry_day - 1]) + 2 * (P_B[entry_day - 1] - P_B[exit_day - 1])

print(f"sum_sq={ssq:.1f} std_full={std_full:.4f} mu14={mu14:.4f} std14={std14:.4f}")
print(f"beta_hat={beta_hat:.4f} alpha_hat={alpha_hat:.2f}")
print(f"z15_full={z_full15:+.4f} z15={z[14]:+.4f} z16={z[15]:+.4f} z17={z[16]:+.4f} z20={z[19]:+.4f}")
print(f"entry_day={entry_day} exit_day={exit_day}")
print(f"entry A={P_A[entry_day-1]:.1f} B={P_B[entry_day-1]:.1f}; exit A={P_A[exit_day-1]:.1f} B={P_B[exit_day-1]:.1f}")
print(f"gross_pnl_spread_pts={pnl:.2f}")

# ---- Plot ----
fig, ax = plt.subplots()
ax.plot(t, S, color=PALETTE["price"], marker="o", ms=4, label="spread S_t = P_A - 2·P_B (synthetic)")
for k, col, lab in ((2.0, PALETTE["signal"], "±2σ"), (1.25, PALETTE["signal2"], "±1.25σ (entry)")):
    ax.axhline(k * std14, color=col, ls="--", lw=1)
    ax.axhline(-k * std14, color=col, ls="--", lw=1)
    ax.text(20.2, k * std14, lab, fontsize=8, color=col, va="center")
ax.axhline(mu14, color=PALETTE["zero"], ls=":", lw=1)
ax.axvline(EST + 0.5, color=PALETTE["volume"], ls="-", lw=1)
ax.text(EST + 0.6, 2.9, "est. window ends (day 14)", fontsize=8, color=PALETTE["volume"])
ax.fill_between(t, mu14 - 2 * std14, mu14 + 2 * std14, color=PALETTE["band"], alpha=0.25)
ax.scatter([entry_day], [S[entry_day - 1]], color=PALETTE["signal"], s=90, zorder=5,
           marker="v", label=f"enter long spread, day {entry_day} (z={z[entry_day-1]:+.3f})")
ax.scatter([exit_day], [S[exit_day - 1]], color=PALETTE["profit"], s=90, zorder=5,
           marker="^", label=f"exit at zero-cross, day {exit_day} (z={z[exit_day-1]:+.3f})")
ax.annotate(f"day 15: z = {z[14]:+.3f}", xy=(15, S[14]), xytext=(10, -2.9),
            fontsize=9, arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
            color=PALETTE["signal"])
ax.set_title("S050 — EG cointegration z-score: synthetic 20-day spread (seed 50)")
ax.set_xlabel("day")
ax.set_ylabel("spread (price points)")
ax.legend()

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S050_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
