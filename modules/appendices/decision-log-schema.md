---
appendix: decision-log-schema
appendix_version: 1.0.0
title: Decision-log (audit) schema
scope: global — referenced by every chapter's Compliance sub-block (§S2/§T2-Robustness)
---

# Appendix G — Decision-log schema (compliance audit log)

Every module writes a decision record for each material action (signal emission,
order intent, cancel-replace, gate veto, kill-switch transition, compliance
block). The log is append-only, tamper-evident (hash-chained per chapter's
runbook), and retained per the chapter's data-rights row.

```python
@dataclass(frozen=True)
class DecisionRecord:
    record_ts: int       # int64 ns UTC — when the record was written
    module_id: str       # e.g. "S001"; module version pinned in a header field
    module_version: str  # semver of the emitting module
    event_ref: str       # triggering event/bar id or "S<nnn>@<computed_at_ns>"
    action: str          # EMIT_SIGNAL | EMIT_INTENT | CANCEL | REPLACE |
                         # GATE_VETO | KILL_TRIP | KILL_REARM | COMPLIANCE_BLOCK
    inputs_hash: str     # sha256 of the canonical input slice used
    params_hash: str     # sha256 of the Config actually in force
    outcome: str         # the decision taken (direction, qty, veto reason code)
    state_before: str    # module-state before the action
    state_after: str     # module-state after the action
    prev_hash: str       # hash of the previous record (hash chain)
```

## Requirements

- **Write-once:** records are never edited or deleted. Corrections are new
  records with `action = CORRECTION` referencing the original.
- **One record per intent:** every `OrderTicket` carries its `ticket_id` in
  `event_ref`; cancel-replace logs both the cancel and the new intent with the
  `replaces` link in `outcome`.
- **Vetoes logged too:** a gate veto or compliance block is a record with
  `action = GATE_VETO | COMPLIANCE_BLOCK` and the rule code in `outcome` —
  "no trade" is a decision and is audited like one.
- **Kill transitions:** `KILL_TRIP` and `KILL_REARM` records include the
  triggering condition and the re-arm checklist result.
- **Retention:** minimum retention and storage location declared per chapter in
  the Compliance sub-block; default 7 years for order-intent records
  `[default]`.
- **Replayability:** given the logged `inputs_hash` and `params_hash`, the
  module's `test_cmd` fixture must be able to reproduce the decision
  (deterministic under the pinned `seed`).
