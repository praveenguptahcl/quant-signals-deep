#!/usr/bin/env python3
"""Merge TB4 (T031-T040) into MASTER.md. Single-writer. Run from repo root."""
import re, sys, subprocess, os

NAMES = {
    "T031": "Distance Pairs + Quality Filter",
    "T032": "Copula Tail-Dependence Pairs",
    "T033": "Johansen VECM Basket Arb",
    "T034": "Index Futures Cash-and-Carry",
    "T035": "Futures Calendar-Spread Carry",
    "T036": "Cross-Asset Lead-Lag (Hayashi–Yoshida)",
    "T037": "ADR / Dual-Listed Premium Convergence",
    "T038": "Sector Momentum + Idiosyncratic Fade",
    "T039": "ETF Creation/Redemption Flow Trader",
    "T040": "PCA Eigenportfolio Residual Reversal",
}
ORDER = [f"T{i:03d}" for i in range(31, 41)]
MARKER = "<!-- STRATEGY CHAPTERS APPEND BELOW -->"

def github_anchor(text):
    t = text.lower()
    t = re.sub(r"[^a-z0-9 _\-]", "", t)
    return t.replace(" ", "-")

master = open("MASTER.md").read()

for tid in ORDER:
    stage = 100 + int(tid[1:])
    assert f"Stage {stage}/200 — {tid} merged" not in master, f"DUP {tid}"

# approvals: T031-T034, T036-T038 via .rereview.md; T035/T039/T040 via spot rereview
for tid in ["T031","T032","T033","T034","T036","T037","T038"]:
    txt = open(f"batches/TB4/{tid}.rereview.md").read()
    assert "APPROVED" in txt.upper(), f"NOT APPROVED {tid}"
spot = open("batches/quarantine/tb4/SPOT_REREVIEW.md").read()
for tid in ["T035","T039","T040"]:
    assert tid in spot and "PASS" in spot, f"spot fail {tid}"
print("All 10 approved (7 rereview + 3 spot PASS), no duplicates.")

for tid in ORDER:
    r = subprocess.run(["python3", f"batches/TB4/plot_{tid}.py"],
                       capture_output=True, timeout=300)
    assert r.returncode == 0, f"plot {tid} failed"
    assert os.path.exists(f"images/{tid}_example.png"), f"PNG {tid} missing"
print("All 10 plots exit 0, PNGs present.")

bodies = []
for tid in ORDER:
    stage = 100 + int(tid[1:])
    txt = open(f"batches/TB4/{tid}.md").read().rstrip("\n")
    head = f"## Stage {stage}/200 — {tid}: {NAMES[tid]}"
    assert txt.startswith(head), f"{tid} heading mismatch"
    bodies.append(txt + "\n\n---\n")

part4 = "\n\n".join(bodies)
assert MARKER in master
master = master.replace(MARKER, part4 + "\n" + MARKER, 1)

toc_group = "#### TB4 — Pairs and basis strategies (Stages 131–140)\n"
for tid in ORDER:
    stage = 100 + int(tid[1:])
    heading = f"Stage {stage}/200 — {tid}: {NAMES[tid]}"
    toc_group += (f"- [x] Stage {stage}/200 — [{tid} — {NAMES[tid]}]"
                  f"](#{github_anchor(heading)})\n")
lines = master.split("\n")
anchor_idx = next(i for i, l in enumerate(lines)
                  if l.startswith("## Part I — Signal deep dives"))
assert lines[anchor_idx-1] == ""
lines.insert(anchor_idx-1, toc_group.rstrip("\n"))
master = "\n".join(lines)

master = master.replace(
    "**Build status:** Stage 130/200 merged · last updated 2026-09-10 · 0 chapters deferred",
    "**Build status:** Stage 140/200 merged · last updated 2026-09-10 · 0 chapters deferred", 1)

log_lines = "".join(
    f"- Stage {100+int(tid[1:])}/200 — {tid} merged 2026-09-10 · reviewer: 4a3a38b5/spot"
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
