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

# ---- SYNTHETIC DATA (seed 121; same numbers as T021.md T4 table) ----
# Avellaneda-Stoikov inventory-skew MM on synthetic large-cap XYZ, $100 scale.
# Parameters (ALL example): gamma=0.10, kappa=100.0 (per $), sigma=0.30 ($/sqrt(tau)),
# T=1.0 session, lot=5 shares, Qmax=20 shares, maker rebate $0.0020/sh,
# taker fee $0.0030/sh, OFI veto: pull resting bid if OFI z < -1.5 (example).
# Fair value = microprice proxy M = mid + (spread/2)*I (spread $0.02), a
# first-order operational proxy of the S004 definition (labeled as such in text).
rng = np.random.default_rng(121)
N = 16
GAMMA, KAPPA, SIGMA, T = 0.10, 100.0, 0.30, 1.0
LOT, QMAX = 5, 20
REBATE, TAKER_FEE = 0.0020, 0.0030
OFI_VETO_Z = -1.5  # example

base = np.array([100.00, 100.02, 100.035, 100.02, 100.00, 99.99, 99.975, 100.00,
                 100.03, 100.05, 100.045, 100.02, 100.005, 100.02, 100.035, 100.025])
mid = base + rng.normal(0, 0.006, N)
imb = np.array([0.2, 0.4, 0.5, 0.3, 0.1, -0.2, -0.4, -0.3, 0.1, 0.3, 0.5, 0.4,
                0.2, 0.0, 0.2, 0.1])
ofi = np.array([200, 500, 800, 300, -100, -600, -1200, -400, 300, 700, 900, 400,
                100, -200, 100, 0], dtype=float)

M = mid + 0.01 * imb  # microprice proxy
tau = T - np.linspace(0, 1, N)
d_half = 0.5 * (GAMMA * SIGMA**2 * tau + (2.0 / GAMMA) * np.log(1 + GAMMA / KAPPA))

q = 0
cash = 0.0
rows = []
trades = []  # (step, side, price, shares, cash_delta)
r = M[0] - q * GAMMA * SIGMA**2 * tau[0]
bid = round(r - d_half[0], 2)
ask = round(r + d_half[0], 2)
rows.append(dict(step=1, mid=mid[0], I=imb[0], M=M[0], qb=q, r=r, bid=bid, ask=ask,
                 z=np.nan, event="start", q=q, cash=cash))

for n in range(1, N):
    r = M[n] - q * GAMMA * SIGMA**2 * tau[n]
    d = d_half[n]
    bid = round(r - d, 2)
    ask = round(r + d, 2)
    # OFI z-score over rolling window of last 6 (population std), needs >=4 obs
    w = ofi[max(0, n - 5):n + 1]
    z = (ofi[n] - w.mean()) / w.std() if len(w) >= 4 and w.std() > 0 else 0.0
    event = "no fill"
    # OFI veto: pull resting bid if flow is sharply adverse to the bid
    veto = (z < OFI_VETO_Z)
    qb = q
    dcash = 0.0
    prev_bid, prev_ask = rows[-1]["bid"], rows[-1]["ask"]
    bid_pulled = (qb >= QMAX) or veto
    ask_pulled = (qb <= -QMAX)
    if M[n] >= prev_ask - 0.002 and not ask_pulled:
        q -= LOT
        dcash = LOT * prev_ask + LOT * REBATE
        cash += dcash
        event = f"SELL {LOT} @ {prev_ask:.2f} (ask lifted)"
        trades.append((n + 1, "SELL", prev_ask, LOT, dcash))
    elif M[n] <= prev_bid + 0.002 and not bid_pulled:
        q += LOT
        dcash = -(LOT * prev_bid) + LOT * REBATE
        cash += dcash
        event = f"BUY {LOT} @ {prev_bid:.2f} (bid hit)"
        trades.append((n + 1, "BUY", prev_bid, LOT, dcash))
    elif veto:
        event = "no fill — OFI veto (bid pulled)"
    elif bid_pulled:
        event = "no fill — inventory cap (bid pulled)"
    rows.append(dict(step=n + 1, mid=mid[n], I=imb[n], M=M[n], qb=qb, r=r, bid=bid,
                     ask=ask, z=z, event=event, q=q, cash=cash))

