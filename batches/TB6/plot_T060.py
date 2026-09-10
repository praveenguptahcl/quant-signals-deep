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

# ---- T060 worked-example numbers (seed 160, synthetic) ----
# 12 synthetic intraday jump events across 6 names.
# Rule (examples): jump z>3.5 on 5-min bars, min jump 1.5%; match window w=15min;
# identified=1 & novelty>=0.5 -> FOLLOW (hold 60min); identified=0 -> FADE;
# earnings announcements always FOLLOW leg with SUE-size context (S100).
rng = np.random.default_rng(160)
names = ["ALP", "BET", "GAM", "DEL", "EPS", "ZET"]
jump_pct = np.round(rng.uniform(1.6, 4.5, 12), 2) * np.where(rng.random(12) < 0.5, 1, -1)
identified = np.array([1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 1, 0])
novelty = np.round(rng.uniform(0.2, 1.0, 12), 2)
earnings = np.array([0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0])
sue = np.round(rng.uniform(1.0, 4.0, 12), 1)
FEE = 0.0008

events, cum = [], 0.0
print("T060 synthetic jump events (seed 160)")
print("#  name jump%  ident nov  earn  SUE   action shares   entry     exit      gross      fees     net")
for i in range(12):
    nm = names[i % 6]
    if earnings[i]:
        action, side = "FOLLOW(earn)", int(np.sign(jump_pct[i]))
    elif identified[i] == 1 and novelty[i] >= 0.5:
        action, side = "FOLLOW", int(np.sign(jump_pct[i]))
    elif identified[i] == 0:
        action, side = "FADE", -int(np.sign(jump_pct[i]))
    else:
        action, side = "SKIP(stale)", 0
    if side == 0:
        shares, entry, exitp, gross, fees, net = 0, 0.0, 0.0, 0.0, 0.0, 0.0
    else:
        shares = 12000 if "FOLLOW" in action else 8000
        if "earn" in action:
            shares = int(shares * min(1.0, sue[i] / 3.0))
        entry = round(50.0, 3)
        drift = float(rng.normal(35 if "FOLLOW" in action else 30, 55))  # hold P&L in bp, signed by side
        exitp = round(entry + side * drift / 100.0, 3)
        gross = round(side * shares * (exitp - entry), 2)
        fees = round(shares * 2 * FEE, 2)
        net = round(gross - fees, 2)
    cum += net
    events.append((i + 1, nm, jump_pct[i], identified[i], novelty[i], earnings[i], sue[i],
                   action, side, shares, entry, exitp, gross, fees, net, cum))
    print(f"{i+1:2d} {nm:3s} {jump_pct[i]:+6.2f} {identified[i]:5d} {novelty[i]:4.2f} "
          f"{earnings[i]:5d} {sue[i]:4.1f} {action:12s} {side:+3d} {shares:7d} "
          f"{entry:8.3f} {exitp:8.3f} {gross:9.2f} {fees:7.2f} {net:9.2f} cum {cum:9.2f}")
print(f"TOTAL NET: ${cum:,.2f}")

nums = [e[0] for e in events]
nets = np.array([e[13] for e in events])
cums = np.array([e[14] for e in events])
leg = [e[7] for e in events]
legcol = {"FOLLOW": PALETTE["profit"], "FOLLOW(earn)": PALETTE["signal2"], "FADE": PALETTE["signal"],
          "SKIP(stale)": PALETTE["volume"]}

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1], "hspace": 0.08})
ax1.plot(nums, cums, color=PALETTE["price"], lw=2, marker="o", ms=5, label="Cumulative net P&L ($)")
for e in events:
    n = e[0]
    ax1.scatter([n], [e[14]], color=legcol[e[7]], s=60, zorder=5)
    ax1.annotate(e[7].split("(")[0], xy=(n, e[14]), xytext=(0, 11), textcoords="offset points",
                 ha="center", fontsize=7, color=legcol[e[7]], weight="bold")
ax1.axhline(0, color=PALETTE["zero"], lw=1)
ax1.set_title("T060 — Identified-News Drift Portfolio: 12 synthetic jump events, cumulative net P&L")
ax1.set_ylabel("Cum. net P&L ($)")
ax1.legend(loc="upper left")
ax1.text(0.98, 0.06, f"Total net ${cum:,.0f}", transform=ax1.transAxes, ha="right",
         fontsize=11, weight="bold", color=PALETTE["profit"] if cum > 0 else PALETTE["loss"])

ax2.bar(nums, nets, color=[legcol[l] for l in leg])
from matplotlib.patches import Patch
ax2.legend(handles=[Patch(color=v, label=k) for k, v in legcol.items()], loc="upper right")
ax2.set_xlabel("Synthetic event # (1–12)")
ax2.set_ylabel("Net/event ($)")
ax2.set_xticks(nums)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T060_example.png", bbox_inches="tight")
plt.close()
print("saved images/T060_example.png")
