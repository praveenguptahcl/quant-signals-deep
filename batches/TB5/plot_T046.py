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

rng = np.random.default_rng(146)  # seed = stage number; stated in chapter T4

# ---- synthetic earnings-event setup (fictional "QRS"; all numbers synthetic) ----
S0 = 150.00
call_mid, put_mid = 4.60, 4.40
straddle_mid = call_mid + put_mid          # 9.00
spread = 0.30
IM = straddle_mid / S0                     # implied move

# trailing 12-event implied-move history (example), drawn with the chapter seed
hist_IM = rng.normal(0.038, 0.012, 12)
mu_IM, sd_IM = hist_IM.mean(), hist_IM.std()
rich_z = (IM - mu_IM) / sd_IM

print("trailing 12-event implied moves (%):", np.round(hist_IM * 100, 2))
print(f"mean {mu_IM*100:.2f}%  std {sd_IM*100:.2f}%")
print(f"today: straddle {straddle_mid:.2f} on S={S0:.2f} -> IM {IM*100:.2f}% -> richness z = {rich_z:.2f}")

VOL_OI, SWEEPS = 0.8, 0          # example UOA read: no informed flow
IV, HAR = 0.32, 0.27            # example VRP read
print(f"UOA filter: vol/OI {VOL_OI} (< 1.5 example), sweeps {SWEEPS} -> PASS")
print(f"VRP: IV {IV*100:.0f}% - HAR {HAR*100:.0f}% = +{(IV-HAR)*100:.0f} vol pts (>= +1 example) -> PASS")

RICH_Z_MIN = 1.0  # example
if rich_z >= RICH_Z_MIN and VOL_OI < 1.5 and SWEEPS == 0 and (IV - HAR) >= 0.01:
    credit = straddle_mid - spread / 2          # sell at bid: mid - half spread
    print(f"\nENTER at t+1 open: sell 1 ATM straddle @ {credit:.2f} (bid)")
else:
    raise SystemExit("gates failed")

# post-event: stock +1.8%, straddle collapses
S1 = 152.70
straddle_mark = 2.10
debit = straddle_mark + spread / 2              # buy back at ask
print(f"EXIT next day: stock {S0:.2f} -> {S1:.2f} (+1.8%); buy back straddle @ {debit:.2f} (ask)")

gross = (credit - debit) * 100
comm = 4 * 0.65
net = gross - comm
print(f"gross ({credit:.2f} - {debit:.2f}) x 100 = {gross:+.2f}")
print(f"commissions 4 x 0.65 = {comm:.2f}")
print(f"NET = {net:+.2f}")

# ---- chart: straddle value path with entry/exit markers ----
fig, ax = plt.subplots()
xs = ["Signal session t\n(mid)", "t+1 open\n(entry, bid)", "Post-event\n(exit, ask)"]
vals = [straddle_mid, credit, debit]
ax.plot(xs, vals, color=PALETTE["price"], lw=2.4, marker="o", markersize=8,
        label="ATM straddle value ($)")
ax.scatter([1], [credit], color=PALETTE["signal"], s=90, zorder=5)
ax.scatter([2], [debit], color=PALETTE["profit"], s=90, zorder=5)
ax.annotate(f"SELL straddle @ {credit:.2f} (t+1 open)\n(IM 6.0%, richness z +{rich_z:.2f})",
            xy=(1, credit), xytext=(18, 34), textcoords="offset points", fontsize=9,
            color=PALETTE["signal"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"], lw=1))
ax.annotate(f"BUY BACK @ {debit:.2f}\nnet +${net:,.2f}", xy=(2, debit), xytext=(-128, -38),
            textcoords="offset points", fontsize=9, color=PALETTE["profit"],
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"], lw=1))
ax.fill_between([0, 2], [straddle_mid] * 2, [debit] * 2, color=PALETTE["band"], alpha=0.35,
                label="Harvested premium")
ax.set_title("T046 — Straddle-Implied Move Fade: synthetic straddle value around an earnings event")
ax.set_ylabel("Straddle value ($)")
ax.legend()

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T046_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T046_example.png")
