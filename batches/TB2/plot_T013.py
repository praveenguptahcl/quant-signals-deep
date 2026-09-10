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

# ---- SYNTHETIC DATA (seed 113; same numbers as T013.md T4) ----
# Three synthetic daily-ETF tapes. RSI-2 uses the S042 definition
# (100 * G2bar/(G2bar+L2bar), simple 2-period means); IBS = (C-L)/(H-L).
rng = np.random.default_rng(113)  # reserved for path jitter only

def rsi2(closes):
    out = []
    for i in range(len(closes)):
        if i < 2:
            out.append(np.nan); continue
        d1, d0 = closes[i] - closes[i - 1], closes[i - 1] - closes[i - 2]
        g = (max(d1, 0) + max(d0, 0)) / 2
        l = (max(-d1, 0) + max(-d0, 0)) / 2
        out.append(100.0 if l == 0 and g > 0 else (0.0 if g == 0 else 100 * g / (g + l)))
    return np.array(out)

def ibs(o, h, l, c):
    return np.array([(cc - ll) / (hh - ll) if hh != ll else 0.5
                     for cc, ll, hh in zip(c, l, h)])

# Trade 1: long fade. Trigger D3: RSI-2 = 0 (< 8), IBS < 0.15.
T1 = dict(label="T1 long", dir=1,
          o=[100.20, 100.00, 99.10, 98.10, 98.60, 100.50, 100.90, 101.60],
          h=[100.80, 100.30, 99.40, 98.60, 99.80, 101.00, 101.70, 102.30],
          l=[99.60, 99.00, 97.70, 97.60, 98.40, 100.20, 100.70, 101.40],
          c=[100.00, 99.20, 97.90, 98.40, 99.60, 100.80, 101.50, 102.10],
          sig_day=2, entry_open=98.10, exit_day=5, exit_open=100.50,
          atr10=1.60, stop_mult=1.8, risk=2000.0)
# Trade 2: long fade that waterfalls into the stop. Trigger D3.
T2 = dict(label="T2 long (stop)", dir=1,
          o=[200.50, 200.00, 198.40, 195.70, 194.30, 191.90, 189.90],
          h=[201.20, 200.40, 198.60, 196.10, 194.60, 192.40, 190.30],
          l=[199.60, 198.20, 195.80, 194.20, 191.70, 189.80, 188.60],
          c=[200.00, 198.50, 196.00, 194.50, 192.00, 190.00, 189.00],
          sig_day=2, entry_open=195.70, exit_day=5, exit_open=191.88,
          atr10=2.10, stop_mult=1.8, risk=2000.0)
# Trade 3: short overbought fade. Trigger D4: RSI-2 = 100 (>= 90), IBS >= 0.85.
T3 = dict(label="T3 short", dir=-1,
          o=[149.80, 150.10, 152.10, 154.40, 154.90, 154.70, 151.90],
          h=[150.60, 152.40, 154.80, 156.20, 155.20, 155.00, 152.40],
          l=[149.40, 149.90, 151.90, 154.20, 154.60, 153.20, 151.50],
          c=[150.00, 152.00, 154.50, 156.00, 155.00, 153.50, 152.00],
          sig_day=3, entry_open=154.90, exit_day=6, exit_open=151.90,
          atr10=1.50, stop_mult=1.8, risk=2000.0)

results = []
for T in (T1, T2, T3):
    c = np.array(T["c"])
    r2 = rsi2(c)
    ib = ibs(T["o"], T["h"], T["l"], c)
    sd = T["sig_day"]
    T["r2_sig"], T["ibs_sig"] = r2[sd], ib[sd]
    stop = T["entry_open"] - T["dir"] * T["stop_mult"] * T["atr10"]
    shares = int(T["risk"] / (T["stop_mult"] * T["atr10"]))
    gross = T["dir"] * (T["exit_open"] - T["entry_open"]) * shares
    notional = shares * (T["entry_open"] + T["exit_open"]) / 2
    spread_cost = 0.0002 * notional          # 2 bp round-trip allowance (example)
    comm = 2 * (shares * 0.005 + 0.50)       # $0.005/share + $0.50/ticket per side
    net = gross - spread_cost - comm
    results.append(dict(label=T["label"], r2=r2, ib=ib, shares=shares, stop=stop,
                        gross=gross, spread=spread_cost, comm=comm, net=net,
                        c=c, sig_day=sd, T=T))
    print(f'{T["label"]}: signal day RSI-2={r2[sd]:.1f} IBS={ib[sd]:.4f} '
          f'stop={stop:.2f} shares={shares} entry={T["entry_open"]:.2f} exit={T["exit_open"]:.2f} '
          f'gross={gross:+.2f} spread={spread_cost:.2f} comm={comm:.2f} net={net:+.2f}')

