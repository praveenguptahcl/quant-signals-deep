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

# ---- T014 worked example (seed 114) ----
# Synthetic 5-minute bars of fictional stock SYN (~$50), seed 114.
# S041 tag-and-reenter fades (n=20, k=2); S030 squeeze arm/exit; S076 vol-breakout cover.
# All prices SYNTHETIC — not market data.
rng = np.random.default_rng(114)
_ = rng.random()
N, K = 20, 2.0
n = 240
rets = rng.normal(0, 0.00055, n)
rets[140:178] *= 0.18          # engineered low-vol segment -> bandwidth squeeze (pct <= 10)
px = 50.0 * np.exp(np.cumsum(rets))


def compute(p):
    t = np.arange(N - 1, len(p))
    cs = np.concatenate([[0.0], np.cumsum(p)])
    mid = (cs[N:] - cs[:-N]) / N
    cs2 = np.concatenate([[0.0], np.cumsum(p * p)])
    var = (cs2[N:] - cs2[:-N] - N * mid * mid) / (N - 1)
    sd = np.sqrt(np.maximum(var, 1e-12))
    up = mid + K * sd
    lo = mid - K * sd
    bw = (up - lo) / mid * 100.0
    return t, mid, up, lo, sd, bw


def at(arr, b):
    return arr[b - (N - 1)]


# Trade 1: lower-band tag at bar 60, re-entry at 61 -> LONG
_, mid, up, lo, sd, bw = compute(px)
px[60] = at(lo, 59) - 0.12
_, mid, up, lo, sd, bw = compute(px)
px[61] = at(lo, 60) + 0.04
entry1, entry1_bar = float(px[61]), 61
# engineered reversion: bars 62-69 drift up to the midline (touch = S041 target)
_, mid, up, lo, sd, bw = compute(px)
mid_target1 = at(mid, 69)
for b in range(62, 70):
    px[b] = px[61] + (mid_target1 - px[61]) * (b - 61) / 8.0
# exit: first close >= midline within 10 bars (S041 time stop M=10)
_, mid, up, lo, sd, bw = compute(px)
exit1_bar = 71
for b in range(62, 72):
    if px[b] >= at(mid, b):
        exit1_bar = b
        break
exit1 = float(px[exit1_bar])

# Trade 2: upper-band tag at bar 110, re-entry at 111 -> SHORT
_, mid, up, lo, sd, bw = compute(px)
px[110] = at(up, 109) + 0.12
_, mid, up, lo, sd, bw = compute(px)
px[111] = at(up, 110) - 0.04
entry2, entry2_bar = float(px[111]), 111
# engineered reversion: bars 112-119 drift down to the midline (touch = S041 target)
_, mid, up, lo, sd, bw = compute(px)
mid_target2 = at(mid, 119)
for b in range(112, 120):
    px[b] = px[111] + (mid_target2 - px[111]) * (b - 111) / 8.0
_, mid, up, lo, sd, bw = compute(px)
exit2_bar = 121
for b in range(112, 122):
    if px[b] <= at(mid, b):
        exit2_bar = b
        break
exit2 = float(px[exit2_bar])

# Trade 3: squeeze (bars ~140-178) + long fade at 180/181, stopped by vol breakout at 184
_, mid, up, lo, sd, bw = compute(px)
Rwin = 125
pcts = np.array([100.0 * np.sum(bw[max(0, i - Rwin):i] <= bw[i]) / Rwin
                 for i in range(len(bw))])
sq_bar = 175
sq_pct = float(at(pcts, sq_bar))
print(f"squeeze check: BW pct at bar {sq_bar} = {sq_pct:.1f}% (example arm threshold p=15%)")
px[180] = at(lo, 179) - 0.05
_, mid, up, lo, sd, bw = compute(px)
px[181] = at(lo, 180) + 0.08
entry3, entry3_bar = float(px[181]), 181
# adverse expansion bar 182: down-drift starts (the tag was the expansion's first leg)
for b in range(182, 192):
    px[b] = px[181] * (1 - 0.0015 * (b - 181))
_, mid, up, lo, sd, bw = compute(px)
rr = np.abs(px[182:187] - px[181:186]) / np.array(
    [np.mean(np.abs(px[max(N - 1, b - 10):b] - px[max(N - 1, b - 10) - 1:b - 1])) for b in range(182, 187)])
