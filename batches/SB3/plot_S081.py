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

rng = np.random.default_rng(81)  # SEED 81 — stated in chapter text

# ---- bivariate Hawkes simulation (Ogata thinning, exponential kernels) ----
T = 90.0
mu_b = mu_s = 0.40          # base intensities (events/sec)
a_self, b_self = 0.90, 1.5  # self-excitation jump / decay (1/sec)
a_cross, b_cross = 0.25, 1.0  # cross-excitation jump / decay (1/sec)

# component bookkeeping: s_bb (buy self), s_bs (buy cross from sells),
#                         s_ss (sell self), s_sb (sell cross from buys)
s = {"bb": 0.0, "bs": 0.0, "ss": 0.0, "sb": 0.0}
t = 0.0
events = []  # (time, side) side: +1 buy, -1 sell
while t < T:
    lam_b = mu_b + s["bb"] + s["bs"]
    lam_s = mu_s + s["ss"] + s["sb"]
    dt = rng.exponential(1.0 / (lam_b + lam_s))
    tp = t + dt
    if tp > T:
        break
    dbb = np.exp(-b_self * dt); dbc = np.exp(-b_cross * dt)
    s = {"bb": s["bb"] * dbb, "bs": s["bs"] * dbc,
         "ss": s["ss"] * dbb, "sb": s["sb"] * dbc}
    lam_bp = mu_b + s["bb"] + s["bs"]
    lam_sp = mu_s + s["ss"] + s["sb"]
    if rng.random() < (lam_bp + lam_sp) / (lam_b + lam_s):
        side = +1 if rng.random() < lam_bp / (lam_bp + lam_sp) else -1
        if side == +1:
            s["bb"] += a_self; s["sb"] += a_cross
        else:
            s["ss"] += a_self; s["bs"] += a_cross
        events.append((tp, side))
    t = tp

times = np.array([e[0] for e in events])
sides = np.array([e[1] for e in events])

# intensities at each event (pre-jump), computed exactly from history
lam_b_e = np.zeros(len(events)); lam_s_e = np.zeros(len(events))
for k in range(len(events)):
    tk = times[k]
    past_b = times[(times < tk) & (sides == 1)]
    past_s = times[(times < tk) & (sides == -1)]
    lam_b_e[k] = mu_b + a_self * np.sum(np.exp(-b_self * (tk - past_b))) \
                       + a_cross * np.sum(np.exp(-b_cross * (tk - past_s)))
    lam_s_e[k] = mu_s + a_self * np.sum(np.exp(-b_self * (tk - past_s))) \
                       + a_cross * np.sum(np.exp(-b_cross * (tk - past_b)))
d_e = lam_b_e - lam_s_e
m_d, sd_d = d_e.mean(), d_e.std()
z_e = (d_e - m_d) / sd_d

# intensities on a grid for the chart
grid = np.arange(0, T, 0.1)
tb = times[sides == 1]; ts = times[sides == -1]
Lam_b = mu_b + a_self * np.sum(np.exp(-b_self * np.maximum(grid[:, None] - tb[None, :], 0))
                               * (tb[None, :] < grid[:, None]), axis=1) \
               + a_cross * np.sum(np.exp(-b_cross * np.maximum(grid[:, None] - ts[None, :], 0))
                                  * (ts[None, :] < grid[:, None]), axis=1)
Lam_s = mu_s + a_self * np.sum(np.exp(-b_self * np.maximum(grid[:, None] - ts[None, :], 0))
                               * (ts[None, :] < grid[:, None]), axis=1) \
               + a_cross * np.sum(np.exp(-b_cross * np.maximum(grid[:, None] - tb[None, :], 0))
                                  * (tb[None, :] < grid[:, None]), axis=1)
z_g = ((Lam_b - Lam_s) - m_d) / sd_d

# ---- print worked-example table: 12 events around the largest |z| burst ----
k0 = int(np.argmax(np.abs(z_e)))
lo, hi = max(0, k0 - 6), min(len(events), k0 + 6)
print(f"burst centered at event {k0}; sample mean(d)={m_d:.4f} sd(d)={sd_d:.4f}")
print("idx | time (s) | side | lam_b (1/s) | lam_s (1/s) | d=lam_b-lam_s | z")
for k in range(lo, hi):
    print(f"{k:>3} | {times[k]:>8.2f} | {'BUY ' if sides[k]==1 else 'SELL'} | "
          f"{lam_b_e[k]:>11.3f} | {lam_s_e[k]:>11.3f} | {d_e[k]:>13.3f} | {z_e[k]:>6.2f}")

# ---- chart ----
fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 2]})
ax1.plot(grid, Lam_b, color=PALETTE["price"], lw=1.3, label="buy intensity (1/s)")
ax1.plot(grid, Lam_s, color=PALETTE["signal"], lw=1.3, label="sell intensity (1/s)")
ax1.set_ylabel("intensity (events/s)")
ax1.legend(loc="upper right")
ax1.set_title("S081 — Hawkes buy/sell intensity imbalance: 90-s synthetic tape (seed 81)")

ax2.plot(grid, z_g, color=PALETTE["signal2"], lw=1.3, label="z-scored imbalance")
ax2.axhline(2.0, color=PALETTE["zero"], ls="--", lw=1, label="burst threshold (+2, example)")
ax2.axhline(-2.0, color=PALETTE["zero"], ls="--", lw=1, label="burst threshold (-2, example)")
ax2.fill_between(grid, 2.0, z_g.max() + 0.5, where=z_g > 2.0, color=PALETTE["signal2"], alpha=0.15)
ax2.fill_between(grid, z_g.min() - 0.5, -2.0, where=z_g < -2.0, color=PALETTE["signal2"], alpha=0.15)
ax2.scatter(times[sides == 1], np.full((sides == 1).sum(), 2.6), marker="^",
            color=PALETTE["price"], s=18, label="buy trades", zorder=5)
ax2.scatter(times[sides == -1], np.full((sides == -1).sum(), -2.6), marker="v",
            color=PALETTE["signal"], s=18, label="sell trades", zorder=5)
ax2.set_xlabel("time (s)")
ax2.set_ylabel("imbalance z")
ax2.legend(loc="upper right", ncol=2)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S081_example.png", bbox_inches="tight")
plt.close()
