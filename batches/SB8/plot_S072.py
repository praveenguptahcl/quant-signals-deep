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

rng = np.random.default_rng(72)  # fixed seed — reproducible
N = 30
t = np.arange(1, N + 1)
# Synthetic daily PCR_vol for fictional name "ABC": base ~0.85 + slow cycle + noise
pcr = 0.85 + 0.12 * np.sin(2 * np.pi * t / 22) + rng.normal(0, 0.06, N)
pcr = np.clip(pcr, 0.45, None)
pcr[21] = 1.95  # day 22: fear spike (synthetic event)
pcr[22] = 1.58  # day 23: elevated

L = 20  # trailing lookback for median/MAD (example)
med = np.full(N, np.nan)
z = np.full(N, np.nan)
for i in range(L, N):
    win = pcr[i - L:i]
    m = np.median(win)
    mad = np.median(np.abs(win - m))
    med[i] = m
    z[i] = (pcr[i] - m) / (1.4826 * max(mad, 1e-9))

# Bands at the last valid window for chart display (example z = +-2)
m_last = med[N - 1]
mad_last = np.median(np.abs(pcr[N - L - 1:N - 1] - m_last))
band_up = m_last + 2 * 1.4826 * mad_last
band_dn = m_last - 2 * 1.4826 * mad_last

plt.figure()
plt.plot(t, pcr, color=PALETTE["price"], lw=2, label="Daily PCR (put vol / call vol)")
plt.plot(t, med, color=PALETTE["signal2"], lw=1.5, ls="--", label="Trailing 20-day median (example)")
plt.axhline(band_up, color=PALETTE["signal"], ls=":", lw=1.5,
            label=f"z = +2 band (example, PCR ~ {band_up:.2f})")
plt.axhline(band_dn, color=PALETTE["profit"], ls=":", lw=1.5,
            label=f"z = -2 band (example, PCR ~ {band_dn:.2f})")
plt.scatter([22], [pcr[21]], color=PALETTE["signal"], s=90, zorder=5)
plt.annotate(f"Day 22 extreme\nPCR = 1.95, z = {z[21]:+.1f}\n(synthetic)",
             xy=(22, pcr[21]), xytext=(9, 1.75),
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
             fontsize=9, color=PALETTE["signal"])
plt.title("S072 — Put/call ratio: 30-day synthetic PCR tape with z-score bands")
plt.xlabel("Day (synthetic)")
plt.ylabel("Put/call volume ratio")
plt.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S072_example.png", bbox_inches="tight")
plt.close()

print("S072 worked-example table (days 19-30), seed 72:")
print("Day | PCR  | med20 | z-score | note")
for i in range(18, 30):
    note = "extreme (z>+2, example)" if (not np.isnan(z[i]) and z[i] > 2) else ""
    print(f"{i+1:>3} | {pcr[i]:.2f} | {med[i]:.2f}  | {z[i]:+.2f}   | {note}")
print(f"band z=+2 -> {band_up:.2f}; z=-2 -> {band_dn:.2f}")
