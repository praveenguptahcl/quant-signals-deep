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

rng = np.random.default_rng(192)  # seed 192 — stated in T092 text

# ---- Worked example (SYNTHETIC) — same numbers as T092 T4 ----
# $500k paper book, 6 candidate momentum trades; 4 vetoed by PIN/VPIN gates.
# Taken: A +$1,240, B −$410 (gross +$830); vetoed would-be: −$980, −$620, −$1,150, −$340.
# Costs 1.5c RT x 2,000 sh = $30/trade. Gated net +$770; ungated net −$2,440.
buckets = np.arange(78)  # 5-min buckets across RTH
toxic = 42 + 18 * np.sin(buckets / 9.0 + 1.2) + 6 * rng.standard_normal(78)
toxic = np.clip(toxic, 5, 95)
VETO_LINE = 60.0  # example toxicity veto

taken_t = np.array([12, 55])       # bucket indices of the 2 taken trades
taken_gross = np.array([1240, -410])
vetoed_t = np.array([30, 41, 49, 68])  # bucket indices of the 4 vetoed candidates
vetoed_wouldbe = np.array([-980, -620, -1150, -340])

COST_PER_TRADE = 2000 * 0.015  # $30
gated_gross = float(taken_gross.sum())
gated_net = gated_gross - 2 * COST_PER_TRADE
ungated_net = gated_gross + float(vetoed_wouldbe.sum()) - 6 * COST_PER_TRADE
print(f"T092 ledger: gated_gross={gated_gross:.0f} gated_net={gated_net:.0f} ungated_net={ungated_net:.0f}")

# cumulative paths for panel 2 (event-ordered: A vetoes interleaved by time)
order = np.array([0, 1, 2, 3, 4, 5])  # event order: A, C, D, E, B, F
ev_gated = np.array([1240, 0, 0, 0, -410, 0], dtype=float)
ev_gated_net = np.cumsum(ev_gated) - np.cumsum([30, 0, 0, 0, 30, 0])
ev_ungated = np.array([1240, -980, -620, -1150, -410, -340], dtype=float)
ev_ungated_net = np.cumsum(ev_ungated) - 30 * np.arange(1, 7)
labels = ["A\ntake", "C\nveto", "D\nveto", "E\nveto", "B\ntake", "F\nveto"]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=False,
                               gridspec_kw={"height_ratios": [1.1, 1]})
fig.suptitle("T092 — PIN-Gated Informed-Flow Avoidance: vetoes win the day (synthetic)", fontweight="bold")

ax1.plot(buckets, toxic, color=PALETTE["signal2"], lw=1.6, label="toxicity index (VPIN %-ile + slow PIN tilt)")
ax1.axhline(VETO_LINE, color=PALETTE["loss"], ls="--", lw=1.4, label="stand-down line 60 (example)")
ax1.fill_between(buckets, VETO_LINE, 100, color=PALETTE["loss"], alpha=0.08)
for bt, g in zip(taken_t, taken_gross):
    ax1.scatter([bt], [toxic[bt]], color=PALETTE["profit"], s=100, zorder=5,
                label=f"TAKE {g:+.0f}" if bt == taken_t[0] else None)
for bt, w in zip(vetoed_t, vetoed_wouldbe):
    ax1.scatter([bt], [toxic[bt]], color=PALETTE["loss"], s=100, marker="x", zorder=5,
                label="VETO (avoided)" if bt == vetoed_t[0] else None)
ax1.set_ylabel("toxicity (percentile)")
ax1.set_xlabel("5-min bucket index (RTH session)")
ax1.legend(loc="upper left", fontsize=8)

ax2.plot(order, ev_gated_net, color=PALETTE["profit"], marker="o", lw=2, label=f"gated net +${gated_net:,.0f}")
ax2.plot(order, ev_ungated_net, color=PALETTE["loss"], marker="x", lw=2, ls="--", label=f"ungated net ${ungated_net:,.0f}")
ax2.set_xticks(order, labels)
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("cumulative net P&L ($)")
ax2.set_xlabel("candidate trades, in time order")
ax2.set_title("Gated (2 taken) vs ungated (6 taken) cumulative net P&L — synthetic", fontsize=11)
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T092_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
