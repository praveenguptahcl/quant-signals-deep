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

# ---- T007 worked example (seed 107) ----
# Synthetic 5-min bars, 90-minute window, fictional same-sector large caps A/B.
# Formation (frozen, per S050-S053): beta_hat = 1.80, mu_hat = 0, sigma_hat = 0.25,
# OU half-life 25 min (in 10-90 min band), ZC = 31 crossings (>= 20 gate pass),
# Engle-Granger ADF rejects at 5% on formation. All values SYNTHETIC.
rng = np.random.default_rng(107)
n = 19
tmin = np.arange(n) * 5.0

BETA, MU, SIG = 1.80, 0.0, 0.25
HL = 25.0
kappa = np.log(2) / HL
s = 0.50 * np.exp(-kappa * tmin) + rng.normal(0, 0.018, n)
s[0] = 0.50                       # exact entry anchor: z = +2.0
z = (s - MU) / SIG

# Synthetic leg B mid path (random walk around 40); leg A implied by spread
PB = 40.00 + np.cumsum(rng.normal(0, 0.04, n))
PA = BETA * PB + s
assert np.isclose(PA[0] - BETA * PB[0], s[0], atol=1e-9)

# ---- Trade logic (mirrors chapter T3 pseudocode, example thresholds) ----
Z_IN, Z_OUT, Z_STOP = 2.0, 0.25, 3.5
R = 200.0
SPREAD = 0.02
COMM = 0.005
assert z[0] >= Z_IN                        # short the spread: short A, long B
risk_share = (Z_STOP - Z_IN) * SIG         # 0.375 spread-$ per 1 share of A
N_A = int(R // risk_share)
N_B = int(round(BETA * N_A))

exit_idx, exit_why = None, ""
for b in range(1, n):
    if z[b] <= Z_OUT:                      # reversion exit (short spread)
        exit_idx, exit_why = b, "reversion"
        break
    if z[b] >= Z_STOP:                      # adverse stop
        exit_idx, exit_why = b, "adverse stop"
        break
    if tmin[b] >= 2 * HL:                   # OU time stop: max 2 half-lives
        exit_idx, exit_why = b, "time stop (2x half-life)"
        break
assert exit_idx is not None

# Causal fills: signal at bar 0 close -> fills at bar 1 open
eA = PA[1] - SPREAD / 2                    # short A: hit bid
eB = PB[1] + SPREAD / 2                    # long B: lift ask
xA = PA[exit_idx] + SPREAD / 2             # cover A: lift ask
xB = PB[exit_idx] - SPREAD / 2             # sell B: hit bid
pnlA = N_A * (eA - xA)
pnlB = N_B * (xB - eB)
gross = pnlA + pnlB
fees = (N_A + N_B) * 2 * COMM
net = gross - fees

print("T007 worked example (seed 107) — SYNTHETIC")
print(f"formation: beta_hat={BETA}, OU half-life={HL:.0f} min, ZC=31 (>=20 pass), ADF rejects at 5%")
print(f"entry bar 0: s={s[0]:.3f}, z={z[0]:.2f} -> SHORT spread: short {N_A} A, long {N_B} B")
print(f"  fills bar 1 open: short A @ {eA:.2f} | long B @ {eB:.2f}")
print(f"exit bar {exit_idx} ({tmin[exit_idx]:.0f} min, {exit_why}): s={s[exit_idx]:.3f}, z={z[exit_idx]:.2f} -> cover A @ {xA:.2f} | sell B @ {xB:.2f}")
print(f"leg A gross {pnlA:.2f} | leg B gross {pnlB:.2f} | gross {gross:.2f} | fees {fees:.2f} | NET {net:.2f}")
print(f"unrounded fills: shortA={eA:.4f} longB={eB:.4f} coverA={xA:.4f} sellB={xB:.4f}")

# ---- Plot ----
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
                               gridspec_kw={"height_ratios": [3, 2]})
ax1.plot(tmin, z, color=PALETTE["price"], lw=1.8, label="Spread z-score (synthetic)")
for lvl, ls, lab in [(Z_IN, "--", f"Entry +{Z_IN}"), (Z_OUT, ":", f"Exit +{Z_OUT}"),
                     (Z_STOP, "--", f"Stop +{Z_STOP}"), (0, "-", "Mean")]:
    ax1.axhline(lvl, color=PALETTE["signal"] if lvl >= 2 else PALETTE["signal2"] if lvl > 0
                else PALETTE["zero"], ls=ls, lw=1.1, label=lab)
ax1.scatter([0], [z[0]], s=90, color=PALETTE["loss"], marker="v", zorder=5,
            label=f"Short spread @ z={z[0]:.2f}")
ax1.scatter([tmin[exit_idx]], [z[exit_idx]], s=90, color=PALETTE["profit"], marker="^",
            zorder=5, label=f"Exit @ z={z[exit_idx]:.2f}")
ax1.set_ylabel("z-score")
ax1.set_title("T007 — Cointegration Z-Score Pairs: synthetic spread path and net P&L")
ax1.legend(loc="upper right", ncol=2)

cum = np.zeros(n)
cum[exit_idx:] = net
ax2.step(tmin, cum, where="post", color=PALETTE["profit"], lw=1.8, label="Cumulative net P&L ($)")
ax2.axhline(0, color=PALETTE["zero"], lw=1)
ax2.annotate(f"Trade 1 net: ${net:,.2f}", xy=(tmin[exit_idx], net),
             xytext=(tmin[exit_idx] + 8, net + 30),
             arrowprops=dict(arrowstyle="->", color=PALETTE["zero"]),
             fontsize=9, color=PALETTE["profit"], weight="bold")
ax2.set_xlabel("Minutes since signal bar (synthetic, 5-min bars)")
ax2.set_ylabel("Net P&L ($)")
ax2.legend(loc="lower left")

# ---- SYNTHETIC WATERMARK (mandatory) ----
fig = plt.gcf()
fig.text(0.5, 0.5, "SYNTHETIC EXAMPLE", fontsize=42, color="red", alpha=0.14,
         ha="center", va="center", rotation=28, weight="bold", zorder=10)
fig.text(0.99, 0.01, "synthetic data — not market data", fontsize=8, color="#7f8c8d",
         ha="right", va="bottom")
plt.tight_layout()
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
plt.savefig(ROOT / "images" / "T007_example.png", bbox_inches="tight")
plt.close()
print("saved", ROOT / "images" / "T007_example.png")
