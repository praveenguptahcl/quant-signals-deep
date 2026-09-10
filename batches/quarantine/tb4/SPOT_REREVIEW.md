# Spot re-review — TB4 quarantine trio (T035, T039, T040)

Reviewer: K (subagent, spot reviewer) | Date: 2026-09-10
Scope: verify the orchestrator's one-line fixes for the attempt-2 TB4 failures,
confirm nothing else was disturbed, confirm the other checks still pass.

Note on scope: `notes/merge-protocol.md` §4 lists **18** QC items
(H1–H6, S1–S4, C1–C4, V1–V4), not 22 — the "22" in the task brief appears to be
a stale count. All checks other than the previously-failed one were verified per
chapter below (17/chapter), and the previously-failed check now passes.

Diff evidence: `git diff 1921e90^:batches/TB4/T0XX.md 1921e90:batches/quarantine/tb4/T0XX.md`
shows exactly the specified changes (T035: −1 line; T039: ±1 line; T040: ±2 lines).
Plot scripts unchanged (0 diff); PNGs regenerated from repo root.

---

## T035 — S2 (chatbot evidence row in T7) → PASS

- Fix verified: the `| Grok Q-TB4-3 §4 (unverified lead) | futures basis timing | "Sharpe ~0.6–0.9 in futures" ...` row is deleted from the T7 evidence table. `grep -n '| Grok' T035.md` → zero matches in any evidence table.
- The claim remains preserved in **Unverified leads** (line 158), so no information was lost.
- T7 table now contains only the verified Corsi (2009) row and the explicitly "synthetic — not evidence" T4 row.
- Other 17 checks confirmed still passing: H1 (T4 labeled "(SYNTHETIC)", "All numbers synthetic" + watermark in script), H2 (net labeled "example — synthetic, not a performance claim"), H3 (`Provenance [D/SR]` present), H4 (thresholds marked `example`), H5 ($2,000 costs modeled, before/after labeled), H6 (no SIP/L1 claims), S1 (4 checkable sources; Corsi DOI + Garman & Klass JSTOR as spot-checked before), S3 (all 6 T6 vendor rows suffixed `indicative — verify before budgeting`), S4 (cites `notes/cost-model.md` §2/§3/§5), C1 (10 sections T1–T10 in order), C2 (S058, S066, S063, S088 all resolve in `notes/plan.md`), C3 (`## Stage 135/200 — T035: ...` exact format), C4 (jargon defined), V1 (PNG at `images/T035_example.png`, relative, descriptive alt text), V2 (SYNTHETIC EXAMPLE watermark in script; house-style rcParams; chart title carries "T035"), V3 (chart numbers match T4 table: entry day 3 @ 9.04, exit day 32 @ 1.73, net $5,316 — script re-run output matches), V4 (mermaid fenced, edges labeled `settlement snapshots`/`daily`).

---

## T039 — S1/S2 (T10 DOI resolved to the wrong paper) → PASS

- Fix verified: T10 entry 5 (line 156) now cites `doi:10.1111/j.1540-6261.1991.tb02683.x`.
- **Crossref check performed live (not trusting the string):** `api.crossref.org/works/10.1111/j.1540-6261.1991.tb02683.x` returns title **"Inferring Trade Direction from Intraday Data"**, authors LEE/READY, *The Journal of Finance* 46(2), 733–746. The DOI now resolves to exactly the cited paper.
- Old DOI `tb03746.x` appears nowhere in the file.
- Other 17 checks confirmed still passing: H1 ("All prices synthetic, seed 139" + watermark), H2 ("the example is arithmetic, not a backtest... makes no performance claim"), H3 (`Provenance [D/SR]`), H4 (thresholds `example`), H5 (5 bp + $0.75/contract costs, before/after labeled), H6 (SIP/L1 carries `simulated only — requires MBO/ITCH`), S1 (6 checkable sources; Lettau DOI + Hasbrouck JSTOR 2329487 spot-checked), S3 (all T6 vendor rows suffixed), S4 (cost-model §2/§3/§4/§5 cited), C1 (10 sections in order), C2 (S056, S094, S032, S088, T009 all resolve in plan.md), C3 (`## Stage 139/200 — T039: ...`), C4 (jargon defined), V1 (PNG exists, relative, descriptive alt), V2 (watermark; title carries "T039"), V3 (T1 net +132.42, T2 +115.47, total −146.81 match script re-run; chapter text prints −146.80 — the $0.01 rounding artifact already noted as a non-failing nit in the rereview), V4 (mermaid fenced, edges labeled "1-min snapshots").