# Assert the example triggers (example thresholds: long RSI-2 < 8 & IBS < 0.15;
# short RSI-2 >= 90 & IBS >= 0.85; long exit RSI-2 > 65; short exit RSI-2 < 35).
assert results[0]["r2"][2] < 8 and results[0]["ib"][2] < 0.15
assert results[0]["r2"][5] > 65
assert results[1]["r2"][2] < 8 and results[1]["ib"][2] < 0.15
assert results[2]["r2"][3] >= 90 and results[2]["ib"][3] >= 0.85
assert results[2]["r2"][6] < 35
print("All T013 trigger assertions passed (seed 113).")

nets = np.array([r["net"] for r in results])
cum = np.cumsum(nets)
print(f"T013 TOTAL net: {cum[-1]:+.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [3, 2]})
fig.suptitle("T013 — RSI-2 / IBS Extreme Fade: three synthetic daily-ETF fades\n"
             "with entry/exit markers and cumulative net P&L", fontweight="bold")

x_all = []
colors = [PALETTE["price"], PALETTE["signal2"], PALETTE["signal"]]
exit_x_max = 0
for j, r in enumerate(results):
    T, c = r["T"], r["c"]
    x = np.arange(len(c)) + j * (len(c) + 3)
    x_all.append(x)
    ax1.plot(x, c, color=colors[j], lw=1.6, label=r["label"] + " close")
    se = x[T["sig_day"] + 1]
    sx = x[T["exit_day"]] + 1   # exit at the open after the exit-trigger close
    exit_x_max = max(exit_x_max, sx)
    m = "^" if T["dir"] == 1 else "v"
    col = PALETTE["profit"] if T["dir"] == 1 else PALETTE["loss"]
    ax1.scatter([se], [T["entry_open"]], marker=m, s=90, color=col, zorder=5)
    ax1.scatter([sx], [T["exit_open"]], marker="v" if T["dir"] == 1 else "^",
                s=90, color=PALETTE["signal"], zorder=5)
    side = "long" if T["dir"] == 1 else "short"
    ax1.annotate(f'{side} in\n${T["entry_open"]:.2f}', xy=(se, T["entry_open"]),
                 xytext=(8, -24), textcoords="offset points", fontsize=8, color=col,
                 weight="bold", arrowprops=dict(arrowstyle="->", color=col, lw=1.0))
    ax1.annotate(f'out ${T["exit_open"]:.2f}\n${r["net"]:+.0f}', xy=(sx, T["exit_open"]),
                 xytext=(8, 14), textcoords="offset points", fontsize=8,
                 color=PALETTE["profit"] if r["net"] >= 0 else PALETTE["loss"],
                 weight="bold", arrowprops=dict(arrowstyle="->", color="#7f8c8d", lw=1.0))
    ax1.annotate(f'RSI-2={r["r2"][T["sig_day"]]:.0f}, IBS={r["ib"][T["sig_day"]]:.2f}',
                 xy=(x[T["sig_day"]], c[T["sig_day"]]), xytext=(8, 8),
                 textcoords="offset points", fontsize=7, color=PALETTE["volume"])
ax1.set_ylabel("price ($)")
ax1.set_title("Synthetic daily tapes (seed 113); entries at next open after the signal close",
              fontsize=11)
ax1.legend(loc="upper left", fontsize=8)
ax1.set_xlim(-1, exit_x_max + 1)

xbar = np.arange(len(results))
bcols = [PALETTE["profit"] if v >= 0 else PALETTE["loss"] for v in nets]
ax2.bar(xbar, nets, color=bcols, alpha=0.85, edgecolor=PALETTE["zero"], lw=0.6)
ax2.plot(xbar, cum, color=PALETTE["price"], marker="o", ms=5, lw=1.6,
         label="cumulative net P&L")
for i, (r, cc) in enumerate(zip(results, cum)):
    ax2.annotate(f'${r["net"]:+.0f}\n(cum ${cc:+.0f})', xy=(i, r["net"]),
                 xytext=(0, 12 if r["net"] >= 0 else -24), textcoords="offset points",
                 ha="center", fontsize=8,
                 color=PALETTE["profit"] if r["net"] >= 0 else PALETTE["loss"], weight="bold")
ax2.axhline(0, color=PALETTE["zero"], lw=0.8)
ax2.set_xticks(xbar); ax2.set_xticklabels([r["label"] for r in results])
ax2.set_ylabel("P&L ($, net of costs)")
ax2.set_xlabel("synthetic trade")
ax2.set_title("Per-trade net P&L and cumulative P&L", fontsize=11)
ax2.legend(loc="upper left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/T013_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
