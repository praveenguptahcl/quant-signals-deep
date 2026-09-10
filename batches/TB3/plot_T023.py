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

# ---- SYNTHETIC DATA (seed 123; same numbers as T023.md T4 table) ----
# Hawkes-burst scalper on synthetic XYZ trade tape, $100 scale, dt=0.1 s.
# Parameters (ALL example): mu=0.8 ev/s, alpha=0.6, beta=2.0 (branching 0.30),
# recursion k(t+1)=d*(k(t)+alpha*x(t)), d=exp(-beta*dt), lambda=mu+k.
# Entry: lambda_total >= 3.0 AND |psi| > 0.4 (example); exit: lambda_total < 2.2
# OR psi flips through 0 OR hold >= 6 ticks OR stop -0.03 / target +0.03 (example).
# lot=100 sh, taker fee $0.0030/sh, pay half-spread 0.01 each way.
rng = np.random.default_rng(123)
N = 22
MU, ALPHA, BETA, DT = 0.8, 0.6, 2.0, 0.1
D = np.exp(-BETA * DT)
LAM_BURST, LAM_EXIT, PSI_TH, MAX_HOLD = 3.0, 2.2, 0.4, 6
STOP, TARGET, LOT, FEE = -0.03, +0.03, 100, 0.0030

signs = np.array([+1, +1, +1, +1, +1, +1, -1, +1, +1, -1, -1, -1, -1,
                  +1, +1, +1, -1, -1, -1, +1, -1, -1])
mid = np.zeros(N)
mid[0] = 100.00
for n in range(1, N):
    mid[n] = mid[n - 1] + signs[n] * 0.01 + rng.normal(0, 0.004)

kp = kn_ = 0.0  # excitation states
pos, entry_px, hold = 0, 0.0, 0
cash = 0.0
rows, trades = [], []
for n in range(N):
    s = signs[n]
    kp = D * (kp + ALPHA * (1.0 if s > 0 else 0.0))
    kn_ = D * (kn_ + ALPHA * (1.0 if s < 0 else 0.0))
    lp, ln = MU + kp, MU + kn_
    lam = lp + ln
    psi = (lp - ln) / lam
    act = "wait"
    if pos == 0 and lam >= LAM_BURST and abs(psi) > PSI_TH:
        side = "LONG" if psi > 0 else "SHORT"
        pos = +1 if psi > 0 else -1
        entry_px = round(mid[n] + 0.01 * pos, 3)  # take the touch: pay half-spread; tick-rounded so cash matches display
        dcash = -pos * LOT * entry_px - LOT * FEE
        cash += dcash
        trades.append((n + 1, "ENTER " + side, entry_px, dcash, "open"))
        act = f"ENTER {side} @ {entry_px:.3f} (taker, fee ${LOT*FEE:.2f})"
        hold = 0
    elif pos != 0:
        hold += 1
        pnl_vs = (mid[n] - entry_px) * pos * LOT
        ex = (lam < LAM_EXIT) or (psi * pos < 0) or (hold >= MAX_HOLD) \
            or (pnl_vs <= STOP * LOT) or (pnl_vs >= TARGET * LOT)
        if ex:
            exit_px = round(mid[n] - 0.01 * pos, 3)  # tick-rounded so cash matches display
            dcash = pos * LOT * exit_px - LOT * FEE
            cash += dcash
            why = "lambda fade" if lam < LAM_EXIT else ("psi flip" if psi * pos < 0
                  else ("max hold" if hold >= MAX_HOLD else ("stop" if pnl_vs <= STOP * LOT else "target")))
            trades.append((n + 1, "EXIT", exit_px, dcash, why))
            act = f"EXIT @ {exit_px:.3f} ({why}; taker, fee ${LOT*FEE:.2f})"
            pos, entry_px, hold = 0, 0.0, 0
    rows.append(dict(n=n + 1, sign="+" if s > 0 else "-", mid=mid[n], lp=lp, ln=ln,
                     lam=lam, psi=psi, act=act, pos=pos, cash=cash))

# flatten any leftover at last mid minus half-spread (example terminal rule)
if pos != 0:
    exit_px = round(mid[-1] - 0.01 * pos, 3)  # tick-rounded so cash matches display
    dcash = pos * LOT * exit_px - LOT * FEE
    cash += dcash
    trades.append((N + 1, "EXIT", exit_px, dcash, "session end"))
    rows[-1]["act"] += f" | EXIT @ {exit_px:.3f} (session end)"

