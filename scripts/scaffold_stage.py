#!/usr/bin/env python3
"""Scaffold a new stage chapter in the quant-signals-deep repo.

Usage: python3 scripts/scaffold_stage.py <BATCH> <ID> <signal|strategy>
Example: python3 scripts/scaffold_stage.py SB2 S011 signal

Creates:
  batches/<BATCH>/<ID>.md        chapter file from the template skeleton
  batches/<BATCH>/plot_<ID>.py   deterministic plot stub (seed 7)
  batches/<BATCH>/source_<ID>.txt  one checkable source per line
"""
import os
import sys

SIGNAL_SECTIONS = [
    "One-line verdict",
    "How it works",
    "The math",
    "Worked example (SYNTHETIC)",
    "Strategies that use this signal",
    "Data required",
    "Local build on M5 Max / 128GB",
    "Buy vs build",
    "Success ratio / efficacy (after-cost)",
    "Failure modes & pitfalls",
    "Visuals",
    "Sources",
    "Unverified leads",
]

STRATEGY_SECTIONS = [
    "One-line verdict",
    "Full mechanics",
    "Signals it consumes",
    "Worked example (SYNTHETIC)",
    "Data & infra",
    "Buy vs build",
    "Success ratio evidence (after-cost)",
    "Failure modes",
    "Visuals",
    "Sources",
    "Unverified leads",
]

CHAPTER_TEMPLATE = """# {id} — <title>

*Batch {batch} · {kind_label} · Provenance [SR]*

> SYNTHETIC EXAMPLE — all worked numbers below are illustrative unless a
> real web-sourced citation is given.

{sections}
---

*Plot: `plot_{id}.py` (seed 7) → `images/{id}_example.png`*
"""

PLOT_STUB = '''#!/usr/bin/env python3
"""Worked-example chart for {id}. Deterministic — seed 7. Regenerating must
reproduce images/{id}_example.png byte-identical."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SEED = 7
rng = np.random.default_rng(SEED)

# TODO: replace with the chapter's worked-example numbers
x = np.arange(10)
y = np.cumsum(rng.normal(0, 1, 10))

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(x, y, marker="o")
ax.set_title("{id} — worked example (SYNTHETIC EXAMPLE)")
ax.text(0.5, 0.02, "SYNTHETIC EXAMPLE", transform=ax.transAxes, ha="center",
        fontsize=14, color="red", alpha=0.5)
fig.tight_layout()
fig.savefig("images/{id}_example.png", dpi=120)
print("wrote images/{id}_example.png")
'''


def main():
    if len(sys.argv) != 4 or sys.argv[3] not in ("signal", "strategy"):
        print(__doc__)
        sys.exit(1)
    batch, cid, kind = sys.argv[1], sys.argv[2], sys.argv[3]
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bdir = os.path.join(repo, "batches", batch)
    os.makedirs(bdir, exist_ok=True)

    sections = SIGNAL_SECTIONS if kind == "signal" else STRATEGY_SECTIONS
    section_md = "\n\n".join(f"## {i+1}. {s}\n\n*TBD*" for i, s in enumerate(sections))
    kind_label = f"Signal {cid[1:]}/100" if kind == "signal" else f"Strategy {cid[1:]}/100"

    chapter = CHAPTER_TEMPLATE.format(
        id=cid, batch=batch, kind_label=kind_label, sections=section_md)
    cpath = os.path.join(bdir, f"{cid}.md")
    ppath = os.path.join(bdir, f"plot_{cid}.py")
    spath = os.path.join(bdir, f"source_{cid}.txt")

    for path, content in ((cpath, chapter),
                          (ppath, PLOT_STUB.format(id=cid)),
                          (spath, "# one checkable source per line: title | author/year | URL or arXiv ID\n")):
        if os.path.exists(path):
            print(f"exists, skipping: {path}")
        else:
            with open(path, "w") as f:
                f.write(content)
            print(f"created: {path}")


if __name__ == "__main__":
    main()
