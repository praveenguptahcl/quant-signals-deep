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

# ---- SYNTHETIC DATA (seed 122; same numbers as T022.md T4 table) ----
# Queue-imbalance maker with toxicity cancel, synthetic XYZ $100 scale.
# Parameters (ALL example): theta_post=0.30, flip-cancel |I|=0.20,
# sign-toxicity Tox=|sum(signs)|/4 cancel at >=0.80 against resting side,
# VPIN regime gate at 0.35 (stays green in this tape), lot=100 sh,
# inventory cap +/-2 lots, maker rebate $0.0020/sh, taker fee $0.0030/sh.
rng = np.random.default_rng(122)
N = 12
TH_POST, TH_FLIP, TH_TOX, TH_VPIN = 0.30, 0.20, 0.80, 0.35
LOT, REBATE, TAKER = 100, 0.0020, 0.0030

Qb = np.array([800, 900, 750, 400, 300, 350, 600, 850, 900, 950, 900, 850])
Qa = np.array([400, 350, 500, 700, 900, 800, 550, 400, 300, 280, 320, 350])
I = (Qb - Qa) / (Qb + Qa)
mid = np.round(100.00 + np.array([0.00, 0.00, 0.01, 0.01, 0.00, -0.01, -0.01,
                                  0.00, 0.02, 0.02, 0.02, 0.03]) + rng.normal(0, 0.003, N), 3)
bb = np.round(mid - 0.01, 2)  # best bid
ba = np.round(mid + 0.01, 2)  # best ask
signs = {  # hand-set synthetic 4-print Lee-Ready windows (+ buy-initiated)
    1: [+1, +1, +1, -1], 2: [+1, +1, +1, +1], 3: [+1, +1, -1, +1],
    4: [-1, -1, -1, +1], 5: [-1, -1, -1, -1], 6: [-1, -1, -1, +1],
    7: [-1, +1, +1, +1], 8: [+1, +1, +1, +1], 9: [+1, +1, +1, +1],
    10: [-1, +1, +1, -1], 11: [+1, +1, +1, -1], 12: [+1, +1, -1, -1],
}
vpin = np.array([0.18, 0.20, 0.22, 0.25, 0.28, 0.26, 0.22, 0.24, 0.20, 0.18, 0.19, 0.20])

resting, resting_px = None, None  # "bid"/"ask"
q, cash = 0, 0.0
fills = []
rows = []
for n in range(1, N + 1):
    i, sgn = I[n - 1], signs[n]
    tox = abs(sum(sgn)) / 4.0
    dom = +1 if sum(sgn) > 0 else (-1 if sum(sgn) < 0 else 0)
    acts = []
    if vpin[n - 1] > TH_VPIN:
        acts.append("PULL ALL (VPIN regime gate)")
        resting, resting_px = None, None
    # toxicity flip-cancels apply to ENTRY posts only; exit-working orders are held
    elif resting == "bid" and (i < -TH_FLIP or (tox >= TH_TOX and dom == -1)):
        acts.append("CANCEL bid (toxicity trigger)")
        resting, resting_px = None, None
    elif resting == "ask" and (i > TH_FLIP or (tox >= TH_TOX and dom == +1)):
        acts.append("CANCEL ask (toxicity trigger)")
        resting, resting_px = None, None
    if resting is None and abs(q) < 2 * LOT:
        if q > 0:  # work the long exit regardless of imbalance side
            resting, resting_px = "ask_exit", ba[n - 1]
            acts.append(f"POST ask (exit) @ {resting_px:.2f}")
        elif q < 0:
            resting, resting_px = "bid_exit", bb[n - 1]
            acts.append(f"POST bid (exit) @ {resting_px:.2f}")
        elif i > TH_POST:
            resting, resting_px = "bid", bb[n - 1]
            acts.append(f"POST bid @ {resting_px:.2f}")
        elif i < -TH_POST:
            resting, resting_px = "ask", ba[n - 1]
            acts.append(f"POST ask @ {resting_px:.2f}")
        else:
            acts.append("stay out (|I| below threshold)")
    elif resting == "bid":
        acts.append(f"hold bid @ {resting_px:.2f}")
    elif resting == "ask":
        acts.append(f"hold ask @ {resting_px:.2f}")
    elif resting == "ask_exit":
        acts.append(f"hold ask (exit) @ {resting_px:.2f}")
    elif resting == "bid_exit":
        acts.append(f"hold bid (exit) @ {resting_px:.2f}")
    action = " | ".join(acts)
    # scripted synthetic fills: a seller hits our bid at #10; a buyer lifts our exit ask at #12
    if n == 10 and resting == "bid":
        q += LOT
        dcash = -LOT * resting_px + LOT * REBATE
        cash += dcash
        fills.append((n, "BUY", resting_px, dcash))
        action += f" -> FILL: buy {LOT} @ {resting_px:.2f} (maker, +${LOT*REBATE:.2f} rebate)"
        resting, resting_px = None, None
    if n == 12 and resting == "ask_exit":
        q -= LOT
        dcash = LOT * resting_px + LOT * REBATE
        cash += dcash
        fills.append((n, "SELL", resting_px, dcash))
        action += f" -> FILL: sell {LOT} @ {resting_px:.2f} (maker, +${LOT*REBATE:.2f} rebate)"
        resting, resting_px = None, None
    rest_disp = ({"ask_exit": "ask(exit)", "bid_exit": "bid(exit)"}.get(resting) or (resting or "flat"))
    rows.append(dict(n=n, mid=mid[n - 1], qb=Qb[n - 1], qa=Qa[n - 1], I=i,
                     sgn=" ".join("+" if s > 0 else "-" for s in sgn), tox=tox,
                     vpin=vpin[n - 1], action=action, rest=rest_disp, q=q, cash=cash))

