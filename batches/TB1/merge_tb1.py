#!/usr/bin/env python3
"""Merge TB1 (T001-T010) into MASTER.md. Single-writer. Run from repo root."""
import re, sys, subprocess

ROOT = "."
NAMES = {
    "T001": "OFI + Queue-Imbalance Directional Scalper",
    "T002": "Microprice Fair-Value Scalper",
    "T003": "VPIN-Gated Breakout Trader",
    "T004": "VWAP-Deviation Mean-Reversion",
    "T005": "RVOL-Filtered Opening-Range Breakout",
    "T006": "Intraday Trend + Vol-Regime Allocator",
    "T007": "Cointegration Z-Score Pairs",
    "T008": "Kalman Dynamic-Hedge Pairs",
    "T009": "ETF-vs-Basket Arbitrage",
    "T010": "Variance-Risk-Premium Harvester",
}
ORDER = [f"T{i:03d}" for i in range(1, 11)]
MARKER = "<!-- STRATEGY CHAPTERS APPEND BELOW -->"

def github_anchor(text):
    t = text.lower()
    t = re.sub(r"[^a-z0-9 _\-]", "", t)
    t = t.replace(" ", "-")
    return t

with open("MASTER.md") as f:
    master = f.read()

# duplicate guard
for tid in ORDER:
    stage = 100 + int(tid[1:])
    if f"Stage {stage}/200 — {tid} merged" in master:
        print(f"SKIP {tid}: already in build log"); sys.exit(1)

# verify approvals
for tid in ORDER:
    p = f"batches/TB1/{tid}.rereview.md"
    try:
        txt = open(p).read()
    except FileNotFoundError:
        print(f"MISSING rereview {tid}"); sys.exit(1)
    if "Verdict: APPROVED" not in txt:
        print(f"NOT APPROVED {tid}"); sys.exit(1)
print("All 10 rereviews APPROVED.")

# verify plots exit 0 + PNGs exist
import os
for tid in ORDER:
    r = subprocess.run(["python3", f"batches/TB1/plot_{tid}.py"],
                       capture_output=True, timeout=300)
    assert r.returncode == 0, f"plot {tid} failed"
    assert os.path.exists(f"images/{tid}_example.png"), f"PNG {tid} missing"
print("All 10 plots exit 0, PNGs present.")

# collect chapter bodies
bodies = []
for tid in ORDER:
    stage = 100 + int(tid[1:])
    txt = open(f"batches/TB1/{tid}.md").read().rstrip("\n")
    head = f"## Stage {stage}/200 — {tid}: {NAMES[tid]}"
    assert txt.startswith(head), f"{tid} heading mismatch: {txt[:80]!r}"
    bodies.append(txt + "\n\n---\n")

# insert before marker
part2 = "\n\n".join(bodies)
assert MARKER in master
master = master.replace(MARKER, part2 + "\n" + MARKER, 1)

# TOC: replace "(none merged yet)" with TB1 group
toc_group = "#### TB1 — Flagship strategies (Stages 101–110)\n"
for tid in ORDER:
    stage = 100 + int(tid[1:])
    heading = f"Stage {stage}/200 — {tid}: {NAMES[tid]}"
    anchor = github_anchor(heading)
    label = f"{tid} — {NAMES[tid]}"
    toc_group += f"- [x] Stage {stage}/200 — [{label}](#{anchor})\n"
old_toc = "### Strategy chapters\n\n*(none merged yet)*"
assert old_toc in master
master = master.replace(old_toc, "### Strategy chapters\n\n" + toc_group.rstrip("\n"), 1)

# header bump
master = master.replace(
    "**Build status:** Stage 100/200 merged · last updated 2026-09-10 · 0 chapters deferred",
    "**Build status:** Stage 110/200 merged · last updated 2026-09-10 · 0 chapters deferred", 1)

# build log
log_lines = ""
for tid in ORDER:
    stage = 100 + int(tid[1:])
    log_lines += (f"- Stage {stage}/200 — {tid} merged 2026-09-10 · reviewer: 387a9af1"
                  f" · plot verified (seed {stage})\n")
log_anchor = "## Build log\n"
# append after existing build-log lines: find last build-log line
lines = master.split("\n")
idx = next(i for i, l in enumerate(lines) if l.startswith("## Build log"))
j = idx + 1
while j < len(lines) and (lines[j].startswith("- Stage") or lines[j] == ""):
    j += 1
lines[idx+1:j] = [l for l in lines[idx+1:j]]  # keep as-is
insert_at = j - (1 if lines[j-1] == "" else 0)
lines.insert(insert_at, log_lines.rstrip("\n"))
master = "\n".join(lines)

with open("MASTER.md.tmp", "w") as f:
    f.write(master)
print("Wrote MASTER.md.tmp")
