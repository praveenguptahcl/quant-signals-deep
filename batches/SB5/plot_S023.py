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

rng = np.random.default_rng(23)  # SEED 23 — stated in chapter text

C_PREV = 100.00   # prior close (synthetic)
ATR14 = 1.50      # synthetic 14-day ATR

anchors_t = np.array([0, 5, 30, 60, 120, 240, 390])  # minutes after 09:30 open
t = np.arange(0, 391)

scen = {
    "A: gap-and-go":     {"anch": [103.00, 103.60, 103.45, 103.90, 104.20, 104.05, 103.80],
                          "col": PALETTE["profit"], "gap_pct": 3.00},
    "B: gap fade":       {"anch": [101.50, 101.65, 101.30, 100.80, 100.40,  99.95,  99.90],
                          "col": PALETTE["signal"], "gap_pct": 1.50},
    "C: gap-and-reverse": {"anch": [102.50, 102.90, 102.60, 101.80, 100.60,  99.90,  99.50],
                          "col": PALETTE["signal2"], "gap_pct": 2.50},
}

fig, ax = plt.subplots()
for name, d in scen.items():
    base = np.interp(t, anchors_t, d["anch"])
    path = base + rng.normal(0, 0.06, t.size)
    for i, at in enumerate(anchors_t):  # pin exact anchor values
        path[at] = d["anch"][i]
    d["path"] = path
    ax.plot(t, path, color=d["col"], lw=1.6, label=name)

ax.axhline(C_PREV, color=PALETTE["zero"], lw=1.2, ls=":", label="prior close 100.00")
ax.axhspan(100.00, 101.00, color=PALETTE["band"], alpha=0.5)
ax.text(330, 100.55, "gap-fill band\n(fade territory)", fontsize=8, ha="center")

# Go trigger for scenario A: first break above the first-5-min high (103.60) after minute 5
pa = scen["A: gap-and-go"]["path"]
entry_idx = int(np.argmax(pa[6:] > 103.60)) + 6
ax.scatter([entry_idx], [pa[entry_idx]], color=PALETTE["profit"], s=70, zorder=5,
           label=f"A go-entry (1st 5-min high break, t={entry_idx} min)")
ax.annotate(f"entry {pa[entry_idx]:.2f}", xy=(entry_idx, pa[entry_idx]),
            xytext=(entry_idx + 40, pa[entry_idx] + 0.35),
            arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]), fontsize=9,
            color=PALETTE["profit"], weight="bold")

ax.set_xlim(0, 390)
ax.set_ylim(98.5, 105.0)
ax.set_xlabel("minutes after 09:30 open")
ax.set_ylabel("price (USD)")
ax.set_title("S023 — Gap-and-go vs fade: three synthetic 1-min gap scenarios (seed 23)")
ax.legend(loc="lower left", fontsize=8)

for name, d in scen.items():
    vals = ", ".join(f"t{a}={v:.2f}" for a, v in zip(anchors_t, d["anch"]))
    atr_mult = d["gap_pct"] / ATR14
    print(f"{name}: gap +{d['gap_pct']:.2f}% = {atr_mult:.2f}x ATR(14) | {vals}")
print(f"scenario A entry: minute {entry_idx}, price {pa[entry_idx]:.2f}")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S023_example.png", bbox_inches="tight")
plt.close()
