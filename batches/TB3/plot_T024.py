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

rng = np.random.default_rng(124)

# ---- Synthetic ZVXR mid-price path, minutes from 10:00 ET ----
# Event prices match the T4 table exactly (forced at event minutes).
events = [  # (minute, price or None)
    (0, 45.00),
    (12, 45.02), (42, 45.09),       # trade 1: long 500 @ 45.02 -> 45.09, net +29.50
    (65, 44.98), (95, 44.90),       # trade 2: short 500 @ 44.98 -> 44.90, net +34.50
    (200, 45.10), (260, 45.14),     # trade 3: short 500 @ 45.10 -> 45.14, net -25.50
    (285, 44.85), (330, 44.93),     # trade 4: long 500 @ 44.85 -> 44.93, net +34.50
]
t = np.arange(0, 341)
ev_t = np.array([e[0] for e in events])
ev_p = np.array([e[1] for e in events])
base = np.interp(t, ev_t, ev_p)
# noise that vanishes exactly at event minutes
d = np.min(np.abs(t[:, None] - ev_t[None, :]), axis=1)
w = np.clip(d / 8.0, 0, 1)
noise = rng.normal(0, 0.012, size=t.shape) * w
price = base + noise

fig, ax = plt.subplots()
ax.plot(t, price, color=PALETTE["price"], lw=1.6, label="ZVXR synthetic mid ($)")

trades = [
    (12, 45.02, 42, 45.09, "long",  "+29.50"),
    (65, 44.98, 95, 44.90, "short", "+34.50"),
    (200, 45.10, 260, 45.14, "short", "-25.50"),
    (285, 44.85, 330, 44.93, "long",  "+34.50"),
]
for i, (te, pe, tx, px, side, net) in enumerate(trades, 1):
    mk_in = "^" if side == "long" else "v"
    col = PALETTE["profit"] if float(net) > 0 else PALETTE["loss"]
    ax.scatter([te], [pe], s=90, marker=mk_in, color=PALETTE["signal"],
               edgecolors="black", linewidths=0.7, zorder=5)
    ax.scatter([tx], [px], s=90, marker="x", color=PALETTE["signal2"],
               linewidths=2.2, zorder=5)
    ax.annotate(f"T{i} {side}\nnet ${net}",
                xy=((te + tx) / 2, (pe + px) / 2), xytext=(0, 26 if i % 2 else -34),
                textcoords="offset points", ha="center", fontsize=8,
                color=col, weight="bold",
                arrowprops=dict(arrowstyle="-", color=col, lw=0.8))

ax.scatter([], [], s=90, marker="^", color=PALETTE["signal"],
           edgecolors="black", label="entry (triangle)")
ax.scatter([], [], s=90, marker="x", color=PALETTE["signal2"],
           linewidths=2.2, label="exit (x)")
ax.set_xlabel("Minutes from 10:00 ET")
ax.set_ylabel("Price ($)")
ax.set_title("T024 — Informed-Size Tracker / Retail Fade: synthetic trade timeline (seed 124)")
ax.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T024_example.png", bbox_inches="tight")
plt.close()
