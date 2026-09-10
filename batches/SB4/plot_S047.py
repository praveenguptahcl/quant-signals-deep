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

# ---- S047 synthetic worked example: bid-ask bounce around a flat mid ----
SEED = 4747
rng = np.random.default_rng(SEED)
MID = 50.00
SPREAD = 0.02              # quoted spread, cents per share (example)
BID, ASK = MID - SPREAD / 2, MID + SPREAD / 2

N = 60
# Trade side: P(switch) = 0.65 -> bounce-heavy tape; P(same) = 0.35 (trend runs)
q = np.empty(N, dtype=int)          # +1 = buyer-initiated (ask print), -1 = seller-initiated (bid print)
q[0] = 1 if rng.random() < 0.5 else -1
for i in range(1, N):
    q[i] = -q[i - 1] if rng.random() < 0.65 else q[i - 1]
p = np.where(q == 1, ASK, BID)

# Roll (1984) implied spread from the synthetic tape
dp = np.diff(p)
cov1 = np.cov(dp[:-1], dp[1:], bias=True)[0, 1]
roll_spread = 2 * np.sqrt(-cov1) if cov1 < 0 else float("nan")
print(f"quoted spread = ${SPREAD:.2f}; Roll implied spread = ${roll_spread:.4f}; cov1 = {cov1:.6f}")

print("trade | side | price")
for i in range(12):
    print(f"{i + 1:5d} | {'ask' if q[i] == 1 else 'bid'}  | {p[i]:.2f}")

# Bounce round-trip: sell at ask, buy at bid (one share), per-share P&L decomposition (cents)
gross = SPREAD * 100                       # +2.0 c
fee = 0.40                                 # -0.4 c exchange+SEC-style fees per share round trip
adverse = 0.80                             # -0.8 c adverse selection (mid moves against the fade)
latency = 0.40                             # -0.4 c missed/queued fills
net = gross - fee - adverse - latency
print(f"gross +{gross:.1f}c, fees -{fee:.1f}c, adverse selection -{adverse:.1f}c, "
      f"latency/queue -{latency:.1f}c -> net +{net:.1f}c per share")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [3, 2]}, sharex=False)

tt = np.arange(N)
ax1.plot(tt, p, "o-", color=PALETTE["price"], ms=3.5, lw=1.1, label="trade price (synthetic)")
ax1.axhline(MID, color=PALETTE["signal2"], ls="--", lw=1.2, label=f"mid {MID:.2f}")
ax1.axhline(ASK, color=PALETTE["loss"], ls=":", lw=1.0, label=f"ask {ASK:.2f}")
ax1.axhline(BID, color=PALETTE["profit"], ls=":", lw=1.0, label=f"bid {BID:.2f}")
ax1.set_xlim(-1, N)
ax1.set_ylabel("price ($)")
ax1.set_title(f"S047 — Bid–ask bounce: synthetic {N}-trade tape, flat mid (Roll ŝ = ${roll_spread:.3f})")
ax1.legend(loc="upper right", ncol=2)

# Waterfall-style P&L decomposition (cents per share)
labels = ["gross\n(spread)", "fees", "adverse\nselection", "latency/\nqueue", "net"]
vals = [gross, -fee, -adverse, -latency, net]
colors = [PALETTE["profit"] if v > 0 else PALETTE["loss"] for v in vals]
bars = ax2.bar(labels, vals, color=colors, edgecolor=PALETTE["zero"], lw=0.8)
for b, v in zip(bars, vals):
    ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + (0.06 if v > 0 else -0.12),
             f"{v:+.1f}¢", ha="center", va="bottom" if v > 0 else "top", fontsize=9,
             weight="bold")
ax2.axhline(0, color=PALETTE["zero"], lw=1.0)
ax2.set_ylabel("per-share P&L (cents)")
ax2.set_title("Bounce round-trip P&L decomposition (example costs)", fontsize=11)
ax2.set_ylim(-1.6, 2.6)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S047_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S047_example.png")
