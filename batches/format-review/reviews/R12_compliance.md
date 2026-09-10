# Reviewer 12 — Compliance / surveillance officer (read S003, T001, T059, T002 full; skimmed S091–S094, T003, T030, T075, RB-list.md; chapter template; merge-protocol.md)

Headline: 12-section signal / 10-section strategy format is strong on causality (t→t+1) and [example]-tag honesty, but regulatory/compliance is not a first-class section anywhere. 0/200 chapters and the template contain any compliance section; merge-protocol.md has zero compliance/manipulation/audit QC items. An AI agent implementing any chapter literally would produce a module with no coded market-manipulation guardrails, no audit spec, no license-enforcement checks.

## CRITICAL (a)

1. No compliance section exists in either chapter format. Ex: T001 T2 "Risk limits" has loss stop and kill switch but nothing on Reg NMS / order-handling / exchange rules. Fix: mandatory "T11/S13 — Regulatory & venue-compliance contract" with coded rules.
2. Spoofing/layering framed as others' data noise, never as constraint on the module's own quoting behavior. Ex: S003 §S10.1 "Spoofing / fleeting quotes — mitigation: weight by quote lifetime (example)"; T022-style post/cancel maker with no bona-fide-intent guard. Fix: every chapter posting passive orders states a coded bona-fide-intent rule (min quote life, cancel-to-trade ceiling) in combination pseudocode.
3. No self-trade / wash-trade prevention rule anywhere in 36,207 lines. "wash trad" once (T075, as others' noise); "self-trade"/"self-match": 0 hits. Fix: mandate stp_flag + pre-trade self-match check on every order path in pseudocode.
4. No per-module audit/logging spec. Ex: T030 §T5 "log every veto" — prose, no schema, no required fields, no immutability, no retention. Fix: mandatory decision-log schema (event, order_id, ack_id, NBBO snapshot, rule_id fired, append-only store, retention) enforced by template.
5. Data-entitlement/licensing limits are buy-vs-build prose, never machine-enforceable checks. Ex: S003 §S8 tier table prices; T059 ingests licensed news wire with zero redistribution gate. Fix: S6/T5 list each feed's license terms as enforceable assertions (entitlement key present, redistribution allowed/denied, display-only flag) gating module at startup.
6. Halt/auction/market-close behavior is "exclude and mask" backtest hygiene, not a runtime state machine. Ex: S003 §S6 "exclude auction prints and halt periods"; no mid-position halt → state spec; T059 RTH 9:30–16:00 with no auction statement. Fix: per-chapter state table (CONTINUOUS_TRADING / HALTED / AUCTION / CLOSED) with allowed action in each.

## MAJOR

7. No order-to-trade / messaging-ratio guardrails as coded rules. Ex: T001 8-event exits on 10k-share children; T003 cancel-persistence rules — high cancel velocity by design. Fix: per-venue message-rate ceiling + cancel-to-trade guard as coded rules in T2.
8. No short-sale / locate / Reg-SHO constraint on short legs. Ex: T059 shorts on negative sentiment with POV cap only. Fix: locate/availability assertion in every chapter with a short leg.
9. News-chapter ingestion has no MNPI / public-dissemination gate. Ex: T059 §T2 "intraday-news latency caveat" on timestamp accuracy but nothing classifying public-dissemination status. Fix: public-dissemination assertion (story must match public wire print with timestamp ≤ t₀) before arming.
10. RB-list 5-agent loop with F1–F5 has no analogue in strategy chapters. T001 kill switch is prose, not coded fail-safe with states. Fix: port F1–F5 as mandatory "T5 fail-safe contract" per strategy chapter.
11. Combination pseudocode is not the single source of truth — prose guards don't appear in the code block. Ex: T001 §T3 omits "mid has not jumped > 1 tick in 5 s" guard and participation-cap veto stated in T2 prose. Fix: pseudocode complete (every prose guard present); "pseudocode is normative; prose is commentary."
12. Spoofing mitigations tagged (example), indistinguishable from firm spec, no calibration procedure. Fix: separate normative guardrails (no example tag) from illustrative parameters; require calibration procedure per guardrail.

## MINOR

13. Provenance tags ([D]/[SR]/lead) have no in-file legend. Fix: one-paragraph legend at top of MASTER.md.
14. Exit rules can instantly re-arm with no whipsaw bound. Ex: T059 opposite-headline flip with no cooldown. Fix: post-exit cooldown or max-flips-per-window parameter in every exit rule.
15. Pre-trade fat-finger checks implied by caps, never stated as pre-trade controls. Fix: 3-line pre-trade check (price collar, notional ceiling, duplicate-order window) in pseudocode standard.

## What's already good (don't break)
Causal-timing discipline (t→t+1, exchange timestamps) — extend same rigor to halt states, audit fields, entitlement gates. Keep [example] tagging; keep out of load-bearing guardrails (#12). RB-list.md's Sentinel/Verifier/Adversary/Gate + F1–F5 is the right architecture — port to strategy modules (#10).
