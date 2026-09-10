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

# ---- VERIFIED INPUT TAPE (duckai-answers Q-SB8-1, hand-checked) ----
# 12 synthetic 5-min log returns; bar 6 is a +1% jump. Fixed tape; seed set for
# reproducibility of the script machinery (nothing is randomly drawn).
rng = np.random.default_rng(64)
r = np.array([0.001, -0.002, 0.0015, 0.0005, -0.001, 0.010,
              -0.0008, 0.0012, -0.0015, 0.0007, 0.0003, -0.0009])
n = len(r)
sq = r ** 2                                  # RV summands
adj = np.abs(r[:-1]) * np.abs(r[1:])          # BV summands (products of adjacent |r|)

RV = float(sq.sum())                         # = 0.00011422 verified
BV = float((np.pi / 2.0) * adj.sum())         # = 0.00004483 verified
J = max(RV - BV, 0.0)                         # jump proxy = 69.39e-6 verified
RJ = (RV - BV) / RV                           # relative jump

# sanity assertions against the verified values (verified values quoted to 2 decimals,
# so tolerance is half of the last quoted digit in units of 1e-6)
assert abs(RV - 0.00011422) < 0.5e-8, RV
assert abs(BV - 44.83e-6) < 0.005e-6, BV
assert abs((RV - BV) - 69.39e-6) < 0.005e-6, RV - BV

# per-bin view: where does the jump show up?
bv_per_bin = np.zeros(n)
bv_per_bin[1:] = (np.pi / 2.0) * adj / (n - 1) * n  # scale so totals match BV on plot basis

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True)

# --- top: the return tape, jump bar highlighted ---
x = np.arange(1, n + 1)
colors = [PALETTE["price"]] * n
colors[5] = PALETTE["signal"]
ax1.bar(x, r * 1e4, color=colors, edgecolor="black", linewidth=0.4)
ax1.axhline(0, color=PALETTE["zero"], linewidth=0.8)
ax1.annotate("jump: +1.0% (+100 bp)\nSquared term = 100e-6\ndominates RV",
             xy=(6, 100), xytext=(9.4, 72),
             fontsize=9, color=PALETTE["signal"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"], lw=1.4))
ax1.set_ylabel("return (basis points)")
ax1.set_title("S064 — Jump-robust RV: 12-return synthetic tape (RV = 114.22e-6, BV = 44.83e-6)")

# --- bottom: RV summands (squared returns) vs BV summands (adjacent products) ---
w = 0.38
sq_u = sq * 1e6          # units of 1e-6 for readability
adj_u = adj * 1e6
ax2.bar(x - w / 2, np.append(sq_u, 0)[:n], width=w, color=PALETTE["price"],
        label="squared returns  (RV terms)", edgecolor="black", linewidth=0.4)
ax2.bar(np.arange(2, n + 1) + w / 2, adj_u, width=w, color=PALETTE["signal2"],
        label="|r_i||r_{i+1}|  (BV terms, x pi/2 in total)", edgecolor="black", linewidth=0.4)
ax2.text(6, 60, f"RV total = {RV*1e6:.2f}e-6\nBV total = {BV*1e6:.2f}e-6\n"
                f"RV-BV (jump proxy) = {(RV-BV)*1e6:.2f}e-6\n"
                f"Relative jump = {RJ:.1%} of RV",
         fontsize=10, bbox=dict(boxstyle="round", fc="white", ec=PALETTE["zero"], alpha=0.95))
ax2.set_xlabel("5-minute interval i")
ax2.set_ylabel("contribution (x 1e-6)")
ax2.legend(loc="upper right")
ax2.set_xlim(0.4, 12.6)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S064_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print(f"RV={RV:.8f} BV={BV:.8f} J={J:.8f} RJ={RJ:.3f}")
