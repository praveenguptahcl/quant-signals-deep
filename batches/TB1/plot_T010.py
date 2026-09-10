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

# ---- SYNTHETIC DATA (seed = stage number 110) ----
rng = np.random.default_rng(110)
DAYS = 126  # ~6 months of synthetic VRP history
vrp_hist = 60 + 28 * rng.normal(0, 1, DAYS)          # variance points, synthetic
vrp_hist[40] = 113.75   # T1 entry: IV 18%, HAR 14.5% -> 324 - 210.25
vrp_hist[90] = 149.21   # T2 entry: IV 19.5%, HAR 15.2% -> 380.25 - 231.04
z_hist = (vrp_hist - 60) / 28

# Straddle valuation: ATM straddle approx = 0.798 * S * IV * sqrt(T in years)
def straddle_mid(S, iv, T):
    return 0.798 * S * iv * np.sqrt(T)

T_yr = 30 / 365
T1 = dict(name="T1", entry_day=40, exit_day=45,
          S=600.0, iv=0.18, har=0.145,
          hedge=[120.0, -310.0, 95.0, -420.0, 60.0],
          exit_mid=22.88, exit_fill=22.92,
          desc="short straddle, VRP convergence exit")
T1["entry_mid"] = round(straddle_mid(T1["S"], T1["iv"], T_yr), 2)
T1["entry_fill"] = T1["entry_mid"] - 0.04  # sold the bid
T1["opt"] = (T1["entry_fill"] - T1["exit_fill"]) * 10 * 100
T1["hedge_pnl"] = sum(T1["hedge"])
T1["fees"] = 10 * 2 * 0.65 + len(T1["hedge"]) * 1.00
T1["net"] = T1["opt"] + T1["hedge_pnl"] - T1["fees"]
T1["vrp"] = T1["iv"] ** 2 * 10000 - T1["har"] ** 2 * 10000  # variance points

T2 = dict(name="T2", entry_day=90, exit_day=94,
          S=600.0, iv=0.195, har=0.152,
          hedge=[85.0, 640.0, 905.0, 470.0],
          exit_mid=32.00, exit_fill=32.04,
          desc="short straddle, realized-vol stop (5-day GK 30% > 1.5x IV)")
T2["entry_mid"] = round(straddle_mid(T2["S"], T2["iv"], T_yr), 2)
T2["entry_fill"] = T2["entry_mid"] - 0.04
T2["opt"] = (T2["entry_fill"] - T2["exit_fill"]) * 10 * 100
T2["hedge_pnl"] = sum(T2["hedge"])
T2["fees"] = 10 * 2 * 0.65 + len(T2["hedge"]) * 1.00
T2["net"] = T2["opt"] + T2["hedge_pnl"] - T2["fees"]
T2["vrp"] = T2["iv"] ** 2 * 10000 - T2["har"] ** 2 * 10000

trades = [T1, T2]
print("T010 synthetic trade table (seed 110):")
cum = 0.0
for t in trades:
    cum += t["net"]
    print(f"  {t['name']}: VRP={t['vrp']:.2f} var-pts (z={(t['vrp']-60)/28:+.2f}) "
          f"entry_mid={t['entry_mid']:.2f} sold={t['entry_fill']:.2f} "
          f"bought_back={t['exit_fill']:.2f} opt={t['opt']:+.2f} "
          f"hedge={t['hedge_pnl']:+.2f} fees=-{t['fees']:.2f} "
          f"net={t['net']:+.2f} cum={cum:+.2f}")
print(f"  total net = {cum:+.2f}")
cum_vals = np.cumsum([t["net"] for t in trades])

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [3, 2]})
days = np.arange(DAYS)
ax1.plot(days, z_hist, color=PALETTE["price"], lw=1.0,
         label="VRP z-score vs trailing 6-month history (synthetic)")
ax1.axhline(1.5, color=PALETTE["signal"], ls="--", lw=0.9, label="entry z = +1.5")
ax1.axhline(0.5, color=PALETTE["signal2"], ls="-.", lw=0.9, label="exit z = +0.5")
ax1.axhline(0, color=PALETTE["zero"], lw=0.8)
for t in trades:
    z_in = (t["vrp"] - 60) / 28
    ax1.scatter(t["entry_day"], z_in, color=PALETTE["signal"], marker="v", s=70, zorder=5)
    ax1.scatter(t["exit_day"], 0.4, color=PALETTE["profit"] if t["net"] > 0 else PALETTE["loss"],
                marker="^", s=70, zorder=5)
    ax1.annotate(f"{t['name']} entry\nz={z_in:.2f}, sell 10 straddles @ {t['entry_fill']:.2f}",
                 (t["entry_day"], z_in), fontsize=7,
                 xytext=(6, 10), textcoords="offset points")
    ax1.annotate(f"{t['name']} exit\nbuy back @ {t['exit_fill']:.2f}",
                 (t["exit_day"], 0.4), fontsize=7,
                 xytext=(6, -20), textcoords="offset points")
ax1.set_ylabel("VRP z-score")
ax1.set_xlabel("day index (synthetic 6-month history)")
ax1.legend(loc="upper left")

ax2.step([0] + [t["exit_day"] for t in trades],
         [0.0] + list(cum_vals), where="post", color=PALETTE["price"], lw=1.6,
         label="cumulative net P&L ($)")
for t, cv in zip(trades, cum_vals):
    ax2.annotate(f"{t['name']}: {t['net']:+.2f}",
                 (t["exit_day"], cv), fontsize=8,
                 xytext=(0, 10 if t["net"] > 0 else -16),
                 textcoords="offset points", ha="center",
                 color=PALETTE["profit"] if t["net"] > 0 else PALETTE["loss"],
                 weight="bold")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("cumulative net P&L ($)")
ax2.set_xlabel("day index (synthetic 6-month history)")

fig.suptitle("T010 — Variance-Risk-Premium Harvester: VRP z-score entries + cumulative net P&L (synthetic)",
             fontsize=13, weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T010_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T010_example.png")
