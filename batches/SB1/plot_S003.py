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
    evs, imbal, mids = [], [], []
    print("ev | bid    | qb   | ask    | qa   | I_t      | mid")
    for r in tape:
        I = (r["qb"] - r["qa"]) / (r["qb"] + r["qa"])
        mid = (r["bid"] + r["ask"]) / 2
        evs.append(r["ev"]); imbal.append(I); mids.append(mid)
        print(f'{r["ev"]:2d} | {r["bid"]:7.2f} | {r["qb"]:4d} | {r["ask"]:7.2f} | '
              f'{r["qa"]:4d} | {I:+.4f} | {mid:8.3f}')

    fig, ax = plt.subplots()
    ax.step(evs, imbal, where="mid", color=PALETTE["signal2"], lw=2.2,
            label="queue imbalance I_t")
    ax.axhline(0.5, color=PALETTE["loss"], ls="--", lw=1.2, label="long trigger (example ±0.5)")
    ax.axhline(-0.5, color=PALETTE["loss"], ls="--", lw=1.2)
    ax.axhline(0, color=PALETTE["zero"], lw=1)
    ax.fill_between(evs, 0.5, 1.0, color=PALETTE["profit"], alpha=0.10)
    ax.fill_between(evs, -1.0, -0.5, color=PALETTE["loss"], alpha=0.10)
    # mark where the imbalance crosses the trigger
    for i in range(1, len(imbal)):
        if abs(imbal[i]) >= 0.5 > abs(imbal[i - 1]):
            ax.annotate("trigger", (evs[i], imbal[i]), textcoords="offset points",
                        xytext=(6, -14), fontsize=8, color=PALETTE["loss"])
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(-1.05, 1.05)
    ax.set_xlabel("event n (snapshot after event)")
    ax.set_ylabel("I_t = (Qb − Qa) / (Qb + Qa)")
    ax.legend(loc="upper right")
    ax.set_title("S003 — Queue (depth) imbalance: 10-event synthetic tape (seed 42)")

    # ---- SYNTHETIC WATERMARK (mandatory) ----
    fig = plt.gcf()
    fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
             ha="center", va="center", rotation=28, weight="bold", zorder=10)
    fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
             ha="right", va="bottom")
    plt.tight_layout()
    plt.savefig("images/S003_example.png", bbox_inches="tight")  # <-- use the chapter's ID
    plt.close()

if __name__ == "__main__":
    main()
