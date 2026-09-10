# Pipeline status (orchestrator-maintained)

| Batch | Stages | State | Writers | Review | Merged | Quarantined |
|-------|--------|-------|---------|--------|--------|-------------|
| SB1 | 1–10 (S001,S003,S004,S006,S008,S014,S024,S025,S035,S040) | writing DONE (10/10) — review in progress |
| SB2 | 11–83 (S011,S013,S021,S027,S032,S042,S043,S063,S066,S083) | writing (3 workers) | A:S011/S013/S063 B:S021/S027/S032 C:S042/S043/S066/S083 | pending | 0 | 0 | A:S001/S003/S004 DONE (chapters+plots+PNGs verified, duck.ai OFI folded) B:S006/S008/S014 DONE (chapters+plots+PNGs verified) C:S024/S025/S035/S040 DONE (chapters+plots+PNGs verified) | reviewer running | 0 | 0 |

## Chatbot channels
- grok-answers.md / cursor-answers.md: async from another chat — fold when present, never block.
- duckai-answers.md: same protocol (duck.ai verified anonymous 2026-09-10).
- SB1: duckai-answers.md present (OFI deep-dive) → folding into S001. Grok BLOCKED on sign-in wall 2026-09-10 16:49 UTC (saved-login restore empty; header logged in SB1/grok-answers.md). Cursor BLOCKED 2026-09-10 16:50 UTC (no chat UI on cursor.com; /agent behind sign-in wall, no saved session; header logged in SB1/cursor-answers.md). Both assigned bots stalled; awaiting user decision.
