---
appendix: chain-snapshot-schema
appendix_version: 1.0.0
title: ChainSnapshot schema (options extension)
scope: global — conditional; used only by options-extension modules (conditional on §0 domain = options)
---

# Appendix D — ChainSnapshot schema (options extension)

Used only by modules whose `§0` front-matter declares `domain: options`.
Non-options modules must not reference this appendix.

```python
@dataclass(frozen=True)
class OptionQuote:
    contract: str      # OCC symbology, e.g. "AAPL  260918C00230000"
    underlying: str    # canonical ticker
    expiry: str        # YYYY-MM-DD
    strike: float
    right: str         # C | P
    bid: float; ask: float; bid_sz: int; ask_sz: int
    iv: float | None   # implied vol, decimal; None if not computable
    delta: float | None; gamma: float | None
    theta: float | None; vega: float | None
    open_interest: int; volume: int

@dataclass(frozen=True)
class ChainSnapshot:
    underlying: str
    snapshot_ts: int   # int64 ns UTC — event_ts of the newest quote in the snapshot
    asof_ts: int       # int64 ns UTC — when we assembled the snapshot
    spot: float        # underlying reference price
    quotes: list[OptionQuote]  # one record per listed contract
    dividends: list[tuple[str, float]]  # (ex_date, amount) known at snapshot
    rate_curve: str    # identifier of the rate curve used (pinned version)
    is_partial: bool   # true if any listed contract is missing/quote-stale
```

## Rules

- `snapshot_ts` = newest constituent `event_ts`; causality for options modules
  is anchored on `snapshot_ts` under the same t→t+1 discipline (appendix e).
- Greeks are model outputs, not market data: the pricing model and its version
  pin are declared in the module's §T0 (Pricing & Greeks block); never restate
  the model elsewhere in the file.
- `is_partial = true` if any contract in the listed chain lacks a quote newer
  than the module's `staleness_ttl` → module-state `DEGRADED`; if the
  at-the-money ±2-strike band is stale → `UNKNOWN` (F1).
- No interpolation of missing strikes/expiries: missing contracts are absent
  from `quotes`, never filled in.
- Expiry/assignment handling (exercise, pin risk, early assignment) is module
  content under the conditional "Expiry & assignment" block; settlement
  conventions (AM/PM, cash/physical) are declared per chapter in §0 domain.