---

## T040 — S2 (unverified "1.44 → 0.9" presented as documented fact) → PASS

- Fix verified: T7 "Documented decay" prose (line 117) now reads "in-paper Sharpe 1.44 after costs (Avellaneda–Lee); post-2007 replications lower; ..." — the undocumented "→ 0.9 already inside the original sample" figure is **removed** from the documented claim; the only documented magnitude is the in-paper 1.44 after-cost figure.
- The 0.9 figure now lives **only** in Unverified leads (line 158), explicitly labeled as the sub-period figure "cited in an earlier draft," magnitudes "not independently verified".
- T7 evidence table contains no Grok/chatbot rows (Avellaneda & Lee row asserts only documented results with the disclosure caveat).
- Other 17 checks confirmed still passing: H1 ("All prices synthetic, seed 140" + watermark), H2 ("not a backtest, and no performance claim is made"), H3 (`Provenance [D/SR]`), H4 (thresholds `example`), H5 (5 bp costs; borrow stubbed at 0 and flagged in optimism paragraph), H6 (no SIP/L1 claims), S1 (4 checkable sources; Avellaneda & Lee DOI 10.1080/14697680903124632 + Engle & Granger DOI spot-checked before), S3 (all T6 vendor rows suffixed), S4 (cost-model §2/§3/§4/§5 cited), C1 (10 sections in order), C2 (S080, S039, S078, S088 all resolve in plan.md), C3 (`## Stage 140/200 — T040: ...`), C4 (jargon defined), V1 (PNG exists, relative, descriptive alt), V2 (watermark; title carries "T040"), V3 (T1 +1,221.60, T2 +480.22, T3 −899.80, total +802.02 — script re-run output matches chapter text exactly), V4 (mermaid fenced, edges labeled "daily bars").

---

## Plot re-runs (from repo root, per merge-protocol §3 step 3)

All three scripts ran clean and wrote to `images/`:

| Chapter | Script output (key numbers) | Matches T4 table |
|---|---|---|
| T035 | entry day 3 @ 9.04, exit day 32 @ 1.73, gross $7,316, costs $2,000, net $5,316 (seed 135) | yes |
| T039 | T1 net +132.42, T2 net +115.47, T3 net −394.69, total −146.81 (seed 139) | yes (−146.80 in text = $0.01 rounding nit, pre-existing) |
| T040 | T1 +1,221.60, T2 +480.22, T3 −899.80, total +802.02 (seed 140) | yes, exact |

PNGs regenerated: `images/T035_example.png`, `images/T039_example.png`, `images/T040_example.png` (untracked new files at repo root — placed where the merger expects them). Nothing numeric changed (plot scripts have zero diff vs pre-quarantine), so no table updates were needed.

## Structure integrity (fix non-disturbance)

- `## Stage 135/200`, `## Stage 139/200`, `## Stage 140/200` headings byte-intact.
- Each file: exactly 10 sections `### T1`–`### T10`, in order, with original titles.
- `git diff` between pre-fix (`1921e90^:batches/TB4/T0XX.md`) and post-fix (`1921e90:batches/quarantine/tb4/T0XX.md`) confirms **only** the specified fixes: T035 −1 line, T039 ±1 line, T040 ±2 lines. No other line touched.

---

## VERDICT

**T035: PASS · T039: PASS · T040: PASS — all three are clear to be moved back and merged.**
