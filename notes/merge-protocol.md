# Merge Protocol — appending chapters to the living MASTER.md (v1)

**Single-writer rule.** Exactly ONE merger agent owns `~/workspace/quant-signals-deep/MASTER.md`
at a time. Reviewers never edit MASTER.md directly — they approve chapter files in
`batches/<BATCH>/`, and the merger appends. If two mergers are ever needed, they serialize
through a lock file `MASTER.lock` (merger creates it, removes it when done; if present and
older than 30 min, the orchestrator investigates before overriding).

---

## 1. File layout

```
~/workspace/quant-signals-deep/
├── MASTER.md                      # the living document (merger-owned)
├── MASTER.lock                    # merge lock (ephemeral)
├── images/                        # S###_example.png / T###_example.png (worker-owned)
├── batches/
│   ├── SB1/ ... SB10/             # S-chapter .md + plot_S###.py + question log
│   ├── TB1/ ... TB10/             # T-chapter .md + plot_T###.py + question log
│   └── quarantine/                # failed-QC chapters + quarantine/README.md log
├── notes/                         # plan.md, visual-spec.md, cost-model.md, this file
└── questions/                     # chatbot-question-bank.md
```

## 2. MASTER.md structure conventions

### Header (maintained by merger)
```markdown
# Intraday Quant Signals & Strategies — 200-Stage Deep Dive

> Living document. Stages 1–100: signal deep dives (S001–S100).
> Stages 101–200: strategy deep dives (T001–T100). Worked examples use synthetic data
> watermarked SYNTHETIC EXAMPLE unless a real web-sourced citation is given.
> Local-build costing assumes a sunk-cost Apple Mac with M5 Max chip and 128GB unified memory.

**Build status:** Stage {k}/200 merged · last updated {YYYY-MM-DD} · {n} chapters deferred (see §Deferred)
```

### Table of contents
- TOC sits after the header, before Part I. Two sections: `### Signal chapters` and
  `### Strategy chapters`, grouped by batch with batch theme.
- Entry format: `- [x] Stage 3/200 — [S003 — Queue (depth) imbalance](#stage-3200--s003--queue-depth-imbalance)`
  (GitHub-style anchor; merger generates anchors by lowercasing, stripping punctuation, spaces→`-`).
- Deferred chapters: `- [ ] Stage 97/200 — S097 — CHAPTER-DEFERRED (in quarantine: <reason-short>)`.

### Chapter heading format (exact)
```markdown
## Stage 3/200 — S003: Queue (depth) imbalance

*Batch SB1 · Signal 3/100 · Provenance [D] · Family A — Microstructure & order flow*
```
For strategies: `## Stage 104/200 — T004: VWAP-Deviation Mean-Reversion` with
`*Batch TB1 · Strategy 4/100 · Signals S040, S003, S067*`.

### Append markers (already in scaffold)
- Signal chapters append above `<!-- SIGNAL CHAPTERS APPEND BELOW -->` (i.e. insert before the marker,
  keeping the marker as the last line of Part I).
- Strategy chapters append above `<!-- STRATEGY CHAPTERS APPEND BELOW -->`.
- Each appended chapter ends with `\n---\n` (horizontal rule) before the marker.

### Build log
Merger appends one line per merged chapter to the `## Build log` section:
`- Stage 3/200 — S003 merged 2026-09-1X · reviewer: <id> · plot verified (seed 7)`.

## 3. Merger procedure (per chapter)

1. **Collect**: read `batches/<BATCH>/<ID>.md`; confirm reviewer sign-off file
   `batches/<BATCH>/<ID>.review.md` exists with `APPROVED`.
2. **Validate**: run the QC checklist (§4). Any failure → do NOT append; follow §5.
3. **Repro check**: run `python3 batches/<BATCH>/plot_<ID>.py`; confirm the PNG regenerates
   byte-identical (or visually identical) and matches `images/<ID>_example.png`.
4. **Append**: insert the chapter before the correct marker; add `\n---\n`.
5. **TOC**: add/update the entry (flip `[ ]`→`[x]` if it was deferred), fix anchors.
6. **Header**: bump `Stage {k}/200`, date, deferred count.
7. **Build log**: append the merge line.
8. **Atomicity**: write to `MASTER.md.tmp`, `diff` sanity-check (only intended additions),
   then `mv` over `MASTER.md`. Never leave a half-written MASTER.md.

