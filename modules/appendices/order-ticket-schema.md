---
appendix: order-ticket-schema
appendix_version: 1.0.0
title: OrderTicket schema (intents only)
scope: global — every T-module's §T0 contract; S-modules never emit this
---

# Appendix C — OrderTicket schema (intents only)

**Doctrine:** strategies emit *intentions only*; execution/broker layers create
orders. A T-module emits `OrderTicket` intents. It never sends orders, never
holds exchange sessions, never mutates order state on the wire.

```python
@dataclass(frozen=True)
class OrderTicket:
    symbol: str        # canonical ticker, exchange-qualified
    side: str          # BUY | SELL | SHORT — intent, not a wire order
    qty: int           # shares (integer; > 0)
    limit: float | None  # limit price; None = marketable intent
    tif: str           # DAY | IOC | FOK | GTC | OPG | CLS
    ticket_id: str     # module-generated UUID; idempotency key
    parent_signal: str # "S<nnn>@<computed_at_ns>" — full provenance
    intent_ts: int     # int64 ns UTC — when the intent was emitted
    state: str         # intent-side tracking state (below); brokers own wire state
```

## Child-order state machine (intent-side mirror)

The module tracks the *intent-side* state of each ticket; the broker owns the
wire truth. States:

```
NEW → WORKING → FILLED
              ↘ CANCELLED
              ↘ PARTIAL (then → FILLED or → CANCELLED)
```

- `NEW`: emitted, not yet acknowledged by the broker adapter.
- `WORKING`: acknowledged; may be partially filled.
- `PARTIAL`: ≥1 partial fill reported, remainder still working.
- `FILLED` / `CANCELLED`: terminal. A ticket in a terminal state never
  re-enters the machine; a new intent is a new `ticket_id`.

Transition rules (module side):
- `NEW → WORKING` only on broker acknowledgment containing this `ticket_id`.
- Any state → `CANCELLED` on kill-switch TRIP, compliance veto, or explicit
  cancel intent; cancels are idempotent (duplicate cancels are no-ops).
- Timeout without acknowledgment → `CANCELLED` + alert (never re-sent under
  the same `ticket_id`; re-issue with a new `ticket_id` only).

## Partial-fill policy

- A partial fill updates the *remaining* quantity of the same ticket; it does
  not spawn a child ticket. `PARTIAL` is a reporting state, not a new intent.
- Fill allocation across multiple tickets for the same symbol: oldest
  `intent_ts` first (FIFO), documented per chapter in the §T2 execution table.
- Overfill beyond `qty` is a broker-adapter defect: halt the module to
  `UNKNOWN`, alert, reconcile against the broker ledger before re-arming.

## Cancel-replace rules

- No in-place mutation: cancel-replace = cancel old `ticket_id` (→ `CANCELLED`)
  + emit a new ticket with a new `ticket_id`, carrying
  `parent_signal` and a `replaces: <old_ticket_id>` annotation in the module's
  decision log.
- A replace is forbidden while the old ticket is `FILLED`; allowed from
  `NEW`/`WORKING`/`PARTIAL` (remaining quantity only).
- Price improvement replaces and quantity changes both go through
  cancel-replace — never by editing an in-flight ticket.

## T-module doctrine line (for §T0 "may/must-NOT")

> **May:** emit `OrderTicket` intents per this schema; track intent-side state;
> issue cancel-replace via new tickets. **Must-NOT:** place orders on any venue,
> hold broker/exchange sessions, net intents into orders inside the strategy, or
> treat the intent-side state machine as broker wire truth.
