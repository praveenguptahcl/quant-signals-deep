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
# Shared synthetic tape (seed 42) — identical generator as plot_S001.py.
# ---------------------------------------------------------------------------
SEED = 42
rng = np.random.default_rng(SEED)

def make_tape():
    bid, ask = 231.40, 231.41
    qb = int(rng.integers(600, 1000))
    qa = int(rng.integers(200, 500))
    types = [
        ("bid", "size", +1), ("ask", "size", -1),
        ("bid", "price", +1), ("ask", "price", +1),
        ("ask", "size", +1), ("bid", "size", -1),
        ("bid", "price", -1), ("ask", "size", -1),
        ("bid", "size", +1), ("ask", "price", +1),
    ]
    rows = [{"ev": 0, "bid": bid, "qb": qb, "ask": ask, "qa": qa}]
    for i, (side, kind, d) in enumerate(types, 1):
        if kind == "size":
            if d > 0:
                new_q = int((qb if side == "bid" else qa) * float(rng.uniform(1.3, 2.1)))
            else:
                new_q = max(50, int((qb if side == "bid" else qa) * float(rng.uniform(0.2, 0.6))))
            if side == "bid":
                qb = new_q
            else:
                qa = new_q
        else:
            if side == "bid":
                bid = round(bid + d * 0.01, 2)
                qb = int(rng.integers(200, 900))
            else:
                ask = round(ask + d * 0.01, 2)
                qa = int(rng.integers(200, 900))
        rows.append({"ev": i, "bid": bid, "qb": qb, "ask": ask, "qa": qa})
    return rows

def main():
    tape = make_tape()
    evs, mids, micros, devs_bps = [], [], [], []
    print("ev | bid    | qb   | ask    | qa   | mid     | P_mu    | dev_bps")
    for r in tape:
        b, a, qb, qa = r["bid"], r["ask"], r["qb"], r["qa"]
        mid = (b + a) / 2
        pmu = (qa * b + qb * a) / (qb + qa)  # cross-weighted: bid price x ask size
        dev_bps = (pmu - mid) / mid * 1e4
        evs.append(r["ev"]); mids.append(mid); micros.append(pmu); devs_bps.append(dev_bps)
        print(f'{r["ev"]:2d} | {b:7.2f} | {qb:4d} | {a:7.2f} | {qa:4d} | '
              f'{mid:8.4f} | {pmu:8.4f} | {dev_bps:+6.2f}')

    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 5.2),
                                   gridspec_kw={"height_ratios": [1.4, 1]})
    ax1.step(evs, mids, where="mid", color=PALETTE["price"], lw=2, label="mid price")
    ax1.step(evs, micros, where="mid", color=PALETTE["signal"], lw=2, ls="--",
             label="microprice P_μ")
    ax1.fill_between(evs, mids, micros, step="mid", color=PALETTE["band"], alpha=0.5)
    ax1.set_ylabel("price ($)")
    ax1.legend(loc="upper left")
    ax1.set_title("S004 — Microprice vs mid: 10-event synthetic tape (seed 42)")
    colors = [PALETTE["profit"] if v >= 0 else PALETTE["loss"] for v in devs_bps]
    ax2.bar(evs, devs_bps, color=colors, alpha=0.8, label="P_μ − mid deviation")
    ax2.axhline(0, color=PALETTE["zero"], lw=1)
    ax2.set_xlabel("event n (snapshot after event)")
    ax2.set_ylabel("deviation (bps)")
    ax2.legend(loc="upper left")

    # ---- SYNTHETIC WATERMARK (mandatory) ----
    fig = plt.gcf()
    fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
             ha="center", va="center", rotation=28, weight="bold", zorder=10)
    fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
             ha="right", va="bottom")
    plt.tight_layout()
    plt.savefig("images/S004_example.png", bbox_inches="tight")  # <-- use the chapter's ID
    plt.close()

if __name__ == "__main__":
    main()