print("| # | mid | Qb, Qa | I | action | resting | prints | Tox | VPIN | q | cash Δ | cash cum |")
prev = 0.0
for rw in rows:
    dc = rw["cash"] - prev
    prev = rw["cash"]
    print(f"| {rw['n']} | {rw['mid']:.3f} | {rw['qb']}, {rw['qa']} | {rw['I']:+.2f} | "
          f"{rw['action']} | {rw['rest']} | {rw['sgn']} | {rw['tox']:.2f} | {rw['vpin']:.2f} | "
          f"{rw['q']:+d} | {dc:+.2f} | {rw['cash']:+.2f} |")
print("fills:", [(s, sd, round(p, 2), round(cd, 3)) for s, sd, p, cd in fills],
      "| final cash (net P&L):", round(cash, 3), "| final q:", q)

# ---- CHART ----
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 5.2), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 2, 2]})
x = np.arange(1, N + 1)
ax1.plot(x, mid, color=PALETTE["price"], lw=1.8, label="mid")
ax1.plot(x, bb, color=PALETTE["signal2"], lw=1.0, ls="--", label="best bid")
ax1.plot(x, ba, color=PALETTE["signal"], lw=1.0, ls="--", label="best ask")
cum = 0.0
eq_after = {}  # marked equity (cash + q x mid) after each fill — the honest net walk
rq, rc = 0, 0.0
for (s, sd, p, cd) in fills:
    rc += cd
    rq += LOT if sd == "BUY" else -LOT
    eq_after[s] = rc + rq * mid[s - 1]
for (s, sd, p, cd) in fills:
    mk = "^" if sd == "BUY" else "v"
    col = PALETTE["profit"] if sd == "BUY" else PALETTE["loss"]
    ax1.scatter([s], [p], marker=mk, s=110, color=col, zorder=5, edgecolors="white", linewidths=0.8)
    tag = f"{sd} {p:.2f}\neq {eq_after[s]:+.2f}" if s < N else f"{sd} {p:.2f}\nnet {cash:+.2f}"
    ax1.annotate(tag, (s, p),
                 textcoords="offset points", xytext=(6, 8 if sd == "BUY" else -28),
                 fontsize=8, color=col, weight="bold")
for n, rw in enumerate(rows, 1):
    if "CANCEL" in rw["action"]:
        ax1.annotate("cancel", (n, rw["mid"]), textcoords="offset points", xytext=(0, 14),
                     fontsize=7.5, color=PALETTE["signal"], style="italic")
ax1.set_title("T022 — Queue-Imbalance Maker with Toxicity Cancel: synthetic 12-step book tape")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left", fontsize=8)

ax2.plot(x, I, color=PALETTE["signal2"], lw=1.8, marker="o", ms=4, label="queue imbalance I")
ax2.axhline(TH_POST, color=PALETTE["profit"], ls=":", label="post threshold ±0.30")
ax2.axhline(-TH_POST, color=PALETTE["profit"], ls=":")
ax2.axhline(TH_FLIP, color=PALETTE["signal"], ls="--", label="flip-cancel ±0.20")
ax2.axhline(-TH_FLIP, color=PALETTE["signal"], ls="--")
ax2.fill_between(x, -TH_POST, TH_POST, color=PALETTE["band"], alpha=0.35)
ax2.set_ylabel("I (shares/shares)")
ax2.legend(loc="upper left", fontsize=8)

eq = [rw["cash"] + rw["q"] * mid[rw["n"] - 1] for rw in rows]  # marked to current mid
ax3.plot(x, eq, color=PALETTE["profit"], lw=1.8, marker="o", ms=4,
         label="equity = cash + q × mid (net $)")
ax3.axhline(0, color=PALETTE["zero"], lw=0.8)
ax3.set_ylabel("equity / net P&L ($)")
ax3.set_xlabel("book update #")
ax3.legend(loc="upper left", fontsize=8)
ax3.annotate(f"final net {cash:+.2f} (spread + 2 rebates)", xy=(N, eq[-1]), fontsize=8.5,
             color=PALETTE["profit"], weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T022_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
