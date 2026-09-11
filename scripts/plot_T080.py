"""Regenerate images/T080_example.png — T080 gate-flow illustration.

Deterministic (seed 180). Run from repo root:
    python3 scripts/plot_T080.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

rng = np.random.default_rng(180)  # seed pinned; unused except for determinism marker

fig, ax = plt.subplots(figsize=(10, 6))
ax.set_xlim(0, 10)
ax.set_ylim(0, 6)
ax.axis("off")
ax.set_title("T080 — Multi-Source Attention Composite: gate flow (seed 180)", fontsize=11)

def box(x, y, w, h, text, color="#dbeafe"):
    ax.add_patch(patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                                        facecolor=color, edgecolor="#1e3a8a"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8,
            wrap=True)

def arrow(x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color="#1e3a8a", lw=1.2))

# feeds
box(0.3, 4.2, 2.2, 1.0, "S099 ASVI\nweekly", "#fef3c7")
box(0.3, 2.9, 2.2, 1.0, "S097 social\n15-min", "#fef3c7")
box(0.3, 1.6, 2.2, 1.0, "S093 news\nnovelty", "#fef3c7")
# gates
box(3.4, 4.2, 2.6, 1.0, "g1: asvi_pctile >= 90\n[default]")
box(3.4, 2.9, 2.6, 1.0, "g2: social_pctile >= 95\n[default]")
box(3.4, 1.6, 2.6, 1.0, "g3: stale_score >= 1\n[default]")
# borrow/macro/sched
box(3.4, 0.3, 2.6, 1.0, "g4/g5/g6: borrow<=5%\nmacro_day=0, sched=0", "#fde68a")
# cost gate
box(6.9, 2.2, 2.6, 1.6, "cost gate\nE[cost] <= 0.5 x edge", "#bbf7d0")
# output
box(6.9, 4.2, 2.6, 1.0, "OrderTicket intent\n(IOC, stp=True)", "#fecaca")

for y in (4.7, 3.4, 2.1):
    arrow(2.5, y, 3.4, y)
arrow(4.7, 0.8, 7.6, 2.2)
arrow(6.0, 4.7, 7.6, 4.7)
arrow(6.0, 3.4, 6.9, 3.0)
arrow(6.0, 2.1, 6.9, 2.6)
ax.text(8.2, 1.2, "any gate fails -> FLAT\n(no intent)", fontsize=8, color="#991b1b",
        ha="center")
ax.text(5, 0.05, "fill at open(t+1) or later — assert fill_event > signal_event",
        fontsize=8, ha="center", style="italic")

fig.tight_layout()
fig.savefig("images/T080_example.png", dpi=120)
print("wrote images/T080_example.png")
