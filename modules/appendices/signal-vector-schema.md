---
appendix: signal-vector-schema
appendix_version: 1.0.0
title: SignalVector schema
scope: global — every S-module's §S0 contract; the single canonical signal output
---

# Appendix B — SignalVector schema

Every S-module emits **only** `SignalVector` records. T-modules consume them.
No other signal output shape is permitted.

```python
@dataclass(frozen=True)
class SignalVector:
    symbol: str        # canonical ticker, exchange-qualified
    direction: int     # +1 long / -1 short / 0 flat — nothing else
    confidence: float  # 0.0 .. 1.0, calibrated as documented in the chapter
    capital: float     # 0.0 .. 1.0, fraction of strategy risk budget requested
    computed_at: int   # int64 ns UTC — the event_ts of the newest input used
    staleness: int     # int64 ns — asof_now - computed_at at emission time
    module_state: str  # OK | DEGRADED | UNKNOWN | OFF (see appendix k)
```

## Field contracts

- `direction ∈ {+1, -1, 0}`. No continuous "score" emission; continuous scores
  are internal features, not outputs.
- `confidence ∈ [0, 1]`. Document how it is calibrated in §S3 (e.g. historical
  hit-rate mapping, logistic fit, `[documented]`/​`[example]` tagged). A confidence
  of `0.0` with `direction 0` is the canonical "no opinion" record.
- `capital ∈ [0, 1]`. Fraction of the *strategy's* per-module risk budget
  requested. `0.0` = "take no position". S-modules never set absolute share
  counts, notionals, or prices — sizing beyond `capital` is the strategy's job.
- `computed_at` = the `event_ts` of the newest input event consumed. The
  t→t+1 causality assertion uses `computed_at`: a fill event must satisfy
  `fill.event_ts > signal.computed_at` (see appendix e).
- `staleness` is informational; consumers apply their own TTL. If `staleness`
  exceeds the module's `staleness_ttl`, the consumer must treat the record as
  expired — the module itself expires to `UNKNOWN` (F4).
- `module_state`: S-modules emit `UNKNOWN` when inputs are missing/invalid
  (F1–F4); consumers treat `UNKNOWN` as restrictive (reduce size / stand down),
  never as benign.

## Emission cadence

Each module declares one cadence token: `per_event | per_bar | per_snapshot`
(see glossary, appendix h). The cadence is fixed per module and declared in §S0
and §1.5. A module emits at most one `SignalVector` per cadence tick per symbol;
re-emission with no new input is forbidden (consumers hold the last record).

## Doctrine line (for §S0 "may/must-NOT")

> **May:** emit `SignalVector` records per this schema. **Must-NOT:** emit
> orders, order intents, prices, share counts, or notionals; call a broker; or
> mutate shared state outside the documented `state` object.