print("| tick | sign | mid | lambda+ | lambda- | lambda_tot | psi | action | pos | cash Δ | cash cum |")
prev = 0.0
for rw in rows:
    dc = rw["cash"] - prev
    prev = rw["cash"]
    print(f"| {rw['n']} | {rw['sign']} | {rw['mid']:.3f} | {rw['lp']:.2f} | {rw['ln']:.2f} | "
          f"{rw['lam']:.2f} | {rw['psi']:+.2f} | {rw['act']} | {rw['pos']:+d} | {dc:+.3f} | {rw['cash']:+.3f} |")
print("trades:", [(s, sd, round(p, 3), round(cd, 3), w) for s, sd, p, cd, w in trades],
      "| final net P&L:", round(cash, 3))

# ---- CHART ----
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 5.2), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 2, 2]})
x = np.arange(1, N + 1)
ax1.plot(x, mid, color=PALETTE["price"], lw=1.8, label="mid ($)")
for (s, sd, p, cd, w) in trades:
    if s > N:
        continue
    mk, col, ec = "^", PALETTE["profit"], "white"  # default
    if "ENTER" in sd:
        mk, col, ec = ("^", PALETTE["profit"], "white") if "LONG" in sd else ("v", PALETTE["loss"], "white")
    else:
        mk, col, ec = ("x", PALETTE["zero"], None)
    if ec is None:
        ax1.scatter([s], [p], marker=mk, s=100, color=col, zorder=5, linewidths=1.6)
    else:
        ax1.scatter([s], [p], marker=mk, s=100, color=col, zorder=5, edgecolors=ec, linewidths=0.8)
    if "ENTER" in sd:
        ax1.annotate(f"{sd}\n{p:.3f}", (s, p), textcoords="offset points", xytext=(6, 8),
                     fontsize=7.5, color=col, weight="bold")
    else:
        # trade net = entry cash delta + exit cash delta
        trade_net = sum(cd for _, sd2, _, cd, _ in trades if "ENTER" in sd2 or "EXIT" in sd2)
        ax1.annotate(f"exit {p:.3f}\ntrade net {trade_net:+.2f} ({w})", (s, p),
                     textcoords="offset points", xytext=(6, -26), fontsize=7.5, color=col, style="italic")
ax1.set_title("T023 — Hawkes Burst Scalper: synthetic 22-tick trade tape, burst detection, signed entry/exit")
ax1.set_ylabel("mid ($)")
ax1.legend(loc="upper left", fontsize=8)

ax2.plot(x, [rw["lp"] for rw in rows], color=PALETTE["profit"], lw=1.6, label="buy intensity λ+")
ax2.plot(x, [rw["ln"] for rw in rows], color=PALETTE["loss"], lw=1.6, label="sell intensity λ−")
ax2.plot(x, [rw["lam"] for rw in rows], color=PALETTE["price"], lw=1.2, ls="--", label="total λ")
ax2.axhline(LAM_BURST, color=PALETTE["signal"], ls=":", label="burst threshold 3.0")
ax2.set_ylabel("intensity (ev/s)")
ax2.legend(loc="upper left", fontsize=8)

ax3.plot(x, [rw["psi"] for rw in rows], color=PALETTE["signal2"], lw=1.8, marker="o", ms=3, label="ψ (signed imbalance)")
ax3.axhline(PSI_TH, color=PALETTE["signal"], ls="--", label="entry ±0.4")
ax3.axhline(-PSI_TH, color=PALETTE["signal"], ls="--")
ax3.axhline(0, color=PALETTE["zero"], lw=0.8)
ax3.fill_between(x, PSI_TH, -PSI_TH, color=PALETTE["band"], alpha=0.35)
ax3.set_ylabel("ψ")
ax3.set_xlabel("tick # (Δt = 0.1 s)")
ax3.legend(loc="upper left", fontsize=8)
ax3.annotate(f"final net P&L {cash:+.2f}", xy=(N, rows[-1]["psi"]), fontsize=9,
             color=PALETTE["zero"], weight="bold")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T023_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
