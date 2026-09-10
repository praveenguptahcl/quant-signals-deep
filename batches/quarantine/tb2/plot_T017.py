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

# ---- T017 worked example (seed 117) ----
# Synthetic scheduled releases on ETF SYNM at $600. Rule: enter at tau+1 in sign(R_jump)
# only if |R_jump| > kappa * sig_diurnal (kappa=2.5) AND S092 identified_news=1.
# Size: risk $500 to HAR-forecast 30-min vol. Exit at tau+30min. All SYNTHETIC.
rng = np.random.default_rng(117)
_ = rng.random()
PX = 600.0
KAPPA = 2.5
RISK = 500.0
HALF_SPREAD, COMM, TICKET = 0.01, 0.005, 0.50

# R_jump%: 2-min jump; sig_d%: diurnal 1-min vol; news: identified-news flag;
# fcast%: HAR 30-min vol forecast; cont%: post-window drift in jump direction
events = [
    dict(name="FOMC-like 14:00", Rj=0.35,  sigd=0.10, news=1, fcast=0.45, cont=0.22),
    dict(name="CPI-like 08:30",  Rj=-0.28, sigd=0.09, news=1, fcast=0.60, cont=-0.30),
    dict(name="NFP-like 08:30",  Rj=0.19,  sigd=0.12, news=1, fcast=0.50, cont=0.10),
    dict(name="NFP-2 08:30",      Rj=0.31,  sigd=0.10, news=0, fcast=0.55, cont=0.25),
]

cum = 0.0
print("event, R_jump%, sig_d%, z, news, fcast%, shares, decision, net")
for e in events:
    z = abs(e["Rj"]) / e["sigd"]
    e["z"] = z
    trade = (z > KAPPA) and (e["news"] == 1)
    shares = int(RISK / ((e["fcast"] / 100) * PX)) if trade else 0
    net = 0.0
    if trade:
        gross = shares * PX * (abs(e["cont"]) / 100)
        net = gross - 2 * (HALF_SPREAD * shares) - 2 * (COMM * shares + TICKET)
        e["dec"] = f"{'LONG' if e['Rj'] > 0 else 'SHORT'} {shares}"
    else:
        e["dec"] = "FLAT (z<kappa)" if z <= KAPPA else "FLAT (no identified news)"
    e.update(shares=shares, net=net)
    cum += net
    e["cum"] = cum
    print(f"{e['name']}, {e['Rj']:+.2f}, {e['sigd']:.2f}, {z:.2f}, {e['news']}, {e['fcast']:.2f}, {shares}, {e['dec']}, {net:+.2f}")
print(f"TOTAL NET = {cum:+.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [3, 1.6]})
x = np.arange(1, 5)
zs = [e["z"] for e in events]
cols = [PALETTE["profit"] if e["shares"] > 0 else PALETTE["volume"] for e in events]
ax1.bar(x, zs, color=cols, edgecolor="black", lw=0.8,
        label="Jump z = |R_jump| / sigma_diurnal")
ax1.axhline(KAPPA, color=PALETTE["signal"], ls="--", lw=1.4, label=f"kappa = {KAPPA} (example)")
for i, e in enumerate(events, 1):
    ax1.text(i, e["z"] + 0.08, f"news={'Y' if e['news'] else 'N'}\n{e['dec'].split(' (')[0]}",
             ha="center", fontsize=7, weight="bold")
ax1.set_xticks(x)
ax1.set_xticklabels([e["name"] for e in events], fontsize=8)
ax1.set_ylabel("Jump z-score")
ax1.set_title("T017 — Scheduled Macro-Announcement Drift: synthetic 4-event diary")
ax1.legend(loc="upper left", fontsize=8)

ax2.step(np.arange(0, 5), [0.0] + [e["cum"] for e in events], where="post",
         color=PALETTE["price"], lw=1.8, label="Cumulative net P&L ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
for i, e in enumerate(events, 1):
    ax2.annotate(f"${e['net']:+.0f}", xy=(i, e["cum"]),
                 xytext=(0, 12 if e["net"] >= 0 else -18), textcoords="offset points",
                 ha="center", fontsize=8, weight="bold",
                 color=PALETTE["profit"] if e["net"] > 0 else PALETTE["loss"] if e["net"] < 0 else PALETTE["volume"])
ax2.set_xlim(0.6, 4.4)
ax2.set_xlabel("Synthetic scheduled release (seed 117)")
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
plt.savefig(ROOT / "images" / "T017_example.png", bbox_inches="tight")
plt.close()
print("saved", ROOT / "images" / "T017_example.png")
