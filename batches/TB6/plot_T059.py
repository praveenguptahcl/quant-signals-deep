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

# ---- T059 worked-example data (MUST match T4 text exactly) ----
rng = np.random.default_rng(159)  # seed stated in T4
wallets = ["W1", "W2", "W3", "W4", "W5"]
meta_p  = np.array([0.72, 0.68, 0.61, 0.48, 0.35])   # S086 meta-labeler score (example)
tau = 0.55                                             # veto threshold (example)
farmed = meta_p > tau                                  # W1..W3 farmed; W4, W5 skipped
gas    = np.array([52.40, 48.10, 55.75, 51.00, 49.25])  # $ gas spent per wallet (example)
drop_usd = 180.00                                      # 450 AIRX @ $0.40 (example projection)
claim_gas = 3.00                                       # $ per eligible wallet (example)
eligible = np.array([True, True, False, False, False]) # realized eligibility
nets = np.where(farmed & eligible, drop_usd - gas - claim_gas,
       np.where(farmed & ~eligible, -gas, 0.0))
for w, p, f, g, e, n in zip(wallets, meta_p, farmed, gas, eligible, nets):
    print(f"{w}: meta {p:.2f} {'BET' if f else 'SKIP'} gas ${g:.2f} "
          f"{'eligible' if (f and e) else ('ineligible' if f else 'skipped')} NET {n:+.2f}$")
print(f"TOTAL NET {nets.sum():+.2f}$")

# weekly cashflow: gas spread over weeks 1-8 (seeded jitter, anchors exact at totals)
weeks = np.arange(0, 9)
week_gas = np.zeros(9)
jitter = rng.normal(0, 0.4, 8); jitter -= jitter.mean()
for i, g in enumerate(gas[farmed]):
    wk = g / 8 + jitter * (g / gas[farmed].sum())
    week_gas[1:9] += wk
cum = -np.cumsum(week_gas)
cum[8] += (drop_usd * (farmed & eligible).sum() - claim_gas * (farmed & eligible).sum())

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=False, height_ratios=[3, 2])
colors = [PALETTE["profit"] if n > 0 else (PALETTE["loss"] if n < 0 else PALETTE["volume"])
          for n in nets]
bars = ax1.bar(wallets, nets, color=colors, edgecolor="k", zorder=3)
ax1.axhline(0, color=PALETTE["zero"], lw=1)
for w, p, n, f in zip(wallets, meta_p, nets, farmed):
    ax1.text(w, n + (6 if n >= 0 else -10), f"meta {p:.2f}\n{n:+.2f}$",
             ha="center", fontsize=8, color=PALETTE["zero"])
ax1.set_ylabel("net P&L per wallet ($)")
ax1.set_title("T059 — Airdrop Farming Yield Optimizer: synthetic campaign per-wallet net & EV path")

ax2.step(weeks, cum, where="post", color=PALETTE["price"], lw=2,
         label="cumulative campaign net ($)")
ax2.fill_between(weeks, cum, 0, step="post", alpha=0.25,
                 color=PALETTE["profit"] if cum[-1] > 0 else PALETTE["loss"])
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.scatter([8], [cum[8]], s=80, color=PALETTE["profit"], edgecolors="k", zorder=5)
ax2.annotate(f"drop claimed\ncum {cum[8]:+.2f}$", xy=(8, cum[8]), xytext=(-70, 25),
             textcoords="offset points", fontsize=8, color=PALETTE["profit"],
             arrowprops=dict(arrowstyle="->", color=PALETTE["profit"], lw=1))
ax2.set_xlabel("campaign week")
ax2.set_ylabel("cumulative net ($)")
ax2.legend(loc="lower right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T059_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/T059_example.png")
