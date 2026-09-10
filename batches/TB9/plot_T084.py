import matplotlib
matplotlib.use("Agg")  # headless render on the Mac/VM
import matplotlib.pyplot as plt
import numpy as np
import os

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

rng = np.random.default_rng(184)  # T084 seed — stated in chapter text

# ---- T084 worked-example inputs (SYNTHETIC) ----
# Fictional "BLK" mid $80.00. Block: 50,000 shares SOLD at $79.90 (temporary impact 10c).
mid0 = 80.00
block_px, block_sh = 79.90, 50_000
temp_impact = mid0 - block_px          # 10c temporary
perm_impact = 0.03                     # 3c permanent (example S048 split)
half_life = 90                        # seconds (example S048 estimate)
print(f"block: {block_sh} sh @ ${block_px:.2f}; temp impact {temp_impact:.2f}, perm {perm_impact:.2f}, t1/2={half_life}s")
# Block detection (S094): 50,000 vs median trade 2,500 -> 20x >= 10x example threshold
print(f"block size ratio: {block_sh/2500:.0f}x median trade -> BLOCK detected")
# Liquidity provision: buy 5,000 sh at $79.91 (9c below pre-block mid, 1c above the block print)
entry_px, entry_sh = 79.91, 5_000
# Kyle lambda (S010) gate: lambda_hat = $0.0000020/share (example) -> own impact 1c
lam = 0.0000020
print(f"Kyle gate: lambda_hat=${lam:.7f}/sh -> own impact on {entry_sh} sh = ${lam*entry_sh:.3f} (cap 2c example: PASS)")
# Exit after one half-life (90 s): mid reverts halfway: 79.90 + (80.00-0.03-79.90)/2
exit_mid = block_px + (mid0 - perm_impact - block_px) / 2
exit_px = exit_mid - 0.005  # lift 0.5c inside
print(f"exit mid after t1/2: ${exit_mid:.4f} -> sell @ ${exit_px:.4f}")
gross = (exit_px - entry_px) * entry_sh
fees = 0.005 * 2 * entry_sh
net = gross - fees
print(f"gross=${gross:.2f}, fees=${fees:.2f}, NET=${net:.2f}")

# synthetic reversion path for the plot
t = np.linspace(0, 240, 241)
# exponential reversion: mid(t) = 79.90 + (79.97-79.90)*(1 - 0.5**(t/90))
mid_path = block_px + (mid0 - perm_impact - block_px) * (1 - 0.5 ** (t / half_life))
mid_path += 0.004 * rng.standard_normal(len(t))  # synthetic noise
pnl_path = np.where(t < 90, 0.0, net)  # flat P&L until exit at t=90s

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), gridspec_kw={"height_ratios": [3, 2]})
fig.suptitle("T084 — Block-Trade Impact Reversion: synthetic block + resiliency exit (seed 184)",
             fontweight="bold")
ax1.axvline(0, color=PALETTE["signal"], lw=1.5, ls="--", label="block print 50k sh @ 79.90")
ax1.plot(t, mid_path, color=PALETTE["price"], lw=1.5, label="mid path (synthetic)")
ax1.axhline(mid0 - perm_impact, color=PALETTE["zero"], ls=":", lw=1, label="post-permanent mid 79.97")
ax1.scatter([5], [entry_px], color=PALETTE["profit"], s=70, zorder=5, marker="^",
            label="provide liquidity: buy 5k @ 79.91")
ax1.scatter([90], [exit_px], color=PALETTE["loss"], s=70, zorder=5, marker="v",
            label="exit @ t1/2=90s: sell 5k @ ~79.96")
ax1.annotate("temporary impact 10c\nreverts w/ t1/2 = 90 s", xy=(120, 79.93), fontsize=8,
             bbox=dict(boxstyle="round", fc="white", alpha=0.9))
ax1.set_xlim(-10, 240); ax1.set_xlabel("seconds after block")
ax1.set_ylabel("price ($)")
ax1.legend(loc="lower right", fontsize=8)

ax2.step(np.array([0, 90, 90, 240]), np.array([0, 0, net, net]), color=PALETTE["price"], lw=1.8,
         where="post")
ax2.scatter([90], [net], color=PALETTE["profit"], s=60, zorder=5)
ax2.text(100, net + 4, f"net ${net:.2f}\n(gross ${gross:.2f} - fees ${fees:.2f})", fontsize=9,
         fontweight="bold", va="bottom")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.set_xlim(-10, 240); ax2.set_xlabel("seconds after block")
ax2.set_ylabel("net P&L ($)")
ax2.set_ylim(-20, net * 1.5)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "images", "T084_example.png")
plt.savefig(out, bbox_inches="tight")
plt.close()
print("saved", out)
