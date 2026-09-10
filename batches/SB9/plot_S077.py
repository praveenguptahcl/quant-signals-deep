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

rng = np.random.default_rng(77)  # seed recorded in chapter text (unused randomness; series is operator-verified)

# ---- VERIFIED Kalman local-level worked example (duck.ai operator-verified, 2026-09-10) ----
y = np.array([100.00, 100.40, 99.80, 100.20, 100.60, 100.30, 100.90, 101.10, 100.80, 101.20])
Q, R = 0.04, 0.16            # process-noise variance, observation-noise variance
x, P = 100.00, 0.16          # x_hat_{0|0}, P_{0|0}
t = np.arange(1, 10)
yobs = y[1:]
xp_a, Pp_a, K_a, xf_a, Pf_a, e_a = [], [], [], [], [], []
for yt in yobs:
    xp, Pp = x, P + Q
    K = Pp / (Pp + R)
    xf = xp + K * (yt - xp)
    Pf = (1 - K) * Pp
    e = yt - xf
    xp_a.append(xp); Pp_a.append(Pp); K_a.append(K); xf_a.append(xf); Pf_a.append(Pf); e_a.append(e)
    x, P = xf, Pf
xp_a, Pp_a, K_a, xf_a, Pf_a, e_a = map(np.array, (xp_a, Pp_a, K_a, xf_a, Pf_a, e_a))

print("t | y_t | x_{t|t-1} | P_{t|t-1} | K_t | x_{t|t} | P_{t|t} | e_t = y_t - x_{t|t}")
for i in range(9):
    print(f"{t[i]} | {yobs[i]:.2f} | {xp_a[i]:.4f} | {Pp_a[i]:.4f} | {K_a[i]:.4f} | {xf_a[i]:.4f} | {Pf_a[i]:.4f} | {e_a[i]:+.4f}")

# ---- chart ----
fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 1]})
ax1.plot(t, yobs, "o", color=PALETTE["price"], ms=7, label="observed price y_t (synthetic)")
ax1.plot(t, xf_a, color=PALETTE["signal"], lw=2, marker="s", ms=5, label="filtered fair value x\u0302_{t|t}")
band = 2 * np.sqrt(Pf_a)
ax1.fill_between(t, xf_a - band, xf_a + band, color=PALETTE["band"], alpha=0.5,
                 label="filtered \u00b12\u03c3 confidence")
ax1.set_ylabel("price")
ax1.set_title("S077 \u2014 Kalman local-level fair value: verified 10-observation example (Q=0.04, R=0.16)")
ax1.legend(loc="upper left")

colors = [PALETTE["profit"] if v >= 0 else PALETTE["loss"] for v in e_a]
ax2.bar(t, e_a, color=colors, alpha=0.85, width=0.6, label="residual e_t = y_t \u2212 x\u0302_{t|t}")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.annotate("e_3 = +0.0980\n(marked)", xy=(3, e_a[2]), xytext=(5.5, 0.30),
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]), fontsize=9, ha="center")
ax2.set_xlabel("observation t")
ax2.set_ylabel("residual")
ax2.set_xticks(t)
ax2.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S077_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
