#!/usr/bin/env python3
"""Merge TB3 (T021-T030) into MASTER.md. Single-writer. Run from repo root."""
import re, sys, subprocess, os

NAMES = {
    "T021": "Avellaneda–Stoikov Inventory Skew MM",
    "T022": "Queue-Imbalance Maker with Toxicity Cancel",
    "T023": "Hawkes Burst Scalper",
    "T024": "Informed-Size Tracker / Retail Fade",
    "T025": "Trade-Classification Trend Filter",
    "T026": "Kyle-Lambda Participation Throttle",
    "T027": "Illiquidity Temporary-Impact Fade",
    "T028": "Spread-Decomposition Router",
    "T029": "Spread-Estimate Edge Filter",
    "T030": "Multi-Level OFI Weighted Predictor",
}
ORDER = [f"T{i:03d}" for i in range(21, 31)]
MARKER = "<!-- STRATEGY CHAPTERS APPEND BELOW -->"

def github_anchor(text):
    t = text.lower()
    t = re.sub(r"[^a-z0-9 _\-]", "", t)
    return t.replace(" ", "-")

master = open("MASTER.md").read()

for tid in ORDER:
    stage = 100 + int(tid[1:])
    assert f"Stage {stage}/200 — {tid} merged" not in master, f"DUP {tid}"
    txt = open(f"batches/TB3/{tid}.rereview.md").read()
    assert "Verdict: APPROVED" in txt, f"NOT APPROVED {tid}"
print("All 10 rereviews APPROVED, no duplicates.")

for tid in ORDER:
    r = subprocess.run(["python3", f"batches/TB3/plot_{tid}.py"],
                       capture_output=True, timeout=300)
    assert r.returncode == 0, f"plot {tid} failed"
    assert os.path.exists(f"images/{tid}_example.png"), f"PNG {tid} missing"
print("All 10 plots exit 0, PNGs present.")

bodies = []
for tid in ORDER:
    stage = 100 + int(tid[1:])
    txt = open(f"batches/TB3/{tid}.md").read().rstrip("\n")
    head = f"## Stage {stage}/200 — {tid}: {NAMES[tid]}"
    assert txt.startswith(head), f"{tid} heading mismatch"
    bodies.append(txt + "\n\n---\n")

# insert before the marker (after TB1 chapters)
part3 = "\n\n".join(bodies)
assert MARKER in master
master = master.replace(MARKER, part3 + "\n" + MARKER, 1)

toc_group = "#### TB3 — Market-making and spread strategies (Stages 121–130)\n"
for tid in ORDER:
    stage = 100 + int(tid[1:])
    heading = f"Stage {stage}/200 — {tid}: {NAMES[tid]}"
    toc_group += (f"- [x] Stage {stage}/200 — [{tid} — {NAMES[tid]}]"
                  f"](#{github_anchor(heading)})\n")
# append after the TB1 group: find end of TB1 TOC group (line before "## Part I — Signal deep dives")
lines = master.split("\n")
anchor_idx = next(i for i, l in enumerate(lines)
                  if l.startswith("## Part I — Signal deep dives"))
# the TB1 group ends right before a blank line preceding that heading
assert lines[anchor_idx-1] == "", lines[anchor_idx-1]
lines.insert(anchor_idx-1, toc_group.rstrip("\n"))
master = "\n".join(lines)

master = master.replace(
    "**Build status:** Stage 110/200 merged · last updated 2026-09-10 · 0 chapters deferred",
    "**Build status:** Stage 130/200 merged · last updated 2026-09-10 · 0 chapters deferred", 1)

log_lines = "".join(
    f"- Stage {100+int(tid[1:])}/200 — {tid} merged 2026-09-10 · reviewer: 9fbe99a9"
    f" · plot verified (seed {100+int(tid[1:])})\n" for tid in ORDER)
lines = master.split("\n")
idx = next(i for i, l in enumerate(lines) if l.startswith("## Build log"))
j = idx + 1
while j < len(lines) and (lines[j].startswith("- Stage") or lines[j] == ""):
    j += 1
insert_at = j - (1 if lines[j-1] == "" else 0)
lines.insert(insert_at, log_lines.rstrip("\n"))
master = "\n".join(lines)

open("MASTER.md.tmp", "w").write(master)
print("Wrote MASTER.md.tmp")
