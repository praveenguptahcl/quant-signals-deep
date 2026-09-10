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

# ---- SYNTHETIC TAPE (hand-specified; operator-verified Duck.ai tape) ----
rng = np.random.default_rng(42)  # script seed (tape itself is hand-specified, not drawn)
closes = np.array([100., 99., 98., 99., 100., 101., 100., 99., 98., 97.])
deltas = np.diff(closes, prepend=np.nan)
gains = np.where(deltas > 0, deltas, 0.0)
losses = np.where(deltas < 0, -deltas, 0.0)

rsi2 = np.full(len(closes), np.nan)
for t in range(2, len(closes)):
    g_bar = (gains[t] + gains[t - 1]) / 2.0      # simple 2-period mean (NOT Wilder's SMMA)
    l_bar = (losses[t] + losses[t - 1]) / 2.0
    rsi2[t] = 0.0 if g_bar == 0 else (100.0 if l_bar == 0 else 100.0 * g_bar / (g_bar + l_bar))

# Verify against operator-checked values: D3 0 / D4 50 / D5 100 / D6 100 / D7 50 / D8 0 / D9 0 / D10 0
expected = {2: 0.0, 3: 50.0, 4: 100.0, 5: 100.0, 6: 50.0, 7: 0.0, 8: 0.0, 9: 0.0}
for t, v in expected.items():
    assert abs(rsi2[t] - v) < 1e-9, (t, rsi2[t], v)

print("Day  Close   Delta   G_bar  L_bar  RSI-2")
for t in range(len(closes)):
    print(f"D{t+1:<3d} {closes[t]:>6.2f} {deltas[t]:>7.2f}  {'-':>5}  {'-':>5}  {'-':>6}"
          if t < 2 else
          f"D{t+1:<3d} {closes[t]:>6.2f} {deltas[t]:>7.2f}  {(gains[t]+gains[t-1])/2:>5.2f}  "
          f"{(losses[t]+losses[t-1])/2:>5.2f}  {rsi2[t]:>6.1f}")

THETA = 10.0  # oversold threshold, example — not an institutional standard
entry_day = int(np.where(rsi2 < THETA)[0][0]) + 1  # first day RSI-2 < 10 (D3)

days = np.arange(1, len(closes) + 1)
fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [1.6, 1]})
ax1.set_title("S042 — RSI / RSI-2 mean reversion (Connors-style): 10-day synthetic tape")
ax1.plot(days, closes, marker="o", color=PALETTE["price"], label="Close ($, synthetic)")
ax1.scatter([entry_day], [closes[entry_day - 1]], s=110, color=PALETTE["profit"],
            zorder=5, label=f"Long entry (D{entry_day}, RSI-2={rsi2[entry_day-1]:.0f})")
ax1.set_ylabel("Price ($)")
ax1.legend(loc="lower left")
ax2.plot(days, rsi2, marker="s", color=PALETTE["signal"], label="RSI-2 (simple 2-period mean)")
ax2.axhline(THETA, color=PALETTE["loss"], ls="--", lw=1.2, label=f"Oversold line ({THETA:.0f}, example)")
ax2.fill_between(days, 0, THETA, color=PALETTE["loss"], alpha=0.08)
ax2.set_ylabel("RSI-2 (0-100)")
ax2.set_xlabel("Day")
ax2.set_ylim(-5, 105)
ax2.set_xticks(days)
ax2.legend(loc="upper right")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S042_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("wrote images/S042_example.png; entry day D%d" % entry_day)
