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

# ---- SYNTHETIC DATA (seed 33) ----
rng = np.random.default_rng(33)

REF = 149.80  # reference price (prior close)
msg_t = np.array([0, 20, 40, 60, 75, 90, 105, 115], dtype=float)  # seconds after 09:28:00
ind_base = np.array([150.18, 150.26, 150.33, 150.41, 150.38, 150.46, 150.52, 150.55])
paired_base = np.array([120, 210, 340, 480, 560, 700, 860, 980]) * 1000
imb_base = np.array([85, 110, 140, 165, 150, 185, 205, 215]) * 1000  # signed buy imbalance

ind = ind_base + rng.uniform(-0.015, 0.015, size=len(msg_t))
paired = (paired_base + rng.integers(-8000, 8000, size=len(msg_t))).astype(int)
imb = (imb_base + rng.integers(-4000, 4000, size=len(msg_t))).astype(int)
imb_ratio = imb / paired
ind_move_bps = (ind - REF) / REF * 1e4

print("  time   | status | ind.price | paired(sh) | imb.buy(sh) | imb_ratio | ind vs ref (bps)")
labels = ["09:28:00", "09:28:20", "09:28:40", "09:29:00", "09:29:15",
          "09:29:30", "09:29:45", "09:29:55"]
for i in range(len(msg_t)):
    st = "Open " if i < len(msg_t) - 1 else "Final"
    print(f"{labels[i]} | {st} | {ind[i]:9.2f} | {paired[i]:10d} | {imb[i]:11d} "
          f"| {imb_ratio[i]:8.1%} | {ind_move_bps[i]:14.1f}")
print(f"final imbalance ratio = {imb_ratio[-1]:.1%}; final indicative vs ref = {ind_move_bps[-1]:.1f} bps")

# synthetic first 5 one-minute continuous-session closes after the open print
open_print = 150.55
m1 = np.array([150.62, 150.70, 150.66, 150.74, 150.81])
print(f"open print = {open_print:.2f}; 1-min closes 09:30-09:35 = {m1}")
print(f"5-min continuation = {(m1[-1] - open_print):+.2f} = {(m1[-1]-open_print)/open_print*1e4:+.1f} bps before costs")

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
x_min = msg_t / 60.0  # minutes after 09:28:00
ax1.plot(x_min, ind, color=PALETTE["price"], marker="o", ms=5,
         label="Indicative clearing price (NOII messages)")
ax1.axvline(2.0, color=PALETTE["signal"], ls="--", lw=1.5, label="Open auction print (09:30)")
ax1.plot([2.0, 2.0], [open_print, open_print], color=PALETTE["signal"], marker="D", ms=7)
m1x = np.arange(2.2, 2.2 + len(m1) * 1.0, 1.0)
ax1.plot(m1x, m1, color=PALETTE["profit"], marker="s", ms=5, label="1-min closes (continuation)")
ax1.axhline(REF, color=PALETTE["zero"], ls=":", lw=1, label=f"Reference price {REF:.2f}")
ax1.set_ylabel("Price ($)")
ax1.set_title("S033 — Opening-auction imbalance: synthetic NOII message timeline (seed 33)")
ax1.set_xlim(-0.1, 7.4)
ax1.legend(loc="upper left")

ax2.bar(x_min, paired / 1000, width=0.18, color=PALETTE["band"],
        edgecolor=PALETTE["price"], label="Paired shares (000s)")
ax2.set_ylabel("Paired shares (000s)")
ax2.set_xlabel("Minutes after 09:28:00 ET")
ax2.set_xticks([0, 1, 2, 3, 4, 5, 6, 7])
ax2.set_xticklabels(["09:28", "09:29", "09:30\n(open)", "09:31", "09:32", "09:33", "09:34", "09:35"])
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S033_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
