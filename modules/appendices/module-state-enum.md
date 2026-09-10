---
appendix: module-state-enum
appendix_version: 1.0.0
title: Module-state enum (canonical vocabulary)
scope: global — the single canonical state vocabulary for all modules
---

# Appendix K — Module-state enum (canonical vocabulary)

This is the **single canonical vocabulary** for module state across all 250
modules. No chapter may introduce alternative state names
(`UNTRUSTED_FLAT`, `STALE`, `PAUSED`, etc. all map to one of these four).

| State | Code | Meaning | Output policy |
|---|---|---|---|
| OK | `OK` | inputs fresh, all guards pass, estimators agree | emit normally |
| DEGRADED | `DEGRADED` | partial data or elevated risk; usable with the restrictions declared in §S0/§T0 | emit with restrictions; alert |
| UNKNOWN | `UNKNOWN` | inputs missing/stale/invalid, bounds violated (F2), estimators disagree (F3), staleness timeout (F4), or any unmapped failure | do not trust output; downstream treats as restrictive (reduce size / widen stops / stand down); alert |
| OFF | `OFF` | administratively disabled: kill-switch TRIPPED, compliance halt, or manual disable | emit nothing |

## Rules

- **Exactly four states.** Sub-states are documented as structured annotations
  on the record (e.g. `UNKNOWN(reason=staleness)`), never as new state names.
- **Invalid input → `UNKNOWN`, never interpolate** (F1, appendix f).
- **`UNKNOWN` is restrictive, never benign** (F1): a consumer may not treat an
  `UNKNOWN` record as "no signal, carry on"; it must reduce risk or stand down.
- State transitions are logged in the decision log (appendix g), including the
  reason code and the guard that fired.
- Kill-switch mapping (T-modules): `ARMED` ≈ module enabled (`OK`/`DEGRADED`
  as computed); `TRIPPED` → `OFF`; `RECOVERY` → `DEGRADED` until the re-arm
  checklist passes → back to computed state.
- R-module mapping: regime states themselves are data, not module-state; the
  *module* reporting them still uses only these four states.