# terminal liquidation: flatten at the touch (pay half-spread + taker fee), example
term = ""
if q != 0:
    if q > 0:
        liq_px = round(M[-1] - 0.01, 2)
        dcash = q * liq_px - abs(q) * TAKER_FEE
        term = f"sell {q} @ {liq_px:.2f} (terminal, taker)"
    else:
        liq_px = round(M[-1] + 0.01, 2)
        dcash = q * liq_px - abs(q) * TAKER_FEE
        term = f"buy {abs(q)} @ {liq_px:.2f} (terminal, taker)"
    cash += dcash
    trades.append((N + 1, "TERMINAL", liq_px, q, dcash))

print("| # | t | mid | I | microprice | q(b) | r | bid / ask | OFI z | event | q(a) | cash Δ | cash cum |")
for i, rw in enumerate(rows):
    t = round(i / (N - 1), 3)
    z = "—" if np.isnan(rw["z"]) else f"{rw['z']:.2f}"
    dc = rw["cash"] - (rows[i - 1]["cash"] if i > 0 else 0.0)
    print(f"| {rw['step']} | {t:.2f} | {rw['mid']:.3f} | {rw['I']:+.1f} | {rw['M']:.3f} | "
          f"{rw['qb']:+d} | {rw['r']:.4f} | {rw['bid']:.2f} / {rw['ask']:.2f} | {z} | "
          f"{rw['event']} | {rw['q']:+d} | {dc:+.3f} | {rw['cash']:+.3f} |")
print("terminal:", term, "| final cash (net P&L):", round(cash, 3))
print("trades:", [(s, sd, round(p, 2), sh, round(cd, 3)) for s, sd, p, sh, cd in trades])

# ---- CHART ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
x = np.arange(1, N + 1)
ax1.plot(x, [rw["M"] for rw in rows], color=PALETTE["price"], lw=1.8, label="microprice fair value (M)")
ax1.plot(x, [rw["bid"] for rw in rows], color=PALETTE["signal2"], lw=1.0, ls="--", label="bid quote")
ax1.plot(x, [rw["ask"] for rw in rows], color=PALETTE["signal"], lw=1.0, ls="--", label="ask quote")
ax1.fill_between(x, [rw["bid"] for rw in rows], [rw["ask"] for rw in rows],
                 color=PALETTE["band"], alpha=0.35, label="quoted spread band")
cum = 0.0
# marked equity after each fill (cash + inventory x final microprice)
eq_after = {}
run_cash, run_q = 0.0, 0
Mfinal = rows[-1]["M"]
for (s, sd, p, sh, cd) in trades:
    if s > N:
        continue
    run_cash += cd
    run_q += sh if sd == "BUY" else (-sh if sd == "SELL" else 0)
    eq_after[(s, sd)] = run_cash + run_q * Mfinal
ann_i = 0
for (s, sd, p, sh, cd) in trades:
    if s > N:
        continue
    mk = "^" if sd == "BUY" else "v"
    col = PALETTE["profit"] if sd == "BUY" else PALETTE["loss"]
    ax1.scatter([s], [p], marker=mk, s=90, color=col, zorder=5,
                edgecolors="white", linewidths=0.8)
    above = (ann_i % 2 == 0)
    ax1.annotate(f"{sd} {p:.2f}\neq {eq_after[(s, sd)]:+.2f}", (s, p),
                 textcoords="offset points", xytext=(6, 10 if above else -30),
                 fontsize=7.5, color=col, weight="bold")
    ann_i += 1
ax1.set_ylabel("price ($)")
ax1.set_title("T021 — Avellaneda–Stoikov Inventory Skew MM: synthetic quote tape, fills, and cumulative net P&L")
ax1.legend(loc="upper left", fontsize=8)

# inventory + cumulative net P&L (marked to last microprice)
inv = [rw["q"] for rw in rows]
cum_pnl = []
run = 0.0
for i, rw in enumerate(rows):
    run = rw["cash"]
    cum_pnl.append(run + rw["q"] * rows[-1]["M"] if i < N else run)
ax2.step(x, inv, where="mid", color=PALETTE["signal2"], lw=1.6, label="inventory q (shares)")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_ylabel("inventory (shares)", color=PALETTE["signal2"])
ax2.set_xlabel("quote update #")
ax2b = ax2.twinx()
ax2b.plot(x, cum_pnl, color=PALETTE["profit"], lw=1.8, marker="o", ms=3, label="cum net P&L (marked to final M)")
ax2b.set_ylabel("cum net P&L ($)", color=PALETTE["profit"])
ax2.annotate(f"terminal flatten: {term}", xy=(N, inv[-1]), fontsize=8, color=PALETTE["zero"])

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T021_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
