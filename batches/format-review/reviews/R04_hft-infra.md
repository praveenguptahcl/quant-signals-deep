# Reviewer 04 — HFT infrastructure engineer

## CRITICAL

1. (a) Chapters are not self-contained — single-chapter builds are impossible. Ex: T001 §T2 "All quantities use the MASTER.md signal definitions"; T001 §T5 and S001 §S10 invoke "purged/embargoed validation (S088)"; S7/T5 delegate to notes/cost-model.md §2–§6. Fix: embed depended-upon definitions verbatim with version pins as an annex; zero dangling references.
2. (a) No machine-readable config surface — every parameter is prose with an `example` flag. Ex: S001 §S3 parameter table: "Default (example): *1 s bars — example, not an institutional standard*". No parameter name, type, units. Fix: §S0/§T0 config block: YAML/JSON with name, type, unit, provenance (documented|example|calibrated), value.
3. (a) No public module interface — no input/output data contract. Ex: S001 §S6 ingest sketch ends with .agg(ofi_sum=...) but no public signature stated. Fix: per chapter I/O contract, e.g. compute_ofi(events: DataFrame[ts_event:int64 ns, bid_px:float64, …]) -> DataFrame[ts:int64 ns, ofi:float64, ofi_z:float64].
4. (a) No test vectors or acceptance criteria — worked examples illustrative, not fixtures. Ex: S001 §S4 seed-42 tape gives no expected module outputs for fixed input CSV, no pass/fail. Fix: canonical input fixture CSV + expected outputs + tolerance per chapter.
5. (a) No instrument config block — "build for any ticker" un-instantiable. Ex: T001 §T2 N=⌊200/0.02⌋=10,000 shares silently assumes $0.01 tick/$0.02 stop. Fix: mandatory instrument config (tick_size, lot_size, currency, session_tz, price_scale).
6. (a) No build/test commands, repo layout, or module path. Ex: S001 §S6 db.Historical("API_KEY") with fabricated path — copy-paste code that cannot run. Fix: module path, pytest target, runnable smoke command per chapter.

## MAJOR

7. (a) Clock domain of t undefined — causality floats. Ex: T001 §T3 "on each L1 snapshot t (exchange time, causal)" but snapshot cadence never specified. Fix: per-chapter time contract (clock source, cadence, tie-break rule, t→t+1 mapping).
8. (a) No timestamp contract per chapter. Fix: required_source, max_skew, jitter_budget, mandated live/simulated-only label.
9. (a) No warmup/init spec — cold-start non-deterministic. Ex: T001 §T2 15-min EWMA baseline: no α, no initial μ/σ, no warmup length. Fix: init values, α/half-life, warmup bars/events, warmup output behavior.
10. (a) No DEGRADED/UNKNOWN output state per signal — gap handling is prose. Fix: per-signal state machine OK|STALE|UNKNOWN with transition conditions and mandated outputs.
11. (a) No latency budget decomposition per chapter. Fix: p50/p99 per-event compute budget per symbol + wire-latency line item.
12. (a) Resource budgets are external references, not per-chapter SLOs. Fix: max_symbols @ p99 latency on reference hardware, hot-RAM-per-symbol cap.
13. (a) No machine-readable regime-gating field. RB-list.md RSV schema never referenced as S/T input. Fix: regime_gates: [{regime_id, gate_type, condition}] in config block.
14. (a) Cross-chapter dependencies unversioned/unpinned. Fix: version chapters, pin consumes: [{id, version}].
15. (b) Failure-mode lists flat and unranked. Ex: T001 §T8: "Cost blowup" sits mid-list although T4 proves commissions decide the day. Fix: rank by expected P&L impact × likelihood.
16. (b) Prose rules and pseudocode duplicate thresholds — drift risk. Fix: single source of truth in §T0 config; prose/pseudocode reference parameter names only.

## MINOR

17. (b) Inline glossary repetition bloats chapters (SIP/NBBO/MBO expansions repeated). Fix: central glossary; define on first use per chapter only.
18. (b) Provenance key [D] unexplained per chapter; chatbot source logs dilute audit surface. Fix: one-line provenance legend in header; move chatbot process logs to appendix.

## Cross-cutting (keep and extend)
- t→t+1 causality discipline, [example] vs [documented] convention, "simulated only — requires MBO/ITCH" honesty labels, RB-list.md RSV schema + fail-safes F1–F5 (best machine-readable pattern in corpus, currently regime-only).
- Highest-leverage fix: a per-chapter §S0/§T0 machine block (config schema + I/O contract + test fixture pointer + build/test commands + versioned deps).
