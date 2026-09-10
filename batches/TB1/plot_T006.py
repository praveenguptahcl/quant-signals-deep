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

# ---- T006 worked example (seed 106) ----
# Synthetic 5-day allocation diary for a SPY-class ETF (~$500).
# Signals: S025 (first-half-hour return, deseasonalized), S027 (open->15:30
# formation), S079 (HMM 2-state vol regime scale). All values SYNTHETIC.
rng = np.random.default_rng(106)
_ = rng.random()  # consume once so the diary is not all-defaults

# Example parameters
R1_THRESH = 0.25      # % deseasonalized first-half-hour return (example)
TAU_HALF, TAU_SUSP = 0.60, 0.80   # HMM scale-down / suspend thresholds (example)
NOTIONAL = 100_000.0  # full-size notional (example)
PX = 500.0
COMM_SPREAD_RT = 0.01  # $/share all-in (example: 1c commission + 1c spread RT)

# Synthetic diary: (r1_deseas%, formation%, P(vol state at 15:25), last-half-hour%)
days = [
    dict(r1=0.42,  form=0.90,  pvol=0.15, r13=0.28),   # full long, winner
    dict(r1=-0.35, form=-0.70, pvol=0.25, r13=-0.22),  # full short, winner
    dict(r1=0.50,  form=1.10,  pvol=0.75, r13=-0.15),  # half long, loser
    dict(r1=0.10,  form=0.20,  pvol=0.10, r13=0.05),   # no trade (below thresh)
    dict(r1=-0.60, form=-1.30, pvol=0.85, r13=-0.40),  # suspended (toxic regime)
]

cum = 0.0
nets = []
for d in days:
    direction = 0
    scale = 0.0
    if abs(d["r1"]) >= R1_THRESH and d["pvol"] < TAU_SUSP:
        direction = 1 if d["r1"] > 0 else -1
        scale = 0.5 if d["pvol"] >= TAU_HALF else 1.0
    shares = int(NOTIONAL * scale / PX)
    signed = direction * shares
    gross = signed * PX * (d["r13"] / 100.0)
    cost = abs(shares) * COMM_SPREAD_RT
    net = gross - cost
    d.update(direction=direction, scale=scale, shares=signed, net=net)
    cum += net
    nets.append(cum)

print("T006 worked example (seed 106) — SYNTHETIC")
for i, d in enumerate(days, 1):
    pos = ("LONG " if d["direction"] > 0 else "SHORT " if d["direction"] < 0 else "FLAT ")
    print(f"day {i}: r1={d['r1']:+.2f}% form={d['form']:+.2f}% P(vol)={d['pvol']:.2f} -> "
          f"{pos} {abs(d['shares'])} sh (scale {d['scale']:.1f}) | r13={d['r13']:+.2f}% -> net ${d['net']:+.2f}")
print(f"5-day total net: ${cum:+.2f}")

# ---- Plot ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
x = np.arange(1, 6)
forms = [d["form"] for d in days]
colors = [PALETTE["profit"] if d["direction"] > 0 else
          PALETTE["loss"] if d["direction"] < 0 else PALETTE["volume"] for d in days]
ax1.bar(x, forms, color=colors, edgecolor=PALETTE["zero"], alpha=0.85,
        label="Formation return 09:30->15:30 (%) — color = position")
pvols = [d["pvol"] for d in days]
ax1b = ax1.twinx()
ax1b.plot(x, pvols, color=PALETTE["signal2"], marker="o", lw=1.6,
          label="HMM P(volatile state) @15:25")
ax1b.set_ylim(0, 1.05)
ax1b.set_ylabel("P(volatile)", color=PALETTE["signal2"])
ax1b.axhline(TAU_HALF, color=PALETTE["signal2"], ls=":", lw=1)
ax1b.axhline(TAU_SUSP, color=PALETTE["signal2"], ls="--", lw=1)
ax1.set_xticks(x)
ax1.set_xticklabels([f"Day {i}" for i in x])
ax1.set_ylabel("Formation return (%)")
ax1.set_title("T006 — Intraday Trend + Vol-Regime Allocator: synthetic 5-day allocation diary")
h1, l1 = ax1.get_legend_handles_labels()
h2, l2 = ax1b.get_legend_handles_labels()
ax1.legend(h1 + h2, l1 + l2, loc="upper left", ncol=2)

daily = [d["net"] for d in days]
ax2.step(np.arange(0, 6), [0] + nets, where="post", color=PALETTE["price"],
         lw=1.8, label="Cumulative net P&L ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
for i, v in enumerate(daily, 1):
    ax2.annotate(f"${v:+.0f}", xy=(i - 0.5, nets[i - 1]), xytext=(0, 12 if v >= 0 else -18),
                 textcoords="offset points", ha="center", fontsize=8,
                 color=PALETTE["profit"] if v > 0 else PALETTE["loss"] if v < 0 else PALETTE["volume"],
                 weight="bold")
ax2.set_xlim(0.5, 5.5)
ax2.set_xlabel("Synthetic trading day (seed 106)")
ax2.set_ylabel("Net P&L ($)")
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
plt.savefig(ROOT / "images" / "T006_example.png", bbox_inches="tight")
plt.close()
print("saved", ROOT / "images" / "T006_example.png")