## 4. Reviewer QC checklist (per chapter — ALL must pass)

**Honesty & provenance**
- [ ] H1. Every worked example labeled synthetic in text; chart watermarked `SYNTHETIC EXAMPLE`.
- [ ] H2. No synthetic number presented as real performance; no "backtest" claims from toy data.
- [ ] H3. Provenance tag `[D]/[SR]/[D/SR]` present and not upgraded without a real citation.
- [ ] H4. Thresholds/parameters marked `example` where the report marks them non-standard.
- [ ] H5. Costs modeled explicitly (spread+fees+impact/slippage); before/after-cost labeled.
- [ ] H6. Latency-sensitive claims on SIP/L1 carry the `simulated only — requires MBO/ITCH` label where due.

**Sources & numbers**
- [ ] S1. ≥3 checkable sources (title/author/year + URL or arXiv ID); spot-check 2 resolve.
- [ ] S2. No invented paper IDs, URLs, or statistics; chatbot-only claims in `Unverified leads`.
- [ ] S3. Vendor prices suffixed `indicative — verify before budgeting`.
- [ ] S4. Cost-model numbers cite `notes/cost-model.md` (§2/§3/§5) or are labeled `measured on <date>`.

**Structure & cross-refs**
- [ ] C1. All template sections present, in order (12 for signals / 10 for strategies).
- [ ] C2. Every `S###`/`T###` cross-ref resolves to a real chapter ID in plan.md (signals 1–100, strategies T001–T100).
- [ ] C3. Chapter heading matches the exact format; stage number = position (1–100 signals, 101–200 strategies).
- [ ] C4. Jargon defined on first use (reviewer reads as a smart non-quant: if a term isn't defined, fail).

**Visuals**
- [ ] V1. PNG exists at `images/<ID>_example.png`, referenced relatively, descriptive alt text.
- [ ] V2. Watermark visible; house style block used; title carries chapter ID.
- [ ] V3. Chart numbers match the worked-example table (spot-check ≥2 points); seed stated in text.
- [ ] V4. Mermaid fenced, follows V2-S/V2-T skeleton, edges labeled with data granularity.

**Reviewer sign-off format** (`batches/<BATCH>/<ID>.review.md`):
```
Reviewer: <agent-id> | Date: YYYY-MM-DD | Chapter: S003
QC: H1-H6 PASS | S1-S4 PASS | C1-C4 PASS | V1-V4 PASS
Spot-checks: <which 2 citations resolved; which 2 chart points matched>
Verdict: APPROVED | Issues: <none / list>
```

## 5. Failed QC — quarantine, never silent drops

1. Move the chapter file to `batches/quarantine/<ID>.md` (keep images and plot script in place;
   note their paths in the log).
2. Append to `batches/quarantine/README.md`:
   ```
   ## <ID> — quarantined YYYY-MM-DD
   - Batch: <BATCH> · Stage: <k>/200
   - Failed checks: <e.g. H1, S2, V3>
   - Reason: <one paragraph, specific>
   - Attempt: 1/2
   - Action: returned to research worker for rework
   ```
3. Merger marks the TOC entry `CHAPTER-DEFERRED (in quarantine: <short reason>)` and bumps the
   deferred count in the header. The batch may merge its other 9 chapters; the deferred slot
   stays visible.
4. **Retry policy**: max 2 re-research passes. After the 2nd failure, the entry stays
   `CHAPTER-DEFERRED` permanently with the reason logged, and the orchestrator is notified.
   A deferred chapter is a visible gap, never a silent omission.
5. **Never**: delete a quarantined file, rewrite history to hide a failure, or merge a chapter
   with known QC failures "to keep momentum". The user explicitly values correctness over speed.

## 6. Ordering & idempotency

- Merge in stage order within a batch (SB1: Stages 1–10 in order). Batches merge in order
  SB1→SB10, then TB1→TB10, but a later batch never inserts before an earlier batch's marker region.
- Re-running the merger on an already-merged chapter must be a no-op: check the Build log for
  `Stage <k>/200 — <ID> merged` before appending (guard against duplicates).

## 7. Glossary & citation index (maintained from Stage 50 onward)

- Once Stage 50 merges, the merger maintains `## Appendix A — Glossary` (term → one-line definition,
  first-use chapter) and `## Appendix B — Citation index` (paper → chapters citing it).
- Workers: define jargon on first use anyway; the glossary is a reader aid, not a substitute.
