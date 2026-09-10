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

rng = np.random.default_rng(182)  # T082 seed — stated in chapter text

# ---- T082 worked-example inputs (SYNTHETIC; SIMULATED-ONLY routing) ----
# Per-venue stats from direct-feed history (example weights):
# score_v = IS_v - 0.10 * eff_spread_cents - 0.50 * VPIN_v
venues = [
    {"name": "NYSE (listing)", "IS": 0.46, "eff_spread_c": 1.1, "vpin": 0.22},
    {"name": "Nasdaq",         "IS": 0.31, "eff_spread_c": 1.3, "vpin": 0.35},
    {"name": "BATS EDGX",      "IS": 0.18, "eff_spread_c": 1.5, "vpin": 0.28},
]
for v in venues:
    v["score"] = v["IS"] - 0.10 * v["eff_spread_c"] - 0.50 * v["vpin"]
    print(f"{v['name']}: score = {v['IS']:.2f} - {0.10*v['eff_spread_c']:.3f} - {0.50*v['vpin']:.3f} = {v['score']:.3f}")
winner = max(venues, key=lambda v: v["score"])
print("route-to winner:", winner["name"])

# Parent order: 10,000-share BUY of fictional "NXQ"; arrival mid $150.00
# SIMULATED-ONLY fills (require direct feeds + colocation):
fill_naive = 150.0065   # SIP-default route avg fill
fill_is    = 150.0043   # IS-weighted route avg fill (simulated)
qty = 10_000
comm = 0.005 * qty
cost_naive = qty * (fill_naive - 150.00) + comm
cost_is    = qty * (fill_is - 150.00) + comm
print(f"naive SIP-route: fill {fill_naive:.4f}, shortfall ${qty*(fill_naive-150):.2f}, +comm ${comm:.2f} = ${cost_naive:.2f}")
print(f"IS-route (SIMULATED-ONLY): fill {fill_is:.4f}, shortfall ${qty*(fill_is-150):.2f}, +comm ${comm:.2f} = ${cost_is:.2f}")
print(f"simulated saving: ${cost_naive - cost_is:.2f}")

# ---- synthetic dislocation timeline (60 s busy minute) ----
n = 600
t = np.arange(n) / 10.0
drift = 0.0008 * np.cumsum(rng.standard_normal(n)) / np.sqrt(n)
direct = 150.00 + drift
lag = np.zeros(n)
# three dislocation bursts: SIP lags direct by 1.2 / 2.0 / 1.5 ms worth of price
for (a, b, amp) in [(90, 130, 0.012), (300, 345, 0.021), (470, 510, 0.015)]:
    lag[a:b] = amp * np.sin(np.linspace(0, np.pi, b - a))
sip = direct - lag
avg_disl_ms = 1.5  # synthetic average dislocation duration (illustrative)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), gridspec_kw={"height_ratios": [3, 2]})
fig.suptitle("T082 — Information-Share Venue Router: synthetic SIP-vs-direct dislocation (seed 182)",
             fontweight="bold")
ax1.plot(t, direct, color=PALETTE["price"], lw=1.2, label="direct-feed mid (synthetic)")
ax1.plot(t, sip, color=PALETTE["signal"], lw=1.2, ls="--", label="SIP mid (synthetic, lagging)")
for (a, b, _) in [(90, 130, 0), (300, 345, 0), (470, 510, 0)]:
    ax1.axvspan(a / 10, b / 10, color=PALETTE["band"], alpha=0.5)
ax1.text(0.02, 0.92, "shaded = price dislocation (direct vs SIP)\navg duration ~1.5 ms — SIMULATED ONLY",
         transform=ax1.transAxes, fontsize=8, va="top",
         bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax1.set_ylabel("mid price ($)")
ax1.legend(loc="lower right")

names = [v["name"] for v in venues]
scores = [v["score"] for v in venues]
cols = [PALETTE["profit"] if v is winner else PALETTE["volume"] for v in venues]
ax2.barh(names, scores, color=cols)
for i, v in enumerate(venues):
    ax2.text(v["score"] + 0.01, i, f"{v['score']:.3f}  (IS {v['IS']:.2f}, spread {v['eff_spread_c']}c, VPIN {v['vpin']:.2f})",
             va="center", fontsize=8)
ax2.axvline(0, color=PALETTE["zero"], lw=1)
ax2.set_xlabel("routing score = IS - 0.10 x spread(c) - 0.50 x VPIN")
ax2.set_title("Venue routing score (synthetic per-venue stats)", fontsize=11)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.5, 0.30, "SIMULATED ONLY — no colo timestamps", fontsize=16, color="red", alpha=0.20,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T082_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
