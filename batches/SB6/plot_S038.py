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

rng = np.random.default_rng(42)  # seed 42 — tape is constructed deterministically below

# ---- SYNTHETIC TAPE (deterministic construction; seed 42 declared for reproducibility) ----
# 12 trade events, minutes 0..38. Mid falls 100.00 -> 99.955 (liquidity pressure),
# then reverts 99.955 -> 99.968 (temporary-impact decay). Spread fixed at $0.02.
t_min  = np.array([0, 3, 7, 10, 14, 17, 21, 24, 28, 31, 35, 38])
mid    = np.array([100.000, 99.990, 99.980, 99.975, 99.965, 99.955,
                   99.950, 99.953, 99.957, 99.961, 99.965, 99.968])
side   = np.array(["ask","bid","ask","bid","bid","bid","ask","ask","bid","ask","bid","ask"])  # aggressor side
bid    = mid - 0.01
ask    = mid + 0.01
trade  = np.where(side == "ask", ask, bid)

def rlog(p1, p0):
    return np.log(p1 / p0) * 100.0  # in percent

# formation leg events 0->5, reversal leg events 5->11
r_tr_f = rlog(trade[5], trade[0]); r_md_f = rlog(mid[5], mid[0])
r_tr_r = rlog(trade[11], trade[5]); r_md_r = rlog(mid[11], mid[5])
bounce_share = (r_tr_f - r_md_f)      # extra formation move in trade prices
bounce_share_r = (r_tr_r - r_md_r)    # extra reversal move in trade prices
# P(0)=ask, P(1)=bid demo: events 6 (ask) -> 8 (bid), mid rose, trade fell
r_tr_pb = rlog(trade[8], trade[6]); r_md_pb = rlog(mid[8], mid[6])

print("== S038 synthetic tape (seed 42) ==")
print(" ev | t(min) |   bid  |   mid  |   ask  | side | trade")
for i in range(len(t_min)):
    print(f" {i:2d} | {t_min[i]:6d} | {bid[i]:6.3f} | {mid[i]:6.3f} | {ask[i]:6.3f} | {side[i]:>4} | {trade[i]:6.3f}")
print(f"formation leg  ev0->ev5 : r(trade)={r_tr_f:+.4f}%  r(mid)={r_md_f:+.4f}%  bounce extra={bounce_share:+.4f}%")
print(f"reversal leg   ev5->ev11: r(trade)={r_tr_r:+.4f}%  r(mid)={r_md_r:+.4f}%  bounce extra={bounce_share_r:+.4f}%")
print(f"reversal fraction: trade {r_tr_r/abs(r_tr_f)*100:.1f}% of formation vs mid {r_md_r/abs(r_md_f)*100:.1f}% of formation")
print(f"P(0)=ask->P(1)=bid (ev6->ev8): r(trade)={r_tr_pb:+.4f}% with r(mid)={r_md_pb:+.4f}%  <- mechanical negative return")

fig, ax = plt.subplots()
ax.plot(t_min, bid, color=PALETTE["volume"], ls="--", lw=1, label="bid (mid - $0.01)")
ax.plot(t_min, ask, color=PALETTE["volume"], ls="--", lw=1, label="ask (mid + $0.01)")
ax.plot(t_min, mid, color=PALETTE["price"], lw=2.2, marker="o", ms=4, label="midquote m(t)")
ax.plot(t_min, trade, color=PALETTE["signal"], lw=1.2, marker="D", ms=6,
        label="transaction price (side-marked)")
for i in range(len(t_min)):
    ax.annotate(side[i], (t_min[i], trade[i]), textcoords="offset points",
                xytext=(0, 9 if side[i] == "ask" else -13), fontsize=7,
                color=PALETTE["signal"], ha="center")
ax.axvline(t_min[5], color=PALETTE["zero"], ls=":", lw=1.2)
ax.annotate("formation leg\n(ev 0→5)", xy=(t_min[2], 100.015), fontsize=8, ha="center",
            color=PALETTE["zero"])
ax.annotate("reversal leg\n(ev 5→11)", xy=(t_min[8], 100.005), fontsize=8, ha="center",
            color=PALETTE["zero"])
ax.text(0.02, 0.03,
        f"r(trade) formation {r_tr_f:+.3f}%  vs  r(mid) {r_md_f:+.3f}%\n"
        f"r(trade) reversal  {r_tr_r:+.3f}%  vs  r(mid) {r_md_r:+.3f}%",
        transform=ax.transAxes, fontsize=8.5, va="bottom", ha="left",
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=PALETTE["zero"], alpha=0.92))
ax.set_title("S038 — Sub-hour microstructure reversal: transaction-price vs midpoint paths (synthetic tape)")
ax.set_xlabel("time (minutes)")
ax.set_ylabel("price ($)")
ax.legend(loc="lower right", ncol=2)

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S038_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
