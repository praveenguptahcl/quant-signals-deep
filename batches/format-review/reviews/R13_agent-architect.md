# Reviewer 13 — AI-agent systems architect (read S001, T001 cover to cover; RB-list ~976 lines)

## CRITICAL

1. (a) S001 §S6 ingest sketch has literal `...` ellipses in the two load-bearing lines: `.with_columns(pb_l=pl.col("pb").shift(1), ...)` and `.with_columns(ofi=pl.when(...).then(...))`. Core deliverable (CKS piecewise ask-side sign convention) is a placeholder; §S9 warns sign errors are the #1 real-world failure. Fix: replace ellipses with actual piecewise expressions from §S3, or label "structure only — do not run."
2. (a) Example-vs-constant marking inconsistent within T001. Backticked `example` on some thresholds ("3 ticks (example)", "R = $200 (example)") but bare on structurally identical numbers (kill-switch "heartbeat missed > 2 s" unmarked in T2, marked in T5; "clock skew > 50 ms vs NTP"; "heartbeat watchdog every 1–2 s"). Worked arithmetic N=⌊200/0.02⌋ presented as fact though both inputs are examples. Fix: every numeric literal carries `example` or `fixed`; audit per chapter.

## MAJOR

3. (a) T001 §T2 uses G*(X_t) — undefined in chapter. "bin lookup G*(X_t), fit on history strictly before today" — no formula, bin spec, feature list. Fix: one-line recap or pointer into T3 combination table.
4. (a) Bare cross-chapter refs with no recap. Ex: S001 §S10 "purged/embargoed validation (S088)"; S001 §S2 forward-ref "S003/S005 territory" before S003 introduced; T001 §T8 "prefer the maker variant (T022)". Fix: every cross-ref gets one-line recap: "S088 — purged/embargoed validation (walk-forward with embargo gaps)".
5. (b) "CCZ 2023" unexpanded author-initial citation (S001 §S3: "edge decays (CCZ 2023: rapid decay)"). Fix: cite as "(Cont–Cucuringu–Zhang 2023, Sources #2)".
6. (b) Acronyms/jargon undefined in-chapter. T001: RTH, ADV ("1% of trailing 1-minute ADV" — self-contradictory), large-tick; S001+T001: ITCH (MBO defined, ITCH not); RB-list R040: MOC undefined. Fix: acronym-at-first-use rule per chapter.
7. (a) Tagging convention mismatches Part III spec. RB-list mandates [example]/[documented] square brackets; S001/T001 use backticked (`example`). Fix: one convention for all 250 chapters.
8. (b) `example` convention and provenance tiers never defined anywhere. Header "Provenance [D]" has no legend; S001 body redefines [D] as its own citation, conflating tier label with citation. Fix: one-line legend per chapter or compendium front-matter: what `example` means, what the provenance scale is.
9. (a) T001 pseudocode and prose disagree on triggers. Code defines microprice(state_t), mid_jump_5s — neither defined; exit prose "crosses through 0" vs code `z < 0` (cross vs level); prose "8 seconds (or 8 events)" vs code `age > 8 s`. Fix: define every helper before sketch; prose and code use identical trigger definitions.
10. (b) S001 ask-side formula needs sign-rationale, not just "(note the minus sign)". Fix: one sentence — "ask side is negated because ask size is supply" — plus pointer §S3 → §S4 hand-checks.
11. (a) No machine-checkable verification hook in S/T chapters. RB-list's Sentinel/Verifier/Adversary/Gate loop spec is executable; S001/T001 have nothing equivalent. Fix: per-chapter verification hook (fixed input → expected output) mirroring R-loop pattern; §S4/T4 worked examples are 90% of it.

## MINOR

12. (b) Inconsistent cross-document citation style (S001 §S6 "notes/cost-model.md §4" vs §S7 "§2", "plan §6"). Fix: always full path.
13. (b) Internal taxonomy never decoded in-chapter (SB1, Family A, "Signal 1/100"). Fix: one-line key in compendium front-matter.
14. (a) T001 depth-baseline vs S001 depth normalizer conflation risk (15-min EWMA of OFI vs 5-min rolling mean D_k). Fix: T001 states "EWMA of OFI (not the depth normalizer D_k of S001)".
15. (a) T001 §T4 worked example doesn't demonstrate its own exit logic (trade 4 exits on "signal flip" but no exit-time z/I values). Fix: add exit-time signal values per trade.

## Pattern note
Honesty labeling strong. Failures are almost all interface failures: runnable code, defined terms, one tagging convention, a stated verification target missing in the first 60 seconds. Highest-leverage: per-chapter machine-verifiable worked example + example/fixed literal audit.
