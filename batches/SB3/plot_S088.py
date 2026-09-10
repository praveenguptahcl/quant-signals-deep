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

# ---- SYNTHETIC WORKED EXAMPLE (deterministic schedule) ----
# 60 synthetic labeled events, one per day, 5-day label horizons.
# Chatbot worked example (Q-SB3-1, arithmetic VERIFIED): test fold = E41-E60;
# purge E36-E40 (intervals overlap the test fold); embargo removes the first 3
# TEST events E41-E43  ->  35 train / 17 test / 8 removed = 60.
# CONVENTION FLAG: de Prado's standard embargo removes the last TRAIN
# observations before the test fold (E33-E35 here) — same count (3),
# different boundary side. See chapter S3/S4.
rng = np.random.default_rng(88088)  # set for reproducibility; schedule is deterministic

N, H = 60, 5
starts = np.arange(1, N + 1)
ends = starts + H
test_lo, test_hi = 41, 60

purged = (starts <= test_hi) & (ends >= test_lo) & (starts <= 40)   # E36-E40
embargoed = (starts >= test_lo) & (starts < test_lo + 3)            # E41-E43 (bot convention)
is_test = (starts >= test_lo + 3) & (starts <= test_hi)             # E44-E60
is_train = (starts <= 40) & ~purged                                 # E1-E35

print("event | start_day | end_day | status")
for i in range(29, 48):  # print E30-E48
    if purged[i]:
        st = "PURGED"
    elif embargoed[i]:
        st = "EMBARGOED (bot convention: first 3 test events)"
    elif is_test[i]:
        st = "TEST"
    elif is_train[i]:
        st = "TRAIN"
    else:
        st = "-"
    print(f"E{i+1:>3} | {starts[i]:>9} | {ends[i]:>7} | {st}")
print(f"\ntrain={is_train.sum()} test={is_test.sum()} "
      f"removed={purged.sum() + embargoed.sum()} "
      f"(purged={purged.sum()}, embargoed={embargoed.sum()}) total={N}")

# ---- CHART ----
fig, ax = plt.subplots()
y_train = np.where(is_train)[0]
y_purge = np.where(purged)[0]
y_emb = np.where(embargoed)[0]
y_test = np.where(is_test)[0]

def draw(idxs, color, hatch=None, label=None):
    if len(idxs):
        ax.broken_barh([(starts[i], H) for i in idxs],
                       (idxs.min() + 0.6, (idxs.max() - idxs.min()) + 0.8),
                       facecolors=color, edgecolor=PALETTE["zero"],
                       linewidth=0.4, hatch=hatch, label=label)

# shade the test window and the purge/embargo bands
ax.axvspan(test_lo, test_hi + H, color=PALETTE["profit"], alpha=0.10)
ax.axvspan(36, 41, color=PALETTE["signal"], alpha=0.12)
ax.axvspan(test_lo, test_lo + 3, color=PALETTE["signal2"], alpha=0.12)

draw(y_train, PALETTE["price"], label="train E1-E35 (kept)")
draw(y_purge, PALETTE["signal"], hatch="///", label="purged E36-E40 (label overlaps test)")
draw(y_emb, PALETTE["signal2"], hatch="\\\\", label="embargoed E41-E43 (bot convention)")
draw(y_test, PALETTE["profit"], label="test E44-E60")

ax.set_xlim(28, 66)
ax.set_ylim(0, 61)
ax.set_xlabel("Day (event label interval = [start, start+5])")
ax.set_ylabel("Event index")
ax.set_title("S088 — Purged + embargoed CV: 60-event synthetic schedule")
ax.legend(loc="upper left", fontsize=8)
ax.text(0.99, 0.02,
        "35 train / 17 test / 8 removed = 60 (arithmetic verified)\n"
        "bot convention: embargo drops first 3 TEST events;\n"
        "de Prado standard drops last 3 TRAIN events instead",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=PALETTE["zero"], alpha=0.92))

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S088_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S088_example.png")
