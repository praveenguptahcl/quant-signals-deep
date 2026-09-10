# Intraday Quant Signals & Strategies — 200-Stage Deep Dive

A living research document: 100 intraday signal deep dives (S001–S100) + 100
strategy deep dives (T001–T100), each with exact math, a worked synthetic example,
a generated chart, local-build costing (sunk-cost M5 Max / 128GB Mac), buy-vs-build
verdicts, and after-cost efficacy evidence. Nothing here is trading advice.

**Status:** see `batches/STATUS.md` (orchestrator-maintained) and the build log in `MASTER.md`.

## Repo layout

```
MASTER.md                 # the living document (merger-owned — see below)
MASTER.lock               # merge lock (ephemeral)
images/                   # S###_example.png / T###_example.png (worker-owned)
batches/
  SB1/ … SB10/            # signal chapters: <ID>.md + plot_<ID>.py + source_<ID>.txt + *-answers.md
  TB1/ … TB10/            # strategy chapters (same layout)
  quarantine/             # failed-QC chapters + README.md log (never silently dropped)
  STATUS.md               # pipeline status (orchestrator-maintained)
notes/
  plan.md                 # the 200-stage plan (read this first)
  chapter-template.md     # 12-section signal / 10-section strategy template
  merge-protocol.md       # merger procedure + reviewer QC checklist (H1-H6, S1-S4, C1-C4, V1-V4)
  visual-spec.md          # chart house style + mermaid skeletons
  cost-model.md           # M5 Max cost-model conventions
  chatbot-channels.md     # chatbot Q&A channel status (Grok/Cursor/ChatGPT/duck.ai/…)
questions/
  chatbot-question-bank.md  # 20 batches × 3 copy-paste research questions (SB1–SB10, TB1–TB10)
scripts/
  scaffold_stage.py       # scaffold a new stage: chapter file + plot stub + source file
```

## Workflow (roles)

- **Worker** — researches one stage, writes `batches/<BATCH>/<ID>.md` from the
  chapter template, plus `plot_<ID>.py` (seed 7) and `source_<ID>.txt`.
- **Reviewer** — runs the QC checklist (`notes/merge-protocol.md` §4), writes
  `batches/<BATCH>/<ID>.review.md` with `APPROVED` or sends it back.
- **Merger** — the ONLY writer of `MASTER.md`. Appends approved chapters per
  `notes/merge-protocol.md`. Serialize via `MASTER.lock`.
- **Chatbot legs** (async, never blocking) — question-bank batches are asked on
  external chatbots; verbatim answers land in `batches/<BATCH>/<bot>-answers.md`
  and get folded into chapters as leads. Chatbot-only claims stay in
  `Unverified leads`, never in `Sources`.

## Honesty rules (non-negotiable)

1. Every worked example is **synthetic** — labeled in text, watermarked
   `SYNTHETIC EXAMPLE` on charts. Never present toy numbers as real performance.
2. **Never invent** paper titles, URLs, arXiv IDs, or statistics. Unverifiable →
   `Unverified leads`.
3. Vendor prices suffixed `indicative — verify before budgeting`.
4. Costs always modeled explicitly (spread + fees + impact/slippage);
   every performance number labeled **before/after cost**.
5. Latency-sensitive claims on SIP/L1 carry `simulated only — requires MBO/ITCH`
   where due.

## Working with an AI agent (Cursor)

1. Read `notes/plan.md`, `batches/STATUS.md`, `notes/chapter-template.md`,
   `notes/merge-protocol.md` first.
2. Pick the next unclaimed stage from `batches/STATUS.md` / `notes/plan.md`.
3. Scaffold it: `python3 scripts/scaffold_stage.py <BATCH> <ID>` (e.g. `SB2 S011`).
4. Write the chapter, generate the chart, run the QC checklist on yourself.
5. Never edit `MASTER.md` directly — leave a review-ready chapter + plot for the merger.
6. See `.cursorrules` for the full agent instruction set.

## Connect this repo to Cursor's web agent

```bash
# from this directory, push to a GitHub repo you own, then:
# cursor.com → Agents → add the repo → prompt it with a stage task, e.g.
# "Read notes/plan.md and batches/STATUS.md, then research stage S011 per
#  notes/chapter-template.md and open a PR with batches/SB2/S011.md,
#  plot_S011.py and source_S011.txt"
```

## License / disclaimer

Research notes for a one-person paper-trading operation. Not investment advice.
All worked examples are synthetic unless a real web-sourced citation is given.
