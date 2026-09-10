# TB2 quarantine (2026-09-10, final review attempt 2/2)

T011 APPROVED (stays in batches/TB2/, merge pending the other nine).
T012–T020 FAILED, one mechanical defect class each. A targeted fix pass is authorized
(all fixes are one-line edits or cost deductions with plot re-runs — no structural issues).
On spot-review PASS they return to batches/TB2/ and merge as stages 112–120.

- T012: S1 — T10 has ZERO URLs/DOIs. Add ≥3 (e.g. Lee–Mykland 2008 doi:10.1093/rfs/hhn025; Lou–Polk–Skouras; Bernard–Thomas).
- T013: S1 — T10 has 1 identifier. Add ≥2 more (Connors/Alvarez, Kakushadze & Serur, Wilder).
- T014: H5 + S1 — deduct 0.5-tick breakout-cover slippage $5.00 on Trade 3 (net → −$111.62, book → −$57.65; update script + PNG); add 1 more URL/DOI.
- T015: S3 — T6 line 86 bare `~$0`; add `indicative — verify before budgeting` suffix (one line).
- T016: H5 — deduct $10/day MOC slippage in T4 + plot_T016.py (Day 1 → +$309.00, Day 2 → +$209.00, book → +$518.00); regenerate PNG.
- T017: H5 — deduct 1¢/share entry slippage in T4 + script (FOMC → +$235.80, CPI → +$241.88, book → +$477.68); regenerate PNG.
- T018: S3 — T6 line 109 bare `~$0`; add suffix (one line).
- T019: S1 + S3 — add 1 more URL/DOI (e.g. Moskowitz et al.); T6 line 102 bare `~$0` suffix (one line).
- T020: S1 — add 1 more URL/DOI (AFML publisher page or Bailey & López de Prado DOI).

Files: T0{12..20}.md, plot_T0{12..20}.py, T0{12..20}_example.png.
Never merge into MASTER.md under T012–T020 until spot re-review passes.
