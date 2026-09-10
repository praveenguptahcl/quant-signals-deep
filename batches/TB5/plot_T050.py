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

# ---- SYNTHETIC WORKED EXAMPLE: T050 GEX pin / dealer-positioning fade (seed 150) ----
# Chapter text and chart MUST agree: both are generated from these arrays.
rng = np.random.default_rng(150)

# Synthetic modeled dealer-GEX (proxy) wall map (SPY-like, $mm per 1% spot move) — synthetic strikes
strikes = np.array([565, 570, 575, 580, 585])
gex = np.array([-420.0, 180.0, 910.0, 640.0, 210.0])
roles = {565: "put wall", 570: "", 575: "max GEX / pin magnet", 580: "call wall", 585: ""}
print("Synthetic modeled dealer-GEX (proxy) map ($mm/1%):")
for k, g in zip(strikes, gex):
    print(f"  strike {k}: {g:+.0f}  ({roles[k]})")
print("Net modeled dealer GEX (proxy) +1.8bn (positive: fade regime) | flip 568 | spot 575.20 (open)")
print("CAVEAT: full-chain OI x modeled gamma is only a proxy — OI reveals neither "
      "customer/dealer ownership nor trade direction; actual dealer positioning is unknown.")

# S070 context: 0DTE straddle-implied move (example) = (C_ATM+P_ATM)/S
call_atm, put_atm, S_ref = 2.90, 2.85, 575.20
imp_move = (call_atm + put_atm) / S_ref * 100
print(f"S070: 0DTE ATM straddle ${call_atm:.2f}+${put_atm:.2f} / S {S_ref:.2f} -> "
      f"implied move {imp_move:.2f}% = ~${S_ref*imp_move/100:.2f}; "
      f"wall distance 4.60 < implied range -> fade in play (example rule)")

# Synthetic intraday path: spot grinds 579.8 -> 577.1 -> 575.6 into the magnet
t = np.arange(20)
path = 579.80 + np.cumsum(rng.normal(-0.11, 0.18, 20))
path = np.round(path, 2)
path[-1] = 575.65
print("Path (synthetic):", ", ".join(f"{p:.2f}" for p in path))

shares = 200
entry_px, exit_px, stop_px, tgt_px = 579.75, float(path[-1]), 583.20, 575.40
cost_rt = shares * 0.005 * 2 + shares * (entry_px + exit_px) / 2 * 0.0001 * 2  # example
gross = shares * (entry_px - exit_px)   # short
net = gross - cost_rt
stop_risk = shares * (stop_px - entry_px)
print("\nTrade (line-by-line net P&L):")
print(f"  short {shares} @ {entry_px:.2f} (11:40 wall tag -> 11:45 fill) "
      f"-> cover @ {exit_px:.2f}")
print(f"  stop {stop_px:.2f} (through wall +0.6%, example) | target {tgt_px:.2f} (magnet)")
print(f"  gross {gross:+.2f}, costs {cost_rt:.2f}, NET {net:+.2f}")
print(f"  stop risk: {stop_risk:.2f} ({net/stop_risk:.2f}R realized)")

# ---- PLOT: GEX wall map + price path with trade markers + net P&L ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2), gridspec_kw={"width_ratios": [1.15, 1]})
cols = [PALETTE["loss"] if g < 0 else PALETTE["profit"] for g in gex]
ax1.bar(strikes.astype(str), gex, color=cols)
ax1.axhline(0, color=PALETTE["zero"], lw=1)
for k, g in zip(strikes, gex):
    if roles[int(k)]:
        ax1.text(str(k), g + (35 if g > 0 else -70), roles[int(k)], ha="center", fontsize=8,
                 color=PALETTE["price"])
ax1.axvline("575", color=PALETTE["signal2"], lw=1.2, ls="--")
ax1.set_ylabel("Modeled dealer GEX — proxy ($mm / 1%)")
ax1.set_xlabel("Strike (synthetic)")
ax1.set_title("Modeled dealer-GEX (proxy) wall map")
ax1.text(0.5, -0.20, "proxy only: OI x modeled gamma — OI reveals neither\ncustomer/dealer ownership nor trade direction",
         transform=ax1.transAxes, fontsize=7.5, ha="center", color="#7f8c8d")

ax2.plot(t, path, color=PALETTE["price"], lw=1.8, label="spot (synthetic $)")
ax2.axhline(580, color=PALETTE["signal2"], lw=1.2, ls=":", label="call wall 580")
ax2.axhline(575, color=PALETTE["signal2"], lw=1.2, ls="--", label="magnet 575")
ax2.axhline(stop_px, color=PALETTE["loss"], lw=1, ls="--", label="stop 583.20")
ax2.annotate("", xy=(0, entry_px), xytext=(-1.6, entry_px + 0.5),
             arrowprops=dict(arrowstyle="->", color=PALETTE["loss"], lw=2))
ax2.text(-1.6, entry_px + 0.5, f"short 200 @ {entry_px:.2f}\n11:45 fill (11:40 tag)",
         color=PALETTE["loss"], fontsize=9, va="center")
ax2.plot(t[-1], exit_px, marker="X", ms=11, color=PALETTE["profit"])
ax2.text(t[-1] - 2.5, exit_px - 0.25, f"cover @ {exit_px:.2f}\nnet {net:+.2f}",
         color=PALETTE["profit"], fontsize=9)
ax2.set_ylabel("Price ($)")
ax2.set_xlabel("15-min bars (synthetic)")
ax2.legend(loc="best", fontsize=8)
ax2.set_title("Pin fade: grind into the magnet")

fig.suptitle("T050 — GEX Pin / Dealer-Positioning Fade: synthetic wall map + fade trade",
             fontsize=13, fontweight="bold", y=1.02)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T050_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("\nSaved images/T050_example.png")
