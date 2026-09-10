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

rng = np.random.default_rng(143)

HALF_SPREAD = 0.005
FEE = 0.0035

# GARCH regime anchors (synthetic, bp per 5-min bar; trailing median = 19.5 bp)
MEDIAN = 19.5
LO_THR = 0.9 * MEDIAN    # 17.55
HI_THR = 1.1 * MEDIAN    # 21.45
SIG_ANCHORS = [(570, 15.0), (605, 14.2), (680, 14.8), (750, 17.0),
               (790, 19.0), (815, 26.0), (855, 31.8), (960, 29.0)]

# price anchors (minute-of-day, price) — events forced exact
TRADES = [  # (name, fill_min, fill_px, exit_min, exit_px, shares) — fills at t+1, never the trigger bar
    ("T1", 610, 200.00, 680, 200.58, 300),   # trigger 10:05 (605) -> fill 10:10 (610)
    ("T2", 825, 199.10, 855, 199.62, 200),   # trigger 13:40 (820) -> fill 13:45 (825)
]
FILL_TAG = {610: "fill 10:10 (t+1)", 825: "fill 13:45 (t+1)"}
PX_ANCHORS = [(570, 199.80)] + [(t[1], t[2]) for t in TRADES] + \
             [(t[3], t[4]) for t in TRADES] + [(750, 200.30), (960, 199.40)]
PX_ANCHORS = sorted(set(PX_ANCHORS))

mins = np.arange(570, 961)
ax_, ay_ = zip(*PX_ANCHORS)
price = np.interp(mins, ax_, ay_) + rng.normal(0, 0.05, len(mins))
sx_, sy_ = zip(*SIG_ANCHORS)
sigma = np.interp(mins, sx_, sy_) + rng.normal(0, 0.5, len(mins))
for m_, p_ in PX_ANCHORS:
    price[mins == m_] = p_
for m_, s_ in SIG_ANCHORS:
    sigma[mins == m_] = s_

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})

# panel 1 — price with regime shading
ax1.axvspan(570, 750, color=PALETTE["profit"], alpha=0.10, label="LOW-vol regime: momentum book")
ax1.axvspan(750, 790, color=PALETTE["volume"], alpha=0.14, label="NEUTRAL: no entries")
ax1.axvspan(790, 961, color=PALETTE["signal"], alpha=0.10, label="HIGH-vol regime: reversal book")
ax1.plot(mins, price, color=PALETTE["price"], lw=1.6, label="SYNX price (synthetic, $)")

for name, em, ep, xm, xp, sh in TRADES:
    gross = (xp - ep) * sh
    costs = 2 * sh * (HALF_SPREAD + FEE)
    net = gross - costs
    ax1.scatter([em], [price[mins == em]], s=90, marker="^", color=PALETTE["profit"],
                zorder=5, edgecolors="black", linewidths=0.7)
    ax1.scatter([xm], [price[mins == xm]], s=90, marker="v", color=PALETTE["loss"],
                zorder=5, edgecolors="black", linewidths=0.7)
    ax1.annotate(f"{name}: {sh} sh @ {ep:.2f}\n{FILL_TAG[em]} -> {xp:.2f} · net {net:+.2f}$",
                 xy=(xm, price[mins == xm][0]), fontsize=8,
                 xytext=(16, 16), textcoords="offset points",
                 arrowprops=dict(arrowstyle="-", color="#2c3e50", lw=0.8),
                 bbox=dict(boxstyle="round,pad=0.25", fc="white", alpha=0.85))
    print(f"{name}: {sh} sh {ep:.2f} -> {xp:.2f} | gross {gross:+.2f} | "
          f"spread {2*sh*HALF_SPREAD:.2f} | fees {2*sh*FEE:.2f} | net {net:+.2f}")
    assert abs(price[mins == em][0] - ep) < 1e-9, name
    assert abs(price[mins == xm][0] - xp) < 1e-9, name

ax1.set_ylabel("Price ($)")
ax1.legend(loc="upper left", fontsize=8)

# panel 2 — GARCH forecast vs median bands
ax2.plot(mins, sigma, color=PALETTE["signal2"], lw=1.6,
         label="GARCH 1-bar-ahead forecast (synthetic, bp/5-min)")
ax2.axhline(MEDIAN, color=PALETTE["zero"], ls="--", lw=1.2, label="trailing median 19.5 bp")
ax2.axhline(LO_THR, color=PALETTE["profit"], ls=":", lw=1.2, label="low threshold 17.55 bp")
ax2.axhline(HI_THR, color=PALETTE["signal"], ls=":", lw=1.2, label="high threshold 21.45 bp")
ax2.axvspan(570, 750, color=PALETTE["profit"], alpha=0.08)
ax2.axvspan(750, 790, color=PALETTE["volume"], alpha=0.10)
ax2.axvspan(790, 961, color=PALETTE["signal"], alpha=0.08)
ax2.annotate("regime @10:00: 14.2 bp < 17.55\n-> LOW (momentum)",
             xy=(605, 14.2), fontsize=8, xytext=(-150, -28), textcoords="offset points",
             arrowprops=dict(arrowstyle="->", color="#2c3e50", lw=0.8))
ax2.annotate("regime @13:35: 26.0 bp > 21.45\n-> HIGH (reversal)",
             xy=(815, 26.0), fontsize=8, xytext=(20, 14), textcoords="offset points",
             arrowprops=dict(arrowstyle="->", color="#2c3e50", lw=0.8))
# trigger bars (t) vs fill bars (t+1): entries fill at t+1, never the signal bar
for tm, lab in [(605, "trigger 10:05"), (820, "trigger 13:40")]:
    ax2.axvline(tm, color=PALETTE["signal"], lw=1.1, ls=":")
    ax2.text(tm + 5, 33.2, lab, fontsize=7.5, color=PALETTE["signal"], va="top")
for tm, lab in [(610, "fill 10:10"), (825, "fill 13:45")]:
    ax2.axvline(tm, color=PALETTE["profit"], lw=1.1, ls="--")
    ax2.text(tm + 5, 33.2, lab, fontsize=7.5, color=PALETTE["profit"], va="top")
ax2.set_xlabel("Time of day (minutes past midnight ET)")
ax2.set_ylabel("Vol forecast (bp)")
ax2.legend(loc="upper left", fontsize=8)
ax2.set_xlim(570, 960)
ax2.set_xticks([570, 630, 690, 750, 810, 870, 930, 960])
ax2.set_xticklabels(["09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30", "16:00"])

fig.suptitle("T043 — GARCH Regime Filter: synthetic regime-gated momentum/reversal trades",
             fontsize=13, fontweight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T043_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/T043_example.png")
