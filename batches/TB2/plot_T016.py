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

# ---- T016 worked example (seed 116) ----
# Synthetic 4-day diary, stock SYN at $100. Rule: at 15:00 enter sign(r_first) only if
# (a) open-auction imbalance sign agrees (S033: rho>=15%, |d|>=20bps) and (b) 20-day
# Corwin-Schultz spread estimate <= 8 bps (S013 cost gate). Exit MOC. All SYNTHETIC.
rng = np.random.default_rng(116)
_ = rng.random()
PX = 100.0
SHARES = 2000
HALF_SPREAD, COMM, TICKET = 0.015, 0.005, 0.50
CS_CAP = 8.0  # bps (example)
cost_rt = 2 * (HALF_SPREAD * SHARES) + 2 * (COMM * SHARES + TICKET)
MOC_SLIP = 0.005 * SHARES  # T2: 0.5c/share slippage on the MOC leg, deducted per traded day

# r_first%: 9:30->15:00; imb: open-auction final sign; rho%: |I|/Q_paired; d: bps displacement;
# cs: 20-day mean CS spread bps; r_last%: 15:00->close
days = [
    dict(rf=0.45,  imb=+1, rho=22.0, d=35.0,  cs=4.2, rlast=0.20),
    dict(rf=-0.30, imb=-1, rho=18.0, d=-28.0, cs=5.1, rlast=-0.15),
    dict(rf=0.25,  imb=-1, rho=16.0, d=-22.0, cs=4.8, rlast=0.10),
    dict(rf=0.60,  imb=+1, rho=25.0, d=40.0,  cs=9.5, rlast=-0.25),
]

cum = 0.0
print("day, r_first%, imb, rho%, d_bps, CS_bps, decision, r_last%, net")
for i, d in enumerate(days, 1):
    dec, side, net = "FLAT", 0, 0.0
    if np.sign(d["imb"]) == np.sign(d["rf"]) and d["cs"] <= CS_CAP:
        side = int(np.sign(d["rf"]))
        gross = side * SHARES * PX * (d["rlast"] / 100)
        net = gross - cost_rt - MOC_SLIP  # 0.5c/share MOC slippage deducted
        dec = f"{'LONG' if side > 0 else 'SHORT'} 2000"
    elif np.sign(d["imb"]) != np.sign(d["rf"]):
        dec = "FLAT (imbalance disagrees)"
    else:
        dec = "FLAT (CS spread > 8 bps)"
    d.update(dec=dec, side=side, net=net)
    cum += net
    d["cum"] = cum
    print(f"{i}, {d['rf']:+.2f}, {d['imb']:+d}, {d['rho']:.1f}, {d['d']:+.0f}, {d['cs']:.1f}, {dec}, {d['rlast']:+.2f}, {net:+.2f}")
print(f"TOTAL NET = {cum:+.2f} on cost/trade = {cost_rt:.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [3, 1.6]})
x = np.arange(1, 5)
cols = [PALETTE["profit"] if d["side"] > 0 else PALETTE["loss"] if d["side"] < 0 else PALETTE["volume"]
        for d in days]
bars = ax1.bar(x, [d["rf"] for d in days], color=cols, edgecolor="black", lw=0.8,
               label="Formation return r_first (9:30->15:00, %)")
for i, d in enumerate(days, 1):
    ax1.annotate(f"imb {'BUY' if d['imb'] > 0 else 'SELL'}\nrho={d['rho']:.0f}%",
                 xy=(i, d["rf"]), xytext=(0, 16 if d["rf"] >= 0 else -26),
                 textcoords="offset points", ha="center", fontsize=7,
                 color=PALETTE["signal2"], weight="bold")
    ax1.text(i, -0.06, f"CS {d['cs']:.1f}bp", ha="center", fontsize=7,
             color=PALETTE["zero"])
ax1.axhline(0, color=PALETTE["zero"], lw=1)
ax1.set_xticks(x)
ax1.set_xticklabels([f"Day {i}\n{d['dec'].split(' (')[0]}" for i, d in enumerate(days, 1)], fontsize=8)
ax1.set_ylabel("Return (%)")
ax1.set_title("T016 — End-of-Day Drift Rider: synthetic 4-day drift diary")
ax1.legend(loc="upper left", fontsize=8)

ax2.step(np.arange(0, 5), [0.0] + [d["cum"] for d in days], where="post",
         color=PALETTE["price"], lw=1.8, label="Cumulative net P&L ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
for i, d in enumerate(days, 1):
    ax2.annotate(f"${d['net']:+.0f}", xy=(i, d["cum"]),
                 xytext=(0, 12 if d["net"] >= 0 else -18), textcoords="offset points",
                 ha="center", fontsize=8, weight="bold",
                 color=PALETTE["profit"] if d["net"] > 0 else PALETTE["loss"] if d["net"] < 0 else PALETTE["volume"])
ax2.set_xlim(0.6, 4.4)
ax2.set_xlabel("Synthetic trading day (seed 116)")
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
plt.savefig(ROOT / "images" / "T016_example.png", bbox_inches="tight")
plt.close()
print("saved", ROOT / "images" / "T016_example.png")
