# Deep-dive chapter templates (draft v0 — planner to refine)

## Per-SIGNAL chapter (S001–S100)
1. One-line verdict: what it is, when it works, when it dies.
2. How it works — plain human explanation (no jargon without definition).
3. The math — exact formula, notation, parameter choices, lookbacks, normalization.
4. Worked example — step-by-step numbers on a small synthetic tape (CLEARLY labeled synthetic), table + generated chart PNG.
5. Strategies that use this signal — list with one-line role each, cross-refs to T-numbers.
6. Data required — exact fields, granularity, collection method (feed/API), code sketch, storage/day estimate.
7. Local build on M5 Max / 128GB — feasibility, throughput estimate, stack options (Python+polars, Rust, kdb-style), marginal cost vs sunk hardware, build time estimate.
8. Buy vs build — vendors with indicative pricing, what buying gains/loses; verdict.
9. Success ratio / efficacy — what papers and practitioners report, AFTER-COST honesty, regimes where it fails.
10. Failure modes & pitfalls — lookahead, staleness, crowding, cost blowups.
11. Visuals — mermaid data-flow diagram + worked-example chart PNG.
12. Sources — papers, docs, URLs.

## Per-STRATEGY chapter (T001–T100)
1. One-line verdict: style, edge source, typical holding period.
2. Full mechanics — entry, exit, position sizing, risk limits, cost model.
3. Signals it consumes — cross-refs to S-numbers, how each is weighted.
4. Worked example — numbers + P&L/equity sketch chart (synthetic, labeled).
5. Data & infra — what must run daily/intraday; M5 Max feasibility and cost.
6. Buy vs build — platforms (QuantConnect, Composer, vendors), indicative pricing, verdict.
7. Success ratio evidence — published Sharpe/returns, capacity, decay notes, after-cost honesty.
8. Failure modes — regime breaks, crowding, latency assumptions.
9. Visuals — mermaid strategy-flow diagram + example chart PNG.
10. Sources.

## Cost-model conventions (M5 Max, 128GB unified memory)
- Hardware treated as sunk; report marginal cost (electricity ~$0) + engineering time.
- Throughput estimates: rows/sec for polars/Python and Rust; memory footprint for 1 day of L1/L2 data per symbol.
- Vendor prices marked "indicative — verify before budgeting".
- Never present synthetic worked examples as real market data.
