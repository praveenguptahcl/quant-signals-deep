# Module build status — 250 standalone module files

Target: modules/signals/S001–S100 · modules/strategies/T001–T100 · modules/regimes/R001–R050
Spec: MODULE_FORMAT_PROPOSAL.md v1.0.0 · template: notes/module-template.md v1.0.0

| Batch | Writers | Modules | Status |
|---|---|---|---|

| R026–R050 (regimes) | writer 7388cf41 | 25 | DONE 2026-09-10 · 25 md + 50 csv + 25 test · 200/200 tests pass · R050 THIN (capability-gated, permanently UNKNOWN) |

| S002–S026 (signals) | writer 560f1651 | 25 | DONE 2026-09-10 · 25 md + 50 csv + 25 test · 150/150 tests pass · THIN: S015, S016, S017, S026 (fixture-minimal, formulas/tests complete) |

| T051–T075 (strategies) | writer bba5f5c7 | 25 | DONE 2026-09-10 · 25 md + 50 csv + 25 test · 150/150 tests pass · THIN: T058 (fixture shows entry only, no exit; rules documented) |

| (partial, in b7b326a) T050 + T076–T079 fixtures/tests | — | 5 | landed via glob sweep; module .md files pending from their writers |

| R001–R025 (regimes) | writer 8b811b51 | 25 | DONE 2026-09-10 · 25 md + 50 csv + 25 test · 225/225 tests pass · no THIN · 6 prose↔fixture mismatches fixed in audit |

| S077–S088 (signals) | writer 615e2fa8 | 12 | DONE 2026-09-10 · 12 md + 24 csv + 12 test · 72/72 tests pass · note: S083–S085 §S11 mermaid diagrams render single-char (fix queued); S089–S100 re-dispatched |

| T076–T100 (strategies) | writer 869e8d5d | 25 | DONE 2026-09-10 · 25 md (+ fixtures/tests landed earlier) · 151/151 tests pass · no THIN · ~100 numeric-tag violations fixed in audit |
