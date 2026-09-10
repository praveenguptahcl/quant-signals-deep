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

rng = np.random.default_rng(144)  # seed = stage number; stated in chapter T4

# ---- synthetic 12-bar session tape (fictional large-cap "AXM", prices synthetic) ----
n = 12
s_b = np.array([1.9, 1.7, 1.3, 1.1, 0.95, 0.90, 0.85, 0.90, 1.00, 1.10, 1.30, 1.60])  # diurnal factor (U-shape)
sig_resid_bp = 10.0  # residual std of the deseasonalized return, bp
mu_bp = np.array([32.0, 20.0, -9.0, 6.0, -13.0, 7.0, 5.0, -7.0, 24.0, -6.0, 16.0, 20.0])
r_bp = mu_bp + rng.normal(0.0, 3.0, n)          # raw bar returns, basis points
r_des_bp = r_bp / s_b                            # deseasonalized returns
z_raw = r_bp / sig_resid_bp
z_des = r_des_bp / sig_resid_bp

price = np.empty(n + 1); price[0] = 200.00
for i in range(n):
    price[i + 1] = price[i] * (1 + r_bp[i] / 10000.0)

# ---- example trade rule: fade |z_des| >= 2.0 at bar close, exit next bar close ----
Z_ENTRY = 2.0  # example threshold
N_SHARES = 5000
SPREAD_BP = 1.0      # paid each side
COMM = 0.005         # $/share/side

trades = []
pos = 0; entry_px = 0.0
for i in range(n - 1):  # last bar has no next bar to exit into
    px = price[i + 1]
    if pos == 0 and abs(z_des[i]) >= Z_ENTRY:
        pos = -1 if z_des[i] > 0 else 1
        entry_px = px
        entry_bar = i
    elif pos != 0:
        exit_px = px
        gross = pos * N_SHARES * (exit_px - entry_px)
        cost = 2 * (SPREAD_BP / 10000.0 * N_SHARES * entry_px + COMM * N_SHARES)
        net = gross - cost
        trades.append((entry_bar, i, pos, entry_px, exit_px, gross, cost, net))
        pos = 0

print("bar | raw_bp | s_b | des_bp | z_raw | z_des | price")
for i in range(n):
    print(f"{i+1:3d} | {r_bp[i]:7.2f} | {s_b[i]:.2f} | {r_des_bp[i]:7.2f} | {z_raw[i]:6.2f} | {z_des[i]:6.2f} | {price[i+1]:8.3f}")
print("\ntrades (entry_bar->exit_bar, dir, entry_px, exit_px, gross, cost, net):")
cum = 0.0
cum_curve = [0.0]
for t in trades:
    cum += t[7]
    cum_curve.append(cum)
    print(f"bar {t[0]+1}->{t[1]+1} dir={'SHORT' if t[2]<0 else 'LONG'} entry {t[3]:.3f} exit {t[4]:.3f} "
          f"gross {t[5]:+.2f} cost {t[6]:.2f} net {t[7]:+.2f}")
print(f"TOTAL net P&L = {cum:+.2f}")

# ---- chart: cumulative net P&L with entry/exit markers ----
fig, ax = plt.subplots()
xs = np.arange(len(cum_curve))
ax.step(xs, cum_curve, where="post", color=PALETTE["price"], lw=2.2,
        label="Cumulative net P&L ($)")
ax.scatter(xs, cum_curve, color=PALETTE["price"], s=36, zorder=5)
for k, t in enumerate(trades):
    ax.annotate(f"exit bar {t[1]+1}\nnet {t[7]:+.2f}",
                xy=(k + 1, cum_curve[k + 1]), xytext=(14, 18 if t[7] > 0 else -26),
                textcoords="offset points", fontsize=8.5,
                color=PALETTE["profit"] if t[7] > 0 else PALETTE["loss"],
                arrowprops=dict(arrowstyle="->", color=PALETTE["zero"], lw=1))
ax.axhline(0, color=PALETTE["zero"], lw=1)
ax.set_title("T044 — Diurnal Deseasonalization Normalizer: cumulative net P&L on a synthetic 12-bar session")
ax.set_xlabel("Trade index (0 = session start)")
ax.set_ylabel("Cumulative net P&L ($)")
ax.legend()

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T044_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T044_example.png")
