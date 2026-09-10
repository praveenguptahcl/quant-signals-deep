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

# ---- T005 worked example (seed 105) ----
# Synthetic 5-minute bars, 09:30-16:00 (78 bars), fictional stock "XYZ".
# All values SYNTHETIC — not market data.
rng = np.random.default_rng(105)
n = 78
t = np.arange(n)

# Opening range (09:30-09:45, bars 0-2): synthetic anchors
ORH, ORL = 50.40, 49.80
W = ORH - ORL
RVOL_OR = 1.8        # passes >= 1.5 example gate
VPIN = 0.22          # passes <= 0.30 example toxicity gate

# Designed intraday path: break above ORH at bar 4, run to target, drift after
C = np.zeros(n)
C[0:3] = [50.10, 50.28, 50.35] + rng.normal(0, 0.02, 3)
C[3] = 50.42 + rng.normal(0, 0.01)
C[4] = 50.48 + rng.normal(0, 0.01)          # trigger bar close > ORH
C[5] = 50.52 + rng.normal(0, 0.01)          # fill at bar-5 open (approx)
rise = np.linspace(C[5], 51.05, 16)
C[6:22] = rise + rng.normal(0, 0.02, 16)
C[22:] = 51.02 + rng.normal(0, 0.03, n - 22)

BAR_RVOL_4 = 1.6     # trigger-bar RVOL passes >= 1.2 example gate
assert C[4] > ORH and BAR_RVOL_4 >= 1.2 and RVOL_OR >= 1.5 and VPIN <= 0.30

# ---- Trade logic (mirrors chapter T3 pseudocode, example thresholds) ----
R = 300.0            # dollar risk budget (example)
SPREAD = 0.02
COMM_RT = 0.01
entry_fill = C[5] + SPREAD / 2          # buy: pay ask at bar-5 open
stop = ORL
risk_share = entry_fill - stop
N = int(R // risk_share)
target = ORH + W                        # +1x OR width (1R, example)

exit_idx = None
for b in range(6, n):
    mid_exit = C[b] - SPREAD / 2
    if mid_exit >= target:               # target hit
        exit_idx = b
        break
    if C[b] + SPREAD / 2 <= stop:        # stopped
        exit_idx = b
        break
assert exit_idx is not None
exit_fill = C[exit_idx] - SPREAD / 2

gross = N * (exit_fill - entry_fill)
comm = N * COMM_RT
net = gross - comm

print("T005 worked example (seed 105) — SYNTHETIC")
print(f"OR 09:30-09:45: high {ORH:.2f} low {ORL:.2f} width {W:.2f}; RVOL_OR {RVOL_OR:.1f}x (>=1.5 pass)")
print(f"trigger bar 4 (09:50-09:55): close {C[4]:.2f} > {ORH:.2f}, bar RVOL {BAR_RVOL_4:.1f}x (>=1.2 pass), VPIN {VPIN:.2f} (<=0.30 pass)")
print(f"fill bar 5 open: buy {N} @ {entry_fill:.2f}; stop {stop:.2f}; risk/share {risk_share:.2f}")
print(f"exit bar {exit_idx}: target {target:.2f} hit -> sell @ {exit_fill:.2f}")
print(f"gross {gross:.2f} | commission {comm:.2f} | NET {net:.2f}")

# ---- Plot ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
ax1.plot(t, C, color=PALETTE["price"], lw=1.6, label="Synthetic price ($)")
ax1.axvspan(-0.5, 2.5, color=PALETTE["band"], alpha=0.35, label="Opening range 09:30-09:45")
ax1.axhline(ORH, color=PALETTE["signal"], ls="--", lw=1.2, label=f"OR high ${ORH:.2f}")
ax1.axhline(ORL, color=PALETTE["signal"], ls="--", lw=1.2, label=f"OR low ${ORL:.2f} (stop)")
ax1.axhline(target, color=PALETTE["profit"], ls=":", lw=1.2, label=f"Target ${target:.2f}")
ax1.scatter([5], [entry_fill], s=90, color=PALETTE["profit"], marker="^",
            zorder=5, label=f"Long entry @ ${entry_fill:.2f}")
ax1.scatter([exit_idx], [exit_fill], s=90, color=PALETTE["loss"], marker="v",
            zorder=5, label=f"Exit @ ${exit_fill:.2f}")
ax1.set_ylabel("Price ($)")
ax1.set_title("T005 — RVOL-Filtered Opening-Range Breakout: synthetic day and net P&L")
ax1.legend(loc="upper left", ncol=2)

cum = np.zeros(n)
cum[exit_idx:] = net
ax2.step(t, cum, where="post", color=PALETTE["profit"], lw=1.8, label="Cumulative net P&L ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.annotate(f"Trade 1 net: ${net:,.2f}", xy=(exit_idx, net), xytext=(exit_idx + 10, net + 40),
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             fontsize=9, color=PALETTE["profit"], weight="bold")
ax2.set_xlabel("5-minute bar index (bar 0 = 09:30 ET, synthetic)")
ax2.set_ylabel("Net P&L ($)")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
plt.savefig(ROOT / "images" / "T005_example.png", bbox_inches="tight")
plt.close()
print("saved", ROOT / "images" / "T005_example.png")
