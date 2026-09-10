# Pipeline status (orchestrator-maintained)

| Batch | Stages | State | Writers | Review | Merged | Quarantined |
|-------|--------|-------|---------|--------|--------|-------------|
| SB1 | 1–40 (S001,S003,S004,S006,S008,S014,S024,S025,S035,S040) | review DONE: 0/10 APPROVED — rework attempt 1/2 | R1:S004/S008/S014/S024 DONE (re-derived: Stoikov G*, bar-level BVC fires, spread labels corrected, lookahead resolved) R2 DONE | re-review running | 0 | 0 |
| SB2 | 11–83 (S011,S013,S021,S027,S032,S042,S043,S063,S066,S083) | writing (3 workers) | A:S011/S013/S063 DONE (chapters+plots+PNGs verified, V4/C4 fixed) B:S021/S027/S032 DONE C:S042/S043/S066/S083 (running) | pending | 0 | 0 |
| SB5 | 22–45 (S022,S023,S026,S028,S029,S030,S031,S033,S044,S045) | writing (3 workers) | A:S022/S023/S026 DONE (verified on disk; HKS figures verified vs paper) B:S028/S029/S030 DONE C:S031/S033/S044/S045 (running) | pending | 0 | 0 |
| SB4 | 2–47 (S002,S005,S007,S010,S012,S015,S017,S018,S020,S047) | writing (3 workers) | A:S002/S005/S007 DONE (verified on disk; Xu-Gould-Howison Table 10 cross-checked) B:S010/S012/S015 (running) C:S017/S018/S020/S047 (running) | pending | 0 | 0 |
| SB3 | 49–94 (S049,S050,S056,S079,S081,S085,S086,S088,S091,S094) | writing (3 workers) | A:S049/S050/S056 DONE (verified on disk; 18-30% over word target, flagged) B DONE C DONE | reviewer running | 0 | 0 |

## Chatbot channels
- grok-answers.md / cursor-answers.md: async from another chat — fold when present, never block.
- duckai-answers.md: same protocol (duck.ai verified anonymous 2026-09-10).
- SB1: duckai-answers.md present (OFI deep-dive) → folding into S001. Grok SB1 COMPLETE 2026-09-10 17:46 UTC: all 3 questions asked one at a time post-login, full verbatim answers saved in SB1/grok-answers.md (Q1: CKS OFI/queue-imbalance/Stoikov microprice formulas + 10-event worked tape; Q2: M5 Max build stack — Databento MBP-1, ~80-160h, $199/mo default; Q3: after-cost verdict — no clean US-equity after-cost Sharpe for imbalance takes; quoting input, not trigger). Cursor BLOCKED 2026-09-10 16:50 UTC (no chat UI on cursor.com; /agent behind sign-in wall, no saved session; header logged in SB1/cursor-answers.md).
