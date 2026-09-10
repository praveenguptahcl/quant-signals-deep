"""Plot + worked-example generator for S004 (Stoikov microprice).

Implements Stoikov's *actual* estimator (2017 working paper / 2018 Quant. Finance):
the microprice is the limit of expected future mid-prices conditional on the
order-book state, P^micro = M + G*(x), where the state x = (imbalance bin,
spread bin) follows a finite-state Markov chain estimated from history.

Finite-state construction (paper Sec. 3):
  Q[x,y]  = P(M_{t+1}-M_t = 0 and X_{t+1} = y | X_t = x)      (transient, nm x nm)
  R1[x,k] = P(M_{t+1}-M_t = K[k] | X_t = x)                   (one-step mid moves)
  R2[x,y] = P(M_{t+1}-M_t != 0 and X_{t+1} = y | X_t = x)     (mid-change trans.)
  G_1  = (I - Q)^{-1} R1 K        first-order adjustment
  B    = (I - Q)^{-1} R2          propagation across mid-price changes
  G*   = G_1 + B G_1 + B^2 G_1 + ...   (converges fast; symmetrized data => OK)

All matrices below are SYNTHETIC "estimates" (seeded); the point is the
estimation machinery, not the values. The cross-weighted mid W is carried
along ONLY as the naive no-learning baseline (paper App. B degenerate case).
Run with cwd=~/workspace/quant-signals-deep.
"""
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

SEED = 42
rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------------------
# Synthetic "estimated" transition structure. n = 4 imbalance bins on
# I = Qb/(Qb+Qa): bin x iff (x-1)/4 < I <= x/4. Spread fixed at 1 tick (m = 1).
# Matrices are built reversal-symmetric (the paper symmetrizes the data so the
# microprice series converges, Thm 3.1: B* G_1 = 0).
# ---------------------------------------------------------------------------
K = np.array([-0.01, -0.005, 0.005, 0.01])  # mid-price move grid ($) — half ticks

Q = 0.80 * np.array([   # transient: quote update, mid unchanged (rows sum 0.80)
    [0.70, 0.20, 0.07, 0.03],
    [0.15, 0.65, 0.15, 0.05],
    [0.05, 0.15, 0.65, 0.15],
    [0.03, 0.07, 0.20, 0.70],
])
R1 = np.array([          # one-step mid-move probs given state (rows sum 0.10)
    [0.040, 0.025, 0.020, 0.015],   # bin 1 (ask-heavy): down moves likelier
    [0.030, 0.025, 0.025, 0.020],
    [0.020, 0.025, 0.025, 0.030],
    [0.015, 0.020, 0.025, 0.040],   # bin 4 (bid-heavy): up moves likelier
])
R2 = 0.10 * np.array([   # state transition coincident with a mid change (rows sum 0.10)
    [0.60, 0.25, 0.10, 0.05],
    [0.20, 0.55, 0.20, 0.05],
    [0.05, 0.20, 0.55, 0.20],
    [0.05, 0.10, 0.25, 0.60],
])

I4 = np.eye(4)
G1 = np.linalg.solve(I4 - Q, R1 @ K)   # first-order adjustment ($)
Bmat = np.linalg.solve(I4 - Q, R2)     # propagation across mid-price changes

# G* = G_1 + B G_1 + B^2 G_1 + ...  (paper: "in practice, this sum converges very fast")
Gstar = G1.copy()
term = G1.copy()
for _ in range(500):
    term = Bmat @ term
    Gstar += term
    if np.abs(term).max() < 1e-13:
        break
# cross-check against the closed geometric sum
Gstar_check = np.linalg.solve(I4 - Bmat, G1)
assert np.allclose(Gstar, Gstar_check, atol=1e-10), "series did not converge"

print("Synthetic estimated matrices (seed 42) — microprice adjustment per state")
print(f"G_1  ($)  = {np.round(G1, 6)}")
print(f"G*   ($)  = {np.round(Gstar, 6)}   (= P^micro - M per imbalance bin)")
print(f"G*   (c)  = {np.round(100 * Gstar, 4)}")
print(f"max |B| eigenvalue = {np.abs(np.linalg.eigvals(Bmat)).max():.4f} (< 1: converges)")
print(f"max |G*| = {100 * np.abs(Gstar).max():.4f} c  (half-spread = 0.50 c)")

# ---------------------------------------------------------------------------
# 10-event synthetic tape: fixed 1c spread; sizes put imbalance at bin centers.
# States drawn from the (row-normalized) Q chain with seed 42.
# ---------------------------------------------------------------------------
BIN_CENTER = np.array([0.125, 0.375, 0.625, 0.875])  # I = Qb/(Qb+Qa) per bin
Pq = Q / Q.sum(axis=1, keepdims=True)
states = [int(rng.integers(0, 4))]
for _ in range(9):
    states.append(int(rng.choice(4, p=Pq[states[-1]])))

BID, ASK = 231.40, 231.41
MID = (BID + ASK) / 2

evs, mids, micros, wbas, devs, devs_w = [], [], [], [], [], []
print("\nev | bin | bid    | qb  | ask    | qa  | mid     | G*(c)  | P*      | W(base) | dev*(bps) | devW(bps)")
for i, x in enumerate(states):
    qb = int(round(1000 * BIN_CENTER[x]))
    qa = 1000 - qb
    imb = qb / (qb + qa)
    gstar = Gstar[x]
    pstar = MID + gstar                                  # Stoikov microprice (learned)
    w = imb * ASK + (1 - imb) * BID                      # cross-weighted mid: BASELINE only
    dstar = (pstar - MID) / MID * 1e4
    dw = (w - MID) / MID * 1e4
    evs.append(i); mids.append(MID); micros.append(pstar); wbas.append(w)
    devs.append(dstar); devs_w.append(dw)
    print(f"{i:2d} | {x+1}   | {BID:6.2f} | {qb:3d} | {ASK:6.2f} | {qa:3d} | "
          f"{MID:8.4f} | {100*gstar:+6.3f} | {pstar:8.4f} | {w:8.4f} | {dstar:+7.2f} | {dw:+7.2f}")

# ---- Plot: microprice (learned) vs mid vs weighted-mid baseline ----
fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 5.2),
                               gridspec_kw={"height_ratios": [1.4, 1]})
ax1.step(evs, mids, where="mid", color=PALETTE["price"], lw=2, label="mid price")
ax1.step(evs, micros, where="mid", color=PALETTE["signal"], lw=2,
         label="microprice P* = M + G*(state) — learned")
ax1.step(evs, wbas, where="mid", color=PALETTE["volume"], lw=1.5, ls="--",
         label="cross-weighted mid W — naive baseline (not the microprice)")
ax1.set_ylabel("price ($)")
ax1.legend(loc="upper left")
ax1.set_title("S004 — Stoikov microprice (learned, Markov) vs weighted-mid baseline: "
              "10-event synthetic tape (seed 42)")
colors = [PALETTE["profit"] if v >= 0 else PALETTE["loss"] for v in devs]
ax2.bar(evs, devs, color=colors, alpha=0.8, label="P* − mid deviation (learned)")
ax2.step(evs, devs_w, where="mid", color=PALETTE["volume"], lw=1.5, ls="--",
         label="W − mid deviation (baseline)")
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
print("wrote images/S004_example.png")
