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

rng = np.random.default_rng(42)  # fixed seed, stated in chapter text

# ---- Synthetic DGP: VAR(1) in (delta-mid, signed trade) ----
# x_t = A1 x_{t-1} + u_t ;  delta-m in dollars, q in {+1,-1} trade signs
A1 = np.array([[0.10, 0.012],
               [0.05, 0.60]])
Sig = np.diag([0.01 ** 2, 1.0])

T, burn = 5000, 200
x = np.zeros((T + burn, 2))
for t in range(1, T + burn):
    x[t] = A1 @ x[t - 1] + rng.multivariate_normal([0.0, 0.0], Sig)
x = x[burn:]

# mid-price tape (for the worked-example table, first 12 events)
mid = 100.00 + np.cumsum(x[:, 0])
bid = mid - 0.005
ask = mid + 0.005

# ---- Estimate VAR(1) by OLS (per-equation), as the chapter's worked example does ----
Y = x[1:]
Z = x[:-1]
A1hat = np.linalg.lstsq(Z, Y, rcond=None)[0].T

# ---- IRF: IRF(H) = sum_{h=0..H} Psi_h e_q ; LRI = e_m' (I - A1)^{-1} e_q ----
e_m = np.array([1.0, 0.0])
e_q = np.array([0.0, 1.0])
H = 40
Psi = np.eye(2)
irf = [0.0]  # h = 0: no contemporaneous quote revision
cum = 0.0
irf_h = {0: 0.0}
for h in range(1, H + 1):
    Psi = A1hat @ Psi
    cum += float(e_m @ Psi @ e_q)
    irf.append(cum)
    irf_h[h] = cum
LRI = float(e_m @ np.linalg.inv(np.eye(2) - A1hat) @ e_q)

# ---- Numbers the chapter quotes (text == chart) ----
print("Estimated A1 (seed 42):")
print(np.array2string(A1hat, precision=4, suppress_small=True))
print(f"LRI = {LRI:.4f} dollars  ({LRI*100:.2f} cents)")
for h in [0, 1, 2, 3, 5, 10, 20, 40]:
    print(f"IRF({h}) = {irf_h[h]:.4f} dollars  ({irf_h[h]*100:.2f} cents)")
print("First 12 tape rows: t, bid, ask, mid, dmid, q")
for t in range(12):
    dm = x[t, 0]
    q = 1 if x[t, 1] > 0 else -1
    print(f"{t:2d}  {bid[t]:8.4f}  {ask[t]:8.4f}  {mid[t]:8.4f}  {dm:+.4f}  {q:+d}")

# ---- Chart ----
fig, ax = plt.subplots()
hs = np.arange(H + 1)
ax.plot(hs, np.array(irf) * 100, color=PALETTE["price"], lw=2.2,
        label="IRF: cumulative quote revision (cents)")
ax.axhline(LRI * 100, color=PALETTE["signal2"], ls="--", lw=1.8,
           label=f"LRI (long-run impact) = {LRI*100:.2f}c")
for h in [1, 5, 20]:
    ax.plot(h, irf_h[h] * 100, "o", color=PALETTE["signal"], ms=7)
    ax.annotate(f"{irf_h[h]*100:.2f}c", (h, irf_h[h] * 100),
                textcoords="offset points", xytext=(6, 6), fontsize=9,
                color=PALETTE["signal"])
ax.set_title("S084 — Hasbrouck trade–quote VAR: synthetic IRF converging to LRI (seed 42)")
ax.set_xlabel("Horizon h (events after the trade innovation)")
ax.set_ylabel("Cumulative mid-price revision (cents)")
ax.legend(loc="lower right")
ax.set_xlim(0, H)
ax.annotate("unexpected +1 buy innovation;\nnot total volume", xy=(26, irf_h[26] * 100),
            fontsize=9, color=PALETTE["zero"],
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.9))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S084_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
