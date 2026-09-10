# Reviewer 19 — Low-latency C++ developer

## CRITICAL

1. (a) No per-chapter COMPUTE contract. Ex: T001 §T5 prose "Python loop ~100–500k events/sec"; no per-event ns budget, state size in bytes, allocation policy. Fix: fixed 5-row table per chapter: per_event_ns_budget, state_bytes, alloc (none-in-hot-path), worst_case_events_per_sec, precision.
2. (a) Algorithms specified as vectorized batch pseudocode, not streaming state machines. Ex: S001 §S6 polars sketch — batch, sorts whole day; tick-driven builder must reverse-engineer a state machine. Fix: named state vector + explicit on_event(e) transition spec with initial/reset conditions.
3. (a) Event-ordering, clock, out-of-order assumptions implicit. Ex: S001 §S6 "sort ts_event"; T001 §T2 "at each L1 snapshot t". Fix: "Event contract" block — ordering guarantee, staleness bound, gap/duplicate/out-of-order handling.
4. (a) Numerical precision unspecified — float vs fixed-point open. Ex: S001 §S6 "float / int"; §S3 prices in dollars. Fix: declare price_repr (int64 cents/ticks), quantities (int64 shares), stats (double), exact scaling rules.
5. (a) No overflow/degenerate-input rules. Ex: I_t = (qb−qa)/(qb+qa) — div-by-zero on empty book; z with σ=0; cumulative OFI int64 overflow unstated. Fix: per formula — divide-by-zero → value, init/warmup values, counter width + saturation vs wrap.

## MAJOR

6. (a) Processing model contradictory within a chapter. Ex: T001 §T2 "at each L1 snapshot t" (event-driven) vs §T9 mermaid "1-s event bars" (bar-driven). Fix: one line per chapter — processing_model: per_event | per_bar(period) | per_snapshot — enforced by merge QC.
7. (a) Every threshold `example` with no calibration recipe. Fix: per-chapter "Parameter calibration" block — objective function, calibration cadence, frozen vs fitted.
8. (a) No state lifecycle / warmup / reset spec. Fix: warmup (events/time), warmup_output (emit|hold), reset_triggers in the compute contract.
9. (b) Key causal rules buried mid-section in prose. Ex: S001 §S3 "Causal timing" sentence sits after the parameter table, 3 paragraphs into math. Fix: fixed "Causality" row at top of every math/mechanics section.
10. (b) Cross-chapter dependency specs unversioned. Fix: pin consumes: S001@<merge-date|git-sha> or spec-hash.
11. (b) Sources section buries 3 real citations under chatbot logs. Fix: move chatbot logs + unverified leads to appendix file; §S12/T10 = verified sources only.
12. (b) §S7/T5 mixes M5 Max research notes with live-path requirements. Fix: split "Live pipeline (required)" vs "Research feasibility (informational)".

## MINOR

13. (b) Acronyms re-defined inline repeatedly (SIP ×3 etc.). Fix: document-level glossary; chapters use bare acronyms.
14. (b) Math and parameter table fused in one section. Fix: split §S3 into S3a Formula (frozen) + S3b Parameters & defaults (calibrated).
15. (a) Kill-switch rules live in §T5 prose, not in the entry/exit rule table. Fix: merge safe-mode transitions into the same rule table as entry/exit, marked priority: override.

## Bottom line for parent
Research-document format, not build-contract format. Fix issues 1–5 before trusting any "automated multi-agent implementation loop". No browser work needed.