exit3_bar = int(np.argmax(rr > 1.75)) + 182
print(f"vol-breakout check: range ratio at bar {exit3_bar} = {rr[exit3_bar - 182]:.2f} (>1.75 covers)")
exit3 = float(px[exit3_bar])
# no-cover alternative: ride to the 10-bar time stop at bar 191
nocov = float(px[191])
nocov_net = (nocov - float(px[181])) * 1000 - (2 * 0.01 * 1000 + 2 * (0.005 * 1000 + 0.50))
print(f"no-cover alternative: time-stop exit at bar 191 = {nocov:.4f}, net {nocov_net:+.2f}")

_, mid, up, lo, sd, bw = compute(px)

SHARES = 1000
HALF_SPREAD, COMM, TICKET = 0.01, 0.005, 0.50
cost_rt = 2 * (HALF_SPREAD * SHARES) + 2 * (COMM * SHARES + TICKET)

trades = [
    dict(side=+1, eb=entry1_bar, e=entry1, xb=exit1_bar, x=exit1, note="long fade -> mid touch"),
    dict(side=-1, eb=entry2_bar, e=entry2, xb=exit2_bar, x=exit2, note="short fade -> mid touch"),
    dict(side=+1, eb=entry3_bar, e=entry3, xb=exit3_bar, x=exit3, note="squeeze: breakout cover"),
]
cum = 0.0
print("bar_e, entry, bar_x, exit, gross, net")
for tr in trades:
    gross = tr["side"] * (tr["x"] - tr["e"]) * SHARES
    net = gross - cost_rt
    tr["gross"], tr["net"] = gross, net
    cum += net
    tr["cum"] = cum
    print(f"{tr['eb']}, {tr['e']:.4f}, {tr['xb']}, {tr['x']:.4f}, {gross:+.2f}, {net:+.2f}  # {tr['note']}")
print(f"TOTAL NET = {cum:+.2f} on cost/trade = {cost_rt:.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=False,
                               gridspec_kw={"height_ratios": [3, 1.6]})
tt = np.arange(N - 1, n)
ax1.plot(tt, px[N - 1:], color=PALETTE["price"], lw=1.3, label="SYN close (synthetic 5-min)")
ax1.plot(tt, up, color=PALETTE["signal2"], lw=0.9, ls="--", label="Upper band (20, 2.0)")
ax1.plot(tt, lo, color=PALETTE["signal2"], lw=0.9, ls="--", label="Lower band (20, 2.0)")
ax1.plot(tt, mid, color=PALETTE["volume"], lw=0.9, label="Midline (SMA-20)")
squeeze = pcts <= 15.0
ax1.fill_between(tt, 47, 53, where=squeeze, color=PALETTE["band"], alpha=0.35,
                 step="mid", label="Squeeze (BW pct <= 10)")
for tr in trades:
    ax1.scatter(tr["eb"], tr["e"], s=90, marker="^" if tr["side"] > 0 else "v",
                color=PALETTE["profit"] if tr["side"] > 0 else PALETTE["loss"],
                edgecolors="black", zorder=5)
    ax1.scatter(tr["xb"], tr["x"], s=90, marker="v" if tr["side"] > 0 else "^",
                color=PALETTE["zero"], edgecolors="black", zorder=5)
    ax1.annotate(f"${tr['net']:+.0f}",
                 xy=(tr["xb"], tr["x"]), xytext=(14, 14 if tr["side"] > 0 else -24),
                 textcoords="offset points", fontsize=8, weight="bold",
                 color=PALETTE["profit"] if tr["net"] > 0 else PALETTE["loss"])
ax1.set_xlim(N - 1, n - 1)
ax1.set_ylabel("Price ($)")
ax1.set_title("T014 — Bollinger Reversal + Squeeze Exit: synthetic 3-trade worked example")
ax1.legend(loc="upper left", ncol=2, fontsize=8)

xs = [0] + [tr["xb"] for tr in trades]
ys = [0.0] + [tr["cum"] for tr in trades]
ax2.step(xs, ys, where="post", color=PALETTE["price"], lw=1.8,
         label="Cumulative net P&L ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
for tr in trades:
    ax2.annotate(f"${tr['net']:+.0f}", xy=(tr["xb"], tr["cum"]),
                 xytext=(0, 12 if tr["net"] >= 0 else -18), textcoords="offset points",
                 ha="center", fontsize=8, weight="bold",
                 color=PALETTE["profit"] if tr["net"] > 0 else PALETTE["loss"])
ax2.set_xlabel("Synthetic 5-min bar (seed 114)")
ax2.set_ylabel("Net P&L ($)")
ax2.set_xlim(N - 1, n - 1)
ax2.legend(loc="upper left", fontsize=8)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
ROOT = Path(__file__).resolve().parents[2]
plt.savefig(ROOT / "images" / "T014_example.png", bbox_inches="tight")
plt.close()
print("saved", ROOT / "images" / "T014_example.png")
