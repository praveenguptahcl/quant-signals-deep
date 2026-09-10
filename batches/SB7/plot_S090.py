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

# ---- WORKED EXAMPLE: chatbot-provided tiny synthetic tape (Duck.ai Q-SB7-1),
# ---- arithmetic OPERATOR-VERIFIED on 2026-09-10 with ONE correction applied.
# The bot's k=2 block had a single arithmetic error:
#   bot wrote 2*(-2.5)^2 = 12  ->  correct 2*6.25 = 12.5
# Corrected chain: sum of squared deviations = 9 + 12.5 + 0.5 = 22.0 (bot: 21.5);
#   s_2^2 = 22.0/7 = 3.142857 (bot: 3.07143);
#   VR(2) = 3.142857/(2*1.0) = 1.5714 (bot: 1.5357);
#   H_hat(2) = 0.5*[1 + ln(1.5714)/ln2] = 0.826 (bot: 0.808).
# Everything else verified: s_1^2 = 1.0; VR(4) = 0.5667; H_hat(4) = 0.295.
rng = np.random.default_rng(7)  # set for reproducibility (this tape is hand-specified)

ks   = np.array([1, 2, 4])                      # horizons plotted
vrs  = np.array([1.0, 1.5714, 0.5667])          # VR(1)=1 by definition; VR(2), VR(4) corrected/verified
hs   = np.array([0.5, 0.826, 0.295])            # H_hat = 0.5*[1 + ln(VR(k))/ln k]

# Sanity: H mapping recomputes from VR to machine precision (k>=2)
hs_check = 0.5 * (1 + np.log(vrs[1:]) / np.log(ks[1:]))
assert np.allclose(hs[1:], hs_check, rtol=1e-3, atol=1e-3), hs_check

print("k, VR(k), H_hat(k)")
for k, v, h in zip(ks, vrs, hs):
    print(f"{k}, {v:.4f}, {h:.3f}")

# Illustrative VR-toggle sizing overlay (bot suggestion, labelled illustrative in text)
def g_illustrative(vr4):
    if vr4 > 1.10:
        return 0.5
    if vr4 < 0.90:
        return 1.25
    return 1.0

print(f"illustrative toggle on this tape: VR(4)={vrs[2]:.4f} < 0.90 -> "
      f"g = {g_illustrative(vrs[2])}x for a mean-reversion strategy")

# ---- PLOT ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5.2))

# Left: VR(k) bars with toggle zones
cols = [PALETTE["profit"] if v > 1 else (PALETTE["loss"] if v < 1 else PALETTE["volume"])
        for v in vrs]
ax1.bar([f"k={k}" for k in ks], vrs, color=cols, edgecolor="#2c3e50")
ax1.axhline(1.0, color=PALETTE["zero"], lw=1.5, ls="--", label="VR = 1 (random walk)")
ax1.axhspan(0, 1.0, color=PALETTE["band"], alpha=0.35)
ax1.set_ylabel("VR(k) = Var(r_t(k)) / [k * Var(r_t)]")
ax1.set_title("Variance ratio vs horizon (corrected chain)")
ax1.set_ylim(0, 2.1)
ax1.legend()
ax1.annotate("VR(2)=1.5714\nH^=0.826\n-> momentum label",
             xy=(1, vrs[1]), xytext=(0.05, 1.85),
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal"]),
             fontsize=9, color=PALETTE["signal"])
ax1.annotate("VR(4)=0.5667\nH^=0.295\n-> reversal label",
             xy=(2, vrs[2]), xytext=(2.15, 1.25),
             arrowprops=dict(arrowstyle="->", color=PALETTE["signal2"]),
             fontsize=9, color=PALETTE["signal2"])

# Right: implied Hurst with zones
ax2.bar([f"k={k}" for k in ks], hs, color=PALETTE["signal2"], edgecolor="#2c3e50")
ax2.axhline(0.5, color=PALETTE["zero"], lw=1.5, ls="--", label="H = 0.5 (random walk)")
ax2.axhspan(0.5, 1.0, color=PALETTE["profit"], alpha=0.18, label="momentum zone")
ax2.axhspan(0, 0.5, color=PALETTE["loss"], alpha=0.18, label="reversion zone")
ax2.set_ylabel("Implied Hurst  H^ = 1/2 [1 + ln VR(k) / ln k]")
ax2.set_title("Implied Hurst — same tape contradicts itself")
ax2.set_ylim(0, 1.0)
ax2.legend(loc="upper right")
fig.suptitle("S090 — VR/Hurst regime test: corrected synthetic example", y=1.02)
fig.text(0.5, 0.02,
         "Tiny-sample lesson: k=2 says momentum (H^=0.826), k=4 says reversal (H^=0.295) — diagnostic, not a standalone rule.",
         ha="center", fontsize=9, style="italic", color=PALETTE["zero"])

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
plt.savefig("images/S090_example.png", bbox_inches="tight")  # <-- use the chapter's ID
plt.close()
print("saved images/S090_example.png")
