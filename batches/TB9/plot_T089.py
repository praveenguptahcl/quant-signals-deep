import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
import os

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

rng = np.random.default_rng(189)  # T089 seed — stated in chapter text

# ---- T089 worked-example inputs (SYNTHETIC; SIMULATED-ONLY) ----
# Fictional "LGX" $200.00. Dislocation = |direct mid - SIP mid|.
# Capture rule (example): trade only if dislocation > effective half-spread (0.6c) + take fee (0.3c) = 0.9c
half_spread_c, fee_c, gate_c = 0.6, 0.3, 0.9
events = [
    {"dis_c": 1.2, "sh": 300, "dir": "buy the lagging SIP ask"},
    {"dis_c": 2.1, "sh": 500, "dir": "buy the lagging SIP ask"},
    {"dis_c": 0.7, "sh": 200, "dir": "skip (below gate)"},
    {"dis_c": 3.4, "sh": 400, "dir": "sell the lagging SIP bid"},
    {"dis_c": 1.0, "sh": 300, "dir": "buy the lagging SIP ask"},
    {"dis_c": 0.5, "sh": 500, "dir": "skip (below gate)"},
    {"dis_c": 2.8, "sh": 200, "dir": "sell the lagging SIP bid"},
    {"dis_c": 1.6, "sh": 600, "dir": "buy the lagging SIP ask"},
]
print("evt | disloc(c) | sh | traded? | net capture ($)")
tot, tot_sh = 0.0, 0
nets = []
for i, e in enumerate(events, 1):
    if e["dis_c"] > gate_c:
        n = (e["dis_c"] - gate_c) / 100 * e["sh"]
        traded = "yes"
        tot += n; tot_sh += e["sh"]
    else:
        n = 0.0; traded = "no"
    nets.append(n)
    print(f"{i:3d} | {e['dis_c']:7.1f} | {e['sh']:3d} | {traded:7s} | ${n:6.2f}")
print(f"TOTAL simulated capture = ${tot:.2f} on {tot_sh} shares (6 of 8 events traded)")
print("REQUIRES co-location + direct feeds; SIP-only remote = infeasible in production")

# synthetic 60-s dislocation timeline for the plot
n = 600
t = np.arange(n) / 10.0
base = 200.00 + 0.01 * np.cumsum(rng.standard_normal(n)) / np.sqrt(n)
dis = np.zeros(n)
bursts = [(80, 120), (250, 300), (420, 470), (540, 570)]
amps = [0.012, 0.021, 0.034, 0.016]
for (a, b), amp in zip(bursts, amps):
    dis[a:b] = amp * np.sin(np.linspace(0, np.pi, b - a))
direct = base + dis / 2
sip = base - dis / 2

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), gridspec_kw={"height_ratios": [3, 2]})
fig.suptitle("T089 — Quote-Matcher (SIP-vs-Direct): synthetic dislocation capture (seed 189)",
             fontweight="bold")
ax1.plot(t, direct, color=PALETTE["price"], lw=1.2, label="direct-feed mid (synthetic)")
ax1.plot(t, sip, color=PALETTE["signal"], lw=1.2, ls="--", label="SIP mid (synthetic)")
for (a, b) in bursts:
    ax1.axvspan(a / 10, b / 10, color=PALETTE["band"], alpha=0.55)
ax1.axhline(200.00, color=PALETTE["zero"], lw=0.8)
ax1.text(0.02, 0.90, "shaded = dislocation windows\navg ~1.5 ms — SIMULATED ONLY",
         transform=ax1.transAxes, fontsize=8, va="top",
         bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax1.set_ylabel("mid price ($)")
ax1.legend(loc="lower right", fontsize=8)

x = np.arange(1, 9)
cols = [PALETTE["profit"] if n_ > 0 else PALETTE["volume"] for n_ in nets]
ax2.bar(x, nets, color=cols)
ax2.axhline(0, color=PALETTE["zero"], lw=1)
for i, n_ in enumerate(nets):
    lbl = f"${n_:.2f}" if n_ > 0 else "skip"
    ax2.text(i + 1, max(n_, 0) + 0.25, lbl, ha="center", fontsize=8)
ax2.set_xticks(x)
ax2.set_xlabel("dislocation event (synthetic)")
ax2.set_ylabel("net capture ($)")
ax2.set_title(f"8 events -> ${tot:.2f} simulated capture (gate {gate_c}c); REQUIRES co-lo + direct feeds",
              fontsize=11)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.5, 0.30, "SIMULATED ONLY — requires co-location + direct feeds", fontsize=15, color="red",
         alpha=0.20, ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T089_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
