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

# ---- Reproducibility ----
# Tape is hand-specified and deterministic (no random draw); seed recorded for
# the plotting pipeline. Synthetic tape = operator-verified corrected chatbot
# worked example (see chapter S4): every day H=102, L=100.
rng = np.random.default_rng(130)

H = np.full(10, 102.0)
L = np.full(10, 100.0)

# Corwin-Schultz per 2-day window (operator-verified corrected values):
# alpha_1 = 0.019797  ->  S_1 = 2*tanh(alpha/2) = 0.019796  (~197.96 bp)
h2 = np.log(H / L) ** 2                       # per-day ln^2(H/L)
k  = 3.0 - 2.0 * np.sqrt(2.0)
beta   = h2[:-1] + h2[1:]                      # beta_t = h_t^2 + h_{t+1}^2
gamma  = np.log(np.maximum(H[:-1], H[1:]) / np.minimum(L[:-1], L[1:])) ** 2
alpha  = (np.sqrt(2 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
S      = 2.0 * np.tanh(alpha / 2.0)            # exact: 2(e^a-1)/(1+e^a) = 2 tanh(a/2)
S      = np.maximum(S, 0.0)                   # zero floor
windows = np.arange(1, 10)                    # windows W1..W9 (days 1-2, ..., 9-10)

fig, ax = plt.subplots()
ax.bar(windows, S * 10000.0, color=PALETTE["price"], edgecolor=PALETTE["zero"],
       alpha=0.85, label="Per-window spread estimate")
ax.axhline(S.mean() * 10000.0, color=PALETTE["signal"], linestyle="--", linewidth=1.6,
           label=f"9-window average = {S.mean()*10000:.2f} bp")
ax.set_title("S013 — Corwin-Schultz spread estimate: 10-day synthetic tape (H=102, L=100 daily)")
ax.set_xlabel("2-day estimation window (W1..W9)")
ax.set_ylabel("Spread estimate S (basis points)")
ax.set_xticks(windows)
ax.legend()
ax.text(0.02, 0.96,
        f"alpha_1 = 0.019797 (verified)\nS_1 = 2*tanh(alpha/2) = 0.019796\n= 197.96 bp (not 196.03)\n(seed 130; deterministic tape)",
        transform=ax.transAxes, fontsize=8, va="top", ha="left",
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=PALETTE["zero"], alpha=0.9))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S013_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
