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

rng = np.random.default_rng(42)  # seed 42 — stated in chapter text

# Synthetic 12-trade tape (hand-picked prices; sizes from seed 42)
prices = np.array([100.00, 100.02, 100.01, 100.01, 100.03, 100.05,
                   100.04, 100.06, 100.08, 100.07, 100.09, 100.11])
sizes = rng.integers(100, 900, size=12)

# Tick-rule classification: +1 uptick, -1 downtick, carry forward on zero tick
prev_px = 99.99
eps, signed = [], []
for p, v in zip(prices, sizes):
    if p > prev_px:
        e = 1
    elif p < prev_px:
        e = -1
    else:
        e = eps[-1] if eps else 1
    eps.append(e)
    signed.append(e * v)
    prev_px = p
signed = np.array(signed, dtype=float)
cum_ti = np.cumsum(signed)

# Print the worked-example table (copy into chapter S4)
print("trade | price | size | tick-rule eps | signed vol | cum TI")
for i, (p, v, e, s, c) in enumerate(zip(prices, sizes, eps, signed, cum_ti), 1):
    print(f"{i:>2} | {p:7.2f} | {v:>4} | {e:+d} | {s:+8.0f} | {c:+8.0f}")

# 3-trade windows: normalized delta (Vbuy - Vsell)/(Vbuy + Vsell)
for w in range(4):
    sl = signed[w*3:(w+1)*3]
    tot = np.sum(np.abs(sl))
    d = sl.sum() / tot
    print(f"window {w+1} (trades {w*3+1}-{w*3+3}): delta={d:+.4f}")
deltas = np.array([signed[w*3:(w+1)*3].sum()/np.sum(np.abs(signed[w*3:(w+1)*3])) for w in range(4)])
print("z of last window vs 4 windows:",
      (deltas[-1]-deltas.mean())/deltas.std(ddof=1))

# ---- Plot: signed-volume bars + cumulative TI line (same units: shares) ----
x = np.arange(1, 13)
fig, ax = plt.subplots()
colors = [PALETTE["profit"] if s >= 0 else PALETTE["loss"] for s in signed]
ax.bar(x, signed, color=colors, alpha=0.75, label="Signed volume (tick-rule ε·V, shares)")
ax.plot(x, cum_ti, color=PALETTE["price"], marker="o", linewidth=2.2,
        label="Cumulative trade imbalance (shares)")
ax.axhline(0, color=PALETTE["zero"], linewidth=1)
ax.set_title("S006 — Signed trade imbalance (volume delta): 12-trade synthetic tape")
ax.set_xlabel("Trade # (event time)")
ax.set_ylabel("Shares")
ax.set_xticks(x)
ax.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S006_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S006_example.png")
