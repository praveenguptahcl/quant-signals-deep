import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

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

# ---- T015 worked example (seed 115) ----
# Synthetic 5-day diary, SPY-class ETF at $500. S026 sign(r1_tilde) on S046-deseasonalized
# first-half-hour return; S027 formation confirm; S046 event-day halve. All SYNTHETIC.
rng = np.random.default_rng(115)
_ = rng.random()
PX = 500.0
R1_THRESH = 0.0025          # deseasonalized |r1| minimum (example)
COST_RT = 0.01              # $/share all-in round trip (example)
BASE_SHARES = 200

# (r1_raw%, diurnal s of open bucket, r_first%, event_day, r13%)
days = [
    dict(r1=0.76, s=1.80, rf=0.95,  ev=0, r13=0.28),   # long full, winner
    dict(r1=-0.63, s=1.80, rf=-0.80, ev=0, r13=-0.22), # short full, winner
    dict(r1=0.18, s=1.80, rf=0.20,  ev=0, r13=0.05),   # flat: below impulse
    dict(r1=0.99, s=1.80, rf=1.20,  ev=1, r13=-0.18),  # CPI day: half long, loser
    dict(r1=-0.90, s=1.80, rf=0.30, ev=0, r13=-0.40),  # flat: S027 disagrees
]

cum = 0.0
print("day, r1_raw%, s, r1_tilde%, r_first%, decision, shares, r13%, net")
for i, d in enumerate(days, 1):
    d["r1t"] = d["r1"] / d["s"]
    dec, shares, net, r13p = "FLAT", 0, 0.0, d["r13"]
    if abs(d["r1t"] / 100) >= R1_THRESH:
        if np.sign(d["rf"]) == np.sign(d["r1t"]):
            side = int(np.sign(d["r1t"]))
            shares = BASE_SHARES // 2 if d["ev"] else BASE_SHARES
            gross = side * shares * PX * (d["r13"] / 100)
            net = gross - COST_RT * shares
            dec = f"{'LONG' if side > 0 else 'SHORT'}{' (halved: event day)' if d['ev'] else ''}"
        else:
            dec = "FLAT (S027 disagrees)"
    else:
        dec = "FLAT (below impulse)"
    d.update(dec=dec, shares=shares, net=net)
    cum += net
    d["cum"] = cum
    print(f"{i}, {d['r1']:+.2f}, {d['s']:.2f}, {d['r1t']:+.2f}, {d['rf']:+.2f}, {dec}, {shares}, {r13p:+.2f}, {net:+.2f}")
print(f"TOTAL NET = {cum:+.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [3, 1.6]})
x = np.arange(1, 6)
cols = [PALETTE["profit"] if d["shares"] > 0 and np.sign(d["r1t"]) > 0
        else PALETTE["loss"] if d["shares"] > 0 else PALETTE["volume"] for d in days]
ax1.bar(x, [d["rf"] for d in days], color=cols, edgecolor="black", lw=0.8,
        label="Formation return r_first (open->15:30, %)")
ax1.bar(x, [d["r1t"] for d in days], color="none", edgecolor=PALETTE["signal2"], lw=1.6,
        label="Deseasonalized r1_tilde (S026/S046, %)")
for i, d in enumerate(days, 1):
    ax1.text(i, d["rf"] + (0.08 if d["rf"] >= 0 else -0.16), d["dec"].split(" (")[0],
             ha="center", fontsize=7, weight="bold")
ax1.axhline(R1_THRESH * 100, color=PALETTE["signal2"], ls=":", lw=1, label="|r1_tilde| 0.25% gate")
ax1.axhline(-R1_THRESH * 100, color=PALETTE["signal2"], ls=":", lw=1)
ax1.set_xticks(x)
ax1.set_xticklabels([f"Day {i}" + (" (CPI)" if d["ev"] else "") for i, d in enumerate(days, 1)])
ax1.set_ylabel("Return (%)")
ax1.set_title("T015 — First-Half-Hour → Close Continuation: synthetic 5-day diary")
ax1.legend(loc="upper left", fontsize=8)

ax2.step(np.arange(0, 6), [0.0] + [d["cum"] for d in days], where="post",
         color=PALETTE["price"], lw=1.8, label="Cumulative net P&L ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
for i, d in enumerate(days, 1):
    ax2.annotate(f"${d['net']:+.0f}", xy=(i, d["cum"]),
                 xytext=(0, 12 if d["net"] >= 0 else -18), textcoords="offset points",
                 ha="center", fontsize=8, weight="bold",
                 color=PALETTE["profit"] if d["net"] > 0 else PALETTE["loss"] if d["net"] < 0 else PALETTE["volume"])
ax2.set_xlim(0.6, 5.4)
ax2.set_xlabel("Synthetic trading day (seed 115)")
ax2.set_ylabel("Net P&L ($)")
ax2.legend(loc="upper left", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
ROOT = Path(__file__).resolve().parents[2]
plt.savefig(ROOT / "images" / "T015_example.png", bbox_inches="tight")
plt.close()
print("saved", ROOT / "images" / "T015_example.png")
