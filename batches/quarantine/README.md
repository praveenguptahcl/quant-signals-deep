# Quarantine log

## SB1 first-review failures — 2026-09-10 (attempt 1/2, in active rework)
Files retained in batches/SB1/ during rework (not moved) — visible here instead of silent.
- S001 — FAILED C4, V4 (undefined jargon: L1, NBBO, SIP, TAQ, MBO, bps; mermaid edge lacking granularity). Action: rework worker R2.
- S003 — FAILED V4 (2 mermaid edges lack granularity). Action: rework worker R2.
- S004 — FAILED H3 (substantive: formula presented as Stoikov microprice is ordinary cross-weighted mid; Stoikov's estimator is the learned state-transition model), S1 (source 3 lacks title/authors), V4. Action: rework worker R1.
- S006 — FAILED V4 (3 mermaid edges unlabeled). Action: rework worker R2.
- S008 — FAILED H3 (substantive: BVC applied trade-by-trade vs ELO bar-level; "equal-volume" buckets 385–697 shares contradict stated n·V), V4. Action: rework worker R1.
- S014 — FAILED H5/S2 (substantive: realized spread and price impact swapped throughout), V4. Action: rework worker R1.
- S024 — FAILED H5 (substantive: lookahead contradiction — S3 N-bar hold vs S4 "earliest honest fill"), V4. Action: rework worker R1.
- S025 — FAILED C4 (9 undefined jargon terms), V4. Action: rework worker R2.
- S035 — FAILED V4 (2 edges). Action: rework worker R2.
- S040 — FAILED V4 (1 edge). Action: rework worker R2.
Batch-wide systemic: V4 mermaid edge granularity — template guidance strengthened for SB4+ briefs and sent to in-flight SB2/SB3 workers.

## SB1 re-review — 2026-09-10 (attempt 1/2)
SB1 re-review 2026-09-10: S001 APPROVED (attempt 1/2)
SB1 re-review 2026-09-10: S003 APPROVED (attempt 1/2)
SB1 re-review 2026-09-10: S004 APPROVED (attempt 1/2)
SB1 re-review 2026-09-10: S006 APPROVED (attempt 1/2)
SB1 re-review 2026-09-10: S008 APPROVED (attempt 1/2)
SB1 re-review 2026-09-10: S014 FAILED S2,V3 (attempt 1/2)
SB1 re-review 2026-09-10: S024 APPROVED (attempt 1/2)
SB1 re-review 2026-09-10: S025 APPROVED (attempt 1/2)
SB1 re-review 2026-09-10: S035 APPROVED (attempt 1/2)
SB1 re-review 2026-09-10: S040 APPROVED (attempt 1/2)

## SB3 first review — 2026-09-10 (attempt 1/2)
SB3 first review 2026-09-10: S049 FAILED H5,C4,V4 (attempt 1/2)
SB3 first review 2026-09-10: S050 FAILED H5,V4,S4-table-duplication (attempt 1/2)
SB3 first review 2026-09-10: S056 FAILED S1,H5,V4 (attempt 1/2)
SB3 first review 2026-09-10: S079 FAILED C4 (attempt 1/2)
SB3 first review 2026-09-10: S081 FAILED S2,C4,multivariate-stability-formula (attempt 1/2)
SB3 first review 2026-09-10: S085 FAILED S1,S2,S3,H5,C4,V4,label-0-contradiction (attempt 1/2)
SB3 first review 2026-09-10: S086 FAILED S2,H5,C4,V4 (attempt 1/2)
SB3 first review 2026-09-10: S088 FAILED S2,C4,V4,ingest-code-bugs,S9-markdown (attempt 1/2)
SB3 first review 2026-09-10: S091 FAILED S2,V4 (attempt 1/2)
SB3 first review 2026-09-10: S094 FAILED S2,H5,C4,V4,lee-ready-lag-code (attempt 1/2)
Batch-wide systemic: V4 mermaid edge granularity (8/10 chapters fail — only S079/S081 label all data edges); C4 undefined acronyms (7/10); H5 explicit spread+fees+impact/slippage cost model (7/10); chatbot material in S9 evidence tables/bodies (S085/S086/S088/S091).
SB5 first review 2026-09-10: S022 FAILED C4,C5 (attempt 1/2)
SB5 first review 2026-09-10: S023 FAILED C4,C5 (attempt 1/2)
SB5 first review 2026-09-10: S026 FAILED C4,C5,S6-sketch-bug (attempt 1/2)
SB5 first review 2026-09-10: S028 FAILED C4,C5,V4 (attempt 1/2)
SB5 first review 2026-09-10: S029 FAILED C4,C5,V4 (attempt 1/2)
SB5 first review 2026-09-10: S030 FAILED C4,V4 (attempt 1/2)
SB5 first review 2026-09-10: S031 FAILED C4,C5,S5,S6-sketch-bug (attempt 1/2)
SB5 first review 2026-09-10: S033 FAILED C4,V3,V4,F2 (attempt 1/2)
SB5 first review 2026-09-10: S044 FAILED C4,S4,V3,S2,F2 (attempt 1/2)
SB5 first review 2026-09-10: S045 FAILED C4,F2 (attempt 1/2)
Batch-wide systemic: C4 undefined acronyms on first use (10/10 chapters fail — RVOL/RTH/L1/L2/TAQ/MBO/ITCH/OPRA/LSTM/HMM/MOC/LOC/SIP/ATR/EMA/SMA/VWAP/bps/ADX); C5 second T-ref not a plan-defined consumer (S022/T005, S023/T012, S026/T006, S028+S029/T003, S031 only T062); V4 gate-edge granularity (S028/S029/S030 GATE→OUT labels, S033 ING→FEAT); substantive worked-example defects in S033 (P&L anchored at wrong price), S044 (%R arithmetic + invalid OHLC + no bar-18 adverse move), S045 (volume-gate logic contradiction); polars sketch bugs in S026 (bucket-1 lag) and S031 (self-referencing streak).

## SB7 first review — 2026-09-10 (attempt 1/2)
SB7 first review 2026-09-10: S051 FAILED H5,S2,C1,C4 (attempt 1/2)
SB7 first review 2026-09-10: S052 FAILED H5,S2,C2,C4 (attempt 1/2)
SB7 first review 2026-09-10: S053 FAILED S1,C4 (attempt 1/2)
SB7 first review 2026-09-10: S054 FAILED S1,S2,C2,C4,V4 (attempt 1/2)
SB7 first review 2026-09-10: S055 FAILED H5,S1,S2,C2,C4,V3,V4 (attempt 1/2)
SB7 first review 2026-09-10: S057 FAILED H5,S1,S2,C4,V4 (attempt 1/2)
SB7 first review 2026-09-10: S058 FAILED H5,S1,S2,C2,C4,V4 (attempt 1/2)
SB7 first review 2026-09-10: S061 FAILED S1,S2,C4,V4 (attempt 1/2)
SB7 first review 2026-09-10: S062 FAILED H5,S1,C2,C4,V4 (attempt 1/2)
SB7 first review 2026-09-10: S090 FAILED H3,S1,S2,C3,C4,V3,V4 (attempt 1/2)
Batch-wide systemic: S1 source count — 8/10 chapters carry <6 sources (only S051/S052 meet the ≥6 template minimum); S2 chatbot claims inside S9 evidence tables (S051/S052/S054/S057/S058/S061/S090); C4 undefined jargon on first use (10/10 fail — OLS/MLE/HTB/ETF/SIC/CRSP/SIP/TAQ/L1/L2/VWAP/RTH/OI/FX/DTE/SOFR/PV/M1-M12/pin-risk among others); V4 data-edge granularity (7/10 fail — unlabeled FEED→ING / SIG→GATE in S061/S062/S090, granularity-free content labels in S054/S055/S057/S058); C2 invalid T cross-references vs notes/plan.md Signals columns (S052→T007, S054→T100, S055→T007, S058→T100, S062→T088); H5 strict spread+fees+impact/slippage stack incomplete (S051/S052/S055/S057/S058/S062); missing exact source-log sentence in S054/S055/S057/S058; substantive worked-example defects — S055 Johansen stats not reproduced by stated recipe (56.61/35.19, 7.63/20.26 vs recomputed 55.67/35.01, 7.51/18.40) + day-88 breach mislabeled day-87; S057 double-counted carry in the 4.00%→0.10% stack; S090 k=4 VR/Hurst values false (0.5667/0.295 vs correct 0.8000/0.4195) with false "verified unchanged" claim + "Signal 90/200" header; S061 wrong Gagnon–Karolyi paper title (published title: "Multi-market trading and arbitrage," JFE 97(1):53–80); S061 example entry threshold 1.5 contradicts S3 default 2.0; S051 malformed S3 parameter table (no header/separator).
