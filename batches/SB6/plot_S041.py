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

rng = np.random.default_rng(44)  # seed 44

# ---- SYNTHETIC 1-MIN SERIES (seed 44): mean-reverting noise + two engineered excursions ----
N, n, k = 70, 20, 2.0
e = rng.normal(0, 0.0015, N)
ar = np.zeros(N)
for t in range(1, N):
    ar[t] = 0.9 * ar[t - 1] + e[t]
rets = np.diff(np.r_[0.0, ar])  # mean-reverting background noise in return space
# lower-band tag event near bar 30: sharp 2-bar dip, then recovery
rets[30] -= 0.012; rets[31] -= 0.018; rets[32] += 0.006; rets[33] += 0.012; rets[34] += 0.010
# upper-band tag event near bar 52: sharp 2-bar spike, then fade
rets[52] += 0.012; rets[53] += 0.018; rets[54] -= 0.006; rets[55] -= 0.012; rets[56] -= 0.010
px = 100.0 * np.exp(np.cumsum(rets))

sma = np.array([px[i - n + 1:i + 1].mean() if i >= n - 1 else np.nan for i in range(N)])
sig = np.array([px[i - n + 1:i + 1].std(ddof=1) if i >= n - 1 else np.nan for i in range(N)])
upper, lower = sma + k * sig, sma - k * sig
pctb = (px - lower) / (upper - lower)
bandw = (upper - lower) / sma * 100.0

def find_lower():
    # deepest lower-band tag in dollars below the band that re-enters on the next bar
    best, bestd = None, 0.0
    for i in range(n, N - 2):
        if px[i] < lower[i] and px[i + 1] > lower[i + 1]:
            d = lower[i] - px[i]
            if d > bestd:
                best, bestd = i, d
    return best

def find_upper():
    # deepest upper-band tag in dollars above the band that re-enters on the next bar
    best, bestd = None, 0.0
    for i in range(n, N - 2):
        if px[i] > upper[i] and px[i + 1] < upper[i + 1]:
            d = px[i] - upper[i]
            if d > bestd:
                best, bestd = i, d
    return best

iL, iU = find_lower(), find_upper()
assert iL is not None and iU is not None and iU > iL, "tag events not found — retune excursions"

def trade(tag_i, direction):
    # enter at close of first bar back inside the band (tag_i+1), exit at mid touch or +10 bars
    entry_i = tag_i + 1
    entry = px[entry_i]
    exit_i = entry_i
    for j in range(entry_i + 1, min(entry_i + 11, N)):
        exit_i = j
        if (direction == "long" and px[j] >= sma[j]) or (direction == "short" and px[j] <= sma[j]):
            break
    pnl = (px[exit_i] - entry) if direction == "long" else (entry - px[exit_i])
    return entry_i, entry, exit_i, px[exit_i], pnl

eL = trade(iL, "long"); eU = trade(iU, "short")

print("== S041 synthetic Bollinger series (seed 44, n=20, k=2) ==")
print(f"lower-tag event: bar {iL}: close {px[iL]:.3f} < lower {lower[iL]:.3f} (SMA {sma[iL]:.3f}, sig {sig[iL]:.3f}, %b {pctb[iL]:.3f}, bandwidth {bandw[iL]:.3f}%)")
print(f"  next bar {iL+1}: close {px[iL+1]:.3f} vs lower {lower[iL+1]:.3f} -> back inside; LONG fade: entry {eL[1]:.3f} (bar {eL[0]}), exit {eL[3]:.3f} (bar {eL[2]}), P&L {eL[4]:+.3f}/share = {eL[4]/eL[1]*10000:+.1f}bp")
print(f"upper-tag event: bar {iU}: close {px[iU]:.3f} > upper {upper[iU]:.3f} (SMA {sma[iU]:.3f}, sig {sig[iU]:.3f}, %b {pctb[iU]:.3f}, bandwidth {bandw[iU]:.3f}%)")
print(f"  next bar {iU+1}: close {px[iU+1]:.3f} vs upper {upper[iU+1]:.3f} -> back inside; SHORT fade: entry {eU[1]:.3f} (bar {eU[0]}), exit {eU[3]:.3f} (bar {eU[2]}), P&L {eU[4]:+.3f}/share = {eU[4]/eU[1]*10000:+.1f}bp")

x = np.arange(N)
fig, ax = plt.subplots()
ax.fill_between(x[n - 1:], lower[n - 1:], upper[n - 1:], color=PALETTE["band"], alpha=0.45,
                label="Bollinger bands (SMA20 ± 2σ)")
ax.plot(x[n - 1:], sma[n - 1:], color=PALETTE["signal2"], lw=1.4, label="mid (SMA20)")
ax.plot(x, px, color=PALETTE["price"], lw=1.8, label="close (synthetic 1-min)")
for tag_i, e, d, col in [(iL, eL, "long", PALETTE["profit"]), (iU, eU, "short", PALETTE["loss"])]:
    ax.scatter([tag_i], [px[tag_i]], color=PALETTE["signal"], s=90, zorder=5,
               label=f"band tag (bar {tag_i})")
    ax.annotate("", xy=(e[0], e[1]), xytext=(e[0] - 3, e[1]),
                arrowprops=dict(arrowstyle="->", color=col, lw=2))
    ax.annotate(f"{d}: {e[1]:.2f}→{e[3]:.2f}\n({e[4] / e[1] * 10000:+.0f}bp)",
                xy=(e[0], e[1]), xytext=(e[0] + 4, e[1] + (0.35 if d == "long" else -0.35)),
                fontsize=8, color=col, ha="left",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=col, alpha=0.9))
    ax.scatter([e[0]], [e[1]], color=col, marker="^" if d == "long" else "v", s=80, zorder=5)
ax.set_title("S041 — Bollinger-band reversal: tag-and-fade events (synthetic 1-min)")
ax.set_xlabel("1-minute bar")
ax.set_ylabel("price ($)")
ax.legend(loc="upper left", ncol=2)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S041_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
