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

# T030 worked example — Multi-Level OFI Weighted Predictor (SYNTHETIC, seed 130)
# Seed recorded so the script is reproducible; the 10 buckets and 4 taken trades are
# the hand-verified rows in the chapter's T4 table (identical numbers).
rng = np.random.default_rng(130)
OUT = "/home/hatch/workspace/quant-signals-deep/images/T030_example.png"

# 10 synthetic 1-s buckets. iOFI = integrated 10-level OFI (shares, example weights);
# bp = S005 static book pressure; lri_sign = S084 VAR long-run-impact sign (+1/-1).
# Trade rule: |iOFI| > 400 (example) AND sign(iOFI) == sign(bp) == lri_sign.
buckets = np.arange(1, 11)
iofi = np.array([120, 520, -180, -480, 610, -550, 90, 430, -220, 260])
bp   = np.array([0.05, 0.14, -0.06, -0.11, -0.08, -0.12, 0.03, 0.09, -0.05, 0.04])
lri  = np.array([1, 1, -1, -1, 1, -1, 1, 1, -1, 1])
theta = 400
trigger = (np.abs(iofi) > theta) & (np.sign(iofi) == np.sign(bp)) & (np.sign(iofi) == lri)

# Taken trades (bucket, direction, entry, exit, 200 shares, cost 1.0c/share round trip):
# T1 long  @100.01  -> 100.035  (+2.5c)  ; T2 short @99.99 -> 99.965 (+2.5c)
# T4 short @100.02  -> 100.045  (-2.5c)  ; T5 long  @99.97 -> 99.995 (+2.5c)
tb, tdir = np.array([2, 4, 6, 8]), np.array([1, -1, -1, 1])
entry = np.array([100.01, 99.99, 100.02, 99.97])
exitp = np.array([100.035, 99.965, 100.045, 99.995])
gross = 200 * tdir * (exitp - entry)
cost = 4 * [2.00]  # 200 shares x 1.0c (example taker round-trip cost)
cost = np.array(cost)
net = gross - cost
assert np.all(trigger[[1, 3, 5, 7]]) and not np.any(trigger[[0, 2, 4, 6, 8, 9]])
assert abs(net.sum() - 2.00) < 1e-9, (net, net.sum())
labels = {2: "+$3.00", 4: "+$3.00", 6: "-$7.00", 8: "+$3.00"}
cum = np.zeros(10); acc = 0.0
for i in range(10):
    if buckets[i] in tb:
        acc += net[list(tb).index(buckets[i])]
    cum[i] = acc

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                              gridspec_kw={"height_ratios": [1.2, 1]})
fig.suptitle("T030 — Multi-Level OFI Weighted Predictor: integrated-OFI buckets "
             "with VAR-confirmed trades and net P&L (10 synthetic buckets, seed 130)",
             fontsize=13, fontweight="bold", y=0.98)

colors = [PALETTE["profit"] if v > 0 else PALETTE["loss"] for v in iofi]
ax1.bar(buckets, iofi, color=colors, edgecolor="#2c3e50")
ax1.axhline(theta, color=PALETTE["signal"], linestyle="--", linewidth=1.2,
            label="trigger band |iOFI| > 400 (example)")
ax1.axhline(-theta, color=PALETTE["signal"], linestyle="--", linewidth=1.2)
ax1.axhline(0, color=PALETTE["zero"], linewidth=1)
for i, b in enumerate(buckets):
    if trigger[i]:
        tag = "TRADE" if b in tb else "blocked"
        ax1.annotate(tag, (b, iofi[i]), textcoords="offset points", xytext=(0, 10),
                     ha="center", fontsize=8, fontweight="bold",
                     color=PALETTE["profit"] if b in tb else PALETTE["loss"])
ax1.annotate("veto: BP -0.08 contradicts iOFI +610 (S005)", (5, 610),
             textcoords="offset points", xytext=(-60, 18), fontsize=8,
             color=PALETTE["loss"], arrowprops=dict(arrowstyle="->", color=PALETTE["loss"]))
ax1.set_xlabel("1-s bucket")
ax1.set_ylabel("integrated 10-level OFI (shares)")
ax1.set_title("Integrated OFI buckets; trades need iOFI + BP + VAR-LRI sign agreement")
ax1.legend(loc="lower right")

x = np.arange(10)
ax2.step(x, cum, where="mid", color=PALETTE["price"], linewidth=2.2,
         label="cumulative net P&L (after 1.0c/share taker cost)")
ax2.scatter(x, cum, s=60, zorder=5, edgecolors="#2c3e50", c=PALETTE["price"])
for b, a in labels.items():
    i = b - 1
    ax2.annotate(a, (x[i], cum[i]), textcoords="offset points", xytext=(0, 12),
                 ha="center", fontsize=8.5, fontweight="bold",
                 color=PALETTE["profit"] if float(a[2:]) > 0 else PALETTE["loss"])
ax2.annotate("entry/exit prices in T4 table", (x[5], cum[5]),
             textcoords="offset points", xytext=(40, -18), fontsize=8, color="#7f8c8d",
             arrowprops=dict(arrowstyle="->", color="#7f8c8d"))
ax2.axhline(0, color=PALETTE["zero"], linewidth=1)
ax2.set_xticks(x); ax2.set_xticklabels([f"B{b}" for b in buckets])
ax2.set_xlabel("bucket (event order)")
ax2.set_ylabel("cumulative net P&L ($)")
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig(OUT, bbox_inches="tight")
plt.close()
print("wrote", OUT, "| net total $%.2f" % cum[-1])
