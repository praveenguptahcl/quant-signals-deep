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

# ---- Reproducibility ----
rng = np.random.default_rng(63)   # fixed seed; tape values reproduced in chapter S4
n = 10
px = 100.0
O = np.zeros(n); H = np.zeros(n); L = np.zeros(n); C = np.zeros(n)
for i in range(n):
    gap = rng.normal(0, 0.004)
    o = px * (1 + gap)
    drift = rng.normal(0.0005, 0.010)
    c = o * (1 + drift)
    hi_rng = abs(rng.normal(0.006, 0.004)) + max(0, drift if drift > 0 else 0) * 0.3
    lo_rng = abs(rng.normal(0.006, 0.004)) + max(0, -drift if drift < 0 else 0) * 0.3
    h = max(o, c) * (1 + hi_rng)
    l = min(o, c) * (1 - lo_rng)
    O[i], H[i], L[i], C[i] = o, h, l, c
    px = c

ln = np.log
p_var = (ln(H / L) ** 2) / (4 * ln(2))                                     # Parkinson
gk_var = 0.5 * ln(H / L) ** 2 - (2 * ln(2) - 1) * ln(C / O) ** 2           # Garman-Klass
rs_var = ln(H / C) * ln(H / O) + ln(L / C) * ln(L / O)                     # Rogers-Satchell
# Yang-Zhang (window-level): overnight var + k * open-close var + (1-k) * RS var
s2o = np.mean(ln(O[1:] / C[:-1]) ** 2)
s2c = np.mean(ln(C / O) ** 2)            # actual open-to-close variance (NOT mean GK)
k_w = 0.34 / (1.34 + (n + 1) / (n - 1))
yz_var = s2o + k_w * s2c + (1 - k_w) * rs_var.mean()
print("S063: s2o=%.8f s2c=%.8f yz_var=%.8f ann=%.2f%%" % (s2o, s2c, yz_var, np.sqrt(yz_var) * np.sqrt(252) * 100))

days = np.arange(1, n + 1)
fig, ax = plt.subplots()
ax.plot(days, np.sqrt(p_var) * 100, marker="o", color=PALETTE["price"],
        label=f"Parkinson (avg ann {np.sqrt(p_var.mean())*np.sqrt(252)*100:.2f}%)")
ax.plot(days, np.sqrt(gk_var) * 100, marker="s", color=PALETTE["signal"],
        label=f"Garman-Klass (avg ann {np.sqrt(gk_var.mean())*np.sqrt(252)*100:.2f}%)")
ax.plot(days, np.sqrt(rs_var) * 100, marker="^", color=PALETTE["signal2"],
        label=f"Rogers-Satchell (avg ann {np.sqrt(rs_var.mean())*np.sqrt(252)*100:.2f}%)")
ax.axhline(np.sqrt(yz_var) * 100, color=PALETTE["profit"], linestyle="--", linewidth=1.6,
           label=f"Yang-Zhang window (ann {np.sqrt(yz_var)*np.sqrt(252)*100:.2f}%)")
ax.set_title("S063 — Range-based vol estimators: daily sig, 10-day synthetic tape (seed 63)")
ax.set_xlabel("Day (D1..D10)")
ax.set_ylabel("Estimated daily sigma (%)")
ax.set_xticks(days)
ax.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S063_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
