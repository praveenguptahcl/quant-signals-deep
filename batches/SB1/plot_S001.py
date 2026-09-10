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

# ---------------------------------------------------------------------------
# S001 worked-example tape (SYNTHETIC). Fixed event-type sequence; magnitudes
# drawn from np.random.default_rng(42). Identical generator is duplicated in
# plot_S003.py and plot_S004.py so all three chapters share one tape.
# ---------------------------------------------------------------------------
SEED = 42
rng = np.random.default_rng(SEED)

def make_tape():
    bid, ask = 231.40, 231.41
    qb = int(rng.integers(600, 1000))
    qa = int(rng.integers(200, 500))
    # (side, kind, direction): kind=size -> size changes; kind=price -> price +/- 1 tick
    types = [
        ("bid", "size", +1), ("ask", "size", -1),
        ("bid", "price", +1), ("ask", "price", +1),
        ("ask", "size", +1), ("bid", "size", -1),
        ("bid", "price", -1), ("ask", "size", -1),
        ("bid", "size", +1), ("ask", "price", +1),
    ]
    rows = [{"ev": 0, "bid": bid, "qb": qb, "ask": ask, "qa": qa}]
    for i, (side, kind, d) in enumerate(types, 1):
        pb, pa, qb_prev, qa_prev = bid, ask, qb, qa
        if kind == "size":
            if d > 0:
                new_q = int((qb if side == "bid" else qa) * float(rng.uniform(1.3, 2.1)))
            else:
                new_q = max(50, int((qb if side == "bid" else qa) * float(rng.uniform(0.2, 0.6))))
            if side == "bid":
                qb = new_q
            else:
                qa = new_q
        else:  # price move of one tick
            if side == "bid":
                bid = round(bid + d * 0.01, 2)
                qb = int(rng.integers(200, 900))
            else:
                ask = round(ask + d * 0.01, 2)
                qa = int(rng.integers(200, 900))
        rows.append({"ev": i, "bid": bid, "qb": qb, "ask": ask, "qa": qa,
                     "pb": pb, "pa": pa, "qb_prev": qb_prev, "qa_prev": qa_prev})
    return rows

def ofi_contrib(r):
    """Cont-Kukanov-Stoikov per-event contribution. e_n = dW - dV (report convention)."""
    pb, pa, qb, qa = r["bid"], r["ask"], r["qb"], r["qa"]
    pbp, pap, qbp, qap = r["pb"], r["pa"], r["qb_prev"], r["qa_prev"]
    if pb > pbp:
        dW = qb
    elif pb == pbp:
        dW = qb - qbp
    else:
        dW = -qbp
    if pa > pap:
        dV = -qap
    elif pa == pap:
        dV = qa - qap
    else:
        dV = qa
    return dW, dV, dW - dV

def main():
    tape = make_tape()
    evs, mids, e_n, cum = [], [], [], []
    print("ev | bid    | qb   | ask    | qa   | e^b    | e^a    | e_n    | cumOFI | mid")
    for r in tape[1:]:
        dW, dV, e = ofi_contrib(r)
        c = (cum[-1] if cum else 0) + e
        mid = (r["bid"] + r["ask"]) / 2
        evs.append(r["ev"]); mids.append(mid); e_n.append(e); cum.append(c)
        print(f'{r["ev"]:2d} | {r["bid"]:7.2f} | {r["qb"]:4d} | {r["ask"]:7.2f} | '
              f'{r["qa"]:4d} | {dW:+6d} | {dV:+6d} | {e:+6d} | {c:+6d} | {mid:8.3f}')
    print("initial:", tape[0])

    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 5.2),
                                   gridspec_kw={"height_ratios": [1, 1.2]})
    ax1.step(evs, mids, where="mid", color=PALETTE["price"], lw=2, label="mid price")
    ax1.set_ylabel("mid price ($)")
    ax1.legend(loc="upper left")
    ax1.set_title("S001 — Order-flow imbalance: 10-event synthetic tape (seed 42)")
    colors = [PALETTE["signal"] if v >= 0 else PALETTE["loss"] for v in e_n]
    ax2.bar(evs, e_n, color=colors, alpha=0.75, label="per-event OFI e_n (shares)")
    ax2.step(evs, cum, where="mid", color=PALETTE["price"], lw=2, label="cumulative OFI")
    ax2.axhline(0, color=PALETTE["zero"], lw=1)
    ax2.set_xlabel("event n")
    ax2.set_ylabel("OFI (shares)")
    ax2.legend(loc="upper left")

    # ---- SYNTHETIC WATERMARK (mandatory) ----
    fig = plt.gcf()
    fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
             ha="center", va="center", rotation=28, weight="bold", zorder=10)
    fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
             ha="right", va="bottom")
    plt.tight_layout()
    plt.savefig("images/S001_example.png", bbox_inches="tight")  # <-- use the chapter's ID
    plt.close()

if __name__ == "__main__":
    main()
