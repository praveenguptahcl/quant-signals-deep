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

rng = np.random.default_rng(100)  # fixed seed, stated in chapter text

# ---- Synthetic earnings panel: 10 stocks (hand-constructed; fictional tickers) ----
tickers = np.array(["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"])
eps_act = np.array([1.45, 0.82, 2.10, 0.55, 3.20, 1.05, 0.30, 1.80, 0.95, 2.60])
eps_exp = np.array([1.20, 0.90, 2.05, 0.70, 2.80, 1.05, 0.45, 1.60, 1.10, 2.30])
sigma   = np.array([0.10, 0.08, 0.15, 0.12, 0.25, 0.09, 0.10, 0.12, 0.11, 0.20])

# Chosen form (stated exactly in chapter): SUE = (EPS_actual - E[EPS]) / sigma(past surprises)
sue = (eps_act - eps_exp) / sigma

# Intraday leg: R = ln(P_tau1 / P_tau0-), AR = R - R_market (hand-designed, consistent with SUE rank)
p0 = np.array([50.00, 21.00, 61.50, 24.40, 88.00, 33.30, 20.05, 30.10, 12.00, 74.20])
p1 = np.array([51.40, 20.82, 61.62, 24.11, 88.97, 33.27, 19.72, 30.55, 11.80, 74.91])
rm = np.array([0.003, -0.001, 0.000, -0.002, 0.001, 0.000, -0.002, 0.001, 0.002, 0.001])
R = np.log(p1 / p0)
AR = R - rm

print("tkr | EPS_act | EPS_exp | sigma |   SUE |  P0    |  P1    | R %   | AR %")
for i in range(10):
    print(f" {tickers[i]:3s} | {eps_act[i]:7.2f} | {eps_exp[i]:7.2f} | {sigma[i]:5.2f} | "
          f"{sue[i]:6.2f} | {p0[i]:6.2f} | {p1[i]:6.2f} | {100*R[i]:5.2f} | {100*AR[i]:6.2f}")

order = np.argsort(sue)
quint = np.digitize(np.arange(10), [2, 4, 6, 8]) + 1   # rank groups of 2: Q1..Q5
qmean = [AR[order[quint == q]].mean() for q in range(1, 6)]
print("\nquintile mean intraday AR (%): " +
      "  ".join(f"Q{q}: {100*qmean[q-1]:+.2f}" for q in range(1, 6)))

# ---- PEAD intraday leg: 4 traded names (A,H long; G,I short), $50k each ----
traded = {"A": ("long",  "07:30 ET, before open"), "H": ("long", "16:45 ET, after close"),
          "G": ("short", "10:15 ET, intraday"),   "I": ("short", "07:15 ET, before open")}
idx = {"A": 0, "H": 7, "G": 6, "I": 8}
notional = 50000.0
gross = 0.0
cost = 0.0
print("\nname | side  | announced            | gross $     | spread $ | fees $ | impact $ | borrow $ | net $")
for t, (side, ann) in traded.items():
    i = idx[t]
    pnl = notional * AR[i] * (1 if side == "long" else -1)   # short profits when AR<0
    spread_c = 0.02 * (notional / p0[i])        # cross 2c half-spread (entry+exit folded in)
    fees_c = 0.0035 * (notional / p0[i]) * 2   # $0.0035/share, both legs
    impact_c = notional * 0.0002               # 2 bps market impact
    borrow_c = notional * 0.03 / 365 if side == "short" else 0.0  # 1-day borrow at 3%/ann
    net = pnl - spread_c - fees_c - impact_c - borrow_c
    gross += pnl
    cost += spread_c + fees_c + impact_c + borrow_c
    print(f" {t:4s} | {side:5s} | {ann:22s} | {pnl:10.2f} | {spread_c:8.2f} | {fees_c:6.2f} | "
          f"{impact_c:8.2f} | {borrow_c:8.2f} | {net:9.2f}")
print(f"\nTOTAL gross {gross:.2f} | costs {cost:.2f} | net {gross-cost:.2f} "
      f"(cost drag = {100*cost/gross:.1f}% of gross)")
print(f"PEAD leg (H+A mean AR) - (G+I mean AR) = "
      f"{100*((AR[7]+AR[0])/2 - (AR[6]+AR[8])/2):.2f}%")

# ---- Chart: quintile drift bars + event timeline ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=False)

x = np.arange(1, 6)
bcols = [PALETTE["profit"] if v >= 0 else PALETTE["loss"] for v in qmean]
ax1.bar(x, 100 * np.array(qmean), color=bcols, edgecolor=PALETTE["zero"])
ax1.axhline(0, color=PALETTE["zero"], lw=1)
ax1.set_xticks(x)
ax1.set_xticklabels([f"Q{q}\n({'low' if q == 1 else 'high' if q == 5 else ''} SUE)" for q in x])
ax1.set_ylabel("mean intraday AR (%)")
ax1.set_title("S100 — Earnings surprise (SUE) / PEAD intraday leg (seed 100)")
ax1.annotate("monotonic drift across SUE quintiles",
             xy=(5, 100 * qmean[4]), xytext=(2.6, 1.2), fontsize=9,
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.95))

# event timeline: intraday path tau0 -> tau1 for the 4 traded names
events = [("A (long, 07:30 pre-open)", 0, PALETTE["profit"]),
          ("H (long, 16:45 post-close)", 7, PALETTE["profit"]),
          ("G (short, 10:15 intraday)", 6, PALETTE["loss"]),
          ("I (short, 07:15 pre-open)", 8, PALETTE["loss"])]
for k, (label, i, c) in enumerate(events):
    steps = 24
    noise = rng.normal(0, 1, steps).cumsum()
    noise = (noise - noise[0]) / (noise[-1] - noise[0] + 1e-9)  # pin endpoints via blend
    drift = np.linspace(0, 1, steps)
    path = p0[i] * np.exp(np.log(p1[i] / p0[i]) * drift + 0.002 * (noise - drift))
    path[0], path[-1] = p0[i], p1[i]
    y = 3 - k
    ax2.plot(np.linspace(0, 1, steps), path, color=c, lw=2)
    ax2.scatter([0, 1], [p0[i], p1[i]], color=c, s=60, zorder=5,
                edgecolors=PALETTE["zero"])
    ax2.text(1.015, path[-1], f"{label}: AR {100*AR[i]:+.2f}%",
             fontsize=9, color=c, va="center")
ax2.set_xlim(-0.02, 1.35)
ax2.set_xticks([0, 1])
ax2.set_xticklabels(["entry (τ₀)", "exit (τ₁)"])
ax2.set_ylabel("price ($)")
ax2.set_title("Event leg: entry/exit prices for the 4 traded names", fontsize=11)
ax2.annotate("entry rule: before-open→open auction;\nintraday→first quote after stamp;\nafter-close→next open",
             xy=(0.02, 0.06), xycoords="axes fraction", fontsize=8.5,
             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#7f8c8d", alpha=0.95))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S100_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
