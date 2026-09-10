---
appendix: f1-f5-failsafes
appendix_version: 1.0.0
title: Universal fail-safes F1–F5 and module-state enum
scope: global — ported into every chapter (RB-list §31, verbatim below)
---

# Appendix F — Universal fail-safes F1–F5

Verbatim from `batches/RB-list.md` §31 ("Universal fail-safes (apply to every
regime)"):

- **F1.** Missing or stale input → state `UNKNOWN`; downstream signals treat
  `UNKNOWN` as *restrictive* (reduce size / widen stops), never as benign.
- **F2.** Every indicator value must satisfy its mathematical bounds
  (e.g. VPIN ∈ [0,1], HHI ∈ (0,1]); out-of-bounds → `UNKNOWN` + alert.
- **F3.** Dual-estimator agreement: Sentinel and Verifier must agree within the
  stated tolerance or the state is `UNKNOWN`.
- **F4.** Staleness timeout: if `computed_at` is older than 3× the cadence, the
  state expires to `UNKNOWN`.
- **F5.** No regime label may be used to *select* backtest periods ex post
  without a pre-registered definition (Adversary checks for regime-mining).

## Module-state enum

Single canonical vocabulary (see also appendix k):

| State | Meaning |
|---|---|
| `OK` | inputs fresh, all guards pass |
| `DEGRADED` | partial data or elevated risk; output usable with restrictions declared in §S0/§T0 |
| `UNKNOWN` | inputs missing/stale/invalid, bounds violated, estimators disagree, or staleness timeout — output must not be trusted; downstream treats as restrictive |
| `OFF` | module administratively disabled (kill-switch TRIP, compliance halt) |

## Hard rules

- **Invalid input → `UNKNOWN`, never interpolate.** Missing fields, out-of-range
  values, crossed/locked quotes reaching the module, or failed bounds checks
  produce `UNKNOWN`, never a best-guess fill-in.
- `UNKNOWN` propagates: any consumer receiving an `UNKNOWN` record must treat
  it restrictively (reduce size, widen stops, or stand down) — never as benign.
- Every chapter's `§S0/§T0` error taxonomy maps each documented failure mode to
  one of the four states; unmapped failures default to `UNKNOWN` + alert.
