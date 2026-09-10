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

# ---- S056 worked example (SYNTHETIC, seed 56) ----
# Fictitious ETF "QTE": 12 five-minute snapshots, iNAV vs ETF price, creation unit
# 50,000 shares x $100 = $5,000,000 notional; actionable cost bound = 8 bps (example).
rng = np.random.default_rng(56)
snap = np.arange(1, 13)
inav = np.array([100.00, 100.02, 99.98, 100.01, 100.03, 100.00,
                 100.02, 99.99, 100.01, 100.00, 100.02, 100.01])
etf = np.array([100.00, 100.03, 99.99, 100.02, 100.04, 100.15,
                100.14, 100.00, 100.05, 100.01, 100.01, 100.01])
prem_bps = (etf - inav) / inav * 1e4
BOUND = 8.0  # example — not an institutional standard

create_idx = int(np.argmax(prem_bps >= BOUND))          # snapshot 6
gross = 50_000 * 100.00 * (prem_bps[create_idx] / 1e4)
basket_exec = 5_000_000 * 0.0002                        # 2 bps example
etf_exec = 50_000 * etf[create_idx] * 0.00015            # 1.5 bps example
creation_fee = 500.0                                    # example
misc = 249.0
net = gross - basket_exec - etf_exec - creation_fee - misc

print("snapshot premium (bps):", np.round(prem_bps, 1).tolist())
print(f"create at snapshot {create_idx + 1}: premium={prem_bps[create_idx]:.1f} bps")
print(f"gross=${gross:,.0f} basket_exec=${basket_exec:,.0f} etf_exec=${etf_exec:,.0f} "
      f"fee=${creation_fee:,.0f} misc=${misc:,.0f} net=${net:,.0f}")

# ---- Plot ----
fig, ax = plt.subplots()
ax.plot(snap, inav, color=PALETTE["price"], marker="o", ms=4, label="iNAV (basket value, synthetic)")
ax.plot(snap, etf, color=PALETTE["signal"], marker="o", ms=4, label="ETF price QTE (synthetic)")
ub = inav * (1 + BOUND / 1e4)
lb = inav * (1 - BOUND / 1e4)
ax.fill_between(snap, lb, ub, color=PALETTE["band"], alpha=0.30,
                label=f"±{BOUND:.0f} bps cost bound (example)")
ax.axvspan(5.6, 7.4, color=PALETTE["profit"], alpha=0.12)
ax.scatter([create_idx + 1], [etf[create_idx]], color=PALETTE["profit"], s=110, zorder=5,
           marker="^", label=f"CREATE: buy basket, sell ETF @ {prem_bps[create_idx]:.0f} bps")
ax.annotate(f"+{prem_bps[8]:.0f} bps < {BOUND:.0f} bps bound\nvisible but NOT monetizable",
            xy=(9, etf[8]), xytext=(8.2, 100.28), fontsize=9,
            arrowprops=dict(arrowstyle="->", color=PALETTE["volume"]),
            color=PALETTE["volume"])
ax.set_title("S056 — ETF vs iNAV: synthetic 12-snapshot premium episode (seed 56)")
ax.set_xlabel("5-minute snapshot")
ax.set_ylabel("price ($)")
ax.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S056_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
