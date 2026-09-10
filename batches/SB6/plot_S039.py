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

rng = np.random.default_rng(43)  # seed 43 — bucket returns drawn below

# ---- SYNTHETIC PANEL (seed 43) ----
# One-factor model: r_i = beta_i * r_mkt + u_i, 6 five-minute buckets (30-min formation).
# Stock A: market-driven leg. Stock B: idiosyncratic (residual) leg.
beta = {"A": 1.0, "B": 0.9}
mkt = np.array([0.02, -0.03, -0.04, 0.01, 0.02, -0.01])          # % per 5-min bucket
rawA = np.array([0.01, -0.05, -0.06, 0.00, 0.01, -0.03])
rawB = np.array([-0.12, -0.10, -0.09, -0.08, -0.06, -0.05])
resA = rawA - beta["A"] * mkt
resB = rawB - beta["B"] * mkt
cum_rawA, cum_resA = np.cumsum(rawA), np.cumsum(resA)
cum_rawB, cum_resB = np.cumsum(rawB), np.cumsum(resB)
sig5 = {"A": 0.05, "B": 0.09}  # 5-min residual vol (%) — illustrative
L = 6
zA = resA.sum() / (sig5["A"] * np.sqrt(L))
zB = resB.sum() / (sig5["B"] * np.sqrt(L))

# synthetic hold outcome: next 3 buckets (15 min), market ~flat
mkt2 = np.array([0.01, 0.00, -0.01])
rawB2 = np.array([0.10, 0.08, 0.12])   # B reverts
resB2 = rawB2 - beta["B"] * mkt2
entry_px, exit_px = 100.0 + cum_rawB[-1], 100.0 + cum_rawB[-1] + rawB2.sum()
gross_bp = (exit_px / entry_px - 1) * 10000
net_bp = gross_bp - 3.0 * 2 - 1.0 - 2.0  # half-spread 3bp x2 legs + 1bp fees + 2bp slippage/impact

print("== S039 synthetic panel (seed 43) ==")
print(" bkt | mkt% | rawA% | resA% | rawB% | resB%")
for i in range(L):
    print(f"  {i+1}  | {mkt[i]:+5.2f} | {rawA[i]:+5.2f} | {resA[i]:+5.2f} | {rawB[i]:+5.2f} | {resB[i]:+5.2f}")
print(f"A: cum raw {rawA.sum():+.2f}%  cum residual {resA.sum():+.2f}%  z={zA:+.2f}")
print(f"B: cum raw {rawB.sum():+.2f}%  cum residual {resB.sum():+.2f}%  z={zB:+.2f}  (threshold |z|>=1.5 example -> fade B only)")
print(f"hold buckets: rawB2={rawB2} sum {rawB2.sum():+.2f}%, resB2 sum {resB2.sum():+.2f}%")
print(f"fade-B trade: long {entry_px:.3f} -> {exit_px:.3f}; gross {gross_bp:+.1f}bp, net (spread+fees+slippage) {net_bp:+.1f}bp")

bk = np.arange(1, 10)
fig, ax = plt.subplots()
ax.plot(bk[:6], cum_rawB, color=PALETTE["volume"], ls="--", marker="s", ms=5, label="B raw cum. return")
ax.plot(bk[:6], cum_resB, color=PALETTE["signal2"], lw=2.4, marker="o", ms=5, label="B residual cum. return (idiosyncratic)")
ax.plot(bk[:6], cum_rawA, color=PALETTE["volume"], ls=":", marker="x", ms=5, label="A raw cum. return")
ax.plot(bk[:6], cum_resA, color=PALETTE["signal"], lw=1.6, marker="o", ms=4, label="A residual cum. return")
ax.plot(bk[5:9], np.r_[cum_rawB[-1], cum_rawB[-1] + np.cumsum(rawB2)], color=PALETTE["profit"],
        lw=2.4, marker="o", ms=5, label="B hold: reversal payoff (+30bp gross)")
ax.axvline(6, color=PALETTE["zero"], ls=":", lw=1.2)
ax.annotate(f"fade trigger (bkt 6)\nB: z={zB:.2f} (fade)\nA: z={zA:.2f} (skip)",
            xy=(6, cum_resB[-1]), xytext=(7.4, -0.75), fontsize=8.5, ha="left",
            arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=PALETTE["zero"], alpha=0.92))
ax.annotate(f"exit: net {net_bp:+.0f}bp after spread+fees+slippage",
            xy=(9, cum_rawB[-1] + rawB2.sum()), xytext=(4.2, 0.35), fontsize=8.5, ha="left",
            arrowprops=dict(arrowstyle="->", color=PALETTE["profit"]))
ax.axhline(0, color=PALETTE["zero"], lw=0.8)
ax.set_title("S039 — Raw vs residual returns: the idiosyncratic leg is the fadeable one (synthetic)")
ax.set_xlabel("5-minute bucket")
ax.set_ylabel("cumulative return (%)")
ax.legend(loc="lower left", ncol=2)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S039_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
