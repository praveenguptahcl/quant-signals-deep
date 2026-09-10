# Reviewer 01 — Risk manager (read S001 full; T001, T002 full; S002 skim; T003/T050 spot; RB-list fail-safes + R001–R042)

## FORMAT CORRECTION (meta)
Strategy chapters are T1–T10, not T1–T12 (zero T11/T12 sections in 36,207 lines).

## CRITICAL

1. (a) No machine-readable risk contract per strategy chapter. Ex: T001 §T2 "Risk limits. Daily loss stop −$2,000 (example), then dark for the day; max gross $1M notional (example)..." is free prose. Fix: fenced YAML `RISK CONTRACT` block — per_trade_R, daily_loss_stop, max_gross, kill_conditions[], enforcement.
2. (a) No position-state schema anywhere (0 mentions). Ex: T001 §T5 "paper ledger is source of truth" — ledger schema never defined. Fix: one canonical PositionState JSON schema; each T chapter references it.
3. (a) Kill switches are prose conditions, not checkable states. Ex: T001 §T2 "Kill-switch: heartbeat missed > 2 s, book sequence gap, clock skew > 50 ms vs NTP... flatten immediately" — no ARMED/TRIPPED/RECOVERY states, no re-arm procedure; 55/100 T chapters lack "Feed-outage safe mode" entirely. Fix: mandatory kill-switch state machine — trigger conditions → TRIPPED actions → re-arm checklist.
4. (a) Signal chapters specify no degradation behavior on stale input. The token UNKNOWN appears 0× in 36,207 lines (RB-list F1–F5 mandates UNKNOWN → restrictive downstream). "Never interpolate OFI across a gap" lives in T001 §T5, not S001. Fix: per-signal degradation contract — stale input → emit UNKNOWN; downstream restricts.
5. (a) No worst-case per-trade loss bound. Ex: T001 §T2 stop −2 ticks, R=$200; but §T4 trade 3 nets −$300 (1.5×R after commissions). Fix: require max_adverse_per_trade row (stop + costs + slippage assumption) in risk contract.

## MAJOR

6. (b) Risk buried in §T2 prose; §T1 verdict table has no risk row. Fix: add "Risk summary" rows to §T1 (per-trade R, daily stop, kill triggers).
7. (b) "Risk limits" prose non-uniform — same label, different enforcement. Ex: one chapter "daily loss stop −$800 … enforced ex post as a next-day review trigger, not an intraday [stop]" vs T001 intraday dark; denominators vary ($/%NAV/%sleeve); 9 chapters lack Risk limits entirely (T041, T044–T047, T055–T057, T081). Fix: fixed field list + mandatory enforcement tag (intraday-hard vs review-only).
8. (a/b) Regime fail-safe architecture disconnected from every S/T chapter. 0 references to RSV/RB-list/regime-gating in any S/T chapter. Fix: "Regime gates" field per chapter — R-IDs + RSV fields consumed.
9. (b) Cost model split across sections and occasionally missing. Ex: T050 §T2 "Chain-data cost sits in T6, not in per-trade P&L"; 4 chapters (T044–T047) lack Cost model subsection. Fix: one mandatory cost-model block per chapter adjacent to sizing.
10. (a) No portfolio-aggregation spec — 100 independent sleeves, no book-level interface. Fix: per-chapter "portfolio interface" note (sleeve NAV fraction, stop-correlation assumption, book-level stop).
11. (b) Honest after-cost verdict discoverable only deep in §T7. Fix: copy one-sentence honest verdict + after-cost status into §T1.
12. (a) Signal chapters lack a module output contract. Fix: "Module output contract" per S chapter — output schema, units, freshness SLA, stale behavior.
13. (a) Re-arm/recovery criteria inconsistent or absent. Fix: mandatory re-arm checklist inside safe-mode block.

## MINOR

14. (b) Risk/cost/safe-mode are bolded sub-subsections inside §T2/§T5, not numbered sections. Fix: promote to numbered sections or mandatory appendix block.
15. (b) Heading inconsistency breaks grep-based review. Ex: T001 "**Risk limits.**" vs T050 "**Risk limits** (*examples*)." Fix: one canonical heading string.
16. (a) Every numeric threshold `example`-tagged with no calibration recipe pointer. Fix: "calibration recipe" line in risk contract (data window, objective metric, shrinkage rule).
